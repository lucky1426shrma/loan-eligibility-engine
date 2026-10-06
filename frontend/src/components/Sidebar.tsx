import React from 'react';
import {
  Inbox,
  MessageSquare,
  PlayCircle,
  Calendar,
  Users,
  ShieldCheck,
  Activity,
} from 'lucide-react';

export type NavTab = 'queue' | 'detail' | 'all' | 'simulator';

interface SidebarProps {
  activeTab: NavTab;
  onSelectTab: (tab: NavTab) => void;
  openHandoffsCount: number;
}

export const Sidebar: React.FC<SidebarProps> = ({
  activeTab,
  onSelectTab,
  openHandoffsCount,
}) => {
  return (
    <aside className="w-16 md:w-18 flex-shrink-0 bg-white border-r border-gray-200 flex flex-col items-center py-5 justify-between select-none min-h-screen">
      {/* Top Brand Logo */}
      <div className="flex flex-col items-center gap-6 w-full">
        <button
          onClick={() => onSelectTab('queue')}
          title="Sunrise Clinic Front Desk Console"
          className="w-10 h-10 rounded-xl bg-gradient-to-tr from-sky-600 to-cyan-500 text-white flex items-center justify-center shadow-sm hover:opacity-95 transition-opacity"
        >
          <Activity className="w-5 h-5 text-white" />
        </button>

        {/* Navigation Item Icons */}
        <nav className="flex flex-col items-center gap-3 w-full px-2">
          {/* Screen 1: Handoff Queue */}
          <button
            onClick={() => onSelectTab('queue')}
            title="Handoff Queue (Screen 1)"
            className={`relative w-11 h-11 rounded-xl flex items-center justify-center transition-all ${
              activeTab === 'queue'
                ? 'bg-sky-50 text-sky-700 font-medium shadow-sm'
                : 'text-gray-400 hover:text-gray-700 hover:bg-gray-100'
            }`}
          >
            <Inbox className="w-5 h-5" />
            {openHandoffsCount > 0 && (
              <span className="absolute -top-1 -right-1 bg-rose-500 text-white text-[10px] font-bold px-1.5 py-0.5 rounded-full ring-2 ring-white">
                {openHandoffsCount}
              </span>
            )}
          </button>

          {/* Screen 2: Conversation Detail */}
          <button
            onClick={() => onSelectTab('detail')}
            title="Conversation Detail (Screen 2)"
            className={`w-11 h-11 rounded-xl flex items-center justify-center transition-all ${
              activeTab === 'detail'
                ? 'bg-sky-50 text-sky-700 font-medium shadow-sm'
                : 'text-gray-400 hover:text-gray-700 hover:bg-gray-100'
            }`}
          >
            <MessageSquare className="w-5 h-5" />
          </button>

          {/* All Conversations Browser */}
          <button
            onClick={() => onSelectTab('all')}
            title="All Conversations (15 + 8 Adversarial)"
            className={`w-11 h-11 rounded-xl flex items-center justify-center transition-all ${
              activeTab === 'all'
                ? 'bg-sky-50 text-sky-700 font-medium shadow-sm'
                : 'text-gray-400 hover:text-gray-700 hover:bg-gray-100'
            }`}
          >
            <Calendar className="w-5 h-5" />
          </button>

          {/* Live Agent Runner / Interactive Simulator */}
          <button
            onClick={() => onSelectTab('simulator')}
            title="Live Agent Simulator & 3x Determinism Runner"
            className={`w-11 h-11 rounded-xl flex items-center justify-center transition-all ${
              activeTab === 'simulator'
                ? 'bg-sky-50 text-sky-700 font-medium shadow-sm'
                : 'text-gray-400 hover:text-gray-700 hover:bg-gray-100'
            }`}
          >
            <PlayCircle className="w-5 h-5" />
          </button>
        </nav>
      </div>

      {/* Bottom Status Indicator */}
      <div className="flex flex-col items-center gap-3">
        <div
          title="Strict Tool Grounding Layer Active (0 Invented Facts)"
          className="w-9 h-9 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center border border-emerald-200"
        >
          <ShieldCheck className="w-5 h-5" />
        </div>
        <div className="w-2.5 h-2.5 rounded-full bg-emerald-500 ring-4 ring-emerald-100 animate-pulse" title="Backend API Connected" />
      </div>
    </aside>
  );
};
