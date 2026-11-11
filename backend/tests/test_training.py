"""Tests for the reproducible training pipeline:
dataset adapter -> prepare -> train -> evaluate -> CLI inference."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]


def run_script(args: list[str], timeout: int = 600) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, *args],
        cwd=str(BACKEND_DIR),
        capture_output=True,
        text=True,
        timeout=timeout,
        encoding="utf-8",
        errors="replace",
    )


# ----------------------------------------------------------------------
# Dataset adapter
# ----------------------------------------------------------------------
def test_adapter_parses_label_formats():
    from training.dataset_adapter import DatasetConfig, parse_label

    config = DatasetConfig()
    assert parse_label(5, config) == 5
    assert parse_label(5.0, config) == 5
    assert parse_label("5", config) == 5
    assert parse_label("TRL 7", config) == 7
    assert parse_label("trl-3", config) == 3
    assert parse_label("5/9", config) == 5
    assert parse_label("TRL 4 of 9", config) == 4
    assert parse_label("ready", config) is None
    assert parse_label(11, config) is None
    assert parse_label(None, config) is None


def test_adapter_reports_missing_column(tmp_path: Path):
    from training.dataset_adapter import DatasetConfig, load_dataset

    csv_path = tmp_path / "bad.csv"
    csv_path.write_text("foo,bar\n1,2\n", encoding="utf-8")
    with pytest.raises(ValueError) as exc:
        load_dataset(csv_path, DatasetConfig())
    assert "text" in str(exc.value)
    assert "dataset_adapter.yaml" in str(exc.value)


def test_adapter_validates_and_reports(tmp_path: Path):
    from training.dataset_adapter import DatasetConfig, load_dataset

    csv_path = tmp_path / "mini.csv"
    rows = ["id,text,trl"]
    rows.append('a,"' + ("principle study " * 20) + '",1')
    rows.append('b,"' + ("concept design " * 20) + '",TRL 3')
    rows.append('c,"' + ("another doc " * 20) + '",not-a-label')  # invalid label
    rows.append('d,"short",5')  # too short
    rows.append('e,"' + ("principle study " * 20) + '",1')  # exact duplicate of a
    csv_path.write_text("\n".join(rows), encoding="utf-8")

    frame, report = load_dataset(csv_path, DatasetConfig())
    assert report.total_rows == 5
    assert report.dropped_invalid_label == 1
    assert report.dropped_too_short == 1
    assert report.dropped_duplicate == 1
    assert report.kept_rows == 2
    assert set(frame["trl"]) == {1, 3}


def test_synthetic_generator_is_deterministic_and_labelled():
    from training.synthetic_data import generate_dataset

    first = generate_dataset(samples_per_class=2, seed=7)
    second = generate_dataset(samples_per_class=2, seed=7)
    assert len(first) == 18
    assert [r["id"] for r in first] == [r["id"] for r in second]
    assert [r["text"] for r in first] == [r["text"] for r in second]
    assert all(r["source"] == "SYNTHETIC_DEMO" for r in first)
    assert sorted({r["trl"] for r in first}) == list(range(1, 10))


# ----------------------------------------------------------------------
# End-to-end training pipeline (subprocess, isolated directories)
# ----------------------------------------------------------------------
@pytest.fixture(scope="module")
def trained(tmp_path_factory):
    """Prepare + train + evaluate a small model in a temp directory."""
    root = tmp_path_factory.mktemp("training_run")
    raw_dir = root / "raw"
    processed = root / "processed"
    models = root / "models"

    prep = run_script([
        "training/prepare_data.py", "--synthetic", "--samples", "12",
        "--raw-dir", str(raw_dir), "--out", str(processed), "--seed", "42",
    ])
    assert prep.returncode == 0, f"prepare_data failed:\n{prep.stdout}\n{prep.stderr}"
    assert (processed / "train.csv").is_file()
    assert (processed / "val.csv").is_file()
    assert (processed / "test.csv").is_file()
    stats = json.loads((processed / "dataset_stats.json").read_text(encoding="utf-8"))
    assert stats["dataset_type"] == "synthetic_demo"
    assert stats["synthetic"] is True
    assert "SYNTHETIC" in stats["disclaimer"].upper()

    train = run_script([
        "training/train_model.py", "--data", str(processed),
        "--models", str(models), "--model", "lr",
    ])
    assert train.returncode == 0, f"train_model failed:\n{train.stdout}\n{train.stderr}"
    assert (models / "trl_model.joblib").is_file()
    metadata = json.loads((models / "model_metadata.json").read_text(encoding="utf-8"))
    assert metadata["dataset_type"] == "synthetic_demo"
    assert metadata["labels"] == list(range(1, 10))

    evaluate = run_script([
        "training/evaluate_model.py", "--data", str(processed),
        "--models", str(models),
    ])
    assert evaluate.returncode == 0, f"evaluate failed:\n{evaluate.stdout}\n{evaluate.stderr}"
    metrics = json.loads((models / "metrics.json").read_text(encoding="utf-8"))
    return {"processed": processed, "models": models, "metrics": metrics,
            "metadata": metadata}


def test_training_pipeline_produces_model(trained):
    metrics = trained["metrics"]
    assert metrics["available"] is True
    assert metrics["mode"] == "demonstration", (
        "synthetic data must be reported as demonstration mode"
    )
    assert "NOT a competition" in metrics["note"] or "not a competition" in metrics["note"]
    assert set(metrics["metrics"]) == {"accuracy", "macro_f1", "weighted_f1"}
    for value in metrics["metrics"].values():
        assert 0.0 <= value <= 1.0


def test_evaluation_metrics_structure(trained):
    metrics = trained["metrics"]
    # per-class metrics for every class present in the test split
    assert metrics["per_class"], "per-class metrics must be present"
    for label, values in metrics["per_class"].items():
        assert label.isdigit()
        assert set(values) == {"precision", "recall", "f1", "support"}
        assert 0.0 <= values["precision"] <= 1.0
        assert 0.0 <= values["recall"] <= 1.0
        assert values["support"] >= 0

    # confusion matrix is square over the evaluated labels
    cm = metrics["confusion_matrix"]
    labels = cm["labels"]
    matrix = cm["matrix"]
    assert len(matrix) == len(labels)
    assert all(len(row) == len(labels) for row in matrix)

    # dataset class distribution present (never fabricated empty)
    assert metrics["class_distribution"]
    assert metrics["n_test"] > 0
    assert metrics["dataset_source"]


def test_model_bundle_loads_and_predicts(trained):
    from app.ml.predictor import load_model_bundle

    bundle = load_model_bundle(trained["models"])
    assert bundle is not None
    assert bundle.labels == list(range(1, 10))
    assert bundle.compatible(
        __import__("app.config.framework", fromlist=["get_framework"]).get_framework().version
    )

    # inference through the production predictor
    from app.config.framework import get_framework
    from app.ml.predictor import predict_hybrid
    from app.ml.rules import assess_rules
    from app.services.document_processing import clean_document
    from app.services.evidence import extract_evidence
    from app.services.ingestion import ExtractedDocument, PageUnit

    framework = get_framework()
    text = (
        "The underlying scientific principle was studied in this work. "
        "We propose a compact technology concept for water treatment. "
        "A proof-of-concept experiment was performed in the laboratory. "
        "Results show a measured flux of 18.4 L/m2h under test conditions."
    )
    extracted = ExtractedDocument(
        filename="t.txt", file_type="txt",
        units=[PageUnit(page=1, locator="page 1", text=text, chars=len(text))],
    )
    processed = clean_document(extracted, framework)
    evidence = extract_evidence(processed, framework, "t.txt").items
    rules = assess_rules(evidence, framework)
    prediction = predict_hybrid(processed, evidence, rules, framework, bundle)

    assert prediction.model_mode == "hybrid"
    assert prediction.ml_level is not None
    assert 1 <= prediction.predicted_trl <= 9
    assert abs(sum(p["probability"] for p in prediction.probabilities) - 1.0) < 0.02


def test_metrics_endpoint_reflects_trained_model(trained, monkeypatch):
    """The API must surface the real metrics file when present."""
    from app.api import meta as meta_module

    real_read = meta_module.read_performance
    monkeypatch.setattr(
        meta_module, "read_performance",
        lambda *a, **k: real_read(trained["models"]),
    )
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        body = client.get("/api/model/performance").json()
    assert body["available"] is True
    assert body["mode"] == "demonstration"
    assert body["metrics"]["accuracy"] >= 0.0
    assert body["confusion_matrix"]["matrix"]


# ----------------------------------------------------------------------
# CLI predictor
# ----------------------------------------------------------------------
def test_cli_predictor_on_text():
    proc = run_script([
        "training/predict.py",
        "--text",
        "The underlying scientific principle was studied in this work. "
        "We propose a compact technology concept for water treatment. "
        "A proof-of-concept experiment was performed in the laboratory. "
        "Results show a measured flux of 18.4 L/m2h under test conditions.",
        "--technology-name", "CLI Device",
    ])
    assert proc.returncode == 0, f"{proc.stdout}\n{proc.stderr}"
    assert "Predicted" in proc.stdout
    assert "TRL" in proc.stdout
    assert "Milestones" in proc.stdout


def test_cli_predictor_on_file(tmp_path: Path):
    from tests.conftest import make_pdf

    pdf_path = make_pdf(tmp_path / "cli.pdf")
    out_json = tmp_path / "out.json"
    proc = run_script([
        "training/predict.py", "--file", str(pdf_path),
        "--json", str(out_json), "--evidence", "3",
    ])
    assert proc.returncode == 0, f"{proc.stdout}\n{proc.stderr}"
    assert out_json.is_file()
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert 1 <= payload["prediction"]["predicted_trl"] <= 9
    assert payload["evidence"]
    # PDF evidence must carry real page numbers
    assert any(e["page_number"] is not None for e in payload["evidence"])


def test_cli_predictor_rejects_bad_file(tmp_path: Path):
    bad = tmp_path / "data.csv"
    bad.write_text("a,b\n1,2", encoding="utf-8")
    proc = run_script(["training/predict.py", "--file", str(bad)])
    assert proc.returncode == 1
    assert "error" in (proc.stdout + proc.stderr).lower()
