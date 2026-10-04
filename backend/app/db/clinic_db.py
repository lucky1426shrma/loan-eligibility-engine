from __future__ import annotations

import copy
import json
import os
import pathlib
import threading
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple


class ClinicDBError(Exception):
    """Base exception for clinic database errors."""
    pass


class SlotAlreadyBookedError(ClinicDBError):
    """Raised when an attempt is made to book an already occupied slot."""
    pass


class PatientNotFoundError(ClinicDBError):
    """Raised when a patient record is not found."""
    pass


class DoctorNotFoundError(ClinicDBError):
    """Raised when a doctor is not found."""
    pass


class InvalidSlotError(ClinicDBError):
    """Raised when a requested slot is invalid (holiday, leave, out of window)."""
    pass


class AppointmentNotFoundError(ClinicDBError):
    """Raised when an appointment is not found."""
    pass


WEEKDAY_MAP = {
    0: "Mon",
    1: "Tue",
    2: "Wed",
    3: "Thu",
    4: "Fri",
    5: "Sat",
    6: "Sun",
}


def _time_to_minutes(time_str: str) -> int:
    h, m = map(int, time_str.split(":"))
    return h * 60 + m


def _minutes_to_time(minutes: int) -> str:
    h = minutes // 60
    m = minutes % 60
    return f"{h:02d}:{m:02d}"


