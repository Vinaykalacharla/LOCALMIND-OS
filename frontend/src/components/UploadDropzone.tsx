"use client";

import { ChangeEvent, KeyboardEvent, useId, useRef, useState } from "react";

interface UploadDropzoneProps {
  onFilesSelected: (files: File[]) => void;
  disabled?: boolean;
}

export default function UploadDropzone({ onFilesSelected, disabled }: UploadDropzoneProps) {
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const inputId = useId();

  function normalize(files: FileList | null) {
    if (!files) return [];
    return Array.from(files).filter((file) => file.size > 0);
  }

  function handleManualSelect(event: ChangeEvent<HTMLInputElement>) {
    onFilesSelected(normalize(event.target.files));
    event.target.value = "";
  }

  function handleKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (disabled) return;
    if (event.key !== "Enter" && event.key !== " ") return;
    event.preventDefault();
    inputRef.current?.click();
  }

  return (
    <div
      role="button"
      tabIndex={disabled ? -1 : 0}
      aria-disabled={disabled}
      aria-label="Choose files to upload"
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
      className={`glow-card relative overflow-hidden border-2 border-dashed p-12 text-center transition-all duration-300 ${dragOver ? "border-[var(--accent)] bg-[var(--accent-dim)]" : "border-[var(--line-strong)] hover:border-[var(--line-accent)]"}`}
    >
      <input
        id={inputId}
        ref={inputRef}
        type="file"
        className="sr-only"
        multiple
        disabled={disabled}
        accept=".pdf,.txt,.md,.json,.py,.js,.ts,.tsx,.jsx,.java,.c,.cpp,.go,.rs,.yaml,.yml"
        onChange={handleManualSelect}
      />

      <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-[var(--panel-soft)] border border-[var(--line)] shadow-sm mb-6 text-[var(--accent-bright)]">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" x2="12" y1="3" y2="15"/>
        </svg>
      </div>

      <div className="eyebrow mb-2">Upload Data</div>
      <div className="font-display text-2xl font-bold text-[var(--text-main)] sm:text-3xl">
        Drag files here or choose them manually
      </div>
      <p className="mx-auto mt-3 max-w-xl text-sm text-[var(--text-muted)]">
        Add PDFs, notes, markdown, JSON, or code files to your local knowledge base. All processing happens entirely on your machine.
      </p>

      <label
        htmlFor={inputId}
        aria-disabled={disabled}
        className={`btn-primary mt-8 inline-flex ${disabled ? "pointer-events-none cursor-not-allowed opacity-60" : "cursor-pointer"}`}
      >
        Select Files to Upload
      </label>

      <div className="mt-6 flex flex-wrap justify-center gap-2">
        {['.pdf', '.txt', '.md', '.json', 'code'].map(ext => (
          <span key={ext} className="tag">{ext}</span>
        ))}
      </div>
    </div>
  );
}
