import type { ReactNode } from "react";
import { useEffect } from "react";
import { useLocation } from "react-router-dom";

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
}

function sectionFor(pathname: string): string {
  if (pathname.startsWith("/assessments/")) return "Assessment result";
  if (pathname.startsWith("/new")) return "Assessment workspace";
  if (pathname.startsWith("/history")) return "Assessment workspace";
  if (pathname.startsWith("/explorer")) return "Assessment workspace";
  if (pathname.startsWith("/trl-guide")) return "Knowledge base";
  if (pathname.startsWith("/model-performance")) return "Model intelligence";
  if (pathname.startsWith("/settings")) return "System";
  return "Portfolio overview";
}

/** Consistent page title + short subtitle (+ optional actions).
    Also sets the document title so browser history entries are readable. */
export default function PageHeader({
  title,
  subtitle,
  actions,
}: PageHeaderProps) {
  const location = useLocation();

  useEffect(() => {
    document.title = `${title} · TRL INSIGHT`;
    return () => {
      document.title = "TRL INSIGHT — Technology Readiness Assessment";
    };
  }, [title]);

  return (
    <div className="mb-7 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0">
        <div className="mb-2 flex items-center gap-2.5">
          <span className="h-1.5 w-7 rounded-full bg-gradient-to-r from-primary via-teal-400 to-cyan-400 shadow-[0_0_10px_rgba(13,148,136,0.35)]" />
          <span className="eyebrow">{sectionFor(location.pathname)}</span>
        </div>
        <h1 className="font-display text-[26px] font-semibold leading-tight tracking-tight text-ink sm:text-[30px]">
          {title}
        </h1>
        {subtitle && (
          <p className="mt-2 max-w-3xl text-sm leading-relaxed text-muted">
            {subtitle}
          </p>
        )}
      </div>
      {actions && (
        <div className="flex flex-wrap items-center gap-2">{actions}</div>
      )}
    </div>
  );
}
