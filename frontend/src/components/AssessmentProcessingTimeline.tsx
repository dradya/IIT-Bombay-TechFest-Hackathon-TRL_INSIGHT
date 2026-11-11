import { CheckCircle2, Circle, Loader2, TriangleAlert } from "lucide-react";

export interface ProcessingStage {
  id: string;
  label: string;
  detail?: string;
  /** done = finished, active = in flight, pending = queued, error = failed. */
  status: "done" | "active" | "pending" | "error";
}

interface AssessmentProcessingTimelineProps {
  stages: ProcessingStage[];
  /** Optional note displayed under the timeline. */
  note?: string;
}

/**
 * Pipeline stage list. Statuses come from the page's real state: upload and
 * extraction complete when the API responds; a single analysis request covers
 * retrieval → prediction → gap analysis, so those stages stay grouped rather
 * than pretending to know sub-step timings.
 */
export default function AssessmentProcessingTimeline({
  stages,
  note,
}: AssessmentProcessingTimelineProps) {
  return (
    <div>
      <ol className="space-y-3">
        {stages.map((stage) => {
          const Icon =
            stage.status === "done"
              ? CheckCircle2
              : stage.status === "active"
                ? Loader2
                : stage.status === "error"
                  ? TriangleAlert
                  : Circle;
          return (
            <li key={stage.id} className="flex items-start gap-3">
              <span
                className={`mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border ${
                  stage.status === "done"
                    ? "border-emerald-200 bg-emerald-50 text-emerald-600"
                    : stage.status === "active"
                      ? "border-teal-200 bg-teal-50 text-primary"
                      : stage.status === "error"
                        ? "border-rose-200 bg-rose-50 text-rose-600"
                        : "border-line bg-panel text-faint"
                }`}
              >
                <Icon
                  className={`h-3.5 w-3.5 ${
                    stage.status === "active" ? "animate-spin" : ""
                  }`}
                />
              </span>
              <div className="min-w-0">
                <p
                  className={`text-sm font-semibold ${
                    stage.status === "pending" ? "text-faint" : "text-ink"
                  }`}
                >
                  {stage.label}
                </p>
                {stage.detail && (
                  <p className="mt-0.5 text-xs leading-relaxed text-faint">
                    {stage.detail}
                  </p>
                )}
              </div>
            </li>
          );
        })}
      </ol>
      {note && (
        <p className="mt-3 rounded-xl border border-line bg-panel px-3 py-2 text-[11px] leading-relaxed text-muted">
          {note}
        </p>
      )}
    </div>
  );
}
