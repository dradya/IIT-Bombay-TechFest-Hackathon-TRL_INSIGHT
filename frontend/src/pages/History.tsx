import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  Eye,
  FileJson,
  FileText,
  History as HistoryIcon,
  Loader2,
  Trash2,
} from "lucide-react";
import { apiDelete, downloadFile, errorMessage } from "../services/api";
import { useApi } from "../hooks/useApi";
import type { AssessmentListResponse, OverviewResponse } from "../types";
import PageHeader from "../components/PageHeader";
import FilterBar from "../components/FilterBar";
import ConfirmDialog from "../components/ConfirmDialog";
import EmptyState from "../components/EmptyState";
import ErrorBanner from "../components/ErrorBanner";
import ConfidenceBar from "../components/ConfidenceBar";
import Skeleton from "../components/Skeleton";
import { useToast } from "../components/Toast";
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
  { value: "flagged", label: "Flagged low-confidence" },
];

const SORT_OPTIONS = [
  { value: "created_desc", label: "Newest first" },
  { value: "created_asc", label: "Oldest first" },
  { value: "trl_desc", label: "TRL high → low" },
  { value: "trl_asc", label: "TRL low → high" },
  { value: "confidence_desc", label: "Confidence high → low" },
  { value: "confidence_asc", label: "Confidence low → high" },
  { value: "coverage_desc", label: "Coverage high → low" },
];

const DOCUMENT_OPTIONS = [
  { value: "single", label: "Single document" },
  { value: "multi", label: "Multi-document" },
];

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

