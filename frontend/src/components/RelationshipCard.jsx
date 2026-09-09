import React from 'react';
import {
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  HelpCircle,
  ExternalLink,
  FileText,
} from 'lucide-react';

const REL_CONFIG = {
  CORROBORATES: {
    label: 'Corroborates',
    badgeClass: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    icon: CheckCircle2,
  },
  CONTRADICTS: {
    label: 'Contradiction',
    badgeClass: 'bg-rose-50 text-rose-700 border-rose-200',
    icon: AlertTriangle,
  },
  RECONCILED: {
    label: 'Context Reconciled',
    badgeClass: 'bg-amber-50 text-amber-700 border-amber-200',
    icon: RefreshCw,
  },
  FAILURE_ANALYSIS: {
    label: 'Failure Analysis',
    badgeClass: 'bg-slate-100 text-slate-700 border-slate-200',
    icon: HelpCircle,
  },
};

const getMicroBadge = (type, reasoning = '') => {
  const rLower = (reasoning || '').toLowerCase();
  switch (type) {
    case 'CORROBORATES':
      return {
        label: 'Confirmed Match',
        badgeClass: 'bg-emerald-100/80 text-emerald-800 border-emerald-300',
      };
    case 'CONTRADICTS':
      return {
        label: 'Value Discrepancy',
        badgeClass: 'bg-rose-100/80 text-rose-800 border-rose-300',
      };
    case 'RECONCILED':
      if (rLower.includes('unit') || rLower.includes('currency') || rLower.includes('measure')) {
        return {
          label: 'Unit Mismatch',
          badgeClass: 'bg-amber-100/80 text-amber-800 border-amber-300',
        };
      }
      return {
        label: 'Vintage Difference',
        badgeClass: 'bg-amber-100/80 text-amber-800 border-amber-300',
      };
    case 'FAILURE_ANALYSIS':
    default:
      return {
        label: 'Extraction Gap',
        badgeClass: 'bg-slate-200/80 text-slate-700 border-slate-300',
      };
  }
};

const cleanDocName = (filename) => {
  if (!filename) return null;
  const name = filename
    .replace(/\.pdf$/i, '')
    .replace(/^[0-9]+[-_]/, '')
    .replace(/[-_]/g, ' ')
    .trim();
  return name.length > 26 ? name.slice(0, 24) + '...' : name;
};

