"use client";

import { useRef, useState } from "react";

interface UploadDropzoneProps {
  onFilesSelected: (files: File[]) => void;
  disabled?: boolean;
}

export default function UploadDropzone({ onFilesSelected, disabled }: UploadDropzoneProps) {
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement | null>(null);

  function normalize(files: FileList | null) {
    if (!files) return [];
    return Array.from(files).filter((file) => file.size > 0);
  }

  return (
    <div
      onDragEnter={(event) => {
        event.preventDefault();
        setDragOver(true);
      }}
      onDragOver={(event) => {
        event.preventDefault();
        setDragOver(true);
      }}
      onDragLeave={(event) => {
        event.preventDefault();
        setDragOver(false);
      }}
      onDrop={(event) => {
        event.preventDefault();
        setDragOver(false);
        if (disabled) return;
        onFilesSelected(normalize(event.dataTransfer.files));
      }}
      className={`shell-panel border-2 border-dashed p-8 text-center transition ${dragOver ? "border-sky-300/30 bg-white/[0.04]" : "border-white/10"}`}
    >
      <input
        ref={inputRef}
        type="file"
        className="hidden"
        multiple
        disabled={disabled}
        accept=".pdf,.txt,.md,.json,.py,.js,.ts,.tsx,.jsx,.java,.c,.cpp,.go,.rs,.yaml,.yml"
        onChange={(event) => onFilesSelected(normalize(event.target.files))}
      />

      <div className="eyebrow">Upload</div>
      <div className="mt-3 font-display text-3xl font-semibold text-white sm:text-[2.5rem]">
        Drag files here or choose them manually.
      </div>
      <p className="mx-auto mt-3 max-w-2xl text-sm leading-7 text-zinc-400 sm:text-base">
        Add PDFs, notes, markdown, JSON, or code files to your local knowledge base.
      </p>

      <button
        type="button"
        disabled={disabled}
        onClick={() => inputRef.current?.click()}
        className="btn-primary mt-6 disabled:cursor-not-allowed disabled:opacity-60"
      >
        Choose Files
      </button>

      <div className="mt-4 text-xs uppercase tracking-[0.22em] text-zinc-500">
        pdf, txt, md, json, py, js, ts, tsx, jsx, java, c, cpp, go, rs, yaml, yml
      </div>
    </div>
  );
}
