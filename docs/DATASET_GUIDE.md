# TRL INSIGHT — Dataset Guide

How to prepare data, plug in the **official competition dataset**, and understand the honesty labels attached to every metric.

## 1. Data contract

The trainer consumes a table (CSV / TSV / JSON / JSONL / Parquet — Parquet additionally needs `pyarrow`) with at least:

| Column | Type | Required | Meaning |
|---|---|---|---|
| *(text column)* | string | ✅ | full document text |
| *(label column)* | int/str | ✅ | TRL label 1–9 |
| `id` | string | – | row id (generated if absent) |
| `domain`, `organization`, `technology_name` | string | – | metadata kept through the split |

Label formats accepted out of the box (first matching pattern wins):

```
5      "5"     5.0     "TRL 7"    "trl-3"    "5/9"    "TRL 4 of 9"    "# 6"
```

## 2. The dataset adapter (`backend/config/dataset_adapter.yaml`)

The adapter is **configuration, not code** — this is the only file you edit to integrate a new dataset:

```yaml
text_column: text            # ← your document-text column
label_column: trl            # ← your label column
id_column: id
domain_column: domain
organization_column: organization
technology_column: technology_name

label_patterns:              # tried in order; group 1 must be 1-9
  - '^\s*(?:trl)?[\s_#-]*([1-9])\s*(?:/\s*9|of\s*9)?\s*$'
  - '^\s*trl[\s_-]*([1-9])\b'
  - '\b([1-9])\s*/\s*9\b'
  - '\b([1-9])\b'
allowed_labels: [1, 2, 3, 4, 5, 6, 7, 8, 9]

min_text_chars: 120           # shorter rows dropped (reported)
max_text_chars: 200000        # longer rows truncated (reported)
deduplicate: true
drop_invalid_labels: true
filters: {}                   # e.g. {split: train} to keep one split
```

Example — official file with columns `document` and `trl_label`:

```yaml
text_column: document
label_column: trl_label
```

## 3. Training on your dataset

```bat
:: Windows
scripts\train.bat --source data\raw\official_dataset.csv --dataset-type official
```

```bash
# Linux / macOS
./scripts/train.sh --source data/raw/official_dataset.csv --dataset-type official
```

Equivalent manual steps:

```bash
cd backend
python training/prepare_data.py --source data/raw/official_dataset.csv \
        --config config/dataset_adapter.yaml --dataset-type official
python training/train_model.py
python training/evaluate_model.py
```

`prepare_data.py` prints a **validation report** (kept/dropped rows, per-class counts, warnings about missing classes) and writes:

```
backend/data/processed/
├── train.csv  val.csv  test.csv    stratified 70/15/15 (seed 42)
└── dataset_stats.json              provenance + class distributions + disclaimer
```

Then `train_model.py` writes `models/trl_model.joblib` + `model_metadata.json`, and `evaluate_model.py` writes `models/metrics.json`, which the API exposes at `GET /api/model/performance`.

## 4. Dataset types & honesty labels

| `--dataset-type` | `metrics.mode` | Shown in UI as |
|---|---|---|
| `synthetic_demo` | `demonstration` | amber badge: *"Demonstration data — not a competition benchmark"* |
| `official` | `trained_evaluation` | normal metrics view |
| `user_dataset` | `trained_evaluation` | normal metrics view |

Rules the system follows:

* **No fabricated metrics** — if `metrics.json` doesn't exist, the API returns `available: false` with instructions instead of numbers.
* **No claimed access** — the project never states or implies access to private/official competition data; the adapter is the integration point for data *you* supply.
* **Provenance everywhere** — model metadata records dataset type, source path, split sizes, selection score, candidates and timestamps; the PDF report prints them.

## 5. The synthetic demonstration dataset

Purpose: let anyone run the full pipeline (train → evaluate → serve) with zero external data.

```bash
python training/prepare_data.py --synthetic --samples 60   # 60 × 9 = 540 docs
```

Generator properties (`training/synthetic_data.py`):

* 8 technology domains × 9 TRL bands; documents assembled from band templates with realistic sections.
* Low-TRL documents contain higher-band activities **only as planned/future or negated statements** — teaching the model that future intent ≠ completion.
* Every row tagged `source = SYNTHETIC_DEMO`; deterministic for a fixed seed (tested).
* Distractors (background, limitations) included so keyword counting alone is insufficient.

**Known limitation (by design):** templates are separable, so test scores are ~1.0. That is why they are labelled `demonstration` and never presented as a benchmark.

## 6. Quality checklist for a real dataset

- [ ] Every row's label reflects the *documented* readiness of the technology in that text (annotator guideline: evidence-based, not aspirational).
- [ ] Class balance checked (`dataset_stats.json → class_distribution`); very rare classes (< 2 rows) can't be stratified — the script warns.
- [ ] Text column contains the actual report content (not titles/abstracts only).
- [ ] Duplicate/near-duplicate documents removed (`deduplicate` handles exact copies only).
- [ ] Train/val/test splits are **by document**, never by sentence, to avoid leakage (default behaviour).
- [ ] For benchmark reporting, quote `models/metrics.json` values with the `n_test` and dataset name.

## 7. Troubleshooting

| Message | Fix |
|---|---|
| `Text column 'x' not found. Available columns: [...]` | set `text_column` in `dataset_adapter.yaml` |
| `Label column 'x' not found` | set `label_column` |
| `dropped_invalid_label: N` | labels didn't match `label_patterns` — add a pattern |
| `classes with no data: [...]` | collect more samples for those TRLs or accept partial coverage |
| `Fewer than two distinct labels present` | need ≥ 2 TRL classes to train |
| Metrics still show `unavailable` | run `training/evaluate_model.py` after training; restart the backend |
