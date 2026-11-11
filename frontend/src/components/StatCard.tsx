import type { LucideIcon } from "lucide-react";

interface StatCardProps {
  label: string;
  value: string;
  icon: LucideIcon;
  hint?: string;
  tone?: "teal" | "blue" | "amber" | "green";
}

const tones = {
  teal: {
    tile: "bg-gradient-to-br from-teal-400/20 to-cyan-400/10 text-teal-700 ring-teal-500/10",
    bar: "from-teal-400 to-cyan-400",
  },
  blue: {
    tile: "bg-gradient-to-br from-blue-400/20 to-indigo-400/10 text-blue-700 ring-blue-500/10",
    bar: "from-blue-500 to-indigo-500",
  },
  amber: {
    tile: "bg-gradient-to-br from-amber-400/25 to-orange-400/10 text-amber-700 ring-amber-500/10",
    bar: "from-amber-400 to-orange-400",
  },
  green: {
    tile: "bg-gradient-to-br from-emerald-400/20 to-teal-400/10 text-emerald-700 ring-emerald-500/10",
    bar: "from-emerald-400 to-teal-400",
  },
};

/** Single KPI tile used across Overview / Performance pages. */
export default function StatCard({
  label,
  value,
  icon: Icon,
  hint,
  tone = "teal",
}: StatCardProps) {
  const t = tones[tone];
  return (
    <div className="card card-hover overflow-hidden p-5">
      <div className="relative flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="eyebrow">{label}</p>
          <p className="stat-value mt-2.5 truncate text-[30px] font-bold leading-none text-ink">
            {value}
          </p>
          {hint && <p className="mt-2 text-xs leading-relaxed text-faint">{hint}</p>}
        </div>
        <span
          className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl ring-1 ring-inset ${t.tile}`}
        >
          <Icon className="h-5 w-5" aria-hidden="true" />
        </span>
      </div>
      <div
        className={`mt-4 h-1 w-12 rounded-full bg-gradient-to-r ${t.bar}`}
      />
    </div>
  );
}
