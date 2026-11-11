"""Cross-source contradiction detection.

Only *explicit* conflicts are reported: a statement classified as completed
(``confirmed``) alongside a statement that explicitly says the activity did not
happen (``contradicted``). Planned work or vague mentions are never dressed up
as contradictions. Every item names both sources and gives a concrete
human-verification step.
"""
from __future__ import annotations

from itertools import islice
from typing import Any, Iterable

from app.services.evidence import (
    STATUS_CONFIRMED,
    STATUS_CONTRADICTED,
    EvidenceRecord,
)


def _source(item: EvidenceRecord, uploaded: dict[str | None, str | None]) -> dict[str, Any]:
    return {
        "evidence_id": item.id,
        "statement": item.statement,
        "source_document": item.source_document,
        "document_id": item.document_id,
        "page_number": item.page_number,
        "location": item.location,
        "status": item.status,
        "uploaded_at": uploaded.get(item.document_id),
        "outdated": item.outdated,
    }


def _verification_steps(milestone_label: str, category_label: str) -> list[str]:
    subject = milestone_label or category_label or "the claim"
    return [
        f"Ask the responsible engineer to confirm the current status of {subject}.",
        "Check whether the excerpts refer to the same configuration, test article "
        "and reporting period.",
        "Prefer the most recent signed test report or certificate; explicitly "
        "supersede older documents in the assessment record.",
        "If the conflict cannot be resolved, keep the milestone as unclear rather "
        "than counting it as confirmed.",
    ]


def detect_contradictions(
    unique_evidence: list[EvidenceRecord],
    all_evidence: list[EvidenceRecord],
    framework: Any,
    uploaded_by_document: dict[str | None, str | None] | None = None,
) -> dict[str, Any]:
    uploaded = uploaded_by_document or {}
    items: list[dict[str, Any]] = []
    seen_pairs: set[tuple[str, str]] = set()
    seen_milestones: set[str] = set()
    seen_categories: set[str] = set()
    counter = 0

    def add(
        *,
        kind: str,
        severity: str,
        left: EvidenceRecord,
        right: EvidenceRecord,
        milestone: str | None,
        milestone_label: str | None,
        category: str | None,
        category_label: str | None,
        explanation: str,
    ) -> None:
        nonlocal counter
        pair = tuple(sorted((left.id, right.id)))
        if pair in seen_pairs:
            return
        seen_pairs.add(pair)
        counter += 1
        items.append(
            {
                "id": f"con_{counter:03d}",
                "type": kind,
                "severity": severity,
                "milestone": milestone,
                "milestone_label": milestone_label,
                "category": category,
                "category_label": category_label,
                "explanation": explanation,
                "sources": [_source(left, uploaded), _source(right, uploaded)],
                "human_verification": _verification_steps(
                    milestone_label or "", category_label or ""
                ),
                "suggested_action": (
                    "Resolve with a dated, signed source before relying on the "
                    "confirmed milestone; otherwise classify it as unclear."
                ),
            }
        )

    milestone_map = {str(ms["id"]): ms for ms in framework.milestones}

    # 1. Same milestone: confirmed vs explicitly contradicted.
    for milestone_id, milestone in milestone_map.items():
        supporting = [
            item
            for item in unique_evidence
            if item.milestone == milestone_id and item.status == STATUS_CONFIRMED
        ]
        contradicting = [
            item
            for item in unique_evidence
            if item.milestone == milestone_id and item.status == STATUS_CONTRADICTED
        ]
        if not supporting or not contradicting:
            continue
        seen_milestones.add(milestone_id)
        for left, right in islice(
            ((a, b) for a in supporting for b in contradicting), 3
        ):
            cross_document = left.document_id != right.document_id
            add(
                kind=(
                    "cross_document_conflict"
                    if cross_document
                    else "explicit_contradiction"
                ),
                severity="high",
                left=left,
                right=right,
                milestone=milestone_id,
                milestone_label=str(milestone.get("label", "")),
                category=left.category,
                category_label=left.category_label,
                explanation=(
                    f"'{left.source_document}' states the milestone "
                    f"'{milestone.get('label', '')}' was achieved, while "
                    f"'{right.source_document}' explicitly states it has not "
                    "occurred. Both excerpts are retained verbatim."
                ),
            )

    # 2. Same evidence category, different milestone: contradictory signals.
    categories = {str(cat["id"]): cat for cat in framework.categories}
    for category_id, category in categories.items():
        if any(
            item.category == category_id and item.milestone in seen_milestones
            for item in unique_evidence
        ):
            # Already covered by a stronger milestone-level conflict.
            continue
        supporting = [
            item
            for item in unique_evidence
            if item.category == category_id and item.status == STATUS_CONFIRMED
        ]
        contradicting = [
            item
            for item in unique_evidence
            if item.category == category_id and item.status == STATUS_CONTRADICTED
        ]
        if not supporting or not contradicting:
            continue
        seen_categories.add(category_id)
        left, right = supporting[0], contradicting[0]
        add(
            kind="category_conflict",
            severity="medium",
            left=left,
            right=right,
            milestone=None,
            milestone_label=None,
            category=category_id,
            category_label=str(category.get("label", "")),
            explanation=(
                f"Within the '{category.get('label', category_id)}' evidence "
                f"category, '{left.source_document}' reports completed work while "
                f"'{right.source_document}' explicitly reports that it has not "
                "happened."
            ),
        )

    # 3. Duplicate claims whose copies disagree (often an old vs new document).
    groups: dict[str, list[EvidenceRecord]] = {}
    for item in all_evidence:
        if item.duplicate_group:
            groups.setdefault(item.duplicate_group, []).append(item)
    for group_id, members in groups.items():
        statuses = {item.status for item in members}
        if STATUS_CONFIRMED not in statuses or STATUS_CONTRADICTED not in statuses:
            continue
        confirmed = next(i for i in members if i.status == STATUS_CONFIRMED)
        contradicted = next(i for i in members if i.status == STATUS_CONTRADICTED)
        add(
            kind="outdated_conflict",
            severity="high",
            left=confirmed,
            right=contradicted,
            milestone=confirmed.milestone,
            milestone_label=confirmed.milestone_label,
            category=confirmed.category,
            category_label=confirmed.category_label,
            explanation=(
                "The same claim appears in multiple documents with opposing "
                "statuses. Check which document is current; the older copy is "
                "marked outdated in the evidence table."
            ),
        )

    by_type: dict[str, int] = {}
    for item in items:
        by_type[item["type"]] = by_type.get(item["type"], 0) + 1

    if items:
        summary = (
            f"{len(items)} contradiction(s) detected across the supplied "
            "documents. Review the named sources before accepting the "
            "confirmed milestone."
        )
    else:
        summary = (
            "No explicit cross-source contradictions were detected. This does "
            "not prove consistency: it only means no confirmed statement was "
            "paired with an explicit negative statement."
        )

    return {
        "total": len(items),
        "by_type": by_type,
        "items": items,
        "summary": summary,
    }


def count_contradictions(report: dict[str, Any] | None) -> int:
    return int((report or {}).get("total", 0) or 0)


def evidence_ids(report: dict[str, Any] | None) -> Iterable[str]:
    for item in (report or {}).get("items", []) or []:
        for source in item.get("sources", []) or []:
            yield str(source.get("evidence_id", ""))
