import React, { useState, useRef, useEffect } from 'react';
import { Plus, MessageSquare, Trash2, Edit2, Check, X } from 'lucide-react';

export default function WorkspaceSidebar({
  sessions = [],
  activeSessionId,
  onSelectSession,
  onCreateSession,
  onRenameSession,
  onDeleteSession,
}) {
  const [editingId, setEditingId] = useState(null);
  const [editTitle, setEditTitle] = useState('');
  const editInputRef = useRef(null);

  useEffect(() => {
    if (editingId && editInputRef.current) {
      editInputRef.current.focus();
      editInputRef.current.select();
    }
  }, [editingId]);

  const startEditing = (e, session) => {
    e.stopPropagation();
    setEditingId(session.id);
    setEditTitle(session.title || '');
  };

  const cancelEditing = (e) => {
    if (e) e.stopPropagation();
    setEditingId(null);
    setEditTitle('');
  };

  const handleSaveTitle = async (e, sessionId) => {
    if (e) e.stopPropagation();
    const trimmed = editTitle.trim();
    if (trimmed && onRenameSession) {
      await onRenameSession(sessionId, trimmed);
    }
    setEditingId(null);
    setEditTitle('');
  };

  const handleKeyDown = (e, sessionId) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleSaveTitle(e, sessionId);
    } else if (e.key === 'Escape') {
      e.preventDefault();
      cancelEditing(e);
    }
  };

  const handleDelete = (e, sessionId, sessionTitle) => {
    e.stopPropagation();
    const confirmed = window.confirm(
      `Are you sure you want to delete "${sessionTitle || 'this workspace'}" and all its documents?`
    );
    if (confirmed && onDeleteSession) {
      onDeleteSession(sessionId);
    }
  };

  return (
    <div className="w-60 border-r border-slate-200 bg-slate-50 flex flex-col shrink-0 h-full">
      {/* Brand / New Workspace Header */}
      <div className="p-3 border-b border-slate-200">
        <button
          onClick={onCreateSession}
          className="w-full flex items-center justify-center space-x-2 py-2 px-3 bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 text-white rounded-lg text-xs font-semibold shadow-xs transition-colors cursor-pointer"
        >
          <Plus className="w-3.5 h-3.5" />
          <span>New Workspace</span>
        </button>
      </div>

      {/* Workspaces List Header */}
      <div className="px-3 py-2 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
        Workspaces
      </div>

      {/* Sessions List */}
      <div className="flex-1 overflow-y-auto px-2 pb-2 space-y-1">
        {sessions.map((s) => {
          const isActive = s.id === activeSessionId;
          const isEditing = editingId === s.id;

          return (
            <div
              key={s.id}
              onClick={() => !isEditing && onSelectSession(s.id)}
              className={`group relative flex items-center justify-between px-2.5 py-2 rounded-lg text-xs cursor-pointer transition-colors ${
                isActive
                  ? 'bg-white text-indigo-900 font-semibold shadow-xs border border-slate-200'
                  : 'text-slate-600 hover:bg-slate-100/80 hover:text-slate-900'
              }`}
            >
              {isEditing ? (
                <div
                  className="flex items-center space-x-1.5 w-full"
                  onClick={(e) => e.stopPropagation()}
                >
                  <input
                    ref={editInputRef}
                    type="text"
                    value={editTitle}
                    onChange={(e) => setEditTitle(e.target.value)}
                    onKeyDown={(e) => handleKeyDown(e, s.id)}
                    className="flex-1 px-1.5 py-0.5 text-xs bg-white border border-indigo-400 rounded focus:outline-none focus:ring-1 focus:ring-indigo-500 font-medium text-slate-800"
                  />
                  <button
                    onClick={(e) => handleSaveTitle(e, s.id)}
                    className="p-1 text-emerald-600 hover:text-emerald-700 hover:bg-emerald-50 rounded"
                    title="Save name"
                  >
                    <Check className="w-3.5 h-3.5" />
                  </button>
                  <button
                    onClick={cancelEditing}
                    className="p-1 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded"
                    title="Cancel"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>
              ) : (
                <>
                  <div className="flex items-center space-x-2 min-w-0 flex-1 pr-1">
                    <MessageSquare
                      className={`w-3.5 h-3.5 shrink-0 ${
                        isActive ? 'text-indigo-600' : 'text-slate-400'
                      }`}
                    />
                    <span className="truncate" title={s.title}>
                      {s.title || 'Untitled Workspace'}
                    </span>
                  </div>

                  {/* Actions: Edit & Delete */}
                  <div className="flex items-center space-x-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button
                      onClick={(e) => startEditing(e, s)}
                      className="p-1 text-slate-400 hover:text-indigo-600 hover:bg-slate-100 rounded transition cursor-pointer"
                      title="Rename workspace"
                    >
                      <Edit2 className="w-3 h-3" />
                    </button>
                    <button
                      onClick={(e) => handleDelete(e, s.id, s.title)}
                      className="p-1 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded transition cursor-pointer"
                      title="Delete workspace"
                    >
                      <Trash2 className="w-3 h-3" />
                    </button>
                  </div>
                </>
              )}
            </div>
          );
        })}

        {sessions.length === 0 && (
          <div className="text-center p-4 text-xs text-slate-400">
            No workspaces yet.
          </div>
        )}
      </div>
    </div>
  );
}
