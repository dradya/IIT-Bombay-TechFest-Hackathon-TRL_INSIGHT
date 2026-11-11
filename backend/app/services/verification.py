"""STEP 6 - Evidence verification.

Checks whether the predicted level actually has supporting evidence and
reports contradictions, missing documentation, proposed-versus-completed
confusion and unsupported high-level claims. Nothing here invents
support: if the evidence is absent, the concern is stated explicitly.
"""
from __future__ import annotations

from typing import Any

from app.config.framework import Framework
from app.ml.rules import RuleResult
from app.services.evidence import (
    STATUS_CONFIRMED,
    STATUS_CONTRADICTED,
    STATUS_PROPOSED,
    EvidenceRecord,
)


def verify_prediction(
    predicted_trl: int,
    evidence: list[EvidenceRecord],
    rule_result: RuleResult,
    framework: Framework,
) -> dict[str, Any]:
    rules = framework.rules
    max_above = int(rules.get("max_levels_above_confirmed", 2))
    supported = rule_result.supported_level
    milestone_map = rule_result.milestone_map

    predicted_milestone = next(
        (m for m in rule_result.milestones if m.trl == predicted_trl), None
    )

    # Evidence that actually backs the predicted level.
    backing: list[EvidenceRecord] = []
    if predicted_milestone is not None:
        backing = [
            e
            for e in evidence
            if e.milestone == predicted_milestone.id and e.status == STATUS_CONFIRMED
        ]
    if not backing:
        # Fall back to the strongest confirming evidence at or below the
        # predicted level (explicitly reported as lower-level support).
        backing = [
            e
            for e in evidence
            if e.status == STATUS_CONFIRMED
            and e.milestone is not None
            and milestone_map.get(e.milestone) is not None
            and milestone_map[e.milestone].trl <= predicted_trl
        ][:6]

    contradictions = [e for e in evidence if e.status == STATUS_CONTRADICTED]
    proposed_high = [
        e
        for e in evidence
        if e.status == STATUS_PROPOSED
        and e.milestone is not None
        and milestone_map.get(e.milestone) is not None
        and milestone_map[e.milestone].trl >= predicted_trl
    ]

    unsupported = (supported or 0) + max_above < predicted_trl

    concerns: list[str] = []
    if predicted_milestone is not None and predicted_milestone.status != "confirmed":
        if predicted_milestone.status == "not_found":
            concerns.append(
                f"No documented evidence was found for the TRL {predicted_trl} "
                f"milestone '{predicted_milestone.label}'."
            )
        elif predicted_milestone.status == "contradicted":
            concerns.append(
                f"The TRL {predicted_trl} milestone '{predicted_milestone.label}' "
                "is explicitly contradicted by the document."
            )
        else:
            concerns.append(
                f"Evidence for the TRL {predicted_trl} milestone "
                f"'{predicted_milestone.label}' is unclear or conflicting."
            )

    if unsupported:
        concerns.append(
            f"The predicted TRL {predicted_trl} is not backed by confirmed evidence: "
            f"only TRL {supported or 'none'} is evidence-confirmed in this document."
        )
    if contradictions:
        levels = sorted(
            {
                milestone_map[e.milestone].trl
                for e in contradictions
                if e.milestone and e.milestone in milestone_map
            }
        )
        if levels:
            concerns.append(
                "The document explicitly contradicts readiness at TRL "
                + ", ".join(str(level) for level in levels)
                + "."
            )
    if proposed_high:
        concerns.append(
            f"{len(proposed_high)} statement(s) describe TRL {predicted_trl}+ "
            "activities as planned/future work - planned activities were not "
            "counted as completed evidence."
        )
    if not concerns:
        concerns.append(
            f"Documented evidence supports the TRL {predicted_trl} milestone chain."
        )

    # Summary
    if unsupported or predicted_milestone is None or predicted_milestone.status != "confirmed":
        summary = (
            f"Insufficient direct evidence for TRL {predicted_trl}. "
            + (" ".join(concerns[:2]))
        ).strip()
    else:
        pages = sorted(
            {e.page_number for e in backing if e.page_number is not None}
        )
        page_note = f" (pages {', '.join(map(str, pages))})" if pages else ""
        summary = (
            f"TRL {predicted_trl} is supported by {len(backing)} confirmed "
            f"excerpt(s){page_note}."
        )

    return {
        "predicted_trl": predicted_trl,
        "evidence_backing": [e.to_dict() for e in backing[:8]],
        "contradictions": [e.to_dict() for e in contradictions[:8]],
        "proposed_mistaken_for_done": [e.to_dict() for e in proposed_high[:8]],
        "unsupported_high_level_claim": bool(unsupported),
        "concerns": concerns,
        "summary": summary,
    }
