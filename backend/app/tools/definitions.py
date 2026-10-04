from __future__ import annotations

from typing import Any, Dict, List

TOOL_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "name": "search_slots",
        "description": "Find available appointment slots for a specific doctor on a given date. Returns list of available slot start times.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "doctor_id": {
                    "type": "STRING",
                    "description": "Doctor identifier (e.g. 'dr_rao' for Dr. Anjali Rao, 'dr_sethi' for Dr. Vikram Sethi)",
                },
                "date": {
                    "type": "STRING",
                    "description": "Date in YYYY-MM-DD format (e.g. '2026-10-03')",
                },
                "window": {
                    "type": "STRING",
                    "description": "Optional time of day filter ('morning', 'evening', 'afternoon', 'subah', 'shaam')",
                },
            },
            "required": ["doctor_id", "date"],
        },
    },
    {
        "name": "book_appointment",
        "description": "Book a new appointment for a patient with a doctor at an available slot.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "patient_id": {
                    "type": "STRING",
                    "description": "Verified patient identifier (e.g. 'pt_0013')",
                },
                "doctor_id": {
                    "type": "STRING",
                    "description": "Doctor identifier (e.g. 'dr_rao' or 'dr_sethi')",
                },
                "date": {
                    "type": "STRING",
                    "description": "Appointment date in YYYY-MM-DD format",
                },
                "start": {
                    "type": "STRING",
                    "description": "Slot start time in HH:MM format (e.g. '09:30')",
                },
            },
            "required": ["patient_id", "doctor_id", "date", "start"],
        },
    },
    {
        "name": "reschedule_appointment",
        "description": "Reschedule an existing active appointment to a new date and start time.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "new_date": {
                    "type": "STRING",
                    "description": "Target rescheduled date in YYYY-MM-DD format",
                },
                "new_start": {
                    "type": "STRING",
                    "description": "Target start time in HH:MM format",
                },
                "appointment_id": {
                    "type": "STRING",
                    "description": "ID of the appointment to reschedule (e.g. 'ap_0001')",
                },
                "patient_id": {
                    "type": "STRING",
                    "description": "Patient ID if appointment ID is not known",
                },
                "doctor_id": {
                    "type": "STRING",
                    "description": "Optional doctor ID if changing doctor or confirming",
                },
            },
            "required": ["new_date", "new_start"],
        },
    },
    {
        "name": "cancel_appointment",
        "description": "Cancel an existing active appointment.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "appointment_id": {
                    "type": "STRING",
                    "description": "ID of the appointment to cancel (e.g. 'ap_0002')",
                },
                "patient_id": {
                    "type": "STRING",
                    "description": "Patient ID whose active appointment is to be cancelled",
                },
            },
        },
    },
    {
        "name": "lookup_patient",
        "description": "Look up patient records by name and/or phone number. Returns all candidates. If multiple match, returns candidates without guessing.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "name": {
                    "type": "STRING",
                    "description": "Full or partial name of the patient",
                },
                "phone": {
                    "type": "STRING",
                    "description": "10-digit phone number of the patient",
                },
            },
        },
    },
    {
        "name": "escalate_to_human",
        "description": "Escalate conversation to human staff when outside front-desk authority, safety risk, emergency, or ambiguous.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "reason": {
                    "type": "STRING",
                    "enum": [
                        "clinical_urgent",
                        "medical_advice",
                        "not_authorised",
                        "ambiguous_patient",
                        "out_of_scope",
                    ],
                    "description": "Standardized reason for escalation",
                },
                "detail": {
                    "type": "STRING",
                    "description": "Brief context explaining why escalation occurred",
                },
            },
            "required": ["reason"],
        },
    },
]
