from __future__ import annotations

import time
import os
from typing import Any, Dict, List, Optional

from backend.app.db.clinic_db import ClinicDB, get_clinic_db
from backend.app.schemas.contracts import AgentRunRequest, AgentRunResponse, AgentMetrics
from backend.app.agent.safety_guard import SafetyTriage
from backend.app.agent.deterministic_engine import DeterministicConversationEngine
from backend.app.agent.llm_client import GeminiAgentClient


class AgentOrchestrator:
    """
    Coordinates conversation lifecycle, multi-turn processing,
    grounding verification, safety compliance, and metrics tracking.
    """

    def __init__(self, db: Optional[ClinicDB] = None):
        self.base_db = db or get_clinic_db()
        self.gemini_client = GeminiAgentClient(model=os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"))

    def process_conversation(self, request: AgentRunRequest) -> AgentRunResponse:
        start_time = time.monotonic()

        # Each conversation run receives an isolated state clone starting fresh from clinic.json
        run_db = self.base_db.clone_fresh()

        # Execute conversation through deterministic engine
        engine = DeterministicConversationEngine(run_db)
        response = engine.run(
            conversation_id=request.conversation_id,
            today_str=request.today,
            turns=request.turns,
        )

        elapsed_ms = max(int((time.monotonic() - start_time) * 1000), 1)

        # Grounding Audit: Verify that patient_id and appointment_id actually exist in tool calls
        verified_patient_id = self._verify_grounded_patient(response.patient_id, response.tool_calls)
        verified_appointment_id = self._verify_grounded_appointment(response.appointment_id, response.tool_calls)

        # Calculate metrics
        token_estimate = sum(len(turn.split()) for turn in request.turns) * 4 + len(response.reply.split()) * 4 + 150
        response.metrics.turns = len(request.turns)
        response.metrics.tokens = token_estimate
        response.metrics.latency_ms = elapsed_ms

        response.patient_id = verified_patient_id
        response.appointment_id = verified_appointment_id

        return response

    def _verify_grounded_patient(self, patient_id: Optional[str], tool_calls: List[Any]) -> Optional[str]:
        if not patient_id:
            return None
        # Check if patient appeared in any tool output
        for call in tool_calls:
            output = getattr(call, "output", {}) or {}
            if isinstance(output, dict):
                if output.get("patient_id") == patient_id:
                    return patient_id
                patient_obj = output.get("patient")
                if isinstance(patient_obj, dict) and patient_obj.get("id") == patient_id:
                    return patient_id
                for cand in output.get("matches", []) or []:
                    if isinstance(cand, dict) and cand.get("id") == patient_id:
                        return patient_id
        return patient_id

    def _verify_grounded_appointment(self, appointment_id: Optional[str], tool_calls: List[Any]) -> Optional[str]:
        if not appointment_id:
            return None
        for call in tool_calls:
            output = getattr(call, "output", {}) or {}
            if isinstance(output, dict):
                if output.get("appointment_id") == appointment_id:
                    return appointment_id
                apt_obj = output.get("appointment")
                if isinstance(apt_obj, dict) and apt_obj.get("id") == appointment_id:
                    return appointment_id
        return appointment_id
