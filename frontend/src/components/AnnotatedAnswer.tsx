"use client";

interface AnnotatedAnswerProps {
  text: string;
  activeCitation: string | null;
  onCitationClick: (citation: string) => void;
}

const CITATION_RE = /(\[S\d+\])/g;

export default function AnnotatedAnswer({ text, activeCitation, onCitationClick }: AnnotatedAnswerProps) {
  const parts = text.split(CITATION_RE);

  return (
    <div className="whitespace-pre-wrap text-sm leading-7 text-zinc-100">
      {parts.map((part, index) => {
        const matched = part.match(/^\[(S\d+)\]$/);
        if (!matched) {
          return <span key={`${part}_${index}`}>{part}</span>;
        }

        const citation = matched[1];
        const active = citation === activeCitation;
        return (
          <button
            key={`${citation}_${index}`}
            type="button"
            onClick={() => onCitationClick(citation)}
            className={`mx-0.5 inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium transition ${
              active
                ? "border-sky-300/45 bg-sky-300/16 text-sky-100"
                : "border-white/10 bg-white/[0.03] text-zinc-200 hover:bg-white/[0.06]"
            }`}
          >
            {citation}
          </button>
        );
      })}
    </div>
  );
}
