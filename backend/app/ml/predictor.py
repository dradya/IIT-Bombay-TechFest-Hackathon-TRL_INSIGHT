"""STEP 5 - Hybrid TRL classification.

Combines
  1. the ML classifier (TF-IDF + evidence features, calibrated
     probabilities) - when a trained model bundle exists,
  2. the structured milestone evidence, and
  3. the configurable rule-based prior,

into a single nine-class prediction with a confidence score, a full
probability distribution, alternative plausible levels and explicit
warnings when the evidence does not support the claim.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger
from app.ml.features import (
    EVIDENCE_FEATURE_VERSION,
    build_evidence_features,
    combine_features,
    text_features,
)
from app.ml.rules import RuleResult
from app.services.document_processing import ProcessedDocument
from app.services.evidence import EvidenceRecord

logger = get_logger("predictor")

MODEL_FILE = "trl_model.joblib"
METADATA_FILE = "model_metadata.json"
PERFORMANCE_FILE = "metrics.json"


@dataclass
class ModelBundle:
    vectorizer: Any
    classifier: Any
    labels: list[int]
    model_name: str = "unknown"
    model_version: str = "0"
    trained_at: str | None = None
    dataset_type: str = "unknown"
    dataset_source: str | None = None
    feature_version: int = 0
    framework_version: str = ""
    feature_names: list[str] = field(default_factory=list)
    val_metrics: dict[str, Any] = field(default_factory=dict)
    path: str = ""

    def compatible(self, framework_version: str) -> bool:
        return (
            self.feature_version == EVIDENCE_FEATURE_VERSION
            and self.framework_version == framework_version
        )


def _load_bundle(path: Path) -> ModelBundle | None:
    try:
        import joblib  # type: ignore
    except ImportError:  # pragma: no cover - joblib ships with sklearn
        logger.warning("joblib unavailable; cannot load model bundle")
        return None
    try:
        payload = joblib.load(path)
    except Exception as exc:  # noqa: BLE001 - corrupt/unsupported bundle
        logger.error("Failed to load model bundle %s: %s", path, exc)
        return None
    if not isinstance(payload, dict) or "vectorizer" not in payload:
        logger.error("Model bundle %s has an unexpected format", path)
        return None
    return ModelBundle(
        vectorizer=payload["vectorizer"],
        classifier=payload["classifier"],
        labels=[int(x) for x in payload.get("labels", list(range(1, 10)))],
        model_name=payload.get("model_name", "unknown"),
        model_version=payload.get("model_version", "0"),
        trained_at=payload.get("trained_at"),
        dataset_type=payload.get("dataset_type", "unknown"),
        dataset_source=payload.get("dataset_source"),
        feature_version=int(payload.get("feature_version", 0)),
        framework_version=payload.get("framework_version", ""),
        feature_names=list(payload.get("feature_names", [])),
        val_metrics=dict(payload.get("val_metrics", {})),
        path=str(path),
    )


@lru_cache(maxsize=4)
def _load_cached(path_str: str, mtime: float) -> ModelBundle | None:
    return _load_bundle(Path(path_str))


def load_model_bundle(models_dir: Path | None = None) -> ModelBundle | None:
    """Load the trained model bundle if one exists (mtime-cached)."""
    models_dir = models_dir or settings.MODELS_DIR
    path = models_dir / MODEL_FILE
    if not path.is_file():
        return None
    try:
        mtime = path.stat().st_mtime
    except OSError:  # pragma: no cover - defensive
        return None
    return _load_cached(str(path), mtime)


def model_available(models_dir: Path | None = None) -> bool:
    path = (models_dir or settings.MODELS_DIR) / MODEL_FILE
    return path.is_file()


def read_performance(models_dir: Path | None = None) -> dict[str, Any] | None:
    path = (models_dir or settings.MODELS_DIR) / PERFORMANCE_FILE
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:  # pragma: no cover
        logger.error("Could not read metrics file: %s", exc)
        return None


def read_model_metadata(models_dir: Path | None = None) -> dict[str, Any] | None:
    path = (models_dir or settings.MODELS_DIR) / METADATA_FILE
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):  # pragma: no cover
        return None


# ----------------------------------------------------------------------
# Prediction
# ----------------------------------------------------------------------
@dataclass
class HybridPrediction:
    predicted_trl: int
    probabilities: list[dict[str, float]]
    confidence: float
    low_confidence: bool
    evidence_coverage: float
    rule_level: int | None
    ml_level: int | None
    model_mode: str
    alternatives: list[dict[str, Any]]
    warnings: list[str]
    method: str
    ml_probability: float | None = None


def _ml_probabilities(
    bundle: ModelBundle,
    processed: ProcessedDocument,
    evidence: list[EvidenceRecord],
    rule_result: RuleResult,
    framework: Any,
) -> list[float] | None:
    """Return a 9-length probability vector aligned to labels 1..9."""
    try:
        text_vec = text_features(processed, bundle.vectorizer)
        ev_vec = build_evidence_features(evidence, rule_result, framework)
        features = combine_features(text_vec, ev_vec)
        proba = bundle.classifier.predict_proba(features)[0]
    except Exception as exc:  # noqa: BLE001 - never break the API on ML errors
        logger.error("ML inference failed (%s); falling back to rules", exc)
        return None

    labels = bundle.labels
    aligned = [0.0] * 9
    for index, label in enumerate(labels):
        if 1 <= int(label) <= 9:
            aligned[int(label) - 1] = float(proba[index])
    total = sum(aligned)
    if total <= 0:  # pragma: no cover - defensive
        return None
    return [value / total for value in aligned]


def predict_hybrid(
    processed: ProcessedDocument,
    evidence: list[EvidenceRecord],
    rule_result: RuleResult,
    framework: Any,
    bundle: ModelBundle | None = None,
) -> HybridPrediction:
    """Combine ML, milestone evidence and rules into the final prediction."""
    rules = framework.rules
    ml_weight = float(rules.get("ml_weight", 0.55))
    rule_weight = float(rules.get("rule_weight", 0.45))
    low_threshold = float(rules.get("low_confidence_threshold", 0.45))
    min_coverage = float(rules.get("min_evidence_coverage", 0.20))
    alt_threshold = float(rules.get("alternative_prob_threshold", 0.12))
    alt_near = float(rules.get("alternative_near_threshold", 0.08))
    alt_max = int(rules.get("alternative_max", 3))
    max_above = int(rules.get("max_levels_above_confirmed", 2))
    disagreement_penalty = float(rules.get("disagreement_penalty", 0.85))

    warnings: list[str] = []
    bundle_ok = bundle is not None and bundle.compatible(framework.version)
    if bundle is not None and not bundle_ok:
        warnings.append(
            "The trained model was built with a different framework/feature "
            "version and was not used; the rule-based assessment was applied instead."
        )
        bundle = None

    # ---- 1. ML probabilities ---------------------------------------
    ml_probs: list[float] | None = None
    ml_level: int | None = None
    if bundle_ok and bundle is not None:
        ml_probs = _ml_probabilities(bundle, processed, evidence, rule_result, framework)
        if ml_probs is not None:
            ml_level = max(range(9), key=lambda i: ml_probs[i]) + 1
        else:
            warnings.append("The trained model failed at inference; rules were used instead.")
            bundle = None
    if bundle is None:
        warnings.append(
            "No compatible trained model is available - this assessment uses the "
            "evidence/rule engine only (demonstration mode)."
        )

    # ---- 2. Rule prior ------------------------------------------------
    rule_dist = [rule_result.rule_distribution.get(level, 0.0) for level in range(1, 10)]
    rule_level = rule_result.supported_level

    # ---- 3. Hybrid combination ---------------------------------------
    if ml_probs is not None:
        hybrid = [
            ml_weight * ml + rule_weight * rule
            for ml, rule in zip(ml_probs, rule_dist, strict=True)
        ]
        mode = "hybrid"
        method = (
            f"Hybrid: {bundle.model_name if bundle else 'ML'} "
            f"(TF-IDF + evidence features, weight {ml_weight:.2f}) + milestone rules "
            f"(weight {rule_weight:.2f})"
        )
    else:
        hybrid = list(rule_dist)
        mode = "rule_only"
        method = (
            "Rule engine only: milestone evidence status + configurable TRL "
            "assessment rules (no trained model used)"
        )

    # ---- 3b. Contradiction demotion ---------------------------------
    # A level whose milestone the document explicitly says has NOT been
    # achieved is strongly demoted in the final distribution (an explicit
    # contradiction outweighs both the ML guess and the prior).
    contradiction_penalty = float(rules.get("contradiction_penalty", 0.25))
    milestone_status = {m.trl: m.status for m in rule_result.milestones}
    for index, level in enumerate(range(1, 10)):
        if milestone_status.get(level) == "contradicted":
            hybrid[index] *= contradiction_penalty

    total = sum(hybrid) or 1.0
    hybrid = [value / total for value in hybrid]
    predicted = max(range(9), key=lambda i: hybrid[i]) + 1

    # ---- 4. Evidence coverage ----------------------------------------
    up_to = [m for m in rule_result.milestones if m.trl <= predicted]
    confirmed_up_to = sum(1 for m in up_to if m.status == "confirmed")
    coverage = (confirmed_up_to / len(up_to)) if up_to else 0.0

    # ---- 5. Confidence ------------------------------------------------
    if ml_probs is not None:
        ml_conf = max(ml_probs)
        if rule_level:
            rule_conf = (
                0.35
                + 0.45 * rule_result.coverage_up_to_supported
                + 0.20 * (1.0 if not rule_result.contradictions else 0.5)
            )
        else:
            rule_conf = 0.15 + 0.05 * min(len(evidence), 4)
        base = 0.55 * ml_conf + 0.45 * rule_conf
    else:
        if rule_level:
            base = 0.85 * (
                0.45
                + 0.40 * rule_result.coverage_up_to_supported
                + 0.15 * (1.0 if not rule_result.contradictions else 0.5)
            )
        else:
            base = 0.85 * (0.18 + 0.05 * min(len(evidence), 4))

    confidence = base * (0.55 + 0.45 * coverage)
    if ml_level is not None and rule_level is not None and ml_level != rule_level:
        confidence *= disagreement_penalty
    confidence = max(0.05, min(0.98, confidence))

    # ---- 6. Guardrails & warnings ------------------------------------
    reference = rule_level or 0
    if predicted > reference + max_above:
        warnings.append(
            f"Predicted TRL {predicted} exceeds the highest evidence-confirmed "
            f"milestone (TRL {reference or 'none'}) by more than {max_above} level(s): "
            "the claim is not fully supported by documented evidence."
        )
        confidence = min(confidence, low_threshold - 0.02)

    # Evidence-backing guardrail: a prediction whose OWN milestone is not
    # confirmed by documented evidence is never presented as certain.
    predicted_ms = next(
        (m for m in rule_result.milestones if m.trl == predicted), None
    )
    if predicted_ms is not None and predicted_ms.status != "confirmed":
        confidence = min(confidence, low_threshold - 0.01)
        if predicted_ms.status == "not_found":
            warnings.append(
                f"No direct evidence was found for the TRL {predicted} milestone "
                f"'{predicted_ms.label}'; confidence was capped accordingly."
            )
        elif predicted_ms.status == "contradicted":
            warnings.append(
                f"The TRL {predicted} milestone '{predicted_ms.label}' is explicitly "
                "contradicted by the document; confidence was capped accordingly."
            )
        else:
            warnings.append(
                f"Evidence for the TRL {predicted} milestone "
                f"'{predicted_ms.label}' is unclear, conflicting or only planned; "
                "confidence was capped accordingly."
            )

    low_confidence = bool(
        confidence < low_threshold
        or coverage < min_coverage
        or (rule_level is None and predicted >= 5)
    )
    if low_confidence and confidence >= low_threshold:
        warnings.append(
            f"Evidence coverage ({coverage:.0%}) is below the required "
            f"threshold ({min_coverage:.0%}); treat this prediction as uncertain."
        )
    warnings.extend(rule_result.warnings)

    # ---- 7. Alternatives ---------------------------------------------
    alternatives: list[dict[str, Any]] = []
    ranked = sorted(range(9), key=lambda i: -hybrid[i])
    for index in ranked:
        level = index + 1
        if level == predicted:
            continue
        probability = hybrid[index]
        near = abs(level - predicted) <= 1
        if probability >= alt_threshold or (near and probability >= alt_near):
            reason = []
            if level == rule_level:
                reason.append("milestone evidence supports this level")
            if ml_level == level:
                reason.append("ML classifier favoured this level")
            if near:
                reason.append("adjacent level with non-trivial probability")
            alternatives.append(
                {
                    "level": level,
                    "probability": round(probability, 4),
                    "reason": "; ".join(reason) or "non-trivial probability mass",
                }
            )
        if len(alternatives) >= alt_max:
            break

    return HybridPrediction(
        predicted_trl=predicted,
        probabilities=[
            {"level": level, "probability": round(hybrid[level - 1], 4)}
            for level in range(1, 10)
        ],
        confidence=round(confidence, 3),
        low_confidence=low_confidence,
        evidence_coverage=round(coverage, 3),
        rule_level=rule_level,
        ml_level=ml_level,
        model_mode=mode,
        alternatives=alternatives,
        warnings=list(dict.fromkeys(warnings)),
        method=method,
        ml_probability=(round(max(ml_probs), 4) if ml_probs is not None else None),
    )
