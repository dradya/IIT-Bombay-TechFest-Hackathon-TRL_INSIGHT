import { useMemo, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import {
  AlertOctagon,
  AlertTriangle,
  ArrowLeft,
  BadgeCheck,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  CircleHelp,
  ClipboardCheck,
  Download,
  FileJson,
  FileText,
  GitBranch,
  Info,
  ListChecks,
  Map as MapIcon,
  Network,
  SearchCheck,
  ShieldCheck,
  Sparkles,
  Target,
  UserCheck,
  XCircle,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useApi } from "../hooks/useApi";
import { downloadFile, errorMessage, reassess } from "../services/api";
import type {
  AssessmentResult,
  AssessmentTimeline as AssessmentTimelineModel,
  EvidenceCategoryCount,
  EvidenceItem,
  ExpertAnswerStatus,
  MilestoneStatusModel,
  Questionnaire,
  TRLReferenceResponse,
} from "../types";
import PageHeader from "../components/PageHeader";
import ErrorBanner, { WarningBanner } from "../components/ErrorBanner";
import ConfidenceRing from "../components/ConfidenceRing";
import TRLProgressionScale from "../components/TRLProgressionScale";
import EvidenceTable from "../components/EvidenceTable";
import StatusBadge from "../components/StatusBadge";
import EmptyState from "../components/EmptyState";
import Skeleton from "../components/Skeleton";
import EvidenceKnowledgeGraph from "../components/EvidenceKnowledgeGraph";
import SHAPExplanationChart from "../components/SHAPExplanationChart";
import ContradictionAlert from "../components/ContradictionAlert";
import TechnologyRoadmap from "../components/TechnologyRoadmap";
import DocumentComparisonViewer from "../components/DocumentComparisonViewer";
import AssessmentTimeline from "../components/AssessmentTimeline";
import ExpertReviewPanel from "../components/ExpertReviewPanel";
import ConfidenceIndicator from "../components/ConfidenceIndicator";
import EvidenceCoverageIndicator from "../components/EvidenceCoverageIndicator";
import MissingMilestoneCard from "../components/MissingMilestoneCard";
import { useToast } from "../components/Toast";
import { formatDate, formatPercent, formatNumber } from "../utils/format";
import {
  Bar,
  BarChart,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

type TabKey =
  | "overview"
  | "evidence"
  | "graph"
  | "explainability"
  | "contradictions"
  | "roadmap"
  | "documents"
  | "review";

const TABS: { key: TabKey; label: string; icon: LucideIcon }[] = [
  { key: "overview", label: "Overview", icon: Info },
  { key: "evidence", label: "Evidence", icon: SearchCheck },
  { key: "graph", label: "Knowledge graph", icon: Network },
  { key: "explainability", label: "Explainability", icon: Sparkles },
  { key: "contradictions", label: "Contradictions", icon: AlertOctagon },
  { key: "roadmap", label: "Roadmap & gaps", icon: MapIcon },
  { key: "documents", label: "Documents & timeline", icon: FileText },
  { key: "review", label: "Expert review", icon: UserCheck },
];

const chartTooltipStyle = {
  borderRadius: 12,
  border: "1px solid #E5EAF2",
  boxShadow: "0 18px 40px -24px rgba(10,22,40,0.45)",
  fontSize: 12,
  padding: "8px 10px",
} as const;

function isTabKey(value: string | null): value is TabKey {
  return TABS.some((tab) => tab.key === value);
}

function SectionCard({
  title,
  subtitle,
  icon: Icon,
  actions,
  children,
}: {
  title: string;
  subtitle?: string;
  icon?: LucideIcon;
  actions?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="card overflow-hidden">
      <div className="flex flex-wrap items-center gap-3 border-b border-line px-5 py-4">
        {Icon && (
          <span className="icon-tile h-9 w-9 shrink-0">
            <Icon className="h-4 w-4" />
          </span>
        )}
        <div className="min-w-0 flex-1">
          <h2 className="section-title">{title}</h2>
          {subtitle && <p className="mt-0.5 text-xs text-faint">{subtitle}</p>}
        </div>
        {actions}
      </div>
      <div className="p-5">{children}</div>
    </section>
  );
}

function DarkChip({ label, dot = "bg-teal-300" }: { label: string; dot?: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-white/15 bg-white/[0.08] px-2.5 py-1 text-[11px] font-semibold text-teal-50">
      <span className={`h-1.5 w-1.5 rounded-full ${dot}`} />
      {label}
    </span>
  );
}

function MilestoneRow({ m }: { m: MilestoneStatusModel }) {
  const icon =
    m.status === "confirmed" ? (
      <CheckCircle2 className="h-4 w-4 text-emerald-600" />
    ) : m.status === "contradicted" ? (
      <XCircle className="h-4 w-4 text-rose-600" />
    ) : m.status === "unclear" ? (
      <CircleHelp className="h-4 w-4 text-amber-600" />
    ) : (
      <span className="inline-block h-3.5 w-3.5 rounded-full border-2 border-slate-300" />
    );
  const tileTone =
    m.status === "confirmed"
      ? "border-emerald-200/70 bg-emerald-50 text-emerald-700"
      : m.status === "contradicted"
        ? "border-rose-200/70 bg-rose-50 text-rose-700"
        : m.status === "unclear"
          ? "border-amber-200/70 bg-amber-50 text-amber-700"
          : "border-line bg-panel text-muted";
  return (
    <li className="flex items-start gap-3 border-b border-line/70 py-3.5 last:border-0">
      <span
        className={`mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border text-[11px] font-bold ${tileTone}`}
      >
        T{m.trl}
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm font-semibold text-ink">{m.label}</span>
          <StatusBadge kind="milestone" value={m.status} />
          <span className="chip px-2 py-0 text-[11px]">
            {m.evidence_count} evidence
          </span>
        </div>
        {m.summary && (
          <p className="mt-1 text-xs leading-relaxed text-muted">{m.summary}</p>
        )}
      </div>
      <span className="mt-1 shrink-0">{icon}</span>
    </li>
  );
}

function Collapsible({
  title,
  count,
  children,
}: {
  title: string;
  count: number;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div className="overflow-hidden rounded-xl border border-line">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between gap-2 bg-panel/60 px-4 py-2.5 text-left text-sm font-semibold text-ink-soft transition-colors hover:bg-panel"
        aria-expanded={open}
      >
        <span>
          {title}{" "}
          <span className="ml-1 font-normal text-faint">({count})</span>
        </span>
        {open ? (
          <ChevronDown className="h-4 w-4 text-faint" />
        ) : (
          <ChevronRight className="h-4 w-4 text-faint" />
        )}
      </button>
      {open && <div className="border-t border-line px-4 py-3">{children}</div>}
    </div>
  );
}

function EvidenceExcerpt({ e }: { e: EvidenceItem }) {
  return (
    <div className="mb-2 rounded-xl border border-line bg-panel px-3 py-2.5 text-sm text-ink-soft last:mb-0">
      <p className="leading-relaxed">{e.statement}</p>
      <p className="mt-1.5 text-xs text-faint">
        {e.source_document}
        {e.page_number !== null
          ? ` · page ${e.page_number}`
          : e.location
            ? ` · ${e.location}`
            : ""}
        {e.status ? ` · ${e.status}` : ""}
      </p>
    </div>
  );
}

function UnavailableBlock({
  title,
  description,
  icon: Icon = Info,
}: {
  title: string;
  description: string;
  icon?: LucideIcon;
}) {
  return (
    <div className="rounded-xl border border-dashed border-line bg-panel/70 px-4 py-5">
      <div className="flex items-start gap-3">
        <span className="icon-tile h-9 w-9 shrink-0">
          <Icon className="h-4 w-4" />
        </span>
        <div>
          <p className="text-sm font-semibold text-ink-soft">{title}</p>
          <p className="mt-1 text-xs leading-relaxed text-muted">{description}</p>
        </div>
      </div>
    </div>
  );
}

function LegendDot({ className, label }: { className: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className={`h-2.5 w-2.5 rounded-sm ${className}`} />
      {label}
    </span>
  );
}

export default function AssessmentDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { showToast } = useToast();
  const [params, setParams] = useSearchParams();
  const requestedTab = params.get("tab");
  const activeTab: TabKey = isTabKey(requestedTab) ? requestedTab : "overview";
  const [selectedLevel, setSelectedLevel] = useState<number | null>(null);
  const [exporting, setExporting] = useState<string | null>(null);

  const assessment = useApi<AssessmentResult>(
    id ? `/api/assessments/${id}` : null,
  );
  const reference = useApi<TRLReferenceResponse>("/api/trl/reference");
  const timeline = useApi<AssessmentTimelineModel>(
    id && activeTab === "documents"
      ? `/api/assessments/${id}/timeline`
      : null,
  );

  const data = assessment.data;
  const referenceData = reference.data;

  const setTab = (tab: TabKey) => {
    const next = new URLSearchParams(params);
    next.set("tab", tab);
    setParams(next, { replace: true });
  };

  const onTabKeyDown = (event: React.KeyboardEvent, index: number) => {
    if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
    event.preventDefault();
    const delta = event.key === "ArrowRight" ? 1 : -1;
    const next = TABS[(index + delta + TABS.length) % TABS.length];
    setTab(next.key);
    const element = document.getElementById(`tab-${next.key}`);
    element?.focus();
  };

  const selectedLevelInfo = useMemo(() => {
    if (selectedLevel === null) return null;
    return referenceData?.levels.find((l) => l.level === selectedLevel) ?? null;
  }, [selectedLevel, referenceData]);

  const levelNames = useMemo(() => {
    const map: Record<number, string> = {};
    referenceData?.levels.forEach((l) => {
      map[l.level] = l.name;
    });
    return map;
  }, [referenceData]);

  const milestoneCounts = useMemo(() => {
    const counts = {
      confirmed: 0,
      not_found: 0,
      unclear: 0,
      contradicted: 0,
    };
    data?.milestones.forEach((m) => {
      counts[m.status] += 1;
    });
    return counts;
  }, [data]);

  const categoryMax = useMemo(() => {
    if (!data) return 1;
    return Math.max(1, ...data.evidence_summary.by_category.map((c) => c.count));
  }, [data]);

  if (assessment.loading && !data) {
    return (
      <div>
        <PageHeader title="Assessment" subtitle="Loading assessment result…" />
        <div className="space-y-4">
          <Skeleton className="h-64 w-full rounded-[1.5rem]" />
          <div className="card p-5">
            <Skeleton className="h-4 w-48" />
            <Skeleton className="mt-4 h-28 w-full" />
          </div>
          <div className="card p-5">
            <Skeleton className="h-64 w-full" />
          </div>
        </div>
      </div>
    );
  }

  if (assessment.error && !data) {
    return (
      <div>
        <PageHeader title="Assessment" subtitle="Could not load this assessment" />
        <ErrorBanner
          message={assessment.error}
          networkError={assessment.networkError}
          onRetry={assessment.refetch}
          hint={
            assessment.error.includes("not found")
              ? "This assessment id does not exist in the database."
              : undefined
          }
        />
        <button
          type="button"
          onClick={() => navigate("/history")}
          className="btn btn-secondary mt-4"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to history
        </button>
      </div>
    );
  }

  if (!data) return null;

  const p = data.prediction;
  const meta = data.metadata;
  const gap = data.gap_analysis;
  const verification = data.verification;
  const uncertainty = data.uncertainty ?? null;
  const contradictions = data.contradictions ?? null;
  const graph = data.graph ?? null;
  const explanation = data.model_explanation ?? null;
  const roadmap = data.roadmap ?? null;
  const questionnaire = data.questionnaire ?? null;
  const documents = data.documents ?? [];
  const isLegacy = !data.uncertainty && !data.documents;

  const doExport = async (kind: "pdf" | "json") => {
    setExporting(kind);
    try {
      // The PDF endpoint is /report (not /pdf); JSON uses /json.
      const endpoint = kind === "pdf" ? "report" : "json";
      await downloadFile(
        `/api/assessments/${data.id}/${endpoint}`,
        `${data.id}.${kind}`,
      );
      showToast(kind === "pdf" ? "PDF report downloaded" : "JSON exported");
    } catch (err) {
      showToast(errorMessage(err), "error");
    } finally {
      setExporting(null);
    }
  };

  const probabilityData = p.probabilities.map((pr) => ({
    name: `TRL ${pr.level}`,
    probability: pr.probability,
  }));

  const tabCount = (key: TabKey): number | null => {
    if (key === "evidence") return data.evidence_summary.total;
    if (key === "contradictions") return contradictions?.total ?? null;
    if (key === "documents") return documents.length || null;
    return null;
  };

  return (
    <div className="max-w-6xl">
      {/* Header */}
      <div className="mb-5">
        <button
          type="button"
          onClick={() => navigate(-1)}
          className="mb-2 inline-flex items-center gap-1.5 text-sm font-medium text-muted transition-colors hover:text-ink"
        >
          <ArrowLeft className="h-4 w-4" />
          Back
        </button>
        <PageHeader
          title={meta.technology_name || "Untitled technology"}
          subtitle={
            [
              meta.domain,
              meta.organization,
              formatDate(data.created_at),
              meta.filename,
            ]
              .filter(Boolean)
              .join("  ·  ") || undefined
          }
          actions={
            <>
              <button
                type="button"
                onClick={() => navigate("/history")}
                className="btn btn-secondary"
              >
                <ArrowLeft className="h-4 w-4" />
                History
              </button>
              <button
                type="button"
                onClick={() => void doExport("pdf")}
                disabled={exporting !== null}
                className="btn btn-primary"
              >
                <Download className="h-4 w-4" />
                {exporting === "pdf" ? "Preparing…" : "Download PDF"}
              </button>
              <button
                type="button"
                onClick={() => void doExport("json")}
                disabled={exporting !== null}
                className="btn btn-secondary"
              >
                <FileJson className="h-4 w-4" />
                {exporting === "json" ? "Preparing…" : "Export JSON"}
              </button>
            </>
          }
        />
        <div className="flex flex-wrap gap-1.5">
          {meta.domain && <span className="chip">{meta.domain}</span>}
          {meta.organization && <span className="chip">{meta.organization}</span>}
          <span className="chip">{meta.filename || "document"}</span>
          <span className="chip">
            <ListChecks className="h-3 w-3" />
            {data.processing.pages > 0
              ? `${data.processing.pages} page(s)`
              : "no fixed pagination"}{" "}
            · {data.processing.evidence_items} evidence items
          </span>
          {documents.length > 1 && (
            <span className="chip">
              <FileText className="h-3 w-3" />
              {documents.length} documents
            </span>
          )}
          {data.parent_assessment_id && (
            <span className="chip border-blue-200 bg-blue-50 text-blue-700">
              Reassessment
            </span>
          )}
          {isLegacy && (
            <span className="chip border-amber-200 bg-amber-50 text-amber-700">
              Pre-2.0 assessment
            </span>
          )}
        </div>
        {data.reassessment_reason && (
          <p className="mt-2 text-xs text-muted">
            Reassessment reason: {data.reassessment_reason}
          </p>
        )}
      </div>

      {/* Prediction hero */}
      <section className="relative overflow-hidden rounded-[1.5rem] border border-white/10 bg-gradient-to-br from-[#061326] via-[#081d38] to-[#0b2444] p-5 text-white shadow-[0_30px_70px_-40px_rgba(6,19,38,0.9)] sm:p-7">
        <div className="pointer-events-none absolute inset-0">
          <div className="absolute inset-0 bg-grid opacity-[0.12]" />
          <div className="absolute -left-24 -top-28 h-72 w-72 rounded-full bg-teal-400/20 blur-3xl" />
          <div className="absolute -bottom-32 right-0 h-72 w-72 rounded-full bg-blue-500/20 blur-3xl" />
        </div>

        <div className="relative flex flex-col gap-7 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex min-w-0 items-start gap-4 sm:gap-5">
            <div className="shrink-0 rounded-2xl border border-teal-300/25 bg-gradient-to-b from-teal-300/15 to-cyan-300/[0.04] px-4 py-3.5 text-center shadow-[inset_0_1px_0_rgba(255,255,255,0.12)]">
              <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-teal-200/80">
                Predicted
              </p>
              <p className="stat-value mt-1 text-5xl font-bold leading-none text-white">
                {p.predicted_trl}
              </p>
              <p className="mt-1 text-[10px] font-bold uppercase tracking-[0.16em] text-teal-200/80">
                TRL
              </p>
            </div>
            <div className="min-w-0">
              <h2 className="font-display text-xl font-semibold leading-tight text-white sm:text-2xl">
                {p.level_name}
              </h2>
              {p.level_category && (
                <p className="mt-0.5 text-xs font-semibold uppercase tracking-[0.12em] text-teal-200/70">
                  {p.level_category}
                </p>
              )}
              <p className="mt-2 max-w-xl text-sm leading-relaxed text-slate-300/90">
                {p.level_description}
              </p>
              <div className="mt-3 flex flex-wrap gap-1.5">
                <DarkChip
                  label={p.model_mode === "hybrid" ? "Hybrid model" : "Rule-only"}
                />
                {p.rule_level !== null && (
                  <DarkChip label={`Rule level ${p.rule_level}`} dot="bg-slate-400" />
                )}
                {p.ml_level !== null && (
                  <DarkChip label={`ML level ${p.ml_level}`} dot="bg-cyan-300" />
                )}
                {contradictions && contradictions.total > 0 && (
                  <DarkChip
                    label={`${contradictions.total} contradiction(s)`}
                    dot="bg-rose-400"
                  />
                )}
              </div>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-6 lg:justify-end">
            <div className="rounded-full border border-white/10 bg-white/[0.04] p-3">
              <ConfidenceRing value={p.confidence} size={124} onDark />
            </div>
            <div className="min-w-44 flex-1 space-y-3 lg:max-w-60">
              <div>
                <div className="mb-1.5 flex items-center justify-between text-[11px] text-slate-300">
                  <span className="font-medium">Evidence coverage</span>
                  <span className="font-bold text-white">
                    {formatPercent(p.evidence_coverage, 0)}
                  </span>
                </div>
                <div className="h-1.5 overflow-hidden rounded-full bg-white/10">
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-teal-400 to-cyan-300 shadow-[0_0_12px_rgba(45,212,191,0.7)]"
                    style={{
                      width: `${Math.max(
                        0,
                        Math.min(100, (p.evidence_coverage ?? 0) * 100),
                      )}%`,
                    }}
                  />
                </div>
              </div>
              {uncertainty && (
                <p className="text-[11px] text-slate-400">
                  Overall reliability {formatPercent(uncertainty.overall, 0)} ·{" "}
                  {uncertainty.calibrated ? "calibrated" : "not calibrated"}
                </p>
              )}
              {data.model.available && data.model.name && (
                <p className="text-[11px] text-slate-400">
                  Model: {data.model.name}{" "}
                  {data.model.version && `v${data.model.version}`}
                </p>
              )}
              {p.method && (
                <p className="text-[11px] leading-relaxed text-slate-400">
                  {p.method}
                </p>
              )}
            </div>
          </div>
        </div>
      </section>

      {/* Low-confidence banner + warnings */}
      {p.low_confidence && (
        <div className="mt-3">
          <WarningBanner
            title="Low-confidence result"
            message={`Confidence is ${formatPercent(p.confidence, 0)} (below the 45% threshold). Treat this TRL as indicative and review the evidence table before acting on it.`}
          />
        </div>
      )}
      {p.warnings.length > 0 && (
        <div className="mt-3 space-y-2">
          {p.warnings.map((w) => (
            <WarningBanner key={w} message={w} />
          ))}
        </div>
      )}

      {/* Tabs */}
      <div className="card mt-4 overflow-hidden">
        <div
          role="tablist"
          aria-label="Assessment sections"
          className="scrollbar-thin flex gap-1 overflow-x-auto border-b border-line px-2 py-2"
        >
          {TABS.map((tab, index) => {
            const Icon = tab.icon;
            const active = activeTab === tab.key;
            const count = tabCount(tab.key);
            return (
              <button
                key={tab.key}
                id={`tab-${tab.key}`}
                role="tab"
                type="button"
                aria-selected={active}
                aria-controls={`panel-${tab.key}`}
                tabIndex={active ? 0 : -1}
                onClick={() => setTab(tab.key)}
                onKeyDown={(e) => onTabKeyDown(e, index)}
                className={`inline-flex shrink-0 items-center gap-2 rounded-lg px-3 py-2 text-xs font-semibold transition-colors ${
                  active
                    ? "bg-teal-50 text-primary-dark shadow-[inset_0_0_0_1px_rgba(13,148,136,0.18)]"
                    : "text-muted hover:bg-panel hover:text-ink"
                }`}
              >
                <Icon className="h-3.5 w-3.5" />
                {tab.label}
                {count !== null && (
                  <span
                    className={`rounded-full px-1.5 py-0.5 text-[10px] tabular-nums ${
                      active ? "bg-white/70 text-primary-dark" : "bg-panel text-faint"
                    }`}
                  >
                    {count}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        <div
          id={`panel-${activeTab}`}
          role="tabpanel"
          aria-labelledby={`tab-${activeTab}`}
          tabIndex={0}
          className="space-y-4 p-5 focus:outline-none"
        >
          {/* ---------------------------- OVERVIEW ---------------------------- */}
          {activeTab === "overview" && (
            <>
              <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1.25fr_1fr]">
                <div className="rounded-xl border border-line bg-white p-4">
                  <ConfidenceIndicator
                    uncertainty={uncertainty}
                    prediction={p}
                  />
                </div>
                <div className="space-y-4">
                  <div className="rounded-xl border border-line bg-white p-4">
                    <EvidenceCoverageIndicator
                      coverage={p.evidence_coverage}
                      covered={milestoneCounts.confirmed}
                      total={data.milestones.length}
                      label="Confirmed milestone coverage"
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    {[
                      {
                        label: "Confirmed",
                        value: milestoneCounts.confirmed,
                        tone: "text-emerald-700",
                      },
                      {
                        label: "Not found",
                        value: milestoneCounts.not_found,
                        tone: "text-slate-600",
                      },
                      {
                        label: "Unclear",
                        value: milestoneCounts.unclear,
                        tone: "text-amber-700",
                      },
                      {
                        label: "Contradicted",
                        value: milestoneCounts.contradicted,
                        tone: "text-rose-700",
                      },
                    ].map((item) => (
                      <div key={item.label} className="panel px-3 py-2.5">
                        <p className="text-[10px] font-semibold uppercase tracking-wide text-faint">
                          {item.label}
                        </p>
                        <p className={`mt-0.5 text-xl font-bold ${item.tone}`}>
                          {item.value}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {contradictions && contradictions.total > 0 && (
                <ContradictionAlert
                  report={contradictions}
                  onInspect={() => setTab("contradictions")}
                />
              )}

              <SectionCard
                title="TRL progression"
                subtitle="Click a level to see its definition from the reference framework"
                icon={BadgeCheck}
                actions={
                  selectedLevel !== null ? (
                    <button
                      type="button"
                      onClick={() => setSelectedLevel(null)}
                      className="text-xs font-semibold text-primary hover:text-primary-dark"
                    >
                      Clear selection
                    </button>
                  ) : undefined
                }
              >
                <TRLProgressionScale
                  predicted={p.predicted_trl}
                  milestones={data.milestones}
                  selected={selectedLevel}
                  onSelect={setSelectedLevel}
                  levelNames={levelNames}
                />
                <div className="mt-4 rounded-xl border border-line bg-panel px-4 py-3.5">
                  {reference.loading ? (
                    <Skeleton className="h-12 w-full" />
                  ) : selectedLevelInfo ? (
                    <div>
                      <p className="text-sm font-semibold text-ink">
                        TRL {selectedLevelInfo.level} — {selectedLevelInfo.name}
                        <span className="ml-2 text-xs font-medium text-faint">
                          {selectedLevelInfo.category}
                        </span>
                      </p>
                      <p className="mt-1 text-sm leading-relaxed text-muted">
                        {selectedLevelInfo.description}
                      </p>
                    </div>
                  ) : (
                    <p className="text-sm leading-relaxed text-muted">
                      <span className="font-semibold text-ink">
                        TRL {p.predicted_trl} — {p.level_name}
                      </span>
                      {p.level_description ? ` · ${p.level_description}` : ""}
                    </p>
                  )}
                </div>
              </SectionCard>

              {p.alternatives.length > 0 && (
                <div className="card flex flex-wrap items-center gap-2 p-4">
                  <span className="eyebrow mr-1">Also plausible</span>
                  {p.alternatives.map((alt) => (
                    <span
                      key={alt.level}
                      title={alt.reason}
                      className="inline-flex cursor-help items-center gap-1.5 rounded-full border border-line bg-panel px-3 py-1 text-xs font-medium text-muted"
                    >
                      TRL {alt.level}
                      <span className="font-bold text-ink">
                        {formatPercent(alt.probability, 0)}
                      </span>
                    </span>
                  ))}
                </div>
              )}

              <SectionCard
                title="Technical milestones"
                subtitle="The 9 milestone chains that define readiness on this scale"
                icon={BadgeCheck}
                actions={
                  <button
                    type="button"
                    onClick={() => setTab("roadmap")}
                    className="text-xs font-semibold text-primary hover:text-primary-dark"
                  >
                    Open roadmap →
                  </button>
                }
              >
                {data.milestones.length === 0 ? (
                  <EmptyState
                    title="No milestone data"
                    description="This assessment did not return any milestone statuses."
                  />
                ) : (
                  <ul>
                    {data.milestones.map((m) => (
                      <MilestoneRow key={m.id} m={m} />
                    ))}
                  </ul>
                )}
              </SectionCard>

              {gap && (
                <SectionCard
                  title="Gap snapshot"
                  subtitle={gap.summary || undefined}
                  icon={Target}
                >
                  <div className="flex flex-wrap items-center gap-3 rounded-xl border border-line bg-panel px-4 py-3">
                    <span className="rounded-lg bg-gradient-to-br from-teal-500 to-teal-700 px-3 py-1.5 text-sm font-bold text-white shadow-sm">
                      TRL {gap.current_trl}
                    </span>
                    <span className="text-sm font-medium text-ink-soft">
                      {gap.current_name}
                    </span>
                    {gap.next_trl !== null && (
                      <>
                        <ChevronRight className="h-4 w-4 text-slate-300" />
                        <span className="rounded-lg border border-line-strong bg-white px-3 py-1.5 text-sm font-bold text-muted">
                          TRL {gap.next_trl}
                        </span>
                        <span className="text-sm text-muted">{gap.next_name}</span>
                      </>
                    )}
                  </div>
                  <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
                    {[
                      ["Completed", gap.completed_milestones.length],
                      ["Missing", gap.missing_milestones.length],
                      ["Unclear", gap.unclear_milestones.length],
                      ["Contradicted", gap.contradicted_milestones.length],
                    ].map(([label, value]) => (
                      <div key={label as string} className="panel px-3 py-2.5">
                        <p className="text-[10px] font-semibold uppercase tracking-wide text-faint">
                          {label}
                        </p>
                        <p className="mt-0.5 text-lg font-bold text-ink">
                          {value}
                        </p>
                      </div>
                    ))}
                  </div>
                  <button
                    type="button"
                    onClick={() => setTab("roadmap")}
                    className="btn btn-secondary mt-3"
                  >
                    <MapIcon className="h-4 w-4" />
                    View full roadmap and recommendations
                  </button>
                </SectionCard>
              )}
            </>
          )}

          {/* ---------------------------- EVIDENCE ---------------------------- */}
          {activeTab === "evidence" && (
            <>
              <EvidenceTable
                evidence={data.evidence}
                summary={data.evidence_summary}
              />

              <SectionCard
                title="Evidence coverage by category"
                subtitle="Counts of extracted evidence per category"
                icon={ListChecks}
              >
                {data.evidence_summary.by_category.length === 0 ? (
                  <p className="text-sm text-faint">No category data available.</p>
                ) : (
                  <ul className="space-y-3.5">
                    {data.evidence_summary.by_category.map(
                      (c: EvidenceCategoryCount) => (
                        <li key={c.category}>
                          <div className="mb-1.5 flex items-center justify-between text-xs">
                            <span className="font-semibold text-ink-soft">
                              {c.label}
                            </span>
                            <span className="tabular-nums text-faint">
                              {c.count} total · {c.confirmed} confirmed
                            </span>
                          </div>
                          <div className="flex h-2.5 w-full overflow-hidden rounded-full bg-slate-100">
                            {c.count > 0 && (
                              <>
                                <div
                                  className="h-full bg-emerald-500"
                                  style={{
                                    width: `${(c.confirmed / categoryMax) * 100}%`,
                                  }}
                                  title={`${c.confirmed} confirmed`}
                                />
                                <div
                                  className="h-full bg-blue-500"
                                  style={{
                                    width: `${(c.proposed / categoryMax) * 100}%`,
                                  }}
                                  title={`${c.proposed} proposed`}
                                />
                                <div
                                  className="h-full bg-amber-400"
                                  style={{
                                    width: `${(c.unclear / categoryMax) * 100}%`,
                                  }}
                                  title={`${c.unclear} unclear`}
                                />
                                <div
                                  className="h-full bg-rose-500"
                                  style={{
                                    width: `${(c.contradicted / categoryMax) * 100}%`,
                                  }}
                                  title={`${c.contradicted} contradicted`}
                                />
                              </>
                            )}
                          </div>
                        </li>
                      ),
                    )}
                  </ul>
                )}
                <div className="mt-4 flex flex-wrap gap-3 text-[11px] text-muted">
                  <LegendDot className="bg-emerald-500" label="Confirmed" />
                  <LegendDot className="bg-blue-500" label="Proposed" />
                  <LegendDot className="bg-amber-400" label="Unclear" />
                  <LegendDot className="bg-rose-500" label="Contradicted" />
                </div>
              </SectionCard>

              {verification && (
                <SectionCard
                  title="Evidence verification"
                  subtitle="Cross-checks of the predicted level against raw excerpts"
                  icon={SearchCheck}
                >
                  {verification.unsupported_high_level_claim && (
                    <div className="mb-4 flex items-start gap-3 rounded-2xl border border-rose-200/80 bg-rose-50 px-4 py-3.5">
                      <AlertOctagon className="mt-0.5 h-5 w-5 shrink-0 text-rose-600" />
                      <div>
                        <p className="text-sm font-semibold text-rose-900">
                          Unsupported high-level claim detected
                        </p>
                        <p className="mt-0.5 text-sm leading-relaxed text-rose-800/90">
                          The document claims activities at TRL{" "}
                          {verification.predicted_trl}+ without confirmed supporting
                          evidence. The claim was not counted as completed readiness.
                        </p>
                      </div>
                    </div>
                  )}

                  {verification.summary && (
                    <p className="mb-4 text-sm leading-relaxed text-ink-soft">
                      {verification.summary}
                    </p>
                  )}

                  {verification.concerns.length > 0 && (
                    <ul className="mb-4 space-y-2">
                      {verification.concerns.map((c) => (
                        <li
                          key={c}
                          className="flex items-start gap-2.5 rounded-xl border border-amber-200/80 bg-amber-50 px-3 py-2.5 text-sm text-amber-900"
                        >
                          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
                          {c}
                        </li>
                      ))}
                    </ul>
                  )}

                  <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                    <div>
                      <p className="eyebrow mb-2">
                        Contradictions ({verification.contradictions.length})
                      </p>
                      {verification.contradictions.length === 0 ? (
                        <p className="text-sm text-faint">
                          No contradictory excerpts found.
                        </p>
                      ) : (
                        <div>
                          {verification.contradictions.map((e) => (
                            <EvidenceExcerpt key={e.id} e={e} />
                          ))}
                        </div>
                      )}
                    </div>
                    <div className="space-y-2">
                      <Collapsible
                        title="Proposed / future work not counted as completed"
                        count={verification.proposed_mistaken_for_done.length}
                      >
                        {verification.proposed_mistaken_for_done.length === 0 ? (
                          <p className="text-sm text-faint">
                            None — no proposed work was mistaken for completed evidence.
                          </p>
                        ) : (
                          verification.proposed_mistaken_for_done.map((e) => (
                            <EvidenceExcerpt key={e.id} e={e} />
                          ))
                        )}
                      </Collapsible>
                      <Collapsible
                        title="Evidence backing the predicted level"
                        count={verification.evidence_backing.length}
                      >
                        {verification.evidence_backing.length === 0 ? (
                          <p className="text-sm text-faint">
                            No confirmed excerpts back this level yet.
                          </p>
                        ) : (
                          verification.evidence_backing.map((e) => (
                            <EvidenceExcerpt key={e.id} e={e} />
                          ))
                        )}
                      </Collapsible>
                    </div>
                  </div>
                </SectionCard>
              )}
            </>
          )}

          {/* -------------------------- KNOWLEDGE GRAPH ------------------------ */}
          {activeTab === "graph" && (
            <SectionCard
              title="Evidence knowledge graph"
              subtitle="Technology, documents, milestones, categories, evidence and contradictions with their real relationships"
              icon={Network}
            >
              {graph ? (
                <EvidenceKnowledgeGraph
                  graph={graph}
                  height={560}
                  onOpenEvidence={() => setTab("evidence")}
                />
              ) : (
                <UnavailableBlock
                  icon={Network}
                  title="Knowledge graph unavailable"
                  description="This assessment predates the 2.0 pipeline, so no graph was stored. Re-run the analysis to build the evidence graph."
                />
              )}
            </SectionCard>
          )}

          {/* --------------------------- EXPLAINABILITY ------------------------ */}
          {activeTab === "explainability" && (
            <>
              <SectionCard
                title="Model feature attribution"
                subtitle="Explains the classifier's decision — not the document's contents"
                icon={Sparkles}
              >
                <SHAPExplanationChart explanation={explanation} />
                <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <div className="rounded-xl border border-blue-200/70 bg-blue-50/50 p-3.5">
                    <p className="text-xs font-semibold text-blue-900">
                      Model explanation
                    </p>
                    <p className="mt-1 text-xs leading-relaxed text-blue-900/75">
                      Feature contributions describe how the classifier weighted the
                      extracted signals. They are not source evidence and cannot
                      confirm a milestone on their own.
                    </p>
                  </div>
                  <div className="rounded-xl border border-emerald-200/70 bg-emerald-50/50 p-3.5">
                    <p className="text-xs font-semibold text-emerald-900">
                      Source-backed evidence
                    </p>
                    <p className="mt-1 text-xs leading-relaxed text-emerald-900/75">
                      Milestone confirmation comes only from verbatim excerpts with
                      locators. Open the Evidence tab to inspect them.
                    </p>
                    <button
                      type="button"
                      onClick={() => setTab("evidence")}
                      className="mt-2 text-xs font-semibold text-primary hover:underline"
                    >
                      Inspect evidence →
                    </button>
                  </div>
                </div>
              </SectionCard>

              <SectionCard
                title="Level alternatives"
                subtitle="Probability mass across all 9 TRL classes"
                icon={Info}
              >
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={probabilityData}
                      layout="vertical"
                      margin={{ top: 4, right: 16, left: 8, bottom: 4 }}
                    >
                      <XAxis
                        type="number"
                        tickFormatter={(v: number) => `${Math.round(v * 100)}%`}
                        tick={{ fontSize: 11, fill: "#8a97a8" }}
                        domain={[0, 1]}
                        axisLine={false}
                        tickLine={false}
                      />
                      <YAxis
                        type="category"
                        dataKey="name"
                        tick={{ fontSize: 11, fill: "#8a97a8" }}
                        width={52}
                        axisLine={false}
                        tickLine={false}
                      />
                      <Tooltip
                        cursor={{ fill: "rgba(13,148,136,0.06)" }}
                        contentStyle={chartTooltipStyle}
                        formatter={(value) => [
                          `${(Number(value) * 100).toFixed(1)}%`,
                          "Probability",
                        ]}
                      />
                      <Bar
                        dataKey="probability"
                        maxBarSize={18}
                        radius={[0, 6, 6, 0]}
                      >
                        {probabilityData.map((_entry, index) => (
                          <Cell
                            key={index}
                            fill={
                              index + 1 === p.predicted_trl
                                ? "#0D9488"
                                : index + 1 < p.predicted_trl
                                  ? "#99F6E4"
                                  : "#E2E8F0"
                            }
                          />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
                <p className="mt-2 text-xs text-faint">
                  {p.model_mode === "hybrid"
                    ? "Hybrid rule + model output. Probabilities are model scores, not calibrated real-world frequencies."
                    : "Rule-only mode: the distribution reflects rule support, not a trained classifier."}
                </p>
              </SectionCard>
            </>
          )}

          {/* --------------------------- CONTRADICTIONS ------------------------ */}
          {activeTab === "contradictions" && (
            <SectionCard
              title="Contradiction analysis"
              subtitle="Conflicting statements, outdated evidence and cross-document conflicts"
              icon={AlertOctagon}
            >
              <ContradictionAlert
                report={contradictions}
                onInspect={() => setTab("evidence")}
              />
            </SectionCard>
          )}

          {/* ------------------------------ ROADMAP ---------------------------- */}
          {activeTab === "roadmap" && (
            <>
              <SectionCard
                title="Technology roadmap"
                subtitle="Milestone-linked actions derived from real gaps"
                icon={MapIcon}
              >
                <TechnologyRoadmap roadmap={roadmap} />
              </SectionCard>

              <SectionCard
                title="Missing evidence questionnaire"
                subtitle="Targeted questions for milestones that are missing or unclear"
                icon={ClipboardCheck}
              >
                {questionnaire ? (
                  <MissingEvidencePanel
                    assessmentId={data.id}
                    questionnaire={questionnaire}
                    missing={[
                      ...(gap?.missing_milestones ?? []),
                      ...(gap?.unclear_milestones ?? []),
                    ]}
                    onCreated={(newId) => navigate(`/assessments/${newId}`)}
                  />
                ) : (
                  <UnavailableBlock
                    icon={ClipboardCheck}
                    title="Questionnaire unavailable"
                    description="This assessment predates the 2.0 pipeline, so no missing-evidence questions were stored. Re-run the analysis to generate them."
                  />
                )}
              </SectionCard>

              {gap && (
                <SectionCard
                  title="Gap analysis"
                  subtitle={gap.summary || undefined}
                  icon={Target}
                >
                  <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                    {[
                      {
                        title: "Completed",
                        items: gap.completed_milestones,
                        tone: "border-emerald-200/80 bg-emerald-50 text-emerald-700",
                      },
                      {
                        title: "Missing",
                        items: gap.missing_milestones,
                        tone: "border-line bg-panel text-muted",
                      },
                      {
                        title: "Unclear",
                        items: gap.unclear_milestones,
                        tone: "border-amber-200/80 bg-amber-50 text-amber-700",
                      },
                    ].map((col) => (
                      <div
                        key={col.title}
                        className="rounded-xl border border-line bg-white p-3.5"
                      >
                        <p
                          className={`mb-2 inline-flex rounded-full border px-2.5 py-0.5 text-xs font-semibold ${col.tone}`}
                        >
                          {col.title} · {col.items.length}
                        </p>
                        {col.items.length === 0 ? (
                          <p className="py-2 text-xs text-faint">None.</p>
                        ) : (
                          <ul className="space-y-1.5">
                            {col.items.map((m) => (
                              <li
                                key={m.id}
                                className="rounded-lg border border-line/70 bg-panel/60 px-2.5 py-2 text-xs"
                              >
                                <span className="font-semibold text-ink-soft">
                                  TRL {m.trl} · {m.label}
                                </span>
                                <span className="mt-0.5 block text-faint">
                                  {m.evidence_count} evidence
                                </span>
                              </li>
                            ))}
                          </ul>
                        )}
                      </div>
                    ))}
                  </div>

                  {gap.contradicted_milestones.length > 0 && (
                    <div className="mt-4 rounded-xl border border-rose-200/80 bg-rose-50 p-3.5">
                      <p className="mb-2 text-xs font-semibold text-rose-800">
                        Contradicted milestones · {gap.contradicted_milestones.length}
                      </p>
                      <ul className="space-y-1.5">
                        {gap.contradicted_milestones.map((m) => (
                          <li key={m.id} className="text-xs text-rose-800">
                            TRL {m.trl} · {m.label}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  <div className="mt-5">
                    <h3 className="eyebrow mb-3">
                      Recommendations ({gap.recommendations.length})
                    </h3>
                    {gap.recommendations.length === 0 ? (
                      <p className="text-sm text-faint">
                        No targeted recommendations — the current milestone chain is
                        complete up to the predicted level.
                      </p>
                    ) : (
                      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                        {gap.recommendations.map((rec) => (
                          <div
                            key={rec.id}
                            className="rounded-xl border border-line bg-white p-4 shadow-[0_1px_2px_rgba(10,22,40,0.04)]"
                          >
                            <div className="flex items-start justify-between gap-2">
                              <h4 className="text-sm font-semibold text-ink">
                                {rec.title}
                              </h4>
                              <StatusBadge kind="priority" value={rec.priority} />
                            </div>

                            {rec.address_labels.length > 0 && (
                              <div className="mt-3">
                                <p className="eyebrow mb-1.5">Addresses</p>
                                <div className="flex flex-wrap gap-1.5">
                                  {rec.address_labels.map((label, i) => (
                                    <span
                                      key={`${label}-${i}`}
                                      className="inline-flex items-center gap-1.5 rounded-full border border-line bg-panel px-2.5 py-1 text-xs text-muted"
                                    >
                                      <span className="font-medium">{label}</span>
                                      <StatusBadge
                                        kind="milestone"
                                        value={rec.address_statuses[i] ?? "unclear"}
                                      />
                                    </span>
                                  ))}
                                </div>
                              </div>
                            )}

                            <div className="mt-3 space-y-3 text-sm">
                              {rec.actions.length > 0 && (
                                <div>
                                  <p className="eyebrow mb-1">Actions</p>
                                  <ul className="space-y-1">
                                    {rec.actions.map((a, i) => (
                                      <li
                                        key={i}
                                        className="flex gap-2 leading-relaxed text-muted"
                                      >
                                        <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-primary" />
                                        {a}
                                      </li>
                                    ))}
                                  </ul>
                                </div>
                              )}
                              {rec.validation_experiments.length > 0 && (
                                <div>
                                  <p className="eyebrow mb-1">
                                    Validation experiments
                                  </p>
                                  <ul className="space-y-1">
                                    {rec.validation_experiments.map((a, i) => (
                                      <li
                                        key={i}
                                        className="flex gap-2 leading-relaxed text-muted"
                                      >
                                        <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-secondary" />
                                        {a}
                                      </li>
                                    ))}
                                  </ul>
                                </div>
                              )}
                              {rec.documentation.length > 0 && (
                                <div>
                                  <p className="eyebrow mb-1">Documentation</p>
                                  <ul className="space-y-1">
                                    {rec.documentation.map((a, i) => (
                                      <li
                                        key={i}
                                        className="flex gap-2 leading-relaxed text-muted"
                                      >
                                        <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-slate-400" />
                                        {a}
                                      </li>
                                    ))}
                                  </ul>
                                </div>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {gap.documentation_requirements.length > 0 && (
                    <div className="mt-5 rounded-xl border border-line bg-panel p-4">
                      <p className="eyebrow mb-2">Documentation requirements</p>
                      <ul className="grid grid-cols-1 gap-1.5 md:grid-cols-2">
                        {gap.documentation_requirements.map((d, i) => (
                          <li
                            key={i}
                            className="flex gap-2 text-sm leading-relaxed text-muted"
                          >
                            <FileText className="mt-0.5 h-3.5 w-3.5 shrink-0 text-faint" />
                            {d}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </SectionCard>
              )}
            </>
          )}

          {/* ----------------------------- DOCUMENTS --------------------------- */}
          {activeTab === "documents" && (
            <>
              <SectionCard
                title="Document provenance"
                subtitle="What each attached document contributed to this assessment"
                icon={FileText}
              >
                <DocumentComparisonViewer documents={documents} />
              </SectionCard>

              <SectionCard
                title="Processing details"
                subtitle="Actual values reported by the analysis pipeline"
                icon={Info}
              >
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
                  {[
                    ["Extraction", data.processing.extraction_method],
                    ["Pages", String(data.processing.pages)],
                    ["Sentences", String(data.processing.sentences)],
                    ["Evidence", String(data.processing.evidence_items)],
                    ["Documents", String(data.processing.documents)],
                    ["Duplicates", String(data.processing.duplicates)],
                    ["Outdated", String(data.processing.outdated)],
                    [
                      "Duration",
                      `${formatNumber(data.processing.duration_ms / 1000, 2)} s`,
                    ],
                  ].map(([label, value]) => (
                    <div key={label} className="panel px-3 py-2.5">
                      <p className="text-[10px] font-semibold uppercase tracking-wide text-faint">
                        {label}
                      </p>
                      <p className="mt-0.5 truncate text-sm font-semibold text-ink">
                        {value}
                      </p>
                    </div>
                  ))}
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  <span className="chip">
                    OCR {data.processing.ocr_used ? "used" : "not used"}
                  </span>
                  <span className="chip">
                    Retrieval: {data.retrieval?.backend ?? "not stored"}
                  </span>
                  {data.retrieval && (
                    <span className="chip">
                      Embeddings: {data.retrieval.model || "default"}
                    </span>
                  )}
                </div>
              </SectionCard>

              <SectionCard
                title="Assessment timeline"
                subtitle="Stored events for this assessment"
                icon={GitBranch}
              >
                {timeline.loading && !timeline.data ? (
                  <div className="space-y-2">
                    <Skeleton className="h-10 w-full" />
                    <Skeleton className="h-10 w-full" />
                  </div>
                ) : timeline.error && !timeline.data ? (
                  <ErrorBanner
                    message={timeline.error}
                    networkError={timeline.networkError}
                    onRetry={timeline.refetch}
                  />
                ) : (
                  <AssessmentTimeline
                    events={timeline.data?.events ?? []}
                    emptyMessage="No timeline events were stored for this assessment."
                  />
                )}
              </SectionCard>
            </>
          )}

          {/* ------------------------------- REVIEW ---------------------------- */}
          {activeTab === "review" && (
            <SectionCard
              title="Expert review"
              subtitle="Append-only review history; the original AI prediction stays intact"
              icon={UserCheck}
            >
              <div className="mb-4 flex items-start gap-3 rounded-xl border border-line bg-panel/70 px-4 py-3">
                <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                <p className="text-xs leading-relaxed text-muted">
                  The AI prediction (TRL {p.predicted_trl}, confidence{" "}
                  {formatPercent(p.confidence, 0)}) is immutable. Reviews record a
                  separate human decision and never overwrite the stored result.
                </p>
              </div>
              <ExpertReviewPanel
                assessmentId={data.id}
                prediction={p}
                evidence={data.evidence}
                onReviewed={assessment.refetch}
              />
            </SectionCard>
          )}
        </div>
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Reassessment questionnaire                                                  */
/* -------------------------------------------------------------------------- */

interface AnswerDraft {
  status: ExpertAnswerStatus;
  evidenceNote: string;
  sourceReference: string;
}

function MissingEvidencePanel({
  assessmentId,
  questionnaire,
  missing,
  onCreated,
}: {
  assessmentId: string;
  questionnaire: Questionnaire;
  missing: MilestoneStatusModel[];
  onCreated: (id: string) => void;
}) {
  const [drafts, setDrafts] = useState<Record<string, AnswerDraft>>({});
  const [reviewer, setReviewer] = useState("");
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const setDraft = (id: string, patch: Partial<AnswerDraft>) => {
    setDrafts((current) => {
      const base: AnswerDraft = current[id] ?? {
        status: "unknown",
        evidenceNote: "",
        sourceReference: "",
      };
      return { ...current, [id]: { ...base, ...patch } };
    });
  };

  const answered = Object.values(drafts).filter(
    (d) => d.status !== "unknown" && (d.evidenceNote.trim() || d.sourceReference.trim()),
  );

  const submit = async () => {
    setError(null);
    if (!reviewer.trim()) {
      setError("Enter the reviewer name so the reassessment can be attributed.");
      return;
    }
    if (answered.length === 0) {
      setError(
        "Answer at least one question with an evidence note or source reference.",
      );
      return;
    }
    setSubmitting(true);
    try {
      const result = await reassess(assessmentId, {
        reviewer_name: reviewer.trim(),
        reason: reason.trim() || "Missing-evidence questionnaire",
        answers: Object.entries(drafts)
          .filter(([, draft]) => draft.status !== "unknown")
          .map(([milestoneId, draft]) => ({
            milestone_id: milestoneId,
            status: draft.status,
            evidence_note: draft.evidenceNote.trim(),
            source_reference: draft.sourceReference.trim(),
          })),
      });
      onCreated(result.id);
    } catch (err) {
      setError(errorMessage(err));
      setSubmitting(false);
    }
  };

  if (questionnaire.total === 0) {
    return (
      <div className="rounded-xl border border-emerald-200/70 bg-emerald-50/50 px-4 py-4 text-sm text-emerald-900">
        <p className="font-semibold">No missing-evidence questions</p>
        <p className="mt-1 text-xs leading-relaxed">
          Every milestone up to the predicted level already has confirmed evidence.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {missing.length > 0 && (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {missing.slice(0, 4).map((m) => (
            <MissingMilestoneCard
              key={m.id}
              milestone={m}
              onAsk={() => {
                const id = questionnaire.items.find(
                  (item) => item.milestone === m.id,
                )?.id;
                if (id) document.getElementById(`question-${id}`)?.scrollIntoView({
                  behavior: "smooth",
                  block: "center",
                });
              }}
            />
          ))}
        </div>
      )}

      <p className="text-xs leading-relaxed text-faint">{questionnaire.note}</p>

      <ol className="space-y-3">
        {questionnaire.items.map((item, index) => {
          const draft = drafts[item.id] ?? {
            status: "unknown" as ExpertAnswerStatus,
            evidenceNote: "",
            sourceReference: "",
          };
          return (
            <li
              key={item.id}
              id={`question-${item.id}`}
              className="rounded-xl border border-line bg-white p-4"
            >
              <div className="flex items-start gap-3">
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border border-line bg-panel text-[11px] font-bold text-muted">
                  {index + 1}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold text-ink">{item.question}</p>
                  <p className="mt-1 text-xs leading-relaxed text-muted">
                    {item.why_it_matters}
                  </p>
                  <p className="mt-1 text-xs text-faint">
                    Expected document: {item.expected_document} · TRL {item.trl} ·{" "}
                    {item.milestone_label}
                  </p>
                </div>
              </div>

              <div className="mt-3 grid gap-2 sm:grid-cols-3">
                {(
                  [
                    ["completed", "Completed"],
                    ["planned", "Planned"],
                    ["not_applicable", "Not applicable"],
                  ] as [ExpertAnswerStatus, string][]
                ).map(([value, label]) => (
                  <button
                    key={value}
                    type="button"
                    onClick={() => setDraft(item.id, { status: value })}
                    aria-pressed={draft.status === value}
                    className={`rounded-lg border px-3 py-2 text-xs font-semibold transition-colors ${
                      draft.status === value
                        ? "border-primary bg-teal-50 text-primary-dark"
                        : "border-line bg-white text-muted hover:bg-panel"
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>

              {draft.status !== "unknown" && (
                <div className="mt-3 grid gap-3 sm:grid-cols-2">
                  <div>
                    <label
                      htmlFor={`note-${item.id}`}
                      className="label"
                    >
                      Evidence note
                    </label>
                    <textarea
                      id={`note-${item.id}`}
                      rows={2}
                      value={draft.evidenceNote}
                      onChange={(e) =>
                        setDraft(item.id, { evidenceNote: e.target.value })
                      }
                      placeholder="What was actually completed or planned?"
                      className="textarea mt-1"
                    />
                  </div>
                  <div>
                    <label
                      htmlFor={`source-${item.id}`}
                      className="label"
                    >
                      Source reference
                    </label>
                    <input
                      id={`source-${item.id}`}
                      type="text"
                      value={draft.sourceReference}
                      onChange={(e) =>
                        setDraft(item.id, { sourceReference: e.target.value })
                      }
                      placeholder="Document, page or section"
                      className="input mt-1"
                    />
                  </div>
                </div>
              )}
            </li>
          );
        })}
      </ol>

      <div className="rounded-xl border border-line bg-panel/70 p-4">
        <p className="text-sm font-semibold text-ink">
          Create a reassessment
        </p>
        <p className="mt-1 text-xs leading-relaxed text-muted">
          Answers become clearly labelled self-reported evidence. The current AI
          prediction is preserved; a new assessment is stored and linked to this one.
        </p>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <div>
            <label htmlFor="reassess-reviewer" className="label">
              Reviewer name <span className="text-danger">*</span>
            </label>
            <input
              id="reassess-reviewer"
              type="text"
              value={reviewer}
              onChange={(e) => setReviewer(e.target.value)}
              placeholder="Your name"
              className="input mt-1"
            />
          </div>
          <div>
            <label htmlFor="reassess-reason" className="label">
              Reason
            </label>
            <input
              id="reassess-reason"
              type="text"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="e.g. Clarified test results"
              className="input mt-1"
            />
          </div>
        </div>
        {error && (
          <div className="mt-3">
            <ErrorBanner message={error} />
          </div>
        )}
        <button
          type="button"
          onClick={() => void submit()}
          disabled={submitting}
          className="btn btn-primary mt-3"
        >
          {submitting ? (
            <LoaderSpinner />
          ) : (
            <ClipboardCheck className="h-4 w-4" />
          )}
          Create reassessment
        </button>
      </div>
    </div>
  );
}

function LoaderSpinner() {
  return (
    <span
      className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white"
      aria-hidden="true"
    />
  );
}
