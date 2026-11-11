import { useMemo } from "react";
import {
  Activity,
  BadgeCheck,
  Database,
  Info,
  Terminal,
  TrendingUp,
} from "lucide-react";
import { useApi } from "../hooks/useApi";
import type { ClassificationReportRow, ModelPerformanceResponse } from "../types";
import PageHeader from "../components/PageHeader";
import ErrorBanner from "../components/ErrorBanner";
import StatCard from "../components/StatCard";
import StatusBadge from "../components/StatusBadge";
import Skeleton from "../components/Skeleton";
import { formatDate, formatPercent } from "../utils/format";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

function fmt(value: number | undefined): string {
  if (value === undefined || value === null || Number.isNaN(value)) return "—";
  return value.toFixed(3);
}

const tooltipStyle = {
  borderRadius: 12,
  border: "1px solid #E5EAF2",
  boxShadow: "0 18px 40px -24px rgba(10,22,40,0.45)",
  fontSize: 12,
  padding: "8px 10px",
} as const;

export default function ModelPerformance() {
  const { data, loading, error, networkError, refetch } =
    useApi<ModelPerformanceResponse>("/api/model/performance");

  const classDistribution = useMemo(() => {
    if (!data) return [];
    return Object.entries(data.class_distribution)
      .map(([label, count]) => ({ name: `TRL ${label}`, count }))
      .sort((a, b) => a.name.localeCompare(b.name, undefined, { numeric: true }));
  }, [data]);

  const perClassF1 = useMemo(() => {
    if (!data) return [];
    return Object.entries(data.per_class)
      .map(([label, m]) => ({ name: `TRL ${label}`, f1: m.f1, support: m.support }))
      .sort((a, b) => a.name.localeCompare(b.name, undefined, { numeric: true }));
  }, [data]);

  if (loading && !data) {
    return (
      <div>
        <PageHeader
          title="Model Performance"
          subtitle="Real evaluation metrics — never fabricated"
        />
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="card p-5">
              <Skeleton className="h-4 w-24" />
              <Skeleton className="mt-3 h-8 w-32" />
            </div>
          ))}
        </div>
        <div className="card mt-4 p-5">
          <Skeleton className="h-64 w-full" />
        </div>
      </div>
    );
  }

  if (error && !data) {
    return (
      <div>
        <PageHeader
          title="Model Performance"
          subtitle="Real evaluation metrics — never fabricated"
        />
        <ErrorBanner message={error} networkError={networkError} onRetry={refetch} />
      </div>
    );
  }

  if (!data) return null;

  // No trained model — show the API's own note; never invent metrics.
  if (!data.available) {
    return (
      <div className="max-w-3xl">
        <PageHeader
          title="Model Performance"
          subtitle="Real evaluation metrics — never fabricated"
        />
        <div className="card p-6">
          <div className="flex items-start gap-4">
            <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-amber-400/25 to-orange-400/10 text-amber-600 ring-1 ring-inset ring-amber-500/10">
              <Info className="h-5 w-5" />
            </span>
            <div className="min-w-0">
              <h2 className="section-title">No trained model available</h2>
              <p className="mt-1.5 text-sm leading-relaxed text-muted">
                {data.note ||
                  "No trained model or evaluation data is available yet. Metrics are never fabricated."}
              </p>
              <div className="mt-4 rounded-xl border border-white/10 bg-slate-950 p-4 shadow-inner">
                <p className="mb-2 flex items-center gap-2 text-xs font-medium text-slate-400">
                  <Terminal className="h-3.5 w-3.5" />
                  Run from the project root to produce genuine metrics:
                </p>
                <pre className="scrollbar-thin overflow-x-auto font-mono text-xs leading-relaxed text-teal-300">
                  {`python training/prepare_data.py --synthetic
python training/train_model.py
python training/evaluate_model.py`}
                </pre>
              </div>
              <p className="mt-3 text-xs text-faint">
                Current mode: <strong className="text-ink-soft">{data.mode}</strong>
              </p>
              <button
                type="button"
                onClick={refetch}
                className="btn btn-secondary mt-4"
              >
                Re-check
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  const cm = data.confusion_matrix;
  const maxCell = cm ? Math.max(1, ...cm.matrix.flat()) : 1;

  const reportEntries: [string, ClassificationReportRow | number][] =
    Object.entries(data.classification_report ?? {});

  const reportRows = reportEntries.filter(
    ([key, value]) =>
      key !== "accuracy" && typeof value === "object" && value !== null,
  ) as [string, ClassificationReportRow][];

  const accuracy =
    typeof data.classification_report?.accuracy === "number"
      ? data.classification_report.accuracy
      : data.metrics.accuracy;

  return (
    <div className="max-w-6xl">
      <PageHeader
        title="Model Performance"
        subtitle="Real evaluation metrics from the last training run"
        actions={
          <StatusBadge
            kind="custom"
            value=""
            tone={data.dataset_type === "synthetic_demo" ? "amber" : "green"}
            label={
              data.dataset_type === "synthetic_demo"
                ? "Demonstration data — not a competition benchmark"
                : data.mode === "trained_evaluation"
                  ? "Trained evaluation"
                  : data.mode
            }
          />
        }
      />

      {/* Model header */}
      <div className="card mb-4 p-5">
        <div className="flex flex-wrap items-center gap-x-8 gap-y-4">
          <div className="flex items-center gap-3">
            <span className="icon-tile h-10 w-10">
              <Activity className="h-5 w-5" />
            </span>
            <div>
              <p className="eyebrow">Model</p>
              <p className="mt-0.5 text-sm font-semibold text-ink">
                {data.model_name || "—"}
                {data.model_version ? ` v${data.model_version}` : ""}
              </p>
            </div>
          </div>
          <div>
            <p className="eyebrow">Trained at</p>
            <p className="mt-0.5 text-sm text-ink-soft">
              {formatDate(data.trained_at)}
            </p>
          </div>
          <div className="min-w-0">
            <p className="eyebrow">Dataset source</p>
            <p
              className="mt-0.5 truncate text-sm text-ink-soft"
              title={data.dataset_source ?? ""}
            >
              {data.dataset_source || "—"}
            </p>
          </div>
          <div>
            <p className="eyebrow">Train / test split</p>
            <p className="mt-0.5 text-sm text-ink-soft">
              {data.n_train ?? "—"} / {data.n_test ?? "—"}
            </p>
          </div>
        </div>
        {data.note && (
          <p className="mt-4 flex items-start gap-2 rounded-xl border border-line bg-panel px-3 py-2.5 text-xs text-muted">
            <Database className="mt-0.5 h-3.5 w-3.5 shrink-0 text-faint" />
            {data.note}
          </p>
        )}
      </div>

      {/* Metric cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard
          label="Accuracy"
          value={formatPercent(data.metrics.accuracy, 1)}
          icon={Activity}
          hint={fmt(data.metrics.accuracy)}
        />
        <StatCard
          label="Macro F1"
          value={fmt(data.metrics.macro_f1)}
          icon={TrendingUp}
          tone="blue"
          hint="Unweighted mean of per-class F1"
        />
        <StatCard
          label="Weighted F1"
          value={fmt(data.metrics.weighted_f1)}
          icon={TrendingUp}
          tone="green"
          hint="Support-weighted mean of per-class F1"
        />
      </div>

      {/* Calibration — only real artefacts, never inferred. */}
      {data.calibration && Object.keys(data.calibration).length > 0 ? (
        <div className="card mt-4 p-5">
          <div className="mb-3 flex items-center gap-3">
            <span className="icon-tile h-9 w-9 shrink-0">
              <BadgeCheck className="h-4 w-4" />
            </span>
            <div>
              <h2 className="section-title">Calibration</h2>
              <p className="mt-0.5 text-xs text-faint">
                Values stored in the evaluation artefact of this exact model
              </p>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
            {Object.entries(data.calibration)
              .filter(
                ([, value]) =>
                  typeof value === "number" ||
                  typeof value === "string" ||
                  typeof value === "boolean",
              )
              .map(([key, value]) => (
                <div key={key} className="panel px-3 py-2.5">
                  <p
                    className="truncate text-[10px] font-semibold uppercase tracking-wide text-faint"
                    title={key}
                  >
                    {key.replace(/_/g, " ")}
                  </p>
                  <p className="mt-0.5 truncate text-sm font-semibold text-ink">
                    {typeof value === "number"
                      ? Number(value.toFixed(4)).toString()
                      : String(value)}
                  </p>
                </div>
              ))}
          </div>
          <p className="mt-3 text-xs leading-relaxed text-faint">
            No calibration value is inferred when the artefact does not include
            one. Raw classifier probabilities are not real-world frequencies.
          </p>
        </div>
      ) : (
        <div className="card mt-4 p-5">
          <div className="flex items-start gap-3">
            <span className="icon-tile h-9 w-9 shrink-0">
              <BadgeCheck className="h-4 w-4" />
            </span>
            <div className="min-w-0">
              <h2 className="section-title">Calibration</h2>
              <p className="mt-1 text-sm leading-relaxed text-muted">
                No calibration artefact is bundled with this model, so no
                calibrated probabilities are reported. Confidence describes
                model/rule agreement and evidence coverage — it is not a
                real-world probability of readiness. Calibration will appear
                here only when a genuine held-out calibration artefact exists.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Confusion matrix */}
      <div className="card mt-4 overflow-hidden">
        <div className="flex items-center gap-3 border-b border-line px-5 py-4">
          <span className="icon-tile h-9 w-9 shrink-0">
            <Activity className="h-4 w-4" />
          </span>
          <div>
            <h2 className="section-title">Confusion matrix</h2>
            <p className="mt-0.5 text-xs text-faint">
              Rows = true label · Columns = predicted label (9 × 9)
            </p>
          </div>
        </div>
        <div className="scrollbar-thin overflow-x-auto p-5">
          {cm ? (
            <table className="border-separate border-spacing-1 text-center text-xs">
              <thead>
                <tr>
                  <th className="px-2 py-1 text-left text-[11px] font-semibold uppercase tracking-[0.12em] text-faint">
                    true \ pred
                  </th>
                  {cm.labels.map((l) => (
                    <th
                      key={l}
                      className="h-7 w-9 rounded bg-panel font-semibold text-muted"
                    >
                      {l}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {cm.matrix.map((row, i) => (
                  <tr key={i}>
                    <th className="w-16 rounded bg-panel px-2 py-1 text-right font-semibold text-muted">
                      TRL {cm.labels[i]}
                    </th>
                    {row.map((value, j) => {
                      const alpha =
                        value === 0 ? 0 : 0.12 + (value / maxCell) * 0.85;
                      const isDiagonal = i === j;
                      return (
                        <td
                          key={j}
                          title={`True TRL ${cm.labels[i]} → predicted TRL ${cm.labels[j]}: ${value}`}
                          className="h-9 w-9 rounded border border-line/70 tabular-nums"
                          style={{
                            backgroundColor:
                              value === 0
                                ? "#FFFFFF"
                                : isDiagonal
                                  ? `rgba(13, 148, 136, ${alpha})`
                                  : `rgba(37, 99, 235, ${alpha})`,
                            color:
                              alpha > 0.55
                                ? "#FFFFFF"
                                : value === 0
                                  ? "#CBD5E1"
                                  : "#0B1B33",
                            fontWeight: isDiagonal && value > 0 ? 700 : 500,
                          }}
                        >
                          {value}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="text-sm text-faint">No confusion matrix available.</p>
          )}
        </div>
        {cm && (
          <div className="flex flex-wrap items-center gap-4 border-t border-line px-5 py-3 text-[11px] text-muted">
            <LegendDot className="bg-teal-600" label="Correct predictions" />
            <LegendDot className="bg-blue-600" label="Misclassifications" />
            <LegendDot className="border border-line bg-white" label="Zero" />
          </div>
        )}
      </div>

      {/* Per-class table + F1 chart */}
      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="card overflow-hidden">
          <div className="border-b border-line px-5 py-4">
            <h2 className="section-title">Per-class metrics</h2>
            <p className="mt-0.5 text-xs text-faint">
              Precision / recall / F1 / support per TRL level
            </p>
          </div>
          <div className="scrollbar-thin overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-line text-[11px] uppercase tracking-[0.12em] text-faint">
                  <th className="px-4 py-2.5 font-semibold">TRL</th>
                  <th className="px-3 py-2.5 font-semibold">Precision</th>
                  <th className="px-3 py-2.5 font-semibold">Recall</th>
                  <th className="px-3 py-2.5 font-semibold">F1</th>
                  <th className="px-3 py-2.5 font-semibold">Support</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line/70">
                {Object.entries(data.per_class)
                  .sort((a, b) => Number(a[0]) - Number(b[0]))
                  .map(([label, m]) => (
                    <tr key={label} className="transition-colors hover:bg-teal-50/30">
                      <td className="px-4 py-2.5 font-semibold text-ink">
                        TRL {label}
                      </td>
                      <td className="px-3 py-2.5 tabular-nums text-muted">
                        {fmt(m.precision)}
                      </td>
                      <td className="px-3 py-2.5 tabular-nums text-muted">
                        {fmt(m.recall)}
                      </td>
                      <td className="px-3 py-2.5 tabular-nums font-semibold text-ink-soft">
                        {fmt(m.f1)}
                      </td>
                      <td className="px-3 py-2.5 tabular-nums text-faint">
                        {m.support}
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="card p-5">
          <h2 className="section-title">Per-class F1</h2>
          <p className="mb-4 mt-0.5 text-xs text-faint">F1 score by TRL level</p>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={perClassF1}
                margin={{ top: 4, right: 8, left: -18, bottom: 0 }}
              >
                <defs>
                  <linearGradient id="f1Bar" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#14b8a6" />
                    <stop offset="100%" stopColor="#0d9488" />
                  </linearGradient>
                </defs>
                <CartesianGrid
                  strokeDasharray="4 6"
                  stroke="#EDF1F7"
                  vertical={false}
                />
                <XAxis
                  dataKey="name"
                  tick={{ fontSize: 10, fill: "#8a97a8" }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  domain={[0, 1]}
                  tick={{ fontSize: 11, fill: "#8a97a8" }}
                  tickFormatter={(v: number) => v.toFixed(1)}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip
                  cursor={{ fill: "rgba(13,148,136,0.06)" }}
                  contentStyle={tooltipStyle}
                  formatter={(value, _n, item) => {
                    const payload = item?.payload as
                      | { support?: number }
                      | undefined;
                    return [
                      `${Number(value).toFixed(3)} (support ${payload?.support ?? 0})`,
                      "F1",
                    ];
                  }}
                />
                <Bar
                  dataKey="f1"
                  fill="url(#f1Bar)"
                  radius={[6, 6, 0, 0]}
                  maxBarSize={30}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Class distribution */}
      <div className="card mt-4 p-5">
        <h2 className="section-title">Class distribution</h2>
        <p className="mb-4 mt-0.5 text-xs text-faint">
          Label counts in the evaluation dataset
        </p>
        <div className="h-56">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={classDistribution}
              margin={{ top: 4, right: 8, left: -18, bottom: 0 }}
            >
              <defs>
                <linearGradient id="distBar" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#60a5fa" />
                  <stop offset="100%" stopColor="#2563eb" />
                </linearGradient>
              </defs>
              <CartesianGrid
                strokeDasharray="4 6"
                stroke="#EDF1F7"
                vertical={false}
              />
              <XAxis
                dataKey="name"
                tick={{ fontSize: 11, fill: "#8a97a8" }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                allowDecimals={false}
                tick={{ fontSize: 11, fill: "#8a97a8" }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip
                cursor={{ fill: "rgba(13,148,136,0.06)" }}
                contentStyle={tooltipStyle}
              />
              <Bar
                dataKey="count"
                fill="url(#distBar)"
                radius={[6, 6, 0, 0]}
                maxBarSize={36}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Classification report */}
      <div className="card mt-4 overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-5 py-4">
          <div>
            <h2 className="section-title">Classification report</h2>
            <p className="mt-0.5 text-xs text-faint">
              Precision / recall / F1 / support / accuracy per class
            </p>
          </div>
          {accuracy !== undefined && (
            <span className="chip">
              <Activity className="h-3.5 w-3.5 text-primary" />
              Accuracy {formatPercent(accuracy, 1)}
            </span>
          )}
        </div>
        <div className="scrollbar-thin overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-line text-[11px] uppercase tracking-[0.12em] text-faint">
                <th className="px-4 py-2.5 font-semibold">Class</th>
                <th className="px-3 py-2.5 font-semibold">Precision</th>
                <th className="px-3 py-2.5 font-semibold">Recall</th>
                <th className="px-3 py-2.5 font-semibold">F1-score</th>
                <th className="px-3 py-2.5 font-semibold">Support</th>
                <th className="px-3 py-2.5 font-semibold">Accuracy</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line/70">
              {reportRows.map(([label, row]) => (
                <tr
                  key={label}
                  className="transition-colors hover:bg-teal-50/30"
                >
                  <td className="px-4 py-2.5 font-semibold text-ink">
                    TRL {label}
                  </td>
                  <td className="px-3 py-2.5 tabular-nums text-muted">
                    {fmt(row.precision)}
                  </td>
                  <td className="px-3 py-2.5 tabular-nums text-muted">
                    {fmt(row.recall)}
                  </td>
                  <td className="px-3 py-2.5 tabular-nums font-semibold text-ink-soft">
                    {fmt(row.f1)}
                  </td>
                  <td className="px-3 py-2.5 tabular-nums text-faint">
                    {row.support}
                  </td>
                  <td className="px-3 py-2.5 tabular-nums text-faint">
                    {fmt(row.accuracy)}
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="bg-panel/60">
                <td className="px-4 py-2.5 text-xs font-semibold uppercase tracking-[0.12em] text-muted">
                  Overall
                </td>
                <td className="px-3 py-2.5 text-xs text-faint">—</td>
                <td className="px-3 py-2.5 text-xs text-faint">—</td>
                <td className="px-3 py-2.5 text-xs font-semibold text-ink-soft">
                  macro {fmt(data.metrics.macro_f1)} · weighted{" "}
                  {fmt(data.metrics.weighted_f1)}
                </td>
                <td className="px-3 py-2.5 text-xs text-faint">
                  {data.n_test ?? "—"}
                </td>
                <td className="px-3 py-2.5 text-xs font-semibold text-ink-soft">
                  {fmt(accuracy)}
                </td>
              </tr>
            </tfoot>
          </table>
        </div>
      </div>
    </div>
  );
}

function LegendDot({ className, label }: { className: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className={`h-3 w-3 rounded-sm ${className}`} />
      {label}
    </span>
  );
}
