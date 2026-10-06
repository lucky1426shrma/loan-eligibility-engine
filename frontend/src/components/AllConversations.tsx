import React from 'react';
import { ConversationSummary } from '../types';
import { ArrowUpRight, ShieldAlert, CheckCircle, Clock } from 'lucide-react';

interface AllConversationsProps {
  conversations: ConversationSummary[];
  onSelectConversation: (id: string) => void;
}

export const AllConversations: React.FC<AllConversationsProps> = ({
  conversations,
  onSelectConversation,
}) => {
  const starterScripts = conversations.filter((c) => c.id.startsWith('cv_'));
  const adversarialScripts = conversations.filter((c) => c.id.startsWith('adv_'));

  const renderTable = (items: ConversationSummary[], title: string, subtitle: string) => (
    <div className="bg-white border border-gray-200 rounded-xl shadow-xs overflow-hidden mb-8">
      <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold text-gray-900">{title}</h2>
          <p className="text-xs text-gray-400 mt-0.5">{subtitle}</p>
        </div>
        <span className="text-xs font-mono font-medium text-gray-400">{items.length} scripts</span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse text-sm">
          <thead>
            <tr className="border-b border-gray-200 bg-gray-50/50 text-[11px] font-semibold text-gray-400 uppercase tracking-wider">
              <th className="py-3 px-6">ID</th>
              <th className="py-3 px-6">Description / Notes</th>
              <th className="py-3 px-6">Terminal State</th>
              <th className="py-3 px-6">Escalation</th>
              <th className="py-3 px-6">Tools</th>
              <th className="py-3 px-6 text-right">View</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {items.map((conv) => (
              <tr
                key={conv.id}
                onClick={() => onSelectConversation(conv.id)}
                className="hover:bg-sky-50/50 cursor-pointer transition-colors group"
              >
                <td className="py-3.5 px-6 font-mono font-bold text-sky-700">
                  {conv.id}
                </td>
                <td className="py-3.5 px-6 text-gray-700 max-w-md truncate text-xs">
                  {conv.description}
                </td>
                <td className="py-3.5 px-6">
                  <span
                    className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-mono font-semibold uppercase ${
                      conv.terminal_state === 'booked'
                        ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                        : conv.terminal_state === 'escalated'
                        ? 'bg-rose-50 text-rose-700 border border-rose-200'
                        : conv.terminal_state === 'rescheduled'
                        ? 'bg-sky-50 text-sky-700 border border-sky-200'
                        : conv.terminal_state === 'cancelled'
                        ? 'bg-amber-50 text-amber-700 border border-amber-200'
                        : 'bg-gray-100 text-gray-700 border border-gray-200'
                    }`}
                  >
                    {conv.terminal_state}
                  </span>
                </td>
                <td className="py-3.5 px-6 text-xs font-mono text-gray-500">
                  {conv.escalation_reason || '—'}
                </td>
                <td className="py-3.5 px-6 text-xs font-mono text-gray-500">
                  {conv.tool_calls_count} calls
                </td>
                <td className="py-3.5 px-6 text-right">
                  <ArrowUpRight className="w-4 h-4 text-gray-400 group-hover:text-sky-600 ml-auto transition-colors" />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );

  return (
    <div className="max-w-6xl mx-auto px-6 py-8">
      <div className="pb-6 mb-8 border-b border-gray-200">
        <h1 className="text-2xl font-bold tracking-tight text-gray-900">
          All Test Conversations
        </h1>
        <p className="text-sm text-gray-500 mt-1">
          Review outcomes for the 15 starter pack conversations and the 8 adversarial test scripts.
        </p>
      </div>

      {renderTable(
        starterScripts,
        'Standard Test Cases (conversations/)',
        'Official starter pack conversation scripts cv_0001 to cv_0015'
      )}

      {renderTable(
        adversarialScripts,
        'Adversarial Test Suite (adversarial/)',
        'Custom edge cases breaking naive LLM implementations'
      )}
    </div>
  );
};
