import { SearchItem } from "@/lib/api";

interface SearchResultsProps {
  results: SearchItem[];
  onOpenSource: (item: SearchItem) => void;
}

export default function SearchResults({ results, onOpenSource }: SearchResultsProps) {
  if (!results.length) {
    return (
      <div className="shell-panel p-6 text-sm leading-7 text-zinc-400">
        No results yet. Run a semantic search to inspect matching chunks and open the exact source text.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {results.map((item, index) => (
        <div key={item.chunk_id} className="shell-panel p-5 sm:p-6">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <div className="eyebrow">Result {index + 1}</div>
              <div className="mt-2 text-lg font-semibold text-white">
                {item.source_file}
                {item.page_number ? ` (p.${item.page_number})` : ""}
              </div>
              <div className="mt-2 flex flex-wrap gap-2">
                <span className="tag">Chunk {item.chunk_index}</span>
                <span className="tag">{item.chunk_id}</span>
              </div>
            </div>
            <div className="rounded-[16px] border border-white/8 bg-white/[0.03] px-4 py-3 text-center">
              <div className="text-[10px] uppercase tracking-[0.22em] text-zinc-500">Score</div>
              <div className="mt-2 text-lg font-semibold text-white">{item.score.toFixed(4)}</div>
            </div>
          </div>

          <div className="mt-5 rounded-[16px] border border-white/8 bg-white/[0.02] p-4">
            <p className="text-sm leading-7 text-zinc-300">{item.preview}</p>
          </div>

          <div className="mt-5 flex flex-wrap items-center justify-between gap-3">
            <div className="text-xs uppercase tracking-[0.18em] text-zinc-500">Open the full source to verify context.</div>
            <button onClick={() => onOpenSource(item)} className="btn-secondary">
              View Source
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
