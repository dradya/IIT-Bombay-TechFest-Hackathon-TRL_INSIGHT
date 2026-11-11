"""train_model.py - reproducible nine-class TRL model training.

  python training/train_model.py                 # auto-select best candidate
  python training/train_model.py --model lr      # force logistic regression
  python training/train_model.py --model xgb     # force gradient boosting

Pipeline:
  1. load the prepared splits (training/prepare_data.py)
  2. featurise with the SAME cleaning/evidence code used in production
  3. fit TF-IDF on the training split only for candidate selection
     (the saved bundle's vectorizer is refit on train+val — the held-out
     test split is never seen)
  4. train candidate classifiers (LR baseline, XGBoost/LightGBM when data
     is sufficient), select by validation macro-F1
  5. retrain the winner on train+val and save the model bundle
     (models/trl_model.joblib) + model_metadata.json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402
from sklearn.feature_extraction.text import TfidfVectorizer  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.metrics import f1_score  # noqa: E402

from app.config.framework import get_framework  # noqa: E402
from app.ml.features import (  # noqa: E402
    EVIDENCE_FEATURE_VERSION,
    combine_features,
    feature_names,
)
from app.ml.predictor import METADATA_FILE, MODEL_FILE  # noqa: E402
from training.common import (  # noqa: E402
    MODELS_DIR,
    PROCESSED_DIR,
    evidence_matrix_for,
    load_yaml,
    save_json,
)

MODEL_VERSION = "1.0.0"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train the TRL classifier")
    parser.add_argument("--data", type=str, default=str(PROCESSED_DIR),
                        help="Directory containing train/val/test.csv")
    parser.add_argument("--models", type=str, default=str(MODELS_DIR),
                        help="Output directory for the model bundle")
    parser.add_argument("--model", type=str, default="auto",
                        choices=["auto", "lr", "xgb", "lgbm"],
                        help="Candidate to train (auto = select best on validation)")
    parser.add_argument("--config", type=str,
                        default=str(Path(__file__).resolve().parents[1]
                                    / "config" / "training.yaml"))
    parser.add_argument("--no-boost", action="store_true",
                        help="Skip boosting candidates (faster, fewer deps)")
    return parser.parse_args()


def _load_splits(data_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    train_path = data_dir / "train.csv"
    val_path = data_dir / "val.csv"
    if not train_path.is_file() or not val_path.is_file():
        raise FileNotFoundError(
            f"Missing splits in {data_dir}. Run first:\n"
            "  python training/prepare_data.py --synthetic"
        )
    train_df = pd.read_csv(train_path)
    val_df = pd.read_csv(val_path)
    for name, frame in (("train", train_df), ("val", val_df)):
        if "text" not in frame.columns or "trl" not in frame.columns:
            raise ValueError(f"{name}.csv must contain 'text' and 'trl' columns")
    return train_df, val_df


def _candidates(name: str, config: dict, n_samples: int, no_boost: bool):
    """Yield (key, builder) for each trainable candidate."""
    min_boost = int(config.get("models", {}).get("min_samples_for_boosting", 150))
    requested = config.get("models", {}).get("candidates", ["lr", "xgb"])

    def build_lr():
        cfg = dict(config.get("logistic_regression", {}))
        cfg.pop("n_jobs", None)
        return LogisticRegression(**cfg)

    yield "lr", build_lr

    # An explicit `--model xgb|lgbm` always trains that candidate, even when
    # the config's `models.candidates` list omits it or the dataset is small
    # (auto selection still respects both gates).
    explicit = name in ("xgb", "lgbm")

    if no_boost or name == "lr" or (not explicit and n_samples < min_boost):
        return

    if name in ("auto", "xgb") and (explicit or "xgb" in requested):
        try:
            import xgboost  # noqa: F401

            def build_xgb():
                from xgboost import XGBClassifier

                cfg = dict(config.get("xgboost", {}))
                cfg.setdefault("n_jobs", -1)
                return XGBClassifier(**cfg)

            yield "xgb", build_xgb
        except ImportError:
            print("[warn] xgboost not installed - skipping xgb candidate")

    if name in ("auto", "lgbm") and (explicit or "lgbm" in requested):
        try:
            import lightgbm  # noqa: F401

            def build_lgbm():
                from lightgbm import LGBMClassifier

                cfg = dict(config.get("lightgbm", {}))
                cfg.setdefault("n_jobs", -1)
                return LGBMClassifier(**cfg)

            yield "lgbm", build_lgbm
        except ImportError:
            print("[warn] lightgbm not installed - skipping lgbm candidate")


def main() -> int:
    args = parse_args()
    started = time.perf_counter()

    config = load_yaml(Path(args.config))
    data_dir = Path(args.data)
    models_dir = Path(args.models)
    models_dir.mkdir(parents=True, exist_ok=True)

    train_df, val_df = _load_splits(data_dir)
    print(f"[data] train={len(train_df)} val={len(val_df)}")

    stats_path = data_dir / "dataset_stats.json"
    dataset_type = "user_dataset"
    dataset_source = str(data_dir)
    if stats_path.is_file():
        stats = json.loads(stats_path.read_text(encoding="utf-8"))
        dataset_type = stats.get("dataset_type", "user_dataset")
        dataset_source = stats.get("source_path", str(data_dir))

    framework = get_framework()
    print("[features] featurising training documents (same pipeline as the API) ...")
    train_corpora, train_ev, _ = evidence_matrix_for(
        train_df["text"].astype(str).tolist(), framework
    )
    print("[features] featurising validation documents ...")
    val_corpora, val_ev, _ = evidence_matrix_for(
        val_df["text"].astype(str).tolist(), framework
    )

    tfidf_cfg = dict(config.get("tfidf", {}))
    ngram = tfidf_cfg.pop("ngram_range", [1, 2])
    tfidf_cfg["ngram_range"] = tuple(int(x) for x in ngram)
    vectorizer = TfidfVectorizer(**tfidf_cfg)
    print(f"[tfidf] fitting on {len(train_corpora)} training documents "
          f"(max_features={tfidf_cfg.get('max_features')}) ...")
    x_train_text = vectorizer.fit_transform(train_corpora)
    x_val_text = vectorizer.transform(val_corpora)

    x_train = combine_features(x_train_text, train_ev)
    x_val = combine_features(x_val_text, val_ev)
    y_train = train_df["trl"].astype(int).to_numpy() - 1
    y_val = val_df["trl"].astype(int).to_numpy() - 1

    print(f"[features] {x_train.shape[1]} features "
          f"(tfidf={x_train_text.shape[1]} + evidence={train_ev.shape[1]})")

    # ---- candidate training & validation ----------------------------
    results: list[dict] = []
    best_key, best_model, best_score = None, None, -1.0

    for key, builder in _candidates(args.model, config, len(train_df), args.no_boost):
        print(f"[train] candidate: {key} ...")
        try:
            model = builder()
            model.fit(x_train, y_train)
            preds = model.predict(x_val)
            score = float(f1_score(y_val, preds, average="macro"))
        except Exception as exc:  # noqa: BLE001 - a broken candidate must not kill training
            print(f"[warn] candidate {key} failed: {exc}")
            results.append({"model": key, "error": str(exc)})
            continue
        results.append({"model": key, "val_macro_f1": round(score, 4)})
        print(f"[train] {key}: validation macro-F1 = {score:.4f}")
        if score > best_score:
            best_key, best_model, best_score = key, model, score

    if best_model is None:
        print("[error] No candidate could be trained.")
        return 1

    print(f"[select] best candidate: {best_key} (val macro-F1={best_score:.4f})")

    # ---- final fit on train+val -------------------------------------
    print("[final] retraining the selected model on train+val ...")
    final_corpora, final_ev, _ = evidence_matrix_for(
        pd.concat([train_df, val_df])["text"].astype(str).tolist(), framework,
        progress=False,
    )
    final_vectorizer = TfidfVectorizer(**tfidf_cfg)
    x_final_text = final_vectorizer.fit_transform(final_corpora)
    x_final = combine_features(x_final_text, final_ev)
    y_final = pd.concat([train_df, val_df])["trl"].astype(int).to_numpy() - 1
    best_model.fit(x_final, y_final)

    trained_at = datetime.now(timezone.utc).isoformat()
    labels = [int(c) + 1 for c in sorted(best_model.classes_)]
    val_metrics = next(
        (r for r in results if r.get("model") == best_key and "val_macro_f1" in r),
        {"val_macro_f1": round(best_score, 4)},
    )

    bundle = {
        "vectorizer": final_vectorizer,
        "classifier": best_model,
        "labels": labels,
        "model_name": {
            "lr": "LogisticRegression+TFIDF",
            "xgb": "XGBoost+TFIDF",
            "lgbm": "LightGBM+TFIDF",
        }.get(best_key, best_key),
        "model_version": MODEL_VERSION,
        "trained_at": trained_at,
        "dataset_type": dataset_type,
        "dataset_source": dataset_source,
        "feature_version": EVIDENCE_FEATURE_VERSION,
        "framework_version": framework.version,
        "feature_names": feature_names(framework),
        "val_metrics": val_metrics,
        "training_config": config,
        "candidates": results,
        "trained_on": "train+val",
    }

    try:
        import joblib
    except ImportError:  # pragma: no cover
        print("[error] joblib is required (pip install joblib)")
        return 1

    model_path = models_dir / MODEL_FILE
    joblib.dump(bundle, model_path, compress=3)
    size_mb = model_path.stat().st_size / (1024 * 1024)

    metadata = {
        "model_name": bundle["model_name"],
        "model_version": MODEL_VERSION,
        "trained_at": trained_at,
        "dataset_type": dataset_type,
        "dataset_source": dataset_source,
        "framework_version": framework.version,
        "feature_version": EVIDENCE_FEATURE_VERSION,
        "n_train_final": int(len(y_final)),
        "n_train": int(len(train_df)),
        "n_val": int(len(val_df)),
        "selection_metric": "macro_f1",
        "selection_score": round(best_score, 4),
        "candidates": results,
        "trained_on": "train+val",
        "feature_count": int(x_final.shape[1]),
        "labels": labels,
        "note": (
            "SYNTHETIC demonstration dataset - functional testing only, "
            "not a competition benchmark."
            if dataset_type == "synthetic_demo"
            else "Trained on a user-provided labelled dataset."
        ),
    }
    save_json(metadata, models_dir / METADATA_FILE)

    elapsed = time.perf_counter() - started
    print(f"[done] model saved -> {model_path} ({size_mb:.2f} MB)")
    print(f"[done] metadata -> {models_dir / METADATA_FILE}")
    print(f"[done] elapsed {elapsed:.1f}s")
    print("[next] python training/evaluate_model.py  (writes models/metrics.json)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
