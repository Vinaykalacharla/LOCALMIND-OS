"use client";

import { useDeferredValue, useEffect, useMemo, useState } from "react";
import { GraphEdge, GraphNode, GraphNodeType, GraphResponse } from "@/lib/api";
import { formatNumber } from "@/lib/format";

interface GraphViewProps {
  graph: GraphResponse | null;
}

type GraphFilter = "all" | GraphNodeType;
type EdgeDensity = 80 | 140 | 220;

interface PositionedNode extends GraphNode {
  x: number;
  y: number;
  radius: number;
}

interface RelationSummary {
  relation: string;
  count: number;
  totalWeight: number;
}

const GRAPH_WIDTH = 1220;
const GRAPH_HEIGHT = 780;
const EDGE_DENSITY_OPTIONS: EdgeDensity[] = [80, 140, 220];
const EDGE_DENSITY_LABELS: Record<EdgeDensity, string> = {
  80: "Quiet",
  140: "Balanced",
  220: "Dense"
};

const TYPE_ORDER: GraphNodeType[] = ["doc", "project", "topic", "person", "other"];
const TYPE_COLORS: Record<GraphNodeType, string> = {
  doc: "#d5b071",
  person: "#7bd3a7",
  project: "#71c7bb",
  topic: "#7c9fe6",
  other: "#8d96a7"
};

const TYPE_SURFACES: Record<GraphNodeType, string> = {
  doc: "rgba(213, 176, 113, 0.11)",
  person: "rgba(123, 211, 167, 0.11)",
  project: "rgba(113, 199, 187, 0.11)",
  topic: "rgba(124, 159, 230, 0.11)",
  other: "rgba(141, 150, 167, 0.10)"
};

const TYPE_NOTES: Record<GraphNodeType, string> = {
  doc: "source material",
  project: "execution lanes",
  topic: "idea clusters",
  person: "named actors",
  other: "support signals"
};

const TYPE_LABELS: Record<GraphFilter, string> = {
  all: "All",
  doc: "Documents",
  project: "Projects",
  topic: "Topics",
  person: "People",
  other: "Other"
};

const GROUP_ZONES: Record<GraphNodeType, { x: number; y: number; width: number; height: number }> = {
  doc: { x: 80, y: 72, width: 300, height: 248 },
  project: { x: 462, y: 72, width: 300, height: 248 },
  topic: { x: 844, y: 72, width: 300, height: 248 },
  person: { x: 224, y: 432, width: 320, height: 252 },
  other: { x: 676, y: 432, width: 320, height: 252 }
};

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function percent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

