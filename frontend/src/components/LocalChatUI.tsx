"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { askQuestion, getCatalog, SourceCatalogItem, AskSource } from "@/lib/api";
import { useToast } from "./ToastProvider";

/* ─────────────────────────────────────────────
   Types
───────────────────────────────────────────── */
type EvidenceStatus = "grounded" | "limited" | "insufficient";

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  sources?: AskSource[];
  evidenceStatus?: EvidenceStatus;
  confidence?: number;
  isGeneral?: boolean;
}

// Minimal SpeechRecognition Type Definitions
declare global {
  interface Window {
    SpeechRecognition: any;
    webkitSpeechRecognition: any;
  }
}

/* ─────────────────────────────────────────────
   Helpers
───────────────────────────────────────────── */
function uid() {
  return Math.random().toString(36).slice(2, 10);
}

function formatDocName(name: string) {
  return name.replace(/\.[^.]+$/, "").replace(/[_-]/g, " ");
}

/* ─────────────────────────────────────────────
   Typing Indicator
───────────────────────────────────────────── */
function TypingDots() {
  return (
    <div className="flex items-center gap-1.5 py-1 px-1">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="block h-1.5 w-1.5 rounded-full bg-[var(--text-muted)]"
          style={{
            animation: "pulse-dot 1.4s ease-in-out infinite",
            animationDelay: `${i * 0.16}s`,
          }}
        />
      ))}
    </div>
  );
}

/* ─────────────────────────────────────────────
   Not-Found Banner
───────────────────────────────────────────── */
function NotFoundBanner({
  onGetGeneral,
  onDismiss,
}: {
  onGetGeneral: () => void;
  onDismiss: () => void;
}) {
  return (
    <div className="flex justify-start mb-4">
      <div className="flex max-w-[85%] flex-wrap items-center justify-between gap-3 rounded-2xl border border-[var(--warning-dim)] bg-[var(--warning-dim)] px-4 py-3">
        <div className="flex items-start gap-3">
          <div className="mt-0.5 text-[var(--warning)]">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" x2="12" y1="9" y2="13"/><line x1="12" x2="12.01" y1="17" y2="17"/></svg>
          </div>
          <div>
            <div className="text-sm font-semibold text-[var(--warning)]">
              No evidence found in your documents
            </div>
            <div className="mt-0.5 text-xs text-[var(--warning)]/80">
              Would you like to ask the local AI using its general knowledge?
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={onGetGeneral}
            className="rounded-lg border border-[var(--warning)]/40 bg-[var(--warning)]/10 px-3 py-1.5 text-xs font-semibold text-[var(--warning)] transition hover:bg-[var(--warning)]/20"
          >
            Get General Answer
          </button>
          <button
            onClick={onDismiss}
            className="rounded-lg border border-[var(--line-strong)] bg-transparent px-3 py-1.5 text-xs font-medium text-[var(--text-muted)] transition hover:bg-[var(--panel-hover)]"
          >
            Dismiss
          </button>
        </div>
      </div>
    </div>
  );
}

