import {
  CalendarPlus,
  GitBranch,
  RefreshCw,
  ScanSearch,
  UserCheck,
} from "lucide-react";
import type { TimelineEvent } from "../types";
import { formatDateTime } from "../utils/format";

interface AssessmentTimelineProps {
  events: TimelineEvent[];
  /** Optional empty-state message. */
  emptyMessage?: string;
}

const KIND_META = {
  created: {
    icon: CalendarPlus,
    tone: "border-teal-200 bg-teal-50 text-teal-700",
    dot: "bg-teal-500",
  },
  reassessment: {
    icon: RefreshCw,
    tone: "border-blue-200 bg-blue-50 text-blue-700",
    dot: "bg-blue-500",
  },
  review: {
    icon: UserCheck,
    tone: "border-indigo-200 bg-indigo-50 text-indigo-700",
    dot: "bg-indigo-500",
  },
  analysis: {
    icon: ScanSearch,
    tone: "border-slate-200 bg-slate-50 text-slate-600",
    dot: "bg-slate-400",
  },
} as const;

/** Append-only assessment history (created, reassessed, reviewed, analysed). */
export default function AssessmentTimeline({
  events,
  emptyMessage = "No history events have been recorded for this assessment yet.",
}: AssessmentTimelineProps) {
  if (events.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-line bg-panel/70 px-4 py-4 text-sm text-muted">
        {emptyMessage}
      </div>
    );
  }

  return (
    <ol className="relative space-y-4 border-l border-line pl-5">
      {events.map((event) => {
        const meta = KIND_META[event.kind] ?? KIND_META.analysis;
        const Icon = meta.icon;
        return (
          <li key={event.id} className="relative">
            <span
              className={`absolute -left-[29px] flex h-6 w-6 items-center justify-center rounded-full border-2 border-white shadow-sm ${meta.tone}`}
            >
              <Icon className="h-3 w-3" />
            </span>
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <p className="text-sm font-semibold text-ink">{event.title}</p>
              <time className="text-[11px] text-faint" dateTime={event.at}>
                {formatDateTime(event.at)}
              </time>
            </div>
            {event.description && (
              <p className="mt-0.5 text-xs leading-relaxed text-muted">
                {event.description}
              </p>
            )}
            <div className="mt-1 flex flex-wrap items-center gap-1.5 text-[11px] text-faint">
              {event.actor && (
                <span className="inline-flex items-center gap-1">
                  <GitBranch className="h-3 w-3" />
                  {event.actor}
                </span>
              )}
              {typeof event.metadata?.predicted_trl === "number" && (
                <span className="chip px-2 py-0 text-[10px]">
                  TRL {String(event.metadata.predicted_trl)}
                </span>
              )}
              {typeof event.metadata?.parent_assessment_id === "string" && (
                <span className="chip px-2 py-0 text-[10px]">
                  Parent {event.metadata.parent_assessment_id}
                </span>
              )}
              {typeof event.metadata?.child_assessment_id === "string" && (
                <span className="chip px-2 py-0 text-[10px]">
                  Child {event.metadata.child_assessment_id}
                </span>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
