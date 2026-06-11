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
    <div className="space-y-8 pb-10">
      {/* Hero Section */}
      <section className="relative overflow-hidden rounded-3xl border border-[var(--line)] bg-[var(--panel-main)] p-8 sm:p-12 shadow-panel backdrop-blur-xl">
        <div className="absolute top-0 right-0 -mt-16 -mr-16 h-64 w-64 rounded-full bg-[var(--accent)] opacity-20 blur-[80px]"></div>
        <div className="absolute bottom-0 left-0 -mb-16 -ml-16 h-48 w-48 rounded-full bg-[var(--cyan)] opacity-10 blur-[60px]"></div>
        
        <div className="relative z-10 max-w-3xl">
          <div className="eyebrow mb-2 inline-block rounded-full bg-[var(--accent-dim)] px-3 py-1 border border-[var(--line-accent)]">Mission Control</div>
          <h2 className="mt-4 font-display text-4xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-white to-zinc-400 sm:text-5xl tracking-tight">
            Your personal AI <br />knowledge vault.
          </h2>
          <p className="mt-5 text-base leading-relaxed text-[var(--text-muted)] sm:text-lg max-w-2xl">
            Everything stays on your device. Upload documents, visualize connections, and chat with your data using local open-source models.
          </p>
          
          <div className="mt-8 flex flex-wrap gap-4">
            <Link href="/upload" className="btn-primary">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" x2="12" y1="3" y2="15"/></svg>
              Upload Data
            </Link>
            <Link href="/local-chat" className="btn-secondary">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 9a2 2 0 0 1-2 2H6l-4 4V4c0-1.1.9-2 2-2h8a2 2 0 0 1 2 2v5Z"/><path d="M18 9h2a2 2 0 0 1 2 2v11l-4-4h-6a2 2 0 0 1-2-2v-1"/></svg>
              Start Chat
            </Link>
          </div>
        </div>
      </section>

      {/* Stats Row */}
      <section className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
        {loading ? (
          <>
            <div className="h-36 skeleton" />
            <div className="h-36 skeleton" />
            <div className="h-36 skeleton" />
            <div className="h-36 skeleton" />
          </>
        ) : (
          <>
            <StatCard tone="brand" label="Indexed Files" value={formatNumber(stats?.indexed_files ?? 0)} subtext="Documents securely stored." />
            <StatCard label="Knowledge Chunks" value={formatNumber(stats?.total_chunks ?? 0)} subtext="Searchable data segments." />
            <StatCard label="Connections" value={formatNumber(stats?.graph_nodes ?? 0)} subtext="Nodes in your knowledge graph." />
            <StatCard label="Last Synced" value={stats?.last_index_time ? formatDateTime(stats.last_index_time).split(',')[0] : "N/A"} subtext="Time of last indexing run." />
          </>
        )}
      </section>

      <div className="grid gap-8 lg:grid-cols-[1.5fr_1fr]">
        {/* Left Column */}
        <div className="space-y-8">
          {/* Active Stack */}
          <section className="glow-card p-6 sm:p-8">
            <div className="flex items-center justify-between mb-6">
              <div>
                <div className="eyebrow mb-1">Infrastructure</div>
                <h3 className="font-display text-xl font-bold text-[var(--text-main)]">Active AI Stack</h3>
              </div>
              <Link href="/models" className="btn-ghost text-xs">Manage</Link>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="metric-tile group">
                <div className="flex items-center gap-2 mb-2">
                  <svg className="text-[var(--accent)]" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>
                  <div className="text-[10px] font-semibold uppercase tracking-widest text-[var(--text-muted)]">Language Model</div>
                </div>
                <div className="text-sm font-semibold text-[var(--text-main)] truncate">{stats?.llm_model || "Extractive Fallback"}</div>
                <div className="mt-1 text-xs text-[var(--text-muted)]">{stats?.llm_mode || "offline"}</div>
              </div>
              
              <div className="metric-tile group">
                <div className="flex items-center gap-2 mb-2">
                  <svg className="text-[var(--cyan)]" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="m2 12 5.25 5 5.25-11.5L21 12"/></svg>
                  <div className="text-[10px] font-semibold uppercase tracking-widest text-[var(--text-muted)]">Embeddings</div>
                </div>
                <div className="text-sm font-semibold text-[var(--text-main)] truncate">{stats?.embedding_model || "Not Loaded"}</div>
                <div className="mt-1 text-xs text-[var(--text-muted)]">{stats?.embedding_mode || "offline"}</div>
              </div>
            </div>
          </section>

          {/* Capabilities */}
          <section className="glow-card p-6 sm:p-8">
             <div className="eyebrow mb-1">System Health</div>
             <h3 className="font-display text-xl font-bold text-[var(--text-main)] mb-6">Feature Status</h3>
             
             <div className="space-y-3">
              {(stats?.feature_status ?? []).map((feature) => (
                <div key={feature.id} className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 rounded-xl bg-[var(--panel-soft)] border border-[var(--line)] hover:bg-[var(--panel-hover)] transition">
                  <div>
                    <div className="text-sm font-semibold text-[var(--text-main)]">{feature.label}</div>
                    <div className="text-xs text-[var(--text-muted)] mt-0.5">{feature.detail}</div>
                  </div>
                  <span className={feature.status === "active" ? "status-pill" : feature.status === "fallback" ? "status-pill warn" : "status-pill danger"}>
                    {feature.status}
                  </span>
                </div>
              ))}
              {!stats?.feature_status?.length ? <div className="text-sm text-[var(--text-muted)]">Capability data unavailable.</div> : null}
            </div>
          </section>
        </div>

        {/* Right Column */}
        <div className="space-y-8">
          {/* Recent Queries */}
          <section className="glow-card p-6 sm:p-8">
            <div className="eyebrow mb-1">Activity</div>
            <h3 className="font-display text-xl font-bold text-[var(--text-main)] mb-6">Recent Inquiries</h3>
            
            <div className="space-y-2">
              {recentQueries.slice(0, 5).map((query, i) => (
                <div key={i} className="flex items-start gap-3 p-3 rounded-lg hover:bg-[var(--panel-soft)] transition cursor-default">
                  <svg className="text-[var(--text-faint)] mt-0.5 shrink-0" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
                  <span className="text-sm text-[var(--text-soft)] line-clamp-2">{query}</span>
                </div>
              ))}
              {!recentQueries.length ? <div className="text-sm text-[var(--text-muted)] italic px-2">Your search history is empty.</div> : null}
            </div>
          </section>

          {/* Topics */}
          <section className="glow-card p-6 sm:p-8">
            <div className="eyebrow mb-1">Knowledge</div>
            <h3 className="font-display text-xl font-bold text-[var(--text-main)] mb-6">Trending Topics</h3>
            
            <div className="flex flex-wrap gap-2 mb-6">
              {topTopics.slice(0, 8).map((topic, i) => (
                <div key={i} className="tag tag-accent text-xs px-3 py-1.5 flex items-center gap-2">
                  {topic.topic}
                  <span className="opacity-50 text-[10px]">{topic.count}</span>
                </div>
              ))}
              {!topTopics.length ? <div className="text-sm text-[var(--text-muted)] italic">No topic trends detected yet.</div> : null}
            </div>

            {weakTopics.length > 0 && (
              <div className="pt-5 border-t border-[var(--line)]">
                <div className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-3 flex items-center gap-2">
                  <svg className="text-[var(--warning)]" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg>
                  Needs Review
                </div>
                <div className="flex flex-wrap gap-2">
                  {weakTopics.slice(0, 6).map((topic, i) => (
                    <span key={i} className="tag text-xs">{topic}</span>
                  ))}
                </div>
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
