import { AlertTriangle, Info } from "lucide-react";
import type { ModelExplanation } from "../types";

interface SHAPExplanationChartProps {
  explanation?: ModelExplanation | null;
  /** Optional max features to show (largest |contribution| first). */
  limit?: number;
}

/**
 * Model-only feature attributions. Rendered separately from evidence and
 * always labelled as an explanation of the classifier, not of the document.
 */
export default function SHAPExplanationChart({
  explanation,
  limit = 12,
}: SHAPExplanationChartProps) {
  if (!explanation || !explanation.available) {
    return (
      <div className="rounded-xl border border-dashed border-line bg-panel/70 px-4 py-4 text-sm text-muted">
        <p className="font-semibold text-ink-soft">Model explanation unavailable</p>
        <p className="mt-1 text-xs leading-relaxed">
          {explanation?.note ||
            "This assessment has no stored feature attribution. Re-run the analysis with a compatible classifier to generate one."}
        </p>
      </div>
    );
  }

  const features = explanation.features
    .slice()
    .sort((a, b) => Math.abs(b.contribution) - Math.abs(a.contribution))
    .slice(0, limit);
  const max = Math.max(0.000001, ...features.map((f) => Math.abs(f.contribution)));
  const shownLimit = Math.min(limit, explanation.features.length);

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-sm font-semibold text-ink">
            Feature attribution · target TRL {explanation.target_trl ?? "—"}
          </p>
          <p className="mt-0.5 text-xs text-faint">
            Method: {explanation.method}
            {explanation.prediction_probability !== null
              ? ` · class probability ${(explanation.prediction_probability * 100).toFixed(1)}%`
              : ""}
            {explanation.baseline !== null
              ? ` · baseline ${explanation.baseline.toFixed(3)}`
              : ""}
          </p>
        </div>
        <span className="chip">{shownLimit} of {explanation.features.length} features</span>
      </div>

      <div className="mt-4 space-y-2">
        {features.map((feature, i) => {
          const width = (Math.abs(feature.contribution) / max) * 50;
          const positive = feature.contribution >= 0;
          return (
            <div key={`${feature.feature}-${i}`} className="grid grid-cols-[minmax(120px,1fr)_2fr_minmax(56px,auto)] items-center gap-2.5">
              <span
                className="truncate text-right text-[11px] font-medium text-ink-soft"
                title={`${feature.label} (${feature.kind})`}
              >
                {feature.label}
              </span>
              <div className="relative h-5 rounded bg-slate-50">
                <span className="absolute left-1/2 top-0 h-full w-px bg-slate-200" />
                <div
                  className={`absolute top-0.5 h-4 rounded ${
                    positive
                      ? "bg-gradient-to-r from-teal-500 to-cyan-400"
                      : "bg-gradient-to-l from-rose-500 to-orange-400"
                  }`}
                  style={
                    positive
                      ? { left: "50%", width: `${width}%` }
                      : { right: "50%", width: `${width}%` }
                  }
                  title={`${feature.contribution >= 0 ? "+" : ""}${feature.contribution.toFixed(4)}`}
                />
              </div>
              <span
                className={`text-right text-[11px] font-semibold tabular-nums ${
                  positive ? "text-teal-700" : "text-rose-600"
                }`}
              >
                {feature.contribution >= 0 ? "+" : ""}
                {feature.contribution.toFixed(3)}
              </span>
            </div>
          );
        })}
      </div>

      <div className="mt-4 flex items-center justify-center gap-4 text-[11px] text-faint">
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2 w-3 rounded bg-gradient-to-r from-teal-500 to-cyan-400" />
          Supports this level
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2 w-3 rounded bg-gradient-to-l from-rose-500 to-orange-400" />
          Opposes this level
        </span>
      </div>

      {explanation.note && (
        <p className="mt-3 flex items-start gap-1.5 rounded-xl border border-line bg-panel px-3 py-2 text-xs leading-relaxed text-muted">
          <Info className="mt-0.5 h-3.5 w-3.5 shrink-0 text-secondary" />
          {explanation.note}
        </p>
      )}
      <p className="mt-2 flex items-start gap-1.5 rounded-xl border border-amber-200/70 bg-amber-50/60 px-3 py-2 text-[11px] leading-relaxed text-amber-900">
        <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
        {explanation.warning}
      </p>
    </div>
  );
}
