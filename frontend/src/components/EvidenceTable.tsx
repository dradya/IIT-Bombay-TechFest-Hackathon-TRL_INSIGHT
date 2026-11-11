import { useMemo, useState } from "react";
import { Search } from "lucide-react";
import type { EvidenceItem, EvidenceSummary } from "../types";
import StatusBadge from "./StatusBadge";
import ConfidenceBar from "./ConfidenceBar";
import EmptyState from "./EmptyState";
import { readDefaultEvidenceFilter } from "../utils/prefs";

interface EvidenceTableProps {
  evidence: EvidenceItem[];
  summary: EvidenceSummary;
}

function pageCell(item: EvidenceItem): string {
  if (item.page_number !== null && item.page_number !== undefined) {
    return `Page ${item.page_number}`;
  }
  if (item.location) return item.location;
  return "—";
}

/** Summary chip (total / confirmed / proposed / …). */
function Chip({
  label,
  count,
  tone,
  dot,
}: {
  label: string;
  count: number;
  tone?: string;
  dot?: string;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium ${
        tone ?? "border-line bg-panel text-muted"
      }`}
    >
      {dot && <span className={`h-1.5 w-1.5 rounded-full ${dot}`} />}
      {label}
      <span className="font-semibold tabular-nums">{count}</span>
    </span>
  );
}

/** Evidence table with status/category filters + text search + summary chips. */
export default function EvidenceTable({ evidence, summary }: EvidenceTableProps) {
  const [statusFilter, setStatusFilter] = useState<string>(() =>
    readDefaultEvidenceFilter(),
  );
  const [categoryFilter, setCategoryFilter] = useState<string>("");
  const [originFilter, setOriginFilter] = useState<string>("");
  const [outdatedOnly, setOutdatedOnly] = useState(false);
  const [query, setQuery] = useState<string>("");

  const categories = useMemo(() => {
    const map = new Map<string, string>();
    evidence.forEach((e) => map.set(e.category, e.category_label));
    return Array.from(map.entries()).sort((a, b) => a[1].localeCompare(b[1]));
  }, [evidence]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return evidence.filter((e) => {
      if (statusFilter && e.status !== statusFilter) return false;
      if (categoryFilter && e.category !== categoryFilter) return false;
      if (originFilter && (e.evidence_type ?? "document") !== originFilter) return false;
      if (outdatedOnly && !e.outdated) return false;
      if (
        q &&
        !e.statement.toLowerCase().includes(q) &&
        !e.category_label.toLowerCase().includes(q) &&
        !(e.milestone_label ?? "").toLowerCase().includes(q)
      ) {
        return false;
      }
      return true;
    });
  }, [evidence, statusFilter, categoryFilter, originFilter, outdatedOnly, query]);

  const hasFilters = Boolean(
    statusFilter || categoryFilter || originFilter || outdatedOnly || query.trim(),
  );

  return (
    <div className="card overflow-hidden">
      {/* Summary chips */}
      <div className="flex flex-wrap items-center gap-2 border-b border-line px-4 py-3">
        <Chip label="Total" count={summary.total} />
        <Chip
          label="Confirmed"
          count={summary.confirmed}
          tone="border-emerald-200/80 bg-emerald-50 text-emerald-700"
          dot="bg-emerald-500"
        />
        <Chip
          label="Proposed"
          count={summary.proposed}
          tone="border-blue-200/80 bg-blue-50 text-blue-700"
          dot="bg-blue-500"
        />
        <Chip
          label="Contradicted"
          count={summary.contradicted}
          tone="border-rose-200/80 bg-rose-50 text-rose-700"
          dot="bg-rose-500"
        />
        <Chip
          label="Unclear"
          count={summary.unclear}
          tone="border-amber-200/80 bg-amber-50 text-amber-700"
          dot="bg-amber-500"
        />
        {typeof summary.duplicates === "number" && summary.duplicates > 0 && (
          <Chip
            label="Duplicates excluded"
            count={summary.duplicates}
            tone="border-slate-200 bg-slate-50 text-slate-600"
            dot="bg-slate-400"
          />
        )}
        {typeof summary.outdated === "number" && summary.outdated > 0 && (
          <Chip
            label="Outdated"
            count={summary.outdated}
            tone="border-amber-200/80 bg-amber-50 text-amber-700"
            dot="bg-amber-500"
          />
        )}
        {typeof summary.self_reported === "number" && summary.self_reported > 0 && (
          <Chip
            label="Self-reported"
            count={summary.self_reported}
            tone="border-blue-200/80 bg-blue-50 text-blue-700"
            dot="bg-blue-400"
          />
        )}
        <span className="ml-auto text-xs font-medium text-faint">
          Showing {filtered.length} of {evidence.length}
        </span>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3 border-b border-line bg-panel/70 px-4 py-3">
        <div className="relative min-w-52 flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-faint" />
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search evidence statements…"
            aria-label="Search evidence statements"
            className="w-full rounded-lg border border-line-strong bg-white py-2 pl-9 pr-3 text-sm"
          />
        </div>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          aria-label="Filter by status"
          className="rounded-lg border border-line-strong bg-white px-3 py-2 text-sm"
        >
          <option value="">All statuses</option>
          <option value="confirmed">Confirmed</option>
          <option value="proposed">Proposed</option>
          <option value="contradicted">Contradicted</option>
          <option value="unclear">Unclear</option>
        </select>
        <select
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value)}
          aria-label="Filter by category"
          className="rounded-lg border border-line-strong bg-white px-3 py-2 text-sm"
        >
          <option value="">All categories</option>
          {categories.map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
        <select
          value={originFilter}
          onChange={(e) => setOriginFilter(e.target.value)}
          aria-label="Filter by evidence origin"
          className="rounded-lg border border-line-strong bg-white px-3 py-2 text-sm"
        >
          <option value="">Any origin</option>
          <option value="document">Document text</option>
          <option value="self_reported">Self-reported</option>
        </select>
        <label className="inline-flex items-center gap-1.5 text-xs font-medium text-muted">
          <input
            type="checkbox"
            checked={outdatedOnly}
            onChange={(e) => setOutdatedOnly(e.target.checked)}
          />
          Outdated only
        </label>
        {hasFilters && (
          <button
            type="button"
            onClick={() => {
              setStatusFilter("");
              setCategoryFilter("");
              setOriginFilter("");
              setOutdatedOnly(false);
              setQuery("");
            }}
            className="text-xs font-semibold text-secondary hover:underline"
          >
            Reset filters
          </button>
        )}
      </div>

      {/* Table */}
      {filtered.length === 0 ? (
        <div className="px-4 py-8">
          <EmptyState
            title={hasFilters ? "No evidence matches the filters" : "No evidence extracted"}
            description={
              hasFilters
                ? "Try a different status, category or search term."
                : "This assessment produced no evidence excerpts."
            }
            actionLabel={hasFilters ? "Reset filters" : undefined}
            onAction={
              hasFilters
                ? () => {
                    setStatusFilter("");
                    setCategoryFilter("");
                    setOriginFilter("");
                    setOutdatedOnly(false);
                    setQuery("");
                  }
                : undefined
            }
          />
        </div>
      ) : (
        <div className="scrollbar-thin overflow-x-auto">
          <table className="w-full min-w-[900px] text-left text-sm">
            <thead>
              <tr className="border-b border-line bg-white text-[11px] uppercase tracking-[0.12em] text-faint">
                <th className="px-4 py-3 font-semibold">Evidence statement</th>
                <th className="px-3 py-3 font-semibold">Category</th>
                <th className="px-3 py-3 font-semibold">Source document</th>
                <th className="px-3 py-3 font-semibold">Page</th>
                <th className="px-3 py-3 font-semibold">Stance</th>
                <th className="px-3 py-3 font-semibold">Relevance</th>
                <th className="px-3 py-3 font-semibold">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line/70">
              {filtered.map((e) => (
                <tr
                  key={e.id}
                  className="align-top transition-colors hover:bg-teal-50/30"
                >
                  <td className="max-w-md px-4 py-3.5">
                    <p className="leading-relaxed text-ink-soft">{e.statement}</p>
                    <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                      {e.milestone_label && (
                        <span className="text-xs text-faint">
                          → {e.milestone_label}
                          {e.is_proposed && " · proposed/future work"}
                        </span>
                      )}
                      {e.duplicate_of && (
                        <span
                          className="chip border-slate-200 bg-slate-50 px-2 py-0 text-[10px] text-slate-600"
                          title="Grouped with an identical claim and counted once."
                        >
                          Duplicate of {e.duplicate_of}
                          {(e.duplicate_count ?? 1) > 1 ? ` · ×${e.duplicate_count}` : ""}
                        </span>
                      )}
                      {e.outdated && (
                        <span className="chip border-amber-200 bg-amber-50 px-2 py-0 text-[10px] text-amber-700">
                          Outdated
                          {e.superseded_by ? ` · superseded by ${e.superseded_by}` : ""}
                        </span>
                      )}
                      {e.evidence_type === "self_reported" && (
                        <span className="chip border-blue-200 bg-blue-50 px-2 py-0 text-[10px] text-blue-700">
                          Self-reported
                        </span>
                      )}
                      {typeof e.semantic_similarity === "number" && (
                        <span className="chip px-2 py-0 text-[10px]">
                          Semantic {(e.semantic_similarity * 100).toFixed(0)}%
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="whitespace-nowrap px-3 py-3.5 text-muted">
                    {e.category_label}
                  </td>
                  <td
                    className="max-w-40 truncate px-3 py-3.5 text-muted"
                    title={e.source_document}
                  >
                    {e.source_document || "—"}
                  </td>
                  <td className="whitespace-nowrap px-3 py-3.5">
                    <span className="chip">{pageCell(e)}</span>
                  </td>
                  <td className="px-3 py-3.5">
                    <StatusBadge kind="stance" value={e.stance} />
                  </td>
                  <td className="px-3 py-3.5">
                    <ConfidenceBar value={e.relevance} />
                  </td>
                  <td className="px-3 py-3.5">
                    <StatusBadge kind="evidence" value={e.status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
