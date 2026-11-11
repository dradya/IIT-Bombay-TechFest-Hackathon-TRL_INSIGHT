import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  AlertOctagon,
  FileText,
  GitCompare,
  Loader2,
  Network,
  X,
} from "lucide-react";
import { useApi } from "../hooks/useApi";
import type {
  AssessmentListResponse,
  CompareItem,
  CompareResponse,
  MilestoneStatusValue,
  OverviewResponse,
} from "../types";
import PageHeader from "../components/PageHeader";
import FilterBar from "../components/FilterBar";
import EmptyState from "../components/EmptyState";
import ErrorBanner from "../components/ErrorBanner";
import StatusBadge from "../components/StatusBadge";
import ConfidenceBar from "../components/ConfidenceBar";
import Skeleton from "../components/Skeleton";
import DocumentComparisonViewer from "../components/DocumentComparisonViewer";
import { formatDate, formatPercent } from "../utils/format";

const TRL_OPTIONS = Array.from({ length: 9 }, (_, i) => ({
  value: String(i + 1),
  label: `TRL ${i + 1}`,
}));

const REVIEW_OPTIONS = [
  { value: "unreviewed", label: "Unreviewed" },
  { value: "accepted", label: "Accepted" },
  { value: "overridden", label: "Overridden" },
  { value: "more_evidence_requested", label: "More evidence requested" },
];

const CONFIDENCE_OPTIONS = [
  { value: "high", label: "High (≥ 70%)" },
  { value: "medium", label: "Medium (45–69%)" },
  { value: "low", label: "Low (< 45%)" },
];

const MAX_COMPARE = 3;

/** Colour for each real milestone status in the comparison matrix. */
const matrixTone: Record<MilestoneStatusValue, string> = {
  confirmed: "bg-emerald-500",
  unclear: "bg-amber-400",
  contradicted: "bg-rose-500",
  not_found: "bg-slate-200",
};

const REVIEW_STYLE: Record<string, string> = {
  unreviewed: "border-slate-200 bg-slate-50 text-slate-600",
  accepted: "border-emerald-200 bg-emerald-50 text-emerald-700",
  overridden: "border-blue-200 bg-blue-50 text-blue-700",
  more_evidence_requested: "border-amber-200 bg-amber-50 text-amber-700",
};

const REVIEW_LABEL: Record<string, string> = {
  unreviewed: "Unreviewed",
  accepted: "Accepted",
  overridden: "Overridden",
  more_evidence_requested: "More evidence",
};

function ReviewBadge({ status }: { status?: string }) {
  const key = status || "unreviewed";
  return (
    <span
      className={`inline-flex rounded-full border px-2 py-0.5 text-[10px] font-semibold ${
        REVIEW_STYLE[key] ?? REVIEW_STYLE.unreviewed
      }`}
    >
      {REVIEW_LABEL[key] ?? key}
    </span>
  );
}

function milestoneByLevel(item: CompareItem) {
  const map = new Map<number, CompareItem["milestones"][number]>();
  item.milestones.forEach((m) => {
    if (!map.has(m.trl)) map.set(m.trl, m);
  });
  return map;
}

