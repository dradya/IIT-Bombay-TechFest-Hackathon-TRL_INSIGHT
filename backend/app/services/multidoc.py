"""Multi-document evidence merging, duplicate handling and provenance.

The single-document path is unchanged: evidence ids keep the ``e001`` form and
the same pipeline is used. Across documents, repeated claims are grouped and
only one copy is counted by the rules and ML features, so the same statement
cannot inflate readiness. Duplicates remain visible in the API/UI with the id
of the primary item they duplicate.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger
from app.services.document_processing import (
    CleanSentence,
    ProcessedDocument,
    clean_document,
)
from app.services.evidence import (
    STATUS_CONFIRMED,
    STATUS_CONTRADICTED,
    STATUS_PROPOSED,
    STATUS_UNCLEAR,
    EvidenceRecord,
    extract_evidence,
)
from app.services.ingestion import ExtractedDocument
from app.utils.text import normalize_for_matching

logger = get_logger("multidoc")

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9\-]{2,}")
_STOPWORDS = {
    "the", "and", "for", "that", "with", "this", "from", "were", "was",
    "are", "has", "have", "been", "which", "their", "there", "than", "then",
    "them", "these", "those", "such", "into", "also", "only", "other",
    "more", "most", "some", "any", "all", "each", "between", "while",
    "where", "when", "what", "would", "could", "should", "about", "after",
    "before", "under", "over", "using", "used", "use", "our", "its", "not",
}

_STATUS_PRIORITY = {
    STATUS_CONFIRMED: 4,
    STATUS_CONTRADICTED: 3,
    STATUS_UNCLEAR: 2,
    STATUS_PROPOSED: 1,
}


@dataclass
class DocumentInput:
    extracted: ExtractedDocument
    document_id: str | None = None
    filename: str = ""
    uploaded_at: str | None = None


@dataclass
class MergeResult:
    all_evidence: list[EvidenceRecord] = field(default_factory=list)
    unique_evidence: list[EvidenceRecord] = field(default_factory=list)
    processed: ProcessedDocument = field(default_factory=ProcessedDocument)
    documents: list[dict[str, Any]] = field(default_factory=list)
    duplicate_groups: list[dict[str, Any]] = field(default_factory=list)
    duplicates: int = 0
    outdated: int = 0


def _tokens(text: str) -> set[str]:
    return {
        token
        for token in _TOKEN_RE.findall(normalize_for_matching(text))
        if token not in _STOPWORDS
    }


def _similar(left: EvidenceRecord, right: EvidenceRecord) -> bool:
    if normalize_for_matching(left.statement) == normalize_for_matching(right.statement):
        return True
    a, b = _tokens(left.statement), _tokens(right.statement)
    if not a or not b:
        return False
    intersection = len(a & b)
    union = len(a | b)
    return union > 0 and (intersection / union) >= 0.86


def _source_names(documents: list[DocumentInput]) -> list[str]:
    used: dict[str, int] = {}
    names: list[str] = []
    for document in documents:
        base = (
            document.filename
            or document.extracted.filename
            or "document"
        ).strip()
        count = used.get(base, 0) + 1
        used[base] = count
        names.append(base if count == 1 else f"{base} (#{count})")
    return names


def _merge_processed(per_document: list[ProcessedDocument]) -> ProcessedDocument:
    if len(per_document) == 1:
        return per_document[0]
    merged = ProcessedDocument()
    sections: set[str] = set()
    headings: list[str] = []
    for processed in per_document:
        merged.sentences.extend(processed.sentences)
        merged.keywords.extend(processed.keywords)
        merged.duplicates_removed += processed.duplicates_removed
        merged.noise_removed += processed.noise_removed
        sections.update(processed.sections)
        for heading in processed.headings:
            if heading not in headings:
                headings.append(heading)
    merged.sections = sorted(sections)
    merged.headings = headings
    merged.keywords = list(dict.fromkeys(merged.keywords))[:30]
    return merged


def _renumber(all_evidence: list[EvidenceRecord]) -> None:
    for index, item in enumerate(all_evidence, start=1):
        item.id = f"e{index:03d}"


def _group_duplicates(
    evidence: list[EvidenceRecord],
    documents: list[DocumentInput],
) -> tuple[list[EvidenceRecord], list[dict[str, Any]]]:
    """Group near-duplicate claims and return the primary (counted) items."""
    uploaded_by_doc = {
        document.document_id: document.uploaded_at
        for document in documents
        if document.document_id
    }

    groups: list[list[EvidenceRecord]] = []
    assigned: set[int] = set()
    for index, item in enumerate(evidence):
        if index in assigned:
            continue
        group = [item]
        assigned.add(index)
        for other_index in range(index + 1, len(evidence)):
            if other_index in assigned:
                continue
            other = evidence[other_index]
            if _similar(item, other):
                group.append(other)
                assigned.add(other_index)
        groups.append(group)

    unique: list[EvidenceRecord] = []
    summaries: list[dict[str, Any]] = []

    for group_index, group in enumerate(groups, start=1):
        group_id = f"dup_{group_index:03d}"
        for item in group:
            item.duplicate_group = group_id if len(group) > 1 else None
            item.duplicate_count = len(group)

        newest = max(
            group,
            key=lambda item: (
                uploaded_by_doc.get(item.document_id) or "",
                item.id,
            ),
        )
        primary = sorted(
            group,
            key=lambda item: (
                -_STATUS_PRIORITY.get(item.status, 0),
                -float(item.relevance),
                uploaded_by_doc.get(item.document_id) or "",
                item.id,
            ),
        )[0]

        for item in group:
            if item is not primary:
                item.duplicate_of = primary.id
            if len(group) > 1 and newest.document_id != item.document_id:
                item.outdated = True
                item.superseded_by = newest.id

        unique.append(primary)
        if len(group) > 1:
            summaries.append(
                {
                    "group": group_id,
                    "primary": primary.id,
                    "count": len(group),
                    "members": [
                        {
                            "evidence_id": item.id,
                            "source_document": item.source_document,
                            "document_id": item.document_id,
                            "status": item.status,
                            "page_number": item.page_number,
                            "outdated": item.outdated,
                            "superseded_by": item.superseded_by,
                        }
                        for item in group
                    ],
                    "newest_evidence_id": newest.id,
                    "newest_document": newest.source_document,
                }
            )

    unique.sort(key=lambda item: item.id)
    return unique, summaries


def merge_documents(
    documents: list[DocumentInput], framework: Any
) -> MergeResult:
    """Clean, extract and merge evidence from one or more documents."""
    if not documents:
        return MergeResult()

    names = _source_names(documents)
    all_evidence: list[EvidenceRecord] = []
    processed_by_doc: list[ProcessedDocument] = []
    per_document_counts: list[dict[str, int]] = []

    for index, document in enumerate(documents):
        processed = clean_document(document.extracted, framework)
        processed_by_doc.append(processed)
        result = extract_evidence(processed, framework, names[index])
        for item in result.items:
            item.document_id = document.document_id
            item.evidence_type = "document"
        all_evidence.extend(result.items)
        per_document_counts.append(
            {
                "evidence_count": len(result.items),
                "confirmed": sum(
                    1 for item in result.items if item.status == STATUS_CONFIRMED
                ),
                "proposed": sum(
                    1 for item in result.items if item.status == STATUS_PROPOSED
                ),
                "contradicted": sum(
                    1 for item in result.items if item.status == STATUS_CONTRADICTED
                ),
                "unclear": sum(
                    1 for item in result.items if item.status == STATUS_UNCLEAR
                ),
            }
        )

    _renumber(all_evidence)
    unique, groups = _group_duplicates(all_evidence, documents)

    document_summaries: list[dict[str, Any]] = []
    for index, document in enumerate(documents):
        counts = per_document_counts[index]
        document_summaries.append(
            {
                "document_id": document.document_id,
                "filename": names[index],
                "page_count": document.extracted.page_count,
                "char_count": document.extracted.char_count,
                "uploaded_at": document.uploaded_at,
                "extraction_method": document.extracted.method,
                **counts,
                "duplicates": sum(
                    1
                    for item in all_evidence
                    if item.document_id == document.document_id
                    and item.duplicate_of is not None
                ),
                "outdated": sum(
                    1
                    for item in all_evidence
                    if item.document_id == document.document_id and item.outdated
                ),
            }
        )

    duplicates = sum(1 for item in all_evidence if item.duplicate_of)
    outdated = sum(1 for item in all_evidence if item.outdated)
    logger.info(
        "Merged %d document(s): %d evidence items, %d unique claims, "
        "%d duplicates, %d outdated",
        len(documents),
        len(all_evidence),
        len(unique),
        duplicates,
        outdated,
    )

    return MergeResult(
        all_evidence=all_evidence,
        unique_evidence=unique,
        processed=_merge_processed(processed_by_doc),
        documents=document_summaries,
        duplicate_groups=groups,
        duplicates=duplicates,
        outdated=outdated,
    )


def supplemental_evidence(
    answers: list[Any],
    framework: Any,
    assessment_id: str = "",
) -> list[EvidenceRecord]:
    """Convert questionnaire answers into clearly-labelled self-reported evidence.

    A ``completed`` answer only confirms a milestone when the reviewer supplies
    a source reference; otherwise it is recorded as ``unclear`` so the system
    never treats an unverified claim as documented evidence.
    """
    records: list[EvidenceRecord] = []
    milestone_map = {str(ms["id"]): ms for ms in framework.milestones}
    category_by_milestone: dict[str, dict[str, Any]] = {}
    for category in framework.categories:
        primary = category.get("primary_milestone")
        if primary:
            category_by_milestone.setdefault(str(primary), category)

    for index, answer in enumerate(answers, start=1):
        milestone_id = str(getattr(answer, "milestone_id", "") or "")
        milestone = milestone_map.get(milestone_id)
        if milestone is None:
            continue
        answer_status = str(getattr(answer, "status", "unknown") or "unknown")
        if answer_status == "not_applicable":
            continue
        note = str(getattr(answer, "evidence_note", "") or "").strip()
        reference = str(getattr(answer, "source_reference", "") or "").strip()
        if not note and not reference:
            continue

        if answer_status == "completed" and reference:
            status = STATUS_CONFIRMED
        elif answer_status == "planned":
            status = STATUS_PROPOSED
        else:
            status = STATUS_UNCLEAR

        category = category_by_milestone.get(milestone_id) or {
            "id": "general",
            "label": "General technical evidence",
        }
        statement = note or (
            f"Reviewer supplied a source reference for '{milestone.get('label')}': "
            f"{reference}"
        )
        records.append(
            EvidenceRecord(
                id=f"e{index:03d}x",
                statement=statement,
                category=str(category.get("id", "general")),
                category_label=str(
                    category.get("label", "General technical evidence")
                ),
                status=status,
                stance={
                    STATUS_CONFIRMED: "supporting",
                    STATUS_CONTRADICTED: "contradicting",
                }.get(status, "insufficient"),
                source_document="Expert questionnaire (self-reported)",
                page_number=None,
                location=reference or "questionnaire answer",
                section="unknown",
                milestone=milestone_id,
                milestone_label=str(milestone.get("label", "")),
                supports_milestone=status == STATUS_CONFIRMED,
                relevance=0.5 if status == STATUS_CONFIRMED else 0.3,
                is_proposed=status == STATUS_PROPOSED,
                future_tense=status == STATUS_PROPOSED,
                negated=False,
                has_results=False,
                completed=status == STATUS_CONFIRMED,
                evidence_type="self_reported",
                document_id=None,
                matched_keywords=[],
            )
        )
    return records
