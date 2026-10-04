from __future__ import annotations

from typing import Any, Dict, List, Optional
from backend.app.db.clinic_db import (
    ClinicDB,
    ClinicDBError,
    SlotAlreadyBookedError,
    PatientNotFoundError,
    DoctorNotFoundError,
    InvalidSlotError,
    AppointmentNotFoundError,
)
from backend.app.schemas.contracts import ToolCallRecord


class ToolExecutionError(Exception):
    def __init__(self, message: str, code: str = "TOOL_ERROR"):
        super().__init__(message)
        self.message = message
        self.code = code


class ToolExecutor:
    """
    Executes tool calls strictly against ClinicDB (Ground Truth).
    Never calls an LLM.
    Enforces deterministic validation, audit history, and actionable errors.
    """

    VALID_ESCALATION_REASONS = {
        "clinical_urgent",
        "medical_advice",
        "not_authorised",
        "ambiguous_patient",
        "out_of_scope",
    }

    def __init__(self, db: ClinicDB):
        self.db = db
        self.call_history: List[ToolCallRecord] = []

    def execute(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatch a tool call by name and record it."""
        try:
            if tool_name == "search_slots":
                result = self._exec_search_slots(arguments)
            elif tool_name == "book_appointment":
                result = self._exec_book_appointment(arguments)
            elif tool_name == "reschedule_appointment":
                result = self._exec_reschedule_appointment(arguments)
            elif tool_name == "cancel_appointment":
                result = self._exec_cancel_appointment(arguments)
            elif tool_name == "lookup_patient":
                result = self._exec_lookup_patient(arguments)
            elif tool_name == "escalate_to_human":
                result = self._exec_escalate_to_human(arguments)
            else:
                result = {
                    "success": False,
                    "error": f"Unknown tool '{tool_name}'. Available tools: search_slots, book_appointment, reschedule_appointment, cancel_appointment, lookup_patient, escalate_to_human.",
                    "code": "UNKNOWN_TOOL",
                }
        except ToolExecutionError as e:
            result = {"success": False, "error": e.message, "code": e.code}
        except ClinicDBError as e:
            result = {"success": False, "error": str(e), "code": type(e).__name__}
        except Exception as e:
            result = {"success": False, "error": f"Invalid tool arguments: {str(e)}", "code": "ARGUMENT_ERROR"}

        record = ToolCallRecord(name=tool_name, arguments=arguments, output=result)
        self.call_history.append(record)
        return result

    def _exec_search_slots(self, args: Dict[str, Any]) -> Dict[str, Any]:
        doctor_id = args.get("doctor_id")
        date = args.get("date")
        window = args.get("window")

        if not doctor_id:
            raise ToolExecutionError("Missing required argument 'doctor_id'", "MISSING_ARGUMENT")
        if not date:
            raise ToolExecutionError("Missing required argument 'date'", "MISSING_ARGUMENT")

        slots = self.db.search_slots(doctor_id=str(doctor_id), date=str(date), window=window)
        return {
            "success": True,
            "doctor_id": doctor_id,
            "date": date,
            "slots": slots,
            "count": len(slots),
        }

    def _exec_book_appointment(self, args: Dict[str, Any]) -> Dict[str, Any]:
        patient_id = args.get("patient_id")
        doctor_id = args.get("doctor_id")
        date = args.get("date")
        start = args.get("start")

        missing = [f for f in ["patient_id", "doctor_id", "date", "start"] if not args.get(f)]
        if missing:
            raise ToolExecutionError(f"Missing required booking arguments: {', '.join(missing)}", "MISSING_ARGUMENT")

        apt = self.db.book_appointment(
            patient_id=str(patient_id),
            doctor_id=str(doctor_id),
            date=str(date),
            start=str(start),
        )
        return {
            "success": True,
            "appointment": apt,
            "appointment_id": apt["id"],
            "patient_id": apt["patient_id"],
            "doctor_id": apt["doctor_id"],
            "date": apt["date"],
            "start": apt["start"],
            "end": apt["end"],
        }

    def _exec_reschedule_appointment(self, args: Dict[str, Any]) -> Dict[str, Any]:
        new_date = args.get("new_date")
        new_start = args.get("new_start")
        appointment_id = args.get("appointment_id")
        patient_id = args.get("patient_id")
        doctor_id = args.get("doctor_id")

        if not new_date or not new_start:
            raise ToolExecutionError("Rescheduling requires 'new_date' and 'new_start'", "MISSING_ARGUMENT")
        if not appointment_id and not patient_id:
            raise ToolExecutionError("Either 'appointment_id' or 'patient_id' must be provided to reschedule", "MISSING_ARGUMENT")

        apt = self.db.reschedule_appointment(
            new_date=str(new_date),
            new_start=str(new_start),
            appointment_id=str(appointment_id) if appointment_id else None,
            patient_id=str(patient_id) if patient_id else None,
            doctor_id=str(doctor_id) if doctor_id else None,
        )
        return {
            "success": True,
            "appointment": apt,
            "appointment_id": apt["id"],
            "patient_id": apt["patient_id"],
            "doctor_id": apt["doctor_id"],
            "date": apt["date"],
            "start": apt["start"],
            "end": apt["end"],
        }

    def _exec_cancel_appointment(self, args: Dict[str, Any]) -> Dict[str, Any]:
        appointment_id = args.get("appointment_id")
        patient_id = args.get("patient_id")

        if not appointment_id and not patient_id:
            raise ToolExecutionError("Either 'appointment_id' or 'patient_id' must be provided to cancel", "MISSING_ARGUMENT")

        apt = self.db.cancel_appointment(
            appointment_id=str(appointment_id) if appointment_id else None,
            patient_id=str(patient_id) if patient_id else None,
        )
        return {
            "success": True,
            "appointment_id": apt["id"],
            "patient_id": apt["patient_id"],
            "status": "cancelled",
        }

    def _exec_lookup_patient(self, args: Dict[str, Any]) -> Dict[str, Any]:
        name = args.get("name")
        phone = args.get("phone")

        if not name and not phone:
            raise ToolExecutionError("Patient lookup requires at least 'name' or 'phone'", "MISSING_ARGUMENT")

        lookup_res = self.db.lookup_patient(
            name=str(name) if name else None,
            phone=str(phone) if phone else None,
        )
        return {
            "success": True,
            "matches": lookup_res["matches"],
            "count": lookup_res["count"],
            "ambiguous": lookup_res["ambiguous"],
            "patient": lookup_res["patient"],
        }

    def _exec_escalate_to_human(self, args: Dict[str, Any]) -> Dict[str, Any]:
        reason = args.get("reason")
        detail = args.get("detail")

        if not reason:
            raise ToolExecutionError("Escalation requires 'reason'", "MISSING_ARGUMENT")
        if reason not in self.VALID_ESCALATION_REASONS:
            raise ToolExecutionError(
                f"Invalid escalation reason '{reason}'. Allowed: {sorted(list(self.VALID_ESCALATION_REASONS))}",
                "INVALID_REASON",
            )

        return {
            "success": True,
            "escalated": True,
            "reason": reason,
            "detail": detail,
        }
