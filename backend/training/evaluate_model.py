"""evaluate_model.py - honest, reproducible model evaluation.

Computes metrics on the HELD-OUT test split and writes
``models/metrics.json`` consumed by GET /api/model/performance.

  python training/evaluate_model.py

Nothing is ever invented: if no model or no test split exists the script
exits with a clear message and no metrics file is written.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402
from sklearn.metrics import (  # noqa: E402
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_recall_fscore_support,
)

from app.config.framework import get_framework  # noqa: E402
from app.ml.predictor import METADATA_FILE, MODEL_FILE, load_model_bundle  # noqa: E402
from training.common import (  # noqa: E402
    MODELS_DIR,
    PROCESSED_DIR,
    evidence_matrix_for,
    save_json,
)

from app.ml.features import combine_features  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate the trained TRL model")
    parser.add_argument("--data", type=str, default=str(PROCESSED_DIR))
    parser.add_argument("--models", type=str, default=str(MODELS_DIR))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    data_dir = Path(args.data)
    models_dir = Path(args.models)

    test_path = data_dir / "test.csv"
    if not test_path.is_file():
        print(f"[error] Missing test split: {test_path}")
        print("        Run: python training/prepare_data.py --synthetic")
        return 1

    bundle = load_model_bundle(models_dir)
    if bundle is None:
        print(f"[error] No trained model found in {models_dir / MODEL_FILE}")
        print("        Run: python training/train_model.py")
        return 1

    metadata: dict = {}
    metadata_path = models_dir / METADATA_FILE
    if metadata_path.is_file():
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    test_df = pd.read_csv(test_path)
    if len(test_df) == 0:
        print("[error] Test split is empty - nothing to evaluate.")
        return 1

    print(f"[eval] model={bundle.model_name} v{bundle.model_version} "
          f"dataset_type={bundle.dataset_type}")
    print(f"[eval] test rows={len(test_df)}")

    framework = get_framework()
    corpora, ev_matrix, _ = evidence_matrix_for(
        test_df["text"].astype(str).tolist(), framework
    )
    x_text = bundle.vectorizer.transform(corpora)
    x_all = combine_features(x_text, ev_matrix)

    y_true = test_df["trl"].astype(int).to_numpy()
    proba = bundle.classifier.predict_proba(x_all)
    # Columns are aligned to sorted classifier classes_ (0-8 => TRL 1-9)
    classes = [int(c) + 1 for c in bundle.classifier.classes_]
    import numpy as np

    pred_idx = np.argmax(proba, axis=1)
    y_pred = np.array([classes[i] for i in pred_idx])

    labels = list(range(1, 10))
    present = sorted(set(y_true.tolist()) | set(y_pred.tolist()))
    eval_labels = [label for label in labels if label in present]

    precision, recall, f1, support = precision_recall_fscore_support(
        y_true, y_pred, labels=eval_labels, zero_division=0
    )
    per_class = {
        str(label): {
            "precision": round(float(precision[i]), 4),
            "recall": round(float(recall[i]), 4),
            "f1": round(float(f1[i]), 4),
            "support": int(support[i]),
        }
        for i, label in enumerate(eval_labels)
    }

    cm = confusion_matrix(y_true, y_pred, labels=eval_labels)
    report_dict = classification_report(
        y_true, y_pred, labels=eval_labels, zero_division=0, output_dict=True
    )

    accuracy = float(accuracy_score(y_true, y_pred))
    macro_f1 = float(f1_score(y_true, y_pred, average="macro", zero_division=0))
    weighted_f1 = float(f1_score(y_true, y_pred, average="weighted", zero_division=0))

    dataset_type = bundle.dataset_type or metadata.get("dataset_type", "user_dataset")
    is_synthetic = dataset_type == "synthetic_demo"

    stats_path = data_dir / "dataset_stats.json"
    class_distribution: dict[str, int] = {}
    full_distribution: dict[str, int] = {}
    if stats_path.is_file():
        stats = json.loads(stats_path.read_text(encoding="utf-8"))
        full_distribution = stats.get("class_distribution", {})
        split_stats = stats.get("splits", {}).get("test", {})
        class_distribution = split_stats.get("class_distribution", {})

    metrics = {
        "available": True,
        "mode": "demonstration" if is_synthetic else "trained_evaluation",
        "note": (
            "Metrics computed on a held-out test split of the SYNTHETIC "
            "demonstration dataset. They prove the pipeline works end to end; "
            "they are NOT a competition or real-world benchmark."
            if is_synthetic
            else "Metrics computed on a held-out test split of the "
                 "user-provided labelled dataset."
        ),
        "model_name": bundle.model_name,
        "model_version": bundle.model_version,
        "trained_at": bundle.trained_at,
        "dataset_type": dataset_type,
        "dataset_source": bundle.dataset_source or str(data_dir),
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "n_train": int(metadata.get("n_train_final") or metadata.get("n_train") or 0),
        "n_test": int(len(test_df)),
        "class_distribution": class_distribution or full_distribution,
        "test_class_distribution": class_distribution,
        "full_class_distribution": full_distribution,
        "metrics": {
            "accuracy": round(accuracy, 4),
            "macro_f1": round(macro_f1, 4),
            "weighted_f1": round(weighted_f1, 4),
        },
        "per_class": per_class,
        "confusion_matrix": {"labels": eval_labels, "matrix": cm.tolist()},
        "classification_report": report_dict,
    }

    out_path = models_dir / "metrics.json"
    save_json(metrics, out_path)

    print(f"[eval] accuracy={accuracy:.4f}  macro_f1={macro_f1:.4f}  "
          f"weighted_f1={weighted_f1:.4f}")
    print(f"[eval] per-class F1: " + ", ".join(
        f"TRL{l}={per_class[str(l)]['f1']:.2f}" for l in eval_labels
    ))
    print(f"[done] wrote {out_path}")
    print(f"[mode] {metrics['mode']} ({metrics['note'][:60]}...)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
