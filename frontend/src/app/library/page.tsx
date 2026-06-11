"use client";

import { useEffect, useState } from "react";
import { getCatalog, SourceCatalogItem, getFileVersions, FileVersion, getFileDiff } from "@/lib/api";
import { useToast } from "@/components/ToastProvider";
import { formatDateTime } from "@/lib/format";

export default function LibraryPage() {
  const [catalog, setCatalog] = useState<SourceCatalogItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [versions, setVersions] = useState<FileVersion[]>([]);
  const [diffText, setDiffText] = useState<string | null>(null);
  const [comparing, setComparing] = useState<[string, string] | null>(null);
  const { pushToast } = useToast();

  useEffect(() => {
    async function load() {
      setLoading(true);
      try {
        const response = await getCatalog();
        setCatalog(response.sources || []);
      } catch (error) {
        pushToast("error", "Failed to load catalog");
      } finally {
        setLoading(false);
      }
    }
    void load();
  }, []);

  async function handleSelectFile(sourceFile: string) {
    if (selectedFile === sourceFile) {
      setSelectedFile(null);
      setVersions([]);
      setDiffText(null);
      setComparing(null);
      return;
    }
    setSelectedFile(sourceFile);
    setDiffText(null);
    setComparing(null);
    try {
      const res = await getFileVersions(sourceFile);
      setVersions(res.versions);
    } catch (e) {
      pushToast("error", "Failed to load versions");
    }
  }

  async function handleCompare(v1: string, v2: string) {
    if (!selectedFile) return;
    setComparing([v1, v2]);
    try {
      const res = await getFileDiff(selectedFile, v1, v2);
      setDiffText(res.diff);
    } catch (e) {
      pushToast("error", "Failed to load diff");
      setDiffText(null);
    }
  }

  return (
    <div className="space-y-8 pb-10 max-w-5xl mx-auto">
      <div className="shell-panel p-6 sm:p-8">
        <h2 className="font-display text-3xl font-bold text-white mb-2">Document Library</h2>
        <p className="text-zinc-400 mb-8 text-sm">View indexed files, extracted text versions, and document diffs.</p>

        {loading ? (
          <div className="space-y-4">
            <div className="h-16 skeleton rounded-xl"></div>
          </div>
        ) : (
          <div className="space-y-4">
            {catalog.length === 0 ? (
              <div className="text-sm text-zinc-500 italic text-center py-8">No documents indexed yet.</div>
            ) : (
              catalog.map(doc => (
                <div key={doc.source_file} className="rounded-xl bg-white/[0.02] border border-white/8 overflow-hidden">
                  <div 
                    className="p-4 flex items-center justify-between cursor-pointer hover:bg-white/[0.04] transition"
                    onClick={() => handleSelectFile(doc.source_file)}
                  >
                    <div>
                      <h3 className="font-semibold text-white">{doc.source_file}</h3>
                      <p className="text-xs text-zinc-500 mt-1">{doc.chunks} chunks • {doc.pages} pages</p>
                    </div>
                    <div className="text-sky-400 text-sm font-medium">
                      {selectedFile === doc.source_file ? "Hide Versions" : "View Versions"}
                    </div>
                  </div>
                  
                  {selectedFile === doc.source_file && (
                    <div className="p-4 border-t border-white/8 bg-black/20">
                      <h4 className="text-sm font-semibold text-zinc-300 mb-3">Extracted Text Versions</h4>
                      {versions.length < 2 ? (
                        <p className="text-xs text-zinc-500">Not enough versions to compare. Upload a modified version of this file with the same name to see diffs.</p>
                      ) : (
                        <div className="space-y-3">
                          <p className="text-xs text-zinc-400">Select any two adjacent versions to compare.</p>
                          <div className="flex flex-wrap gap-2">
                            {versions.slice(0, -1).map((v, idx) => {
                              const older = versions[idx + 1];
                              const isComparing = comparing?.[0] === older.version_id && comparing?.[1] === v.version_id;
                              return (
                                <button 
                                  key={v.version_id}
                                  onClick={() => handleCompare(older.version_id, v.version_id)}
                                  className={`px-3 py-1.5 text-xs rounded border transition ${isComparing ? 'bg-sky-500/20 border-sky-500/50 text-sky-200' : 'bg-white/5 border-white/10 hover:bg-white/10 text-zinc-300'}`}
                                >
                                  Compare {formatDateTime(new Date(older.timestamp * 1000).toISOString())} → {formatDateTime(new Date(v.timestamp * 1000).toISOString())}
                                </button>
                              );
                            })}
                          </div>
                          
                          {diffText && (
                            <div className="mt-4 p-4 rounded bg-[#0d1117] border border-[#30363d] overflow-x-auto">
                              <pre className="text-xs leading-5">
                                {diffText.split('\\n').map((line, i) => {
                                  let color = 'text-zinc-300';
                                  if (line.startsWith('+')) color = 'text-[#3fb950] bg-[#2ea0431a]';
                                  else if (line.startsWith('-')) color = 'text-[#f85149] bg-[#f851491a]';
                                  else if (line.startsWith('@@')) color = 'text-[#388bfd]';
                                  return <div key={i} className={color}>{line}</div>;
                                })}
                              </pre>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        )}
      </div>
    </div>
  );
}
