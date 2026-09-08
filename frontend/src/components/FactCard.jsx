import React from 'react';
import { ExternalLink, Tag, Calendar, Hash } from 'lucide-react';

export default function FactCard({ fact, isSelected = false, onPageSelect }) {
  const isAnomaly = fact.entity === 'System' || fact.value === 'No grounded facts detected';

  return (
    <div
      className={`bg-white border rounded-xl p-4 shadow-sm transition-all duration-150 ${
        isSelected
          ? 'border-indigo-500 ring-2 ring-indigo-500/10 shadow-md'
          : 'border-slate-200 hover:border-indigo-200 hover:shadow-card'
      }`}
    >
      {/* Header: Entity & Value */}
      <div className="flex items-start justify-between gap-2 mb-2.5">
        <div className="flex flex-col">
          <span className="text-[11px] font-medium tracking-wide uppercase text-slate-400">
            {fact.metric || 'Metric'}
          </span>
          <h4 className="text-sm font-semibold text-slate-900 leading-snug">
            {fact.entity || 'Unknown Entity'}
          </h4>
        </div>

        <div className="text-right">
          <span
            className={`inline-block font-mono text-sm font-bold px-2.5 py-1 rounded-lg ${
              isAnomaly
                ? 'bg-rose-50 text-rose-700 border border-rose-100'
                : 'bg-indigo-50 text-indigo-700 border border-indigo-100'
            }`}
          >
            {fact.value}
          </span>
        </div>
      </div>

      {/* Meta tags (Unit, Period, Page) */}
      <div className="flex flex-wrap items-center gap-2 mb-3 text-xs text-slate-500">
        {fact.unit && (
          <span className="inline-flex items-center space-x-1 bg-slate-50 px-2 py-0.5 rounded border border-slate-200">
            <Tag className="w-3 h-3 text-slate-400" />
            <span>{fact.unit}</span>
          </span>
        )}

        {fact.time_period && (
          <span className="inline-flex items-center space-x-1 bg-slate-50 px-2 py-0.5 rounded border border-slate-200">
            <Calendar className="w-3 h-3 text-slate-400" />
            <span>{fact.time_period}</span>
          </span>
        )}

        <span className="inline-flex items-center space-x-1 bg-slate-50 px-2 py-0.5 rounded border border-slate-200">
          <Hash className="w-3 h-3 text-slate-400" />
          <span>Page {fact.page_number}</span>
        </span>
      </div>

      {/* Evidence Callout */}
      {fact.raw_text_evidence && (
        <div className="bg-slate-50 p-3 rounded-lg border border-slate-100 mb-3">
          <span className="block text-[10px] uppercase font-semibold text-slate-400 mb-1">
            Verbatim Evidence
          </span>
          <p className="text-xs text-slate-700 font-mono leading-relaxed break-words">
            "{fact.raw_text_evidence}"
          </p>
        </div>
      )}

      {/* Footer Action */}
      <div className="flex justify-end pt-1 border-t border-slate-100">
        <button
          onClick={() => onPageSelect(fact.page_number, fact.document_id)}
          className="inline-flex items-center space-x-1.5 text-xs font-medium text-indigo-600 hover:text-indigo-800 transition-colors"
        >
          <span>View Evidence (Page {fact.page_number})</span>
          <ExternalLink className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
}

