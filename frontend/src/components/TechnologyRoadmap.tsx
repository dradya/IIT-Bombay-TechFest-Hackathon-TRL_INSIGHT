import {
  ArrowRight,
  CalendarClock,
  CheckCircle2,
  FlaskConical,
  FileText,
  ListChecks,
  Target,
} from "lucide-react";
import type { RoadmapPhase, TechnologyRoadmap as Roadmap } from "../types";

interface TechnologyRoadmapProps {
  roadmap?: Roadmap | null;
}

const HORIZON: Record<
  RoadmapPhase["horizon"],
  { label: string; tone: string; bar: string }
> = {
  now: {
    label: "Now",
    tone: "border-teal-200 bg-teal-50/60",
    bar: "from-teal-500 to-cyan-400",
  },
  next: {
    label: "Next",
    tone: "border-blue-200 bg-blue-50/50",
    bar: "from-blue-500 to-indigo-500",
  },
  later: {
    label: "Later",
    tone: "border-slate-200 bg-slate-50/60",
    bar: "from-slate-400 to-slate-300",
  },
};

const PRIORITY: Record<string, string> = {
  high: "bg-rose-50 text-rose-700 border-rose-200",
  medium: "bg-amber-50 text-amber-700 border-amber-200",
  low: "bg-slate-50 text-slate-600 border-slate-200",
};

/** Milestone-linked advancement plan. Every action carries a real milestone id. */
export default function TechnologyRoadmap({ roadmap }: TechnologyRoadmapProps) {
  if (!roadmap) {
    return (
      <div className="rounded-xl border border-dashed border-line bg-panel/70 px-4 py-4 text-sm text-muted">
        <p className="font-semibold text-ink-soft">Roadmap unavailable</p>
        <p className="mt-1 text-xs leading-relaxed">
          This assessment predates the 2.0 pipeline. Re-run the analysis to generate a
          milestone-linked progression plan.
        </p>
      </div>
    );
  }

  return (
    <div>
      <div className="flex flex-wrap items-center gap-2">
        <span className="chip">
          Current <strong className="text-ink">TRL {roadmap.current_trl}</strong>
        </span>
        <ArrowRight className="h-3.5 w-3.5 text-faint" />
        <span className="chip border-teal-200 bg-teal-50 text-teal-800">
          Target{" "}
          <strong>{roadmap.target_trl ? `TRL ${roadmap.target_trl}` : "not set"}</strong>
        </span>
        {roadmap.target_name && (
          <span className="text-xs text-faint">{roadmap.target_name}</span>
        )}
      </div>
      {roadmap.note && (
        <p className="mt-2 text-xs leading-relaxed text-faint">{roadmap.note}</p>
      )}

      <div className="mt-4 grid gap-3 lg:grid-cols-3">
        {roadmap.phases.map((phase) => {
          const style = HORIZON[phase.horizon] ?? HORIZON.later;
          return (
            <section
              key={phase.id}
              className={`rounded-xl border px-4 py-3.5 ${style.tone}`}
              aria-label={`${style.label} horizon`}
            >
              <div className="flex items-center justify-between gap-2">
                <h3 className="inline-flex items-center gap-1.5 text-sm font-bold text-ink">
                  <CalendarClock className="h-4 w-4" />
                  {style.label}
                </h3>
                {phase.target_trl && (
                  <span className="rounded-full bg-white/80 px-2 py-0.5 text-[10px] font-bold text-ink-soft ring-1 ring-inset ring-line">
                    TRL {phase.target_trl}
                  </span>
                )}
              </div>
              <div className={`mt-2 h-1 w-14 rounded-full bg-gradient-to-r ${style.bar}`} />
              <p className="mt-2 text-[11px] leading-relaxed text-muted">
                {phase.summary}
              </p>

              {phase.items.length === 0 ? (
                <p className="mt-3 text-xs italic text-faint">
                  No actions in this horizon.
                </p>
              ) : (
                <ul className="mt-3 space-y-2.5">
                  {phase.items.map((item) => (
                    <li
                      key={item.id}
                      className="rounded-lg border border-white/80 bg-white/85 px-3 py-2.5 shadow-sm"
                    >
                      <div className="flex flex-wrap items-start justify-between gap-1.5">
                        <p className="text-xs font-semibold leading-snug text-ink">
                          {item.title}
                        </p>
                        <span
                          className={`rounded-full border px-1.5 py-0 text-[9px] font-bold uppercase ${
                            PRIORITY[item.priority] ?? PRIORITY.low
                          }`}
                        >
                          {item.priority}
                        </span>
                      </div>
                      {item.description && (
                        <p className="mt-1 text-[11px] leading-relaxed text-muted">
                          {item.description}
                        </p>
                      )}
                      {item.milestone_label && (
                        <p className="mt-1.5 inline-flex items-center gap-1 text-[10px] font-semibold text-primary-dark">
                          <Target className="h-3 w-3" />
                          {item.milestone_label}
                        </p>
                      )}
                      {item.actions.length > 0 && (
                        <ul className="mt-1.5 list-disc space-y-0.5 pl-4 text-[11px] leading-relaxed text-ink-soft">
                          {item.actions.map((a, i) => (
                            <li key={i}>{a}</li>
                          ))}
                        </ul>
                      )}
                      {item.validation_experiments.length > 0 && (
                        <div className="mt-1.5">
                          <p className="inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-wide text-faint">
                            <FlaskConical className="h-3 w-3" />
                            Validation
                          </p>
                          <ul className="mt-0.5 list-disc space-y-0.5 pl-4 text-[11px] text-ink-soft">
                            {item.validation_experiments.map((a, i) => (
                              <li key={i}>{a}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                      {item.documentation.length > 0 && (
                        <div className="mt-1.5">
                          <p className="inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-wide text-faint">
                            <FileText className="h-3 w-3" />
                            Documentation
                          </p>
                          <ul className="mt-0.5 list-disc space-y-0.5 pl-4 text-[11px] text-ink-soft">
                            {item.documentation.map((a, i) => (
                              <li key={i}>{a}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                      {item.success_criteria.length > 0 && (
                        <div className="mt-1.5">
                          <p className="inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-wide text-faint">
                            <ListChecks className="h-3 w-3" />
                            Acceptance criteria
                          </p>
                          <ul className="mt-0.5 list-disc space-y-0.5 pl-4 text-[11px] text-ink-soft">
                            {item.success_criteria.map((a, i) => (
                              <li key={i}>{a}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </li>
                  ))}
                </ul>
              )}
              {phase.items.length > 0 && phase.items.every((i) => i.status === "confirmed") && (
                <p className="mt-2 inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-700">
                  <CheckCircle2 className="h-3.5 w-3.5" />
                  All linked milestones confirmed
                </p>
              )}
            </section>
          );
        })}
      </div>
    </div>
  );
}
