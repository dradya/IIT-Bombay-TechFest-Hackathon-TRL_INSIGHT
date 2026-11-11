"""STEP 7 - Gap analysis.

Compares the evidence actually available with the requirements of the
next TRL and produces concrete, traceable recommendations. Every
recommendation names the missing milestone(s) it addresses, and no
recommendation is emitted for a milestone that is already confirmed.
"""
from __future__ import annotations

from typing import Any

from app.config.framework import Framework
from app.ml.rules import RuleResult

STATUS_LABELS = {
    "confirmed": "confirmed",
    "not_found": "missing",
    "contradicted": "contradicted",
    "unclear": "unclear",
}


def _milestone_dicts(statuses: list[str], rule_result: RuleResult) -> list[dict[str, Any]]:
    return [m.to_dict() for m in rule_result.milestones if m.status in statuses]


def build_gap_analysis(
    predicted_trl: int,
    rule_result: RuleResult,
    framework: Framework,
) -> dict[str, Any]:
    level_info = framework.level(predicted_trl)
    current_name = level_info.get("name", "")
    next_trl = predicted_trl + 1 if predicted_trl < 9 else None
    next_name = framework.level(next_trl).get("name") if next_trl else None

    milestone_map = rule_result.milestone_map
    chain_ids = [m["id"] for m in framework.milestones_up_to(next_trl or predicted_trl)]

    completed = [
        m.to_dict()
        for m in rule_result.milestones
        if m.id in chain_ids and m.status == "confirmed"
    ]
    missing = [
        m.to_dict()
        for m in rule_result.milestones
        if m.id in chain_ids and m.status == "not_found"
    ]
    unclear = [
        m.to_dict()
        for m in rule_result.milestones
        if m.id in chain_ids and m.status == "unclear"
    ]
    contradicted = [
        m.to_dict()
        for m in rule_result.milestones
        if m.status == "contradicted"
    ]

    # ------------------------------------------------------------------
    # Recommendations: every template whose milestone is not confirmed
    # inside the chain up to the next target level.
    # ------------------------------------------------------------------
    recommendations: list[dict[str, Any]] = []
    missing_actions = framework.missing_milestone_actions
    effective_next = next_trl or 9  # TRL 9 assessments use the full chain

    for template in framework.recommendations:
        target = int(template.get("target_trl", 0))
        addresses = list(template.get("addresses", []))
        relevant = [a for a in addresses if a in chain_ids and a in milestone_map]
        if not relevant:
            continue
        if target > effective_next:
            continue  # too far ahead of the current assessment
        # Only recommend work that is still missing (never restate
        # milestones that are already confirmed).
        unresolved = [a for a in relevant if milestone_map[a].status != "confirmed"]
        if not unresolved:
            continue

        statuses = [milestone_map[a].status for a in relevant]
        if target == effective_next:
            priority = "high"
        elif target >= predicted_trl:
            priority = "medium"
        else:
            priority = "low"

        recommendations.append(
            {
                "id": template.get("id", f"rec_{target}"),
                "title": template.get("title", ""),
                "addresses": relevant,
                "address_labels": [
                    milestone_map[a].label if a in milestone_map else a for a in relevant
                ],
                "address_statuses": [
                    STATUS_LABELS.get(s, s) for s in statuses
                ],
                "actions": list(template.get("actions", [])),
                "validation_experiments": list(template.get("validation_experiments", [])),
                "documentation": list(template.get("documentation", [])),
                "priority": priority,
            }
        )

    # TRL 9 assessments: sustaining recommendations are always relevant.
    if next_trl is None and not any(r["id"] == "rec_sustain" for r in recommendations):
        sustain = next(
            (t for t in framework.recommendations if t.get("id") == "rec_sustain"), None
        )
        if sustain is not None:
            mid = (sustain.get("addresses") or ["m9"])[0]
            if mid in milestone_map:
                recommendations.append(
                    {
                        "id": "rec_sustain",
                        "title": sustain.get("title", ""),
                        "addresses": [mid],
                        "address_labels": [milestone_map[mid].label],
                        "address_statuses": [
                            STATUS_LABELS.get(milestone_map[mid].status, milestone_map[mid].status)
                        ],
                        "actions": list(sustain.get("actions", [])),
                        "validation_experiments": list(
                            sustain.get("validation_experiments", [])
                        ),
                        "documentation": list(sustain.get("documentation", [])),
                        "priority": "medium",
                    }
                )

    # Fallback: if nothing matched (e.g. unusual framework), generate
    # generic actions for each missing milestone so the user still gets
    # actionable output.
    if not recommendations:
        for milestone in missing + unclear:
            mid = milestone["id"]
            recommendations.append(
                {
                    "id": f"rec_auto_{mid}",
                    "title": missing_actions.get(mid, f"Address milestone {milestone['label']}"),
                    "addresses": [mid],
                    "address_labels": [milestone["label"]],
                    "address_statuses": [STATUS_LABELS.get(milestone["status"], milestone["status"])],
                    "actions": [missing_actions.get(mid, "Collect evidence for this milestone.")],
                    "validation_experiments": [],
                    "documentation": ["Documented test/analysis report with measured results."],
                    "priority": "high" if milestone["status"] == "not_found" else "medium",
                }
            )

    recommendations.sort(
        key=lambda r: ({"high": 0, "medium": 1, "low": 2}[r["priority"]], r["id"])
    )

    documentation_requirements: list[str] = []
    for rec in recommendations:
        for doc in rec["documentation"]:
            if doc not in documentation_requirements:
                documentation_requirements.append(doc)
    if not documentation_requirements:
        documentation_requirements = [
            "Technical report with page-referenced measured results."
        ]

    n_chain = len(chain_ids)
    n_done = len(completed)
    if next_trl is None:
        summary = (
            f"TRL {predicted_trl} ({current_name}) is the top of the scale: "
            f"{n_done}/{n_chain} chain milestones confirmed. Sustain operational "
            "evidence and continue monitoring."
        )
    else:
        summary = (
            f"Current supported readiness: TRL {predicted_trl} ({current_name}). "
            f"Next target: TRL {next_trl} ({next_name}). "
            f"{n_done}/{n_chain} milestones in the chain are confirmed; "
            f"{len(missing)} missing, {len(unclear)} unclear"
            + (f", {len(contradicted)} contradicted" if contradicted else "")
            + "."
        )
        if rule_result.supported_level is not None and rule_result.supported_level != predicted_trl:
            summary += (
                f" Note: confirmed evidence directly reaches only TRL "
                f"{rule_result.supported_level}."
            )
        elif rule_result.supported_level is None:
            summary += " Note: no milestone is confirmed by documented evidence yet."

    return {
        "current_trl": predicted_trl,
        "current_name": current_name,
        "next_trl": next_trl,
        "next_name": next_name,
        "completed_milestones": completed,
        "missing_milestones": missing,
        "unclear_milestones": unclear,
        "contradicted_milestones": contradicted,
        "recommendations": recommendations,
        "documentation_requirements": documentation_requirements,
        "summary": summary,
    }
