"use client";

import { useEffect, useMemo, useState } from "react";
import { GraphEdge, GraphNode, GraphNodeType, GraphResponse } from "@/lib/api";
import { formatNumber } from "@/lib/format";

interface GraphViewProps {
  graph: GraphResponse | null;
}

type GraphFilter = "all" | GraphNodeType;

interface PositionedNode extends GraphNode {
  x: number;
  y: number;
  radius: number;
}

const GRAPH_WIDTH = 1140;
const GRAPH_HEIGHT = 760;

const TYPE_ORDER: GraphNodeType[] = ["doc", "project", "topic", "person", "other"];
const TYPE_COLORS: Record<GraphNodeType, string> = {
  doc: "#d6b174",
  person: "#8fd8a8",
  project: "#84d1c1",
  topic: "#8aa9e8",
  other: "#9aa3af"
};

const TYPE_LABELS: Record<GraphFilter, string> = {
  all: "All",
  doc: "Documents",
  project: "Projects",
  topic: "Topics",
  person: "People",
  other: "Other"
};

const GROUP_CENTERS: Record<GraphNodeType, { x: number; y: number }> = {
  doc: { x: 210, y: 190 },
  project: { x: 570, y: 190 },
  topic: { x: 930, y: 190 },
  person: { x: 390, y: 540 },
  other: { x: 780, y: 540 }
};

function buildLayout(nodes: GraphNode[]): PositionedNode[] {
  const grouped = new Map<GraphNodeType, GraphNode[]>();
  TYPE_ORDER.forEach((type) => grouped.set(type, []));
  nodes.forEach((node) => {
    grouped.get(node.type)?.push(node);
  });

  const positioned: PositionedNode[] = [];
  TYPE_ORDER.forEach((type) => {
    const group = (grouped.get(type) ?? []).sort(
      (a, b) => b.mentions - a.mentions || b.degree - a.degree || a.label.localeCompare(b.label)
    );
    const center = GROUP_CENTERS[type];
    const columns = Math.max(1, Math.ceil(Math.sqrt(group.length || 1)));
    const rows = Math.max(1, Math.ceil(group.length / columns));

    group.forEach((node, index) => {
      const col = index % columns;
      const row = Math.floor(index / columns);
      const x = center.x + (col - (columns - 1) / 2) * 86 + (row % 2 === 0 ? 0 : 12);
      const y = center.y + (row - (rows - 1) / 2) * 76;
      positioned.push({
        ...node,
        x,
        y,
        radius: Math.min(22, 8 + node.mentions * 2)
      });
    });
  });

  return positioned;
}

function connectedNodeIds(edges: GraphEdge[], nodeId: string | null): Set<string> {
  const ids = new Set<string>();
  if (!nodeId) {
    return ids;
  }
  for (const edge of edges) {
    if (edge.source === nodeId) {
      ids.add(edge.target);
    } else if (edge.target === nodeId) {
      ids.add(edge.source);
    }
  }
  return ids;
}

function statusForRelation(edge: GraphEdge, selectedId: string | null): "selected" | "muted" | "normal" {
  if (!selectedId) {
    return "normal";
  }
  if (edge.source === selectedId || edge.target === selectedId) {
    return "selected";
  }
  return "muted";
}

