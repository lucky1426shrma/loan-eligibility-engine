import {
  HandoffQueueResponse,
  ConversationSummary,
  ConversationDetailData,
  ConversationOutcome,
} from '../types';

const API_BASE = ''; // Uses Vite proxy in development

export async function fetchHandoffQueue(): Promise<HandoffQueueResponse> {
  const res = await fetch(`${API_BASE}/api/handoffs`);
  if (!res.ok) throw new Error(`Failed to fetch handoff queue: ${res.statusText}`);
  return res.json();
}

export async function resolveHandoff(conversationId: string): Promise<boolean> {
  const res = await fetch(`${API_BASE}/api/handoffs/${conversationId}/resolve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });
  return res.ok;
}

export async function fetchConversations(): Promise<ConversationSummary[]> {
  const res = await fetch(`${API_BASE}/api/conversations`);
  if (!res.ok) throw new Error(`Failed to fetch conversations: ${res.statusText}`);
  return res.json();
}

export async function fetchConversationDetail(conversationId: string): Promise<ConversationDetailData> {
  const res = await fetch(`${API_BASE}/api/conversations/${conversationId}`);
  if (!res.ok) throw new Error(`Failed to fetch conversation ${conversationId}: ${res.statusText}`);
  return res.json();
}

export async function runAgentConversation(payload: {
  conversation_id: string;
  today: string;
  turns: string[];
}): Promise<ConversationOutcome> {
  const res = await fetch(`${API_BASE}/agent/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`Agent run failed: ${res.statusText}`);
  return res.json();
}

export async function verifyDeterminism(conversationId: string, repeats = 3): Promise<{
  is_stable: boolean;
  repeats: number;
  fingerprints: string[];
  runs: any[];
}> {
  const res = await fetch(`${API_BASE}/api/conversations/${conversationId}/verify-determinism?repeats=${repeats}`, {
    method: 'POST',
  });
  if (!res.ok) throw new Error(`Determinism test failed: ${res.statusText}`);
  return res.json();
}
