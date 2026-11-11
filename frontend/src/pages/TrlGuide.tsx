import { useMemo, useState } from "react";
import { BookOpen, ChevronDown, ChevronRight, Layers, Tag } from "lucide-react";
import { useApi } from "../hooks/useApi";
import type { TRLReferenceResponse } from "../types";
import PageHeader from "../components/PageHeader";
import ErrorBanner from "../components/ErrorBanner";
import EmptyState from "../components/EmptyState";
import Skeleton from "../components/Skeleton";
import TRLProgressionScale from "../components/TRLProgressionScale";

const STATUS_INFO: Record<
  string,
  { label: string; tone: string; description: string }
> = {
  confirmed: {
    label: "Confirmed",
    tone: "border-green-200 bg-green-50 text-green-700",
    description:
      "A completed, non-future statement in the document that matches the milestone's defining indicators. Only confirmed evidence counts towards readiness.",
  },
  not_found: {
    label: "Not found",
    tone: "border-slate-200 bg-slate-50 text-slate-600",
    description:
      "No excerpt in the document addresses this milestone — the capability has not been evidenced yet.",
  },
  contradicted: {
    label: "Contradicted",
    tone: "border-red-200 bg-red-50 text-red-700",
    description:
      "The document contains evidence that conflicts with the milestone being complete (failures, reversals, negated statements).",
  },
  unclear: {
    label: "Unclear",
    tone: "border-amber-200 bg-amber-50 text-amber-700",
    description:
      "Relevant excerpts exist but their status cannot be determined confidently — ambiguous, partial or out-of-context statements.",
  },
};

