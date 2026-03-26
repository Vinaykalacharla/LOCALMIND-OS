"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import StatCard from "@/components/StatCard";
import { getInsights, getStats, InsightsResponse, StatsResponse } from "@/lib/api";
import { useToast } from "@/components/ToastProvider";
import { formatDateTime, formatNumber } from "@/lib/format";

export default function DashboardPage() {
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [insights, setInsights] = useState<InsightsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const { pushToast } = useToast();

  useEffect(() => {
    async function load() {
      setLoading(true);
      try {
        const [nextStats, nextInsights] = await Promise.all([getStats(), getInsights()]);
        setStats(nextStats);
        setInsights(nextInsights);
      } catch (error) {
        const message = error instanceof Error ? error.message : "Failed to load dashboard";
        pushToast("error", message);
      } finally {
        setLoading(false);
      }
    }

    void load();
  }, [pushToast]);

  const recentQueries = insights?.recent_queries ?? [];
  const weakTopics = insights?.not_revised_topics ?? [];
  const topTopics = insights?.most_searched_topics ?? [];

  return (
    <div className="space-y-6">
      <section className="shell-panel p-6 sm:p-8">
        <div className="max-w-3xl">
          <div className="eyebrow">Overview</div>
          <h2 className="mt-3 font-display text-3xl font-semibold text-white sm:text-[2.6rem]">
            A clear view of your local AI workspace.
          </h2>
          <p className="mt-3 text-sm leading-7 text-zinc-400 sm:text-base">
            Check indexing status, recent activity, and what is ready before you upload files, search your data, or use trust-mode chat with scoped retrieval.
          </p>
        </div>

        <div className="mt-6 flex flex-wrap gap-3">
          <Link href="/upload" className="btn-primary">
            Upload files
          </Link>
          <Link href="/search" className="btn-secondary">
            Search data
          </Link>
          <Link href="/chat" className="btn-secondary">
            Open chat
          </Link>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {loading ? (
          <>
            <div className="h-32 animate-pulse rounded-[18px] bg-white/5" />
            <div className="h-32 animate-pulse rounded-[18px] bg-white/5" />
            <div className="h-32 animate-pulse rounded-[18px] bg-white/5" />
            <div className="h-32 animate-pulse rounded-[18px] bg-white/5" />
          </>
        ) : (
          <>
            <StatCard label="Indexed Files" value={formatNumber(stats?.indexed_files ?? 0)} subtext="Files available in the index." />
            <StatCard label="Total Chunks" value={formatNumber(stats?.total_chunks ?? 0)} subtext="Chunks ready for retrieval." />
            <StatCard label="Graph Nodes" value={formatNumber(stats?.graph_nodes ?? 0)} subtext="Nodes in graph view." />
            <StatCard label="Last Indexed" value={stats?.last_index_time ? formatDateTime(stats.last_index_time) : "N/A"} subtext="Most recent indexing time." />
          </>
        )}
      </section>

      <section className="grid gap-6 xl:grid-cols-[minmax(0,1.1fr)_minmax(320px,0.9fr)]">
        <div className="shell-panel p-5 sm:p-6">
          <div className="eyebrow">Offline AI Stack</div>
          <div className="mt-2 text-2xl font-semibold text-white">Local model and retrieval status</div>

          <div className="mt-5 grid gap-3 sm:grid-cols-2">
            <div className="metric-tile">
              <div className="text-[11px] uppercase tracking-[0.22em] text-zinc-500">LLM</div>
              <div className="mt-2 text-sm font-medium text-white">{stats?.llm_model || "Extractive fallback"}</div>
              <div className="mt-1 text-xs text-zinc-500">{stats?.llm_mode || "unknown"}</div>
            </div>
            <div className="metric-tile">
              <div className="text-[11px] uppercase tracking-[0.22em] text-zinc-500">Embeddings</div>
              <div className="mt-2 text-sm font-medium text-white">{stats?.embedding_model || "Not loaded"}</div>
              <div className="mt-1 text-xs text-zinc-500">{stats?.embedding_mode || "unknown"}</div>
            </div>
            <div className="metric-tile">
              <div className="text-[11px] uppercase tracking-[0.22em] text-zinc-500">Reranker</div>
              <div className="mt-2 text-sm font-medium text-white">{stats?.reranker_model || "Lexical only"}</div>
              <div className="mt-1 text-xs text-zinc-500">{stats?.reranker_mode || "disabled"}</div>
            </div>
            <div className="metric-tile">
              <div className="text-[11px] uppercase tracking-[0.22em] text-zinc-500">Chunking</div>
              <div className="mt-2 text-sm font-medium text-white">{stats?.chunking_version || "unknown"}</div>
              <div className="mt-1 text-xs text-zinc-500">
                {stats?.reindex_recommended ? "Reindex recommended" : "Index is current"}
              </div>
            </div>
          </div>

          <div className="mt-5 flex flex-wrap gap-3">
            <Link href="/models" className="btn-primary">
              Manage models
            </Link>
            <Link href="/evaluate" className="btn-secondary">
              Evaluate stack
            </Link>
          </div>
        </div>

        <div className="shell-panel p-5 sm:p-6">
          <div className="eyebrow">Capabilities</div>
          <div className="mt-2 text-2xl font-semibold text-white">What is active right now</div>

          <div className="mt-5 space-y-3">
            {(stats?.feature_status ?? []).map((feature) => (
              <div
                key={feature.id}
                className="rounded-[16px] border border-white/8 bg-white/[0.02] px-4 py-4"
              >
                <div className="flex items-center justify-between gap-3">
                  <div className="text-sm font-medium text-white">{feature.label}</div>
                  <span className={feature.status === "active" ? "status-pill" : feature.status === "fallback" ? "status-pill warn" : "status-pill danger"}>
                    {feature.status}
                  </span>
                </div>
                <div className="mt-2 text-sm leading-6 text-zinc-400">{feature.detail}</div>
              </div>
            ))}
            {!stats?.feature_status?.length ? <div className="text-sm text-zinc-500">Capability data is not available yet.</div> : null}
          </div>
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-2">
        <div className="shell-panel p-5 sm:p-6">
          <div className="eyebrow">New Capabilities</div>
          <div className="mt-2 text-2xl font-semibold text-white">Trust and study workflows</div>

          <div className="mt-5 grid gap-3 sm:grid-cols-3">
            <div className="metric-tile">
              <div className="text-[11px] uppercase tracking-[0.22em] text-zinc-500">Trust mode</div>
              <div className="mt-2 text-sm font-medium text-white">Refuses weak evidence</div>
            </div>
            <div className="metric-tile">
              <div className="text-[11px] uppercase tracking-[0.22em] text-zinc-500">Scoped chat</div>
              <div className="mt-2 text-sm font-medium text-white">Ask from selected files only</div>
            </div>
            <div className="metric-tile">
              <div className="text-[11px] uppercase tracking-[0.22em] text-zinc-500">Study outputs</div>
              <div className="mt-2 text-sm font-medium text-white">Guide, flashcards, quiz</div>
            </div>
          </div>

          <div className="mt-5 flex flex-wrap gap-3">
            <Link href="/chat" className="btn-primary">
              Open trust chat
            </Link>
            <Link href="/search" className="btn-secondary">
              Validate retrieval
            </Link>
          </div>
        </div>

        <div className="shell-panel p-5 sm:p-6">
          <div className="eyebrow">Recent activity</div>
          <div className="mt-2 text-2xl font-semibold text-white">Queries and weak topics</div>

          <div className="mt-5 grid gap-3 sm:grid-cols-2">
            <div className="metric-tile">
              <div className="text-[11px] uppercase tracking-[0.22em] text-zinc-500">Recent queries</div>
              <div className="mt-2 text-3xl font-display font-semibold text-white">{formatNumber(recentQueries.length)}</div>
            </div>
            <div className="metric-tile">
              <div className="text-[11px] uppercase tracking-[0.22em] text-zinc-500">Weak topics</div>
              <div className="mt-2 text-3xl font-display font-semibold text-white">{formatNumber(weakTopics.length)}</div>
            </div>
          </div>

          <div className="mt-5 space-y-2">
            {recentQueries.slice(0, 4).map((query) => (
              <div key={query} className="rounded-[14px] border border-white/6 bg-white/[0.02] px-4 py-3 text-sm leading-6 text-zinc-300">
                {query}
              </div>
            ))}
            {!recentQueries.length ? <div className="text-sm text-zinc-500">No recent queries yet.</div> : null}
          </div>
        </div>

        <div className="shell-panel p-5 sm:p-6">
          <div className="eyebrow">Topics</div>
          <div className="mt-2 text-2xl font-semibold text-white">Most searched topics</div>

          <div className="mt-5 space-y-2">
            {topTopics.slice(0, 6).map((topic) => (
              <div key={topic.topic} className="flex items-center justify-between rounded-[14px] border border-white/6 bg-white/[0.02] px-4 py-3">
                <span className="text-sm text-zinc-200">{topic.topic}</span>
                <span className="text-xs text-zinc-500">{topic.count}</span>
              </div>
            ))}
            {!topTopics.length ? <div className="text-sm text-zinc-500">No topic data yet.</div> : null}
          </div>

          {weakTopics.length ? (
            <div className="mt-5 border-t border-white/6 pt-5">
              <div className="text-sm font-medium text-white">Topics to revisit</div>
              <div className="mt-3 flex flex-wrap gap-2">
                {weakTopics.slice(0, 8).map((topic) => (
                  <span key={topic} className="rounded-full border border-white/8 px-3 py-1 text-xs text-zinc-300">
                    {topic}
                  </span>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      </section>
    </div>
  );
}