export default function History() {
  const navigate = useNavigate();
  const { showToast } = useToast();
  const [searchParams, setSearchParams] = useSearchParams();

  const [searchInput, setSearchInput] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [domain, setDomain] = useState("");
  const [trl, setTrl] = useState("");
  const [reviewStatus, setReviewStatus] = useState(
    () => searchParams.get("review_status") ?? "",
  );
  const [confidence, setConfidence] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [sort, setSort] = useState("created_desc");
  const [documentScope, setDocumentScope] = useState("");
  const [pendingDelete, setPendingDelete] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [exportingId, setExportingId] = useState<string | null>(null);

  // Deep links from Overview (/history?review_status=unreviewed).
  useEffect(() => {
    const fromUrl = searchParams.get("review_status") ?? "";
    setReviewStatus((current) => (current === fromUrl ? current : fromUrl));
  }, [searchParams]);

  // Debounce the search input (400 ms).
  useEffect(() => {
    const t = window.setTimeout(() => setDebouncedSearch(searchInput), 400);
    return () => window.clearTimeout(t);
  }, [searchInput]);

  const overview = useApi<OverviewResponse>("/api/overview");

  const query = useMemo(() => {
    const params = new URLSearchParams();
    if (debouncedSearch.trim()) params.set("search", debouncedSearch.trim());
    if (domain) params.set("domain", domain);
    if (trl) params.set("trl", trl);
    if (reviewStatus) params.set("review_status", reviewStatus);
    if (dateFrom) params.set("date_from", dateFrom);
    if (dateTo) params.set("date_to", dateTo);
    if (sort) params.set("sort", sort);
    if (confidence === "high") params.set("confidence_min", "0.7");
    if (confidence === "medium") {
      params.set("confidence_min", "0.45");
      params.set("confidence_max", "0.6999");
    }
    if (confidence === "low") params.set("confidence_max", "0.4499");
    if (confidence === "flagged") params.set("low_confidence", "true");
    const qs = params.toString();
    return `/api/assessments${qs ? `?${qs}` : ""}`;
  }, [
    debouncedSearch,
    domain,
    trl,
    reviewStatus,
    confidence,
    dateFrom,
    dateTo,
    sort,
  ]);

  const list = useApi<AssessmentListResponse>(query);

  const hasActiveFilters = Boolean(
    debouncedSearch.trim() ||
      domain ||
      trl ||
      reviewStatus ||
      confidence ||
      dateFrom ||
      dateTo ||
      documentScope ||
      sort !== "created_desc",
  );

  const changeReviewStatus = (value: string) => {
    setReviewStatus(value);
    const next = new URLSearchParams(searchParams);
    if (value) next.set("review_status", value);
    else next.delete("review_status");
    setSearchParams(next, { replace: true });
  };

  const clearFilters = () => {
    setSearchInput("");
    setDebouncedSearch("");
    setDomain("");
    setTrl("");
    changeReviewStatus("");
    setConfidence("");
    setDateFrom("");
    setDateTo("");
    setSort("created_desc");
    setDocumentScope("");
  };

  const doExport = async (
    id: string,
    kind: "pdf" | "json",
    name: string,
  ) => {
    setExportingId(`${id}-${kind}`);
    try {
      // The PDF endpoint is /report (not /pdf); JSON uses /json.
      const endpoint = kind === "pdf" ? "report" : "json";
      await downloadFile(`/api/assessments/${id}/${endpoint}`, `${name}.${kind}`);
      showToast(kind === "pdf" ? "PDF report downloaded" : "JSON exported");
    } catch (err) {
      showToast(errorMessage(err), "error");
    } finally {
      setExportingId(null);
    }
  };

  const confirmDelete = async () => {
    if (!pendingDelete) return;
    setDeleting(true);
    try {
      await apiDelete(`/api/assessments/${pendingDelete}`);
      showToast("Assessment deleted");
      setPendingDelete(null);
      list.refetch();
      overview.refetch();
    } catch (err) {
      showToast(errorMessage(err), "error");
    } finally {
      setDeleting(false);
    }
  };

  const loadedItems = list.data?.items ?? [];
  const items = useMemo(() => {
    if (!documentScope) return loadedItems;
    return loadedItems.filter((item) => {
      const count = item.document_count ?? 1;
      return documentScope === "multi" ? count > 1 : count <= 1;
    });
  }, [loadedItems, documentScope]);

  const domains = overview.data?.domains ?? [];
  const reviews = overview.data?.reviews;

  const renderBody = () => {
    if (list.loading && !list.data) {
      return (
        <div className="space-y-2 p-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-14 w-full" />
          ))}
        </div>
      );
    }
    if (list.error && !list.data) {
      return (
        <div className="p-4">
          <ErrorBanner
            message={list.error}
            networkError={list.networkError}
            onRetry={list.refetch}
          />
        </div>
      );
    }
    if (items.length === 0) {
      return hasActiveFilters ? (
        <div className="p-4">
          <EmptyState
            title="No assessments match your filters"
            description="Try a different search term, domain, review status or confidence band — or clear the filters to see everything."
            actionLabel="Clear filters"
            onAction={clearFilters}
          />
        </div>
      ) : (
        <div className="p-4">
          <EmptyState
            icon={HistoryIcon}
            title="No assessments yet"
            description="Once you analyse your first technology document, every assessment will be listed here with its TRL, confidence and exports."
            actionLabel="Start with New Assessment"
            actionTo="/new"
          />
        </div>
      );
    }

    return (
      <div className="scrollbar-thin overflow-x-auto">
        <table className="w-full min-w-[1080px] text-left text-sm">
          <thead>
            <tr className="border-b border-line bg-panel/50 text-[11px] uppercase tracking-[0.12em] text-faint">
              <th className="px-4 py-3 font-semibold">Technology</th>
              <th className="px-3 py-3 font-semibold">Domain</th>
              <th className="px-3 py-3 font-semibold">TRL</th>
              <th className="px-3 py-3 font-semibold">Confidence</th>
              <th className="px-3 py-3 font-semibold">Coverage</th>
              <th className="px-3 py-3 font-semibold">Docs</th>
              <th className="px-3 py-3 font-semibold">Review</th>
              <th className="px-3 py-3 font-semibold">Date</th>
              <th className="px-4 py-3 text-right font-semibold">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line/70">
            {items.map((a) => (
              <tr key={a.id} className="transition-colors hover:bg-teal-50/30">
                <td className="max-w-56 px-4 py-3.5">
                  <button
                    type="button"
                    onClick={() => navigate(`/assessments/${a.id}`)}
                    className="block truncate text-left font-semibold text-ink hover:text-primary hover:underline"
                  >
                    {a.technology_name || "Untitled technology"}
                  </button>
                  <span className="block truncate text-xs text-faint">
                    {a.organization || a.filename || "No organization"}
                  </span>
                </td>
                <td className="whitespace-nowrap px-3 py-3.5 text-muted">
                  {a.domain || "—"}
                </td>
                <td className="px-3 py-3.5">
                  {a.predicted_trl !== null ? (
                    <span className="inline-flex items-center gap-1.5">
                      <span className="rounded-lg bg-gradient-to-br from-teal-500 to-teal-700 px-2 py-0.5 text-xs font-bold text-white shadow-sm">
                        {a.predicted_trl}
                      </span>
                      <span className="text-xs text-faint">TRL</span>
                    </span>
                  ) : (
                    "—"
                  )}
                  {(a.contradictions_total ?? 0) > 0 && (
                    <span className="mt-1 block text-[10px] font-semibold text-rose-600">
                      {a.contradictions_total} contradiction
                      {a.contradictions_total === 1 ? "" : "s"}
                    </span>
                  )}
                </td>
                <td className="px-3 py-3.5">
                  <div className="w-28">
                    <ConfidenceBar value={a.confidence ?? 0} />
                  </div>
                  {a.low_confidence && (
                    <span className="mt-1 block text-[11px] font-medium text-warning">
                      Low confidence
                    </span>
                  )}
                </td>
                <td className="px-3 py-3.5 text-muted">
                  {formatPercent(a.evidence_coverage, 0)}
                </td>
                <td className="px-3 py-3.5">
                  <span className="inline-flex items-center gap-1 text-xs text-muted">
                    <FileText className="h-3.5 w-3.5 text-faint" />
                    {a.document_count ?? 1}
                  </span>
                </td>
                <td className="px-3 py-3.5">
                  <ReviewBadge status={a.review_status} />
                  {a.latest_review_decision && (
                    <span className="mt-1 block text-[10px] text-faint">
                      {a.latest_review_decision.replace(/_/g, " ")}
                    </span>
                  )}
                </td>
                <td className="whitespace-nowrap px-3 py-3.5 text-muted">
                  {formatDate(a.created_at)}
                </td>
                <td className="px-4 py-3.5">
                  <div className="flex items-center justify-end gap-1">
                    <button
                      type="button"
                      onClick={() => navigate(`/assessments/${a.id}`)}
                      title="Open assessment"
                      aria-label={`Open ${a.technology_name || "Untitled technology"}`}
                      className="rounded-lg p-2 text-muted transition-colors hover:bg-teal-50 hover:text-primary"
                    >
                      <Eye className="h-4 w-4" />
                    </button>
                    <button
                      type="button"
                      onClick={() =>
                        void doExport(a.id, "pdf", a.technology_name || a.id)
                      }
                      title="Download PDF"
                      aria-label={`Download PDF for ${a.technology_name || "Untitled technology"}`}
                      disabled={exportingId !== null}
                      className="rounded-lg p-2 text-muted transition-colors hover:bg-teal-50 hover:text-primary disabled:opacity-50"
                    >
                      {exportingId === `${a.id}-pdf` ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <FileText className="h-4 w-4" />
                      )}
                    </button>
                    <button
                      type="button"
                      onClick={() =>
                        void doExport(a.id, "json", a.technology_name || a.id)
                      }
                      title="Export JSON"
                      aria-label={`Export JSON for ${a.technology_name || "Untitled technology"}`}
                      disabled={exportingId !== null}
                      className="rounded-lg p-2 text-muted transition-colors hover:bg-slate-100 hover:text-ink disabled:opacity-50"
                    >
                      {exportingId === `${a.id}-json` ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <FileJson className="h-4 w-4" />
                      )}
                    </button>
                    <button
                      type="button"
                      onClick={() => setPendingDelete(a.id)}
                      title="Delete assessment"
                      aria-label={`Delete ${a.technology_name || "Untitled technology"}`}
                      className="rounded-lg p-2 text-muted transition-colors hover:bg-rose-50 hover:text-danger"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  };

  return (
    <div>
      <PageHeader
        title="Assessment History"
        subtitle="Every TRL assessment stored in this workspace — search, filter, export or delete."
        actions={
          list.data ? (
            <span className="chip">
              <HistoryIcon className="h-3.5 w-3.5 text-primary" />
              {documentScope ? items.length : list.data.total}{" "}
              {documentScope
                ? "shown"
                : `result${list.data.total === 1 ? "" : "s"}`}
            </span>
          ) : undefined
        }
      />

      {reviews && (
        <div className="mb-4 flex flex-wrap gap-2">
          {[
            ["Unreviewed", reviews.unreviewed, "unreviewed"],
            ["Accepted", reviews.accepted, "accepted"],
            ["Overridden", reviews.overridden, "overridden"],
            ["More evidence", reviews.more_evidence_requested, "more_evidence_requested"],
          ].map(([label, count, value]) => (
            <button
              key={value}
              type="button"
              onClick={() => changeReviewStatus(value as string)}
              className={`rounded-full border px-3 py-1 text-xs font-semibold transition-colors ${
                reviewStatus === value
                  ? "border-primary bg-teal-50 text-primary-dark"
                  : "border-line bg-white text-muted hover:bg-panel"
              }`}
            >
              {label} <span className="tabular-nums">{count}</span>
            </button>
          ))}
        </div>
      )}

      <div className="mb-4">
        <FilterBar
          searchValue={searchInput}
          onSearchChange={setSearchInput}
          searchPlaceholder="Search by name, domain or organization…"
          fields={[
            {
              key: "domain",
              label: "Domain",
              value: domain,
              options: domains.map((d) => ({ value: d, label: d })),
              onChange: setDomain,
            },
            {
              key: "trl",
              label: "TRL",
              value: trl,
              options: TRL_OPTIONS,
              onChange: setTrl,
            },
            {
              key: "review",
              label: "Review status",
              value: reviewStatus,
              options: REVIEW_OPTIONS,
              onChange: changeReviewStatus,
            },
            {
              key: "confidence",
              label: "Confidence",
              value: confidence,
              options: CONFIDENCE_OPTIONS,
              onChange: setConfidence,
            },
            {
              key: "documents",
              label: "Documents",
              value: documentScope,
              options: DOCUMENT_OPTIONS,
              onChange: setDocumentScope,
            },
            {
              key: "sort",
              label: "Sort",
              value: sort,
              options: SORT_OPTIONS,
              onChange: setSort,
            },
          ]}
          extra={
            <>
              <div className="min-w-36">
                <label htmlFor="history-date-from" className="label">
                  From
                </label>
                <input
                  id="history-date-from"
                  type="date"
                  value={dateFrom}
                  max={dateTo || undefined}
                  onChange={(e) => setDateFrom(e.target.value)}
                  className="input py-2"
                />
              </div>
              <div className="min-w-36">
                <label htmlFor="history-date-to" className="label">
                  To
                </label>
                <input
                  id="history-date-to"
                  type="date"
                  value={dateTo}
                  min={dateFrom || undefined}
                  onChange={(e) => setDateTo(e.target.value)}
                  className="input py-2"
                />
              </div>
            </>
          }
          onClear={clearFilters}
          hasActiveFilters={hasActiveFilters}
        />
      </div>

      {documentScope && list.data && (
        <p className="mb-2 text-xs text-faint">
          Document-count filter applies to the loaded rows (
          {list.data.items.length} of {list.data.total} returned by the server).
        </p>
      )}

      <div className="card overflow-hidden">
        {list.loading && list.data && (
          <div className="flex items-center gap-2 border-b border-line bg-panel/60 px-4 py-2 text-xs text-muted">
            <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />
            Updating results…
          </div>
        )}
        {list.error && list.data && (
          <div className="border-b border-line px-4 py-3">
            <ErrorBanner
              message={list.error}
              networkError={list.networkError}
              onRetry={list.refetch}
            />
          </div>
        )}
        {renderBody()}
      </div>

      <ConfirmDialog
        open={pendingDelete !== null}
        title="Delete assessment?"
        message="This permanently removes the assessment result from the local database. The uploaded document stays on disk. This cannot be undone."
        confirmLabel="Delete"
        busy={deleting}
        onConfirm={() => void confirmDelete()}
        onCancel={() => setPendingDelete(null)}
      />
    </div>
  );
}
