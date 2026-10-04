import pytest
from backend.app.db.clinic_db import (
    ClinicDB,
    SlotAlreadyBookedError,
    PatientNotFoundError,
    DoctorNotFoundError,
    InvalidSlotError,
)
from backend.app.tools.executor import ToolExecutor, ToolExecutionError


@pytest.fixture
def db():
    instance = ClinicDB()
    instance.reset()
    return instance


@pytest.fixture
def executor(db):
    return ToolExecutor(db)


def test_search_slots_normal_day(executor):
    # 2026-10-03 is Saturday. Dr. Rao works 09:00 to 13:00 (15 min intervals).
    # ap_0006 is 09:15-09:30 and ap_0007 is 09:45-10:00.
    res = executor.execute("search_slots", {"doctor_id": "dr_rao", "date": "2026-10-03"})
    assert res["success"] is True
    slots = res["slots"]
    assert "09:00" in slots
    assert "09:30" in slots
    assert "09:15" not in slots  # Occupied by ap_0006
    assert "09:45" not in slots  # Occupied by ap_0007


def test_search_slots_sunday_closed(executor):
    # 2026-10-04 is Sunday. No doctor works.
    res = executor.execute("search_slots", {"doctor_id": "dr_rao", "date": "2026-10-04"})
    assert res["success"] is True
    assert res["slots"] == []


def test_search_slots_clinic_holiday(executor):
    # 2026-10-02 is clinic holiday.
    res = executor.execute("search_slots", {"doctor_id": "dr_rao", "date": "2026-10-02"})
    assert res["success"] is True
    assert res["slots"] == []


def test_search_slots_doctor_on_leave(executor):
    # Dr. Sethi is on leave 2026-10-05 to 2026-10-07.
    res = executor.execute("search_slots", {"doctor_id": "dr_sethi", "date": "2026-10-05"})
    assert res["success"] is True
    assert res["slots"] == []


def test_lookup_patient_ambiguous(executor):
    # "Sharma" matches Rajesh Kumar Sharma, R. K. Sharma, Rajesh Sharma.
    res = executor.execute("lookup_patient", {"name": "Sharma"})
    assert res["success"] is True
    assert res["ambiguous"] is True
    assert res["count"] == 3
    assert res["patient"] is None


def test_lookup_patient_unambiguous(executor):
    res = executor.execute("lookup_patient", {"phone": "9812200311"})
    assert res["success"] is True
    assert res["ambiguous"] is False
    assert res["patient"]["name"] == "Harpreet Singh"
    assert res["patient"]["id"] == "pt_0013"


def test_book_appointment_success(executor):
    res = executor.execute(
        "book_appointment",
        {
            "patient_id": "pt_0013",
            "doctor_id": "dr_rao",
            "date": "2026-10-03",
            "start": "09:00",
        },
    )
    assert res["success"] is True
    assert res["appointment_id"].startswith("ap_")
    assert res["appointment"]["status"] == "booked"


def test_book_appointment_rejects_already_booked(executor):
    # ap_0001 is booked at 09:30 on 2026-10-01 for Dr. Rao
    res = executor.execute(
        "book_appointment",
        {
            "patient_id": "pt_0014",
            "doctor_id": "dr_rao",
            "date": "2026-10-01",
            "start": "09:30",
        },
    )
    assert res["success"] is False
    assert res["code"] == "SlotAlreadyBookedError"


def test_reschedule_appointment(executor):
    res = executor.execute(
        "reschedule_appointment",
        {
            "appointment_id": "ap_0001",
            "new_date": "2026-10-03",
            "new_start": "10:00",
        },
    )
    assert res["success"] is True
    assert res["appointment"]["date"] == "2026-10-03"
    assert res["appointment"]["start"] == "10:00"


def test_cancel_appointment(executor):
    res = executor.execute("cancel_appointment", {"appointment_id": "ap_0002"})
    assert res["success"] is True
    assert res["status"] == "cancelled"


def test_escalate_to_human_valid_and_invalid(executor):
    res_valid = executor.execute("escalate_to_human", {"reason": "clinical_urgent", "detail": "Chest pain"})
    assert res_valid["success"] is True
    assert res_valid["escalated"] is True

    res_invalid = executor.execute("escalate_to_human", {"reason": "random_unsupported_reason"})
    assert res_invalid["success"] is False
    assert res_invalid["code"] == "INVALID_REASON"
