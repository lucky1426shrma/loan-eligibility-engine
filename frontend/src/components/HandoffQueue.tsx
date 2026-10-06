import React, { useState } from 'react';
import { HandoffQueueResponse, HandoffItem } from '../types';
import { resolveHandoff } from '../api/client';
import { CheckCircle2, AlertCircle, ArrowUpRight } from 'lucide-react';

interface HandoffQueueProps {
  queueData: HandoffQueueResponse;
  onSelectConversation: (conversationId: string) => void;
  onRefresh: () => void;
}

export const HandoffQueue: React.FC<HandoffQueueProps> = ({
  queueData,
  onSelectConversation,
  onRefresh,
}) => {
  const [resolvingId, setResolvingId] = useState<string | null>(null);
  const [resolvedMessage, setResolvedMessage] = useState<string | null>(null);

  const { metrics, open_handoffs } = queueData;

  const handleResolve = async (e: React.MouseEvent, conversationId: string) => {
    e.stopPropagation();
    try {
      setResolvingId(conversationId);
      await resolveHandoff(conversationId);
      setResolvedMessage(`Handoff ${conversationId} marked as resolved.`);
      setTimeout(() => setResolvedMessage(null), 3000);
      onRefresh();
    } catch (err) {
      console.error(err);
    } finally {
      setResolvingId(null);
    }
  };

  const getReasonBadge = (reason: string) => {
    switch (reason) {
      case 'clinical_urgent':
      case 'CLINICAL':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-50 text-rose-700 border border-rose-200">
            CLINICAL
          </span>
        );
      case 'not_authorised':
      case 'NOT AUTHORISED':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-200">
            NOT AUTHORISED
          </span>
        );
      case 'ambiguous_patient':
      case 'AMBIGUOUS PATIENT':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-yellow-50 text-yellow-800 border border-yellow-200">
            AMBIGUOUS PATIENT
          </span>
        );
      case 'medical_advice':
      case 'MEDICAL ADVICE':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-purple-50 text-purple-700 border border-purple-200">
            MEDICAL ADVICE
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-gray-100 text-gray-700 border border-gray-200 uppercase">
            {reason.replace('_', ' ')}
          </span>
        );
    }
  };

  return (
    <div className="max-w-6xl mx-auto px-6 py-8">
      {/* Header section matching PDF Screen 1 */}
      <div className="flex items-center justify-between pb-6 border-b border-gray-200">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-gray-900">Handoff Queue</h1>
          <p className="text-sm text-gray-500 mt-1">
            Sunrise Clinic, Dehradun — conversations the agent escalated
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-sky-50 text-sky-700 border border-sky-200 tracking-wider">
            {metrics.open_escalated_count} OPEN
          </span>
        </div>
      </div>

      {resolvedMessage && (
        <div className="mt-4 p-3 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-800 text-sm flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-600" />
          {resolvedMessage}
        </div>
      )}

      {/* Top 4 Metrics Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-6">
        {/* Metric 1: CONVERSATIONS */}
        <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-xs">
          <div className="text-[11px] font-semibold tracking-wider text-gray-400 uppercase">
            Conversations
          </div>
          <div className="text-3xl font-extrabold text-gray-900 mt-2">
            {metrics.conversations_today}
          </div>
          <div className="text-xs text-gray-400 mt-1">today</div>
        </div>

        {/* Metric 2: COMPLETED BY AGENT */}
        <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-xs">
          <div className="text-[11px] font-semibold tracking-wider text-gray-400 uppercase">
            Completed by Agent
          </div>
          <div className="text-3xl font-extrabold text-gray-900 mt-2">
            {metrics.completed_by_agent}
          </div>
          <div className="text-xs text-emerald-600 font-medium mt-1">
            {metrics.completed_percentage}%
          </div>
        </div>

        {/* Metric 3: ESCALATED */}
        <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-xs">
          <div className="text-[11px] font-semibold tracking-wider text-gray-400 uppercase">
            Escalated
          </div>
          <div className="text-3xl font-extrabold text-gray-900 mt-2">
            {metrics.escalated_total}
          </div>
          <div className="text-xs text-amber-600 font-medium mt-1">
            {metrics.open_escalated_count} still open
          </div>
        </div>

        {/* Metric 4: URGENT */}
        <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-xs">
          <div className="text-[11px] font-semibold tracking-wider text-gray-400 uppercase">
            Urgent
          </div>
          <div className="text-3xl font-extrabold text-rose-600 mt-2">
            {metrics.urgent_count}
          </div>
          <div className="text-xs text-rose-500 font-medium mt-1">
            clinical, unresolved
          </div>
        </div>
      </div>

      {/* Open Handoffs Section Table */}
      <div className="mt-10 bg-white border border-gray-200 rounded-xl shadow-xs overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
          <h2 className="text-base font-semibold text-gray-900">Open handoffs</h2>
          <span className="text-xs text-gray-400">Click any row to open conversation detail</span>
        </div>

        {open_handoffs.length === 0 ? (
          <div className="p-12 text-center text-gray-400">
            <CheckCircle2 className="w-8 h-8 mx-auto text-emerald-500 mb-2" />
            <p className="font-medium text-gray-700">No open handoffs in the queue</p>
            <p className="text-xs mt-1">All escalated conversations have been resolved by clinic staff.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-sm">
              <thead>
                <tr className="border-b border-gray-200 bg-gray-50/50 text-[11px] font-semibold text-gray-400 uppercase tracking-wider">
                  <th className="py-3 px-6">Conversation</th>
                  <th className="py-3 px-6">Caller Said</th>
                  <th className="py-3 px-6">Reason</th>
                  <th className="py-3 px-6">Time</th>
                  <th className="py-3 px-6 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {open_handoffs.map((handoff) => (
                  <tr
                    key={handoff.conversation_id}
                    onClick={() => onSelectConversation(handoff.conversation_id)}
                    className="hover:bg-sky-50/50 cursor-pointer transition-colors group"
                  >
                    {/* Conversation ID */}
                    <td className="py-4 px-6 font-mono font-medium text-sky-700 flex items-center gap-1.5">
                      <span>{handoff.conversation_id}</span>
                      <ArrowUpRight className="w-3.5 h-3.5 opacity-0 group-hover:opacity-100 transition-opacity text-sky-500" />
                    </td>

                    {/* Caller Said */}
                    <td className="py-4 px-6 text-gray-800 font-medium max-w-md truncate">
                      “{handoff.caller_said}”
                    </td>

                    {/* Reason badge */}
                    <td className="py-4 px-6">
                      {getReasonBadge(handoff.reason)}
                    </td>

                    {/* Time */}
                    <td className="py-4 px-6 text-gray-500 font-mono text-xs">
                      {handoff.time}
                    </td>

                    {/* Action button */}
                    <td className="py-4 px-6 text-right">
                      <button
                        onClick={(e) => handleResolve(e, handoff.conversation_id)}
                        disabled={resolvingId === handoff.conversation_id}
                        className="px-3.5 py-1.5 rounded-lg bg-sky-600 hover:bg-sky-700 active:bg-sky-800 text-white text-xs font-semibold shadow-xs transition-colors disabled:opacity-50"
                      >
                        {resolvingId === handoff.conversation_id ? 'Resolving...' : 'Resolve'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* PDF Mockup Caption Note */}
      <p className="text-center text-xs text-gray-400 mt-6 italic">
        Counters across the top, then the open handoffs the agent escalated, each with what the caller said, the reason, and a way to resolve it.
      </p>
    </div>
  );
};
