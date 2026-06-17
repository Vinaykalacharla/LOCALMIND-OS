"use client";

import { useEffect, useState } from "react";
import { Collection, getCollections, createCollection, deleteCollection, detectContradictions } from "@/lib/api";
import { useToast } from "@/components/ToastProvider";

export default function CollectionsPage() {
  const [collections, setCollections] = useState<Collection[]>([]);
  const [loading, setLoading] = useState(true);
  const [newWorkspaceName, setNewWorkspaceName] = useState("");
  const [analyzingId, setAnalyzingId] = useState<string | null>(null);
  const [analysisResult, setAnalysisResult] = useState<Record<string, string>>({});
  const { pushToast } = useToast();

  async function load() {
    setLoading(true);
    try {
      const response = await getCollections();
      setCollections(response.collections || []);
    } catch (error) {
      pushToast("error", "Failed to load workspaces");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!newWorkspaceName.trim()) return;
    try {
      await createCollection({ name: newWorkspaceName, files: [] });
      setNewWorkspaceName("");
      pushToast("success", "Workspace created");
      void load();
    } catch (error) {
      pushToast("error", "Failed to create workspace");
    }
  }

  
  async function handleAnalyze(c: Collection) {
    if (c.files.length === 0) {
      pushToast("error", "Add some files to this workspace first");
      return;
    }
    setAnalyzingId(c.id);
    try {
      const res = await detectContradictions(c.files);
      setAnalysisResult(prev => ({ ...prev, [c.id]: res.analysis }));
      if (res.has_contradiction) {
        pushToast("info", "Contradictions detected!");
      } else {
        pushToast("success", "No contradictions found");
      }
    } catch (error) {
      pushToast("error", "Analysis failed");
    } finally {
      setAnalyzingId(null);
    }
  }

  async function handleDelete(id: string) {
    if (!confirm("Are you sure you want to delete this workspace?")) return;
    try {
      await deleteCollection(id);
      pushToast("success", "Workspace deleted");
      void load();
    } catch (error) {
      pushToast("error", "Failed to delete workspace");
    }
  }

  return (
    <div className="space-y-8 pb-10 max-w-4xl mx-auto">
      <div className="shell-panel p-6 sm:p-8">
        <h2 className="font-display text-3xl font-bold text-white mb-2">Workspaces</h2>
        <p className="text-zinc-400 mb-8 text-sm">Group your files into persistent collections for targeted search and study.</p>

        <form onSubmit={handleCreate} className="flex gap-4 mb-8">
          <input
            type="text"
            className="flex-1 rounded-[14px] border border-white/8 bg-zinc-950/80 px-4 py-3 text-sm text-zinc-100 outline-none focus:border-sky-400"
            placeholder="New workspace name..."
            value={newWorkspaceName}
            onChange={(e) => setNewWorkspaceName(e.target.value)}
          />
          <button type="submit" className="btn-primary" disabled={!newWorkspaceName.trim()}>Create</button>
        </form>

        {loading ? (
          <div className="space-y-4">
            <div className="h-16 skeleton rounded-xl"></div>
            <div className="h-16 skeleton rounded-xl"></div>
          </div>
        ) : (
          <div className="space-y-4">
            {collections.length === 0 ? (
              <div className="text-sm text-zinc-500 italic text-center py-8">No workspaces created yet.</div>
            ) : (
              collections.map(c => (
                <div key={c.id} className="mb-4">
                  <div className="flex items-center justify-between p-4 rounded-xl bg-white/[0.02] border border-white/8 hover:bg-white/[0.04] transition">
                    <div>
                      <h3 className="font-semibold text-white">{c.name}</h3>
                      <p className="text-xs text-zinc-500 mt-1">{c.files.length} files attached</p>
                    </div>
                    <div className="flex gap-3">
                      <button onClick={() => handleAnalyze(c)} disabled={analyzingId === c.id} className="btn-secondary text-xs disabled:opacity-60">
                        {analyzingId === c.id ? "Analyzing..." : "Analyze Contradictions"}
                      </button>
                      <button onClick={() => handleDelete(c.id)} className="btn-secondary text-xs border-red-500/20 text-red-400 hover:bg-red-500/10">Delete</button>
                    </div>
                  </div>
                  {analysisResult[c.id] && (
                    <div className="p-4 mt-2 rounded-xl bg-sky-500/10 border border-sky-500/20 text-sm text-sky-100 whitespace-pre-wrap">
                      <div className="font-semibold mb-2 text-sky-300">Contradiction Analysis:</div>
                      {analysisResult[c.id]}
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
