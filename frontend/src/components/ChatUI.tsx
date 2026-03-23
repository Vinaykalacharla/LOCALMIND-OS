"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import AnnotatedAnswer from "@/components/AnnotatedAnswer";
import { AnswerMode, AskResponse, AskSource, askQuestion, getCatalog, SourceCatalogItem } from "@/lib/api";
import { useToast } from "./ToastProvider";

interface Message {
  id: string;
  role: "user" | "assistant";
  text: string;
  sources?: AskSource[];
  confidence?: number;
  confidenceLabel?: "high" | "medium" | "low";
  evidenceStatus?: "grounded" | "limited" | "insufficient";
  followUpQuestion?: string;
  answerMode?: AnswerMode;
  usedScope?: string[];
  trustMode?: boolean;
}

const DEMO_QUESTIONS = [
  "Explain TCP congestion control in 5 points from my notes",
  "Compare Cross Entropy vs MSE from my materials",
  "Make a 7-day revision plan using weak topics"
];

const ANSWER_MODES: Array<{ value: AnswerMode; label: string; helper: string }> = [
  { value: "answer", label: "Answer", helper: "Direct grounded answer" },
  { value: "study_guide", label: "Study guide", helper: "Core idea plus recall checks" },
  { value: "flashcards", label: "Flashcards", helper: "Short Q/A cards from evidence" },
  { value: "quiz", label: "Quiz", helper: "Questions plus answer key" }
];

const TOP_K_OPTIONS = [4, 6, 8];

function evidencePillClass(label: "high" | "medium" | "low") {
  if (label === "high") return "status-pill";
  if (label === "medium") return "status-pill warn";
  return "status-pill danger";
}

function evidenceLabel(status?: "grounded" | "limited" | "insufficient") {
  if (status === "grounded") return "Grounded evidence";
  if (status === "limited") return "Partial evidence";
  if (status === "insufficient") return "Insufficient evidence";
  return "Pending";
}

function answerModeLabel(mode?: AnswerMode) {
  return ANSWER_MODES.find((item) => item.value === mode)?.label ?? "Answer";
}