export default function GraphView({ graph }: GraphViewProps) {
  const [filter, setFilter] = useState<GraphFilter>("all");
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const visibleNodes = useMemo(() => {
    if (!graph) {
      return [];
    }
    const normalizedQuery = query.trim().toLowerCase();
    return graph.nodes.filter((node) => {
      const matchesType = filter === "all" || node.type === filter;
      const matchesQuery = !normalizedQuery || node.label.toLowerCase().includes(normalizedQuery);
      return matchesType && matchesQuery;
    });
  }, [filter, graph, query]);

  const visibleNodeIds = useMemo(() => new Set(visibleNodes.map((node) => node.id)), [visibleNodes]);
  const visibleEdges = useMemo(() => {
    if (!graph) {
      return [];
    }
    return graph.edges
      .filter((edge) => visibleNodeIds.has(edge.source) && visibleNodeIds.has(edge.target))
      .sort((a, b) => b.weight - a.weight || a.relation.localeCompare(b.relation))
      .slice(0, 180);
  }, [graph, visibleNodeIds]);

  const positionedNodes = useMemo(() => buildLayout(visibleNodes), [visibleNodes]);
  const positionedById = useMemo(() => new Map(positionedNodes.map((node) => [node.id, node])), [positionedNodes]);

  useEffect(() => {
    if (!visibleNodes.length) {
      setSelectedId(null);
      return;
    }
    if (!selectedId || !visibleNodes.some((node) => node.id === selectedId)) {
      setSelectedId(visibleNodes[0].id);
    }
  }, [selectedId, visibleNodes]);

  if (!graph || graph.nodes.length === 0) {
    return <div className="shell-panel p-6 text-sm leading-7 text-zinc-400">Graph will appear after ingestion.</div>;
  }

  const selectedNode = positionedNodes.find((node) => node.id === selectedId) ?? null;
  const neighborIds = connectedNodeIds(visibleEdges, selectedId);
  const relatedConnections = selectedNode
    ? visibleEdges
        .filter((edge) => edge.source === selectedNode.id || edge.target === selectedNode.id)
        .map((edge) => {
          const otherId = edge.source === selectedNode.id ? edge.target : edge.source;
          return {
            edge,
            node: positionedById.get(otherId)
          };
        })
        .filter((item) => item.node)
        .sort((a, b) => {
          const weightDiff = b.edge.weight - a.edge.weight;
          if (weightDiff !== 0) return weightDiff;
          return (b.node?.mentions ?? 0) - (a.node?.mentions ?? 0);
        })
        .slice(0, 8)
    : [];

  return (
    <div className="space-y-4">
      <div className="shell-panel p-5 sm:p-6">
        <div className="mb-6 grid gap-4 xl:grid-cols-[minmax(0,1.05fr)_320px]">
          <div>
            <div className="eyebrow">Knowledge Map</div>
            <div className="mt-2 text-3xl font-semibold text-white sm:text-[2.6rem]">
              Explore how your documents and topics connect.
            </div>
            <div className="mt-3 max-w-3xl text-sm leading-7 text-zinc-400">
              Filter the graph, search by label, and inspect related nodes from one place.
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-3 xl:grid-cols-1">
            <div className="metric-tile">
              <div className="text-[11px] uppercase tracking-[0.24em] text-zinc-500">Visible nodes</div>
              <div className="mt-3 text-3xl font-display font-semibold text-white">{formatNumber(visibleNodes.length)}</div>
            </div>
            <div className="metric-tile">
              <div className="text-[11px] uppercase tracking-[0.24em] text-zinc-500">Visible edges</div>
              <div className="mt-3 text-3xl font-display font-semibold text-white">{formatNumber(visibleEdges.length)}</div>
            </div>
            <div className="metric-tile">
              <div className="text-[11px] uppercase tracking-[0.24em] text-zinc-500">Selected node</div>
              <div className="mt-3 text-sm font-semibold text-white">{selectedNode?.label ?? "None"}</div>
            </div>
          </div>
        </div>

        <div className="mb-4 flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
          <div>
            <div className="text-sm font-medium text-white">Relationship filters</div>
            <div className="text-xs text-zinc-400">
              Showing {visibleNodes.length} of {graph.nodes.length} nodes and {visibleEdges.length} weighted edges.
            </div>
          </div>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Filter graph labels..."
              className="input-shell min-w-[220px]"
            />
            <div className="flex flex-wrap gap-2">
              {(["all", ...TYPE_ORDER] as GraphFilter[]).map((type) => (
                <button
                  key={type}
                  onClick={() => setFilter(type)}
                  className={`rounded-full border px-3 py-1.5 text-xs transition ${
                    filter === type
                      ? "border-white/16 bg-white/[0.12] text-white"
                      : "border-white/10 text-zinc-300 hover:bg-white/[0.07]"
                  }`}
                >
                  {TYPE_LABELS[type]}
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
          <div className="overflow-auto rounded-[20px] border border-white/8 bg-white/[0.02] p-3 signal-grid">
            <svg viewBox={`0 0 ${GRAPH_WIDTH} ${GRAPH_HEIGHT}`} className="h-[680px] w-full min-w-[840px]">
              {TYPE_ORDER.map((type) => {
                const center = GROUP_CENTERS[type];
                return (
                  <g key={type}>
                    <rect
                      x={center.x - 150}
                      y={center.y - 110}
                      width={300}
                      height={220}
                      rx={28}
                      fill="rgba(15, 23, 42, 0.18)"
                      stroke="rgba(255,255,255,0.08)"
                      strokeDasharray="6 10"
                    />
                    <text x={center.x} y={center.y - 86} textAnchor="middle" fill="#94a3b8" fontSize="16">
                      {TYPE_LABELS[type]}
                    </text>
                  </g>
                );
              })}

              {visibleEdges.map((edge, index) => {
                const source = positionedById.get(edge.source);
                const target = positionedById.get(edge.target);
                if (!source || !target) return null;
                const relationState = statusForRelation(edge, selectedId);
                const stroke =
                  relationState === "selected"
                    ? "rgba(132, 209, 193, 0.95)"
                    : relationState === "muted"
                      ? "rgba(71, 85, 105, 0.2)"
                      : "rgba(120, 140, 160, 0.48)";
                const opacity = relationState === "muted" ? 0.45 : Math.min(0.9, 0.3 + edge.weight * 0.12);
                return (
                  <line
                    key={`${edge.source}_${edge.target}_${index}`}
                    x1={source.x}
                    y1={source.y}
                    x2={target.x}
                    y2={target.y}
                    stroke={stroke}
                    strokeWidth={relationState === "selected" ? 2.5 : 0.9 + edge.weight * 0.35}
                    opacity={opacity}
                  />
                );
              })}

              {positionedNodes.map((node) => {
                const selected = node.id === selectedId;
                const connected = neighborIds.has(node.id);
                const faded = !!selectedId && !selected && !connected;
                const showLabel = selected || connected || node.mentions >= 3 || positionedNodes.length <= 18;
                return (
                  <g
                    key={node.id}
                    onClick={() => setSelectedId(node.id)}
                    style={{ cursor: "pointer", opacity: faded ? 0.45 : 1 }}
                  >
                    <circle
                      cx={node.x}
                      cy={node.y}
                      r={node.radius}
                      fill={TYPE_COLORS[node.type]}
                      stroke={selected ? "#f8fafc" : "rgba(255,255,255,0.25)"}
                      strokeWidth={selected ? 3 : 1}
                    />
                    <circle cx={node.x} cy={node.y} r={Math.max(2, node.radius - 4)} fill="rgba(2,6,23,0.16)" />
                    {showLabel ? (
                      <text
                        x={node.x}
                        y={node.y + node.radius + 16}
                        textAnchor="middle"
                        fill={selected ? "#f8fafc" : "#cbd5e1"}
                        fontSize="12"
                      >
                        {node.label.slice(0, 28)}
                      </text>
                    ) : null}
                  </g>
                );
              })}
            </svg>
          </div>

          <div className="shell-panel-soft p-4">
            <div className="mb-3 text-sm font-medium text-white">Node details</div>
            {selectedNode ? (
              <div className="space-y-4">
                <div>
                  <div className="mb-1 text-lg font-semibold text-white">{selectedNode.label}</div>
                  <div className="text-xs uppercase tracking-[0.2em] text-zinc-400">{selectedNode.type}</div>
                </div>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div className="rounded-[18px] border border-white/10 bg-white/[0.04] p-3">
                    <div className="text-zinc-400">Mentions</div>
                    <div className="mt-1 text-lg font-semibold text-white">{selectedNode.mentions}</div>
                  </div>
                  <div className="rounded-[18px] border border-white/10 bg-white/[0.04] p-3">
                    <div className="text-zinc-400">Degree</div>
                    <div className="mt-1 text-lg font-semibold text-white">{selectedNode.degree}</div>
                  </div>
                </div>
                <div>
                  <div className="mb-2 text-xs uppercase tracking-[0.2em] text-zinc-400">Related nodes</div>
                  <div className="space-y-2">
                    {relatedConnections.length ? (
                      relatedConnections.map(({ edge, node }) => (
                        <button
                          key={`${edge.source}-${edge.target}`}
                          onClick={() => node && setSelectedId(node.id)}
                          className="w-full rounded-[14px] border border-white/8 bg-white/[0.02] px-3 py-3 text-left transition hover:bg-white/[0.04]"
                        >
                          <div className="text-sm text-white">{node?.label}</div>
                          <div className="mt-1 text-xs text-zinc-400">
                            {edge.relation} | weight {edge.weight} | mentions {node?.mentions ?? 0}
                          </div>
                        </button>
                      ))
                    ) : (
                      <div className="rounded-[14px] border border-white/8 bg-white/[0.02] px-3 py-3 text-sm text-zinc-400">
                        No visible relationships for this selection.
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ) : (
              <div className="text-sm text-zinc-400">Filter returned no nodes.</div>
            )}
          </div>
        </div>
      </div>

      <div className="shell-panel p-5">
        <div className="mb-2 text-sm font-medium text-white">Top connections</div>
        <div className="space-y-2 text-xs text-zinc-300">
          {visibleEdges.slice(0, 12).map((edge, index) => (
            <button
              key={`${edge.source}-${edge.target}-${index}`}
              onClick={() => setSelectedId(edge.source)}
              className="flex w-full items-center justify-between rounded-[14px] border border-white/8 bg-white/[0.02] px-3 py-3 text-left transition hover:bg-white/[0.04]"
            >
              <span className="truncate pr-3">
                {positionedById.get(edge.source)?.label ?? edge.source} {"->"} {positionedById.get(edge.target)?.label ?? edge.target}
              </span>
              <span className="shrink-0 text-zinc-400">
                {edge.relation} | weight {edge.weight}
              </span>
            </button>
          ))}
          {!visibleEdges.length ? (
            <div className="rounded-[14px] border border-white/8 bg-white/[0.02] px-3 py-2 text-zinc-400">
              No connections match the current filters.
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
