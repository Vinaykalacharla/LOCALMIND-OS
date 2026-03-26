"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  applyModelManagerSettings,
  getModelManager,
  getStatus,
  JobStatus,
  ModelGroupState,
  ModelManagerResponse,
  reindexKnowledgeBase,
  validateModelManagerSettings
} from "@/lib/api";
import { useToast } from "@/components/ToastProvider";
import { formatNumber } from "@/lib/format";

const initialJobStatus: JobStatus = { state: "processing", step: "queued", progress: 0, message: "Queued" };

type ModelKey = "llm" | "embedding" | "reranker";

type SelectionState = {
  llm: string;
  embedding: string;
  reranker: string;
};

function validationPill(ok: boolean): string {
  return ok ? "status-pill" : "status-pill warn";
}

function selectClasses(): string {
  return "mt-3 w-full rounded-[14px] border border-white/8 bg-zinc-950/80 px-4 py-3 text-sm text-zinc-100 outline-none transition focus:border-sky-400";
}

function optionDescription(group: ModelGroupState, selection: string): string {
  const matched = group.options.find((item) => item.id === selection);
  return matched?.detail || "Choose a local model or fallback mode.";
}

export default function ModelsPage() {
  const [manager, setManager] = useState<ModelManagerResponse | null>(null);
  const [selections, setSelections] = useState<SelectionState>({ llm: "auto", embedding: "auto", reranker: "auto" });
  const [loading, setLoading] = useState(true);
  const [applying, setApplying] = useState(false);
  const [validating, setValidating] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<JobStatus | null>(null);
  const { pushToast } = useToast();

  async function loadManager(showErrorToast = true) {
    setLoading(true);
    try {
      const response = await getModelManager();
      setManager(response);
      setSelections({
        llm: response.llm.selected,
        embedding: response.embedding.selected,
        reranker: response.reranker.selected
      });
    } catch (error) {
      if (showErrorToast) {
        const message = error instanceof Error ? error.message : "Failed to load model manager";
        pushToast("error", message);
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    async function initialLoad() {
      setLoading(true);
      try {
        const response = await getModelManager();
        setManager(response);
        setSelections({
          llm: response.llm.selected,
          embedding: response.embedding.selected,
          reranker: response.reranker.selected
        });
      } catch (error) {
        const message = error instanceof Error ? error.message : "Failed to load model manager";
        pushToast("error", message);
      } finally {
        setLoading(false);
      }
    }

    void initialLoad();
  }, [pushToast]);

  useEffect(() => {
    if (!jobId) return;
    const timer = setInterval(async () => {
      try {
        const response = await getStatus(jobId);
        setJobStatus(response);
        if (response.state === "done" || response.state === "error") {
          clearInterval(timer);
          pushToast(response.state === "done" ? "success" : "error", response.message || response.state);
          if (response.state === "done") {
            void loadManager(false);
          }
        }
      } catch (error) {
        clearInterval(timer);
        const message = error instanceof Error ? error.message : "Failed to fetch reindex status";
        pushToast("error", message);
      }
    }, 900);
    return () => clearInterval(timer);
  }, [jobId, pushToast]);

  function updateSelection(key: ModelKey, value: string) {
    setSelections((current) => ({ ...current, [key]: value }));
  }

  async function onApply() {
    if (applying) return;
    setApplying(true);
    try {
      const response = await applyModelManagerSettings(selections);
      setManager(response);
      setSelections({
        llm: response.llm.selected,
        embedding: response.embedding.selected,
        reranker: response.reranker.selected
      });
      pushToast("success", "Local model settings applied");
      if (response.reindex_recommended) {
        pushToast("info", "Embedding runtime changed. Reindex the knowledge base to align the vector store.");
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to apply model settings";
      pushToast("error", message);
    } finally {
      setApplying(false);
    }
  }

  async function onValidate() {
    if (validating) return;
    setValidating(true);
    try {
      const response = await validateModelManagerSettings(selections);
      setManager(response);
      const allValid = Object.values(response.validation).every((item) => item.ok);
      pushToast(allValid ? "success" : "info", allValid ? "Selected stack validated" : "Validation finished with warnings");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to validate selected models";
      pushToast("error", message);
    } finally {
      setValidating(false);
    }
  }

  async function onReindex() {
    if (jobId && jobStatus?.state === "processing") return;
    setJobStatus(initialJobStatus);
    try {
      const response = await reindexKnowledgeBase();
      setJobId(response.job_id);
      pushToast("info", "Reindex started");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to start reindex";
      pushToast("error", message);
    }
  }

  if (loading && !manager) {
    return <div className="h-[32rem] animate-pulse rounded-[28px] bg-white/5" />;
  }

  const groups: Array<{ key: ModelKey; label: string; state: ModelGroupState }> = manager
    ? [
        { key: "llm", label: "LLM", state: manager.llm },
        { key: "embedding", label: "Embeddings", state: manager.embedding },
        { key: "reranker", label: "Reranker", state: manager.reranker }
      ]
    : [];

  return (
    <div className="space-y-6">
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <div className="metric-tile">
          <div className="text-[11px] uppercase tracking-[0.22em] text-zinc-500">Indexed chunks</div>
          <div className="mt-2 text-3xl font-display font-semibold text-white">{formatNumber(manager?.indexed_chunks ?? 0)}</div>
        </div>
        <div className="metric-tile">
          <div className="text-[11px] uppercase tracking-[0.22em] text-zinc-500">Runtime embedding</div>
          <div className="mt-2 text-sm font-medium text-white">{manager?.embedding.active_model || "None"}</div>
          <div className="mt-1 text-xs text-zinc-500">{manager?.embedding.active_mode || "unknown"}</div>
        </div>
        <div className="metric-tile">
          <div className="text-[11px] uppercase tracking-[0.22em] text-zinc-500">Index built with</div>
          <div className="mt-2 text-sm font-medium text-white">{manager?.index_embedding_model || "Unknown"}</div>
          <div className="mt-1 text-xs text-zinc-500">
            {manager?.reindex_recommended ? "Reindex required" : "Index and runtime are aligned"}
          </div>
        </div>
        <div className="metric-tile">
          <div className="text-[11px] uppercase tracking-[0.22em] text-zinc-500">Validation</div>
          <div className="mt-2 text-sm font-medium text-white">
            {manager && Object.values(manager.validation).every((item) => item.ok) ? "Ready" : "Needs review"}
          </div>
          <div className="mt-1 text-xs text-zinc-500">Validate before long runs or demos.</div>
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-[minmax(0,1.1fr)_minmax(320px,0.9fr)]">
        <div className="shell-panel p-5 sm:p-6">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="eyebrow">Model Manager</div>
              <div className="mt-2 text-2xl font-semibold text-white">Switch local runtime components</div>
              <div className="mt-2 max-w-2xl text-sm leading-7 text-zinc-400">
                Pick a local LLM, embedding backend, and reranker. Switching embeddings changes the vector space, so reindex after applying if the runtime no longer matches the stored index.
              </div>
            </div>
            <div className="flex flex-wrap gap-3">
              <button onClick={onApply} disabled={applying || loading} className="btn-primary disabled:opacity-60">
                {applying ? "Applying..." : "Apply selection"}
              </button>
              <button onClick={onValidate} disabled={validating || loading} className="btn-secondary disabled:opacity-60">
                {validating ? "Validating..." : "Validate stack"}
              </button>
            </div>
          </div>

          <div className="mt-6 space-y-5">
            {groups.map((group) => {
              const validation = manager?.validation[group.key];
              return (
                <div key={group.key} className="rounded-[18px] border border-white/8 bg-white/[0.02] px-4 py-4">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div className="text-sm font-medium text-white">{group.label}</div>
                    <span className={validationPill(Boolean(validation?.ok))}>
                      {validation?.ok ? "validated" : "check required"}
                    </span>
                  </div>

                  <select
                    value={selections[group.key]}
                    onChange={(event) => updateSelection(group.key, event.target.value)}
                    className={selectClasses()}
                  >
                    {group.state.options.map((option) => (
                      <option key={option.id} value={option.id}>
                        {option.label}
                      </option>
                    ))}
                  </select>

                  <div className="mt-3 grid gap-3 sm:grid-cols-2">
                    <div className="rounded-[14px] border border-white/8 bg-black/20 px-4 py-3">
                      <div className="text-[11px] uppercase tracking-[0.18em] text-zinc-500">Selected</div>
                      <div className="mt-2 text-sm text-white">{selections[group.key]}</div>
                      <div className="mt-1 text-xs leading-6 text-zinc-500">
                        {optionDescription(group.state, selections[group.key])}
                      </div>
                    </div>
                    <div className="rounded-[14px] border border-white/8 bg-black/20 px-4 py-3">
                      <div className="text-[11px] uppercase tracking-[0.18em] text-zinc-500">Active runtime</div>
                      <div className="mt-2 text-sm text-white">{group.state.active_model || "None"}</div>
                      <div className="mt-1 text-xs leading-6 text-zinc-500">{group.state.active_mode || "unknown"}</div>
                    </div>
                  </div>

                  <div className="mt-3 text-sm leading-7 text-zinc-400">{validation?.detail || "Validation status is not available."}</div>
                  {group.key === "embedding" && group.state.requires_reindex ? (
                    <div className="mt-3 rounded-[14px] border border-amber-300/20 bg-amber-300/10 px-4 py-3 text-sm leading-7 text-amber-100">
                      Runtime embeddings no longer match the stored vector index. Reindex before relying on search quality.
                    </div>
                  ) : null}
                </div>
              );
            })}
          </div>
        </div>

        <div className="space-y-6">
          <div className="shell-panel p-5 sm:p-6">
            <div className="eyebrow">Paths</div>
            <div className="mt-2 text-2xl font-semibold text-white">Local model roots</div>
            <div className="mt-5 space-y-3 text-sm leading-7 text-zinc-400">
              <div className="rounded-[16px] border border-white/8 bg-white/[0.02] px-4 py-4">
                <div className="text-xs uppercase tracking-[0.18em] text-zinc-500">LLM models</div>
                <div className="mt-2 break-all">{manager?.model_roots.llm}</div>
              </div>
              <div className="rounded-[16px] border border-white/8 bg-white/[0.02] px-4 py-4">
                <div className="text-xs uppercase tracking-[0.18em] text-zinc-500">Embedding models</div>
                <div className="mt-2 break-all">{manager?.model_roots.embedding}</div>
              </div>
              <div className="rounded-[16px] border border-white/8 bg-white/[0.02] px-4 py-4">
                <div className="text-xs uppercase tracking-[0.18em] text-zinc-500">Reranker models</div>
                <div className="mt-2 break-all">{manager?.model_roots.reranker}</div>
              </div>
            </div>
          </div>

          <div className="shell-panel p-5 sm:p-6">
            <div className="eyebrow">Reindex</div>
            <div className="mt-2 text-2xl font-semibold text-white">Align the vector index</div>
            <div className="mt-3 text-sm leading-7 text-zinc-400">
              Use this after changing the embedding backend. The rebuild keeps all existing chunks and refreshes vectors and index metadata.
            </div>

            <div className="mt-5 flex flex-wrap gap-3">
              <button onClick={onReindex} disabled={jobStatus?.state === "processing"} className="btn-primary disabled:opacity-60">
                {jobStatus?.state === "processing" ? "Reindexing..." : "Reindex knowledge base"}
              </button>
              <Link href="/evaluate" className="btn-secondary">
                Open evaluation
              </Link>
            </div>

            {jobStatus ? (
              <div className="mt-5 space-y-4">
                <div className="flex items-center justify-between gap-3">
                  <span className="tag">{jobStatus.step}</span>
                  <span className="text-sm font-medium text-white">{jobStatus.progress}%</span>
                </div>
                <div className="h-2.5 w-full overflow-hidden rounded-full bg-white/8">
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-sky-400 to-sky-300 transition-all"
                    style={{ width: `${Math.max(4, jobStatus.progress)}%` }}
                  />
                </div>
                <div className="rounded-[16px] border border-white/8 bg-white/[0.02] px-4 py-4 text-sm leading-7 text-zinc-300">
                  {jobStatus.message}
                </div>
              </div>
            ) : null}
          </div>
        </div>
      </section>
    </div>
  );
}