export default function TrlGuide() {
  const { data, loading, error, networkError, refetch } =
    useApi<TRLReferenceResponse>("/api/trl/reference");
  const [openLevel, setOpenLevel] = useState<number | null>(null);

  const milestoneByTrl = useMemo(() => {
    const map = new Map<number, TRLReferenceResponse["milestones"][number]>();
    data?.milestones.forEach((m) => {
      if (!map.has(m.trl)) map.set(m.trl, m);
    });
    return map;
  }, [data]);

  if (loading && !data) {
    return (
      <div>
        <PageHeader
          title="TRL Reference Guide"
          subtitle="The 9-level readiness framework, milestones and evidence rules"
        />
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="card p-5">
              <Skeleton className="h-6 w-72" />
              <Skeleton className="mt-3 h-4 w-full" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (error && !data) {
    return (
      <div>
        <PageHeader
          title="TRL Reference Guide"
          subtitle="The 9-level readiness framework, milestones and evidence rules"
        />
        <ErrorBanner message={error} networkError={networkError} onRetry={refetch} />
      </div>
    );
  }

  if (!data) return null;

  const meta = data.meta as {
    name?: string;
    description?: string;
    scale_note?: string;
  };

  const levelNames = Object.fromEntries(
    data.levels.map((level) => [level.level, level.name]),
  ) as Record<number, string>;

  return (
    <div className="max-w-5xl">
      <PageHeader
        title="TRL Reference Guide"
        subtitle={meta.description || "The 9-level readiness framework, milestones and evidence rules"}
        actions={
          <span className="chip">
            <BookOpen className="h-3.5 w-3.5 text-primary" />
            Framework v{data.version}
          </span>
        }
      />

      {meta.scale_note && (
        <p className="panel mb-4 px-4 py-3 text-xs leading-relaxed text-muted">
          {meta.scale_note}
        </p>
      )}

      {/* Visual progression scale — reference only, no assessment loaded. */}
      <div className="card mb-4 p-5">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="section-title">Progression scale</h2>
            <p className="mt-0.5 text-xs text-faint">
              Click a level to open its definition. No assessment is loaded, so
              readiness colours are intentionally neutral.
            </p>
          </div>
          <span className="chip">
            <Layers className="h-3.5 w-3.5 text-primary" />
            9 levels · {data.milestones.length} milestones
          </span>
        </div>
        <TRLProgressionScale
          predicted={0}
          selected={openLevel}
          onSelect={(level) =>
            setOpenLevel((current) => (current === level ? null : level))
          }
          levelNames={levelNames}
        />
      </div>

      {/* Levels accordion */}
      <div className="space-y-3">
        {data.levels.map((level) => {
          const milestone = milestoneByTrl.get(level.level);
          const isOpen = openLevel === level.level;
          return (
            <div
              key={level.level}
              className={`card overflow-hidden transition-all duration-200 ${
                isOpen ? "border-teal-200 shadow-[0_18px_40px_-28px_rgba(13,148,136,0.5)]" : ""
              }`}
            >
              <button
                type="button"
                onClick={() => setOpenLevel(isOpen ? null : level.level)}
                className="flex w-full items-center gap-4 px-5 py-4 text-left transition-colors hover:bg-teal-50/25"
                aria-expanded={isOpen}
              >
                <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-teal-500 to-teal-700 text-base font-bold text-white shadow-[0_10px_20px_-12px_rgba(13,148,136,0.9)]">
                  {level.level}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-semibold text-ink">{level.name}</span>
                    <span className="chip px-2 py-0 text-[11px]">
                      {level.category}
                    </span>
                  </span>
                  <span className="mt-0.5 block truncate text-xs text-faint">
                    {level.description}
                  </span>
                </span>
                {isOpen ? (
                  <ChevronDown className="h-5 w-5 shrink-0 text-faint" />
                ) : (
                  <ChevronRight className="h-5 w-5 shrink-0 text-faint" />
                )}
              </button>

              {isOpen && (
                <div className="border-t border-line px-5 py-4">
                  <p className="text-sm leading-relaxed text-muted">
                    {level.description}
                  </p>

                  <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-3">
                    <div>
                      <h3 className="eyebrow mb-2">Examples</h3>
                      {level.examples.length === 0 ? (
                        <p className="text-xs text-faint">None listed.</p>
                      ) : (
                        <ul className="space-y-1.5">
                          {level.examples.map((e, i) => (
                            <li key={i} className="flex gap-2 text-sm leading-relaxed text-muted">
                              <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-primary" />
                              {e}
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                    <div>
                      <h3 className="eyebrow mb-2">Requirements</h3>
                      {level.requirements.length === 0 ? (
                        <p className="text-xs text-faint">None listed.</p>
                      ) : (
                        <ul className="space-y-1.5">
                          {level.requirements.map((e, i) => (
                            <li key={i} className="flex gap-2 text-sm leading-relaxed text-muted">
                              <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-secondary" />
                              {e}
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                    <div>
                      <h3 className="eyebrow mb-2">Progression criteria</h3>
                      {level.progression_criteria.length === 0 ? (
                        <p className="text-xs text-faint">None listed.</p>
                      ) : (
                        <ul className="space-y-1.5">
                          {level.progression_criteria.map((e, i) => (
                            <li key={i} className="flex gap-2 text-sm leading-relaxed text-muted">
                              <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-warning" />
                              {e}
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  </div>

                  {/* Defining milestone */}
                  {milestone && (
                    <div className="mt-4 rounded-xl border border-teal-200/70 bg-teal-50/60 p-4">
                      <div className="flex items-start gap-2.5">
                        <Tag className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                        <div className="min-w-0">
                          <p className="text-sm font-semibold text-primary-dark">
                            Defining milestone: {milestone.label}
                          </p>
                          <p className="mt-0.5 text-sm leading-relaxed text-muted">
                            {milestone.description}
                          </p>
                          {milestone.defining_indicators.length > 0 && (
                            <div className="mt-2.5">
                              <p className="eyebrow mb-1.5">Defining indicators</p>
                              <div className="flex flex-wrap gap-1.5">
                                {milestone.defining_indicators.map((ind, i) => (
                                  <span
                                    key={i}
                                    className="rounded-full border border-teal-200/80 bg-white px-2.5 py-1 text-xs text-primary-dark"
                                  >
                                    {ind}
                                  </span>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Evidence categories */}
      <div className="card mt-6 overflow-hidden">
        <div className="flex items-center gap-3 border-b border-line px-5 py-4">
          <span className="icon-tile h-9 w-9 shrink-0">
            <Layers className="h-4 w-4" />
          </span>
          <div>
            <h2 className="section-title">Evidence categories</h2>
            <p className="mt-0.5 text-xs text-faint">
              {data.evidence_categories.length} categories used to classify extracted excerpts
            </p>
          </div>
        </div>
        <div className="grid grid-cols-1 gap-px bg-line md:grid-cols-2">
          {data.evidence_categories.map((cat) => {
            const primary = data.milestones.find((m) => m.id === cat.primary_milestone);
            return (
              <div key={cat.id} className="bg-white px-5 py-4 transition-colors hover:bg-teal-50/20">
                <div className="flex items-start justify-between gap-2">
                  <h3 className="text-sm font-semibold text-ink">{cat.label}</h3>
                  {primary && (
                    <span className="chip shrink-0 px-2 py-0 text-[11px]">
                      → TRL {primary.trl}
                    </span>
                  )}
                </div>
                <p className="mt-1 text-sm leading-relaxed text-muted">{cat.description}</p>
                {primary && (
                  <p className="mt-1.5 text-xs text-faint">
                    Primary milestone: {primary.label}
                  </p>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Evidence statuses */}
      <div className="card mt-6 overflow-hidden">
        <div className="flex items-center gap-3 border-b border-line px-5 py-4">
          <span className="icon-tile h-9 w-9 shrink-0">
            <BookOpen className="h-4 w-4" />
          </span>
          <div>
            <h2 className="section-title">Evidence statuses</h2>
            <p className="mt-0.5 text-xs text-faint">
              The four states every milestone and excerpt can take
            </p>
          </div>
        </div>
        <div className="grid grid-cols-1 gap-4 p-5 md:grid-cols-2">
          {data.evidence_statuses.map((status) => {
            const info = STATUS_INFO[status] ?? {
              label: status,
              tone: "border-slate-200 bg-slate-50 text-slate-600",
              description: "No description available.",
            };
            return (
              <div key={status} className="rounded-xl border border-line bg-white p-4">
                <span
                  className={`inline-flex rounded-full border px-2.5 py-0.5 text-xs font-semibold ${info.tone}`}
                >
                  {info.label}
                </span>
                <p className="mt-2 text-sm leading-relaxed text-muted">{info.description}</p>
              </div>
            );
          })}
        </div>
        <div className="mx-5 mb-5 flex items-start gap-3 rounded-xl border border-amber-200/80 bg-amber-50 px-4 py-3">
          <span className="text-sm font-semibold text-amber-800">
            Important:
          </span>
          <p className="text-sm leading-relaxed text-amber-800">
            Proposed or future-work statements never count as completed evidence. A
            sentence such as “we plan to validate the prototype” is recorded as{" "}
            <em>proposed</em> and does not confirm the milestone — only completed,
            non-negated statements do.
          </p>
        </div>
      </div>

      {/* Assessment rules */}
      {Object.keys(data.assessment_rules).length > 0 && (
        <div className="card mt-6 p-5">
          <h2 className="section-title mb-3">Assessment rules</h2>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
            {Object.entries(data.assessment_rules).map(([key, value]) => (
              <div key={key} className="panel px-3 py-2.5">
                <p className="truncate text-[11px] text-faint" title={key}>
                  {key.replace(/_/g, " ")}
                </p>
                <p className="mt-0.5 truncate text-sm font-semibold text-ink" title={String(value)}>
                  {String(value)}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {!data.levels.length && (
        <div className="mt-4">
          <EmptyState
            icon={BookOpen}
            title="No framework levels returned"
            description="The backend returned an empty reference framework."
          />
        </div>
      )}
    </div>
  );
}
