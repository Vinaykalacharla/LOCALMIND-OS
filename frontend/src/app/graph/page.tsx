"use client";

import { useEffect, useState } from "react";
import GraphView from "@/components/GraphView";
import { GraphResponse, getGraph } from "@/lib/api";
import { useToast } from "@/components/ToastProvider";

export default function GraphPage() {
  const [graph, setGraph] = useState<GraphResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const { pushToast } = useToast();

  useEffect(() => {
    async function loadGraph() {
      setLoading(true);
      try {
        const res = await getGraph();
        setGraph(res);
      } catch (error) {
        const msg = error instanceof Error ? error.message : "Graph load failed";
        pushToast("error", msg);
      } finally {
        setLoading(false);
      }
    }
    loadGraph();
  }, [pushToast]);

  return (
    <div className="mx-auto max-w-[1480px]">
      {loading ? (
        <div className="shell-panel overflow-hidden p-0">
          <div className="border-b border-white/8 bg-white/[0.02] px-5 py-4">
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <span className="h-3 w-3 rounded-full bg-[#ff5f57]" />
                <span className="h-3 w-3 rounded-full bg-[#febc2e]" />
                <span className="h-3 w-3 rounded-full bg-[#28c840]" />
              </div>
              <div>
                <div className="text-sm font-medium text-white">Loading graph studio</div>
                <div className="mt-1 text-xs text-zinc-400">Preparing nodes, relation lanes, and the inspector surface.</div>
              </div>
            </div>
          </div>

          <div className="grid gap-5 p-5 xl:grid-cols-[minmax(0,1.08fr)_380px]">
            <div className="h-[48rem] animate-pulse rounded-[30px] border border-white/8 bg-[radial-gradient(circle_at_top,rgba(119,167,255,0.08),rgba(255,255,255,0.02))]" />
            <div className="space-y-5">
              <div className="h-[25rem] animate-pulse rounded-[24px] border border-white/8 bg-white/[0.03]" />
              <div className="h-[18rem] animate-pulse rounded-[24px] border border-white/8 bg-white/[0.03]" />
            </div>
          </div>
        </div>
      ) : (
        <GraphView graph={graph} />
      )}
    </div>
  );
}
