import React, { useRef } from 'react';
import { Upload, FileText, ChevronDown, Layers, Loader2, Clock } from 'lucide-react';

export default function Header({
  documents = [],
  activeDoc,
  onSelectDoc,
  onUpload,
  isUploading = false,
  processingCount = 0,
  onOpenProgressDrawer,
}) {
  const fileInputRef = useRef(null);

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      onUpload(e.target.files);
      e.target.value = '';
    }
  };

  return (
    <header className="h-16 bg-white border-b border-slate-200 px-6 flex items-center justify-between shrink-0 z-20">
      {/* Brand & Title */}
      <div className="flex items-center space-x-3">
        <div className="w-9 h-9 rounded-xl bg-indigo-600 flex items-center justify-center text-white shadow-sm shadow-indigo-200">
          <Layers className="w-5 h-5" />
        </div>
        <div className="flex items-center space-x-2">
          <h1 className="font-semibold text-slate-900 tracking-tight text-base">
            Fact Knowledge Layer
          </h1>
        </div>
      </div>

      {/* Middle: Active Document Selector & Background Status */}
      <div className="flex items-center space-x-3">
        <div className="relative flex items-center">
          <FileText className="w-4 h-4 text-slate-400 absolute left-3 pointer-events-none" />
          <select
            value={activeDoc ? activeDoc.id : ''}
            onChange={(e) => {
              const selected = documents.find((d) => d.id === Number(e.target.value));
              if (selected) onSelectDoc(selected);
            }}
            disabled={documents.length === 0}
            className="pl-9 pr-9 py-1.5 text-sm bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded-lg text-slate-700 font-medium appearance-none cursor-pointer focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition-all max-w-[280px] truncate"
          >
            {documents.length === 0 ? (
              <option value="">No documents uploaded</option>
            ) : (
              documents.map((doc) => (
                <option key={doc.id} value={doc.id}>
                  {doc.filename} {doc.status === 'PROCESSING' || doc.status === 'PARSING' || doc.status === 'EXTRACTING' ? '(Processing...)' : `(${doc.page_count} p)`}
                </option>
              ))
            )}
          </select>
          <ChevronDown className="w-4 h-4 text-slate-400 absolute right-3 pointer-events-none" />
        </div>

        {processingCount > 0 ? (
          <button
            type="button"
            onClick={onOpenProgressDrawer}
            className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-xs font-medium bg-amber-50 hover:bg-amber-100 text-amber-700 border border-amber-200 transition cursor-pointer"
            title="Click to view processing details"
          >
            <Clock className="w-3 h-3 animate-spin text-amber-600" />
            <span>Parsing {processingCount} {processingCount === 1 ? 'doc' : 'docs'}...</span>
          </button>
        ) : documents.length > 0 ? (
          <button
            type="button"
            onClick={onOpenProgressDrawer}
            className="text-xs text-slate-500 hover:text-slate-800 font-medium px-2 py-0.5 rounded hover:bg-slate-100 transition cursor-pointer"
            title="Click to view upload history"
          >
            {documents.length} {documents.length === 1 ? 'doc' : 'docs'}
          </button>
        ) : null}
      </div>

      {/* Right: Upload Button */}
      <div className="flex items-center space-x-3">
        <input
          type="file"
          ref={fileInputRef}
          onChange={handleFileChange}
          multiple
          accept=".pdf,application/pdf"
          className="hidden"
        />
        <button
          onClick={() => fileInputRef.current && fileInputRef.current.click()}
          disabled={isUploading}
          className="inline-flex items-center space-x-2 bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 text-white rounded-lg px-4 py-2 text-sm font-medium shadow-sm transition-all duration-150 disabled:opacity-60 disabled:cursor-not-allowed"
        >
          {isUploading ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>Uploading PDFs...</span>
            </>
          ) : (
            <>
              <Upload className="w-4 h-4" />
              <span>Upload PDFs</span>
            </>
          )}
        </button>
      </div>
    </header>
  );
}