export default function ChatUI() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [expandedSources, setExpandedSources] = useState<string | null>(null);
  const [activeCitation, setActiveCitation] = useState<{ messageId: string; citation: string } | null>(null);
  const [catalog, setCatalog] = useState<SourceCatalogItem[]>([]);
  const [catalogFilter, setCatalogFilter] = useState("");
  const [selectedSourceFiles, setSelectedSourceFiles] = useState<string[]>([]);
  const [answerMode, setAnswerMode] = useState<AnswerMode>("answer");
  const [topK, setTopK] = useState(6);
  const [trustMode, setTrustMode] = useState(true);
  const { pushToast } = useToast();
  const streamEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    streamEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [loading, messages]);

  useEffect(() => {
    async function loadCatalog() {
      try {
        const response = await getCatalog();
        setCatalog(response.sources);
      } catch (error) {
        const message = error instanceof Error ? error.message : "Failed to load source catalog";
        pushToast("error", message);
      }
    }

    void loadCatalog();
  }, [pushToast]);

  function toggleSourceFile(sourceFile: string) {
    setSelectedSourceFiles((current) =>
      current.includes(sourceFile) ? current.filter((item) => item !== sourceFile) : [...current, sourceFile]
    );
  }

  async function submit(q: string) {
    const trimmed = q.trim();
    if (!trimmed || loading) return;

    const userMsg: Message = { id: `u_${Date.now()}`, role: "user", text: trimmed };
    setMessages((prev) => [...prev, userMsg]);
    setQuestion("");
    setLoading(true);
    try {
      const response: AskResponse = await askQuestion(trimmed, {
        topK,
        sourceFiles: selectedSourceFiles,
        mode: answerMode,
        trustMode
      });
      const botId = `a_${Date.now()}`;
      const botMsg: Message = {
        id: botId,
        role: "assistant",
        text: response.answer,
        sources: response.sources,
        confidence: response.confidence,
        confidenceLabel: response.confidence_label,
        evidenceStatus: response.evidence_status,
        followUpQuestion: response.follow_up_question,
        answerMode: response.answer_mode,
        usedScope: response.used_scope,
        trustMode: response.trust_mode
      };
      setMessages((prev) => [...prev, botMsg]);
      if (response.sources.length) {
        setExpandedSources(botId);
        setActiveCitation({ messageId: botId, citation: response.sources[0].citation });
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to ask question";
      pushToast("error", message);
    } finally {
      setLoading(false);
    }
  }

  const totalSources = messages.reduce((acc, message) => acc + (message.sources?.length ?? 0), 0);
  const trustedResponses = messages.filter((message) => message.role === "assistant" && message.evidenceStatus === "grounded").length;

  const visibleCatalog = useMemo(() => {
    const normalized = catalogFilter.trim().toLowerCase();
    if (!normalized) return catalog;
    return catalog.filter((item) => item.source_file.toLowerCase().includes(normalized));
  }, [catalog, catalogFilter]);

  return (
    <div className="space-y-6">
      <section className="grid gap-6 xl:grid-cols-[minmax(0,1.12fr)_340px]">
        <div className="shell-panel p-6 xl:p-8">
          <div className="eyebrow">Trust Mode Chat</div>
          <h2 className="mt-3 max-w-3xl font-display text-3xl font-semibold text-white sm:text-[2.6rem]">
            Ask grounded questions, restrict scope, and switch the answer style on demand.
          </h2>
          <p className="mt-3 max-w-3xl text-sm leading-7 text-zinc-400 sm:text-base">
            The assistant now shows evidence quality, can refuse weak answers in trust mode, and can answer only from selected files.
          </p>

          <div className="mt-6 grid gap-3 sm:grid-cols-4">
            <div className="metric-tile">
              <div className="text-[11px] uppercase tracking-[0.22em] text-zinc-500">Messages</div>
              <div className="mt-2 text-3xl font-display font-semibold text-white">{messages.length}</div>
            </div>
            <div className="metric-tile">
              <div className="text-[11px] uppercase tracking-[0.22em] text-zinc-500">Sources used</div>
              <div className="mt-2 text-3xl font-display font-semibold text-white">{totalSources}</div>
            </div>
            <div className="metric-tile">
              <div className="text-[11px] uppercase tracking-[0.22em] text-zinc-500">Grounded replies</div>
              <div className="mt-2 text-3xl font-display font-semibold text-white">{trustedResponses}</div>
            </div>
            <div className="metric-tile">
              <div className="text-[11px] uppercase tracking-[0.22em] text-zinc-500">Scoped files</div>
              <div className="mt-2 text-3xl font-display font-semibold text-white">{selectedSourceFiles.length}</div>
            </div>
          </div>
        </div>

        <div className="shell-panel p-5">
          <div className="eyebrow">Controls</div>
          <div className="mt-2 text-xl font-semibold text-white">Answer setup</div>

          <div className="mt-5 space-y-4">
            <div>
              <div className="text-[11px] uppercase tracking-[0.22em] text-zinc-500">Answer mode</div>
              <div className="mt-3 grid gap-2">
                {ANSWER_MODES.map((item) => (
                  <button
                    key={item.value}
                    type="button"
                    onClick={() => setAnswerMode(item.value)}
                    className={`rounded-[16px] border px-4 py-3 text-left transition ${
                      answerMode === item.value
                        ? "border-sky-300/26 bg-sky-300/10 text-white"
                        : "border-white/8 bg-white/[0.02] text-zinc-300 hover:bg-white/[0.04]"
                    }`}
                  >
                    <div className="text-sm font-medium">{item.label}</div>
                    <div className="mt-1 text-xs text-zinc-400">{item.helper}</div>
                  </button>
                ))}
              </div>
            </div>

            <div>
              <div className="text-[11px] uppercase tracking-[0.22em] text-zinc-500">Answer context</div>
              <div className="mt-3 flex flex-wrap gap-2">
                {TOP_K_OPTIONS.map((value) => (
                  <button
                    key={value}
                    type="button"
                    onClick={() => setTopK(value)}
                    className={`rounded-full border px-4 py-2 text-sm transition ${
                      topK === value
                        ? "border-white/14 bg-white/[0.08] text-white"
                        : "border-white/8 bg-transparent text-zinc-300 hover:bg-white/[0.04]"
                    }`}
                  >
                    {value} sources
                  </button>
                ))}
              </div>
            </div>

            <div className="rounded-[16px] border border-white/8 bg-white/[0.02] p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="text-sm font-medium text-white">Trust mode</div>
                  <div className="mt-1 text-xs leading-6 text-zinc-400">
                    Refuse low-evidence answers and suggest a narrower next step.
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setTrustMode((current) => !current)}
                  className={`inline-flex h-8 w-14 items-center rounded-full border px-1 transition ${
                    trustMode ? "border-sky-300/30 bg-sky-300/12" : "border-white/10 bg-white/[0.03]"
                  }`}
                >
                  <span
                    className={`h-5 w-5 rounded-full bg-white transition ${trustMode ? "translate-x-6" : "translate-x-0"}`}
                  />
                </button>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
        <div className="shell-panel p-5 sm:p-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="eyebrow">Source scope</div>
              <div className="mt-2 text-2xl font-semibold text-white">Ask from selected files only</div>
            </div>
            {selectedSourceFiles.length ? (
              <button type="button" onClick={() => setSelectedSourceFiles([])} className="btn-secondary">
                Clear scope
              </button>
            ) : null}
          </div>

          <div className="mt-4 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <input
              value={catalogFilter}
              onChange={(event) => setCatalogFilter(event.target.value)}
              placeholder="Filter indexed files"
              className="input-shell lg:max-w-[280px]"
            />
            <div className="text-xs uppercase tracking-[0.18em] text-zinc-500">
              {selectedSourceFiles.length ? `${selectedSourceFiles.length} file${selectedSourceFiles.length === 1 ? "" : "s"} selected` : "Using all indexed files"}
            </div>
          </div>

          <div className="mt-4 max-h-[260px] overflow-auto pr-1">
            <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
              {visibleCatalog.map((item) => {
                const selected = selectedSourceFiles.includes(item.source_file);
                return (
                  <button
                    key={item.source_file}
                    type="button"
                    onClick={() => toggleSourceFile(item.source_file)}
                    className={`rounded-[16px] border px-4 py-3 text-left transition ${
                      selected
                        ? "border-sky-300/30 bg-sky-300/10"
                        : "border-white/8 bg-white/[0.02] hover:bg-white/[0.04]"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="text-sm font-medium text-white">{item.source_file}</div>
                      <div className="tag">{item.kind}</div>
                    </div>
                    <div className="mt-2 text-xs text-zinc-400">
                      {item.chunks} chunks{item.pages ? ` • ${item.pages} pages` : ""}
                    </div>
                  </button>
                );
              })}
            </div>
            {!visibleCatalog.length ? <div className="mt-2 text-sm text-zinc-500">No indexed files match this filter.</div> : null}
          </div>
        </div>

        <div className="shell-panel p-5">
          <div className="eyebrow">Examples</div>
          <div className="mt-2 text-xl font-semibold text-white">Starter questions</div>
          <div className="mt-4 space-y-3">
            {DEMO_QUESTIONS.map((prompt) => (
              <button
                key={prompt}
                onClick={() => void submit(prompt)}
                className="w-full rounded-[16px] border border-white/8 bg-white/[0.02] px-4 py-4 text-left text-sm leading-6 text-zinc-200 transition hover:bg-white/[0.04]"
              >
                {prompt}
              </button>
            ))}
          </div>

          {messages.length ? (
            <button onClick={() => setMessages([])} className="btn-secondary mt-5 w-full">
              Clear conversation
            </button>
          ) : null}
        </div>
      </section>

      <section className="shell-panel p-4 sm:p-5">
        <div className="mb-4 flex items-center justify-between gap-3">
          <div>
            <div className="eyebrow">Conversation</div>
            <div className="mt-2 text-2xl font-semibold text-white">Messages</div>
          </div>
          <div className={loading ? "status-pill warn" : "status-pill"}>{loading ? "Working" : "Ready"}</div>
        </div>

        <div className="space-y-3">
          {!messages.length ? (
            <div className="rounded-[18px] border border-white/8 bg-white/[0.02] px-4 py-6 text-sm leading-7 text-zinc-400">
              No messages yet. Choose a mode, optionally scope the files, and ask a question.
            </div>
          ) : null}

          {messages.map((message) => {
            const selectedCitation = activeCitation?.messageId === message.id ? activeCitation.citation : null;
            return (
              <div
                key={message.id}
                className={`rounded-[18px] border p-4 sm:p-5 ${
                  message.role === "user"
                    ? "border-sky-300/15 bg-sky-300/5"
                    : "border-white/8 bg-white/[0.02]"
                }`}
              >
                <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
                  <div className="text-xs uppercase tracking-[0.18em] text-zinc-400">
                    {message.role === "user" ? "You" : "Assistant"}
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    {message.answerMode ? <div className="tag">{answerModeLabel(message.answerMode)}</div> : null}
                    {message.sources?.length ? <div className="tag">{message.sources.length} sources</div> : null}
                    {message.confidenceLabel ? (
                      <div className={evidencePillClass(message.confidenceLabel)}>{evidenceLabel(message.evidenceStatus)}</div>
                    ) : null}
                  </div>
                </div>

                {message.role === "assistant" ? (
                  <AnnotatedAnswer
                    text={message.text}
                    activeCitation={selectedCitation}
                    onCitationClick={(citation) => {
                      setActiveCitation({ messageId: message.id, citation });
                      setExpandedSources(message.id);
                    }}
                  />
                ) : (
                  <pre className="whitespace-pre-wrap text-sm leading-7 text-zinc-100">{message.text}</pre>
                )}

                {message.role === "assistant" ? (
                  <div className="mt-4 grid gap-3 lg:grid-cols-[minmax(0,1fr)_260px]">
                    <div className="rounded-[16px] border border-white/8 bg-white/[0.02] p-4 text-sm text-zinc-300">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-medium text-white">Evidence status</span>
                        {message.confidence !== undefined ? (
                          <span className="tag">{Math.round(message.confidence * 100)}% confidence</span>
                        ) : null}
                        {message.trustMode ? <span className="tag">Trust mode on</span> : null}
                      </div>
                      <div className="mt-2 leading-7 text-zinc-400">
                        {message.evidenceStatus === "grounded"
                          ? "The retrieved evidence covered the question well."
                          : message.evidenceStatus === "limited"
                            ? "The answer is usable, but the evidence is partial. Verify the cited chunks."
                            : "The system refused to guess because the retrieved evidence was too weak."}
                      </div>
                    </div>

                    <div className="rounded-[16px] border border-white/8 bg-white/[0.02] p-4 text-sm text-zinc-300">
                      <div className="font-medium text-white">Scope used</div>
                      <div className="mt-2 leading-7 text-zinc-400">
                        {message.usedScope?.length
                          ? `${message.usedScope.length} selected file${message.usedScope.length === 1 ? "" : "s"}`
                          : "All indexed files"}
                      </div>
                    </div>
                  </div>
                ) : null}

                {message.followUpQuestion ? (
                  <div className="mt-4 rounded-[16px] border border-amber-300/12 bg-amber-300/[0.06] p-4 text-sm leading-7 text-amber-100">
                    <div className="font-medium">Next step</div>
                    <div className="mt-1 text-amber-100/85">{message.followUpQuestion}</div>
                  </div>
                ) : null}

                {message.sources && message.sources.length > 0 ? (
                  <div className="mt-4">
                    <button
                      onClick={() => setExpandedSources((current) => (current === message.id ? null : message.id))}
                      className="btn-secondary"
                    >
                      {expandedSources === message.id ? "Hide evidence" : `View evidence (${message.sources.length})`}
                    </button>
                    {expandedSources === message.id ? (
                      <div className="mt-3 space-y-2">
                        {message.sources.map((source) => {
                          const selected = selectedCitation === source.citation;
                          return (
                            <button
                              key={source.chunk_id}
                              type="button"
                              onClick={() => setActiveCitation({ messageId: message.id, citation: source.citation })}
                              className={`block w-full rounded-[16px] border p-4 text-left transition ${
                                selected
                                  ? "border-sky-300/28 bg-sky-300/10"
                                  : "border-white/8 bg-white/[0.02] hover:bg-white/[0.04]"
                              }`}
                            >
                              <div className="flex flex-wrap items-start justify-between gap-3">
                                <div>
                                  <div className="flex flex-wrap items-center gap-2">
                                    <span className="tag">{source.citation}</span>
                                    <span className="text-xs text-zinc-400">
                                      {source.source_file}
                                      {source.page_number ? ` (p.${source.page_number})` : ""}
                                    </span>
                                  </div>
                                  <div className="mt-2 text-xs uppercase tracking-[0.18em] text-zinc-500">
                                    score {source.score.toFixed(2)} • retrieval {source.retrieval_score.toFixed(2)}
                                  </div>
                                </div>
                                <div className="w-24 rounded-full bg-white/[0.05] p-1">
                                  <div
                                    className="h-1.5 rounded-full bg-sky-300"
                                    style={{ width: `${Math.max(10, Math.round(source.score * 100))}%` }}
                                  />
                                </div>
                              </div>
                              <div className="mt-3 text-sm leading-7 text-zinc-300">
                                {source.text.slice(0, 420)}
                                {source.text.length > 420 ? "..." : ""}
                              </div>
                            </button>
                          );
                        })}
                      </div>
                    ) : null}
                  </div>
                ) : null}
              </div>
            );
          })}

          {loading ? (
            <div className="rounded-[18px] border border-white/8 bg-white/[0.02] p-5">
              <div className="text-xs uppercase tracking-[0.18em] text-zinc-500">Assistant</div>
              <div className="mt-3 flex items-center gap-2">
                <div className="h-2 w-2 animate-pulse rounded-full bg-sky-300" />
                <div className="h-2 w-2 animate-pulse rounded-full bg-sky-300 [animation-delay:120ms]" />
                <div className="h-2 w-2 animate-pulse rounded-full bg-sky-300 [animation-delay:240ms]" />
              </div>
            </div>
          ) : null}
          <div ref={streamEndRef} />
        </div>
      </section>

      <section className="sticky bottom-4 z-10">
        <div className="shell-panel p-4">
          <div className="flex flex-col gap-3 lg:flex-row">
            <textarea
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  void submit(question);
                }
              }}
              placeholder={
                selectedSourceFiles.length
                  ? `Ask using ${selectedSourceFiles.length} selected file${selectedSourceFiles.length === 1 ? "" : "s"}`
                  : "Ask a question about your indexed data"
              }
              rows={3}
              className="input-shell min-h-[96px] flex-1 resize-none leading-7"
            />
            <div className="flex w-full shrink-0 flex-col gap-3 lg:w-[240px]">
              <button onClick={() => void submit(question)} disabled={loading} className="btn-primary h-[56px] disabled:opacity-60">
                {loading ? "Working..." : "Send"}
              </button>
              <div className="rounded-[14px] border border-white/8 bg-white/[0.02] px-4 py-3 text-xs leading-6 text-zinc-400">
                {answerModeLabel(answerMode)} mode • {topK} source context • {trustMode ? "trust mode on" : "trust mode off"}
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
