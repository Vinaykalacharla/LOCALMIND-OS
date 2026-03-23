import { SearchItem } from "@/lib/api";

interface SourceModalProps {
  item: SearchItem | null;
  onClose: () => void;
}

export default function SourceModal({ item, onClose }: SourceModalProps) {
  if (!item) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm" onClick={onClose}>
      <div
        className="shell-panel max-h-[85vh] w-full max-w-3xl overflow-auto p-6"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="mb-4 flex items-start justify-between gap-4">
          <div>
            <div className="eyebrow">Source Preview</div>
            <h3 className="mt-2 text-xl font-semibold text-white">
              {item.source_file}
              {item.page_number ? ` (p.${item.page_number})` : ""}
            </h3>
            <div className="mt-2 text-xs uppercase tracking-[0.2em] text-zinc-500">Chunk {item.chunk_id}</div>
          </div>
          <button onClick={onClose} className="btn-secondary">
            Close
          </button>
        </div>

        <div className="mb-4 flex flex-wrap gap-2">
          <span className="tag">Chunk {item.chunk_index}</span>
          <span className="tag">Score {item.score.toFixed(4)}</span>
          {item.page_number ? <span className="tag">Page {item.page_number}</span> : null}
        </div>

        <div className="rounded-[24px] border border-white/10 bg-black/20 p-4">
          <pre className="whitespace-pre-wrap text-sm leading-7 text-zinc-200">{item.text || item.preview}</pre>
        </div>
      </div>
    </div>
  );
}
