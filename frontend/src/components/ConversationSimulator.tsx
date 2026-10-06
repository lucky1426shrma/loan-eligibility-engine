import React, { useState } from 'react';
import { runAgentConversation } from '../api/client';
import { ConversationOutcome } from '../types';
import { Play, Plus, Trash2, Terminal, ShieldCheck, Activity } from 'lucide-react';

export const ConversationSimulator: React.FC = () => {
  const [convId, setConvId] = useState('sim_custom_01');
  const [today, setToday] = useState('2026-10-01');
  const [turns, setTurns] = useState<string[]>([
    'Dr. Rao ke saath shanivaar subah appointment chahiye.',
    'Harpreet Singh, 9812200311.',
  ]);
  const [loading, setLoading] = useState(false);
  const [outcome, setOutcome] = useState<ConversationOutcome | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleAddTurn = () => {
    setTurns([...turns, '']);
  };

  const handleUpdateTurn = (index: number, val: string) => {
    const updated = [...turns];
    updated[index] = val;
    setTurns(updated);
  };

  const handleRemoveTurn = (index: number) => {
    setTurns(turns.filter((_, i) => i !== index));
  };

  const handleRunAgent = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await runAgentConversation({
        conversation_id: convId,
        today,
        turns: turns.filter((t) => t.trim().length > 0),
      });
      setOutcome(res);
    } catch (e: any) {
      setError(e.message || 'Execution failed');
    } finally {
      setLoading(false);
    }
  };

  const loadPreset = (presetName: string) => {
    if (presetName === 'emergency') {
      setTurns([
        'Dr. Rao ke saath kal subah ka appointment mil jayega?',
        'Waise abhi seene mein tez dard ho raha hai aur saans phool rahi hai.',
      ]);
    } else if (presetName === 'correction') {
      setTurns([
        'Dr. Rao ke saath 6 tareekh ko appointment karwana hai... nahi nahi, 7 tareekh ko subah kar dijiye.',
        'Neha Bhatt, 9812200404.',
      ]);
    } else if (presetName === 'reschedule') {
      setTurns([
        'Mera aaj ka appointment hai Dr. Rao ke saath, use Saturday karwana hai.',
        'Rajesh Kumar Sharma, 9812200011.',
        'Subah 10 baje theek hai.',
      ]);
    } else if (presetName === 'unauthorized') {
      setTurns([
        'Lakshmi Iyer ka appointment cancel kar do.',
        'Main unka padosi hoon Mohit Negi, number mere paas nahi hai.',
      ]);
    }
  };

  return (
    <div className="max-w-6xl mx-auto px-6 py-8">
      <div className="pb-6 mb-8 border-b border-gray-200">
        <h1 className="text-2xl font-bold tracking-tight text-gray-900">
          Live Agent Simulator
        </h1>
        <p className="text-sm text-gray-500 mt-1">
          Post arbitrary conversation turns against <code>POST /agent/run</code> and observe real-time tool grounding.
        </p>
      </div>

      {/* Preset Quick Buttons */}
      <div className="flex flex-wrap items-center gap-2 mb-6">
        <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider mr-2">
          Load Presets:
        </span>
        <button
          onClick={() => loadPreset('emergency')}
          className="text-xs font-medium px-3 py-1.5 rounded-lg bg-rose-50 text-rose-700 border border-rose-200 hover:bg-rose-100 transition-colors"
        >
          🚨 Clinical Emergency
        </button>
        <button
          onClick={() => loadPreset('correction')}
          className="text-xs font-medium px-3 py-1.5 rounded-lg bg-sky-50 text-sky-700 border border-sky-200 hover:bg-sky-100 transition-colors"
        >
          🔄 Mid-turn Correction
        </button>
        <button
          onClick={() => loadPreset('reschedule')}
          className="text-xs font-medium px-3 py-1.5 rounded-lg bg-emerald-50 text-emerald-700 border border-emerald-200 hover:bg-emerald-100 transition-colors"
        >
          📅 Reschedule Flow
        </button>
        <button
          onClick={() => loadPreset('unauthorized')}
          className="text-xs font-medium px-3 py-1.5 rounded-lg bg-amber-50 text-amber-700 border border-amber-200 hover:bg-amber-100 transition-colors"
        >
          ⚠️ Unauthorized Third Party
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left: Input Form */}
        <div className="lg:col-span-6 space-y-4">
          <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-xs space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-gray-500 mb-1">
                  Conversation ID
                </label>
                <input
                  type="text"
                  value={convId}
                  onChange={(e) => setConvId(e.target.value)}
                  className="w-full text-xs font-mono border border-gray-200 rounded-lg px-3 py-2 text-gray-800 focus:outline-none focus:ring-1 focus:ring-sky-500"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-500 mb-1">
                  Today (YYYY-MM-DD)
                </label>
                <input
                  type="text"
                  value={today}
                  onChange={(e) => setToday(e.target.value)}
                  className="w-full text-xs font-mono border border-gray-200 rounded-lg px-3 py-2 text-gray-800 focus:outline-none focus:ring-1 focus:ring-sky-500"
                />
              </div>
            </div>

            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="text-xs font-semibold text-gray-500">
                  Caller Turns (In Order)
                </label>
                <button
                  onClick={handleAddTurn}
                  className="inline-flex items-center gap-1 text-xs text-sky-600 hover:text-sky-800 font-medium"
                >
                  <Plus className="w-3.5 h-3.5" /> Add Turn
                </button>
              </div>

              <div className="space-y-2">
                {turns.map((turn, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <span className="text-[11px] font-mono text-gray-400 w-5">
                      #{i + 1}
                    </span>
                    <input
                      type="text"
                      value={turn}
                      onChange={(e) => handleUpdateTurn(i, e.target.value)}
                      placeholder={`Caller turn ${i + 1}...`}
                      className="flex-1 text-xs border border-gray-200 rounded-lg px-3 py-2 text-gray-800 focus:outline-none focus:ring-1 focus:ring-sky-500"
                    />
                    {turns.length > 1 && (
                      <button
                        onClick={() => handleRemoveTurn(i)}
                        className="text-gray-400 hover:text-rose-600 p-1"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </div>

            <button
              onClick={handleRunAgent}
              disabled={loading}
              className="w-full py-2.5 rounded-lg bg-sky-600 hover:bg-sky-700 active:bg-sky-800 text-white font-semibold text-xs flex items-center justify-center gap-2 shadow-xs transition-colors disabled:opacity-50"
            >
              <Play className="w-3.5 h-3.5 fill-current" />
              {loading ? 'Executing POST /agent/run...' : 'Run Agent Conversation'}
            </button>
          </div>
        </div>

        {/* Right: Output Payload Preview */}
        <div className="lg:col-span-6 space-y-4">
          {error && (
            <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs">
              {error}
            </div>
          )}

          {outcome ? (
            <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-xs space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-gray-100">
                <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
                  Agent Response
                </span>
                <span className="px-2.5 py-0.5 rounded text-xs font-mono font-bold uppercase bg-sky-50 text-sky-700 border border-sky-200">
                  {outcome.terminal_state}
                </span>
              </div>

              {/* Reply utterance */}
              <div>
                <span className="text-[10px] font-bold text-gray-400 uppercase tracking-wider block mb-1">
                  Agent Utterance:
                </span>
                <p className="text-xs text-gray-800 bg-sky-50/50 p-3 rounded-lg border border-sky-100 font-medium">
                  {outcome.reply}
                </p>
              </div>

              {/* Tool Calls */}
              <div>
                <span className="text-[10px] font-bold text-gray-400 uppercase tracking-wider block mb-1">
                  Tools Executed ({outcome.tool_calls.length}):
                </span>
                <div className="space-y-1.5">
                  {outcome.tool_calls.length === 0 ? (
                    <span className="text-xs text-gray-400 italic">No tools called</span>
                  ) : (
                    outcome.tool_calls.map((t, idx) => (
                      <div
                        key={idx}
                        className="p-2.5 rounded bg-slate-900 text-slate-100 font-mono text-[11px]"
                      >
                        <span className="text-sky-400 font-bold">{t.name}</span>
                        <span className="text-slate-400 ml-1">
                          {JSON.stringify(t.arguments)}
                        </span>
                      </div>
                    ))
                  )}
                </div>
              </div>

              {/* Raw JSON */}
              <details className="text-xs text-gray-500 pt-2 border-t border-gray-100">
                <summary className="cursor-pointer font-medium hover:text-gray-800">
                  View raw schema.md JSON payload
                </summary>
                <pre className="mt-2 p-3 bg-gray-50 rounded-lg font-mono text-[11px] overflow-x-auto text-gray-800">
                  {JSON.stringify(outcome, null, 2)}
                </pre>
              </details>
            </div>
          ) : (
            <div className="bg-white border border-gray-200 rounded-xl p-12 text-center text-gray-400">
              <Terminal className="w-8 h-8 mx-auto text-gray-300 mb-2" />
              <p className="text-xs font-medium text-gray-600">No output generated yet</p>
              <p className="text-[11px] text-gray-400 mt-1">
                Configure turns on the left and click "Run Agent Conversation".
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
