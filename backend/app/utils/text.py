"""Text utilities: normalization, sentence splitting, heading detection.

Evidence excerpts must remain traceable to the original document, so all
matching is done on a lower-cased copy while excerpts themselves are only
whitespace-collapsed (never paraphrased).
"""
from __future__ import annotations

import re
import unicodedata

# Abbreviations that must not trigger a sentence break.
_ABBREVIATIONS = {
    "e.g", "i.e", "etc", "et al", "fig", "figs", "eq", "eqs", "vs", "cf",
    "dr", "mr", "mrs", "prof", "no", "vol", "pp", "ref", "refs", "ca",
    "approx", "min", "max", "sec", "ch", "dept", "est", "resp", "inc",
    "ltd", "st", "al", "appr", "fig.", "al.",
}

_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(\[])")


def normalize_for_matching(text: str) -> str:
    """Lower-cased, accent-folded copy used for pattern matching only."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.lower()


def collapse_whitespace(text: str) -> str:
    """Collapse whitespace for display while preserving wording exactly."""
    return re.sub(r"\s+", " ", text).strip()


def split_sentences(text: str, min_chars: int = 25, max_chars: int = 1200) -> list[str]:
    """Split text into sentences with abbreviation-aware boundaries."""
    if not text or not text.strip():
        return []
    # First split on paragraph / line boundaries (keeps bullets together).
    chunks = re.split(r"\n\s*\n|\r\n\s*\r\n", text)
    sentences: list[str] = []
    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue
        # Protect common abbreviations from the sentence splitter.
        protected = _protect_abbreviations(chunk)
        parts = _SENTENCE_RE.split(protected)
        for part in parts:
            part = part.replace("\x00", " ")
            part = collapse_whitespace(part)
            # Independent clauses separated by ';' often carry different
            # evidence statuses (e.g. "not yet tested; lab tests were run").
            if ";" in part and len(part) >= 2 * min_chars:
                pieces = [p.strip() for p in part.split(";") if len(p.strip()) >= min_chars]
                if len(pieces) > 1:
                    for piece in pieces:
                        if len(piece) >= min_chars:
                            sentences.append(piece)
                    continue
            if len(part) < min_chars:
                continue
            if len(part) > max_chars:
                # Hard-wrap very long sentences at clause boundaries.
                sub = re.split(r"(?<=[;:])\s+", part)
                buf = ""
                for s in sub:
                    if buf and len(buf) + len(s) > max_chars:
                        if len(buf) >= min_chars:
                            sentences.append(buf.strip())
                        buf = s
                    else:
                        buf = f"{buf} {s}".strip()
                if len(buf) >= min_chars:
                    sentences.append(buf.strip())
                continue
            sentences.append(part)
    return sentences


def _protect_abbreviations(text: str) -> str:
    def repl(match: re.Match) -> str:
        word = match.group(0).rstrip(".")
        if word.lower() in _ABBREVIATIONS:
            return word.lower() + "\x00"
        return match.group(0)

    return re.sub(r"\b[A-Za-z]{1,12}\.", repl, text)


def is_heading(line: str) -> bool:
    """Heuristic heading detector for line-oriented formats."""
    line = line.strip()
    if not line or len(line) > 90:
        return False
    if line.endswith((".", ",", ";", ":")):
        return False
    letters = [c for c in line if c.isalpha()]
    if len(letters) < 3:
        return False
    # Numbered section heading: "3.2   Thermal analysis"
    if re.match(r"^\d+(\.\d+)*\s+\S", line) and sum(c.isalpha() for c in line) > 3:
        return True
    # All caps or Title Case short line.
    if line.isupper() and 3 <= len(letters) <= 60:
        return True
    words = line.split()
    if 1 <= len(words) <= 10:
        titled = sum(1 for w in words if w[:1].isupper())
        if titled >= max(1, int(0.7 * len(words))) and not line.endswith("?"):
            return True
    return False


def strip_noise(text: str, patterns: list[str] | None = None) -> str:
    """Remove obvious non-content noise (URLs, emails) from matching text."""
    for pattern in patterns or [r"https?://\S+", r"\S+@\S+\.\S+"]:
        try:
            text = re.sub(pattern, " ", text)
        except re.error:  # pragma: no cover - defensive
            continue
    return text


def keyword_hits(text_lower: str, keywords: list[str]) -> tuple[int, list[str]]:
    """Return how many keywords occur in ``text_lower`` and which ones."""
    hits: list[str] = []
    for kw in keywords:
        kw_l = kw.lower()
        if not kw_l:
            continue
        if re.search(r"(?<![\w-])" + re.escape(kw_l) + r"(?![\w-])", text_lower):
            hits.append(kw)
    return len(hits), hits
