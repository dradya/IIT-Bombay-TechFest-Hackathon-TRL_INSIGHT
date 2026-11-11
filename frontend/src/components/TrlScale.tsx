interface TrlScaleProps {
  /** Predicted TRL 1-9 to highlight. */
  predicted: number;
  /** Optional: clicked level (1-9) — parent shows the description. */
  selected?: number | null;
  onSelect?: (level: number) => void;
  /** Compact mode for cards (no labels under bars). */
  compact?: boolean;
}

/**
 * Visual TRL 1-9 progression bar. Levels ≤ predicted are tinted teal,
 * the predicted level is solid teal. Clicking a level selects it so the
 * parent can show the level description from /api/trl/reference.
 */
export default function TrlScale({
  predicted,
  selected = null,
  onSelect,
  compact = false,
}: TrlScaleProps) {
  return (
    <div
      className="flex w-full items-end gap-1.5 sm:gap-2"
      role="group"
      aria-label="TRL 1-9 scale"
    >
      {Array.from({ length: 9 }, (_, i) => i + 1).map((level) => {
        const isPredicted = level === predicted;
        const isReached = level <= predicted;
        const isSelected = selected === level;
        const height = `${26 + level * 7}px`;
        return (
          <button
            key={level}
            type="button"
            onClick={() => onSelect?.(level)}
            aria-label={`TRL ${level}${isPredicted ? " (predicted)" : ""}`}
            aria-pressed={isSelected}
            className={`group flex min-w-0 flex-1 flex-col items-center gap-1.5 rounded-lg pb-1 pt-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 ${
              onSelect ? "cursor-pointer" : "cursor-default"
            }`}
          >
            <span
              className={`w-full rounded-md border transition-all duration-200 ${
                isPredicted
                  ? "border-teal-500 bg-gradient-to-t from-teal-600 to-cyan-400 shadow-[0_0_20px_rgba(13,148,136,0.45)]"
                  : isReached
                    ? "border-teal-200 bg-gradient-to-t from-teal-100 to-teal-50 group-hover:border-teal-300"
                    : "border-slate-200 bg-slate-50 group-hover:border-slate-300 group-hover:bg-slate-100"
              } ${isSelected ? "ring-2 ring-secondary ring-offset-1" : ""}`}
              style={{ height }}
            />
            <span
              className={`text-[11px] font-semibold tabular-nums ${
                isPredicted
                  ? "text-primary-dark"
                  : isReached
                    ? "text-teal-700/70"
                    : "text-faint"
              }`}
            >
              {level}
            </span>
            {!compact && isSelected && <span className="sr-only">selected</span>}
          </button>
        );
      })}
    </div>
  );
}
