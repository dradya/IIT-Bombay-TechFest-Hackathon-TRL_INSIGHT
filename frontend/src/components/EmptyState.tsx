import type { LucideIcon } from "lucide-react";
import { Compass, Inbox } from "lucide-react";
import { Link } from "react-router-dom";

interface EmptyStateProps {
  icon?: LucideIcon;
  title: string;
  description: string;
  actionLabel?: string;
  actionTo?: string;
  onAction?: () => void;
}

/** Friendly empty state — never renders fake data. */
export default function EmptyState({
  icon: Icon = Inbox,
  title,
  description,
  actionLabel,
  actionTo,
  onAction,
}: EmptyStateProps) {
  return (
    <div className="card relative flex flex-col items-center justify-center overflow-hidden px-6 py-16 text-center">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_50%_0%,rgba(13,148,136,0.09),transparent_55%)]" />
      <div className="relative mb-1 flex h-16 w-16 items-center justify-center">
        <span className="absolute inset-0 rounded-2xl border border-teal-200/60" />
        <span className="absolute inset-2 rounded-xl border border-teal-200/40" />
        <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-teal-400/20 to-cyan-400/10 text-primary ring-1 ring-inset ring-teal-500/10">
          <Icon className="h-5 w-5" aria-hidden="true" />
        </span>
      </div>
      <h3 className="relative mt-3 font-display text-base font-semibold text-ink">
        {title}
      </h3>
      <p className="relative mt-1.5 max-w-md text-sm leading-relaxed text-muted">
        {description}
      </p>
      {actionLabel && actionTo && (
        <Link to={actionTo} className="btn btn-primary relative mt-6">
          <Compass className="h-4 w-4" />
          {actionLabel}
        </Link>
      )}
      {actionLabel && !actionTo && onAction && (
        <button
          type="button"
          onClick={onAction}
          className="btn btn-primary relative mt-6"
        >
          <Compass className="h-4 w-4" />
          {actionLabel}
        </button>
      )}
    </div>
  );
}