export default function Explorer() {
  const navigate = useNavigate();

  const [searchInput, setSearchInput] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [domain, setDomain] = useState("");
  const [trlMin, setTrlMin] = useState("");
  const [trlMax, setTrlMax] = useState("");
  const [confidence, setConfidence] = useState("");
  const [reviewStatus, setReviewStatus] = useState("");
  const [selectedIds, setSelectedIds] = useState<string[]>([]);

  useEffect(() => {
    const t = window.setTimeout(() => setDebouncedSearch(searchInput), 400);
    return () => window.clearTimeout(t);
  }, [searchInput]);

  const overview = useApi<OverviewResponse>("/api/overview");

  const query = useMemo(() => {
    const params = new URLSearchParams();
    if (debouncedSearch.trim()) params.set("search", debouncedSearch.trim());
    if (domain) params.set("domain", domain);
    if (trlMin) params.set("trl_min", trlMin);
    if (trlMax) params.set("trl_max", trlMax);
    if (reviewStatus) params.set("review_status", reviewStatus);
    if (confidence === "high") params.set("confidence_min", "0.7");
    if (confidence === "medium") {
      params.set("confidence_min", "0.45");
      params.set("confidence_max", "0.6999");
    }
    if (confidence === "low") params.set("confidence_max", "0.4499");
    const qs = params.toString();
    return `/api/assessments${qs ? `?${qs}` : ""}`;
  }, [debouncedSearch, domain, trlMin, trlMax, confidence, reviewStatus]);

  const list = useApi<AssessmentListResponse>(query);
  const items = list.data?.items ?? [];
  const domains = overview.data?.domains ?? [];
  const hasActiveFilters = Boolean(
    debouncedSearch.trim() ||
      domain ||
      trlMin ||
      trlMax ||
      confidence ||
      reviewStatus,
  );

  // Real comparison data from /api/assessments/compare (2-3 ids).
  const compareQuery =
    selectedIds.length >= 2
      ? `/api/assessments/compare?ids=${encodeURIComponent(selectedIds.join(","))}`
      : null;
  const compare = useApi<CompareResponse>(compareQuery);

  // Keep only selections that still exist in the current result set.
  useEffect(() => {
    if (!list.data) return;
    const valid = new Set(list.data.items.map((i) => i.id));
    setSelectedIds((prev) => prev.filter((id) => valid.has(id)));
  }, [list.data]);

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      if (prev.includes(id)) return prev.filter((x) => x !== id);
      if (prev.length >= MAX_COMPARE) return prev;
      return [...prev, id];
    });
  };

  const selected = useMemo(
    () => items.filter((i) => selectedIds.includes(i.id)),
    [items, selectedIds],
  );

  // Guard against stale compare data while a new selection loads.
  const compareItems = useMemo(() => {
    const raw = compare.data?.items ?? [];
    if (raw.length !== selectedIds.length) return [];
    const ids = new Set(selectedIds);
    return raw.every((r) => ids.has(r.id)) ? raw : [];
  }, [compare.data, selectedIds]);

  const compareReady = selectedIds.length >= 2 && compareItems.length >= 2;

  const clearFilters = () => {
    setSearchInput("");
    setDebouncedSearch("");
    setDomain("");
    setTrlMin("");
    setTrlMax("");
    setConfidence("");
    setReviewStatus("");
  };

  const compareRows: {
    label: string;
    render: (item: CompareItem) => React.ReactNode;
  }[] = [
    {
      label: "Predicted TRL",
      render: (a) => (
        <span className="font-bold text-ink">
          {a.predicted_trl !== null ? `TRL ${a.predicted_trl}` : "—"}
        </span>
      ),
    },
    {
      label: "Confidence",
      render: (a) => (
        <div>
          <div className="w-28">
            <ConfidenceBar value={a.confidence ?? 0} showLabel={false} />
          </div>
          <span className="mt-1 block text-xs text-faint">
            {formatPercent(a.confidence, 0)}
          </span>
        </div>
      ),
    },
    {
      label: "Evidence coverage",
      render: (a) => <span>{formatPercent(a.evidence_coverage, 0)}</span>,
    },
    {
      label: "Overall reliability",
      render: (a) =>
        a.uncertainty_overall !== null ? (
          <span>{formatPercent(a.uncertainty_overall, 0)}</span>
        ) : (
          <span className="text-xs text-faint">Not stored</span>
        ),
    },
    {
      label: "Evidence items",
      render: (a) => <span className="tabular-nums">{a.evidence_total}</span>,
    },
    {
      label: "Contradictions",
      render: (a) =>
        a.contradictions_total > 0 ? (
          <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-rose-700">
            <AlertOctagon className="h-3.5 w-3.5" />
            {a.contradictions_total}
          </span>
        ) : (
          <span className="text-xs text-faint">None</span>
        ),
    },
    {
      label: "Documents",
      render: (a) => (
        <span className="inline-flex items-center gap-1.5 text-xs text-muted">
          <FileText className="h-3.5 w-3.5 text-faint" />
          {a.documents.length || "—"}
        </span>
      ),
    },
    {
      label: "Assessed",
      render: (a) => <span>{formatDate(a.created_at)}</span>,
    },
    {
      label: "Open",
      render: (a) => (
        <button
          type="button"
          onClick={() => navigate(`/assessments/${a.id}`)}
          className="text-xs font-semibold text-secondary hover:underline"
        >
          View result →
        </button>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        title="Technology Explorer"
        subtitle="Browse assessed technologies and compare up to 3 side by side."
        actions={
          selectedIds.length > 0 && (
            <button
              type="button"
              onClick={() => setSelectedIds([])}
              className="btn btn-secondary"
            >
              <X className="h-4 w-4" />
              Clear selection ({selectedIds.length})
            </button>
          )
        }
      />

      <div className="mb-4">
        <FilterBar
          searchValue={searchInput}
          onSearchChange={setSearchInput}
          searchPlaceholder="Search technologies…"
          fields={[
            {
              key: "domain",
              label: "Domain",
              value: domain,
              options: domains.map((d) => ({ value: d, label: d })),
              onChange: setDomain,
            },
            {
              key: "trl-min",
              label: "TRL from",
              value: trlMin,
              options: TRL_OPTIONS,
              onChange: setTrlMin,
            },
            {
              key: "trl-max",
              label: "TRL to",
              value: trlMax,
              options: TRL_OPTIONS,
              onChange: setTrlMax,
            },
            {
              key: "confidence",
              label: "Confidence",
              value: confidence,
              options: CONFIDENCE_OPTIONS,
              onChange: setConfidence,
            },
            {
              key: "review",
              label: "Review status",
              value: reviewStatus,
              options: REVIEW_OPTIONS,
              onChange: setReviewStatus,
            },
          ]}
          onClear={clearFilters}
          hasActiveFilters={hasActiveFilters}
        />
      </div>

      {list.loading && !list.data && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="card p-5">
              <Skeleton className="h-5 w-40" />
              <Skeleton className="mt-3 h-4 w-24" />
              <Skeleton className="mt-4 h-8 w-full" />
            </div>
          ))}
        </div>
      )}

      {list.error && (
        <div className="mb-4">
          <ErrorBanner
            message={list.error}
            networkError={list.networkError}
            onRetry={list.refetch}
          />
        </div>
      )}

      {list.data && items.length === 0 && (
        <EmptyState
          icon={GitCompare}
          title={
            hasActiveFilters
              ? "No technologies match your filters"
              : "No assessments yet"
          }
          description={
            hasActiveFilters
              ? "Adjust the domain, TRL, confidence or review-status filters to widen the search."
              : "Run your first assessment — it will show up here as an explorer card."
          }
          actionLabel={hasActiveFilters ? "Clear filters" : "New Assessment"}
          onAction={hasActiveFilters ? clearFilters : () => navigate("/new")}
        />
      )}

      {items.length > 0 && (
        <>
          <div className="mb-3 flex items-center gap-2 text-xs text-muted">
            <Loader2
              className={`h-3.5 w-3.5 text-primary ${
                list.loading ? "animate-spin" : "hidden"
              }`}
            />
            {items.length === 1 ? "1 technology" : `${items.length} technologies`}{" "}
            · select up to {MAX_COMPARE} to compare
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
            {items.map((a) => {
              const isSelected = selectedIds.includes(a.id);
              const isFull =
                selectedIds.length >= MAX_COMPARE && !isSelected;
              return (
                <div
                  key={a.id}
                  className={`card relative p-5 transition-all duration-200 ${
                    isSelected
                      ? "border-primary shadow-[0_0_0_3px_rgba(13,148,136,0.12),0_18px_40px_-28px_rgba(10,22,40,0.5)]"
                      : "hover:-translate-y-0.5 hover:border-line-strong hover:shadow-[0_18px_40px_-28px_rgba(10,22,40,0.45)]"
                  } ${isFull ? "opacity-60" : ""}`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <button
                      type="button"
                      onClick={() => navigate(`/assessments/${a.id}`)}
                      className="min-w-0 text-left"
                    >
                      <h3 className="truncate text-sm font-semibold text-ink hover:text-primary">
                        {a.technology_name || "Untitled technology"}
                      </h3>
                      <p className="mt-0.5 truncate text-xs text-faint">
                        {a.organization || "No organization"} ·{" "}
                        {a.domain || "No domain"}
                      </p>
                    </button>
                    <label
                      className={`flex shrink-0 cursor-pointer items-center gap-1.5 text-xs font-medium ${
                        isFull
                          ? "cursor-not-allowed text-slate-300"
                          : "text-muted"
                      }`}
                      title={
                        isFull
                          ? `Max ${MAX_COMPARE} selections`
                          : "Select for comparison"
                      }
                    >
                      <input
                        type="checkbox"
                        checked={isSelected}
                        disabled={isFull}
                        onChange={() => toggleSelect(a.id)}
                        className="h-4 w-4 rounded border-slate-300 accent-teal-600"
                      />
                      Compare
                    </label>
                  </div>

                  <div className="mt-4 flex items-center gap-4">
                    <span className="flex h-14 w-14 shrink-0 flex-col items-center justify-center rounded-2xl bg-gradient-to-br from-teal-500 to-teal-700 text-white shadow-[0_12px_24px_-14px_rgba(13,148,136,0.9)]">
                      <span className="text-xl font-bold leading-none">
                        {a.predicted_trl ?? "–"}
                      </span>
                      <span className="text-[9px] font-semibold uppercase tracking-wide opacity-80">
                        TRL
                      </span>
                    </span>
                    <div className="min-w-0 flex-1 space-y-2">
                      <div>
                        <p className="mb-0.5 flex justify-between text-[11px] text-faint">
                          <span>Confidence</span>
                          <span className="font-semibold text-ink-soft">
                            {formatPercent(a.confidence, 0)}
                          </span>
                        </p>
                        <ConfidenceBar
                          value={a.confidence ?? 0}
                          showLabel={false}
                        />
                      </div>
                      <div>
                        <p className="mb-0.5 flex justify-between text-[11px] text-faint">
                          <span>Coverage</span>
                          <span className="font-semibold text-ink-soft">
                            {formatPercent(a.evidence_coverage, 0)}
                          </span>
                        </p>
                        <ConfidenceBar
                          value={a.evidence_coverage ?? 0}
                          showLabel={false}
                        />
                      </div>
                    </div>
                  </div>

                  <div className="mt-4 flex items-center justify-between border-t border-line pt-3">
                    <div className="flex min-w-0 items-center gap-2">
                      <span className="text-xs text-faint">
                        {formatDate(a.created_at)}
                      </span>
                      <ReviewBadge status={a.review_status} />
                    </div>
                    <div className="flex items-center gap-2">
                      {a.low_confidence && (
                        <StatusBadge
                          kind="custom"
                          value=""
                          tone="amber"
                          label="Low conf."
                        />
                      )}
                      <button
                        type="button"
                        onClick={() => navigate(`/assessments/${a.id}`)}
                        className="text-xs font-semibold text-secondary hover:underline"
                      >
                        Open →
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}

      {/* Real comparison view */}
      {selected.length >= 2 && (
        <div className="card mt-6 overflow-hidden">
          <div className="flex items-center justify-between border-b border-line px-5 py-4">
            <div className="flex items-center gap-3">
              <span className="icon-tile h-9 w-9">
                <GitCompare className="h-4 w-4" />
              </span>
              <div>
                <h2 className="section-title">
                  Comparison ({selected.length})
                </h2>
                <p className="mt-0.5 text-xs text-faint">
                  Values read directly from each stored assessment result
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={() => setSelectedIds([])}
              className="text-xs font-semibold text-primary hover:text-primary-dark"
            >
              Clear
            </button>
          </div>

          {compare.error && (
            <div className="border-b border-line px-5 py-4">
              <ErrorBanner
                message={compare.error}
                networkError={compare.networkError}
                onRetry={compare.refetch}
                hint={
                  compare.error.includes("409")
                    ? "A selected assessment predates the multi-document pipeline. Open it and re-run the analysis."
                    : undefined
                }
              />
            </div>
          )}

          {!compareReady && !compare.error && (
            <div className="flex items-center gap-2 px-5 py-6 text-sm text-muted">
              <Loader2 className="h-4 w-4 animate-spin text-primary" />
              Loading comparison data…
            </div>
          )}

          {compareReady && (
            <>
              <div className="scrollbar-thin overflow-x-auto">
                <table className="w-full min-w-[680px] text-left text-sm">
                  <thead>
                    <tr className="border-b border-line bg-panel/50">
                      <th className="px-4 py-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-faint">
                        Attribute
                      </th>
                      {compareItems.map((a) => (
                        <th
                          key={a.id}
                          className="px-4 py-3 text-sm font-semibold text-ink"
                        >
                          <button
                            type="button"
                            onClick={() => navigate(`/assessments/${a.id}`)}
                            className="max-w-52 truncate hover:text-primary hover:underline"
                          >
                            {a.technology_name || "Untitled"}
                          </button>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line/70">
                    {compareRows.map((row) => (
                      <tr
                        key={row.label}
                        className="transition-colors hover:bg-teal-50/30"
                      >
                        <td className="whitespace-nowrap px-4 py-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-faint">
                          {row.label}
                        </td>
                        {compareItems.map((a) => (
                          <td key={a.id} className="px-4 py-3 text-ink-soft">
                            {row.render(a)}
                          </td>
                        ))}
                      </tr>
                    ))}

                    {/* Milestone matrix uses real per-milestone statuses. */}
                    <tr className="transition-colors hover:bg-teal-50/30">
                      <td className="whitespace-nowrap px-4 py-3 align-top text-[11px] font-semibold uppercase tracking-[0.12em] text-faint">
                        Milestone matrix (TRL 1–9)
                      </td>
                      {compareItems.map((a) => {
                        const byLevel = milestoneByLevel(a);
                        if (a.milestones.length === 0) {
                          return (
                            <td key={a.id} className="px-4 py-3">
                              <span className="text-xs text-faint">
                                No milestone detail stored.
                              </span>
                            </td>
                          );
                        }
                        return (
                          <td key={a.id} className="px-4 py-3">
                            <div className="flex gap-1">
                              {Array.from({ length: 9 }, (_, i) => i + 1).map(
                                (lvl) => {
                                  const m = byLevel.get(lvl);
                                  return (
                                    <span
                                      key={lvl}
                                      title={
                                        m
                                          ? `TRL ${lvl}: ${m.status.replace(
                                              /_/g,
                                              " ",
                                            )} · ${m.evidence_count} evidence`
                                          : `TRL ${lvl}: no milestone record`
                                      }
                                      className={`h-5 w-5 rounded ${
                                        m
                                          ? matrixTone[m.status]
                                          : "border border-dashed border-slate-300 bg-white"
                                      }`}
                                    />
                                  );
                                },
                              )}
                            </div>
                            <p className="mt-1.5 text-[11px] text-faint">
                              Each square is that level's real milestone status.
                            </p>
                          </td>
                        );
                      })}
                    </tr>
                  </tbody>
                </table>
              </div>

              <div className="flex flex-wrap gap-4 border-t border-line px-5 py-3 text-[11px] text-muted">
                <span className="inline-flex items-center gap-1.5">
                  <span className="h-3 w-3 rounded bg-emerald-500" /> Confirmed
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <span className="h-3 w-3 rounded bg-amber-400" /> Unclear
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <span className="h-3 w-3 rounded bg-rose-500" /> Contradicted
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <span className="h-3 w-3 rounded bg-slate-200" /> Not found
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <span className="h-3 w-3 rounded border border-dashed border-slate-300 bg-white" />{" "}
                  No record
                </span>
              </div>

              {compare.data?.note && (
                <p className="border-t border-line bg-panel/40 px-5 py-3 text-xs leading-relaxed text-muted">
                  {compare.data.note}
                </p>
              )}
            </>
          )}
        </div>
      )}

      {/* Cross-assessment document provenance */}
      {compareReady && (
        <div className="card mt-4 overflow-hidden">
          <div className="flex items-center gap-3 border-b border-line px-5 py-4">
            <span className="icon-tile h-9 w-9">
              <Network className="h-4 w-4" />
            </span>
            <div>
              <h2 className="section-title">Document provenance comparison</h2>
              <p className="mt-0.5 text-xs text-faint">
                What each attached document contributed in every selected
                assessment
              </p>
            </div>
          </div>
          <div className="grid grid-cols-1 gap-4 p-5 lg:grid-cols-3">
            {compareItems.map((a) => (
              <div
                key={a.id}
                className="rounded-xl border border-line bg-white p-4"
              >
                <p className="mb-3 truncate text-sm font-semibold text-ink">
                  {a.technology_name || "Untitled"}
                </p>
                {a.documents.length > 0 ? (
                  <DocumentComparisonViewer documents={a.documents} />
                ) : (
                  <p className="rounded-lg border border-dashed border-line bg-panel/60 px-3 py-3 text-xs leading-relaxed text-faint">
                    No document provenance is stored for this assessment. It may
                    predate the 2.0 multi-document pipeline — re-run the analysis
                    to capture per-document provenance.
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
