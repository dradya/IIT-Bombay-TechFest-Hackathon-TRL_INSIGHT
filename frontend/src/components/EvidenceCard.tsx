import { Copy, FileWarning, Layers, Quote } from "lucide-react";
import type { EvidenceItem } from "../types";
import StatusBadge from "./StatusBadge";

interface EvidenceCardProps {
  evidence: EvidenceItem;
  /** Optional click handler (e.g. focus the node in the graph). */
  onSelect?: (evidence: EvidenceItem) => void;
  selected?: boolean;
  compact?: boolean;
}

function provenance(e: EvidenceItem): string {
  const parts = [e.source_document || "Source document"];
  if (e.page_number !== null && e.page_number !== undefined) {
    parts.push(`page ${e.page_number}`);
  } else if (e.location) {
    parts.push(e.location);
  }
  if (e.section) parts.push(e.section);
  return parts.join(" · ");
}

/** Single evidence excerpt with provenance, status and duplicate handling. */
export default function EvidenceCard({
  evidence: e,
  onSelect,
  selected = false,
  compact = false,
}: EvidenceCardProps) {
  const isDuplicate = Boolean(e.duplicate_of);
  const Component = onSelect ? "button" : "div";
  return (
    <Component
      type={onSelect ? "button" : undefined}
      onClick={onSelect ? () => onSelect(e) : undefined}
      className={`w-full rounded-xl border bg-white px-4 text-left transition-colors ${
        compact ? "py-3" : "py-4"
      } ${
        selected
          ? "border-primary ring-2 ring-teal-500/15"
          : "border-line hover:border-line-strong"
      } ${onSelect ? "cursor-pointer hover:bg-teal-50/30" : ""}`}
    >
      <div className="flex items-start gap-2.5">
        <Quote className="mt-0.5 h-3.5 w-3.5 shrink-0 text-teal-500" aria-hidden="true" />
        <div className="min-w-0 flex-1">
          <p className={`leading-relaxed text-ink-soft ${compact ? "text-[13px]" : "text-sm"}`}>
            {e.statement}
          </p>
          <p className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-faint">
            <span className="inline-flex items-center gap-1">
              <Layers className="h-3 w-3" />
              {e.category_label}
            </span>
            <span aria-hidden="true">·</span>
            <span>{provenance(e)}</span>
          </p>
          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            <StatusBadge kind="evidence" value={e.status} />
            <StatusBadge kind="stance" value={e.stance} />
            {e.evidence_type === "self_reported" && (
              <span className="chip border-blue-200 bg-blue-50 px-2 py-0 text-[10px] text-blue-700">
                Self-reported
              </span>
            )}
            {isDuplicate && (
              <span
                className="chip border-slate-200 bg-slate-50 px-2 py-0 text-[10px] text-slate-600"
                title={`Grouped with ${e.duplicate_of}; counted once in the assessment.`}
              >
                <Copy className="h-3 w-3" />
                Duplicate of {e.duplicate_of}
                {(e.duplicate_count ?? 1) > 1 ? ` · ×${e.duplicate_count}` : ""}
              </span>
            )}
            {e.outdated && (
              <span
                className="chip border-amber-200 bg-amber-50 px-2 py-0 text-[10px] text-amber-700"
                title={e.superseded_by ? `Superseded by ${e.superseded_by}` : "Older evidence"}
              >
                <FileWarning className="h-3 w-3" />
                Outdated
              </span>
            )}
            {typeof e.semantic_similarity === "number" && (
              <span className="chip px-2 py-0 text-[10px]">
                Similarity {(e.semantic_similarity * 100).toFixed(0)}%
              </span>
            )}
          </div>
        </div>
      </div>
    </Component>
  );
}