function titleCase(value: string): string {
  return value
    .split(/[_\\s-]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function signalScore(node: GraphNode): number {
  return node.degree * 2 + node.mentions;
}

function relationWeightLabel(weight: number): string {
  if (weight >= 4) {
    return "critical";
  }
  if (weight >= 2.5) {
    return "strong";
  }
  if (weight >= 1.5) {
    return "stable";
  }
  return "light";
}

function buildLayout(nodes: GraphNode[]): PositionedNode[] {
  const grouped = new Map<GraphNodeType, GraphNode[]>();
  TYPE_ORDER.forEach((type) => grouped.set(type, []));
  nodes.forEach((node) => {
    grouped.get(node.type)?.push(node);
  });

  const positioned: PositionedNode[] = [];
  TYPE_ORDER.forEach((type, typeIndex) => {
    const zone = GROUP_ZONES[type];
    const centerX = zone.x + zone.width / 2;
    const centerY = zone.y + zone.height / 2;
    const group = (grouped.get(type) ?? []).sort(
      (a, b) => b.degree - a.degree || b.mentions - a.mentions || a.label.localeCompare(b.label)
    );

    group.forEach((node, index) => {
      const radius = clamp(10 + node.mentions * 1.7 + Math.min(node.degree, 10) * 0.45, 11, 24);
      if (index === 0) {
        positioned.push({ ...node, x: centerX, y: centerY, radius });
        return;
      }

      const ring = Math.floor(Math.sqrt(index)) + 1;
      const slots = Math.max(6, ring * 6);
      const positionInRing = (index - 1) % slots;
      const angle = ((positionInRing / slots) * Math.PI * 2) + typeIndex * 0.32;
      const offsetX = Math.cos(angle) * ring * 54 * 1.14;
      const offsetY = Math.sin(angle) * ring * 46;
      positioned.push({
        ...node,
        x: clamp(centerX + offsetX, zone.x + 28, zone.x + zone.width - 28),
        y: clamp(centerY + offsetY, zone.y + 36, zone.y + zone.height - 28),
        radius
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

function edgeControlPoint(source: PositionedNode, target: PositionedNode): { x: number; y: number } {
  const dx = target.x - source.x;
  const dy = target.y - source.y;
  const distance = Math.hypot(dx, dy) || 1;
  const normalX = -dy / distance;
  const normalY = dx / distance;
  const curve = clamp(distance * 0.12, 16, 54) * (source.x < target.x ? 1 : -1);
  return {
    x: (source.x + target.x) / 2 + normalX * curve,
    y: (source.y + target.y) / 2 + normalY * curve
  };
}

function edgePath(source: PositionedNode, target: PositionedNode): string {
  const control = edgeControlPoint(source, target);
  return `M ${source.x} ${source.y} Q ${control.x} ${control.y} ${target.x} ${target.y}`;
}

function edgeLabelPosition(source: PositionedNode, target: PositionedNode): { x: number; y: number } {
  const control = edgeControlPoint(source, target);
  const x = (source.x + 2 * control.x + target.x) / 4;
  const y = (source.y + 2 * control.y + target.y) / 4;
  return { x, y };
}

function summarizeRelations(edges: GraphEdge[]): RelationSummary[] {
  const grouped = new Map<string, RelationSummary>();
  for (const edge of edges) {
    const key = edge.relation || "related";
    const current = grouped.get(key) ?? { relation: key, count: 0, totalWeight: 0 };
    current.count += 1;
    current.totalWeight += edge.weight;
    grouped.set(key, current);
  }
  return Array.from(grouped.values()).sort(
    (a, b) => b.totalWeight - a.totalWeight || b.count - a.count || a.relation.localeCompare(b.relation)
  );
}

export default function GraphView({ graph }: GraphViewProps) {
  const [filter, setFilter] = useState<GraphFilter>("all");
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [focusOnly, setFocusOnly] = useState(false);
  const [edgeDensity, setEdgeDensity] = useState<EdgeDensity>(140);
  const deferredQuery = useDeferredValue(query);

  const filteredNodes = useMemo(() => {
    if (!graph) {
      return [];
    }
    const normalizedQuery = deferredQuery.trim().toLowerCase();
    return graph.nodes.filter((node) => {
      const matchesType = filter === "all" || node.type === filter;
      const matchesQuery = !normalizedQuery || node.label.toLowerCase().includes(normalizedQuery);
      return matchesType && matchesQuery;
    });
  }, [deferredQuery, filter, graph]);

  const filteredNodeIds = useMemo(() => new Set(filteredNodes.map((node) => node.id)), [filteredNodes]);

  const candidateEdges = useMemo(() => {
    if (!graph) {
      return [];
    }
    return graph.edges
      .filter((edge) => filteredNodeIds.has(edge.source) && filteredNodeIds.has(edge.target))
      .sort((a, b) => b.weight - a.weight || a.relation.localeCompare(b.relation));
  }, [filteredNodeIds, graph]);

  useEffect(() => {
    if (!filteredNodes.length) {
      setSelectedId(null);
      return;
    }
    if (!selectedId || !filteredNodes.some((node) => node.id === selectedId)) {
      const topNode = [...filteredNodes].sort((a, b) => b.degree - a.degree || b.mentions - a.mentions)[0];
      setSelectedId(topNode?.id ?? filteredNodes[0].id);
    }
  }, [filteredNodes, selectedId]);

  const focusNodeIds = useMemo(() => {
    if (!focusOnly || !selectedId) {
      return filteredNodeIds;
    }
    const ids = connectedNodeIds(candidateEdges, selectedId);
    ids.add(selectedId);
    return ids;
  }, [candidateEdges, filteredNodeIds, focusOnly, selectedId]);

  const visibleNodes = useMemo(
    () => filteredNodes.filter((node) => focusNodeIds.has(node.id)),
    [filteredNodes, focusNodeIds]
  );
  const visibleNodeIds = useMemo(() => new Set(visibleNodes.map((node) => node.id)), [visibleNodes]);

  const visibleEdges = useMemo(
    () =>
      candidateEdges
        .filter((edge) => visibleNodeIds.has(edge.source) && visibleNodeIds.has(edge.target))
        .slice(0, edgeDensity),
    [candidateEdges, edgeDensity, visibleNodeIds]
  );

  const positionedNodes = useMemo(() => buildLayout(visibleNodes), [visibleNodes]);
  const positionedById = useMemo(() => new Map(positionedNodes.map((node) => [node.id, node])), [positionedNodes]);
  const selectedNode = positionedNodes.find((node) => node.id === selectedId) ?? null;
  const neighborIds = useMemo(() => connectedNodeIds(visibleEdges, selectedId), [selectedId, visibleEdges]);

  const relatedConnections = useMemo(() => {
    if (!selectedNode) {
      return [];
    }
    return visibleEdges
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
        if (weightDiff !== 0) {
          return weightDiff;
        }
        return (b.node?.degree ?? 0) - (a.node?.degree ?? 0);
      })
      .slice(0, 10);
  }, [positionedById, selectedNode, visibleEdges]);

  const visibleTypeCounts = useMemo(
    () =>
      TYPE_ORDER.map((type) => ({
        type,
        total: visibleNodes.filter((node) => node.type === type).length
      })),
    [visibleNodes]
  );
  const totalTypeCounts = useMemo(
    () =>
      TYPE_ORDER.map((type) => ({
        type,
        total: (graph?.nodes ?? []).filter((node) => node.type === type).length
      })),
    [graph]
  );

  const networkDensity = useMemo(() => {
    const possible = (visibleNodes.length * (visibleNodes.length - 1)) / 2;
    if (possible <= 0) {
      return 0;
    }
    return Math.min(1, visibleEdges.length / possible);
  }, [visibleEdges.length, visibleNodes.length]);

  const strongestRelation = useMemo(() => summarizeRelations(visibleEdges)[0] ?? null, [visibleEdges]);
  const topNodes = useMemo(
    () =>
      [...visibleNodes]
        .sort((a, b) => b.degree - a.degree || b.mentions - a.mentions || a.label.localeCompare(b.label))
        .slice(0, 6),
    [visibleNodes]
  );
  const selectedRelationSummary = useMemo(
    () => summarizeRelations(relatedConnections.map(({ edge }) => edge)).slice(0, 4),
    [relatedConnections]
  );
  const relationBreakdown = useMemo(() => summarizeRelations(visibleEdges).slice(0, 6), [visibleEdges]);
  const activeQuery = deferredQuery.trim();
  const visibleCoverage = graph?.nodes.length ? visibleNodes.length / graph.nodes.length : 0;
  const maxVisibleSignal = useMemo(
    () => visibleNodes.reduce((best, node) => Math.max(best, signalScore(node)), 1),
    [visibleNodes]
  );
  const selectedWeightTotal = useMemo(
    () => relatedConnections.reduce((total, { edge }) => total + edge.weight, 0),
    [relatedConnections]
  );

  if (!graph || graph.nodes.length === 0) {
    return (
      <div className="shell-panel p-6 sm:p-8">
        <div className="eyebrow">Knowledge Map</div>
        <div className="mt-3 text-2xl font-semibold text-white">Graph will appear after ingestion.</div>
        <div className="mt-3 max-w-2xl text-sm leading-7 text-zinc-400">
          Upload documents first, then LocalMind will build entity links, topic clusters, and relation lanes for this view.
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <div className="shell-panel overflow-hidden p-0">
        <div className="relative">
          <div className="pointer-events-none absolute inset-0 overflow-hidden">
            <div className="absolute left-10 top-6 h-40 w-40 rounded-full bg-sky-400/10 blur-3xl" />
            <div className="absolute right-0 top-0 h-48 w-64 rounded-full bg-emerald-300/8 blur-3xl" />
            <div className="absolute bottom-0 left-1/3 h-40 w-72 rounded-full bg-amber-300/8 blur-3xl" />
          </div>

          <div className="relative grid gap-5 border-b border-white/8 px-5 py-6 sm:px-6 xl:grid-cols-[minmax(0,1fr)_420px]">
            <div>
              <div className="eyebrow">Graph Studio</div>
              <div className="mt-2 max-w-4xl text-3xl font-semibold leading-tight text-white sm:text-[2.95rem]">
                A cleaner graph console with stronger focus, better hierarchy, and a more premium desktop feel.
              </div>
              <div className="mt-3 max-w-3xl text-sm leading-7 text-zinc-400">
                Search entities, isolate a neighborhood, and inspect the dominant relation lanes from one surface without the
                graph feeling like a debug screen.
              </div>
              <div className="mt-5 flex flex-wrap gap-2">
                <div className="status-pill">{focusOnly ? "Focused neighborhood" : "Full constellation"}</div>
                <div className="tag">Filter {TYPE_LABELS[filter]}</div>
                <div className="tag">Density {EDGE_DENSITY_LABELS[edgeDensity]}</div>
                <div className="tag">{activeQuery ? `Query ${activeQuery}` : "Query all nodes"}</div>
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <div className="rounded-[22px] border border-white/10 bg-white/[0.04] p-4 backdrop-blur">
                <div className="text-[11px] uppercase tracking-[0.24em] text-zinc-500">Visible nodes</div>
                <div className="mt-3 text-3xl font-display font-semibold text-white">{formatNumber(visibleNodes.length)}</div>
                <div className="mt-2 text-xs text-zinc-400">{percent(visibleCoverage)} of the graph is currently in frame.</div>
              </div>
              <div className="rounded-[22px] border border-white/10 bg-white/[0.04] p-4 backdrop-blur">
                <div className="text-[11px] uppercase tracking-[0.24em] text-zinc-500">Relation density</div>
                <div className="mt-3 text-3xl font-display font-semibold text-white">{percent(networkDensity)}</div>
                <div className="mt-2 text-xs text-zinc-400">{formatNumber(visibleEdges.length)} weighted lanes are active.</div>
              </div>
              <div className="rounded-[22px] border border-white/10 bg-white/[0.04] p-4 backdrop-blur">
                <div className="text-[11px] uppercase tracking-[0.24em] text-zinc-500">Pinned node</div>
                <div className="mt-3 truncate text-lg font-semibold text-white">{selectedNode?.label ?? "Auto selected"}</div>
                <div className="mt-2 text-xs text-zinc-400">
                  {selectedNode ? `${TYPE_LABELS[selectedNode.type]} with ${relatedConnections.length} visible neighbors.` : "Selection follows the strongest visible node."}
                </div>
              </div>
              <div className="rounded-[22px] border border-white/10 bg-white/[0.04] p-4 backdrop-blur">
                <div className="text-[11px] uppercase tracking-[0.24em] text-zinc-500">Dominant lane</div>
                <div className="mt-3 text-lg font-semibold text-white">
                  {strongestRelation ? titleCase(strongestRelation.relation) : "No visible relation"}
                </div>
                <div className="mt-2 text-xs text-zinc-400">
                  {strongestRelation ? `${strongestRelation.count} links | weight ${strongestRelation.totalWeight}` : "Increase scope or edge load to expose lanes."}
                </div>
              </div>
            </div>
          </div>

          <div className="relative px-5 py-4 sm:px-6">
            <div className="grid gap-4 rounded-[28px] border border-white/8 bg-white/[0.03] p-4 xl:grid-cols-[minmax(0,1.18fr)_minmax(0,0.92fr)]">
              <div className="space-y-3">
                <div className="text-sm font-medium text-white">Search and focus</div>
                <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
                  <input
                    value={query}
                    onChange={(event) => setQuery(event.target.value)}
                    placeholder="Search graph labels, entities, or clusters..."
                    className="input-shell min-w-[220px] flex-1"
                  />
                  {query ? (
                    <button onClick={() => setQuery("")} className="btn-secondary">
                      Clear query
                    </button>
                  ) : null}
                  <button
                    onClick={() => setFocusOnly((value) => !value)}
                    className={`rounded-full border px-4 py-2 text-xs uppercase tracking-[0.18em] transition ${
                      focusOnly
                        ? "border-sky-300/30 bg-sky-300/12 text-white"
                        : "border-white/10 bg-white/[0.03] text-zinc-300 hover:bg-white/[0.06]"
                    }`}
                  >
                    {focusOnly ? "Focus neighborhood" : "Show full scope"}
                  </button>
                </div>
                <div className="text-xs leading-6 text-zinc-400">
                  Spotlight search narrows the graph instantly. Focus mode keeps only the selected node and its direct visible
                  connections on stage.
                </div>
              </div>

              <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_auto]">
                <div>
                  <div className="mb-2 text-xs uppercase tracking-[0.18em] text-zinc-500">Node filter</div>
                  <div className="flex flex-wrap gap-2">
                    {(["all", ...TYPE_ORDER] as GraphFilter[]).map((type) => {
                      const total =
                        type === "all"
                          ? graph.nodes.length
                          : totalTypeCounts.find((item) => item.type === type)?.total ?? 0;
                      return (
                        <button
                          key={type}
                          onClick={() => setFilter(type)}
                          className={`rounded-full border px-3 py-1.5 text-xs transition ${
                            filter === type
                              ? "border-white/18 bg-white/[0.12] text-white"
                              : "border-white/10 text-zinc-300 hover:bg-white/[0.07]"
                          }`}
                        >
                          {TYPE_LABELS[type]} {formatNumber(total)}
                        </button>
                      );
                    })}
                  </div>
                </div>
                <div>
                  <div className="mb-2 text-xs uppercase tracking-[0.18em] text-zinc-500">Edge load</div>
                  <div className="flex flex-wrap gap-2">
                    {EDGE_DENSITY_OPTIONS.map((option) => (
                      <button
                        key={option}
                        onClick={() => setEdgeDensity(option)}
                        className={`rounded-full border px-3 py-1.5 text-xs transition ${
                          edgeDensity === option
                            ? "border-white/18 bg-white/[0.12] text-white"
                            : "border-white/10 text-zinc-300 hover:bg-white/[0.07]"
                        }`}
                      >
                        {EDGE_DENSITY_LABELS[option]} {option}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.08fr)_380px]">
        <div className="shell-panel overflow-hidden p-0">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/8 bg-white/[0.02] px-5 py-4">
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <span className="h-3 w-3 rounded-full bg-[#ff5f57]" />
                <span className="h-3 w-3 rounded-full bg-[#febc2e]" />
                <span className="h-3 w-3 rounded-full bg-[#28c840]" />
              </div>
              <div>
                <div className="text-sm font-medium text-white">Knowledge Stage</div>
                <div className="text-xs text-zinc-400">Desktop-style canvas for relation scanning and cluster inspection.</div>
              </div>
            </div>

            <div className="flex flex-wrap gap-2">
              {visibleTypeCounts.map(({ type, total }) => (
                <div
                  key={type}
                  className="rounded-full border border-white/8 px-3 py-1.5 text-xs text-zinc-300"
                  style={{ background: TYPE_SURFACES[type] }}
                >
                  <span className="font-medium text-white">{TYPE_LABELS[type]}</span> {formatNumber(total)}
                </div>
              ))}
            </div>
          </div>

          <div className="p-4">
            <div className="relative overflow-hidden rounded-[30px] border border-white/8 bg-[#050c15] shadow-[inset_0_1px_0_rgba(255,255,255,0.05)]">
              <div className="pointer-events-none absolute inset-0">
                <div className="absolute left-[10%] top-[10%] h-48 w-48 rounded-full bg-sky-400/12 blur-3xl" />
                <div className="absolute right-[12%] top-[18%] h-44 w-44 rounded-full bg-emerald-300/10 blur-3xl" />
                <div className="absolute bottom-[8%] left-[42%] h-52 w-52 rounded-full bg-amber-300/8 blur-3xl" />
              </div>

              <div className="pointer-events-none absolute left-4 top-4 z-10 flex flex-wrap gap-2">
                <div className="rounded-full border border-white/10 bg-black/30 px-3 py-1.5 text-[11px] uppercase tracking-[0.18em] text-zinc-300 backdrop-blur">
                  {selectedNode ? `${selectedNode.label} pinned` : "Auto-selection active"}
                </div>
                <div className="rounded-full border border-white/10 bg-black/30 px-3 py-1.5 text-[11px] uppercase tracking-[0.18em] text-zinc-400 backdrop-blur">
                  {formatNumber(visibleNodes.length)} nodes | {formatNumber(visibleEdges.length)} lanes
                </div>
              </div>

              <div className="pointer-events-none absolute bottom-4 left-4 right-4 z-10 flex flex-wrap items-center justify-between gap-3">
                <div className="flex flex-wrap gap-2">
                  {TYPE_ORDER.map((type) => (
                    <div
                      key={type}
                      className="rounded-full border border-white/10 bg-black/30 px-3 py-1.5 text-[11px] uppercase tracking-[0.16em] text-zinc-300 backdrop-blur"
                    >
                      <span className="mr-2 inline-block h-2.5 w-2.5 rounded-full align-middle" style={{ backgroundColor: TYPE_COLORS[type] }} />
                      {TYPE_LABELS[type]}
                    </div>
                  ))}
                </div>
                <div className="rounded-full border border-white/10 bg-black/30 px-3 py-1.5 text-[11px] uppercase tracking-[0.16em] text-zinc-400 backdrop-blur">
                  Click a node to pin the inspector.
                </div>
              </div>

              <div className="overflow-auto p-3">
                <svg viewBox={`0 0 ${GRAPH_WIDTH} ${GRAPH_HEIGHT}`} className="h-[760px] w-full min-w-[980px]">
              <defs>
                <linearGradient id="graphBackground" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stopColor="#050b14" />
                  <stop offset="42%" stopColor="#091626" />
                  <stop offset="100%" stopColor="#08111d" />
                </linearGradient>
                <linearGradient id="graphOverlay" x1="0%" y1="0%" x2="0%" y2="100%">
                  <stop offset="0%" stopColor="rgba(255,255,255,0.05)" />
                  <stop offset="100%" stopColor="rgba(255,255,255,0)" />
                </linearGradient>
                <filter id="nodeGlow">
                  <feGaussianBlur stdDeviation="8" result="blur" />
                  <feMerge>
                    <feMergeNode in="blur" />
                    <feMergeNode in="SourceGraphic" />
                  </feMerge>
                </filter>
                <filter id="labelShadow">
                  <feDropShadow dx="0" dy="5" stdDeviation="8" floodColor="rgba(3,8,15,0.55)" />
                </filter>
                <pattern id="graphGrid" width="32" height="32" patternUnits="userSpaceOnUse">
                  <path d="M 32 0 L 0 0 0 32" fill="none" stroke="rgba(148,163,184,0.08)" strokeWidth="1" />
                </pattern>
              </defs>

              <rect x={0} y={0} width={GRAPH_WIDTH} height={GRAPH_HEIGHT} rx={26} fill="url(#graphBackground)" />
              <rect x={0} y={0} width={GRAPH_WIDTH} height={GRAPH_HEIGHT} rx={26} fill="url(#graphGrid)" opacity="0.46" />
              <rect x={0} y={0} width={GRAPH_WIDTH} height={GRAPH_HEIGHT} rx={26} fill="url(#graphOverlay)" opacity="0.48" />
              <circle cx={180} cy={120} r={220} fill="rgba(124,159,230,0.10)" />
              <circle cx={1060} cy={170} r={220} fill="rgba(123,211,167,0.08)" />
              <circle cx={610} cy={680} r={260} fill="rgba(213,176,113,0.06)" />

              {TYPE_ORDER.map((type) => {
                const zone = GROUP_ZONES[type];
                const count = visibleTypeCounts.find((item) => item.type === type)?.total ?? 0;
                return (
                  <g key={type}>
                    <rect
                      x={zone.x}
                      y={zone.y}
                      width={zone.width}
                      height={zone.height}
                      rx={36}
                      fill={TYPE_SURFACES[type]}
                      stroke="rgba(255,255,255,0.08)"
                      strokeDasharray="8 12"
                    />
                    <rect
                      x={zone.x + 10}
                      y={zone.y + 10}
                      width={zone.width - 20}
                      height={zone.height - 20}
                      rx={28}
                      fill="none"
                      stroke="rgba(255,255,255,0.03)"
                    />
                    <text x={zone.x + 24} y={zone.y + 32} fill="#f8fafc" fontSize="14" fontWeight="700">
                      {TYPE_LABELS[type]}
                    </text>
                    <text x={zone.x + 24} y={zone.y + 52} fill="#7f8da3" fontSize="11">
                      {TYPE_NOTES[type]}
                    </text>
                    <text x={zone.x + zone.width - 24} y={zone.y + 32} textAnchor="end" fill="#8ea0b7" fontSize="12">
                      {formatNumber(count)}
                    </text>
                  </g>
                );
              })}

              {selectedNode ? (
                <>
                  <circle
                    cx={selectedNode.x}
                    cy={selectedNode.y}
                    r={selectedNode.radius + 20}
                    fill="none"
                    stroke="rgba(255,255,255,0.10)"
                    strokeWidth="1.4"
                  />
                  <circle
                    cx={selectedNode.x}
                    cy={selectedNode.y}
                    r={selectedNode.radius + 30}
                    fill="none"
                    stroke="rgba(255,255,255,0.07)"
                    strokeWidth="1.6"
                    strokeDasharray="8 10"
                  />
                </>
              ) : null}

              {visibleEdges.map((edge, index) => {
                const source = positionedById.get(edge.source);
                const target = positionedById.get(edge.target);
                if (!source || !target) {
                  return null;
                }
                const relationState = statusForRelation(edge, selectedId);
                const labelPoint = edgeLabelPosition(source, target);
                const path = edgePath(source, target);
                const stroke =
                  relationState === "selected"
                    ? "rgba(123, 211, 167, 0.96)"
                    : relationState === "muted"
                      ? "rgba(71, 85, 105, 0.24)"
                      : "rgba(125, 146, 173, 0.48)";
                const opacity = relationState === "muted" ? 0.32 : Math.min(0.95, 0.24 + edge.weight * 0.12);
                const labelWidth = Math.max(92, edge.relation.length * 7 + 30);
                return (
                  <g key={`${edge.source}_${edge.target}_${index}`}>
                    <path
                      d={path}
                      fill="none"
                      stroke={stroke}
                      strokeWidth={relationState === "selected" ? 3 : 1 + edge.weight * 0.4}
                      opacity={opacity}
                    />
                    {relationState === "selected" ? (
                      <g transform={`translate(${labelPoint.x - labelWidth / 2} ${labelPoint.y - 15})`} pointerEvents="none">
                        <rect
                          width={labelWidth}
                          height={30}
                          rx={15}
                          fill="rgba(5, 10, 18, 0.88)"
                          stroke="rgba(255,255,255,0.10)"
                          filter="url(#labelShadow)"
                        />
                        <text x={labelWidth / 2} y={13} textAnchor="middle" fill="#d8f5ea" fontSize="10" fontWeight="700">
                          {titleCase(edge.relation)}
                        </text>
                        <text x={labelWidth / 2} y={23} textAnchor="middle" fill="#7bd3a7" fontSize="9">
                          weight {edge.weight}
                        </text>
                      </g>
                    ) : null}
                  </g>
                );
              })}

              {positionedNodes.map((node) => {
                const selected = node.id === selectedId;
                const connected = neighborIds.has(node.id);
                const faded = !!selectedId && !selected && !connected;
                const showLabel = selected || connected || node.degree >= 3 || positionedNodes.length <= 18;
                const labelWidth = Math.min(144, Math.max(66, node.label.length * 6.1));
                const nodeSignal = signalScore(node);
                return (
                  <g
                    key={node.id}
                    onClick={() => setSelectedId(node.id)}
                    style={{ cursor: "pointer", opacity: faded ? 0.28 : 1 }}
                  >
                    <title>{`${node.label} | ${TYPE_LABELS[node.type]} | degree ${node.degree} | mentions ${node.mentions}`}</title>
                    <circle
                      cx={node.x}
                      cy={node.y}
                      r={selected ? node.radius + 14 : connected ? node.radius + 8 : node.radius + 5}
                      fill={selected ? `${TYPE_COLORS[node.type]}22` : `${TYPE_COLORS[node.type]}14`}
                      filter="url(#nodeGlow)"
                    />
                    <circle
                      cx={node.x}
                      cy={node.y}
                      r={node.radius}
                      fill={TYPE_COLORS[node.type]}
                      stroke={selected ? "#f8fafc" : connected ? "rgba(255,255,255,0.45)" : "rgba(255,255,255,0.20)"}
                      strokeWidth={selected ? 2.8 : connected ? 1.6 : 1}
                    />
                    <circle cx={node.x} cy={node.y} r={Math.max(4, node.radius - 6)} fill="rgba(4, 10, 18, 0.2)" />
                    <text x={node.x} y={node.y + 4} textAnchor="middle" fill="#f8fafc" fontSize="10" fontWeight="700">
                      {node.degree}
                    </text>
                    {showLabel ? (
                      <g transform={`translate(${node.x} ${node.y + node.radius + 18})`}>
                        <rect
                          x={-labelWidth / 2}
                          y={-14}
                          width={labelWidth}
                          height={28}
                          rx={14}
                          fill={selected ? "rgba(10, 18, 30, 0.94)" : "rgba(8, 15, 25, 0.78)"}
                          stroke={selected ? "rgba(255,255,255,0.16)" : "rgba(255,255,255,0.06)"}
                          filter="url(#labelShadow)"
                        />
                        <text x={0} y={-1} textAnchor="middle" fill={selected ? "#f8fafc" : "#d7deea"} fontSize="11" fontWeight="600">
                          {node.label.slice(0, 22)}
                        </text>
                        <text x={0} y={9} textAnchor="middle" fill="#7f8da3" fontSize="9">
                          signal {nodeSignal}
                        </text>
                      </g>
                    ) : null}
                  </g>
                );
              })}
                </svg>
              </div>
            </div>
          </div>
        </div>

        <div className="space-y-5">
          <div className="shell-panel-soft overflow-hidden p-0">
            <div className="border-b border-white/8 bg-white/[0.02] px-4 py-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-sm font-medium text-white">Node inspector</div>
                  <div className="mt-1 text-xs text-zinc-400">Pinned context, signal, and strongest local relationships.</div>
                </div>
                <div className="rounded-full border border-white/10 px-3 py-1 text-[11px] uppercase tracking-[0.18em] text-zinc-400">
                  {selectedNode ? TYPE_LABELS[selectedNode.type] : "No selection"}
                </div>
              </div>
            </div>

            <div className="p-4">
              {selectedNode ? (
                <div className="space-y-4">
                <div className="rounded-[24px] border border-white/10 bg-[radial-gradient(circle_at_top,rgba(119,167,255,0.12),rgba(255,255,255,0.02))] p-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="tag" style={{ background: TYPE_SURFACES[selectedNode.type], borderColor: `${TYPE_COLORS[selectedNode.type]}35` }}>
                      {TYPE_LABELS[selectedNode.type]}
                    </span>
                    <span className="tag">Signal {signalScore(selectedNode)}</span>
                  </div>
                  <div className="mt-4 text-2xl font-semibold text-white">{selectedNode.label}</div>
                  <div className="mt-2 text-sm leading-7 text-zinc-400">
                    Degree {selectedNode.degree} with {selectedNode.mentions} mentions across the current visible knowledge map.
                  </div>
                  <div className="mt-4 grid grid-cols-3 gap-2 text-xs">
                    <div className="rounded-[18px] border border-white/10 bg-white/[0.04] p-3">
                      <div className="text-zinc-400">Neighbors</div>
                      <div className="mt-1 text-lg font-semibold text-white">{relatedConnections.length}</div>
                    </div>
                    <div className="rounded-[18px] border border-white/10 bg-white/[0.04] p-3">
                      <div className="text-zinc-400">Mentions</div>
                      <div className="mt-1 text-lg font-semibold text-white">{selectedNode.mentions}</div>
                    </div>
                    <div className="rounded-[18px] border border-white/10 bg-white/[0.04] p-3">
                      <div className="text-zinc-400">Lane weight</div>
                      <div className="mt-1 text-lg font-semibold text-white">{selectedWeightTotal.toFixed(1)}</div>
                    </div>
                  </div>
                </div>

                <div>
                  <div className="mb-2 text-xs uppercase tracking-[0.18em] text-zinc-500">Relation mix</div>
                  <div className="space-y-2">
                    {selectedRelationSummary.length ? (
                      selectedRelationSummary.map((item) => (
                        <div key={item.relation} className="rounded-[18px] border border-white/8 bg-white/[0.03] p-3">
                          <div className="flex items-center justify-between gap-3 text-sm text-white">
                            <span>{titleCase(item.relation)}</span>
                            <span className="text-zinc-400">{item.count} lanes</span>
                          </div>
                          <div className="mt-2 h-1.5 rounded-full bg-white/[0.05]">
                            <div
                              className="h-full rounded-full"
                              style={{
                                width: percent(Math.min(1, item.totalWeight / Math.max(1, selectedWeightTotal))),
                                backgroundColor: TYPE_COLORS[selectedNode.type]
                              }}
                            />
                          </div>
                          <div className="mt-2 text-xs text-zinc-400">Weight {item.totalWeight.toFixed(1)}</div>
                        </div>
                      ))
                    ) : (
                      <div className="rounded-[18px] border border-white/8 bg-white/[0.03] px-3 py-3 text-sm text-zinc-400">
                        No visible relation mix for this node.
                      </div>
                    )}
                  </div>
                </div>

                <div>
                  <div className="mb-2 text-xs uppercase tracking-[0.18em] text-zinc-500">Strongest neighbors</div>
                  <div className="space-y-2">
                    {relatedConnections.length ? (
                      relatedConnections.map(({ edge, node }) => (
                        <button
                          key={`${edge.source}-${edge.target}`}
                          onClick={() => node && setSelectedId(node.id)}
                          className="w-full rounded-[18px] border border-white/8 bg-white/[0.03] px-3 py-3 text-left transition hover:bg-white/[0.05]"
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0">
                              <div className="truncate text-sm font-medium text-white">{node?.label}</div>
                              <div className="mt-1 text-xs text-zinc-400">
                                {titleCase(edge.relation)} | degree {node?.degree ?? 0} | mentions {node?.mentions ?? 0}
                              </div>
                            </div>
                            <div className="shrink-0 rounded-full border border-white/10 px-2.5 py-1 text-[11px] uppercase tracking-[0.14em] text-zinc-300">
                              {relationWeightLabel(edge.weight)}
                            </div>
                          </div>
                        </button>
                      ))
                    ) : (
                      <div className="rounded-[18px] border border-white/8 bg-white/[0.03] px-3 py-3 text-sm text-zinc-400">
                        No visible relationships for this selection.
                      </div>
                    )}
                  </div>
                </div>
                </div>
              ) : (
                <div className="text-sm text-zinc-400">Filter returned no visible nodes.</div>
              )}
            </div>
          </div>

          <div className="shell-panel-soft overflow-hidden p-0">
            <div className="border-b border-white/8 bg-white/[0.02] px-4 py-4">
              <div className="text-sm font-medium text-white">Network pulse</div>
              <div className="mt-1 text-xs text-zinc-400">The highest-signal nodes in the current viewport.</div>
            </div>

            <div className="p-4">
              <div className="space-y-3">
                {topNodes.map((node, index) => {
                  const score = signalScore(node);
                  return (
                    <button
                      key={node.id}
                      onClick={() => setSelectedId(node.id)}
                      className="w-full rounded-[18px] border border-white/8 bg-white/[0.03] px-3 py-3 text-left transition hover:bg-white/[0.05]"
                    >
                      <div className="flex items-center justify-between gap-3">
                        <div className="min-w-0">
                          <div className="truncate text-sm font-medium text-white">
                            {index + 1}. {node.label}
                          </div>
                          <div className="mt-1 text-xs text-zinc-400">
                            {TYPE_LABELS[node.type]} | score {score} | degree {node.degree}
                          </div>
                        </div>
                        <div className="shrink-0 text-xs text-zinc-400">{percent(score / maxVisibleSignal)}</div>
                      </div>
                      <div className="mt-3 h-1.5 rounded-full bg-white/[0.05]">
                        <div
                          className="h-full rounded-full"
                          style={{
                            width: percent(score / maxVisibleSignal),
                            backgroundColor: TYPE_COLORS[node.type]
                          }}
                        />
                      </div>
                    </button>
                  );
                })}
                {!topNodes.length ? (
                  <div className="rounded-[18px] border border-white/8 bg-white/[0.03] px-3 py-3 text-sm text-zinc-400">
                    No ranked nodes match the current filters.
                  </div>
                ) : null}
              </div>
            </div>
          </div>
        </div>
      </div>
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,0.92fr)]">
        <div className="shell-panel overflow-hidden p-0">
          <div className="border-b border-white/8 bg-white/[0.02] px-5 py-4">
            <div className="text-sm font-medium text-white">Connection ledger</div>
            <div className="mt-1 text-xs text-zinc-400">The heaviest visible relation lanes in the current viewport.</div>
          </div>

          <div className="p-5">
            <div className="space-y-2">
            {visibleEdges.slice(0, 12).map((edge, index) => {
              const source = positionedById.get(edge.source);
              const target = positionedById.get(edge.target);
              return (
                <button
                  key={`${edge.source}-${edge.target}-${index}`}
                  onClick={() => setSelectedId(edge.source)}
                  className="flex w-full items-center justify-between gap-3 rounded-[18px] border border-white/8 bg-white/[0.03] px-3 py-3 text-left transition hover:bg-white/[0.05]"
                >
                  <div className="min-w-0">
                    <div className="truncate text-sm text-white">
                      {source?.label ?? edge.source} {"->"} {target?.label ?? edge.target}
                    </div>
                    <div className="mt-1 text-xs text-zinc-400">
                      {titleCase(edge.relation)} | {relationWeightLabel(edge.weight)}
                    </div>
                  </div>
                  <div className="shrink-0 rounded-full border border-white/10 px-2.5 py-1 text-[11px] text-zinc-300">
                    weight {edge.weight}
                  </div>
                </button>
              );
            })}
            {!visibleEdges.length ? (
              <div className="rounded-[18px] border border-white/8 bg-white/[0.03] px-3 py-3 text-sm text-zinc-400">
                No connections match the current filters.
              </div>
            ) : null}
            </div>
          </div>
        </div>

        <div className="shell-panel overflow-hidden p-0">
          <div className="border-b border-white/8 bg-white/[0.02] px-5 py-4">
            <div className="text-sm font-medium text-white">Relation spectrum</div>
            <div className="mt-1 text-xs text-zinc-400">A weighted breakdown of the active relation families.</div>
          </div>

          <div className="p-5">
            <div className="space-y-3">
            {relationBreakdown.map((item) => {
              const strongestWeight = Math.max(1, strongestRelation?.totalWeight ?? 1);
              return (
                <div key={item.relation} className="rounded-[18px] border border-white/8 bg-white/[0.03] p-3">
                  <div className="flex items-center justify-between text-sm text-white">
                    <span>{titleCase(item.relation)}</span>
                    <span className="text-zinc-400">{item.count} links</span>
                  </div>
                  <div className="mt-2 h-1.5 rounded-full bg-white/[0.05]">
                    <div
                      className="h-full rounded-full bg-white/75"
                      style={{ width: percent(Math.min(1, item.totalWeight / strongestWeight)) }}
                    />
                  </div>
                  <div className="mt-2 text-xs text-zinc-400">Total weight {item.totalWeight}</div>
                </div>
              );
            })}
            {!visibleEdges.length ? (
              <div className="rounded-[18px] border border-white/8 bg-white/[0.03] px-3 py-3 text-sm text-zinc-400">
                Relation summaries will appear when the current scope has visible edges.
              </div>
            ) : null}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
