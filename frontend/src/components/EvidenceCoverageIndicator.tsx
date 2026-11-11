import { formatPercent } from "../utils/format";

interface EvidenceCoverageIndicatorProps {
  /** 0-1 coverage value from the API. */
  coverage: number;
  /** Optional count of covered milestones. */
  covered?: number;
  total?: number;
  label?: string;
  /** Render white-on-dark for hero panels. */
  onDark?: boolean;
}

/** Evidence coverage meter with an explicit denominator when supplied. */
export default function EvidenceCoverageIndicator({
  coverage,
  covered,
  total,
  label = "Evidence coverage",
  onDark = false,
}: EvidenceCoverageIndicatorProps) {
  const pct = Math.max(0, Math.min(1, coverage));
  return (
    <div>
      <div className="mb-1.5 flex items-center justify-between gap-3 text-[11px]">
        <span className={onDark ? "font-medium text-slate-300" : "text-muted"}>
          {label}
        </span>
        <span className={onDark ? "font-bold text-white" : "font-semibold text-ink"}>
          {formatPercent(pct, 0)}
          {typeof covered === "number" && typeof total === "number" && total > 0
            ? ` · ${covered}/${total}`
            : ""}
        </span>
      </div>
      <div
        className={`h-1.5 overflow-hidden rounded-full ${
          onDark ? "bg-white/10" : "bg-slate-100"
        }`}
        role="progressbar"
        aria-valuenow={Math.round(pct * 100)}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div
          className={`h-full rounded-full ${
            onDark
              ? "bg-gradient-to-r from-teal-400 to-cyan-300 shadow-[0_0_12px_rgba(45,212,191,0.7)]"
              : pct >= 0.7
                ? "bg-gradient-to-r from-teal-500 to-cyan-400"
                : pct >= 0.45
                  ? "bg-gradient-to-r from-blue-500 to-indigo-500"
                  : "bg-gradient-to-r from-amber-400 to-orange-500"
          }`}
          style={{ width: `${pct * 100}%` }}
        />
      </div>
    </div>
  );
}