class ClinicDB:
    """
    Thread-safe, in-memory representation of the clinic state.
    Serves as the ground-truth layer against clinic.json.
    Never calls an LLM.
    """

    def __init__(self, json_path: Optional[str | pathlib.Path] = None):
        self._lock = threading.RLock()
        if json_path is None:
            # Look in parent directories for clinic.json
            current = pathlib.Path(__file__).resolve().parent
            for _ in range(4):
                candidate = current / "clinic.json"
                if candidate.is_file():
                    json_path = candidate
                    break
                current = current.parent
            if json_path is None:
                json_path = pathlib.Path("clinic.json")

        self.json_path = pathlib.Path(json_path).resolve()
        if not self.json_path.exists():
            raise FileNotFoundError(f"clinic.json not found at {self.json_path}")

        with open(self.json_path, "r", encoding="utf-8") as f:
            self._canonical_data = json.load(f)

        self._state: Dict[str, Any] = copy.deepcopy(self._canonical_data)

    def reset(self) -> None:
        """Reset state back to the original canonical clinic.json."""
        with self._lock:
            self._state = copy.deepcopy(self._canonical_data)

    def clone_fresh(self) -> "ClinicDB":
        """Returns a new independent instance starting from canonical clinic.json."""
        return ClinicDB(self.json_path)

    @property
    def clinic_info(self) -> Dict[str, Any]:
        with self._lock:
            return copy.deepcopy(self._state.get("clinic", {}))

    @property
    def reference_date(self) -> str:
        with self._lock:
            return self._state.get("clinic", {}).get("reference_date", "2026-10-01")

    @property
    def slot_minutes(self) -> int:
        with self._lock:
            return int(self._state.get("clinic", {}).get("slot_minutes", 15))

    @property
    def holidays(self) -> List[str]:
        with self._lock:
            return list(self._state.get("holidays", []))

    @property
    def doctors(self) -> List[Dict[str, Any]]:
        with self._lock:
            return copy.deepcopy(self._state.get("doctors", []))

    @property
    def patients(self) -> List[Dict[str, Any]]:
        with self._lock:
            return copy.deepcopy(self._state.get("patients", []))

    @property
    def appointments(self) -> List[Dict[str, Any]]:
        with self._lock:
            return copy.deepcopy(self._state.get("appointments", []))

    def get_doctor(self, doctor_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            for doc in self._state.get("doctors", []):
                if doc["id"].lower() == doctor_id.lower():
                    return copy.deepcopy(doc)
            return None

    def get_patient_by_id(self, patient_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            for pt in self._state.get("patients", []):
                if pt["id"].lower() == patient_id.lower():
                    return copy.deepcopy(pt)
            return None

    def get_appointment_by_id(self, appointment_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            for apt in self._state.get("appointments", []):
                if apt["id"].lower() == appointment_id.lower():
                    return copy.deepcopy(apt)
            return None

    def lookup_patient(
        self,
        name: Optional[str] = None,
        phone: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Search for patients by name and/or phone.
        Returns candidates, never guesses.
        """
        with self._lock:
            patients = self._state.get("patients", [])
            matches: List[Dict[str, Any]] = []

            clean_phone = "".join(filter(str.isdigit, phone)) if phone else None
            clean_name = name.strip().lower() if name else None

            for pt in patients:
                pt_phone = "".join(filter(str.isdigit, pt.get("phone", "")))
                pt_name = pt.get("name", "").strip().lower()

                phone_match = False
                name_match = False

                if clean_phone:
                    phone_match = (clean_phone == pt_phone) or (clean_phone in pt_phone)

                if clean_name:
                    # Token and substring matching
                    name_tokens = clean_name.split()
                    pt_tokens = pt_name.split()
                    
                    # Direct substring
                    if clean_name in pt_name:
                        name_match = True
                    # Check token overlap
                    elif any(t in pt_tokens for t in name_tokens):
                        name_match = True

                if clean_phone and clean_name:
                    if phone_match and name_match:
                        matches.append(copy.deepcopy(pt))
                elif clean_phone:
                    if phone_match:
                        matches.append(copy.deepcopy(pt))
                elif clean_name:
                    if name_match:
                        matches.append(copy.deepcopy(pt))

            # Edge case: If phone was supplied and matched multiple patients (e.g. family/guardian share phone),
            # but name was also supplied and narrowed it, we already filtered above.
            # If phone matched multiple and name wasn't supplied or didn't distinguish, return all candidates.
            is_ambiguous = len(matches) > 1
            single_patient = matches[0] if len(matches) == 1 else None

            return {
                "matches": matches,
                "count": len(matches),
                "ambiguous": is_ambiguous,
                "patient": single_patient,
            }

    def search_slots(
        self,
        doctor_id: str,
        date: str,
        window: Optional[str] = None,
    ) -> List[str]:
        """
        Return free slots (start times) for a doctor on a specific date.
        Respects clinic holidays, Sundays, doctor leave, operating windows, and existing bookings.
        """
        with self._lock:
            doc = self.get_doctor(doctor_id)
            if not doc:
                raise DoctorNotFoundError(f"Doctor '{doctor_id}' does not exist.")

            # Validate date format
            try:
                dt = datetime.strptime(date, "%Y-%m-%d")
            except ValueError:
                raise ValueError(f"Invalid date format '{date}', expected YYYY-MM-DD.")

            # Check clinic holidays
            if date in self._state.get("holidays", []):
                return []

            # Check Sunday (no doctor works Sunday)
            weekday_num = dt.weekday()
            weekday_str = WEEKDAY_MAP.get(weekday_num, "")
            if weekday_str == "Sun":
                return []

            # Check doctor leave dates
            if date in doc.get("leave_dates", []):
                return []

            slot_duration = self.slot_minutes
            all_slots: set[str] = set()

            # Find matching doctor windows for this weekday
            doc_windows = [w for w in doc.get("windows", []) if w.get("day") == weekday_str]
            if not doc_windows:
                return []

            for w in doc_windows:
                start_min = _time_to_minutes(w["start"])
                end_min = _time_to_minutes(w["end"])

                curr = start_min
                while curr + slot_duration <= end_min:
                    all_slots.add(_minutes_to_time(curr))
                    curr += slot_duration

            # Filter out existing booked appointments
            booked_slots: set[str] = set()
            for apt in self._state.get("appointments", []):
                if (
                    apt.get("doctor_id") == doc["id"]
                    and apt.get("date") == date
                    and apt.get("status") == "booked"
                ):
                    booked_slots.add(apt.get("start"))

            free_slots = sorted(list(all_slots - booked_slots))

            # Apply window filter if requested (e.g. "morning", "evening", "subah", "shaam")
            if window:
                w_lower = window.lower()
                if "morn" in w_lower or "subah" in w_lower:
                    free_slots = [s for s in free_slots if _time_to_minutes(s) < 13 * 60]
                elif "even" in w_lower or "shaam" in w_lower:
                    free_slots = [s for s in free_slots if _time_to_minutes(s) >= 16 * 60]
                elif "afternoon" in w_lower or "dopahar" in w_lower:
                    free_slots = [
                        s for s in free_slots if 12 * 60 <= _time_to_minutes(s) < 16 * 60
                    ]

            return free_slots

    def book_appointment(
        self,
        patient_id: str,
        doctor_id: str,
        date: str,
        start: str,
    ) -> Dict[str, Any]:
        """
        Creates an appointment in a free slot atomically.
        Guarantees that a slot cannot be double-booked even under concurrent calls.
        """
        with self._lock:
            # Validate patient
            patient = self.get_patient_by_id(patient_id)
            if not patient:
                raise PatientNotFoundError(f"Patient '{patient_id}' not found.")

            # Validate doctor
            doctor = self.get_doctor(doctor_id)
            if not doctor:
                raise DoctorNotFoundError(f"Doctor '{doctor_id}' not found.")

            # Validate date format
            try:
                dt = datetime.strptime(date, "%Y-%m-%d")
            except ValueError:
                raise ValueError(f"Invalid date format '{date}', expected YYYY-MM-DD.")

            # Check clinic holiday
            if date in self._state.get("holidays", []):
                raise InvalidSlotError(f"Clinic is closed on {date} (public holiday).")

            # Check Sunday
            if WEEKDAY_MAP.get(dt.weekday()) == "Sun":
                raise InvalidSlotError(f"Clinic is closed on Sundays ({date}).")

            # Check doctor leave
            if date in doctor.get("leave_dates", []):
                raise InvalidSlotError(
                    f"Dr. {doctor.get('name')} is on leave on {date}."
                )

            # Check if start slot is within doctor windows
            weekday_str = WEEKDAY_MAP.get(dt.weekday(), "")
            doc_windows = [w for w in doctor.get("windows", []) if w.get("day") == weekday_str]
            slot_min = _time_to_minutes(start)
            slot_end_min = slot_min + self.slot_minutes

            slot_in_window = False
            for w in doc_windows:
                w_start = _time_to_minutes(w["start"])
                w_end = _time_to_minutes(w["end"])
                if slot_min >= w_start and slot_end_min <= w_end:
                    slot_in_window = True
                    break

            if not slot_in_window:
                raise InvalidSlotError(
                    f"Slot {start} is outside working hours for Dr. {doctor.get('name')} on {weekday_str}."
                )

            # Atomic check: check for conflicting booked appointment
            for apt in self._state.get("appointments", []):
                if (
                    apt.get("doctor_id") == doctor["id"]
                    and apt.get("date") == date
                    and apt.get("start") == start
                    and apt.get("status") == "booked"
                ):
                    raise SlotAlreadyBookedError(
                        f"Slot {start} on {date} for Dr. {doctor.get('name')} is already booked."
                    )

            # Generate next appointment ID
            existing_ids = [apt.get("id", "") for apt in self._state.get("appointments", [])]
            max_num = 0
            for aid in existing_ids:
                if aid.startswith("ap_"):
                    try:
                        max_num = max(max_num, int(aid[3:]))
                    except ValueError:
                        pass
            new_id = f"ap_{max_num + 1:04d}"
            end_time = _minutes_to_time(slot_end_min)

            new_apt = {
                "id": new_id,
                "patient_id": patient["id"],
                "doctor_id": doctor["id"],
                "date": date,
                "start": start,
                "end": end_time,
                "status": "booked",
            }

            self._state.setdefault("appointments", []).append(new_apt)
            return copy.deepcopy(new_apt)

    def reschedule_appointment(
        self,
        new_date: str,
        new_start: str,
        appointment_id: Optional[str] = None,
        patient_id: Optional[str] = None,
        doctor_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Moves an existing appointment to a new slot atomically.
        """
        with self._lock:
            target_apt: Optional[Dict[str, Any]] = None

            if appointment_id:
                for apt in self._state.get("appointments", []):
                    if apt.get("id") == appointment_id:
                        target_apt = apt
                        break
            elif patient_id:
                for apt in self._state.get("appointments", []):
                    if apt.get("patient_id") == patient_id and apt.get("status") == "booked":
                        target_apt = apt
                        break

            if not target_apt:
                raise AppointmentNotFoundError(
                    f"No active appointment found for ID '{appointment_id}' / patient '{patient_id}'."
                )

            if target_apt.get("status") != "booked":
                raise InvalidSlotError(
                    f"Appointment '{target_apt.get('id')}' is {target_apt.get('status')}, cannot reschedule."
                )

            target_doctor_id = doctor_id or target_apt.get("doctor_id")
            doctor = self.get_doctor(target_doctor_id)
            if not doctor:
                raise DoctorNotFoundError(f"Doctor '{target_doctor_id}' not found.")

            # Validate new date & time
            try:
                dt = datetime.strptime(new_date, "%Y-%m-%d")
            except ValueError:
                raise ValueError(f"Invalid date format '{new_date}', expected YYYY-MM-DD.")

            if new_date in self._state.get("holidays", []):
                raise InvalidSlotError(f"Clinic is closed on {new_date} (public holiday).")

            if WEEKDAY_MAP.get(dt.weekday()) == "Sun":
                raise InvalidSlotError(f"Clinic is closed on Sundays ({new_date}).")

            if new_date in doctor.get("leave_dates", []):
                raise InvalidSlotError(
                    f"Dr. {doctor.get('name')} is on leave on {new_date}."
                )

            weekday_str = WEEKDAY_MAP.get(dt.weekday(), "")
            doc_windows = [w for w in doctor.get("windows", []) if w.get("day") == weekday_str]
            slot_min = _time_to_minutes(new_start)
            slot_end_min = slot_min + self.slot_minutes

            slot_in_window = False
            for w in doc_windows:
                w_start = _time_to_minutes(w["start"])
                w_end = _time_to_minutes(w["end"])
                if slot_min >= w_start and slot_end_min <= w_end:
                    slot_in_window = True
                    break

            if not slot_in_window:
                raise InvalidSlotError(
                    f"Slot {new_start} is outside working hours for Dr. {doctor.get('name')} on {weekday_str}."
                )

            # Atomic check for collision on new slot (excluding current appointment itself)
            for apt in self._state.get("appointments", []):
                if apt.get("id") == target_apt.get("id"):
                    continue
                if (
                    apt.get("doctor_id") == doctor["id"]
                    and apt.get("date") == new_date
                    and apt.get("start") == new_start
                    and apt.get("status") == "booked"
                ):
                    raise SlotAlreadyBookedError(
                        f"Slot {new_start} on {new_date} for Dr. {doctor.get('name')} is already booked."
                    )

            target_apt["date"] = new_date
            target_apt["start"] = new_start
            target_apt["end"] = _minutes_to_time(slot_end_min)
            target_apt["doctor_id"] = doctor["id"]

            return copy.deepcopy(target_apt)

    def cancel_appointment(
        self,
        appointment_id: Optional[str] = None,
        patient_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Cancels an existing appointment atomically.
        """
        with self._lock:
            target_apt: Optional[Dict[str, Any]] = None

            if appointment_id:
                for apt in self._state.get("appointments", []):
                    if apt.get("id") == appointment_id:
                        target_apt = apt
                        break
            elif patient_id:
                for apt in self._state.get("appointments", []):
                    if apt.get("patient_id") == patient_id and apt.get("status") == "booked":
                        target_apt = apt
                        break

            if not target_apt:
                raise AppointmentNotFoundError(
                    f"No active appointment found for ID '{appointment_id}' / patient '{patient_id}'."
                )

            if target_apt.get("status") != "booked":
                raise InvalidSlotError(
                    f"Appointment '{target_apt.get('id')}' is already {target_apt.get('status')}."
                )

            target_apt["status"] = "cancelled"
            return copy.deepcopy(target_apt)


# Global singleton instance for server runtime
_global_db: Optional[ClinicDB] = None
_global_db_lock = threading.Lock()


def get_clinic_db() -> ClinicDB:
    global _global_db
    with _global_db_lock:
        if _global_db is None:
            _global_db = ClinicDB()
        return _global_db
