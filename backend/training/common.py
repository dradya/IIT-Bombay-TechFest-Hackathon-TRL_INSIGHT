"""Shared helpers for the training/inference scripts.

Makes ``backend/`` importable no matter where the script is launched
from, and provides the featurisation bridge so training uses EXACTLY the
same cleaning -> evidence -> feature code path as the live API
(no train/serve skew, no leakage: the TF-IDF vectorizer is fitted on the
training split only and travels inside the saved model bundle).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

DATA_DIR = BACKEND_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
MODELS_DIR = BACKEND_DIR / "models"
CONFIG_DIR = BACKEND_DIR / "config"

import yaml  # noqa: E402  (path set up above)


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"Configuration file not found: {path}")
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Configuration file must contain a mapping: {path}")
    return data


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def save_json(payload: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2, default=str)


def document_from_text(text: str, filename: str = "document.txt"):
    """Wrap raw text as a single-page extracted document.

    This lets training reuse the production cleaning/evidence pipeline
    unchanged (the API path additionally carries real page numbers).
    """
    from app.services.ingestion import ExtractedDocument, PageUnit

    return ExtractedDocument(
        filename=filename,
        file_type="txt",
        units=[PageUnit(page=1, locator="page 1", text=text, chars=len(text))],
        method="raw-text",
    )


def process_raw_text(text: str, framework: Any, filename: str = "document.txt"):
    """Return (processed, evidence, rule_result) for one raw document."""
    from app.ml.rules import assess_rules
    from app.services.document_processing import clean_document
    from app.services.evidence import extract_evidence

    extracted = document_from_text(text, filename)
    processed = clean_document(extracted, framework)
    evidence = extract_evidence(processed, framework, source_document=filename).items
    rules = assess_rules(evidence, framework)
    return processed, evidence, rules


def build_corpus(processed: Any) -> str:
    """Corpus string used for TF-IDF - identical at train and inference."""
    return " ".join(sentence.text for sentence in processed.sentences)


def evidence_matrix_for(
    texts: list[str], framework: Any, progress: bool = True
) -> tuple[list[str], Any, list[Any]]:
    """Compute TF-IDF corpora + evidence feature matrix for raw texts.

    Returns (corpora, evidence_features_ndarray, rule_results).
    """
    import numpy as np

    from app.ml.features import build_evidence_features

    corpora: list[str] = []
    rows: list[Any] = []
    rule_results: list[Any] = []
    total = len(texts)
    for index, text in enumerate(texts, start=1):
        processed, evidence, rules = process_raw_text(text, framework)
        corpora.append(build_corpus(processed))
        rows.append(build_evidence_features(evidence, rules, framework))
        rule_results.append(rules)
        if progress and (index % 100 == 0 or index == total):
            print(f"  featurised {index}/{total} documents", flush=True)
    matrix = np.vstack(rows) if rows else np.zeros((0, 0))
    return corpora, matrix, rule_results
