import { AlertOctagon, CheckCircle2, ShieldQuestion } from "lucide-react";
import type { ContradictionReport } from "../types";

interface ContradictionAlertProps {
  report?: ContradictionReport | null;
  /** Optional handler to jump to the evidence tab / graph. */
  onInspect?: () => void;
}

const TYPE_LABEL: Record<string, string> = {
  explicit_contradiction: "Explicit contradiction",
  cross_document_conflict: "Cross-document conflict",
  category_conflict: "Category conflict",
  outdated_conflict: "Outdated vs. current evidence",
};

const SEVERITY_STYLE: Record<string, string> = {
  high: "border-rose-200 bg-rose-50/60",
  medium: "border-amber-200 bg-amber-50/60",
  low: "border-slate-200 bg-slate-50/60",
};

/**
 * Contradiction report with sources, explanation and human verification steps.
 * An empty report is shown explicitly — never padded with examples.
 */
export default function ContradictionAlert({
  report,
  onInspect,
}: ContradictionAlertProps) {
  if (!report) {
    return (
      <div className="rounded-xl border border-dashed border-line bg-panel/70 px-4 py-4 text-sm text-muted">
        <p className="font-semibold text-ink-soft">Contradiction analysis unavailable</p>
        <p className="mt-1 text-xs leading-relaxed">
          This assessment predates the 2.0 pipeline. Re-run the analysis to compare
          statements across documents and flag outdated evidence.
        </p>
      </div>
    );
  }

  if (report.total === 0) {
    return (
      <div className="flex items-start gap-3 rounded-xl border border-emerald-200/70 bg-emerald-50/50 px-4 py-3.5">
        <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
        <div>
          <p className="text-sm font-semibold text-emerald-800">
            No contradictions detected
          </p>
          <p className="mt-0.5 text-xs leading-relaxed text-emerald-900/70">
            The detector found no conflicting milestone claims, performance values or
            outdated supersession in the supplied evidence.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-sm font-semibold text-rose-800">
          <AlertOctagon className="h-4 w-4" />
          {report.total} contradiction{report.total === 1 ? "" : "s"} detected
        </div>
        {onInspect && (
          <button
            type="button"
            onClick={onInspect}
            className="text-xs font-semibold text-secondary hover:underline"
          >
            Inspect evidence →
          </button>
        )}
      </div>
      {report.summary && (
        <p className="mb-3 text-xs leading-relaxed text-muted">{report.summary}</p>
      )}
      <ul className="space-y-3">
        {report.items.map((item) => (
          <li
            key={item.id}
            className={`rounded-xl border px-4 py-3.5 ${
              SEVERITY_STYLE[item.severity] ?? SEVERITY_STYLE.low
            }`}
          >
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-full bg-white/80 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-rose-700 ring-1 ring-inset ring-rose-200/70">
                {item.severity} severity
              </span>
              <span className="text-xs font-semibold text-ink">
                {TYPE_LABEL[item.type] ?? item.type.replace(/_/g, " ")}
              </span>
              {item.milestone_label && (
                <span className="chip bg-white/80 px-2 py-0 text-[10px]">
                  {item.milestone_label}
                </span>
              )}
              {item.category_label && (
                <span className="chip bg-white/80 px-2 py-0 text-[10px]">
                  {item.category_label}
                </span>
              )}
            </div>
            <p className="mt-2 text-sm leading-relaxed text-ink-soft">
              {item.explanation}
            </p>

            {item.sources.length > 0 && (
              <div className="mt-3 space-y-2">
                {item.sources.map((source) => (
                  <div
                    key={`${item.id}-${source.evidence_id}`}
                    className="rounded-lg border border-white/70 bg-white/80 px-3 py-2"
                  >
                    <p className="text-[13px] leading-relaxed text-ink-soft">
                      “{source.statement}”
                    </p>
                    <p className="mt-1 text-[11px] text-faint">
                      {source.source_document}
                      {source.page_number !== null
                        ? ` · page ${source.page_number}`
                        : source.location
                          ? ` · ${source.location}`
                          : ""}{" "}
                      · {source.evidence_id} · {source.status}
                      {source.outdated ? " · outdated" : ""}
                    </p>
                  </div>
                ))}
              </div>
            )}

            {item.human_verification.length > 0 && (
              <div className="mt-3">
                <p className="mb-1 inline-flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-[0.1em] text-muted">
                  <ShieldQuestion className="h-3.5 w-3.5" />
                  Suggested human verification
                </p>
                <ul className="list-disc space-y-1 pl-5 text-xs leading-relaxed text-ink-soft">
                  {item.human_verification.map((step, i) => (
                    <li key={i}>{step}</li>
                  ))}
                </ul>
              </div>
            )}
            {item.suggested_action && (
              <p className="mt-2 text-xs font-medium text-ink-soft">
                Suggested action: {item.suggested_action}
              </p>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
