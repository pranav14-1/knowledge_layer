import React, { useState, useEffect, useCallback, useRef } from 'react';
import Header from './components/Header';
import PdfViewer from './components/PdfViewer';
import FactDashboard from './components/FactDashboard';
import UploadProgressModal from './components/UploadProgressModal';
import WorkspaceSidebar from './components/WorkspaceSidebar';
import { api } from './api';

const STORAGE_KEY_DOC_ID = 'fact_layer_active_doc_id';
const STORAGE_KEY_PAGE = 'fact_layer_active_page';
const STORAGE_ACTIVE_CHAT = 'fact_layer_active_chat_id';

export default function App() {
  const [sessions, setSessions] = useState([]);
  const [activeSessionId, setActiveSessionId] = useState(() => {
    const saved = localStorage.getItem(STORAGE_ACTIVE_CHAT);
    return saved ? Number(saved) : null;
  });

  const [documents, setDocuments] = useState([]);
  const [activeDoc, setActiveDoc] = useState(null);
  const [facts, setFacts] = useState([]);
  const [relationships, setRelationships] = useState([]);
  const [currentPage, setCurrentPage] = useState(() => {
    const saved = localStorage.getItem(STORAGE_KEY_PAGE);
    return saved ? parseInt(saved, 10) : 1;
  });
  const [selectedFactId, setSelectedFactId] = useState(null);
  const [isUploading, setIsUploading] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [processingCount, setProcessingCount] = useState(0);
  const [showProgressDrawer, setShowProgressDrawer] = useState(false);
  const [pendingUploads, setPendingUploads] = useState([]);
  const [errorToast, setErrorToast] = useState(null);

  const pollingTimerRef = useRef(null);

  const stopPolling = useCallback(() => {
    if (pollingTimerRef.current) {
      clearInterval(pollingTimerRef.current);
      pollingTimerRef.current = null;
    }
    setIsProcessing(false);
    setProcessingCount(0);
  }, []);

  // Load chat sessions on mount
  const loadSessions = useCallback(async () => {
    try {
      const data = await api.getChats();
      setSessions(data);
      if (data.length > 0) {
        if (!activeSessionId || !data.some((s) => s.id === activeSessionId)) {
          setActiveSessionId(data[0].id);
          localStorage.setItem(STORAGE_ACTIVE_CHAT, data[0].id);
        }
      }
    } catch (err) {
      console.error('Failed to load chat sessions:', err);
    }
  }, [activeSessionId]);

  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  const handleNewChat = async () => {
    try {
      const newSession = await api.createChat('New Workspace');
      setSessions((prev) => [newSession, ...prev]);
      setActiveSessionId(newSession.id);
      localStorage.setItem(STORAGE_ACTIVE_CHAT, newSession.id);
    } catch (err) {
      console.error('Failed to create new chat session:', err);
    }
  };

  const handleDeleteChat = async (sessionId) => {
    try {
      await api.deleteChat(sessionId);
      const remaining = sessions.filter((s) => s.id !== sessionId);
      setSessions(remaining);
      if (activeSessionId === sessionId) {
        const nextId = remaining[0]?.id || null;
        setActiveSessionId(nextId);
        if (nextId) localStorage.setItem(STORAGE_ACTIVE_CHAT, nextId);
        else localStorage.removeItem(STORAGE_ACTIVE_CHAT);
      }
    } catch (err) {
      console.error('Failed to delete chat session:', err);
    }
  };

  const handleRenameChat = async (sessionId, newTitle) => {
    try {
      const updated = await api.updateChat(sessionId, newTitle);
      setSessions((prev) =>
        prev.map((s) => (s.id === sessionId ? { ...s, title: updated.title } : s))
      );
    } catch (err) {
      console.error('Failed to rename chat session:', err);
    }
  };

  const refreshData = useCallback(async (preferredDocId = null) => {
    if (!activeSessionId) {
      setDocuments([]);
      setActiveDoc(null);
      setFacts([]);
      setRelationships([]);
      return [];
    }

    try {
      const docs = await api.getDocuments(activeSessionId);
      setDocuments(docs);

      const processing = docs.filter(
        (d) => d.status === 'QUEUED' || d.status === 'PARSING' || d.status === 'EXTRACTING' || d.status === 'PROCESSING'
      );
      setProcessingCount(processing.length);
      if (processing.length > 0) {
        setIsProcessing(true);
        setShowProgressDrawer(true);
      } else {
        setIsProcessing(false);
      }

      const savedDocId = preferredDocId || Number(localStorage.getItem(STORAGE_KEY_DOC_ID));
      let current = null;
      if (savedDocId) {
        current = docs.find((d) => d.id === savedDocId) || null;
      }
      if (!current && docs.length > 0) {
        current = docs[0];
      }
      setActiveDoc(current);
      if (current) {
        localStorage.setItem(STORAGE_KEY_DOC_ID, current.id);
      }

      if (current) {
        const docFacts = await api.getFacts(current.id, activeSessionId);
        setFacts(docFacts);
      } else {
        setFacts([]);
      }

      const rels = await api.getRelationships(null, activeSessionId);
      setRelationships(rels);

      return docs;
    } catch (err) {
      console.error('Failed to load initial data:', err);
      return [];
    }
  }, [activeSessionId]);

  useEffect(() => {
    if (activeSessionId) {
      localStorage.setItem(STORAGE_ACTIVE_CHAT, activeSessionId);
      refreshData();
    }
  }, [activeSessionId, refreshData]);

  const startPolling = useCallback(() => {
    if (pollingTimerRef.current || !activeSessionId) return;

    pollingTimerRef.current = setInterval(async () => {
      try {
        const statusData = await api.getDocumentsStatus(activeSessionId);
        const pending = statusData.documents.filter(
          (d) => d.status !== 'COMPLETED' && d.status !== 'FAILED'
        );
        setProcessingCount(pending.length);

        setDocuments((prevDocs) =>
          prevDocs.map((doc) => {
            const match = statusData.documents.find((s) => s.id === doc.id);
            return match ? { ...doc, ...match } : doc;
          })
        );

        if (statusData.all_completed || pending.length === 0) {
          stopPolling();
          await refreshData();
        }
      } catch (err) {
        console.warn('Status polling check failed:', err);
      }
    }, 1500);
  }, [refreshData, stopPolling, activeSessionId]);

  useEffect(() => {
    if (isProcessing) {
      startPolling();
    } else {
      stopPolling();
    }
    return () => {
      if (pollingTimerRef.current) clearInterval(pollingTimerRef.current);
    };
  }, [isProcessing, startPolling, stopPolling]);

  const handleSelectDoc = async (doc) => {
    setActiveDoc(doc);
    setCurrentPage(1);
    setSelectedFactId(null);
    if (doc?.id) {
      localStorage.setItem(STORAGE_KEY_DOC_ID, doc.id);
      localStorage.setItem(STORAGE_KEY_PAGE, '1');
      try {
        const docFacts = await api.getFacts(doc.id, activeSessionId);
        setFacts(docFacts);
      } catch (err) {
        console.error('Error fetching facts for doc:', err);
      }
    }
  };

  const handleUpload = async (fileList) => {
    if (!fileList || fileList.length === 0 || !activeSessionId) return;

    const validFiles = Array.from(fileList).filter((f) =>
      f.name.toLowerCase().endsWith('.pdf')
    );

    if (validFiles.length === 0) {
      setErrorToast('Please select valid PDF files (.pdf) only.');
      return;
    }

    const optimisticDocs = validFiles.map((file, idx) => ({
      id: `pending-${Date.now()}-${idx}`,
      filename: file.name,
      page_count: 1,
      status: 'UPLOADING',
      progress: 15,
    }));

    setPendingUploads(optimisticDocs);
    setIsUploading(true);
    setErrorToast(null);
    setShowProgressDrawer(true);

    try {
      const res = await api.uploadDocuments(validFiles, activeSessionId);
      const newlyUploadedId = res.documents?.[0]?.id;

      setPendingUploads([]);
      await refreshData(newlyUploadedId);
      setIsProcessing(true);
      startPolling();
    } catch (err) {
      console.error('Upload failed:', err);
      setPendingUploads([]);
      setErrorToast(
        err.response?.data?.detail || 'Failed to upload PDF files. Please ensure only valid PDFs are selected.'
      );
    } finally {
      setIsUploading(false);
    }
  };

  const handlePageSelect = (pageNumber, docId) => {
    if (docId && activeDoc && activeDoc.id !== docId) {
      const targetDoc = documents.find((d) => d.id === docId);
      if (targetDoc) {
        setActiveDoc(targetDoc);
        localStorage.setItem(STORAGE_KEY_DOC_ID, targetDoc.id);
        api.getFacts(targetDoc.id, activeSessionId).then(setFacts).catch(console.error);
      }
    }
    setCurrentPage(pageNumber);
    localStorage.setItem(STORAGE_KEY_PAGE, String(pageNumber));
  };

  const handleFactJump = (pageNumber, docId) => {
    handlePageSelect(pageNumber, docId);
  };

  const allDisplayDocs = [
    ...pendingUploads,
    ...documents.filter((d) => !pendingUploads.some((p) => p.filename === d.filename)),
  ];

  return (
    <div className="h-screen flex bg-white overflow-hidden select-none">
      {/* Workspaces Sidebar */}
      <WorkspaceSidebar
        sessions={sessions}
        activeSessionId={activeSessionId}
        onSelectSession={setActiveSessionId}
        onCreateSession={handleNewChat}
        onRenameSession={handleRenameChat}
        onDeleteSession={handleDeleteChat}
      />

      <div className="flex-1 flex flex-col min-w-0">
        <Header
          documents={documents}
          activeDoc={activeDoc}
          onSelectDoc={handleSelectDoc}
          onUpload={handleUpload}
          isUploading={isUploading}
          processingCount={processingCount}
          onOpenProgressDrawer={() => setShowProgressDrawer(true)}
        />

        {errorToast && (
          <div className="bg-rose-50 border-b border-rose-200 px-6 py-2 text-xs text-rose-700 flex items-center justify-between">
            <span>{errorToast}</span>
            <button
              onClick={() => setErrorToast(null)}
              className="font-bold hover:text-rose-900 ml-4"
            >
              ×
            </button>
          </div>
        )}

        {activeSessionId ? (
          <main className="flex-1 flex overflow-hidden">
            <section className="w-1/2 h-full border-r border-slate-200 flex flex-col">
              <PdfViewer
                activeDoc={activeDoc}
                currentPage={currentPage}
                onPageChange={(page) => {
                  setCurrentPage(page);
                  localStorage.setItem(STORAGE_KEY_PAGE, String(page));
                }}
              />
            </section>

            <section className="w-1/2 h-full flex flex-col bg-white">
              <FactDashboard
                activeSessionId={activeSessionId}
                facts={facts}
                relationships={relationships}
                activeDoc={activeDoc}
                selectedFactId={selectedFactId}
                onPageSelect={handlePageSelect}
                onFactJump={handleFactJump}
              />
            </section>
          </main>
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center text-slate-500 p-8">
            <p>Select or create a workspace to begin.</p>
            <button onClick={handleNewChat} className="mt-4 px-4 py-2 bg-indigo-600 text-white rounded shadow-sm text-sm hover:bg-indigo-700">
              Create Workspace
            </button>
          </div>
        )}

        <UploadProgressModal
          documents={allDisplayDocs}
          isOpen={showProgressDrawer}
          onClose={() => setShowProgressDrawer(false)}
        />
      </div>
    </div>
  );
}
