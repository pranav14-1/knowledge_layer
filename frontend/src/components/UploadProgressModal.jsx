import React, { useState } from 'react';
import {
  FileText,
  Loader2,
  CheckCircle2,
  AlertCircle,
  Clock,
  X,
  ChevronDown,
  ChevronUp,
  UploadCloud,
} from 'lucide-react';

const STATUS_CONFIG = {
  UPLOADING: {
    label: 'Uploading to server...',
    badgeClass: 'bg-indigo-50 text-indigo-700 border-indigo-200',
    icon: Loader2,
    barColor: 'bg-indigo-500',
    spin: true,
  },
  QUEUED: {
    label: 'Queued for processing',
    badgeClass: 'bg-slate-100 text-slate-700 border-slate-200',
    icon: Clock,
    barColor: 'bg-slate-400',
    spin: false,
  },
  PARSING: {
    label: 'Parsing Layout (Docling / PyMuPDF)',
    badgeClass: 'bg-indigo-50 text-indigo-700 border-indigo-200',
    icon: Loader2,
    barColor: 'bg-indigo-600',
    spin: true,
  },
  EXTRACTING: {
    label: 'Extracting & Reconciling Facts',
    badgeClass: 'bg-indigo-50 text-indigo-700 border-indigo-200',
    icon: Loader2,
    barColor: 'bg-indigo-600',
    spin: true,
  },
  COMPLETED: {
    label: 'Processing Complete',
    badgeClass: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    icon: CheckCircle2,
    barColor: 'bg-emerald-500',
    spin: false,
  },
  FAILED: {
    label: 'Failed',
    badgeClass: 'bg-rose-50 text-rose-700 border-rose-200',
    icon: AlertCircle,
    barColor: 'bg-rose-500',
    spin: false,
  },
};

export default function UploadProgressModal({
  documents = [],
  isOpen = false,
  onClose,
}) {
  const [isCollapsed, setIsCollapsed] = useState(false);

  if (!isOpen || documents.length === 0) return null;

  const inProgressCount = documents.filter(
    (d) => d.status !== 'COMPLETED' && d.status !== 'FAILED'
  ).length;

  const sortedDocuments = [...documents].sort((a, b) => {
    const isActiveA = a.status !== 'COMPLETED' && a.status !== 'FAILED';
    const isActiveB = b.status !== 'COMPLETED' && b.status !== 'FAILED';
    if (isActiveA && !isActiveB) return -1;
    if (!isActiveA && isActiveB) return 1;
    return (b.id || 0) - (a.id || 0);
  });

  return (
    <div className="fixed bottom-5 right-5 z-50 w-96 max-w-[calc(100vw-2.5rem)] bg-white border border-slate-200 rounded-2xl shadow-modal overflow-hidden transition-all duration-200 animate-in fade-in slide-in-from-bottom-3">
      {/* Drawer Header */}
      <div className="px-4 py-3 bg-slate-900 text-white flex items-center justify-between">
        <div className="flex items-center space-x-2">
          {inProgressCount > 0 ? (
            <div className="w-2 h-2 rounded-full bg-indigo-400 animate-ping" />
          ) : (
            <div className="w-2 h-2 rounded-full bg-emerald-400" />
          )}
          <span className="text-xs font-semibold tracking-wide">
            {inProgressCount > 0
              ? `Processing ${inProgressCount} ${inProgressCount === 1 ? 'file' : 'files'}...`
              : 'All uploads completed'}
          </span>
        </div>

        <div className="flex items-center space-x-1">
          <button
            onClick={() => setIsCollapsed(!isCollapsed)}
            className="p-1 rounded text-slate-300 hover:text-white hover:bg-slate-800 transition-colors"
            title={isCollapsed ? 'Expand' : 'Collapse'}
          >
            {isCollapsed ? (
              <ChevronUp className="w-4 h-4" />
            ) : (
              <ChevronDown className="w-4 h-4" />
            )}
          </button>

          <button
            onClick={onClose}
            className="p-1 rounded text-slate-300 hover:text-white hover:bg-slate-800 transition-colors"
            title="Dismiss"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Progress Cards List */}
      {!isCollapsed && (
        <div className="p-3 max-h-80 overflow-y-auto space-y-2.5 bg-slate-50">
          {sortedDocuments.map((doc) => {
            const config = STATUS_CONFIG[doc.status] || STATUS_CONFIG.QUEUED;
            const StatusIcon = config.icon;
            const progressVal =
              doc.progress !== undefined
                ? doc.progress
                : doc.status === 'COMPLETED'
                ? 100
                : doc.status === 'EXTRACTING'
                ? 70
                : doc.status === 'PARSING'
                ? 35
                : 15;

            return (
              <div
                key={doc.id || doc.filename}
                className="bg-white border border-slate-200 rounded-xl p-3 shadow-xs transition-all duration-200"
              >
                {/* File Details & Status Badge */}
                <div className="flex items-start justify-between gap-2 mb-2">
                  <div className="flex items-center space-x-2 min-w-0">
                    <div className="w-7 h-7 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center shrink-0">
                      <FileText className="w-4 h-4" />
                    </div>
                    <div className="min-w-0">
                      <p className="text-xs font-semibold text-slate-800 truncate" title={doc.filename}>
                        {doc.filename}
                      </p>
                      {doc.page_count > 1 && (
                        <span className="text-[10px] text-slate-400">
                          {doc.page_count} pages
                        </span>
                      )}
                    </div>
                  </div>

                  <span
                    className={`inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-medium border shrink-0 ${config.badgeClass}`}
                  >
                    <StatusIcon
                      className={`w-3 h-3 ${config.spin ? 'animate-spin' : ''}`}
                    />
                    <span>{config.label}</span>
                  </span>
                </div>

                {/* Progress Bar & Percentage */}
                <div className="space-y-1">
                  <div className="flex items-center justify-between text-[10px] text-slate-400 font-mono">
                    <span>Progress</span>
                    <span className="font-semibold text-slate-700">{progressVal}%</span>
                  </div>
                  <div className="w-full bg-slate-100 rounded-full h-1.5 overflow-hidden">
                    <div
                      className={`h-1.5 rounded-full transition-all duration-300 ease-out ${config.barColor}`}
                      style={{ width: `${Math.max(8, progressVal)}%` }}
                    />
                  </div>
                </div>

                {/* Error Message if Failed */}
                {doc.status === 'FAILED' && doc.error_message && (
                  <p className="mt-2 text-[10px] text-rose-600 bg-rose-50 p-1.5 rounded border border-rose-100 font-mono break-words">
                    {doc.error_message}
                  </p>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
