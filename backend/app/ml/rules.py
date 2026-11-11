"""Rules engine: milestone assessment + rule-based TRL prior.

This is the second pillar of the hybrid prediction. It never trusts
keyword counts alone: a milestone is only CONFIRMED when at least one
excerpt matches the milestone's defining indicators inside a completed
statement, and a single explicit contradiction demotes the milestone to
``unclear`` (conflicting evidence).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from app.config.framework import Framework
from app.services.evidence import (
    STATUS_CONFIRMED,
    STATUS_CONTRADICTED,
    STATUS_PROPOSED,
    STATUS_UNCLEAR,
    EvidenceRecord,
)


@dataclass
class MilestoneAssessment:
    id: str
    trl: int
    label: str
    status: str
    evidence_count: int = 0
    supporting: int = 0
    contradicting: int = 0
    proposed: int = 0
    unclear: int = 0
    summary: str = ""
    evidence_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "trl": self.trl,
            "label": self.label,
            "status": self.status,
            "evidence_count": self.evidence_count,
            "supporting": self.supporting,
            "contradicting": self.contradicting,
            "proposed": self.proposed,
            "unclear": self.unclear,
            "summary": self.summary,
            "evidence_ids": self.evidence_ids[:8],
        }


@dataclass
class RuleResult:
    milestones: list[MilestoneAssessment]
    supported_level: int | None
    rule_distribution: dict[int, float]
    warnings: list[str] = field(default_factory=list)
    contradictions: list[EvidenceRecord] = field(default_factory=list)
    proposed_items: list[EvidenceRecord] = field(default_factory=list)
    coverage_up_to_supported: float = 0.0

    @property
    def milestone_map(self) -> dict[str, MilestoneAssessment]:
        return {m.id: m for m in self.milestones}

    def status_of(self, milestone_id: str) -> str:
        ms = self.milestone_map.get(milestone_id)
        return ms.status if ms else "not_found"


def _describe(status: str, ms: MilestoneAssessment) -> str:
    pages = _pages(ms)
    where = f" ({pages})" if pages else ""
    if status == STATUS_CONFIRMED:
        return f"Confirmed by {ms.supporting} excerpt(s){where}."
    if status == "not_found":
        return (
            "No supporting evidence found in this document. "
            "(Absence of evidence is not proof that the activity never happened.)"
        )
    if status == STATUS_CONTRADICTED:
        return (
            f"Explicitly contradicted by {ms.contradicting} excerpt(s){where}: "
            "the document states this has not occurred."
        )
    if ms.supporting and ms.contradicting:
        return (
            f"Conflicting evidence ({ms.supporting} supporting, "
            f"{ms.contradicting} contradicting) - treated as unclear."
        )
    if ms.proposed:
        return (
            f"Only planned/future evidence ({ms.proposed} excerpt(s)) - "
            "proposed work does not confirm this milestone."
        )
    return "Evidence found but insufficient or unclear to confirm this milestone."


def _pages(ms: MilestoneAssessment) -> str:
    return ""  # filled by caller with real page numbers when available


def assess_milestones(
    evidence: list[EvidenceRecord], framework: Framework
) -> list[MilestoneAssessment]:
    """Derive the status of every milestone from the extracted evidence."""
    by_milestone: dict[str, list[EvidenceRecord]] = {}
    for item in evidence:
        if item.milestone:
            by_milestone.setdefault(item.milestone, []).append(item)

    assessments: list[MilestoneAssessment] = []
    for ms in framework.milestones:
        items = by_milestone.get(ms["id"], [])
        supporting = [i for i in items if i.status == STATUS_CONFIRMED]
        contradicting = [i for i in items if i.status == STATUS_CONTRADICTED]
        proposed = [i for i in items if i.status == STATUS_PROPOSED]
        unclear = [i for i in items if i.status == STATUS_UNCLEAR]

        if supporting and not contradicting:
            status = STATUS_CONFIRMED
        elif supporting and contradicting:
            status = "unclear"  # conflicting evidence
        elif contradicting:
            status = STATUS_CONTRADICTED
        elif proposed or unclear:
            status = "unclear"
        else:
            status = "not_found"

        assessment = MilestoneAssessment(
            id=ms["id"],
            trl=int(ms["trl"]),
            label=ms["label"],
            status=status,
            evidence_count=len(items),
            supporting=len(supporting),
            contradicting=len(contradicting),
            proposed=len(proposed),
            unclear=len(unclear),
            evidence_ids=[i.id for i in items],
        )
        assessment.summary = _describe(status, assessment)
        assessments.append(assessment)
    return assessments


def _rule_distribution(
    supported: int | None,
    framework: Framework,
    coverage: float,
    has_contradictions: bool,
) -> dict[int, float]:
    rules = framework.rules
    tau_confirmed = float(rules.get("rule_prior_tau_confirmed", 1.0))
    tau_uncertain = float(rules.get("rule_prior_tau_uncertain", 1.7))
    good = float(rules.get("evidence_coverage_good", 0.5))

    tau = tau_confirmed if coverage >= good else tau_uncertain
    if has_contradictions:
        tau = max(tau, tau_uncertain)

    raw: dict[int, float] = {}
    if supported and supported >= 1:
        for level in range(1, 10):
            raw[level] = math.exp(-abs(level - supported) / tau)
    else:
        # Nothing confirmed: skeptical prior that favours low readiness.
        for level in range(1, 10):
            raw[level] = 0.72 ** (level - 1)

    total = sum(raw.values()) or 1.0
    return {level: round(value / total, 6) for level, value in raw.items()}


def assess_rules(
    evidence: list[EvidenceRecord],
    framework: Framework,
    predicted_trl: int | None = None,
) -> RuleResult:
    """Full rule-based assessment: milestones, supported level, prior."""
    milestones = assess_milestones(evidence, framework)

    supported: int | None = None
    for assessment in reversed(milestones):
        if assessment.status == STATUS_CONFIRMED:
            supported = assessment.trl
            break

    confirmed_count = sum(1 for m in milestones if m.status == STATUS_CONFIRMED)
    denom = supported or 0
    coverage = (confirmed_count / denom) if denom else 0.0
    contradictions = [i for i in evidence if i.status == STATUS_CONTRADICTED]
    proposed_items = [i for i in evidence if i.status == STATUS_PROPOSED]

    warnings: list[str] = []
    for assessment in milestones:
        if assessment.status == STATUS_CONTRADICTED:
            warnings.append(
                f"The document explicitly states that '{assessment.label}' "
                "has not been achieved."
            )
        elif assessment.status == "unclear" and assessment.supporting and assessment.contradicting:
            warnings.append(
                f"Conflicting evidence found for '{assessment.label}' "
                f"({assessment.supporting} supporting vs "
                f"{assessment.contradicting} contradicting excerpts)."
            )
    if proposed_items and (supported is None or len(proposed_items) >= 3):
        warnings.append(
            f"{len(proposed_items)} planned/future-tense statement(s) were detected "
            "and were NOT counted as completed evidence."
        )

    distribution = _rule_distribution(supported, framework, coverage, bool(contradictions))

    return RuleResult(
        milestones=milestones,
        supported_level=supported,
        rule_distribution=distribution,
        warnings=warnings,
        contradictions=contradictions,
        proposed_items=proposed_items,
        coverage_up_to_supported=round(coverage, 3),
    )


def milestone_summary_for_display(
    result: RuleResult, evidence: list[EvidenceRecord]
) -> list[dict[str, Any]]:
    """Milestone dictionaries enriched with real page references."""
    pages_by_id: dict[str, list[int]] = {}
    for item in evidence:
        if item.milestone and item.page_number:
            pages_by_id.setdefault(item.milestone, []).append(item.page_number)

    out: list[dict[str, Any]] = []
    for assessment in result.milestones:
        data = assessment.to_dict()
        pages = sorted(set(pages_by_id.get(assessment.id, [])))
        if pages:
            data["summary"] = data["summary"].rstrip(".") + f" [pages {', '.join(map(str, pages))}]."
        out.append(data)
    return out
