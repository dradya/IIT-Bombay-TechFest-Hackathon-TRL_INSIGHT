import { ArrowRight, CircleHelp, FileQuestion } from "lucide-react";
import type { MilestoneStatusModel } from "../types";
import StatusBadge from "./StatusBadge";

interface MissingMilestoneCardProps {
  milestone: MilestoneStatusModel;
  /** Optional handler for "generate questions" / roadmap focus. */
  onAsk?: (milestone: MilestoneStatusModel) => void;
}

const CALL_TO_ACTION: Record<string, string> = {
  not_found: "No confirmed evidence addresses this milestone yet.",
  unclear: "Evidence exists but does not clearly demonstrate completion.",
  contradicted: "Evidence conflicts with the milestone claim.",
  confirmed: "Milestone is confirmed by source evidence.",
};

/** Missing / unclear milestone with the reason and next action. */
export default function MissingMilestoneCard({
  milestone,
  onAsk,
}: MissingMilestoneCardProps) {
  const isMissing = milestone.status === "not_found";
  return (
    <div className="rounded-xl border border-line bg-white px-4 py-3.5">
      <div className="flex items-start gap-3">
        <span
          className={`mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border text-[11px] font-bold ${
            milestone.status === "contradicted"
              ? "border-rose-200 bg-rose-50 text-rose-700"
              : milestone.status === "unclear"
                ? "border-amber-200 bg-amber-50 text-amber-700"
                : "border-line bg-panel text-muted"
          }`}
        >
          T{milestone.trl}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-sm font-semibold text-ink">{milestone.label}</p>
            <StatusBadge kind="milestone" value={milestone.status} />
            <span className="chip px-2 py-0 text-[10px]">
              {milestone.evidence_count} evidence
            </span>
          </div>
          <p className="mt-1 text-xs leading-relaxed text-muted">
            {milestone.summary || CALL_TO_ACTION[milestone.status]}
          </p>
          <p className="mt-1.5 inline-flex items-center gap-1.5 text-[11px] font-medium text-faint">
            {isMissing ? (
              <FileQuestion className="h-3.5 w-3.5" />
            ) : (
              <CircleHelp className="h-3.5 w-3.5" />
            )}
            {CALL_TO_ACTION[milestone.status]}
          </p>
        </div>
        {onAsk && (
          <button
            type="button"
            onClick={() => onAsk(milestone)}
            className="btn btn-secondary btn-sm shrink-0"
          >
            Ask
            <ArrowRight className="h-3.5 w-3.5" />
          </button>
        )}
      </div>
    </div>
  );
}
