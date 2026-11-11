import { useEffect, useMemo, useRef, useState } from "react";
import {
  Building2,
  FileText,
  Flag,
  Layers,
  Minus,
  Plus,
  RotateCcw,
  TriangleAlert,
  X,
} from "lucide-react";
import type { GraphEdge, GraphNode, GraphNodeType, KnowledgeGraph } from "../types";

interface EvidenceKnowledgeGraphProps {
  graph: KnowledgeGraph;
  /** Optional callback when an evidence node is opened. */
  onOpenEvidence?: (evidenceId: string) => void;
  height?: number;
}

const TYPE_ORDER: GraphNodeType[] = [
  "technology",
  "document",
  "milestone",
  "category",
  "evidence",
  "contradiction",
];

const TYPE_META: Record<
  GraphNodeType,
  { label: string; color: string; stroke: string; title: string }
> = {
  technology: {
    label: "Technology",
    color: "#0f766e",
    stroke: "#ccfbf1",
    title: "Assessed technology",
  },
  document: {
    label: "Document",
    color: "#2563eb",
    stroke: "#dbeafe",
    title: "Source document",
  },
  milestone: {
    label: "Milestone",
    color: "#6366f1",
    stroke: "#e0e7ff",
    title: "TRL milestone",
  },
  category: {
    label: "Category",
    color: "#0891b2",
    stroke: "#cffafe",
    title: "Evidence category",
  },
  evidence: {
    label: "Evidence",
    color: "#0d9488",
    stroke: "#ccfbf1",
    title: "Evidence excerpt",
  },
  contradiction: {
    label: "Contradiction",
    color: "#e11d48",
    stroke: "#ffe4e6",
    title: "Detected conflict",
  },
};

const STATUS_COLOR: Record<string, string> = {
  confirmed: "#059669",
  proposed: "#2563eb",
  contradicted: "#e11d48",
  unclear: "#d97706",
  not_found: "#94a3b8",
};

const VIEW_W = 1840;
const VIEW_H = 1000;

function evidenceColor(node: GraphNode): string {
  if (node.type === "contradiction") return TYPE_META.contradiction.color;
  if (node.status && STATUS_COLOR[node.status]) return STATUS_COLOR[node.status];
  return TYPE_META[node.type].color;
}

function layout(nodes: GraphNode[]): Record<string, { x: number; y: number }> {
  const positions: Record<string, { x: number; y: number }> = {};
  const byType = new Map<GraphNodeType, GraphNode[]>();
  nodes.forEach((node) => {
    const list = byType.get(node.type) ?? [];
    list.push(node);
    byType.set(node.type, list);
  });

  const xByType: Record<GraphNodeType, number | number[]> = {
    technology: VIEW_W * 0.07,
    document: VIEW_W * 0.19,
    milestone: VIEW_W * 0.34,
    category: VIEW_W * 0.48,
    evidence: [VIEW_W * 0.6, VIEW_W * 0.735, VIEW_W * 0.865],
    contradiction: VIEW_W * 0.95,
  };

  (Object.keys(xByType) as GraphNodeType[]).forEach((type) => {
    const list = byType.get(type) ?? [];
    if (list.length === 0) return;
    const xs = xByType[type];
    if (type === "evidence") {
      const columns = xs as number[];
      const perColumn = Math.max(1, Math.ceil(list.length / columns.length));
      const gap = Math.min(20, (VIEW_H - 120) / Math.max(1, perColumn - 1));
      list.forEach((node, index) => {
        const col = Math.min(columns.length - 1, Math.floor(index / perColumn));
        const row = index % perColumn;
        positions[node.id] = {
          x: columns[col],
          y: 70 + row * gap,
        };
      });
      return;
    }
    const yGap = (VIEW_H - 140) / Math.max(1, list.length - 1);
    list.forEach((node, index) => {
      positions[node.id] = {
        x: xs as number,
        y: list.length === 1 ? VIEW_H / 2 : 70 + index * yGap,
      };
    });
  });

  return positions;
}

