"""prepare_data.py - dataset loading, validation and splitting.

Two modes:

  # 1. SYNTHETIC DEMONSTRATION DATA (clearly labelled, local testing only)
  python training/prepare_data.py --synthetic --samples 540

  # 2. A REAL / OFFICIAL DATASET (column mapping via config file)
  python training/prepare_data.py --source data/raw/official_dataset.csv \
      --config config/dataset_adapter.yaml --dataset-type official

Outputs (backend/data/processed/):
  train.csv, val.csv, test.csv   - stratified splits
  dataset_stats.json             - class distributions + validation report
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402
from sklearn.model_selection import train_test_split  # noqa: E402

from training.common import (  # noqa: E402
    PROCESSED_DIR,
    RAW_DIR,
    load_yaml,
    save_json,
)
from training.dataset_adapter import (  # noqa: E402
    DEFAULT_CONFIG,
    DatasetConfig,
    load_dataset,
)

KEEP_COLUMNS = ["id", "text", "trl", "domain", "technology_name",
                "organization", "source"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare the TRL dataset for training")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--source", type=str, help="Path to a CSV/JSON/JSONL dataset")
    source.add_argument("--synthetic", action="store_true",
                        help="Generate the SYNTHETIC demonstration dataset")
    parser.add_argument("--config", type=str, default=str(DEFAULT_CONFIG),
                        help="Dataset adapter YAML (column mapping)")
    parser.add_argument("--out", type=str, default=str(PROCESSED_DIR),
                        help="Output directory for the splits")
    parser.add_argument("--raw-dir", type=str, default=str(RAW_DIR),
                        help="Directory for the generated raw synthetic CSV")
    parser.add_argument("--samples", type=int, default=60,
                        help="Synthetic: documents per TRL class (1-9)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--dataset-type", type=str, default=None,
                        choices=["synthetic_demo", "user_dataset", "official"],
                        help="Declare the dataset type (default: derived)")
    parser.add_argument("--force", action="store_true",
                        help="Overwrite existing synthetic raw file")
    return parser.parse_args()


def build_synthetic(samples: int, seed: int, force: bool, raw_dir: Path) -> tuple[Path, str]:
    from training.synthetic_data import generate_dataset

    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / "synthetic_demo_dataset.csv"
    if raw_path.exists() and not force:
        print(f"[synthetic] Reusing existing file: {raw_path}")
        return raw_path, "synthetic_demo"

    print(f"[synthetic] Generating {samples * 9} documents (seed={seed}) ...")
    records = generate_dataset(samples_per_class=samples, seed=seed)
    frame = pd.DataFrame(records)
    frame.to_csv(raw_path, index=False, encoding="utf-8")
    print(f"[synthetic] Wrote {len(frame)} rows -> {raw_path}")
    print("[synthetic] NOTE: this is SYNTHETIC demonstration data for local "
          "functional testing only - never a real-world benchmark.")
    return raw_path, "synthetic_demo"


def main() -> int:
    args = parse_args()

    if args.synthetic:
        raw_path, dataset_type = build_synthetic(
            args.samples, args.seed, args.force, Path(args.raw_dir)
        )
    else:
        raw_path = Path(args.source)
        dataset_type = args.dataset_type or "user_dataset"

    config = DatasetConfig.from_yaml(args.config)
    print(f"[load] {raw_path} (adapter: {Path(args.config).name})")
    frame, report = load_dataset(raw_path, config)

    if len(frame) == 0:
        print("[error] No valid rows after validation:")
        for issue in report.issues:
            print(f"        - {issue}")
        return 1

    print(f"[validate] kept {report.kept_rows}/{report.total_rows} rows")
    for issue in report.issues:
        print(f"           ! {issue}")
    print(f"[validate] class distribution: {report.label_counts}")

    missing = set(range(1, 10)) - {int(k) for k in report.label_counts}
    if missing:
        print(f"[warn] classes with no data: {sorted(missing)} - training will "
              "only be possible for the classes present.")

    # ---- stratified split (70/15/15 from training.yaml) --------------
    split_cfg = load_yaml(Path(__file__).resolve().parents[1] / "config" / "training.yaml")
    ratios = split_cfg.get("split", {})
    train_ratio = float(ratios.get("train", 0.70))
    val_ratio = float(ratios.get("val", 0.15))
    seed = int(ratios.get("seed", args.seed))
    test_ratio = 1.0 - train_ratio - val_ratio

    labels = frame["trl"].astype(int)
    # Guard: classes with a single sample cannot be stratified.
    counts = labels.value_counts()
    stratify = labels if counts.min() >= 2 else None
    if stratify is None:
        print("[warn] some classes have <2 samples; splitting without stratification.")

    train_df, temp_df = train_test_split(
        frame, test_size=(val_ratio + test_ratio), random_state=seed,
        stratify=stratify,
    )
    temp_labels = temp_df["trl"].astype(int)
    temp_counts = temp_labels.value_counts()
    stratify_temp = temp_labels if temp_counts.min() >= 2 else None
    relative_test = test_ratio / (val_ratio + test_ratio)
    val_df, test_df = train_test_split(
        temp_df, test_size=relative_test, random_state=seed,
        stratify=stratify_temp,
    )

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    columns = [c for c in KEEP_COLUMNS if c in frame.columns]
    for name, split in (("train", train_df), ("val", val_df), ("test", test_df)):
        split[columns].to_csv(out_dir / f"{name}.csv", index=False, encoding="utf-8")
        print(f"[split] {name}: {len(split)} rows")

    def distribution(split: pd.DataFrame) -> dict[str, int]:
        counts = split["trl"].astype(int).value_counts().sort_index()
        return {str(k): int(v) for k, v in counts.items()}

    stats = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dataset_type": dataset_type,
        "source_path": str(raw_path),
        "adapter_config": str(args.config),
        "seed": seed,
        "split_ratios": {"train": train_ratio, "val": val_ratio, "test": test_ratio},
        "total_rows": int(len(frame)),
        "class_distribution": distribution(frame),
        "splits": {
            "train": {"rows": int(len(train_df)), "class_distribution": distribution(train_df)},
            "val": {"rows": int(len(val_df)), "class_distribution": distribution(val_df)},
            "test": {"rows": int(len(test_df)), "class_distribution": distribution(test_df)},
        },
        "validation_report": report.to_dict(),
        "synthetic": dataset_type == "synthetic_demo",
        "disclaimer": (
            "SYNTHETIC demonstration dataset generated for local functional "
            "testing. Not real-world data and not a competition benchmark."
            if dataset_type == "synthetic_demo"
            else "User-provided dataset. Results reflect this dataset only."
        ),
    }
    save_json(stats, out_dir / "dataset_stats.json")
    print(f"[done] splits + dataset_stats.json written to {out_dir}")
    if dataset_type == "synthetic_demo":
        print("[reminder] dataset_type=synthetic_demo -> evaluation will be "
              "reported as DEMONSTRATION mode, never as competition accuracy.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
