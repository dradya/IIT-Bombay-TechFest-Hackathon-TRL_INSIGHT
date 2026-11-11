"""STEP 4 - Feature engineering.

Two feature families are combined:

1. TF-IDF text features (word 1-2 grams) fitted on the training corpus
   only (no leakage - the vectorizer travels inside the saved model
   bundle and is never refitted at inference time).
2. Evidence/milestone features computed by the deterministic extraction
   pipeline: category counts by status, milestone indicators, negation and
   future-tense counts, evidence completeness.

The layout is versioned (``EVIDENCE_FEATURE_VERSION``) and stored with the
model so training and inference can never silently disagree.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np

from app.config.framework import Framework
from app.ml.rules import RuleResult
from app.services.evidence import (
    STATUS_CONFIRMED,
    STATUS_CONTRADICTED,
    STATUS_PROPOSED,
    STATUS_UNCLEAR,
    EvidenceRecord,
)

if TYPE_CHECKING:  # pragma: no cover
    from app.services.document_processing import ProcessedDocument

EVIDENCE_FEATURE_VERSION = 1

SCALAR_FEATURES = [
    "total_evidence",
    "confirmed_evidence",
    "confirmed_ratio",
    "milestone_coverage",
    "contradicted_evidence",
    "proposed_evidence",
    "unclear_evidence",
    "future_tense_ratio",
    "negated_ratio",
    "milestones_confirmed",
    "milestones_contradicted",
    "milestones_unclear",
    "milestones_not_found",
    "results_section_ratio",
    "defining_hits_total",
]


def feature_names(framework: Framework) -> list[str]:
    """Fixed feature layout - identical at training and inference time."""
    names: list[str] = []
    for cat in framework.categories:
        for status in (STATUS_CONFIRMED, STATUS_PROPOSED, STATUS_CONTRADICTED):
            names.append(f"cat::{cat['id']}::{status}")
    for ms in framework.milestones:
        for status in (STATUS_CONFIRMED, STATUS_PROPOSED, STATUS_CONTRADICTED, "not_found"):
            names.append(f"ms::{ms['id']}::{status}")
    names.extend(SCALAR_FEATURES)
    return names


def build_evidence_features(
    evidence: list[EvidenceRecord],
    rule_result: RuleResult,
    framework: Framework,
) -> np.ndarray:
    """Deterministic numeric feature vector from the evidence pipeline."""
    values: dict[str, float] = {}

    for cat in framework.categories:
        subset = [e for e in evidence if e.category == cat["id"]]
        values[f"cat::{cat['id']}::{STATUS_CONFIRMED}"] = sum(
            1 for e in subset if e.status == STATUS_CONFIRMED
        )
        values[f"cat::{cat['id']}::{STATUS_PROPOSED}"] = sum(
            1 for e in subset if e.status == STATUS_PROPOSED
        )
        values[f"cat::{cat['id']}::{STATUS_CONTRADICTED}"] = sum(
            1 for e in subset if e.status == STATUS_CONTRADICTED
        )

    for assessment in rule_result.milestones:
        values[f"ms::{assessment.id}::{STATUS_CONFIRMED}"] = float(
            assessment.status == STATUS_CONFIRMED
        )
        values[f"ms::{assessment.id}::{STATUS_PROPOSED}"] = float(
            assessment.status == STATUS_PROPOSED and assessment.supporting == 0
        )
        values[f"ms::{assessment.id}::{STATUS_CONTRADICTED}"] = float(
            assessment.status == STATUS_CONTRADICTED
        )
        values[f"ms::{assessment.id}::not_found"] = float(
            assessment.status == "not_found"
        )

    total = len(evidence)
    confirmed = sum(1 for e in evidence if e.status == STATUS_CONFIRMED)
    proposed = sum(1 for e in evidence if e.status == STATUS_PROPOSED)
    contradicted = sum(1 for e in evidence if e.status == STATUS_CONTRADICTED)
    unclear = sum(1 for e in evidence if e.status == STATUS_UNCLEAR)
    future = sum(1 for e in evidence if e.future_tense)
    negated = sum(1 for e in evidence if e.negated)
    results_sections = sum(1 for e in evidence if e.section == "results")

    milestones = rule_result.milestones
    n_ms = len(milestones) or 1

    scalars: dict[str, float] = {
        "total_evidence": total,
        "confirmed_evidence": confirmed,
        "confirmed_ratio": (confirmed / total) if total else 0.0,
        "milestone_coverage": (sum(1 for m in milestones if m.status == STATUS_CONFIRMED) / n_ms),
        "contradicted_evidence": contradicted,
        "proposed_evidence": proposed,
        "unclear_evidence": unclear,
        "future_tense_ratio": (future / total) if total else 0.0,
        "negated_ratio": (negated / total) if total else 0.0,
        "milestones_confirmed": sum(1 for m in milestones if m.status == STATUS_CONFIRMED),
        "milestones_contradicted": sum(
            1 for m in milestones if m.status == STATUS_CONTRADICTED
        ),
        "milestones_unclear": sum(1 for m in milestones if m.status == "unclear"),
        "milestones_not_found": sum(1 for m in milestones if m.status == "not_found"),
        "results_section_ratio": (results_sections / total) if total else 0.0,
        "defining_hits_total": float(sum(1 for e in evidence if e.supports_milestone)),
    }
    values.update(scalars)

    vector = np.array([values.get(name, 0.0) for name in feature_names(framework)],
                      dtype=np.float64)
    return vector


def combine_features(text_matrix: Any, evidence_matrix: np.ndarray) -> Any:
    """Horizontal-stack TF-IDF and evidence features.

    Accepts a single-row evidence vector (inference) or a 2-D batch
    (training). Works with sparse or dense text matrices.
    """
    ev = np.asarray(evidence_matrix, dtype=np.float64)
    if ev.ndim == 1:
        ev = ev.reshape(1, -1)
    try:
        from scipy import sparse  # type: ignore

        if hasattr(text_matrix, "tocsr"):
            rows = getattr(text_matrix, "shape", (0, 0))[0]
            if ev.shape[0] != rows:
                raise ValueError(
                    f"Row mismatch: text={rows} vs evidence={ev.shape[0]}"
                )
            ev_sparse = sparse.csr_matrix(ev)
            return sparse.hstack([text_matrix, ev_sparse], format="csr")
    except ImportError:  # pragma: no cover - scipy always ships with sklearn
        pass
    if hasattr(text_matrix, "toarray"):
        text_matrix = text_matrix.toarray()
    return np.hstack([np.asarray(text_matrix), ev])


def text_features(
    processed: "ProcessedDocument", vectorizer: Any
) -> Any:
    """TF-IDF features from the cleaned document text."""
    corpus = " ".join(s.text for s in processed.sentences)
    return vectorizer.transform([corpus])
