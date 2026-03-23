"use client";

import { useEffect, useMemo, useState } from "react";
import UploadDropzone from "@/components/UploadDropzone";
import { getStatus, ingestDemoData, ingestFiles, JobStatus } from "@/lib/api";
import { useToast } from "@/components/ToastProvider";
import { formatDateTime, formatNumber } from "@/lib/format";

const initialStatus: JobStatus = { state: "processing", step: "queued", progress: 0, message: "Queued" };

function formatFileSize(value: number): string {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${Math.round(value / 1024)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

export default function UploadPage() {
  const [files, setFiles] = useState<File[]>([]);
  const [jobId, setJobId] = useState<string | null>(null);
  const [status, setStatus] = useState<JobStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const { pushToast } = useToast();

  useEffect(() => {
    if (!jobId) return;
    const timer = setInterval(async () => {
      try {
        const response = await getStatus(jobId);
        setStatus(response);
        if (response.state === "done" || response.state === "error") {
          clearInterval(timer);
          setBusy(false);
          pushToast(response.state === "done" ? "success" : "error", response.message || response.state);
        }
      } catch (error) {
        const msg = error instanceof Error ? error.message : "Failed to fetch job status";
        pushToast("error", msg);
        clearInterval(timer);
        setBusy(false);
      }
    }, 900);
    return () => clearInterval(timer);
  }, [jobId, pushToast]);

  const totalSize = useMemo(() => files.reduce((acc, file) => acc + file.size, 0), [files]);

  function addFiles(nextFiles: File[]) {
    setFiles((prev) => {
      const keyed = new Map(prev.map((file) => [`${file.name}_${file.size}_${file.lastModified}`, file] as const));
      nextFiles.forEach((file) => keyed.set(`${file.name}_${file.size}_${file.lastModified}`, file));
      return Array.from(keyed.values());
    });
  }

  function removeFile(target: File) {
    setFiles((prev) =>
      prev.filter((file) => `${file.name}_${file.size}_${file.lastModified}` !== `${target.name}_${target.size}_${target.lastModified}`)
    );
  }

  async function onUpload() {
    if (!files.length || busy) return;
    setBusy(true);
    setStatus(initialStatus);
    try {
      const response = await ingestFiles(files);
      setJobId(response.job_id);
      pushToast("info", "Upload started");
    } catch (error) {
      setBusy(false);
      const msg = error instanceof Error ? error.message : "Upload failed";
      pushToast("error", msg);
    }
  }

  async function onLoadDemo() {
    if (busy) return;
    setBusy(true);
    setStatus(initialStatus);
    try {
      const response = await ingestDemoData();
      setJobId(response.job_id);
      pushToast("info", "Demo upload started");
    } catch (error) {
      setBusy(false);
      const msg = error instanceof Error ? error.message : "Demo ingest failed";
      pushToast("error", msg);
    }
  }

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <section className="grid gap-6 xl:grid-cols-[minmax(0,1.15fr)_340px]">
        <UploadDropzone onFilesSelected={addFiles} disabled={busy} />

        <div className="shell-panel p-5">
          <div className="eyebrow">How it works</div>
          <div className="mt-2 text-2xl font-semibold text-white">Upload flow</div>
          <div className="mt-4 space-y-3 text-sm leading-7 text-zinc-400">
            <div className="rounded-[16px] border border-white/8 bg-white/[0.02] px-4 py-4">
              Files are processed locally and added to search and graph views.
            </div>
            <div className="rounded-[16px] border border-white/8 bg-white/[0.02] px-4 py-4">
              Duplicate files are skipped when they were already indexed.
            </div>
            <div className="rounded-[16px] border border-white/8 bg-white/[0.02] px-4 py-4">
              If the vault is enabled, stored data remains encrypted at rest.
            </div>
          </div>

          <div className="mt-5 flex flex-wrap gap-3">
            <button onClick={onUpload} disabled={!files.length || busy} className="btn-primary disabled:opacity-60">
              {busy ? "Processing..." : "Upload and index"}
            </button>
            <button onClick={onLoadDemo} disabled={busy} className="btn-secondary disabled:opacity-60">
              Load demo data
            </button>
          </div>
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-[minmax(0,1.08fr)_minmax(320px,0.92fr)]">
        <div className="shell-panel p-5 sm:p-6">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="eyebrow">Selected files</div>
              <div className="mt-2 text-2xl font-semibold text-white">Upload list</div>
            </div>
            {files.length ? (
              <button onClick={() => setFiles([])} className="btn-secondary">
                Clear all
              </button>
            ) : null}
          </div>

          <div className="mt-5 grid gap-3 sm:grid-cols-3">
            <div className="metric-tile">
              <div className="text-[11px] uppercase tracking-[0.22em] text-zinc-500">Files</div>
              <div className="mt-2 text-3xl font-display font-semibold text-white">{formatNumber(files.length)}</div>
            </div>
            <div className="metric-tile">
              <div className="text-[11px] uppercase tracking-[0.22em] text-zinc-500">Total size</div>
              <div className="mt-2 text-3xl font-display font-semibold text-white">{formatFileSize(totalSize)}</div>
            </div>
            <div className="metric-tile">
              <div className="text-[11px] uppercase tracking-[0.22em] text-zinc-500">Status</div>
              <div className="mt-2 text-lg font-medium capitalize text-white">{status?.state ?? "idle"}</div>
            </div>
          </div>

          <div className="mt-5 space-y-2">
            {files.length ? (
              files.map((file) => (
                <div
                  key={`${file.name}_${file.size}_${file.lastModified}`}
                  className="flex flex-wrap items-center justify-between gap-3 rounded-[16px] border border-white/8 bg-white/[0.02] px-4 py-4"
                >
                  <div className="min-w-0">
                    <div className="truncate text-sm font-medium text-white">{file.name}</div>
                    <div className="mt-1 text-xs uppercase tracking-[0.18em] text-zinc-500">
                      {formatFileSize(file.size)} | modified {formatDateTime(new Date(file.lastModified).toISOString())}
                    </div>
                  </div>
                  <button onClick={() => removeFile(file)} className="btn-secondary">
                    Remove
                  </button>
                </div>
              ))
            ) : (
              <div className="rounded-[16px] border border-white/8 bg-white/[0.02] px-4 py-4 text-sm text-zinc-500">
                No files selected yet.
              </div>
            )}
          </div>
        </div>

        <div className="space-y-6">
          <div className="shell-panel p-5 sm:p-6">
            <div className="eyebrow">Progress</div>
            <div className="mt-2 text-2xl font-semibold text-white">Current upload</div>

            {status ? (
              <div className="mt-5 space-y-4">
                <div className="flex items-center justify-between gap-3">
                  <span className="tag">{status.step}</span>
                  <span className="text-sm font-medium text-white">{status.progress}%</span>
                </div>
                <div className="h-2.5 w-full overflow-hidden rounded-full bg-white/8">
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-sky-400 to-sky-300 transition-all"
                    style={{ width: `${Math.max(4, status.progress)}%` }}
                  />
                </div>
                <div className="rounded-[16px] border border-white/8 bg-white/[0.02] px-4 py-4 text-sm leading-7 text-zinc-300">
                  {status.message}
                </div>
              </div>
            ) : (
              <div className="mt-5 rounded-[16px] border border-white/8 bg-white/[0.02] px-4 py-4 text-sm leading-7 text-zinc-500">
                No upload is running.
              </div>
            )}
          </div>

          <div className="shell-panel p-5">
            <div className="eyebrow">Steps</div>
            <div className="mt-2 text-2xl font-semibold text-white">Pipeline</div>
            <div className="mt-4 space-y-3">
              <div className="rounded-[14px] border border-white/8 bg-white/[0.02] px-4 py-3 text-sm text-zinc-300">
                1. Extract readable text from files.
              </div>
              <div className="rounded-[14px] border border-white/8 bg-white/[0.02] px-4 py-3 text-sm text-zinc-300">
                2. Create chunks and embeddings.
              </div>
              <div className="rounded-[14px] border border-white/8 bg-white/[0.02] px-4 py-3 text-sm text-zinc-300">
                3. Refresh search and graph data.
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
