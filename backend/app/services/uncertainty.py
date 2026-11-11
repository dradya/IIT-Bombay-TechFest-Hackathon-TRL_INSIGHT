"""Uncertainty decomposition.

TRL INSIGHT never presents a single opaque "confidence" number. This module
separates the quantities that actually drive trust:

* **model probability** — the highest probability from the trained classifier
  (``None`` in rule-only mode).
* **confidence** — the hybrid predictor's calibrated-by-guardrail confidence.
* **coverage** — fraction of milestones up to the prediction confirmed by
  documented evidence.
* **completeness** — fraction of *all nine* milestones confirmed.
* **reliability** — a deterministic source-quality signal (page provenance,
  contradictions, duplicates, extraction warnings). It is **not** a
  probability.

The overall score is a transparent weighted combination of those real inputs.
It is explicitly **not calibrated**: no held-out calibration dataset ships with
the project, so ``calibrated`` stays ``False`` and the note says so.
"""
from __future__ import annotations

from typing import Any, Iterable

from app.config.framework import Framework
from app.ml.predictor import HybridPrediction
from app.ml.rules import RuleResult
from app.services.evidence import (
    STATUS_CONFIRMED,
    EvidenceRecord,
)

BAND_LOW = 0.45
BAND_HIGH = 0.70

_WEIGHTS = {
    "confidence": 0.40,
    "coverage": 0.25,
    "completeness": 0.20,
    "reliability": 0.15,
}


def _reliability(
    evidence: list[EvidenceRecord],
    rule_result: RuleResult,
    documents: list[dict[str, Any]] | None,
    contradictions_total: int,
    duplicates: int,
    extraction_warnings: Iterable[str] = (),
) -> tuple[float, list[str]]:
    """Deterministic source-quality score with an audit trail."""
    reasons: list[str] = []
    score = 0.55

    if evidence:
        paged = sum(1 for item in evidence if item.page_number is not None)
        paged_ratio = paged / len(evidence)
        score += 0.15 * paged_ratio
        if paged:
            reasons.append(
                f"{paged}/{len(evidence)} excerpts carry a page number."
            )
        else:
            reasons.append(
                "No excerpt carries a page number (page-less format or "
                "missing pagination); locators are used instead."
            )
    else:
        reasons.append("No evidence excerpts were extracted.")

    methods = {
        str(document.get("extraction_method") or "")
        for document in (documents or [])
    }
    if methods & {"docling", "pymupdf", "pdfplumber"}:
        score += 0.08
        reasons.append("Layout-aware extraction preserved document structure.")
    elif methods and methods <= {"text"}:
        score -= 0.02
        reasons.append("Plain-text extraction: no layout or table structure.")

    if documents and len(documents) > 1:
        score += 0.05
        reasons.append(f"{len(documents)} documents were cross-checked.")

    if contradictions_total:
        score -= min(0.30, 0.10 * contradictions_total)
        reasons.append(
            f"{contradictions_total} contradiction(s) require human resolution."
        )
    if duplicates:
        score -= min(0.10, 0.02 * duplicates)
        reasons.append(
            f"{duplicates} duplicate claim(s) were excluded from counting."
        )

    warnings = [w for w in extraction_warnings if w]
    if warnings:
        score -= min(0.10, 0.02 * len(warnings))

    if any(m.status == STATUS_CONFIRMED for m in rule_result.milestones) and not (
        rule_result.contradictions
    ):
        score += 0.05
    if rule_result.supported_level is None:
        score -= 0.10
        reasons.append("No milestone is confirmed by documented evidence.")

    return max(0.05, min(0.98, score)), reasons


def build_uncertainty(
    prediction: HybridPrediction,
    rule_result: RuleResult,
    evidence: list[EvidenceRecord],
    framework: Framework,
    *,
    documents: list[dict[str, Any]] | None = None,
    contradictions_total: int = 0,
    duplicates: int = 0,
    extraction_warnings: Iterable[str] = (),
) -> dict[str, Any]:
    confidence = max(0.0, min(1.0, float(prediction.confidence)))
    coverage = max(0.0, min(1.0, float(prediction.evidence_coverage)))

    total_milestones = len(framework.milestones) or 1
    confirmed_milestones = sum(
        1 for milestone in rule_result.milestones
        if milestone.status == STATUS_CONFIRMED
    )
    completeness = confirmed_milestones / total_milestones

    reliability, reliability_reasons = _reliability(
        evidence,
        rule_result,
        documents,
        contradictions_total,
        duplicates,
        extraction_warnings,
    )

    overall = (
        _WEIGHTS["confidence"] * confidence
        + _WEIGHTS["coverage"] * coverage
        + _WEIGHTS["completeness"] * completeness
        + _WEIGHTS["reliability"] * reliability
    )
    overall = max(0.0, min(1.0, overall))
    band = "high" if overall >= BAND_HIGH else "medium" if overall >= BAND_LOW else "low"

    model_probability = getattr(prediction, "ml_probability", None)
    components = {
        "confidence": round(confidence, 4),
        "coverage": round(coverage, 4),
        "completeness": round(completeness, 4),
        "reliability": round(reliability, 4),
        "model_probability": (
            round(float(model_probability), 4)
            if model_probability is not None
            else None
        ),
    }

    if confidence < BAND_LOW:
        driver = "limited or conflicting evidence lowers confidence"
    elif coverage < BAND_LOW:
        driver = "the milestone chain ahead of the prediction is not fully documented"
    elif reliability < BAND_LOW:
        driver = "source quality (provenance/duplicates/contradictions) lowers reliability"
    else:
        driver = "confidence, coverage, completeness and source quality agree"

    explanation = (
        f"Overall uncertainty signal {overall:.0%} ({band}). "
        f"Confidence {confidence:.0%}, evidence coverage {coverage:.0%}, "
        f"documentation completeness {completeness:.0%}, source reliability "
        f"{reliability:.0%}; {driver}. "
        + " ".join(reliability_reasons)
    )

    return {
        "model_probability": (
            round(float(model_probability), 4)
            if model_probability is not None
            else None
        ),
        "confidence": round(confidence, 4),
        "coverage": round(coverage, 4),
        "completeness": round(completeness, 4),
        "reliability": round(reliability, 4),
        "overall": round(overall, 4),
        "band": band,
        "calibrated": False,
        "calibration_source": None,
        "calibration_note": (
            "Not calibrated: no held-out calibration dataset is bundled. "
            "The overall score combines real confidence, coverage, "
            "completeness and source-quality signals; it is not a "
            "statistically calibrated probability."
        ),
        "components": components,
        "explanation": explanation,
    }
