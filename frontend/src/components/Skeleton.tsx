interface SkeletonProps {
  className?: string;
  /** Number of stacked lines (1 = single block). */
  lines?: number;
}

/** Neutral shimmering placeholder block — no layout shift. */
export default function Skeleton({ className = "", lines = 1 }: SkeletonProps) {
  if (lines === 1) {
    return (
      <div
        className={`animate-pulse rounded-xl bg-gradient-to-r from-slate-100 via-slate-50 to-slate-100 ${className}`}
        aria-hidden="true"
      />
    );
  }
  return (
    <div className="space-y-2" aria-hidden="true">
      {Array.from({ length: lines }).map((_, i) => (
        <div
          key={i}
          className={`animate-pulse rounded-xl bg-gradient-to-r from-slate-100 via-slate-50 to-slate-100 ${className}`}
        />
      ))}
    </div>
  );
}
