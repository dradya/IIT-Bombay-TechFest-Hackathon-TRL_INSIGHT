import { useId } from "react";

interface ConfidenceRingProps {
  /** 0-1 confidence value from the API. */
  value: number;
  size?: number;
  label?: string;
  /** Render for a dark surface (hero panels). */
  onDark?: boolean;
}

/** SVG donut ring showing prediction confidence as a percentage. */
export default function ConfidenceRing({
  value,
  size = 120,
  label = "Confidence",
  onDark = false,
}: ConfidenceRingProps) {
  const gid = useId().replace(/:/g, "");
  const clamped = Math.max(0, Math.min(1, value));
  const stroke = Math.max(8, Math.round(size * 0.08));
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - clamped);
  const pct = (clamped * 100).toFixed(0);

  const [from, to] = onDark
    ? ["#5eead4", "#67e8f9"]
    : clamped >= 0.7
      ? ["#14b8a6", "#22d3ee"]
      : clamped >= 0.45
        ? ["#3b82f6", "#6366f1"]
        : ["#f59e0b", "#f97316"];

  return (
    <div
      className="relative inline-flex items-center justify-center"
      style={{ width: size, height: size }}
      role="img"
      aria-label={`${label}: ${pct}%`}
    >
      <svg width={size} height={size} className="-rotate-90">
        <defs>
          <linearGradient id={`ring-${gid}`} x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor={from} />
            <stop offset="100%" stopColor={to} />
          </linearGradient>
        </defs>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          strokeWidth={stroke}
          className={onDark ? "stroke-white/10" : "stroke-slate-100"}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={`url(#ring-${gid})`}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          style={{
            transition: "stroke-dashoffset 600ms cubic-bezier(0.2,0.7,0.2,1)",
            filter: onDark
              ? "drop-shadow(0 0 10px rgba(94,234,212,0.55))"
              : "drop-shadow(0 2px 6px rgba(13,148,136,0.28))",
          }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span
          className={`stat-value text-2xl font-bold ${
            onDark ? "text-white" : "text-ink"
          }`}
        >
          {pct}%
        </span>
        <span
          className={`mt-0.5 text-[10px] font-semibold uppercase tracking-[0.12em] ${
            onDark ? "text-teal-200/80" : "text-faint"
          }`}
        >
          {label}
        </span>
      </div>
    </div>
  );
}
