"use client";

import { useEffect, useMemo, useState } from "react";
import SearchResults from "@/components/SearchResults";
import SourceModal from "@/components/SourceModal";
import { SearchItem, SourceCatalogItem, getCatalog, semanticSearch } from "@/lib/api";
import { useToast } from "@/components/ToastProvider";
import { formatNumber } from "@/lib/format";

const PRESET_QUERIES = [
  "tcp congestion control",
  "compare cross entropy and mse",
  "revision plan weak topics"
];

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState<SearchItem | null>(null);
  const [topK, setTopK] = useState(5);
  const [lastSearchQuery, setLastSearchQuery] = useState("");
  const [catalog, setCatalog] = useState<SourceCatalogItem[]>([]);
  const [catalogFilter, setCatalogFilter] = useState("");
  const [selectedSourceFiles, setSelectedSourceFiles] = useState<string[]>([]);
  const { pushToast } = useToast();

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

  const visibleCatalog = useMemo(() => {
    const normalized = catalogFilter.trim().toLowerCase();
    if (!normalized) return catalog;
    return catalog.filter((item) => item.source_file.toLowerCase().includes(normalized));
  }, [catalog, catalogFilter]);

  function toggleSourceFile(sourceFile: string) {
    setSelectedSourceFiles((current) =>
      current.includes(sourceFile) ? current.filter((item) => item !== sourceFile) : [...current, sourceFile]
    );
  }

  async function runSearch(nextQuery = query, nextTopK = topK, nextSourceFiles = selectedSourceFiles) {
    const trimmed = nextQuery.trim();
    if (!trimmed || loading) return;
    setLoading(true);
    try {
      const response = await semanticSearch(trimmed, {
        topK: nextTopK,
        sourceFiles: nextSourceFiles
      });
      setResults(response.results);
      setLastSearchQuery(trimmed);
      if (!response.results.length) {
        pushToast("info", nextSourceFiles.length ? "No matching chunks found in the selected files" : "No similar chunks found");
      }
    } catch (error) {
      const msg = error instanceof Error ? error.message : "Search failed";
      pushToast("error", msg);
    } finally {
      setLoading(false);
    }
  }

  function handleTopKChange(value: number) {
    if (value === topK) return;
    setTopK(value);
    if (lastSearchQuery) {
      void runSearch(lastSearchQuery, value, selectedSourceFiles);
    }
  }

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <section className="grid gap-6 xl:grid-cols-[minmax(0,1.15fr)_320px]">
        <div className="shell-panel p-6 sm:p-8">
          <div className="eyebrow">Search</div>
          <h2 className="mt-3 font-display text-3xl font-semibold text-white sm:text-[2.6rem]">
            Find the most relevant parts of your local data.
          </h2>
          <p className="mt-3 max-w-3xl text-sm leading-7 text-zinc-400 sm:text-base">
            Run a semantic search, optionally restrict it to specific files, and inspect the matching chunks before using them.
          </p>

          <div className="mt-6 flex flex-col gap-3 lg:flex-row">
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  void runSearch();
                }
              }}
              placeholder="Search your knowledge base"
              className="input-shell min-h-[56px] flex-1"
            />
            <button onClick={() => void runSearch()} disabled={loading} className="btn-primary min-h-[56px] min-w-[150px] disabled:opacity-60">
              {loading ? "Searching..." : "Search"}
            </button>
          </div>

          <div className="mt-4 flex flex-wrap gap-2">
            {PRESET_QUERIES.map((preset) => (
              <button
                key={preset}
                onClick={() => {
                  setQuery(preset);
                  void runSearch(preset, topK, selectedSourceFiles);
                }}
                className="tag transition hover:bg-white/[0.05]"
              >
                {preset}
              </button>
            ))}
          </div>
        </div>

        <div className="shell-panel p-5">
          <div className="eyebrow">Settings</div>
          <div className="mt-2 text-xl font-semibold text-white">Retrieval options</div>

          <div className="mt-5">
            <div className="text-[11px] uppercase tracking-[0.22em] text-zinc-500">Results to return</div>
            <div className="mt-3 flex flex-wrap gap-2">
              {[3, 5, 8, 12].map((value) => (
                <button
                  key={value}
                  onClick={() => handleTopKChange(value)}
                  className={`rounded-full border px-4 py-2 text-sm transition ${
                    topK === value
                      ? "border-white/14 bg-white/[0.08] text-white"
                      : "border-white/8 bg-transparent text-zinc-300 hover:bg-white/[0.04]"
                  }`}
                >
                  {value}
                </button>
              ))}
            </div>
          </div>

          <div className="mt-5 grid gap-3">
            <div className="metric-tile">
              <div className="text-[11px] uppercase tracking-[0.22em] text-zinc-500">top_k</div>
              <div className="mt-2 text-3xl font-display font-semibold text-white">{topK}</div>
            </div>
            <div className="metric-tile">
              <div className="text-[11px] uppercase tracking-[0.22em] text-zinc-500">Scoped files</div>
              <div className="mt-2 text-3xl font-display font-semibold text-white">{formatNumber(selectedSourceFiles.length)}</div>
            </div>
            <div className="metric-tile">
              <div className="text-[11px] uppercase tracking-[0.22em] text-zinc-500">Current results</div>
              <div className="mt-2 text-3xl font-display font-semibold text-white">{formatNumber(results.length)}</div>
            </div>
          </div>
        </div>
      </section>

      <section className="shell-panel p-5 sm:p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="eyebrow">Source scope</div>
            <div className="mt-2 text-2xl font-semibold text-white">Search within selected files</div>
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

        <div className="mt-4 max-h-[280px] overflow-auto pr-1">
          <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
            {visibleCatalog.map((item) => {
              const selectedFile = selectedSourceFiles.includes(item.source_file);
              return (
                <button
                  key={item.source_file}
                  type="button"
                  onClick={() => toggleSourceFile(item.source_file)}
                  className={`rounded-[16px] border px-4 py-3 text-left transition ${
                    selectedFile
                      ? "border-sky-300/30 bg-sky-300/10"
                      : "border-white/8 bg-white/[0.02] hover:bg-white/[0.04]"
                  }`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="text-sm font-medium text-white">{item.source_file}</div>
                    <div className="tag">{item.kind}</div>
                  </div>
                  <div className="mt-2 text-xs text-zinc-400">
                    {item.chunks} chunks{item.pages ? ` - ${item.pages} pages` : ""}
                  </div>
                </button>
              );
            })}
          </div>
          {!visibleCatalog.length ? <div className="mt-2 text-sm text-zinc-500">No indexed files match this filter.</div> : null}
        </div>
      </section>

      {loading ? (
        <div className="space-y-3">
          <div className="h-32 animate-pulse rounded-[20px] bg-white/5" />
          <div className="h-32 animate-pulse rounded-[20px] bg-white/5" />
          <div className="h-32 animate-pulse rounded-[20px] bg-white/5" />
        </div>
      ) : (
        <section className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="eyebrow">Results</div>
              <div className="mt-2 text-2xl font-semibold text-white">
                {results.length ? `${results.length} result${results.length === 1 ? "" : "s"}` : "No results"}
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              {query.trim() ? <div className="tag">{query.trim()}</div> : null}
              {selectedSourceFiles.length ? (
                <div className="tag">{selectedSourceFiles.length} scoped file{selectedSourceFiles.length === 1 ? "" : "s"}</div>
              ) : null}
            </div>
          </div>
          <SearchResults results={results} onOpenSource={setSelected} />
        </section>
      )}

      <SourceModal item={selected} onClose={() => setSelected(null)} />
    </div>
  );
}
