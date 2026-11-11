import type { Prediction, Uncertainty } from "../types";
import { formatPercent } from "../utils/format";

interface ConfidenceIndicatorProps {
  uncertainty?: Uncertainty | null;
  prediction?: Prediction | null;
  compact?: boolean;
}

const DIMENSIONS: {
  key: keyof Pick<Uncertainty, "model_probability" | "confidence" | "coverage" | "completeness" | "reliability">;
  label: string;
  help: string;
  tone: string;
}[] = [
  {
    key: "model_probability",
    label: "Model probability",
    help: "Highest class probability from the ML branch (null in rule-only mode).",
    tone: "from-blue-500 to-indigo-500",
  },
  {
    key: "confidence",
    label: "Prediction confidence",
    help: "Combined rule/ML confidence in the selected level.",
    tone: "from-teal-500 to-cyan-400",
  },
  {
    key: "coverage",
    label: "Evidence coverage",
    help: "Share of milestones up to the predicted TRL with confirmed evidence.",
    tone: "from-emerald-500 to-teal-400",
  },
  {
    key: "completeness",
    label: "Evidence completeness",
    help: "Fraction of all nine milestones with confirmed evidence.",
    tone: "from-cyan-500 to-blue-400",
  },
  {
    key: "reliability",
    label: "Assessment reliability",
    help: "Source and extraction quality signal — not a probability.",
    tone: "from-slate-500 to-slate-400",
  },
];

const BAND_LABEL: Record<string, string> = {
  high: "High",
  medium: "Medium",
  low: "Low",
};

/**
 * Uncertainty decomposition. Values are shown only when the backend supplied
 * them; a legacy assessment gets an explicit unavailable state.
 */
export default function ConfidenceIndicator({
  uncertainty,
  prediction,
  compact = false,
}: ConfidenceIndicatorProps) {
  if (!uncertainty) {
    return (
      <div className="rounded-xl border border-dashed border-line bg-panel/70 px-4 py-3 text-xs leading-relaxed text-muted">
        <p className="font-semibold text-ink-soft">Uncertainty decomposition unavailable</p>
        <p className="mt-1">
          This assessment was created before TRL INSIGHT 2.0, so only the original
          confidence
          {prediction ? ` (${formatPercent(prediction.confidence, 0)})` : ""} and
          evidence coverage
          {prediction ? ` (${formatPercent(prediction.evidence_coverage, 0)})` : ""} are
          stored. Re-run the assessment to compute coverage, completeness and reliability.
        </p>
      </div>
    );
  }

  const rows = DIMENSIONS.map((d) => {
    const raw = uncertainty[d.key];
    return { ...d, value: typeof raw === "number" ? raw : null };
  });

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-sm font-semibold text-ink">
            Overall reliability {formatPercent(uncertainty.overall, 0)}
          </p>
          <p className="mt-0.5 text-xs text-faint">
            Band: {BAND_LABEL[uncertainty.band] ?? uncertainty.band} ·{" "}
            {uncertainty.calibrated
              ? "calibrated on validation data"
              : "not calibrated (no genuine validation data)"}
          </p>
        </div>
        <span
          className={`rounded-full px-2.5 py-1 text-[11px] font-bold uppercase tracking-wide ${
            uncertainty.band === "high"
              ? "bg-emerald-50 text-emerald-700"
              : uncertainty.band === "medium"
                ? "bg-amber-50 text-amber-700"
                : "bg-rose-50 text-rose-700"
          }`}
        >
          {BAND_LABEL[uncertainty.band] ?? uncertainty.band} certainty
        </span>
      </div>

      <dl className={`mt-4 ${compact ? "space-y-2.5" : "space-y-3.5"}`}>
        {rows.map((row) => (
          <div key={row.key as string}>
            <div className="mb-1 flex items-center justify-between gap-3 text-xs">
              <dt className="text-muted" title={row.help}>
                {row.label}
              </dt>
              <dd className="font-semibold tabular-nums text-ink">
                {row.value === null ? "—" : formatPercent(row.value, 0)}
              </dd>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-slate-100">
              <div
                className={`h-full rounded-full bg-gradient-to-r ${row.tone}`}
                style={{ width: `${Math.max(0, Math.min(1, row.value ?? 0)) * 100}%` }}
              />
            </div>
          </div>
        ))}
      </dl>

      {uncertainty.explanation && (
        <p className="mt-4 rounded-xl border border-line bg-panel px-3 py-2.5 text-xs leading-relaxed text-muted">
          {uncertainty.explanation}
        </p>
      )}
      {uncertainty.calibration_note && (
        <p className="mt-2 text-[11px] leading-relaxed text-faint">
          {uncertainty.calibration_note}
        </p>
      )}
    </div>
  );
}
