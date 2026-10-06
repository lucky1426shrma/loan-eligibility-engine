export interface ToolCall {
  name: string;
  arguments: Record<string, any>;
  output?: any;
}

export interface AgentMetrics {
  turns: number;
  tokens: number;
  latency_ms: number;
}

export interface ConversationOutcome {
  conversation_id: string;
  tool_calls: ToolCall[];
  terminal_state: "booked" | "rescheduled" | "cancelled" | "escalated" | "refused" | "abandoned";
  escalation_reason: "clinical_urgent" | "medical_advice" | "not_authorised" | "ambiguous_patient" | "out_of_scope" | null;
  patient_id: string | null;
  appointment_id: string | null;
  reply: string;
  metrics: AgentMetrics;
}

export interface HandoffItem {
  conversation_id: string;
  caller_said: string;
  reason: string;
  time: string;
  terminal_state: string;
}

export interface HandoffMetrics {
  conversations_today: number;
  completed_by_agent: number;
  completed_percentage: number;
  escalated_total: number;
  open_escalated_count: number;
  urgent_count: number;
}

export interface HandoffQueueResponse {
  metrics: HandoffMetrics;
  open_handoffs: HandoffItem[];
}

export interface ConversationSummary {
  id: string;
  description: string;
  today: string;
  turns_count: number;
  terminal_state: string;
  escalation_reason: string | null;
  tool_calls_count: number;
  is_resolved: boolean;
}

export interface ConversationDetailData {
  conversation_id: string;
  description: string;
  today: string;
  turns: string[];
  expected?: any;
  outcome: ConversationOutcome;
  is_resolved: boolean;
}
