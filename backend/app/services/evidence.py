"""STEP 3 - Evidence extraction.

For every source-located sentence the extractor determines:

* the evidence category (which part of the TRL chain it concerns),
* the milestone it can support,
* the evidence STATUS - critically distinguishing
    - confirmed      : an activity actually performed (optionally with results)
    - proposed       : future intent / planned work (does NOT prove anything)
    - contradicted   : the document explicitly states something did not happen
    - unclear        : mentions the topic without enough information,
* whether the excerpt matches the milestone's DEFINING indicators
  (only then can it confirm a milestone),
* a relevance score.

Excerpts are copied verbatim from the document; page numbers come from the
ingestion step and are never fabricated.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.config.framework import Framework
from app.services.document_processing import CleanSentence, ProcessedDocument
from app.utils.text import keyword_hits, normalize_for_matching

STATUS_CONFIRMED = "confirmed"
STATUS_PROPOSED = "proposed"
STATUS_CONTRADICTED = "contradicted"
STATUS_UNCLEAR = "unclear"

STANCE_BY_STATUS = {
    STATUS_CONFIRMED: "supporting",
    STATUS_CONTRADICTED: "contradicting",
    STATUS_PROPOSED: "insufficient",
    STATUS_UNCLEAR: "insufficient",
}

# How strongly each canonical section supports "this really happened".
SECTION_WEIGHT = {
    "results": 1.0,
    "discussion": 0.9,
    "methods": 0.85,
    "abstract": 0.75,
    "conclusion": 0.75,
    "introduction": 0.5,
    "future_work": 0.25,
    "references": 0.0,
    "unknown": 0.5,
}


@dataclass
class EvidenceRecord:
    id: str
    statement: str
    category: str
    category_label: str
    status: str
    stance: str
    source_document: str
    page_number: int | None
    location: str
    section: str
    milestone: str | None
    milestone_label: str | None
    supports_milestone: bool
    relevance: float
    is_proposed: bool = False
    future_tense: bool = False
    negated: bool = False
    has_results: bool = False
    completed: bool = False
    matched_keywords: list[str] = field(default_factory=list)
    # --- TRL INSIGHT 2.0 additive provenance / graph fields -------------
    document_id: str | None = None
    evidence_type: str = "document"
    duplicate_group: str | None = None
    duplicate_of: str | None = None
    duplicate_count: int = 1
    superseded_by: str | None = None
    outdated: bool = False
    semantic_similarity: float | None = None
    semantic_milestone: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "statement": self.statement,
            "category": self.category,
            "category_label": self.category_label,
            "status": self.status,
            "stance": self.stance,
            "source_document": self.source_document,
            "page_number": self.page_number,
            "location": self.location,
            "section": self.section,
            "milestone": self.milestone,
            "milestone_label": self.milestone_label,
            "supports_milestone": self.supports_milestone,
            "relevance": round(float(self.relevance), 3),
            "is_proposed": self.is_proposed,
            "future_tense": self.future_tense,
            "negated": self.negated,
            "document_id": self.document_id,
            "evidence_type": self.evidence_type,
            "duplicate_group": self.duplicate_group,
            "duplicate_of": self.duplicate_of,
            "duplicate_count": self.duplicate_count,
            "superseded_by": self.superseded_by,
            "outdated": self.outdated,
            "semantic_similarity": self.semantic_similarity,
            "semantic_milestone": self.semantic_milestone,
        }


class PatternSet:
    """Compiled status patterns from the framework configuration."""

    def __init__(self, patterns: dict[str, list[str]]):
        self.contradicted = _compile(patterns.get("contradicted", []))
        self.proposed = _compile(patterns.get("proposed", []))
        self.completion = _compile(patterns.get("completion", []))
        self.results = _compile(patterns.get("results", []))

    def find(self, group: list[re.Pattern[str]], text: str) -> str | None:
        for pattern in group:
            if pattern.search(text):
                return pattern.pattern
        return None


def _compile(patterns: list[str]) -> list[re.Pattern[str]]:
    out: list[re.Pattern[str]] = []
    for raw in patterns:
        try:
            out.append(re.compile(raw, re.IGNORECASE))
        except re.error:
            continue
    return out


_PATTERN_CACHE: dict[str, PatternSet] = {}


def get_pattern_set(framework: Framework) -> PatternSet:
    key = framework.version
    if key not in _PATTERN_CACHE:
        _PATTERN_CACHE[key] = PatternSet(framework.status_patterns)
    return _PATTERN_CACHE[key]


@dataclass
class EvidenceResult:
    items: list[EvidenceRecord] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)


def _best_category(lower: str, framework: Framework) -> tuple[dict[str, Any] | None, int, list[str]]:
    best: dict[str, Any] | None = None
    best_hits = 0
    best_words: list[str] = []
    for cat in framework.categories:
        count, words = keyword_hits(lower, cat.get("keywords", []))
        if count > best_hits:
            best, best_hits, best_words = cat, count, words
    return best, best_hits, best_words


def _best_milestone(lower: str, framework: Framework) -> tuple[dict[str, Any] | None, int]:
    best: dict[str, Any] | None = None
    best_hits = 0
    for ms in framework.milestones:
        count, _ = keyword_hits(lower, ms.get("defining_indicators", []))
        if count > best_hits:
            best, best_hits = ms, count
    return best, best_hits


def _relevance(
    *,
    defining_hits: int,
    category_hits: int,
    completed: bool,
    has_results: bool,
    completion_required: bool,
    section: str,
    text: str,
) -> float:
    score = 0.0
    score += 0.30 * min(defining_hits, 3) / 3.0
    score += 0.25 * min(category_hits, 4) / 4.0
    if completed:
        score += 0.15 if has_results else 0.10
    elif not completion_required:
        score += 0.08
    score += 0.15 * SECTION_WEIGHT.get(section, 0.5)
    length = len(text)
    score += 0.15 if 40 <= length <= 450 else 0.06
    return max(0.0, min(1.0, score))


def extract_evidence(
    processed: ProcessedDocument,
    framework: Framework,
    source_document: str,
    max_items: int = 120,
) -> EvidenceResult:
    """Extract and classify evidence from the cleaned document."""
    patterns = get_pattern_set(framework)
    tp = framework.text_processing
    future_sections = set(tp.get("future_section_names", ["future_work"]))

    records: list[EvidenceRecord] = []
    counter = 0

    for sent in processed.sentences:
        lower = sent.normalized
        if not lower:
            continue

        matched_contradicted = patterns.find(patterns.contradicted, lower)
        matched_proposed = patterns.find(patterns.proposed, lower)
        matched_completion = patterns.find(patterns.completion, lower)
        matched_results = patterns.find(patterns.results, lower)

        category, category_hits, cat_words = _best_category(lower, framework)
        milestone, defining_hits = _best_milestone(lower, framework)

        if category is None and milestone is None:
            continue  # not about the technology readiness chain

        # A sentence with a milestone match always belongs to that milestone's
        # primary category when no stronger category was found.
        if category is None and milestone is not None:
            primary = milestone["trl"]
            for cat in framework.categories:
                if cat.get("primary_milestone") == milestone["id"]:
                    category = cat
                    break
            category = category or {"id": "general", "label": "General technical evidence",
                                    "primary_milestone": milestone["id"]}
            category_hits = max(category_hits, 1)

        # A milestone match implies its category even if another category won.
        if milestone is not None and category is not None:
            ms_cat_ids = [
                c["id"] for c in framework.categories_for_milestone(milestone["id"])
            ]
            if category.get("id") not in ms_cat_ids and defining_hits > 0:
                for cat in framework.categories_for_milestone(milestone["id"]):
                    count, _ = keyword_hits(lower, cat.get("keywords", []))
                    if count > 0:
                        category = cat
                        category_hits = max(category_hits, count)
                        break

        completed = matched_completion is not None
        has_results = matched_results is not None
        in_future_section = sent.section in future_sections

        # ---- status resolution (conservative order) -------------------
        if matched_contradicted is not None:
            status = STATUS_CONTRADICTED
            negated, future = True, False
        elif matched_proposed is not None or (in_future_section and not completed):
            status = STATUS_PROPOSED
            negated, future = False, True
        elif milestone is not None and milestone.get("completion_required") and not completed:
            status = STATUS_UNCLEAR
            negated, future = False, matched_proposed is not None
        elif completed or not (
            milestone is not None and milestone.get("completion_required")
        ):
            status = STATUS_CONFIRMED
            negated, future = False, False
        else:
            status = STATUS_UNCLEAR
            negated, future = False, False

        completion_required = bool(milestone and milestone.get("completion_required"))
        supports = (
            status == STATUS_CONFIRMED
            and defining_hits > 0
            and (completed or not completion_required)
        )

        relevance = _relevance(
            defining_hits=defining_hits,
            category_hits=category_hits,
            completed=completed,
            has_results=has_results,
            completion_required=completion_required,
            section=sent.section,
            text=sent.text,
        )

        # Keep genuinely relevant items only.
        if defining_hits == 0 and category_hits == 0:
            continue
        if relevance < 0.30 and status in (STATUS_UNCLEAR, STATUS_PROPOSED):
            continue
        if relevance < 0.22:
            continue

        counter += 1
        milestone_label = milestone.get("label") if milestone else None
        records.append(
            EvidenceRecord(
                id=f"e{counter:03d}",
                statement=sent.text,
                category=(category or {}).get("id", "general"),
                category_label=(category or {}).get("label", "General technical evidence"),
                status=status,
                stance=STANCE_BY_STATUS[status],
                source_document=source_document,
                page_number=sent.page,
                location=sent.locator,
                section=sent.section,
                milestone=milestone.get("id") if milestone else None,
                milestone_label=milestone_label,
                supports_milestone=supports,
                relevance=relevance,
                is_proposed=(status == STATUS_PROPOSED),
                future_tense=future,
                negated=negated,
                has_results=has_results,
                completed=completed,
                matched_keywords=sorted(set(cat_words))[:6],
            )
        )

    # Rank: milestone-confirming evidence first, then by relevance.
    records.sort(key=lambda r: (not r.supports_milestone, -r.relevance, r.id))
    truncated = len(records) > max_items
    records = records[:max_items]

    stats = {
        "total": len(records),
        "confirmed": sum(1 for r in records if r.status == STATUS_CONFIRMED),
        "proposed": sum(1 for r in records if r.status == STATUS_PROPOSED),
        "contradicted": sum(1 for r in records if r.status == STATUS_CONTRADICTED),
        "unclear": sum(1 for r in records if r.status == STATUS_UNCLEAR),
        "milestone_supporting": sum(1 for r in records if r.supports_milestone),
        "truncated": truncated,
    }
    return EvidenceResult(items=records, stats=stats)


def evidence_by_category(
    items: list[EvidenceRecord], framework: Framework
) -> list[dict[str, Any]]:
    """Per-category counts used by the API/ UI."""
    out: list[dict[str, Any]] = []
    for cat in framework.categories:
        subset = [i for i in items if i.category == cat["id"]]
        out.append(
            {
                "category": cat["id"],
                "label": cat["label"],
                "count": len(subset),
                "confirmed": sum(1 for i in subset if i.status == STATUS_CONFIRMED),
                "proposed": sum(1 for i in subset if i.status == STATUS_PROPOSED),
                "contradicted": sum(1 for i in subset if i.status == STATUS_CONTRADICTED),
                "unclear": sum(1 for i in subset if i.status == STATUS_UNCLEAR),
            }
        )
    return out