/* ─────────────────────────────────────────────
   Message Bubble
───────────────────────────────────────────── */
function MessageBubble({ msg }: { msg: ChatMessage }) {
  const isUser = msg.role === "user";
  const isGeneral = msg.isGeneral;

  if (isUser) {
    return (
      <div className="flex justify-end mb-4">
        <div className="max-w-[75%] rounded-[20px] rounded-tr-sm px-5 py-3.5 text-sm leading-relaxed text-white shadow-sm"
             style={{ background: "linear-gradient(135deg, var(--accent) 0%, var(--accent-bright) 100%)" }}>
          {msg.text}
        </div>
      </div>
    );
  }

  // assistant bubble
  return (
    <div className="flex justify-start mb-6">
      <div className="max-w-[85%]">
        {/* Header */}
        <div className="mb-2 flex items-center gap-2 px-1">
          <div className={`flex h-6 w-6 items-center justify-center rounded-full text-[10px] font-bold ${isGeneral ? 'bg-[var(--success-dim)] text-[var(--success)] border border-[var(--success)]/20' : 'bg-[var(--accent-dim)] text-[var(--accent-bright)] border border-[var(--accent)]/20'}`}>
            {isGeneral ? "G" : "AI"}
          </div>
          <span className="text-[10px] uppercase tracking-widest text-[var(--text-muted)] font-semibold">
            {isGeneral ? "General Knowledge" : "Vault AI"}
          </span>
          {msg.evidenceStatus && !isGeneral && (
            <span className={`tag ${msg.evidenceStatus === "grounded" ? 'tag-success' : msg.evidenceStatus === "limited" ? 'tag-warning' : 'tag-danger'}`}>
              {msg.evidenceStatus === "grounded" ? "✓ Grounded" : msg.evidenceStatus === "limited" ? "~ Partial match" : "Ungrounded"}
            </span>
          )}
        </div>

        {/* Text bubble */}
        <div className={`rounded-[20px] rounded-tl-sm px-5 py-4 text-sm leading-relaxed text-[var(--text-main)] border ${isGeneral ? 'border-[var(--success)]/10 bg-[var(--success-dim)]/50' : 'border-[var(--line)] bg-[var(--panel-main)] shadow-sm'}`}>
          <div className="whitespace-pre-wrap">{msg.text}</div>
        </div>

        {/* Sources */}
        {msg.sources && msg.sources.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2 pl-1">
            <div className="text-[10px] font-semibold uppercase tracking-widest text-[var(--text-muted)] w-full mb-1">Sources</div>
            {msg.sources.slice(0, 4).map((src) => (
              <span key={src.chunk_id} className="tag flex items-center gap-1 border-[var(--line-strong)] bg-[var(--panel-soft)] text-[var(--text-soft)]" title={src.text.slice(0, 150)}>
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
                {formatDocName(src.source_file)}
                {src.page_number && <span className="opacity-50">p.{src.page_number}</span>}
              </span>
            ))}
            {msg.sources.length > 4 && (
              <span className="tag border-[var(--line)] bg-transparent text-[var(--text-muted)]">
                +{msg.sources.length - 4} more
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

/* ─────────────────────────────────────────────
   Main Component
───────────────────────────────────────────── */
export default function LocalChatUI() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [catalog, setCatalog] = useState<SourceCatalogItem[]>([]);
  const [catalogLoading, setCatalogLoading] = useState(true);
  const [isListening, setIsListening] = useState(false);

  // Not-found banner state
  const [notFoundBanner, setNotFoundBanner] = useState<{
    visible: boolean;
    question: string;
  }>({ visible: false, question: "" });

  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const { pushToast } = useToast();

  /* Load indexed documents */
  useEffect(() => {
    (async () => {
      try {
        const res = await getCatalog();
        setCatalog(res.sources);
      } catch {
        // silently fail
      } finally {
        setCatalogLoading(false);
      }
    })();
  }, []);

  /* Auto-scroll */
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading, notFoundBanner.visible]);

  /* Auto-resize textarea */
  function handleInputChange(e: React.ChangeEvent<HTMLTextAreaElement>) {
    setInput(e.target.value);
    e.target.style.height = "auto";
    e.target.style.height = Math.min(e.target.scrollHeight, 160) + "px";
  }

  /* Voice Input */
  const toggleListening = useCallback(() => {
    if (isListening) {
      setIsListening(false);
      return;
    }

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      pushToast("error", "Speech recognition is not supported in this browser.");
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = true;

    recognition.onstart = () => setIsListening(true);
    
    recognition.onresult = (event: any) => {
      let finalTranscript = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const transcript = event.results[i][0].transcript;
        if (event.results[i].isFinal) finalTranscript += transcript;
      }
      if (finalTranscript) {
        setInput((prev) => prev + (prev ? " " : "") + finalTranscript);
      }
    };

    recognition.onerror = () => setIsListening(false);
    recognition.onend = () => setIsListening(false);

    try {
      recognition.start();
    } catch {
      setIsListening(false);
    }
  }, [isListening, pushToast]);

  /* Core send function */
  const sendMessage = useCallback(
    async (question: string, isGeneralFallback = false) => {
      const trimmed = question.trim();
      if (!trimmed || loading) return;

      setNotFoundBanner({ visible: false, question: "" });

      if (!isGeneralFallback) {
        const userMsg: ChatMessage = { id: uid(), role: "user", text: trimmed };
        setMessages((prev) => [...prev, userMsg]);
        setInput("");
        if (textareaRef.current) textareaRef.current.style.height = "auto";
      }

      setLoading(true);
      try {
        const response = await askQuestion(trimmed, {
          topK: 6,
          sourceFiles: [],
          mode: "answer",
          trustMode: !isGeneralFallback,
        });

        const botMsg: ChatMessage = {
          id: uid(),
          role: "assistant",
          text: response.answer,
          sources: response.sources,
          evidenceStatus: response.evidence_status,
          confidence: response.confidence,
          isGeneral: isGeneralFallback,
        };
        setMessages((prev) => [...prev, botMsg]);

        if (response.evidence_status === "insufficient" && !isGeneralFallback) {
          setNotFoundBanner({ visible: true, question: trimmed });
        }
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Something went wrong";
        pushToast("error", msg);
      } finally {
        setLoading(false);
      }
    },
    [loading, pushToast]
  );

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void sendMessage(input);
    }
  }

  function handleGetGeneral() {
    void sendMessage(notFoundBanner.question, true);
  }

  return (
    <div className="flex h-[calc(100vh-8rem)] flex-col gap-4">
      {/* ── Header & Indexed Docs Panel ── */}
      <div className="glow-card shrink-0 p-4 sm:p-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="eyebrow mb-1">Local Intelligence</div>
          <h1 className="font-display text-2xl font-bold text-[var(--text-main)] tracking-tight">Secure Chat</h1>
        </div>
        
        <div className="flex items-center gap-3">
          <div className="text-xs font-medium text-[var(--text-muted)] uppercase tracking-wider">Indexed Context</div>
          {catalogLoading ? (
            <div className="h-6 w-20 skeleton rounded-full" />
          ) : catalog.length === 0 ? (
            <span className="tag">Empty Vault</span>
          ) : (
            <div className="flex -space-x-2">
              {catalog.slice(0, 3).map((doc, i) => (
                <div key={i} className="flex h-8 w-8 items-center justify-center rounded-full border-2 border-[var(--panel-main)] bg-[var(--panel-soft)] text-[10px] font-bold text-[var(--text-muted)]" title={doc.source_file}>
                  {formatDocName(doc.source_file).slice(0,2).toUpperCase()}
                </div>
              ))}
              {catalog.length > 3 && (
                <div className="flex h-8 w-8 items-center justify-center rounded-full border-2 border-[var(--panel-main)] bg-[var(--accent-dim)] text-[10px] font-bold text-[var(--accent-bright)]">
                  +{catalog.length - 3}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* ── Chat Window ── */}
      <div className="glow-card flex min-h-0 flex-1 flex-col overflow-hidden">
        <div className="flex-1 overflow-y-auto p-4 sm:p-6 scroll-smooth">
          {messages.length === 0 && !loading ? (
            <div className="flex h-full flex-col items-center justify-center text-center animate-fade">
              <div className="mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-[var(--accent-dim)] text-[var(--accent-bright)] border border-[var(--accent)]/20 shadow-sm">
                <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
              </div>
              <h3 className="text-xl font-display font-bold text-[var(--text-main)] mb-2">How can I help?</h3>
              <p className="text-sm text-[var(--text-muted)] max-w-md mb-8">
                Ask me anything about the data in your vault. I run entirely on your local machine, ensuring 100% privacy.
              </p>
              
              <div className="grid sm:grid-cols-2 gap-3 w-full max-w-lg">
                {[
                  "Summarize my recent documents",
                  "What are the key concepts?",
                  "Explain the technical architecture",
                  "Find definitions for all acronyms"
                ].map(q => (
                  <button key={q} onClick={() => void sendMessage(q)} className="rounded-xl border border-[var(--line)] bg-[var(--panel-soft)] p-3 text-left text-sm text-[var(--text-soft)] transition hover:border-[var(--accent)]/30 hover:bg-[var(--accent-dim)]/50">
                    {q}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="mx-auto max-w-4xl space-y-2">
              {messages.map((msg) => (
                <MessageBubble key={msg.id} msg={msg} />
              ))}
              {loading && (
                <div className="flex justify-start mb-6 animate-fade">
                  <div className="rounded-[20px] rounded-tl-sm border border-[var(--line)] bg-[var(--panel-main)] px-5 py-3 shadow-sm">
                    <TypingDots />
                  </div>
                </div>
              )}
              {notFoundBanner.visible && !loading && (
                <NotFoundBanner onGetGeneral={handleGetGeneral} onDismiss={() => setNotFoundBanner({ visible: false, question: "" })} />
              )}
              <div ref={bottomRef} className="h-4" />
            </div>
          )}
        </div>

        {/* ── Input Bar ── */}
        <div className="border-t border-[var(--line)] bg-[var(--bg-subtle)]/50 p-4 backdrop-blur-md">
          <div className="mx-auto max-w-4xl relative">
            <div className="flex items-end gap-3 rounded-2xl border border-[var(--line-strong)] bg-[var(--panel-main)] p-2 shadow-sm transition-all focus-within:border-[var(--accent)]/50 focus-within:ring-4 focus-within:ring-[var(--accent)]/10">
              <button
                onClick={toggleListening}
                className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl transition ${isListening ? 'bg-[var(--danger-dim)] text-[var(--danger)] animate-pulse' : 'bg-transparent text-[var(--text-muted)] hover:bg-[var(--panel-hover)]'}`}
                title="Voice input"
              >
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" x2="12" y1="19" y2="22"/></svg>
              </button>

              <textarea
                ref={textareaRef}
                value={input}
                onChange={handleInputChange}
                onKeyDown={handleKeyDown}
                placeholder={isListening ? "Listening..." : "Message your offline AI..."}
                rows={1}
                disabled={loading}
                className="my-auto max-h-32 min-h-[40px] flex-1 resize-none bg-transparent px-2 py-2 text-sm text-[var(--text-main)] outline-none placeholder:text-[var(--text-muted)] disabled:opacity-50 scrollbar-hide"
              />

              <button
                onClick={() => void sendMessage(input)}
                disabled={loading || (!input.trim() && !isListening)}
                className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[var(--accent)] text-white shadow-sm transition hover:bg-[var(--accent-bright)] disabled:opacity-30 disabled:hover:bg-[var(--accent)]"
              >
                {loading ? (
                  <svg className="animate-spin" width="18" height="18" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" strokeDasharray="31.4" strokeDashoffset="10"/></svg>
                ) : (
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/></svg>
                )}
              </button>
            </div>
            <div className="mt-2 text-center text-[10px] text-[var(--text-muted)]">
              AI can make mistakes. All processing happens locally.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