function nodeRadius(node: GraphNode): number {
  switch (node.type) {
    case "technology":
      return 30;
    case "document":
      return 12;
    case "milestone":
      return 11;
    case "category":
      return 9;
    case "contradiction":
      return 11;
    default:
      return 4.5 + Math.min(4, (node.weight ?? 1) * 4);
  }
}

function shortLabel(node: GraphNode): string {
  const label = node.label || node.id;
  if (node.type === "milestone") return label.replace(/^TRL\s*(\d+):\s*/, "T$1 · ").slice(0, 34);
  return label.length > 38 ? `${label.slice(0, 37)}…` : label;
}

/**
 * Interactive evidence graph rendered with SVG. Supports pan, zoom, node
 * dragging, type filters and a details panel. Edges are the backend's real
 * relationships; nothing is connected for visual effect.
 */
export default function EvidenceKnowledgeGraph({
  graph,
  onOpenEvidence,
  height = 560,
}: EvidenceKnowledgeGraphProps) {
  const [positions, setPositions] = useState<Record<string, { x: number; y: number }>>(
    () => layout(graph.nodes),
  );
  const [visibleTypes, setVisibleTypes] = useState<Set<GraphNodeType>>(
    () => new Set(TYPE_ORDER),
  );
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [draggingNode, setDraggingNode] = useState<string | null>(null);
  const [panning, setPanning] = useState(false);
  const svgRef = useRef<SVGSVGElement | null>(null);
  const lastPoint = useRef({ x: 0, y: 0 });

  useEffect(() => {
    setPositions(layout(graph.nodes));
    setSelectedId(null);
    setZoom(1);
    setPan({ x: 0, y: 0 });
  }, [graph]);

  const nodeMap = useMemo(() => {
    const map = new Map<string, GraphNode>();
    graph.nodes.forEach((n) => map.set(n.id, n));
    return map;
  }, [graph.nodes]);

  const counts = useMemo(() => {
    const out = {} as Record<GraphNodeType, number>;
    TYPE_ORDER.forEach((t) => (out[t] = 0));
    graph.nodes.forEach((n) => (out[n.type] = (out[n.type] ?? 0) + 1));
    return out;
  }, [graph.nodes]);

  const visibleNodes = graph.nodes.filter((n) => visibleTypes.has(n.type));
  const visibleIds = new Set(visibleNodes.map((n) => n.id));
  const visibleEdges = graph.edges.filter(
    (e) => visibleIds.has(e.source) && visibleIds.has(e.target),
  );
  const selected = selectedId ? nodeMap.get(selectedId) ?? null : null;
  const connected = selected
    ? graph.edges
        .filter((e) => e.source === selected.id || e.target === selected.id)
        .map((edge: GraphEdge) => ({
          edge,
          other: nodeMap.get(edge.source === selected.id ? edge.target : edge.source),
        }))
        .filter((entry) => entry.other)
    : [];

  const toGraphDelta = (dx: number, dy: number) => {
    const rect = svgRef.current?.getBoundingClientRect();
    if (!rect || rect.width === 0) return { dx: 0, dy: 0 };
    return { dx: (dx * VIEW_W) / rect.width, dy: (dy * VIEW_H) / rect.height };
  };

  const handlePointerDown = (e: React.PointerEvent<SVGSVGElement>) => {
    if (e.button !== 0) return;
    setPanning(true);
    lastPoint.current = { x: e.clientX, y: e.clientY };
    (e.currentTarget as SVGSVGElement).setPointerCapture(e.pointerId);
  };

  const handlePointerMove = (e: React.PointerEvent<SVGSVGElement>) => {
    if (!panning && !draggingNode) return;
    const delta = toGraphDelta(
      e.clientX - lastPoint.current.x,
      e.clientY - lastPoint.current.y,
    );
    lastPoint.current = { x: e.clientX, y: e.clientY };
    if (draggingNode) {
      setPositions((prev) => {
        const current = prev[draggingNode] ?? { x: 0, y: 0 };
        return {
          ...prev,
          [draggingNode]: { x: current.x + delta.dx, y: current.y + delta.dy },
        };
      });
    } else if (panning) {
      setPan((prev) => ({ x: prev.x + delta.dx, y: prev.y + delta.dy }));
    }
  };

  const endPointer = () => {
    setPanning(false);
    setDraggingNode(null);
  };

  const toggleType = (type: GraphNodeType) => {
    setVisibleTypes((prev) => {
      const next = new Set(prev);
      if (next.has(type)) next.delete(type);
      else next.add(type);
      return next;
    });
  };

  const resetView = () => {
    setPositions(layout(graph.nodes));
    setZoom(1);
    setPan({ x: 0, y: 0 });
  };

  if (graph.nodes.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-line bg-panel/70 px-4 py-6 text-sm text-muted">
        This assessment produced no graph nodes.
      </div>
    );
  }

  return (
    <div>
      <div className="flex flex-wrap items-center gap-1.5">
        {TYPE_ORDER.map((type) => {
          const meta = TYPE_META[type];
          const on = visibleTypes.has(type);
          return (
            <button
              key={type}
              type="button"
              onClick={() => toggleType(type)}
              aria-pressed={on}
              className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-semibold transition-colors ${
                on
                  ? "border-line-strong bg-white text-ink shadow-sm"
                  : "border-line bg-panel text-faint opacity-60"
              }`}
            >
              <span
                className="h-2 w-2 rounded-full"
                style={{ backgroundColor: meta.color }}
              />
              {meta.label}
              <span className="tabular-nums text-faint">{counts[type] ?? 0}</span>
            </button>
          );
        })}
        <div className="ml-auto flex items-center gap-1">
          <button
            type="button"
            onClick={() => setZoom((z) => Math.max(0.4, +(z - 0.15).toFixed(2)))}
            className="btn btn-secondary btn-sm px-2"
            aria-label="Zoom out"
          >
            <Minus className="h-3.5 w-3.5" />
          </button>
          <span className="w-10 text-center text-[11px] font-semibold tabular-nums text-muted">
            {Math.round(zoom * 100)}%
          </span>
          <button
            type="button"
            onClick={() => setZoom((z) => Math.min(2.6, +(z + 0.15).toFixed(2)))}
            className="btn btn-secondary btn-sm px-2"
            aria-label="Zoom in"
          >
            <Plus className="h-3.5 w-3.5" />
          </button>
          <button
            type="button"
            onClick={resetView}
            className="btn btn-secondary btn-sm px-2"
            aria-label="Reset graph view"
          >
            <RotateCcw className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      <div className="mt-3 flex flex-col gap-3 lg:flex-row">
        <div className="relative min-w-0 flex-1 overflow-hidden rounded-xl border border-line bg-[#fbfdff]">
          <svg
            ref={svgRef}
            viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
            style={{ height, touchAction: "none" }}
            className={`w-full ${panning ? "cursor-grabbing" : "cursor-grab"}`}
            role="img"
            aria-label="Evidence knowledge graph"
            onPointerDown={handlePointerDown}
            onPointerMove={handlePointerMove}
            onPointerUp={endPointer}
            onPointerLeave={endPointer}
            onWheel={(e) => {
              e.preventDefault();
              setZoom((z) =>
                Math.max(0.4, Math.min(2.6, +(z + (e.deltaY > 0 ? -0.08 : 0.08)).toFixed(2))),
              );
            }}
          >
            <defs>
              <pattern id="graph-grid" width="32" height="32" patternUnits="userSpaceOnUse">
                <path d="M 32 0 L 0 0 0 32" fill="none" stroke="#eef3f9" strokeWidth="1" />
              </pattern>
              <filter id="graph-glow" x="-60%" y="-60%" width="220%" height="220%">
                <feGaussianBlur stdDeviation="5" result="blur" />
                <feMerge>
                  <feMergeNode in="blur" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
            </defs>
            <rect width={VIEW_W} height={VIEW_H} fill="url(#graph-grid)" />
            <g transform={`translate(${pan.x} ${pan.y}) scale(${zoom})`}>
              {visibleEdges.map((edge) => {
                const from = positions[edge.source];
                const to = positions[edge.target];
                if (!from || !to) return null;
                const highlighted =
                  selectedId !== null &&
                  (edge.source === selectedId || edge.target === selectedId);
                const midX = (from.x + to.x) / 2;
                const stroke =
                  edge.type === "contradicts"
                    ? "#e11d48"
                    : edge.type === "duplicate_of"
                      ? "#94a3b8"
                      : "#cbd8e6";
                return (
                  <path
                    key={edge.id}
                    d={`M ${from.x} ${from.y} C ${midX} ${from.y}, ${midX} ${to.y}, ${to.x} ${to.y}`}
                    fill="none"
                    stroke={stroke}
                    strokeWidth={highlighted ? 2 : 0.9}
                    strokeOpacity={highlighted ? 0.9 : selectedId ? 0.18 : 0.45}
                    strokeDasharray={edge.type === "duplicate_of" ? "4 4" : undefined}
                  />
                );
              })}
              {visibleNodes.map((node) => {
                const point = positions[node.id];
                if (!point) return null;
                const radius = nodeRadius(node);
                const isSelected = selectedId === node.id;
                const color = evidenceColor(node);
                const showLabel = node.type !== "evidence";
                return (
                  <g
                    key={node.id}
                    transform={`translate(${point.x} ${point.y})`}
                    className="cursor-pointer"
                    onPointerDown={(e) => {
                      e.stopPropagation();
                      setDraggingNode(node.id);
                      lastPoint.current = { x: e.clientX, y: e.clientY };
                      (e.currentTarget as SVGGElement)
                        .closest("svg")
                        ?.setPointerCapture(e.pointerId);
                    }}
                    onClick={(e) => {
                      e.stopPropagation();
                      setSelectedId((current) => (current === node.id ? null : node.id));
                    }}
                  >
                    <circle
                      r={radius + (isSelected ? 5 : 0)}
                      fill={isSelected ? `${color}22` : "transparent"}
                    />
                    <circle
                      r={radius}
                      fill={node.type === "evidence" ? color : `${color}18`}
                      stroke={color}
                      strokeWidth={node.type === "evidence" ? 1 : 1.8}
                      filter={isSelected ? "url(#graph-glow)" : undefined}
                      opacity={
                        node.status === "not_found" || node.status === "unclear"
                          ? 0.85
                          : 1
                      }
                    />
                    {node.type === "contradiction" && (
                      <text
                        textAnchor="middle"
                        dominantBaseline="central"
                        fontSize="11"
                        fontWeight="700"
                        fill="#fff"
                      >
                        !
                      </text>
                    )}
                    {node.type === "technology" && (
                      <text
                        textAnchor="middle"
                        dominantBaseline="central"
                        fontSize="11"
                        fontWeight="700"
                        fill="#0f766e"
                      >
                        TECH
                      </text>
                    )}
                    {showLabel && (
                      <text
                        x={radius + 7}
                        y={0}
                        dominantBaseline="central"
                        fontSize={node.type === "milestone" ? 9.5 : 10.5}
                        fill={node.type === "milestone" ? "#4f46e5" : "#42526b"}
                        fontWeight={node.type === "document" ? 600 : 500}
                      >
                        {shortLabel(node)}
                      </text>
                    )}
                  </g>
                );
              })}
            </g>
          </svg>

          <div className="pointer-events-none absolute bottom-2 left-3 flex flex-wrap gap-x-3 gap-y-1 text-[10px] text-faint">
            <span>Drag background to pan · scroll to zoom · drag nodes to rearrange</span>
            {graph.truncated && (
              <span className="inline-flex items-center gap-1 text-amber-700">
                <TriangleAlert className="h-3 w-3" />
                graph truncated for rendering
              </span>
            )}
          </div>
        </div>

        {/* Details panel */}
        <div className="w-full shrink-0 lg:w-72">
          {selected ? (
            <div className="rounded-xl border border-line bg-white p-4">
              <div className="flex items-start justify-between gap-2">
                <span
                  className="inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide"
                  style={{
                    color: evidenceColor(selected),
                    backgroundColor: `${evidenceColor(selected)}14`,
                  }}
                >
                  {TYPE_META[selected.type].title}
                </span>
                <button
                  type="button"
                  onClick={() => setSelectedId(null)}
                  className="text-faint hover:text-ink"
                  aria-label="Close node details"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
              <p className="mt-2 text-sm font-semibold leading-snug text-ink">
                {selected.label}
              </p>
              {selected.status && (
                <p className="mt-1 text-[11px] text-muted">
                  Status: <strong>{selected.status.replace(/_/g, " ")}</strong>
                </p>
              )}
              {(selected.document_id || selected.page_number !== null) && (
                <p className="mt-1 text-[11px] leading-relaxed text-faint">
                  {selected.document_id ? `Document ${selected.document_id}` : ""}
                  {selected.page_number !== null ? ` · page ${selected.page_number}` : ""}
                </p>
              )}
              {Object.keys(selected.metadata ?? {}).length > 0 && (
                <dl className="mt-3 space-y-1.5 border-t border-line pt-3 text-[11px]">
                  {Object.entries(selected.metadata)
                    .filter(([, value]) => value !== null && value !== "" && value !== undefined)
                    .slice(0, 8)
                    .map(([key, value]) => (
                      <div key={key} className="flex justify-between gap-2">
                        <dt className="text-faint">{key.replace(/_/g, " ")}</dt>
                        <dd className="max-w-40 truncate text-right font-medium text-ink-soft" title={String(value)}>
                          {String(value)}
                        </dd>
                      </div>
                    ))}
                </dl>
              )}
              {selected.type === "evidence" && onOpenEvidence && (
                <button
                  type="button"
                  onClick={() => onOpenEvidence(selected.id.replace(/^evidence::/, ""))}
                  className="btn btn-secondary btn-sm mt-3 w-full"
                >
                  <FileText className="h-3.5 w-3.5" />
                  Show in evidence table
                </button>
              )}

              <div className="mt-3 border-t border-line pt-3">
                <p className="mb-1.5 text-[10px] font-bold uppercase tracking-[0.1em] text-faint">
                  Relationships ({connected.length})
                </p>
                {connected.length === 0 ? (
                  <p className="text-[11px] text-faint">No visible connections.</p>
                ) : (
                  <ul className="max-h-44 space-y-1 overflow-auto pr-1">
                    {connected.slice(0, 24).map(({ edge, other }) => (
                      <li key={edge.id}>
                        <button
                          type="button"
                          onClick={() => other && setSelectedId(other.id)}
                          className="flex w-full items-center gap-1.5 rounded-md px-1.5 py-1 text-left text-[11px] text-muted hover:bg-panel"
                        >
                          <Layers className="h-3 w-3 shrink-0 text-faint" />
                          <span className="truncate">
                            {edge.type.replace(/_/g, " ")} · {other?.label}
                          </span>
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          ) : (
            <div className="rounded-xl border border-line bg-panel/70 p-4 text-xs leading-relaxed text-muted">
              <p className="mb-2 flex items-center gap-1.5 font-semibold text-ink-soft">
                <Flag className="h-3.5 w-3.5" />
                Explore the assessment
              </p>
              <p>
                Click a node to inspect its provenance and relationships. Evidence
                nodes are coloured by status; red nodes mark detected contradictions.
              </p>
              <ul className="mt-3 space-y-1.5">
                <li className="flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full bg-emerald-600" /> confirmed
                  evidence
                </li>
                <li className="flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full bg-blue-600" /> proposed evidence
                </li>
                <li className="flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full bg-amber-600" /> unclear evidence
                </li>
                <li className="flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full bg-rose-600" /> contradicted
                </li>
              </ul>
              <p className="mt-3 border-t border-line pt-2 text-[11px] text-faint">
                <Building2 className="mr-1 inline h-3 w-3" />
                {graph.node_count} nodes · {graph.edge_count} edges
              </p>
            </div>
          )}
        </div>
      </div>
      <p className="mt-2 text-[11px] leading-relaxed text-faint">{graph.note}</p>
    </div>
  );
}
