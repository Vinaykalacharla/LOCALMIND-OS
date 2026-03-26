"use client";

import { useEffect, useState } from "react";
import { EvaluationResponse, getEvaluation } from "@/lib/api";
import { useToast } from "@/components/ToastProvider";

function percent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

function listLabel(items: string[]): string {
  if (!items.length) return "None detected";
  return items.join(", ");
}

export default function EvaluatePage() {
  const [evaluation, setEvaluation] = useState<EvaluationResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const { pushToast } = useToast();

  useEffect(() => {
    async function loadEvaluation() {
      setLoading(true);
      try {
        const response = await getEvaluation();
        setEvaluation(response);
      } catch (error) {
        const message = error instanceof Error ? error.message : "Failed to load evaluation";
        pushToast("error", message);
      } finally {
        setLoading(false);
      }
    }

    void loadEvaluation();
  }, [pushToast]);

  if (loading) {
    return <div className="h-[32rem] animate-pulse rounded-[28px] bg-white/5" />;
  }

  return (
    <div className="space-y-6">
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <div className="metric-tile">
          <div className="text-[11px] uppercase tracking-[0.22em] text-zinc-500">Top 1</div>
          <div className="mt-2 text-3xl font-display font-semibold text-white">
            {percent(evaluation?.retrieval_top1 ?? 0)}
          </div>
        </div>
        <div className="metric-tile">
          <div className="text-[11px] uppercase tracking-[0.22em] text-zinc-500">Top 3</div>
          <div className="mt-2 text-3xl font-display font-semibold text-white">
            {percent(evaluation?.retrieval_top3 ?? 0)}
          </div>
        </div>
        <div className="metric-tile">
          <div className="text-[11px] uppercase tracking-[0.22em] text-zinc-500">Top 5</div>
          <div className="mt-2 text-3xl font-display font-semibold text-white">
            {percent(evaluation?.retrieval_top5 ?? 0)}
          </div>
        </div>
        <div className="metric-tile">
          <div className="text-[11px] uppercase tracking-[0.22em] text-zinc-500">MRR</div>
          <div className="mt-2 text-3xl font-display font-semibold text-white">
            {percent(evaluation?.mean_reciprocal_rank ?? 0)}
          </div>
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-[minmax(0,1.05fr)_minmax(320px,0.95fr)]">
        <div className="shell-panel p-5 sm:p-6">
          <div className="eyebrow">Benchmark</div>
          <div className="mt-2 text-2xl font-semibold text-white">Self-check over indexed chunks</div>

          <div className="mt-5 grid gap-3 sm:grid-cols-2">
            <div className="metric-tile">
              <div className="text-[11px] uppercase tracking-[0.22em] text-zinc-500">Cases</div>
              <div className="mt-2 text-3xl font-display font-semibold text-white">{evaluation?.total_cases ?? 0}</div>
            </div>
            <div className="metric-tile">
              <div className="text-[11px] uppercase tracking-[0.22em] text-zinc-500">Avg query terms</div>
              <div className="mt-2 text-3xl font-display font-semibold text-white">
                {evaluation?.avg_query_terms ?? 0}
              </div>
            </div>
          </div>

          <div className="mt-5 space-y-3">
            {(evaluation?.cases ?? []).slice(0, 8).map((item, index) => (
              <div key={`${item.expected_chunk_id}_${index}`} className="rounded-[16px] border border-white/8 bg-white/[0.02] px-4 py-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="tag">{item.rank ? `Rank ${item.rank}` : "Missed"}</div>
                  <div className={item.hit_in_top_3 ? "status-pill" : "status-pill warn"}>
                    {item.hit_in_top_3 ? "Top 3 hit" : "Needs work"}
                  </div>
                </div>
                <div className="mt-3 text-sm font-medium text-white">{item.query}</div>
                <div className="mt-2 text-sm leading-6 text-zinc-400">
                  Expected: {item.source_file}
                </div>
                <div className="text-sm leading-6 text-zinc-400">
                  Top hit: {item.top_hit_source_file || "None"}
                </div>
              </div>
            ))}
            {!evaluation?.cases.length ? (
              <div className="rounded-[16px] border border-white/8 bg-white/[0.02] px-4 py-4 text-sm text-zinc-500">
                Add more indexed chunks to generate evaluation cases.
              </div>
            ) : null}
          </div>
        </div>

        <div className="space-y-6">
          <div className="shell-panel p-5 sm:p-6">
            <div className="eyebrow">Active Stack</div>
            <div className="mt-2 text-2xl font-semibold text-white">Loaded right now</div>
            <div className="mt-5 space-y-3">
              <div className="rounded-[16px] border border-white/8 bg-white/[0.02] px-4 py-4">
                <div className="text-xs uppercase tracking-[0.18em] text-zinc-500">LLM</div>
                <div className="mt-2 text-sm font-medium text-white">{evaluation?.stack.llm_model || "None"}</div>
                <div className="mt-1 text-sm text-zinc-400">{evaluation?.stack.llm_mode || "unknown"}</div>
              </div>
              <div className="rounded-[16px] border border-white/8 bg-white/[0.02] px-4 py-4">
                <div className="text-xs uppercase tracking-[0.18em] text-zinc-500">Embeddings</div>
                <div className="mt-2 text-sm font-medium text-white">{evaluation?.stack.embedding_model || "None"}</div>
                <div className="mt-1 text-sm text-zinc-400">{evaluation?.stack.embedding_mode || "unknown"}</div>
              </div>
              <div className="rounded-[16px] border border-white/8 bg-white/[0.02] px-4 py-4">
                <div className="text-xs uppercase tracking-[0.18em] text-zinc-500">Reranker</div>
                <div className="mt-2 text-sm font-medium text-white">{evaluation?.stack.reranker_model || "None"}</div>
                <div className="mt-1 text-sm text-zinc-400">{evaluation?.stack.reranker_mode || "unknown"}</div>
              </div>
            </div>
          </div>

          <div className="shell-panel p-5 sm:p-6">
            <div className="eyebrow">Local Models</div>
            <div className="mt-2 text-2xl font-semibold text-white">Detected folders and files</div>
            <div className="mt-5 space-y-3 text-sm leading-7 text-zinc-400">
              <div className="rounded-[16px] border border-white/8 bg-white/[0.02] px-4 py-4">
                <div className="text-xs uppercase tracking-[0.18em] text-zinc-500">GGUF files</div>
                <div className="mt-2">{listLabel(evaluation?.available_models.llm_files ?? [])}</div>
              </div>
              <div className="rounded-[16px] border border-white/8 bg-white/[0.02] px-4 py-4">
                <div className="text-xs uppercase tracking-[0.18em] text-zinc-500">Embedding folders</div>
                <div className="mt-2">{listLabel(evaluation?.available_models.embedding_folders ?? [])}</div>
              </div>
              <div className="rounded-[16px] border border-white/8 bg-white/[0.02] px-4 py-4">
                <div className="text-xs uppercase tracking-[0.18em] text-zinc-500">Reranker folders</div>
                <div className="mt-2">{listLabel(evaluation?.available_models.reranker_folders ?? [])}</div>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
