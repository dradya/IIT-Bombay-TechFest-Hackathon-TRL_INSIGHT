import { useState } from "react";
import {
  BadgeCheck,
  History,
  Loader2,
  Lock,
  ShieldCheck,
  UserCheck,
} from "lucide-react";
import { createReview, errorMessage } from "../services/api";
import { useApi } from "../hooks/useApi";
import type {
  EvidenceItem,
  ReviewDecision,
  ReviewListResponse,
  Prediction,
} from "../types";
import ErrorBanner from "./ErrorBanner";
import Skeleton from "./Skeleton";
import { useToast } from "./Toast";
import { formatDateTime, formatPercent } from "../utils/format";

interface ExpertReviewPanelProps {
  assessmentId: string;
  prediction: Prediction;
  evidence: EvidenceItem[];
  onReviewed?: () => void;
}

const DECISIONS: { value: ReviewDecision; label: string; description: string }[] = [
  {
    value: "accept",
    label: "Accept AI assessment",
    description: "The TRL and cited evidence are accepted as recorded.",
  },
  {
    value: "override",
    label: "Override TRL",
    description: "Record a corrected TRL; the original AI prediction stays intact.",
  },
  {
    value: "needs_more_evidence",
    label: "Request more evidence",
    description: "Mark the assessment for further investigation.",
  },
];

const STATUS_STYLE: Record<string, string> = {
  unreviewed: "border-slate-200 bg-slate-50 text-slate-600",
  accepted: "border-emerald-200 bg-emerald-50 text-emerald-700",
  overridden: "border-blue-200 bg-blue-50 text-blue-700",
  more_evidence_requested: "border-amber-200 bg-amber-50 text-amber-700",
};

