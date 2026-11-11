"""Model explanations (SHAP when available, exact linear attribution otherwise).

This explains the *classifier's* decision, not the document. Feature
attributions are returned in a separate object from source-backed evidence and
carry an explicit warning so the UI cannot present them as citations.

Attribution methods:

* **SHAP** — ``shap.LinearExplainer`` for linear classifiers and
  ``shap.TreeExplainer`` for tree ensembles, evaluated for the predicted class.
* **exact linear attribution** — ``coefficient × feature value`` for linear
  models when SHAP is unavailable or fails. Clearly labelled, not called SHAP.
* **unavailable** — no compatible model, so no explanation is fabricated.
"""
from __future__ import annotations

from typing import Any

import numpy as np

from app.config.framework import Framework
from app.core.config import settings
from app.core.logging import get_logger
from app.ml.features import (
    build_evidence_features,
    combine_features,
    feature_names,
    text_features,
)
from app.ml.predictor import ModelBundle
from app.ml.rules import RuleResult
from app.services.evidence import EvidenceRecord
from app.services.document_processing import ProcessedDocument

logger = get_logger("explain")

_SCALAR_LABELS = {
    "total_evidence": "Total evidence excerpts",
    "confirmed_evidence": "Confirmed evidence count",
    "confirmed_ratio": "Confirmed evidence ratio",
    "milestone_coverage": "Confirmed milestone coverage",
    "contradicted_evidence": "Contradicted evidence count",
    "proposed_evidence": "Proposed evidence count",
    "unclear_evidence": "Unclear evidence count",
    "future_tense_ratio": "Future-tense ratio",
    "negated_ratio": "Negated-statement ratio",
    "milestones_confirmed": "Milestones confirmed",
    "milestones_contradicted": "Milestones contradicted",
    "milestones_unclear": "Milestones unclear",
    "milestones_not_found": "Milestones not found",
    "results_section_ratio": "Results-section evidence ratio",
    "defining_hits_total": "Milestone-indicator hit count",
}


def _unavailable(note: str, warning: str | None = None) -> dict[str, Any]:
    return {
        "available": False,
        "method": "unavailable",
        "target_trl": None,
        "baseline": None,
        "prediction_probability": None,
        "features": [],
        "note": note,
        "warning": warning
        or (
            "Model feature attributions explain the classifier's decision. "
            "They are not source evidence and must not be cited as document "
            "support."
        ),
    }


def _all_feature_names(bundle: ModelBundle, framework: Framework) -> list[str]:
    try:
        text_names = [str(name) for name in bundle.vectorizer.get_feature_names_out()]
    except Exception:  # noqa: BLE001 - custom vectorizer
        text_names = []
    names = [f"text::{name}" for name in text_names]
    names.extend(f"ev::{name}" for name in feature_names(framework))
    return names


def _pretty(name: str, framework: Framework) -> tuple[str, str]:
    """Return (human label, kind) for one model feature."""
    if name.startswith("text::"):
        term = name[len("text::"):]
        return f"Text term: '{term}'", "text"
    raw = name[len("ev::"):] if name.startswith("ev::") else name
    if raw in _SCALAR_LABELS:
        return _SCALAR_LABELS[raw], "evidence"
    parts = raw.split("::")
    if len(parts) == 3 and parts[0] == "ms":
        milestone = framework.milestone(parts[1])
        label = milestone.get("label", parts[1])
        return f"Milestone '{label}': {parts[2].replace('_', ' ')}", "evidence"
    if len(parts) == 3 and parts[0] == "cat":
        category = framework.category(parts[1])
        label = category.get("label", parts[1])
        return f"Category '{label}': {parts[2].replace('_', ' ')}", "evidence"
    return raw.replace("::", " · "), "evidence"


def _matrix_rows(features: Any) -> np.ndarray:
    if hasattr(features, "toarray"):
        features = features.toarray()
    matrix = np.asarray(features, dtype=np.float64)
    if matrix.ndim == 1:
        matrix = matrix.reshape(1, -1)
    return matrix


def _class_index(classifier: Any, labels: list[int], predicted_trl: int) -> int:
    classes: list[int] = []
    raw = getattr(classifier, "classes_", None)
    if raw is not None:
        try:
            classes = [int(value) for value in list(raw)]
        except (TypeError, ValueError):
            classes = []
    if not classes:
        classes = [int(value) for value in labels]
    if predicted_trl in classes:
        return classes.index(predicted_trl)
    return 0


def _shap_values(
    classifier: Any, matrix: np.ndarray, class_index: int
) -> tuple[np.ndarray, float] | None:
    """Real SHAP values for the predicted class, or ``None``."""
    try:
        import shap  # type: ignore
    except Exception:  # noqa: BLE001 - optional dependency
        return None

    try:
        if hasattr(classifier, "coef_"):
            background = np.zeros((1, matrix.shape[1]), dtype=np.float64)
            explainer = shap.LinearExplainer(classifier, background)
        else:
            explainer = shap.TreeExplainer(classifier)

        values = explainer.shap_values(matrix)
        expected = explainer.expected_value

        if isinstance(values, list):  # multiclass linear / tree list form
            class_values = values[class_index]
            baseline = expected[class_index] if np.ndim(expected) else expected
        else:
            array = np.asarray(values, dtype=np.float64)
            if array.ndim == 3:  # (samples, features, classes)
                class_values = array[0, :, class_index]
                baseline = (
                    float(np.asarray(expected).reshape(-1)[class_index])
                    if np.ndim(expected)
                    else float(expected)
                )
            else:
                class_values = array[0] if array.ndim == 2 else array
                baseline = (
                    float(np.asarray(expected).reshape(-1)[0])
                    if np.ndim(expected)
                    else float(expected)
                )
        class_values = np.asarray(class_values, dtype=np.float64).reshape(-1)
        return class_values, float(baseline)
    except Exception as exc:  # noqa: BLE001 - never break an assessment
        logger.info("SHAP explanation failed (%s); using linear fallback", exc)
        return None


