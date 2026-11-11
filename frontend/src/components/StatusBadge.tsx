import type { EvidenceStatus, MilestoneStatusValue, Stance } from "../types";

type Tone = "green" | "red" | "gray" | "amber" | "blue" | "teal";

const tones: Record<Tone, string> = {
  green: "border-emerald-200/80 bg-emerald-50 text-emerald-700",
  red: "border-rose-200/80 bg-rose-50 text-rose-700",
  gray: "border-slate-200 bg-slate-50 text-slate-600",
  amber: "border-amber-200/80 bg-amber-50 text-amber-700",
  blue: "border-blue-200/80 bg-blue-50 text-blue-700",
  teal: "border-teal-200/80 bg-teal-50 text-teal-700",
};

const dots: Record<Tone, string> = {
  green: "bg-emerald-500",
  red: "bg-rose-500",
  gray: "bg-slate-400",
  amber: "bg-amber-500",
  blue: "bg-blue-500",
  teal: "bg-teal-500",
};

const evidenceTone: Record<EvidenceStatus, Tone> = {
  confirmed: "green",
  proposed: "blue",
  contradicted: "red",
  unclear: "amber",
};

const evidenceLabel: Record<EvidenceStatus, string> = {
  confirmed: "Confirmed",
  proposed: "Proposed",
  contradicted: "Contradicted",
  unclear: "Unclear",
};

const stanceTone: Record<Stance, Tone> = {
  supporting: "green",
  contradicting: "red",
  insufficient: "gray",
};

const stanceLabel: Record<Stance, string> = {
  supporting: "Supporting",
  contradicting: "Contradicting",
  insufficient: "Insufficient",
};

const milestoneTone: Record<MilestoneStatusValue, Tone> = {
  confirmed: "green",
  not_found: "gray",
  contradicted: "red",
  unclear: "amber",
};

const milestoneLabel: Record<MilestoneStatusValue, string> = {
  confirmed: "Confirmed",
  not_found: "Not found",
  contradicted: "Contradicted",
  unclear: "Unclear",
};

const priorityTone: Record<string, Tone> = {
  high: "red",
  medium: "amber",
  low: "gray",
};

interface StatusBadgeProps {
  kind: "evidence" | "stance" | "milestone" | "priority" | "mode" | "custom";
  value: string;
  tone?: Tone;
  label?: string;
}

/** Pill badge for evidence statuses, stances, milestones, priority, model mode. */
export default function StatusBadge({ kind, value, tone, label }: StatusBadgeProps) {
  let resolved: Tone = tone ?? "gray";
  let text = label ?? value;

  if (kind === "evidence") {
    const v = value as EvidenceStatus;
    resolved = tone ?? evidenceTone[v] ?? "gray";
    text = label ?? evidenceLabel[v] ?? value;
  } else if (kind === "stance") {
    const v = value as Stance;
    resolved = tone ?? stanceTone[v] ?? "gray";
    text = label ?? stanceLabel[v] ?? value;
  } else if (kind === "milestone") {
    const v = value as MilestoneStatusValue;
    resolved = tone ?? milestoneTone[v] ?? "gray";
    text = label ?? milestoneLabel[v] ?? value.replace(/_/g, " ");
  } else if (kind === "priority") {
    resolved = tone ?? priorityTone[value] ?? "gray";
    text = label ?? `${value.charAt(0).toUpperCase()}${value.slice(1)} priority`;
  } else if (kind === "mode") {
    resolved = tone ?? (value === "hybrid" ? "teal" : "blue");
    text = label ?? (value === "hybrid" ? "Hybrid model" : "Rule-only");
  }

  return (
    <span
      className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border px-2.5 py-0.5 text-[11px] font-semibold ${tones[resolved]}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${dots[resolved]}`} />
      {text}
    </span>
  );
}
