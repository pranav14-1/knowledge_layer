import React, { useState, useMemo } from 'react';
import {
  List,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  HelpCircle,
  Search,
  Filter,
  Layers,
  MessageSquare
} from 'lucide-react';
import FactCard from './FactCard';
import RelationshipCard from './RelationshipCard';
import ChatWidget from './ChatWidget';

const TABS = [
  { id: 'CHAT', label: 'Chat Assistant', icon: MessageSquare },
  { id: 'ALL_FACTS', label: 'All Facts', icon: List },
  { id: 'CORROBORATES', label: 'Corroborations', icon: CheckCircle2 },
  { id: 'CONTRADICTS', label: 'Contradictions', icon: AlertTriangle },
  { id: 'RECONCILED', label: 'Reconciled', icon: RefreshCw },
  { id: 'FAILURE_ANALYSIS', label: 'Extraction Failures', icon: HelpCircle },
];

export default function FactDashboard({
  activeSessionId,
  facts = [],
  relationships = [],
  activeDoc,
  selectedFactId,
  onPageSelect,
  onFactJump,
}) {
  const [activeTab, setActiveTab] = useState('CHAT');
  const [searchQuery, setSearchQuery] = useState('');

  // Counts for tabs
  const tabCounts = useMemo(() => {
    const counts = {
      ALL_FACTS: facts.length,
      CORROBORATES: 0,
      CONTRADICTS: 0,
      RECONCILED: 0,
      FAILURE_ANALYSIS: 0,
    };
    relationships.forEach((rel) => {
      if (counts[rel.relationship_type] !== undefined) {
        counts[rel.relationship_type]++;
      }
    });
    return counts;
  }, [facts, relationships]);

  // Filtered facts for "All Facts" tab
  const filteredFacts = useMemo(() => {
    if (!searchQuery.trim()) return facts;
    const q = searchQuery.toLowerCase();
    return facts.filter(
      (f) =>
        f.entity?.toLowerCase().includes(q) ||
        f.metric?.toLowerCase().includes(q) ||
        f.value?.toLowerCase().includes(q) ||
        f.raw_text_evidence?.toLowerCase().includes(q)
    );
  }, [facts, searchQuery]);

  // Filtered relationships for relationship tabs
  const filteredRelationships = useMemo(() => {
    const relsInTab = relationships.filter(
      (r) => r.relationship_type === activeTab
    );
    if (!searchQuery.trim()) return relsInTab;
    const q = searchQuery.toLowerCase();
    return relsInTab.filter(
      (r) =>
        r.explanation_reasoning?.toLowerCase().includes(q) ||
        r.fact_a?.entity?.toLowerCase().includes(q) ||
        r.fact_b?.entity?.toLowerCase().includes(q) ||
        r.fact_a?.metric?.toLowerCase().includes(q) ||
        r.fact_b?.metric?.toLowerCase().includes(q)
    );
  }, [relationships, activeTab, searchQuery]);

  return (
    <div className="h-full flex flex-col bg-white">
      {/* Tab Navigation & Search Bar Header */}
      <div className="p-4 border-b border-slate-200 bg-white shrink-0">
        {/* Pills Tab Bar */}
        <div className="flex items-center space-x-1.5 overflow-x-auto pb-2 scrollbar-none">
          {TABS.map((tab) => {
            const Icon = tab.icon;
            const count = tabCounts[tab.id] || 0;
            const isActive = activeTab === tab.id;

            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition-all duration-150 ${
                  isActive
                    ? 'bg-indigo-50 text-indigo-700 font-semibold shadow-xs'
                    : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                <span>{tab.label}</span>
                <span
                  className={`text-[10px] px-1.5 py-0.2 rounded-full font-mono ${
                    isActive
                      ? 'bg-indigo-200/60 text-indigo-800'
                      : 'bg-slate-200 text-slate-600'
                  }`}
                >
                  {count}
                </span>
              </button>
            );
          })}
        </div>

        {/* Search input */}
        <div className="relative mt-2">
          <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search by entity, metric, value, or citation..."
            className="w-full pl-9 pr-3 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-lg text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition-all"
          />
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3 bg-panel h-full">
        {activeTab === 'CHAT' ? (
          <div className="h-full -m-4">
            <ChatWidget
              activeSessionId={activeSessionId}
              activeDoc={activeDoc}
              onPageSelect={onPageSelect}
            />
          </div>
        ) : activeTab === 'ALL_FACTS' ? (
          filteredFacts.length === 0 ? (
            <div className="h-64 flex flex-col items-center justify-center text-center p-6">
              <Layers className="w-8 h-8 text-slate-300 mb-2" />
              <p className="text-sm font-semibold text-slate-700">No Facts Available</p>
              <p className="text-xs text-slate-500 mt-1 max-w-xs">
                {activeDoc
                  ? 'No facts extracted for this document yet.'
                  : 'Select or upload a PDF to inspect extracted facts.'}
              </p>
            </div>
          ) : (
            filteredFacts.map((fact) => (
              <FactCard
                key={fact.id}
                fact={fact}
                isSelected={selectedFactId === fact.id}
                onPageSelect={onPageSelect}
              />
            ))
          )
        ) : filteredRelationships.length === 0 ? (
          <div className="h-64 flex flex-col items-center justify-center text-center p-6">
            <Filter className="w-8 h-8 text-slate-300 mb-2" />
            <p className="text-sm font-semibold text-slate-700">
              No {TABS.find((t) => t.id === activeTab)?.label} Found
            </p>
            <p className="text-xs text-slate-500 mt-1 max-w-xs">
              Upload multiple related documents to trigger automatic cross-referencing and reconciliation.
            </p>
          </div>
        ) : (
          filteredRelationships.map((rel) => (
            <RelationshipCard
              key={rel.id}
              relationship={rel}
              onFactJump={onFactJump}
            />
          ))
        )}
      </div>
    </div>
  );
}

