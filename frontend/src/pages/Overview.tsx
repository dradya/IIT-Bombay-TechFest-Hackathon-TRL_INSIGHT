import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  ArrowRight,
  ArrowUpRight,
  BarChart3,
  ClipboardList,
  Gauge,
  Globe2,
  Layers,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  TrendingUp,
} from "lucide-react";
import { useApi } from "../hooks/useApi";
import type { OverviewResponse } from "../types";
import PageHeader from "../components/PageHeader";
import StatCard from "../components/StatCard";
import ConfidenceRing from "../components/ConfidenceRing";
import EmptyState from "../components/EmptyState";
import ErrorBanner from "../components/ErrorBanner";
import FilterBar from "../components/FilterBar";
import StatusBadge from "../components/StatusBadge";
import Skeleton from "../components/Skeleton";
import TRLDistributionChart from "../components/TRLDistributionChart";
import {
  formatDateTime,
  formatNumber,
  formatPercent,
  timeAgo,
} from "../utils/format";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const TEAL = "#0D9488";

const tooltipStyle = {
  borderRadius: 12,
  border: "1px solid #E5EAF2",
  boxShadow: "0 18px 40px -24px rgba(10,22,40,0.45)",
  fontSize: 12,
  padding: "8px 10px",
} as const;

export default function Overview() {
  const navigate = useNavigate();
  const [domain, setDomain] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const query = useMemo(() => {
    const params = new URLSearchParams();
    if (domain) params.set("domain", domain);
    if (dateFrom) params.set("date_from", dateFrom);
    if (dateTo) params.set("date_to", dateTo);
    const qs = params.toString();
    return `/api/overview${qs ? `?${qs}` : ""}`;
  }, [domain, dateFrom, dateTo]);

  const { data, loading, error, networkError, refetch } =
    useApi<OverviewResponse>(query);

  const hasActiveFilters = Boolean(domain || dateFrom || dateTo);
  const clearFilters = () => {
    setDomain("");
    setDateFrom("");
    setDateTo("");
  };

  if (loading && !data) {
    return (
      <div>
        <PageHeader
          title="Overview"
          subtitle="Portfolio-wide technology readiness snapshot"
        />
        <Skeleton className="h-64 w-full rounded-[1.5rem]" />
        <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="card p-5">
              <Skeleton className="h-3 w-24" />
              <Skeleton className="mt-3 h-8 w-32" />
            </div>
          ))}
        </div>
        <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
          <div className="card p-5">
            <Skeleton className="h-56 w-full" />
          </div>
          <div className="card p-5">
            <Skeleton className="h-56 w-full" />
          </div>
        </div>
      </div>
    );
  }

  if (error && !data) {
    return (
      <div>
        <PageHeader
          title="Overview"
          subtitle="Portfolio-wide technology readiness snapshot"
        />
        <ErrorBanner message={error} networkError={networkError} onRetry={refetch} />
      </div>
    );
  }

  if (!data) return null;

  // Empty state — the API has no assessments yet: never render fake numbers.
  if (!data.has_data) {
    return (
      <div>
        <PageHeader
          title="Overview"
          subtitle="Portfolio-wide technology readiness snapshot"
        />
        <div className={`mb-4 ${hasActiveFilters ? "" : "hidden"}`}>
          <FilterBar
            searchValue=""
            onSearchChange={() => undefined}
            showSearch={false}
            fields={[]}
            extra={
              <OverviewDateFilters
                dateFrom={dateFrom}
                dateTo={dateTo}
                onFrom={setDateFrom}
                onTo={setDateTo}
              />
            }
            onClear={clearFilters}
            hasActiveFilters={hasActiveFilters}
          />
        </div>
        {hasActiveFilters ? (
          <EmptyState
            icon={ClipboardList}
            title="No assessments match these filters"
            description="No stored assessment falls inside the selected domain or date range. Widen the filters to see the full portfolio."
            actionLabel="Clear filters"
            onAction={clearFilters}
          />
        ) : (
          <EmptyState
            icon={ClipboardList}
            title="No assessments yet"
            description="Upload a technical document and run your first TRL assessment. Statistics, charts and history will appear here once results exist."
            actionLabel="Start with New Assessment"
            actionTo="/new"
          />
        )}
      </div>
    );
  }

  // Trend: assessments ordered by date with their predicted TRL.
  const trend = data.recent
    .slice()
    .sort(
      (a, b) =>
        new Date(a.created_at).getTime() - new Date(b.created_at).getTime(),
    )
    .map((a, i) => ({
      index: i + 1,
      trl: a.predicted_trl ?? 0,
      label: a.technology_name,
      date: formatDateTime(a.created_at),
    }));

  const confidenceBands = [
    {
      name: "High ≥ 70%",
      count: data.confidence.high,
      bar: "bg-gradient-to-r from-teal-500 to-cyan-400",
    },
    {
      name: "Medium 45–69%",
      count: data.confidence.medium,
      bar: "bg-gradient-to-r from-blue-500 to-indigo-500",
    },
    {
      name: "Low < 45%",
      count: data.confidence.low,
      bar: "bg-gradient-to-r from-amber-400 to-orange-500",
    },
  ];

  const coverage = data.coverage;
  const coverageBands = coverage
    ? [
        {
          name: "High ≥ 70%",
          count: coverage.high,
          bar: "bg-gradient-to-r from-emerald-500 to-teal-400",
        },
        {
          name: "Medium 40–69%",
          count: coverage.medium,
          bar: "bg-gradient-to-r from-cyan-500 to-blue-400",
        },
        {
          name: "Low < 40%",
          count: coverage.low,
          bar: "bg-gradient-to-r from-amber-400 to-orange-500",
        },
      ]
    : [];

  const domainRows = data.domain_distribution ?? [];
  const domainMax = Math.max(1, ...domainRows.map((d) => d.count));
  const reviews = data.reviews;
  const unreviewed = reviews?.unreviewed ?? reviews?.awaiting_review ?? 0;

  const avgConfidence = data.average_confidence ?? data.confidence.average ?? 0;
  const avgTrl = data.average_trl ?? 0;
  const avgTrlPct = Math.max(0, Math.min(100, (avgTrl / 9) * 100));

  return (
    <div>
      <PageHeader
        title="Overview"
        subtitle="Portfolio-wide technology readiness snapshot"
        actions={
          <button
            type="button"
            onClick={() => navigate("/new")}
            className="btn btn-primary"
          >
            <Sparkles className="h-4 w-4" />
            New assessment
          </button>
        }
      />

      {error && (
        <div className="mb-4">
          <ErrorBanner
            message={error}
            networkError={networkError}
            onRetry={refetch}
          />
        </div>
      )}

      <div className="mb-4">
        <FilterBar
          searchValue=""
          onSearchChange={() => undefined}
          showSearch={false}
          fields={[
            {
              key: "domain",
              label: "Domain",
              value: domain,
              options: (data.domains ?? []).map((d) => ({ value: d, label: d })),
              onChange: setDomain,
            },
          ]}
          extra={
            <OverviewDateFilters
              dateFrom={dateFrom}
              dateTo={dateTo}
              onFrom={setDateFrom}
              onTo={setDateTo}
            />
          }
          onClear={clearFilters}
          hasActiveFilters={hasActiveFilters}
        />
      </div>

      {/* Portfolio readiness hero */}
      <section className="relative overflow-hidden rounded-[1.5rem] border border-white/10 bg-gradient-to-br from-[#061326] via-[#081d38] to-[#0b2444] p-6 text-white shadow-[0_30px_70px_-40px_rgba(6,19,38,0.9)] sm:p-8">
        <div className="pointer-events-none absolute inset-0">
          <div className="absolute inset-0 bg-grid opacity-[0.12]" />
          <div className="absolute -left-24 -top-28 h-80 w-80 rounded-full bg-teal-400/20 blur-3xl" />
          <div className="absolute -bottom-32 right-0 h-80 w-80 rounded-full bg-blue-500/20 blur-3xl" />
        </div>

        <div className="relative grid items-center gap-8 lg:grid-cols-[1.7fr_auto]">
          <div className="min-w-0">
            <div className="flex items-center gap-2.5">
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-teal-300 opacity-70" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-teal-300" />
              </span>
              <span className="text-[11px] font-bold uppercase tracking-[0.18em] text-teal-200/90">
                Portfolio readiness
              </span>
            </div>

            <h2 className="mt-3 max-w-2xl font-display text-[26px] font-semibold leading-tight tracking-tight text-white sm:text-[32px]">
              Readiness across{" "}
              <span className="text-teal-300">
                {data.total_assessments} assessed{" "}
                {data.total_assessments === 1 ? "technology" : "technologies"}
              </span>
            </h2>
            <p className="mt-2 max-w-xl text-sm leading-relaxed text-slate-300/90">
              {hasActiveFilters
                ? "Filtered view. Only assessments matching the selected domain and dates are included."
                : "Evidence-based estimates from your stored documents. Nothing here is inferred beyond the model and rule output."}
            </p>

            <div className="mt-7 flex flex-wrap items-end gap-x-10 gap-y-6">
              <div>
                <div className="flex items-end gap-2">
                  <span className="stat-value text-[52px] font-bold leading-none text-white">
                    {formatNumber(data.average_trl, 1)}
                  </span>
                  <span className="mb-1.5 text-sm font-semibold text-slate-400">
                    / 9
                  </span>
                </div>
                <p className="mt-1.5 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">
                  Mean predicted TRL
                </p>
                <div className="mt-3 h-1.5 w-44 overflow-hidden rounded-full bg-white/10">
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-teal-400 to-cyan-300 shadow-[0_0_14px_rgba(45,212,191,0.7)]"
                    style={{ width: `${avgTrlPct}%` }}
                  />
                </div>
              </div>

              <div className="flex flex-wrap gap-2">
                <HeroChip
                  icon={Layers}
                  label="Assessments"
                  value={String(data.total_assessments)}
                />
                <HeroChip
                  icon={TrendingUp}
                  label="Avg confidence"
                  value={formatPercent(avgConfidence, 0)}
                />
                <HeroChip
                  icon={Globe2}
                  label="Domains"
                  value={String(data.domains.length)}
                />
                <HeroChip
                  icon={ShieldAlert}
                  label="Low confidence"
                  value={String(data.confidence.low)}
                  tone="amber"
                />
                <HeroChip
                  icon={ShieldCheck}
                  label="Awaiting review"
                  value={String(unreviewed)}
                  tone="amber"
                />
              </div>
            </div>
          </div>

          <div className="flex justify-center lg:justify-end">
            <div className="relative rounded-full border border-white/10 bg-white/[0.04] p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.08)]">
              <ConfidenceRing
                value={avgConfidence}
                label="Avg confidence"
                size={168}
                onDark
              />
            </div>
          </div>
        </div>
      </section>

      {/* Stat cards */}
      <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Total assessments"
          value={String(data.total_assessments)}
          icon={Layers}
          hint="Stored in the local database"
        />
        <StatCard
          label="Average predicted TRL"
          value={formatNumber(data.average_trl, 1)}
          icon={Gauge}
          tone="blue"
          hint="Mean of predicted levels"
        />
        <StatCard
          label="Average confidence"
          value={formatPercent(avgConfidence, 0)}
          icon={BarChart3}
          tone="green"
          hint="Model / rule confidence"
        />
        <StatCard
          label="Awaiting expert review"
          value={String(unreviewed)}
          icon={ClipboardList}
          tone="amber"
          hint="Assessments without a recorded review"
        />
      </div>

      {/* Charts row */}
      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="card p-5">
          <div className="mb-4 flex items-start justify-between gap-3">
            <div>
              <h2 className="section-title">TRL distribution</h2>
              <p className="mt-0.5 text-xs text-faint">
                Assessments per readiness level (1–9)
              </p>
            </div>
            <span className="icon-tile h-9 w-9">
              <BarChart3 className="h-4 w-4" />
            </span>
          </div>
          <TRLDistributionChart distribution={data.distribution} height={224} />
        </div>

        <div className="card p-5">
          <div className="mb-4 flex items-start justify-between gap-3">
            <div>
              <h2 className="section-title">Technology assessment trend</h2>
              <p className="mt-0.5 text-xs text-faint">
                Predicted TRL of recent assessments, ordered by date
              </p>
            </div>
            <span className="icon-tile h-9 w-9">
              <TrendingUp className="h-4 w-4" />
            </span>
          </div>
          <div className="h-56">
            {trend.length === 0 ? (
              <div className="flex h-full items-center justify-center text-sm text-faint">
                No data points yet.
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart
                  data={trend}
                  margin={{ top: 8, right: 12, left: -18, bottom: 0 }}
                >
                  <CartesianGrid
                    strokeDasharray="4 6"
                    stroke="#EDF1F7"
                    vertical={false}
                  />
                  <XAxis
                    dataKey="index"
                    tick={{ fontSize: 11, fill: "#8a97a8" }}
                    tickFormatter={(v: number) => `#${v}`}
                    allowDecimals={false}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    domain={[0, 9]}
                    ticks={[1, 3, 5, 7, 9]}
                    tick={{ fontSize: 11, fill: "#8a97a8" }}
                    width={40}
                    axisLine={false}
                    tickLine={false}
                  />
                  <ReferenceLine y={5} stroke="#CBD5E1" strokeDasharray="4 4" />
                  <Tooltip
                    contentStyle={tooltipStyle}
                    labelFormatter={(v) => `Assessment #${v}`}
                    formatter={(value, _name, item) => {
                      const payload = item?.payload as
                        | { label?: string; date?: string }
                        | undefined;
                      return [
                        `TRL ${value}`,
                        payload?.label ?? "",
                        payload?.date ?? "",
                      ];
                    }}
                  />
                  <Line
                    type="monotone"
                    dataKey="trl"
                    stroke={TEAL}
                    strokeWidth={2.5}
                    dot={{
                      r: 4,
                      fill: "#fff",
                      stroke: TEAL,
                      strokeWidth: 2,
                    }}
                    activeDot={{ r: 6, stroke: TEAL, strokeWidth: 2, fill: "#fff" }}
                    name="Predicted TRL"
                  />
                </LineChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>
      </div>

      {/* Confidence + coverage + domains */}
      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="card p-5">
          <h2 className="section-title">Confidence overview</h2>
          <p className="mt-0.5 text-xs text-faint">
            High ≥ 70% · Medium 45–69% · Low &lt; 45%
          </p>
          <div className="flex items-center justify-center py-3">
            <ConfidenceRing
              value={avgConfidence}
              label="Avg confidence"
              size={116}
            />
          </div>
          <div className="space-y-3.5">
            {confidenceBands.map((b) => (
              <div key={b.name}>
                <div className="mb-1.5 flex items-center justify-between text-xs">
                  <span className="text-muted">{b.name}</span>
                  <span className="font-semibold tabular-nums text-ink">
                    {b.count}
                  </span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-slate-100">
                  <div
                    className={`h-full rounded-full transition-[width] duration-500 ${b.bar}`}
                    style={{
                      width: `${
                        data.total_assessments > 0
                          ? (b.count / data.total_assessments) * 100
                          : 0
                      }%`,
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="card p-5">
          <h2 className="section-title">Evidence coverage</h2>
          <p className="mt-0.5 text-xs text-faint">
            Share of required milestones backed by confirmed evidence
          </p>
          {coverage ? (
            <>
              <p className="mt-3 text-3xl font-bold text-ink">
                {formatPercent(coverage.average, 0)}
              </p>
              <p className="text-[11px] text-faint">Portfolio average coverage</p>
              <div className="mt-4 space-y-3.5">
                {coverageBands.map((b) => (
                  <div key={b.name}>
                    <div className="mb-1.5 flex items-center justify-between text-xs">
                      <span className="text-muted">{b.name}</span>
                      <span className="font-semibold tabular-nums text-ink">
                        {b.count}
                      </span>
                    </div>
                    <div className="h-2 overflow-hidden rounded-full bg-slate-100">
                      <div
                        className={`h-full rounded-full transition-[width] duration-500 ${b.bar}`}
                        style={{
                          width: `${
                            data.total_assessments > 0
                              ? (b.count / data.total_assessments) * 100
                              : 0
                          }%`,
                        }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <p className="mt-4 text-sm text-faint">
              Coverage buckets are not available for this result set.
            </p>
          )}
        </div>

        <div className="card p-5">
          <h2 className="section-title">Domain distribution</h2>
          <p className="mt-0.5 text-xs text-faint">
            Assessments grouped by recorded technology domain
          </p>
          {domainRows.length === 0 ? (
            <p className="mt-4 text-sm text-faint">
              No domain metadata was recorded for these assessments.
            </p>
          ) : (
            <ul className="mt-4 space-y-3">
              {domainRows.slice(0, 7).map((row) => (
                <li key={row.domain}>
                  <div className="mb-1 flex items-center justify-between gap-2 text-xs">
                    <span className="truncate text-muted" title={row.domain}>
                      {row.domain}
                    </span>
                    <span className="font-semibold tabular-nums text-ink">
                      {row.count}
                    </span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-slate-100">
                    <div
                      className="h-full rounded-full bg-gradient-to-r from-teal-500 to-cyan-400"
                      style={{ width: `${(row.count / domainMax) * 100}%` }}
                    />
                  </div>
                </li>
              ))}
            </ul>
          )}
          <button
            type="button"
            onClick={() => navigate("/history")}
            className="mt-4 inline-flex items-center gap-1 text-xs font-semibold text-primary hover:text-primary-dark"
          >
            Browse all assessments
            <ArrowRight className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      {/* Review queue */}
      <div className="card mt-4 p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="section-title">Expert review queue</h2>
            <p className="mt-0.5 text-xs text-faint">
              Review status is derived from recorded expert decisions; the AI
              prediction itself is never overwritten.
            </p>
          </div>
          <button
            type="button"
            onClick={() => navigate("/history?review_status=unreviewed")}
            className="btn btn-secondary btn-sm"
          >
            <ClipboardList className="h-3.5 w-3.5" />
            Review unreviewed
          </button>
        </div>
        {reviews ? (
          <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
            {[
              {
                label: "Unreviewed",
                value: reviews.unreviewed,
                status: "unreviewed",
                tone: "text-amber-700",
              },
              {
                label: "Accepted",
                value: reviews.accepted,
                status: "accepted",
                tone: "text-emerald-700",
              },
              {
                label: "Overridden",
                value: reviews.overridden,
                status: "overridden",
                tone: "text-blue-700",
              },
              {
                label: "More evidence",
                value: reviews.more_evidence_requested,
                status: "more_evidence_requested",
                tone: "text-rose-700",
              },
            ].map((item) => (
              <button
                key={item.label}
                type="button"
                onClick={() =>
                  navigate(`/history?review_status=${item.status}`)
                }
                className="panel px-3 py-3 text-left transition-colors hover:bg-teal-50/40"
              >
                <p className="text-[10px] font-semibold uppercase tracking-wide text-faint">
                  {item.label}
                </p>
                <p className={`mt-1 text-2xl font-bold ${item.tone}`}>
                  {item.value}
                </p>
              </button>
            ))}
          </div>
        ) : (
          <p className="mt-4 text-sm text-faint">
            Review aggregates are unavailable for this result set.
          </p>
        )}
      </div>

      {/* Recent + activity */}
      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* Recently assessed */}
        <div className="card p-5">
          <div className="mb-2 flex items-center justify-between">
            <h2 className="section-title">Recently assessed</h2>
            <button
              type="button"
              onClick={() => navigate("/history")}
              className="inline-flex items-center gap-1 text-xs font-semibold text-primary hover:text-primary-dark"
            >
              View all
              <ArrowRight className="h-3.5 w-3.5" />
            </button>
          </div>
          {data.recent.length === 0 ? (
            <p className="py-6 text-center text-sm text-faint">
              No recent assessments.
            </p>
          ) : (
            <ul className="divide-y divide-line/70">
              {data.recent.slice(0, 6).map((a) => (
                <li key={a.id}>
                  <button
                    type="button"
                    onClick={() => navigate(`/assessments/${a.id}`)}
                    className="group -mx-2 flex w-full items-center gap-3 rounded-xl px-2 py-2.5 text-left transition-colors hover:bg-teal-50/50"
                  >
                    <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-teal-200/70 bg-teal-50 text-xs font-bold text-primary-dark">
                      {a.predicted_trl ?? "–"}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-semibold text-ink">
                        {a.technology_name || "Untitled technology"}
                      </span>
                      <span className="block truncate text-xs text-faint">
                        {a.domain || "No domain"} ·{" "}
                        {formatPercent(a.confidence, 0)} confidence
                        {a.document_count && a.document_count > 1
                          ? ` · ${a.document_count} docs`
                          : ""}
                      </span>
                    </span>
                    {a.review_status && a.review_status !== "unreviewed" && (
                      <StatusBadge
                        kind="custom"
                        value=""
                        tone="green"
                        label={
                          a.review_status === "accepted"
                            ? "Accepted"
                            : a.review_status === "overridden"
                              ? "Overridden"
                              : "More evidence"
                        }
                      />
                    )}
                    <ArrowUpRight className="h-4 w-4 shrink-0 text-slate-300 transition-colors group-hover:text-primary" />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Activity feed */}
        <div className="card p-5">
          <h2 className="section-title">Recent activity</h2>
          {data.activity.length === 0 ? (
            <p className="py-6 text-center text-sm text-faint">
              No activity yet.
            </p>
          ) : (
            <ol className="relative mt-3 space-y-4 border-l border-line pl-4">
              {data.activity.slice(0, 8).map((item) => (
                <li key={`${item.id}-${item.created_at}`} className="relative">
                  <span className="absolute -left-[21px] top-1.5 h-2.5 w-2.5 rounded-full border-2 border-white bg-gradient-to-br from-teal-400 to-cyan-400 shadow-[0_0_0_3px_rgba(13,148,136,0.08)]" />
                  <button
                    type="button"
                    onClick={() => navigate(`/assessments/${item.id}`)}
                    className="block w-full text-left"
                  >
                    <p className="text-sm leading-relaxed text-ink-soft">
                      <span className="font-semibold text-ink">
                        {item.technology_name}
                      </span>{" "}
                      assessed at{" "}
                      {item.predicted_trl !== null ? (
                        <StatusBadge
                          kind="custom"
                          value=""
                          tone="teal"
                          label={`TRL ${item.predicted_trl}`}
                        />
                      ) : (
                        "—"
                      )}
                    </p>
                    <p className="mt-1 text-xs text-faint">
                      {timeAgo(item.created_at)} ·{" "}
                      {formatDateTime(item.created_at)}
                    </p>
                  </button>
                </li>
              ))}
            </ol>
          )}
        </div>
      </div>
    </div>
  );
}

function HeroChip({
  icon: Icon,
  label,
  value,
  tone = "teal",
}: {
  icon: typeof Layers;
  label: string;
  value: string;
  tone?: "teal" | "amber";
}) {
  return (
    <div
      className={`rounded-xl border px-3 py-2 ${
        tone === "amber"
          ? "border-amber-300/25 bg-amber-300/[0.07]"
          : "border-white/10 bg-white/[0.04]"
      }`}
    >
      <div className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-400">
        <Icon className="h-3 w-3" />
        {label}
      </div>
      <p
        className={`mt-1 text-sm font-bold ${
          tone === "amber" ? "text-amber-200" : "text-white"
        }`}
      >
        {value}
      </p>
    </div>
  );
}

function OverviewDateFilters({
  dateFrom,
  dateTo,
  onFrom,
  onTo,
}: {
  dateFrom: string;
  dateTo: string;
  onFrom: (value: string) => void;
  onTo: (value: string) => void;
}) {
  return (
    <>
      <div className="min-w-36">
        <label htmlFor="overview-date-from" className="label">
          From
        </label>
        <input
          id="overview-date-from"
          type="date"
          value={dateFrom}
          max={dateTo || undefined}
          onChange={(e) => onFrom(e.target.value)}
          className="input py-2"
        />
      </div>
      <div className="min-w-36">
        <label htmlFor="overview-date-to" className="label">
          To
        </label>
        <input
          id="overview-date-to"
          type="date"
          value={dateTo}
          min={dateFrom || undefined}
          onChange={(e) => onTo(e.target.value)}
          className="input py-2"
        />
      </div>
    </>
  );
}
