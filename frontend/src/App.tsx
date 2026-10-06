import React, { useState, useEffect } from 'react';
import { Sidebar, NavTab } from './components/Sidebar';
import { HandoffQueue } from './components/HandoffQueue';
import { ConversationDetail } from './components/ConversationDetail';
import { AllConversations } from './components/AllConversations';
import { ConversationSimulator } from './components/ConversationSimulator';
import {
  fetchHandoffQueue,
  fetchConversations,
  fetchConversationDetail,
} from './api/client';
import {
  HandoffQueueResponse,
  ConversationSummary,
  ConversationDetailData,
} from './types';
import { Loader2 } from 'lucide-react';

export function App() {
  const [activeTab, setActiveTab] = useState<NavTab>('queue');
  const [queueData, setQueueData] = useState<HandoffQueueResponse | null>(null);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [selectedConvId, setSelectedConvId] = useState<string>('cv_0011');
  const [detailData, setDetailData] = useState<ConversationDetailData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [detailLoading, setDetailLoading] = useState<boolean>(false);

  // Load initial handoff queue and conversation summaries
  const loadData = async () => {
    try {
      setLoading(true);
      const [queueRes, convsRes] = await Promise.all([
        fetchHandoffQueue(),
        fetchConversations(),
      ]);
      setQueueData(queueRes);
      setConversations(convsRes);

      // Default selection to first open handoff or cv_0011 (clinical urgent)
      if (queueRes.open_handoffs.length > 0) {
        setSelectedConvId(queueRes.open_handoffs[0].conversation_id);
      }
    } catch (err) {
      console.error('Failed to load clinic data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  // Load detailed conversation data whenever selectedConvId changes
  useEffect(() => {
    if (!selectedConvId) return;
    const loadDetail = async () => {
      try {
        setDetailLoading(true);
        const data = await fetchConversationDetail(selectedConvId);
        setDetailData(data);
      } catch (err) {
        console.error(`Failed to load detail for ${selectedConvId}:`, err);
      } finally {
        setDetailLoading(false);
      }
    };
    loadDetail();
  }, [selectedConvId]);

  const handleSelectConversation = (id: string) => {
    setSelectedConvId(id);
    setActiveTab('detail');
  };

  const allConversationIds = conversations.map((c) => c.id);

  return (
    <div className="flex min-h-screen bg-gray-50/70 font-sans text-gray-900 antialiased">
      {/* Shared Persistent Sidebar */}
      <Sidebar
        activeTab={activeTab}
        onSelectTab={setActiveTab}
        openHandoffsCount={queueData?.metrics.open_escalated_count ?? 0}
      />

      {/* Main Content Area */}
      <main className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="flex flex-col items-center justify-center min-h-[60vh] gap-3 text-gray-400">
            <Loader2 className="w-8 h-8 animate-spin text-sky-600" />
            <p className="text-sm font-medium">Loading clinic front desk console...</p>
          </div>
        ) : (
          <>
            {/* Screen 1: Handoff Queue */}
            {activeTab === 'queue' && queueData && (
              <HandoffQueue
                queueData={queueData}
                onSelectConversation={handleSelectConversation}
                onRefresh={loadData}
              />
            )}

            {/* Screen 2: Conversation Detail */}
            {activeTab === 'detail' && (
              <>
                {detailLoading || !detailData ? (
                  <div className="flex flex-col items-center justify-center min-h-[60vh] gap-3 text-gray-400">
                    <Loader2 className="w-8 h-8 animate-spin text-sky-600" />
                    <p className="text-sm font-medium">Loading conversation {selectedConvId}...</p>
                  </div>
                ) : (
                  <ConversationDetail
                    data={detailData}
                    onBack={() => setActiveTab('queue')}
                    onSelectConversation={setSelectedConvId}
                    allConversations={allConversationIds}
                  />
                )}
              </>
            )}

            {/* All Conversations Directory */}
            {activeTab === 'all' && (
              <AllConversations
                conversations={conversations}
                onSelectConversation={handleSelectConversation}
              />
            )}

            {/* Live Interactive Simulator */}
            {activeTab === 'simulator' && <ConversationSimulator />}
          </>
        )}
      </main>
    </div>
  );
}

export default App;
