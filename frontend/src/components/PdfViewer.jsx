import React, { useState, useEffect, useRef } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import {
  ChevronLeft,
  ChevronRight,
  ZoomIn,
  ZoomOut,
  Maximize2,
  FileSearch,
  Loader2,
  AlertCircle,
} from 'lucide-react';
import { api } from '../api';

// Set up pdfjs worker using matching cdn version
pdfjs.GlobalWorkerOptions.workerSrc = `https://unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

export default function PdfViewer({ activeDoc, currentPage = 1, onPageChange }) {
  const [numPages, setNumPages] = useState(null);
  const [pageNumber, setPageNumber] = useState(currentPage);
  const [scale, setScale] = useState(1.1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const containerRef = useRef(null);

  // Sync internal pageNumber when parent passes new currentPage prop
  useEffect(() => {
    if (currentPage && currentPage !== pageNumber) {
      setPageNumber(currentPage);
    }
  }, [currentPage]);

  // Reset state on document change
  useEffect(() => {
    setLoading(true);
    setError(null);
    setPageNumber(currentPage || 1);
  }, [activeDoc?.id]);

  function onDocumentLoadSuccess({ numPages }) {
    setNumPages(numPages);
    setLoading(false);
  }

  function onDocumentLoadError(err) {
    console.error('Error loading PDF document:', err);
    setError('Failed to load PDF document.');
    setLoading(false);
  }

  const changePage = (offset) => {
    setPageNumber((prev) => {
      const next = prev + offset;
      const clamped = Math.max(1, Math.min(next, numPages || 1));
      if (onPageChange) onPageChange(clamped);
      return clamped;
    });
  };

  const setExplicitPage = (val) => {
    const num = parseInt(val, 10);
    if (!isNaN(num) && num >= 1 && num <= (numPages || 1)) {
      setPageNumber(num);
      if (onPageChange) onPageChange(num);
    }
  };

  if (!activeDoc) {
    return (
      <div className="h-full flex flex-col items-center justify-center p-8 text-center bg-panel">
        <div className="w-12 h-12 rounded-full bg-slate-100 flex items-center justify-center text-slate-400 mb-3">
          <FileSearch className="w-6 h-6" />
        </div>
        <h3 className="text-sm font-semibold text-slate-700">No Document Selected</h3>
        <p className="text-xs text-slate-500 max-w-xs mt-1">
          Upload or select a PDF document from the header dropdown to inspect layout and facts.
        </p>
      </div>
    );
  }

  const pdfUrl = api.getPdfUrl(activeDoc.filename);

  return (
    <div className="h-full flex flex-col bg-slate-50 relative overflow-hidden">
      {/* Floating Glassmorphism Toolbar */}
      <div className="absolute top-4 left-1/2 -translate-x-1/2 z-10 bg-white/90 backdrop-blur-md border border-slate-200 shadow-glass rounded-xl px-3 py-1.5 flex items-center space-x-2 text-xs font-medium text-slate-700">
        {/* Page Nav */}
        <button
          onClick={() => changePage(-1)}
          disabled={pageNumber <= 1}
          className="p-1 rounded hover:bg-slate-100 disabled:opacity-40 disabled:hover:bg-transparent"
          title="Previous Page"
        >
          <ChevronLeft className="w-4 h-4" />
        </button>

        <div className="flex items-center space-x-1">
          <input
            type="number"
            value={pageNumber}
            onChange={(e) => setExplicitPage(e.target.value)}
            className="w-10 text-center py-0.5 border border-slate-200 rounded text-slate-800 font-semibold focus:outline-none focus:ring-1 focus:ring-indigo-500"
            min={1}
            max={numPages || 1}
          />
          <span className="text-slate-400">/</span>
          <span>{numPages || '–'}</span>
        </div>

        <button
          onClick={() => changePage(1)}
          disabled={numPages ? pageNumber >= numPages : true}
          className="p-1 rounded hover:bg-slate-100 disabled:opacity-40 disabled:hover:bg-transparent"
          title="Next Page"
        >
          <ChevronRight className="w-4 h-4" />
        </button>

        <div className="h-4 w-px bg-slate-200 mx-1" />

        {/* Zoom Controls */}
        <button
          onClick={() => setScale((s) => Math.max(0.6, s - 0.15))}
          className="p-1 rounded hover:bg-slate-100"
          title="Zoom Out"
        >
          <ZoomOut className="w-3.5 h-3.5" />
        </button>

        <span className="w-11 text-center font-mono text-[11px] text-slate-500">
          {Math.round(scale * 100)}%
        </span>

        <button
          onClick={() => setScale((s) => Math.min(2.2, s + 0.15))}
          className="p-1 rounded hover:bg-slate-100"
          title="Zoom In"
        >
          <ZoomIn className="w-3.5 h-3.5" />
        </button>

        <button
          onClick={() => setScale(1.1)}
          className="p-1 rounded hover:bg-slate-100 text-slate-400 hover:text-slate-700"
          title="Reset Zoom"
        >
          <Maximize2 className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* PDF Viewport Scroll Container */}
      <div
        ref={containerRef}
        className="flex-1 overflow-auto p-8 pt-16 flex justify-center items-start"
      >
        {error ? (
          <div className="m-auto flex flex-col items-center justify-center p-6 text-center text-rose-600">
            <AlertCircle className="w-8 h-8 mb-2" />
            <p className="text-sm font-semibold">{error}</p>
            <p className="text-xs text-slate-500 mt-1">
              Please verify backend server is running on port 8000.
            </p>
          </div>
        ) : (
          <Document
            file={pdfUrl}
            onLoadSuccess={onDocumentLoadSuccess}
            onLoadError={onDocumentLoadError}
            loading={
              <div className="m-auto flex flex-col items-center justify-center p-12 text-slate-400">
                <Loader2 className="w-6 h-6 animate-spin mb-2 text-indigo-600" />
                <span className="text-xs font-medium">Loading document...</span>
              </div>
            }
          >
            <div className="relative shadow-md rounded-md overflow-hidden bg-white">
              <Page
                pageNumber={pageNumber}
                scale={scale}
                renderTextLayer={false}
                renderAnnotationLayer={false}
              />
            </div>
          </Document>
        )}
      </div>
    </div>
  );
}

