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
      onKeyDown={handleKeyDown}
      className={`shell-panel border-2 border-dashed p-8 text-center transition ${dragOver ? "border-sky-300/30 bg-white/[0.04]" : "border-white/10"}`}
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

      <div className="eyebrow">Upload</div>
      <div className="mt-3 font-display text-3xl font-semibold text-white sm:text-[2.5rem]">
        Drag files here or choose them manually.
      </div>
      <p className="mx-auto mt-3 max-w-2xl text-sm leading-7 text-zinc-400 sm:text-base">
        Add PDFs, notes, markdown, JSON, or code files to your local knowledge base.
      </p>

      <label
        htmlFor={inputId}
        aria-disabled={disabled}
        className={`btn-primary mt-6 ${disabled ? "pointer-events-none cursor-not-allowed opacity-60" : "cursor-pointer"}`}
      >
        Choose Files
      </label>

      <div className="mt-4 text-xs uppercase tracking-[0.22em] text-zinc-500">
        pdf, txt, md, json, py, js, ts, tsx, jsx, java, c, cpp, go, rs, yaml, yml
      </div>
    </div>
  );
}
