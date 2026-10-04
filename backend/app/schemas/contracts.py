from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


TerminalStateType = Literal[
    "booked",
    "rescheduled",
    "cancelled",
    "escalated",
    "refused",
    "abandoned",
]

EscalationReasonType = Literal[
    "clinical_urgent",
    "medical_advice",
    "not_authorised",
    "ambiguous_patient",
    "out_of_scope",
]


class AgentRunRequest(BaseModel):
    conversation_id: str = Field(..., description="Unique conversation identifier, e.g. cv_0001")
    today: str = Field(..., description="Current reference date in YYYY-MM-DD format")
    turns: List[str] = Field(..., description="Caller's utterances in chronological order")


class ToolCallRecord(BaseModel):
    name: str = Field(..., description="The name of the tool called")
    arguments: Dict[str, Any] = Field(..., description="Arguments passed to the tool")
    output: Optional[Any] = Field(None, description="Result returned by the tool execution")


class AgentMetrics(BaseModel):
    turns: int = Field(default=0, description="Total conversation turns")
    tokens: int = Field(default=0, description="Estimated total tokens used")
    latency_ms: int = Field(default=0, description="Total execution latency in milliseconds")


class AgentRunResponse(BaseModel):
    conversation_id: str
    tool_calls: List[ToolCallRecord]
    terminal_state: TerminalStateType
    escalation_reason: Optional[EscalationReasonType] = None
    patient_id: Optional[str] = None
    appointment_id: Optional[str] = None
    reply: str
    metrics: AgentMetrics
