"""STEP 2 - Document cleaning and segmentation.

Normalisation, section segmentation, sentence splitting, de-duplication,
noise removal and technical keyword identification. Cleaning never
rewrites content: evidence excerpts stay traceable to the source text.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from app.config.framework import Framework
from app.services.ingestion import ExtractedDocument, PageUnit
from app.utils.text import (
    collapse_whitespace,
    is_heading,
    normalize_for_matching,
    split_sentences,
)

_STOPWORDS = {
    "the", "and", "for", "that", "with", "this", "from", "were", "was", "are",
    "has", "have", "been", "which", "their", "there", "than", "then", "them",
    "these", "those", "such", "into", "also", "only", "other", "more", "most",
    "some", "any", "all", "each", "between", "while", "where", "when", "what",
    "which", "would", "could", "should", "about", "after", "before", "under",
    "over", "using", "used", "use", "based", "case", "cases", "shown", "show",
    "shows", "does", "done", "both", "within", "without", "however", "therefore",
    "because", "through", "during", "above", "below", "figure", "table", "section",
    "paper", "study", "work", "works", "well", "one", "two", "three", "first",
    "second", "new", "high", "highly", "level", "levels", "based", "given",
    "similar", "different", "several", "various", "many", "much", "data",
    "results", "result", "analysis", "method", "methods", "approach", "system",
}

_NOISE_PATTERNS = [
    re.compile(r"^https?://\S+$", re.I),
    re.compile(r"^[\d\s.\-/–—:]+$"),
    re.compile(r"^(doi|issn|isbn|vol|pp|pages?)\b", re.I),
    re.compile(r"^©", re.I),
    re.compile(r"^all rights reserved", re.I),
    re.compile(r"^\s*references\s*$", re.I),
    re.compile(r"^\s*\[\d+\]\s"),
    re.compile(r"^\s*fig(ure)?\.?\s*\d+\s*$", re.I),
]


@dataclass
class CleanSentence:
    id: str
    text: str
    page: int | None
    locator: str
    section: str
    unit_index: int
    normalized: str = ""

    def __post_init__(self) -> None:
        if not self.normalized:
            self.normalized = normalize_for_matching(self.text)


@dataclass
class ProcessedDocument:
    sentences: list[CleanSentence] = field(default_factory=list)
    sections: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    duplicates_removed: int = 0
    noise_removed: int = 0
    headings: list[str] = field(default_factory=list)

    @property
    def stats(self) -> dict[str, Any]:
        return {
            "sentences": len(self.sentences),
            "sections": len(self.sections),
            "duplicates_removed": self.duplicates_removed,
            "noise_removed": self.noise_removed,
            "keywords": len(self.keywords),
        }


def _section_aliases(framework: Framework) -> dict[str, str]:
    tp = framework.text_processing
    aliases: dict[str, str] = {}
    for canonical, names in (tp.get("section_aliases") or {}).items():
        for name in names:
            aliases[str(name).lower()] = canonical
    return aliases


def _match_section(heading: str, aliases: dict[str, str]) -> str | None:
    h = heading.strip().lower().rstrip(":")
    h = re.sub(r"^\d+(\.\d+)*\s+", "", h)
    if h in aliases:
        return aliases[h]
    for name, canonical in aliases.items():
        if h.startswith(name) or name in h.split():
            return canonical
    return None


def _is_noise(text: str) -> bool:
    stripped = text.strip()
    if len(stripped) < 12:
        return True
    return any(p.search(stripped) for p in _NOISE_PATTERNS)


def _technical_keywords(sentences: list[CleanSentence], limit: int = 30) -> list[str]:
    counter: Counter[str] = Counter()
    for sent in sentences:
        for token in re.findall(r"[a-zA-Z][a-zA-Z\-]{3,}", sent.text.lower()):
            token = token.strip("-")
            if token in _STOPWORDS or len(token) < 4:
                continue
            counter[token] += 1
    ranked = sorted(counter.items(), key=lambda kv: (-kv[1], -len(kv[0]), kv[0]))
    return [word for word, count in ranked if count >= 1][:limit]


def clean_document(extracted: ExtractedDocument, framework: Framework) -> ProcessedDocument:
    """Segment the extracted text into clean, source-located sentences."""
    tp = framework.text_processing
    min_chars = int(tp.get("min_sentence_chars", 25))
    max_chars = int(tp.get("max_sentence_chars", 1200))
    aliases = _section_aliases(framework)

    processed = ProcessedDocument(headings=list(extracted.headings))
    seen: set[str] = set()
    current_section = "unknown"
    counter = 0

    for unit_index, unit in enumerate(extracted.units):
        blocks = _segment_by_heading(unit, aliases)
        for section, block_text in blocks:
            if section:
                current_section = section
            for sentence in split_sentences(block_text, min_chars=min_chars, max_chars=max_chars):
                if _is_noise(sentence):
                    processed.noise_removed += 1
                    continue
                key = normalize_for_matching(sentence)
                if key in seen:
                    processed.duplicates_removed += 1
                    continue
                seen.add(key)
                counter += 1
                processed.sentences.append(
                    CleanSentence(
                        id=f"s{counter:04d}",
                        text=sentence,
                        page=unit.page,
                        locator=unit.locator,
                        section=current_section,
                        unit_index=unit_index,
                    )
                )

    sections = sorted({s.section for s in processed.sentences})
    processed.sections = sections
    processed.keywords = _technical_keywords(processed.sentences)
    return processed


def _segment_by_heading(
    unit: PageUnit, aliases: dict[str, str]
) -> list[tuple[str | None, str]]:
    """Split a unit into (section, text) blocks at recognised headings."""
    lines = unit.text.splitlines()
    blocks: list[tuple[str | None, str]] = []
    current_section: str | None = None
    buf: list[str] = []

    for line in lines:
        if is_heading(line):
            canonical = _match_section(line, aliases)
            if canonical:
                if buf:
                    blocks.append((current_section, "\n".join(buf)))
                    buf = []
                current_section = canonical
        buf.append(line)

    if buf:
        blocks.append((current_section, "\n".join(buf)))
    return blocks


def summarize_text(text: str, limit: int = 500) -> str:
    return collapse_whitespace(text)[:limit]
