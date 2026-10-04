import concurrent.futures
import pytest
from backend.app.db.clinic_db import ClinicDB, SlotAlreadyBookedError


def test_concurrency_double_booking_prevention():
    """
    Verify that when multiple concurrent requests race for the exact same slot,
    only one succeeds, and the other racing requests fail.
    """
    db = ClinicDB()
    db.reset()

    # Slot to race for: Dr. Rao, 2026-10-03 at 11:00
    doctor_id = "dr_rao"
    date = "2026-10-03"
    start = "11:00"

    # Patient IDs for 10 concurrent requests
    patient_ids = [
        "pt_0013", "pt_0014", "pt_0015", "pt_0016", "pt_0017",
        "pt_0020", "pt_0021", "pt_0022", "pt_0023", "pt_0025",
    ]

    successes = []
    failures = []

    def attempt_booking(pid: str):
        try:
            res = db.book_appointment(
                patient_id=pid,
                doctor_id=doctor_id,
                date=date,
                start=start,
            )
            return ("SUCCESS", res)
        except SlotAlreadyBookedError as e:
            return ("FAILED_ALREADY_BOOKED", str(e))
        except Exception as e:
            return ("FAILED_OTHER", str(e))

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(attempt_booking, pid) for pid in patient_ids]
        for f in concurrent.futures.as_completed(futures):
            status, payload = f.result()
            if status == "SUCCESS":
                successes.append(payload)
            else:
                failures.append(payload)

    # EXACTLY ONE request must succeed!
    assert len(successes) == 1, f"Expected exactly 1 success, got {len(successes)}"
    # All 9 other requests must fail
    assert len(failures) == 9, f"Expected 9 failures, got {len(failures)}"

    # Check that in DB there is only 1 booking for this doctor/date/slot
    matching_in_db = [
        apt for apt in db.appointments
        if apt["doctor_id"] == doctor_id and apt["date"] == date and apt["start"] == start and apt["status"] == "booked"
    ]
    assert len(matching_in_db) == 1
