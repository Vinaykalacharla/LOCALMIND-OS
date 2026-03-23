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
    <div className="mx-auto max-w-[1400px]">
      {loading ? <div className="h-[32rem] animate-pulse rounded-[28px] bg-white/5" /> : <GraphView graph={graph} />}
    </div>
  );
}