def _linear_values(
    classifier: Any, matrix: np.ndarray, class_index: int
) -> tuple[np.ndarray, float] | None:
    coefficients = getattr(classifier, "coef_", None)
    if coefficients is None:
        return None
    coefficients = np.asarray(coefficients, dtype=np.float64)
    if coefficients.ndim == 1:
        row = coefficients
    else:
        if class_index >= coefficients.shape[0]:
            return None
        row = coefficients[class_index]
    intercept = getattr(classifier, "intercept_", 0.0)
    intercept = np.asarray(intercept, dtype=np.float64).reshape(-1)
    baseline = float(intercept[class_index]) if class_index < intercept.size else 0.0
    return row * matrix[0], baseline


def explain_prediction(
    bundle: ModelBundle | None,
    processed: ProcessedDocument,
    evidence: list[EvidenceRecord],
    rule_result: RuleResult,
    framework: Framework,
    predicted_trl: int,
    model_probability: float | None = None,
) -> dict[str, Any]:
    if bundle is None:
        return _unavailable(
            "No trained model is loaded, so there is no model decision to "
            "explain. The rule-based assessment is shown instead."
        )
    if not bundle.compatible(framework.version):
        return _unavailable(
            "The trained model was built with a different framework/feature "
            "version and was not used for this assessment, so no model "
            "explanation is available."
        )

    try:
        text_vec = text_features(processed, bundle.vectorizer)
        ev_vec = build_evidence_features(evidence, rule_result, framework)
        features = combine_features(text_vec, ev_vec)
        matrix = _matrix_rows(features)
        probability = None
        try:
            proba = np.asarray(bundle.classifier.predict_proba(features))[0]
            probability = float(np.max(proba))
        except Exception:  # noqa: BLE001 - probabilities are optional
            probability = model_probability
    except Exception as exc:  # noqa: BLE001 - never break an assessment
        logger.error("Could not rebuild model features for explanation: %s", exc)
        return _unavailable(f"Model features could not be rebuilt: {exc}")

    labels = [int(value) for value in bundle.labels]
    class_index = _class_index(bundle.classifier, labels, predicted_trl)

    method = ""
    values: np.ndarray | None = None
    baseline: float | None = None

    if settings.SHAP_ENABLED:
        shaped = _shap_values(bundle.classifier, matrix, class_index)
        if shaped is not None:
            values, baseline = shaped
            method = "shap"

    if values is None:
        linear = _linear_values(bundle.classifier, matrix, class_index)
        if linear is not None:
            values, baseline = linear
            method = "linear_coefficients"

    if values is None:
        return _unavailable(
            "The installed classifier type has no supported exact attribution "
            "and SHAP is unavailable, so no model explanation is reported."
        )

    names = _all_feature_names(bundle, framework)
    if len(names) != matrix.shape[1]:
        names = [
            f"feature_{index}" for index in range(matrix.shape[1])
        ]

    row = matrix[0]
    contributions: list[dict[str, Any]] = []
    for index, contribution in enumerate(values):
        value = float(row[index])
        contribution = float(contribution)
        if abs(contribution) < 1e-9 and abs(value) < 1e-12:
            continue
        label, kind = _pretty(names[index], framework)
        contributions.append(
            {
                "feature": names[index],
                "label": label,
                "value": round(value, 6),
                "contribution": round(contribution, 6),
                "direction": (
                    "supports"
                    if contribution > 0
                    else "opposes"
                    if contribution < 0
                    else "neutral"
                ),
                "kind": kind,
                "_abs": abs(contribution),
            }
        )

    contributions.sort(key=lambda item: -item["_abs"])
    top = contributions[:12]
    for item in top:
        item.pop("_abs", None)

    if method == "shap":
        note = (
            f"SHAP values for the predicted class (TRL {predicted_trl}) from "
            f"the actual {bundle.model_name} classifier. Positive contributions "
            "push the model toward this level, negative contributions away "
            "from it."
        )
    else:
        note = (
            f"Exact linear attribution for the predicted class (TRL "
            f"{predicted_trl}): coefficient × feature value from the actual "
            f"{bundle.model_name} classifier. SHAP was unavailable or "
            "inapplicable, so these are not SHAP values."
        )

    return {
        "available": True,
        "method": method,
        "target_trl": predicted_trl,
        "baseline": round(float(baseline or 0.0), 6),
        "prediction_probability": (
            round(float(probability), 4) if probability is not None else None
        ),
        "features": top,
        "note": note,
        "warning": (
            "Model feature attributions explain the classifier's decision. "
            "They are not source evidence and must not be cited as document "
            "support."
        ),
    }