export default function RelationshipCard({ relationship, onFactJump }) {
  const config = REL_CONFIG[relationship.relationship_type] || REL_CONFIG.FAILURE_ANALYSIS;
  const StatusIcon = config.icon;
  const microBadge = getMicroBadge(relationship.relationship_type, relationship.explanation_reasoning);

  const factA = relationship.fact_a;
  const factB = relationship.fact_b;
  const isFailure = relationship.relationship_type === 'FAILURE_ANALYSIS' || factA?.id === factB?.id;

  return (
    <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm hover:border-slate-300 transition-all duration-150">
      {/* Top Bar: Relationship Type Badge */}
      <div className="flex items-center justify-between mb-4">
        <span
          className={`inline-flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-semibold border ${config.badgeClass}`}
        >
          <StatusIcon className="w-3.5 h-3.5" />
          <span>{config.label}</span>
        </span>
        <span className="text-[11px] font-mono text-slate-400">
          Rel #{relationship.id}
        </span>
      </div>

      {/* Side-by-Side Fact Comparison Matrix or Unified Failure Inspection Card */}
      {isFailure ? (
        <div className="bg-slate-50 border border-slate-200/80 rounded-lg p-4 mb-4">
          <div className="flex items-center justify-between mb-2">
            <span
              className="inline-flex items-center text-[11px] font-bold uppercase tracking-wider text-indigo-700 truncate max-w-[300px]"
              title={factA?.document_filename || 'Source Document'}
            >
              <FileText className="w-3.5 h-3.5 mr-1.5 inline-block text-indigo-500" />
              {cleanDocName(factA?.document_filename) || 'Source Document'}
            </span>
            {factA && (
              <span className="text-xs font-semibold px-2 py-0.5 rounded bg-slate-200/60 text-slate-700">
                Page {factA.page_number}
              </span>
            )}
          </div>

          <h5 className="text-xs font-semibold text-slate-900 mb-1">
            {factA?.entity} — {factA?.metric}
          </h5>
          <div className="font-mono text-sm font-bold text-slate-800 mb-2">
            {factA?.value}{' '}
            <span className="text-xs font-normal text-slate-500">
              {factA?.unit || ''} {factA?.time_period ? `(${factA.time_period})` : ''}
            </span>
          </div>

          {factA?.raw_text_evidence && (
            <p className="text-[11px] font-mono text-slate-600 bg-white/80 p-2.5 rounded border border-slate-100 italic line-clamp-3 mb-3">
              "{factA.raw_text_evidence}"
            </p>
          )}

          {factA && onFactJump && (
            <button
              onClick={() => onFactJump(factA.page_number, factA.document_id)}
              className="inline-flex items-center space-x-1 text-xs font-medium text-indigo-600 hover:text-indigo-800"
            >
              <span>Jump to Page {factA.page_number}</span>
              <ExternalLink className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-4 relative">
          {/* Fact A Block */}
          <div className="bg-slate-50 border border-slate-200/80 rounded-lg p-3.5 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <span
                  className="inline-flex items-center text-[10px] font-bold uppercase tracking-wider text-indigo-700 truncate max-w-[200px]"
                  title={factA?.document_filename || 'Source Document Fact'}
                >
                  <FileText className="w-3 h-3 mr-1 inline-block text-indigo-500" />
                  {cleanDocName(factA?.document_filename) || 'Source Document'}
                </span>
                {factA && (
                  <span className="text-[11px] font-medium text-slate-500">
                    Page {factA.page_number}
                  </span>
                )}
              </div>

              <h5 className="text-xs font-semibold text-slate-900 mb-1">
                {factA?.entity} — {factA?.metric}
              </h5>
              <div className="font-mono text-sm font-bold text-slate-800 mb-2">
                {factA?.value}{' '}
                <span className="text-xs font-normal text-slate-500">
                  {factA?.unit || ''} {factA?.time_period ? `(${factA.time_period})` : ''}
                </span>
              </div>

              {factA?.raw_text_evidence && (
                <p className="text-[11px] font-mono text-slate-600 bg-white/80 p-2 rounded border border-slate-100 italic line-clamp-3">
                  "{factA.raw_text_evidence}"
                </p>
              )}
            </div>

            {factA && onFactJump && (
              <button
                onClick={() => onFactJump(factA.page_number, factA.document_id)}
                className="mt-3 inline-flex items-center space-x-1 text-[11px] font-medium text-indigo-600 hover:text-indigo-800 self-start"
              >
                <span>Jump to Page {factA.page_number}</span>
                <ExternalLink className="w-3 h-3" />
              </button>
            )}
          </div>

          {/* Fact B Block */}
          <div className="bg-slate-50 border border-slate-200/80 rounded-lg p-3.5 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <span
                  className="inline-flex items-center text-[10px] font-bold uppercase tracking-wider text-slate-600 truncate max-w-[200px]"
                  title={factB?.document_filename || 'Corpus Fact Match'}
                >
                  <FileText className="w-3 h-3 mr-1 inline-block text-slate-500" />
                  {cleanDocName(factB?.document_filename) || 'Corpus Match'}
                </span>
                {factB && (
                  <span className="text-[11px] font-medium text-slate-500">
                    Page {factB.page_number}
                  </span>
                )}
              </div>

              <h5 className="text-xs font-semibold text-slate-900 mb-1">
                {factB?.entity} — {factB?.metric}
              </h5>
              <div className="font-mono text-sm font-bold text-slate-800 mb-2">
                {factB?.value}{' '}
                <span className="text-xs font-normal text-slate-500">
                  {factB?.unit || ''} {factB?.time_period ? `(${factB.time_period})` : ''}
                </span>
              </div>

              {factB?.raw_text_evidence && (
                <p className="text-[11px] font-mono text-slate-600 bg-white/80 p-2 rounded border border-slate-100 italic line-clamp-3">
                  "{factB.raw_text_evidence}"
                </p>
              )}
            </div>

            {factB && onFactJump && (
              <button
                onClick={() => onFactJump(factB.page_number, factB.document_id)}
                className="mt-3 inline-flex items-center space-x-1 text-[11px] font-medium text-indigo-600 hover:text-indigo-800 self-start"
              >
                <span>Jump to Page {factB.page_number}</span>
                <ExternalLink className="w-3 h-3" />
              </button>
            )}
          </div>
        </div>
      )}

      {/* High-Contrast, Actionable 1-Sentence Reasoning Box */}
      <div className="bg-slate-50 border-l-4 border-indigo-500 p-3 text-xs font-medium text-slate-800 rounded-r-lg shadow-sm">
        <div className="flex items-center justify-between mb-1.5">
          <div className="flex items-center space-x-2">
            <span
              className={`inline-flex items-center px-2 py-0.5 rounded-full border text-[10px] font-bold uppercase tracking-wider ${microBadge.badgeClass}`}
            >
              {microBadge.label}
            </span>
          </div>
          <span className="text-[10px] font-mono font-medium text-slate-400 uppercase tracking-wider">
            Auditor Insight
          </span>
        </div>
        <p className="text-xs font-medium text-slate-800 leading-snug">
          {relationship.explanation_reasoning}
        </p>
      </div>
    </div>
  );
}
