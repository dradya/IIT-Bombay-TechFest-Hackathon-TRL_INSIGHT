interface ConfidenceBarProps {
  /** 0-1 value. */
  value: number;
  showLabel?: boolean;
  className?: string;
}

const palettes = {
  high: "bg-gradient-to-r from-teal-500 to-cyan-400",
  medium: "bg-gradient-to-r from-blue-500 to-indigo-500",
  low: "bg-gradient-to-r from-amber-400 to-orange-500",
} as const;

/** Thin horizontal confidence / coverage meter (0-100%). */
export default function ConfidenceBar({
  value,
  showLabel = true,
  className = "",
}: ConfidenceBarProps) {
  const clamped = Math.max(0, Math.min(1, value));
  const pct = Math.round(clamped * 100);
  const tone = clamped >= 0.7 ? "high" : clamped >= 0.45 ? "medium" : "low";
  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <div
        className="h-1.5 w-full min-w-14 overflow-hidden rounded-full bg-slate-100"
        role="progressbar"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div
          className={`h-full rounded-full transition-[width] duration-500 ${palettes[tone]}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      {showLabel && (
        <span className="w-9 shrink-0 text-right text-xs font-semibold tabular-nums text-muted">
          {pct}%
        </span>
      )}
    </div>
  );
}
