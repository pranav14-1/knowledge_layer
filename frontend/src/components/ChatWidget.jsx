import React, { useState, useEffect, useRef } from 'react';
import { Bot, User, Send, Loader2, FileText, ExternalLink, ChevronRight, Sparkles } from 'lucide-react';
import { api } from '../api';

export default function ChatWidget({ activeSessionId, activeDoc, onPageSelect }) {
  const [messages, setMessages] = useState([]);
  const [inputContent, setInputContent] = useState('');
  const [isLoadingMessages, setIsLoadingMessages] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isSending]);

  useEffect(() => {
    if (!activeSessionId) {
      setMessages([]);
      return;
    }
    let isCurrent = true;
    setIsLoadingMessages(true);

    api.getChat(activeSessionId)
      .then((detail) => {
        if (isCurrent) {
          setMessages(detail.messages || []);
          setIsLoadingMessages(false);
        }
      })
      .catch((err) => {
        console.error(`Failed to load messages for chat ${activeSessionId}:`, err);
        if (isCurrent) setIsLoadingMessages(false);
      });

    return () => {
      isCurrent = false;
    };
  }, [activeSessionId]);

  const handleSendMessage = async (e) => {
    if (e) e.preventDefault();
    const trimmed = inputContent.trim();
    if (!trimmed || !activeSessionId || isSending) return;

    const optimisticMsg = {
      id: `temp-${Date.now()}`,
      session_id: activeSessionId,
      role: 'user',
      content: trimmed,
      citations: [],
      created_at: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, optimisticMsg]);
    setInputContent('');
    setIsSending(true);

    try {
      const docFilterId = activeDoc ? activeDoc.id : null;
      const assistantReply = await api.sendChatMessage(activeSessionId, trimmed, docFilterId);
      setMessages((prev) => [...prev, assistantReply]);
    } catch (err) {
      console.error('Failed to send message:', err);
      setMessages((prev) => [
        ...prev,
        {
          id: `err-${Date.now()}`,
          session_id: activeSessionId,
          role: 'assistant',
          content: 'Sorry, I encountered an issue processing your request. Please try again.',
          citations: [],
          created_at: new Date().toISOString(),
        },
      ]);
    } finally {
      setIsSending(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden bg-white">
      {/* Context Bar */}
      <div className="px-5 py-2.5 bg-slate-50/70 border-b border-slate-100 flex items-center justify-between text-xs">
        <div className="flex items-center space-x-2 text-slate-600">
          <Sparkles className="w-3.5 h-3.5 text-indigo-600" />
          <span className="font-medium">
            Grounded in {activeDoc ? activeDoc.filename : 'All Uploaded Documents'}
          </span>
        </div>
        {activeDoc && (
          <span className="text-[10px] text-slate-400 font-mono">
            Filtered to Doc #{activeDoc.id}
          </span>
        )}
      </div>

      {/* Messages Container */}
      <div className="flex-1 overflow-y-auto p-6 space-y-5">
        {isLoadingMessages ? (
          <div className="h-full flex flex-col items-center justify-center text-slate-400">
            <Loader2 className="w-6 h-6 animate-spin text-indigo-600 mb-2" />
            <span className="text-xs">Loading conversation history...</span>
          </div>
        ) : messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center p-6 text-slate-400">
            <div className="w-10 h-10 rounded-full bg-indigo-50 text-indigo-600 flex items-center justify-center mb-3">
              <Bot className="w-5 h-5" />
            </div>
            <h4 className="text-sm font-semibold text-slate-800">
              Grounded Knowledge Assistant
            </h4>
            <p className="text-xs text-slate-500 max-w-sm mt-1 mb-5">
              Ask any question about financial metrics, entities, or reconciliations across your documents.
            </p>

            <div className="grid grid-cols-1 gap-2 w-full max-w-md text-left">
              {[
                'What are the key financial metrics reported?',
                'Compare reported revenues across the documents',
                'Are there any conflicting numbers or contradictions?',
              ].map((prompt, idx) => (
                <button
                  key={idx}
                  onClick={() => setInputContent(prompt)}
                  className="p-2.5 bg-slate-50 hover:bg-indigo-50 border border-slate-200 hover:border-indigo-200 rounded-lg text-xs text-slate-700 hover:text-indigo-900 transition flex items-center justify-between group cursor-pointer"
                >
                  <span>{prompt}</span>
                  <ChevronRight className="w-3.5 h-3.5 text-slate-400 group-hover:text-indigo-600" />
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((msg) => {
            const isUser = msg.role === 'user';
            return (
              <div key={msg.id} className={`flex items-start space-x-3 ${isUser ? 'flex-row-reverse space-x-reverse' : ''}`}>
                <div className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 text-xs font-semibold ${isUser ? 'bg-slate-900 text-white' : 'bg-indigo-50 text-indigo-600 border border-indigo-100'}`}>
                  {isUser ? <User className="w-3.5 h-3.5" /> : <Bot className="w-4 h-4" />}
                </div>

                <div className={`max-w-[85%] rounded-xl p-3.5 text-xs leading-relaxed ${isUser ? 'bg-slate-900 text-white shadow-xs' : 'bg-white border border-slate-200 text-slate-800 shadow-xs'}`}>
                  <div className="whitespace-pre-wrap">{msg.content}</div>

                  {!isUser && msg.citations && msg.citations.length > 0 && (
                    <div className="mt-3 pt-2.5 border-t border-slate-100">
                      <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 block mb-1.5">
                        Sources & Evidence
                      </span>
                      <div className="flex flex-wrap gap-1.5">
                        {msg.citations.map((c, cIdx) => (
                          <button
                            key={cIdx}
                            onClick={() => {
                              if (c.page_number && onPageSelect) {
                                onPageSelect(c.page_number, c.document_id);
                              }
                            }}
                            className="inline-flex items-center space-x-1 px-2 py-0.5 rounded bg-indigo-50 hover:bg-indigo-100 border border-indigo-200 text-indigo-800 text-[10px] font-medium transition cursor-pointer"
                            title={c.evidence ? `Quote: "${c.evidence}"` : 'Jump to page'}
                          >
                            <FileText className="w-2.5 h-2.5 text-indigo-600" />
                            <span className="truncate max-w-[120px]">
                              {c.filename || 'Document'}
                            </span>
                            <span className="text-indigo-500 font-mono">
                              p.{c.page_number || 1}
                            </span>
                            <ExternalLink className="w-2.5 h-2.5 text-indigo-500" />
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            );
          })
        )}

        {isSending && (
          <div className="flex items-start space-x-3">
            <div className="w-7 h-7 rounded-lg bg-indigo-50 text-indigo-600 border border-indigo-100 flex items-center justify-center shrink-0">
              <Bot className="w-4 h-4" />
            </div>
            <div className="bg-white border border-slate-200 rounded-xl p-3 shadow-xs flex items-center space-x-2 text-xs text-slate-500">
              <Loader2 className="w-3.5 h-3.5 animate-spin text-indigo-600" />
              <span>Searching knowledge facts & reasoning...</span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Bar */}
      <div className="p-3 border-t border-slate-200 bg-white">
        <form onSubmit={handleSendMessage} className="flex items-center space-x-2">
          <input
            type="text"
            value={inputContent}
            onChange={(e) => setInputContent(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isSending || !activeSessionId}
            placeholder="Ask anything about the extracted facts... (Press Enter to send)"
            className="flex-1 px-3.5 py-2 text-xs bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 text-slate-800 placeholder-slate-400 disabled:opacity-60 transition"
          />
          <button
            type="submit"
            disabled={!inputContent.trim() || isSending || !activeSessionId}
            className="p-2 bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 disabled:opacity-40 disabled:cursor-not-allowed text-white rounded-lg transition shadow-xs cursor-pointer"
            title="Send message"
          >
            {isSending ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Send className="w-4 h-4" />
            )}
          </button>
        </form>
      </div>
    </div>
  );
}