/** Expert review workflow. AI output is immutable; reviews are append-only. */
export default function ExpertReviewPanel({
  assessmentId,
  prediction,
  evidence,
  onReviewed,
}: ExpertReviewPanelProps) {
  const reviews = useApi<ReviewListResponse>(
    `/api/assessments/${assessmentId}/reviews`,
  );
  const { showToast } = useToast();
  const [reviewer, setReviewer] = useState("");
  const [decision, setDecision] = useState<ReviewDecision>("accept");
  const [reviewedTrl, setReviewedTrl] = useState<string>(
    String(prediction.predicted_trl),
  );
  const [notes, setNotes] = useState("");
  const [selectedEvidence, setSelectedEvidence] = useState<string[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const status = reviews.data?.review_status ?? "unreviewed";

  const submit = async () => {
    if (!reviewer.trim()) {
      setError("Enter the reviewer's name.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await createReview(assessmentId, {
        reviewer_name: reviewer.trim(),
        decision,
        reviewed_trl: decision === "override" ? Number(reviewedTrl) : null,
        notes: notes.trim(),
        evidence_ids: selectedEvidence,
      });
      setNotes("");
      setSelectedEvidence([]);
      showToast("Review recorded — the AI prediction was not modified.");
      reviews.refetch();
      onReviewed?.();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-[1fr_auto]">
        <div className="rounded-xl border border-line bg-panel/60 p-4">
          <p className="eyebrow">Original AI prediction (immutable)</p>
          <div className="mt-2 flex flex-wrap items-baseline gap-3">
            <span className="stat-value text-2xl font-bold text-ink">
              TRL {prediction.predicted_trl}
            </span>
            <span className="text-sm text-muted">{prediction.level_name}</span>
            <span className="chip">
              {formatPercent(prediction.confidence, 0)} confidence
            </span>
            <span className="chip">
              {formatPercent(prediction.evidence_coverage, 0)} coverage
            </span>
          </div>
          <p className="mt-2 inline-flex items-center gap-1.5 text-[11px] text-faint">
            <Lock className="h-3 w-3" />
            Reviews are stored separately and never overwrite this prediction.
          </p>
        </div>
        <div className="flex flex-col items-start justify-center gap-2 rounded-xl border border-line p-4 sm:items-end">
          <span
            className={`rounded-full border px-3 py-1 text-xs font-bold capitalize ${
              STATUS_STYLE[status] ?? STATUS_STYLE.unreviewed
            }`}
          >
            {status.replace(/_/g, " ")}
          </span>
          <p className="text-[11px] text-faint">
            {reviews.data?.total ?? 0} review{(reviews.data?.total ?? 0) === 1 ? "" : "s"} recorded
          </p>
        </div>
      </div>

      {reviews.error && (
        <ErrorBanner
          message={reviews.error}
          networkError={reviews.networkError}
          onRetry={reviews.refetch}
        />
      )}

      <div className="rounded-xl border border-line p-4">
        <h3 className="inline-flex items-center gap-2 text-sm font-semibold text-ink">
          <UserCheck className="h-4 w-4 text-primary" />
          Record a review
        </h3>

        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <div>
            <label htmlFor="reviewer-name" className="label">
              Reviewer name <span className="text-danger">*</span>
            </label>
            <input
              id="reviewer-name"
              type="text"
              value={reviewer}
              onChange={(e) => setReviewer(e.target.value)}
              placeholder="e.g. Dr A. Rao"
              className="input"
              maxLength={120}
            />
          </div>
          <div>
            <label htmlFor="review-decision" className="label">
              Decision
            </label>
            <select
              id="review-decision"
              value={decision}
              onChange={(e) => setDecision(e.target.value as ReviewDecision)}
              className="input"
            >
              {DECISIONS.map((d) => (
                <option key={d.value} value={d.value}>
                  {d.label}
                </option>
              ))}
            </select>
          </div>
        </div>
        <p className="mt-1.5 text-[11px] text-faint">
          {DECISIONS.find((d) => d.value === decision)?.description}
        </p>

        {decision === "override" && (
          <div className="mt-3 max-w-xs">
            <label htmlFor="reviewed-trl" className="label">
              Corrected TRL <span className="text-danger">*</span>
            </label>
            <select
              id="reviewed-trl"
              value={reviewedTrl}
              onChange={(e) => setReviewedTrl(e.target.value)}
              className="input"
            >
              {Array.from({ length: 9 }, (_, i) => i + 1).map((level) => (
                <option key={level} value={level}>
                  TRL {level}
                </option>
              ))}
            </select>
          </div>
        )}

        <div className="mt-3">
          <label htmlFor="review-notes" className="label">
            Reviewer comments
          </label>
          <textarea
            id="review-notes"
            rows={3}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="What did you verify? Note any evidence you rejected or added."
            className="textarea"
            maxLength={4000}
          />
        </div>

        <fieldset className="mt-3">
          <legend className="label">
            Evidence accepted during review ({selectedEvidence.length} selected)
          </legend>
          <div className="scrollbar-thin max-h-44 space-y-1 overflow-auto rounded-xl border border-line bg-panel/60 p-2">
            {evidence.length === 0 ? (
              <p className="px-2 py-1 text-xs text-faint">No evidence items.</p>
            ) : (
              evidence.map((item) => {
                const checked = selectedEvidence.includes(item.id);
                return (
                  <label
                    key={item.id}
                    className={`flex cursor-pointer items-start gap-2 rounded-lg px-2 py-1.5 text-xs transition-colors ${
                      checked ? "bg-teal-50" : "hover:bg-white"
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() =>
                        setSelectedEvidence((prev) =>
                          checked
                            ? prev.filter((id) => id !== item.id)
                            : [...prev, item.id],
                        )
                      }
                      className="mt-0.5"
                    />
                    <span className="min-w-0">
                      <span className="line-clamp-2 text-ink-soft">{item.statement}</span>
                      <span className="mt-0.5 block text-[10px] text-faint">
                        {item.id} · {item.source_document}
                        {item.page_number !== null ? ` · page ${item.page_number}` : ""}
                      </span>
                    </span>
                  </label>
                );
              })
            )}
          </div>
        </fieldset>

        {error && (
          <div className="mt-3">
            <ErrorBanner message={error} />
          </div>
        )}

        <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
          <p className="inline-flex items-center gap-1.5 text-[11px] text-faint">
            <ShieldCheck className="h-3.5 w-3.5" />
            Self-reported claims in review notes are not source evidence.
          </p>
          <button
            type="button"
            onClick={() => void submit()}
            disabled={submitting}
            className="btn btn-primary"
          >
            {submitting ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <BadgeCheck className="h-4 w-4" />
            )}
            {submitting ? "Saving…" : "Record review"}
          </button>
        </div>
      </div>

      <div>
        <h3 className="mb-2 inline-flex items-center gap-2 text-sm font-semibold text-ink">
          <History className="h-4 w-4 text-faint" />
          Review history
        </h3>
        {reviews.loading && !reviews.data ? (
          <Skeleton className="h-24 w-full" />
        ) : (reviews.data?.items.length ?? 0) === 0 ? (
          <p className="rounded-xl border border-dashed border-line bg-panel/70 px-4 py-3 text-xs text-muted">
            No expert reviews yet. The AI assessment is currently unreviewed.
          </p>
        ) : (
          <ol className="space-y-2">
            {reviews.data!.items
              .slice()
              .reverse()
              .map((review) => (
                <li
                  key={review.id}
                  className="rounded-xl border border-line bg-white px-4 py-3"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-xs font-semibold text-ink">
                        {review.reviewer_name}
                      </span>
                      <span
                        className={`rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide ${
                          review.decision === "accept"
                            ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                            : review.decision === "override"
                              ? "border-blue-200 bg-blue-50 text-blue-700"
                              : "border-amber-200 bg-amber-50 text-amber-700"
                        }`}
                      >
                        {review.decision.replace(/_/g, " ")}
                      </span>
                      {review.reviewed_trl !== null && (
                        <span className="chip px-2 py-0 text-[10px]">
                          Corrected to TRL {review.reviewed_trl}
                        </span>
                      )}
                      {review.evidence_ids.length > 0 && (
                        <span className="chip px-2 py-0 text-[10px]">
                          {review.evidence_ids.length} evidence accepted
                        </span>
                      )}
                    </div>
                    <time className="text-[11px] text-faint" dateTime={review.created_at}>
                      {formatDateTime(review.created_at)}
                    </time>
                  </div>
                  {review.notes && (
                    <p className="mt-1.5 text-xs leading-relaxed text-muted">
                      {review.notes}
                    </p>
                  )}
                </li>
              ))}
          </ol>
        )}
      </div>
    </div>
  );
}
