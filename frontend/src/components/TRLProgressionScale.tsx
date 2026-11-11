import type { MilestoneStatusModel } from "../types";

export interface TRLProgressionScaleProps {
  /** Predicted TRL 1-9. */
  predicted: number;
  /** Optional milestone statuses to colour each level. */
  milestones?: MilestoneStatusModel[];
  /** Currently inspected level (1-9). */
  selected?: number | null;
  onSelect?: (level: number) => void;
  /** Optional level names keyed by 1-9. */
  levelNames?: Record<number, string>;
  className?: string;
}

const STATUS_STYLES = {
  confirmed: {
    node: "border-emerald-500 bg-emerald-500 text-white",
    label: "text-emerald-700",
    caption: "Confirmed",
  },
  contradicted: {
    node: "border-rose-500 bg-rose-500 text-white",
    label: "text-rose-700",
    caption: "Contradicted",
  },
  unclear: {
    node: "border-amber-400 bg-amber-400 text-amber-950",
    label: "text-amber-700",
    caption: "Unclear",
  },
  not_found: {
    node: "border-slate-200 bg-white text-slate-400",
    label: "text-faint",
    caption: "Missing",
  },
} as const;

/**
 * Nine-level readiness progression. Colours come from the assessment's real
 * milestone statuses when supplied; otherwise levels at/below the prediction
 * are shown as reached. Never invents a status.
 */
export default function TRLProgressionScale({
  predicted,
  milestones = [],
  selected = null,
  onSelect,
  levelNames = {},
  className = "",
}: TRLProgressionScaleProps) {
  const byLevel = new Map<number, MilestoneStatusModel>();
  milestones.forEach((m) => {
    if (!byLevel.has(m.trl)) byLevel.set(m.trl, m);
  });

  return (
    <div className={`relative ${className}`}>
      <div className="pointer-events-none absolute left-0 right-0 top-[22px] h-px bg-line" />
      <ol className="relative grid grid-cols-9 gap-1" aria-label="TRL progression 1 to 9">
        {Array.from({ length: 9 }, (_, i) => i + 1).map((level) => {
          const milestone = byLevel.get(level);
          const status = milestone?.status;
          const style = status
            ? STATUS_STYLES[status]
            : level <= predicted
              ? STATUS_STYLES.confirmed
              : STATUS_STYLES.not_found;
          const isPredicted = level === predicted;
          const isSelected = selected === level;
          const name = levelNames[level] ?? milestone?.label ?? "";
          return (
            <li key={level} className="flex min-w-0 flex-col items-center text-center">
              <button
                type="button"
                onClick={() => onSelect?.(level)}
                aria-label={`TRL ${level}${isPredicted ? " (predicted)" : ""}${
                  status ? ` — ${STATUS_STYLES[status].caption}` : ""
                }`}
                aria-pressed={isSelected}
                className={`relative z-10 flex h-11 w-11 items-center justify-center rounded-full border-2 text-xs font-bold shadow-sm transition-all ${
                  style.node
                } ${
                  isPredicted
                    ? "ring-4 ring-teal-500/20"
                    : ""
                } ${isSelected ? "scale-110 ring-2 ring-secondary ring-offset-2" : ""} ${
                  onSelect ? "cursor-pointer hover:scale-105" : "cursor-default"
                } focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2`}
              >
                {level}
              </button>
              <span
                className={`mt-2 hidden max-w-full truncate text-[10px] font-semibold uppercase tracking-[0.06em] sm:block ${
                  isPredicted ? "text-ink" : style.label
                }`}
                title={name}
              >
                {name || `TRL ${level}`}
              </span>
              {isPredicted && (
                <span className="mt-1 rounded-full bg-teal-50 px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wide text-primary-dark">
                  Predicted
                </span>
              )}
            </li>
          );
        })}
      </ol>
      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1.5 text-[11px] text-faint">
        {(
          [
            ["confirmed", "Confirmed"],
            ["unclear", "Unclear"],
            ["contradicted", "Contradicted"],
            ["not_found", "Not evidenced"],
          ] as const
        ).map(([key, label]) => (
          <span key={key} className="inline-flex items-center gap-1.5">
            <span
              className={`h-2 w-2 rounded-full ${
                key === "confirmed"
                  ? "bg-emerald-500"
                  : key === "unclear"
                    ? "bg-amber-400"
                    : key === "contradicted"
                      ? "bg-rose-500"
                      : "border border-slate-300 bg-white"
              }`}
            />
            {label}
          </span>
        ))}
      </div>
    </div>
  );
}
