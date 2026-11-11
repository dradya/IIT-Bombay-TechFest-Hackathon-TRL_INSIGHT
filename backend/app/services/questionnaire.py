"""Missing-evidence questionnaire for reassessment.

Questions are generated only for milestones that are genuinely unresolved
(``not_found``, ``unclear`` or ``contradicted``) in the current assessment.
Answers are self-reported; the reassessment flow treats a ``completed`` answer
as confirmed evidence *only* when a source reference is supplied.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.config.framework import Framework


def _expected_document(framework: Framework, milestone_id: str) -> str:
    for recommendation in framework.recommendations:
        if milestone_id in (recommendation.get("addresses") or []):
            docs = recommendation.get("documentation") or []
            if docs:
                return str(docs[0])
    return (
        "A dated test report, certificate or peer-reviewed publication that "
        "names the measured result."
    )


def build_questionnaire(
    assessment_id: str,
    rule_result: Any,
    framework: Framework,
    gap_analysis: dict[str, Any],
) -> dict[str, Any]:
    gap_status: dict[str, str] = {}
    for key in (
        "missing_milestones",
        "unclear_milestones",
        "contradicted_milestones",
    ):
        for milestone in gap_analysis.get(key, []) or []:
            gap_status[str(milestone.get("id"))] = str(milestone.get("status", ""))

    items: list[dict[str, Any]] = []
    for assessment in rule_result.milestones:
        status = gap_status.get(assessment.id, assessment.status)
        if status == "confirmed":
            continue
        milestone = framework.milestone(assessment.id)
        label = str(milestone.get("label", assessment.label))
        if status == "contradicted":
            question = (
                f"The documents explicitly state that '{label}' has not been "
                "achieved. Has this since been completed, and where is that "
                "documented?"
            )
        elif status == "unclear":
            question = (
                f"Evidence for '{label}' is unclear or conflicting. Has this "
                "activity been completed, and which document reports the result?"
            )
        else:
            question = (
                f"No evidence was found for '{label}'. Has this activity been "
                "completed, planned, or is it not applicable?"
            )
        items.append(
            {
                "id": f"q_{assessment.id}",
                "milestone": assessment.id,
                "milestone_label": label,
                "trl": int(assessment.trl),
                "status": status,
                "question": question,
                "why_it_matters": str(milestone.get("description", "")),
                "expected_document": _expected_document(framework, assessment.id),
                "options": [
                    "completed",
                    "planned",
                    "not_applicable",
                    "unknown",
                ],
            }
        )

    return {
        "assessment_id": assessment_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total": len(items),
        "items": items,
        "note": (
            "Answers are self-reported. They are only treated as confirmed "
            "evidence when a source reference is supplied; otherwise the "
            "milestone stays unclear."
        ),
    }
