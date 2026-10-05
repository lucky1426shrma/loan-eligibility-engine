from __future__ import annotations

import json
import pathlib
import sys
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Ensure repo root is on sys.path
root_dir = pathlib.Path(__file__).resolve().parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from backend.app.schemas.contracts import AgentRunRequest, AgentRunResponse
from backend.app.db.clinic_db import get_clinic_db
from backend.app.agent.orchestrator import AgentOrchestrator

app = FastAPI(
    title="Sunrise Clinic - Front Desk Agent API",
    description="Python REST API exposing conversational agent with six tools over clinic schedule",
    version="1.0.0",
)

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

orchestrator = AgentOrchestrator()

# In-memory handoff resolution tracking
resolved_handoffs: set[str] = set()


@app.get("/health")
def health_check():
    db = get_clinic_db()
    return {
        "status": "healthy",
        "clinic": db.clinic_info.get("name", "Sunrise Clinic"),
        "reference_date": db.reference_date,
    }


@app.post("/agent/run", response_model=AgentRunResponse)
def run_agent(request: AgentRunRequest) -> AgentRunResponse:
    """
    Main evaluation endpoint satisfying schema.md contract.
    """
    try:
        response = orchestrator.process_conversation(request)
        return response
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent error processing conversation: {str(e)}",
        )


# =========================================================================
# Additional endpoints for the React Frontend UI
# =========================================================================

@app.get("/api/clinic")
def get_clinic_data():
    db = get_clinic_db()
    return {
        "clinic": db.clinic_info,
        "doctors": db.doctors,
        "holidays": db.holidays,
        "patients_count": len(db.patients),
        "appointments_count": len(db.appointments),
    }


def _load_all_scripts() -> List[Dict[str, Any]]:
    scripts: List[Dict[str, Any]] = []
    # Search in conversations and adversarial folders
    conv_dir = root_dir / "conversations"
    adv_dir = root_dir / "adversarial"

    dirs_to_check = [conv_dir, adv_dir]
    for d in dirs_to_check:
        if d.is_dir():
            for p in sorted(d.glob("*.json")):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        data["_path"] = str(p)
                        scripts.append(data)
                except Exception:
                    pass
    return scripts


@app.get("/api/conversations")
def list_conversations():
    scripts = _load_all_scripts()
    summaries = []
    for s in scripts:
        cid = s.get("id", "")
        # Run agent on script to get current outcome
        req = AgentRunRequest(
            conversation_id=cid,
            today=s.get("today", "2026-10-01"),
            turns=s.get("turns", []),
        )
        res = orchestrator.process_conversation(req)
        summaries.append({
            "id": cid,
            "description": s.get("description", ""),
            "today": s.get("today", "2026-10-01"),
            "turns_count": len(s.get("turns", [])),
            "terminal_state": res.terminal_state,
            "escalation_reason": res.escalation_reason,
            "tool_calls_count": len(res.tool_calls),
            "is_resolved": cid in resolved_handoffs,
        })
    return summaries


@app.get("/api/handoffs")
def get_handoff_queue():
    """
    Returns open handoffs for Screen 1 of the frontend.
    """
    scripts = _load_all_scripts()
    total_conversations = len(scripts)
    completed_by_agent = 0
    escalated_count = 0
    urgent_count = 0
    open_handoffs = []

    # Map timestamps for visual realism matching the UI mockup
    mock_times = {
        "cv_0011": "11:42",
        "cv_0009": "11:20",
        "cv_0007": "10:57",
        "cv_0010": "10:18",
        "adv_0003": "09:45",
        "adv_0002": "09:12",
    }

    for s in scripts:
        cid = s.get("id", "")
        req = AgentRunRequest(
            conversation_id=cid,
            today=s.get("today", "2026-10-01"),
            turns=s.get("turns", []),
        )
        res = orchestrator.process_conversation(req)

        if res.terminal_state in {"booked", "rescheduled", "cancelled"}:
            completed_by_agent += 1
        elif res.terminal_state == "escalated":
            escalated_count += 1
            if res.escalation_reason == "clinical_urgent":
                urgent_count += 1

            if cid not in resolved_handoffs:
                # Find caller's last or key utterance
                turns = s.get("turns", [])
                caller_said = turns[-1] if turns else ""
                for t in reversed(turns):
                    if any(w in t.lower() for w in ["dard", "dawai", "sharma", "cancel", "lakshmi", "crocin"]):
                        caller_said = t
                        break

                time_str = mock_times.get(cid, "10:30")
                open_handoffs.append({
                    "conversation_id": cid,
                    "caller_said": caller_said,
                    "reason": res.escalation_reason,
                    "time": time_str,
                    "terminal_state": res.terminal_state,
                })

    return {
        "metrics": {
            "conversations_today": total_conversations,
            "completed_by_agent": completed_by_agent,
            "completed_percentage": int((completed_by_agent / total_conversations) * 100) if total_conversations else 0,
            "escalated_total": escalated_count,
            "open_escalated_count": len(open_handoffs),
            "urgent_count": urgent_count,
        },
        "open_handoffs": open_handoffs,
    }


class ResolveHandoffRequest(BaseModel):
    resolution_notes: Optional[str] = "Resolved by human desk staff"


@app.post("/api/handoffs/{conversation_id}/resolve")
def resolve_handoff(conversation_id: str, body: Optional[ResolveHandoffRequest] = None):
    resolved_handoffs.add(conversation_id)
    return {
        "success": True,
        "conversation_id": conversation_id,
        "status": "resolved",
    }


@app.get("/api/conversations/{conversation_id}")
def get_conversation_detail(conversation_id: str):
    """
    Returns full transcript and outcome for Screen 2 (Conversation Detail).
    """
    scripts = _load_all_scripts()
    target = next((s for s in scripts if s.get("id") == conversation_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Conversation script not found")

    req = AgentRunRequest(
        conversation_id=conversation_id,
        today=target.get("today", "2026-10-01"),
        turns=target.get("turns", []),
    )
    res = orchestrator.process_conversation(req)

    return {
        "conversation_id": conversation_id,
        "description": target.get("description", ""),
        "today": target.get("today", "2026-10-01"),
        "turns": target.get("turns", []),
        "expected": target.get("expected", {}),
        "outcome": res.model_dump(),
        "is_resolved": conversation_id in resolved_handoffs,
    }


@app.post("/api/conversations/{conversation_id}/verify-determinism")
def verify_determinism(conversation_id: str, repeats: int = 3):
    """
    Executes conversation 3 times to verify deterministic stability.
    """
    scripts = _load_all_scripts()
    target = next((s for s in scripts if s.get("id") == conversation_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Conversation script not found")

    results = []
    fingerprints = set()

    for r in range(repeats):
        req = AgentRunRequest(
            conversation_id=conversation_id,
            today=target.get("today", "2026-10-01"),
            turns=target.get("turns", []),
        )
        res = orchestrator.process_conversation(req)
        fp = f"{res.terminal_state}/{res.escalation_reason}/{','.join(sorted(c.name for c in res.tool_calls))}"
        fingerprints.add(fp)
        results.append({
            "run": r + 1,
            "fingerprint": fp,
            "terminal_state": res.terminal_state,
            "escalation_reason": res.escalation_reason,
            "tool_calls": [c.name for c in res.tool_calls],
            "latency_ms": res.metrics.latency_ms,
        })

    is_stable = len(fingerprints) == 1
    return {
        "conversation_id": conversation_id,
        "repeats": repeats,
        "is_stable": is_stable,
        "fingerprints": list(fingerprints),
        "runs": results,
    }
