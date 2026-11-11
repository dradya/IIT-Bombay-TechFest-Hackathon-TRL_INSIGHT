# TRL INSIGHT — Model & Methodology

This document explains how the TRL prediction is made: features, the hybrid math, evidence semantics, confidence guardrails, evaluation, and what is — and is not — claimed about performance.

## 1. Design goals

1. **Evidence-first** — a prediction must be traceable to excerpts that actually exist in the document.
2. **Honest uncertainty** — weak evidence ⇒ low confidence + explicit warnings; never a confident guess.
3. **Interpretable** — every number decomposes into understandable parts (rule prior, ML probability, coverage).
4. **No train/serve skew** — training runs the *same* cleaning → evidence → feature code as the API.
5. **Deterministic** — identical input produces identical output.

## 2. Evidence semantics (the core of the system)

### 2.1 Four evidence statuses

| Status | Meaning | Milestone effect |
|---|---|---|
| `confirmed` | The document states the activity **was performed** (past/completed tense), ideally with results | Can confirm a milestone |
| `proposed` | Future intent: *will be tested*, *plans to*, *aims to*, *under development*, or the sentence sits in a "Future Work" section | **Never** confirms |
| `contradicted` | The document explicitly says it has **not** happened (*has not been certified*, *not yet tested*, *failed to demonstrate*) | Demotes / blocks; triggers warnings |
| `unclear` | Mentioned but incomplete (e.g. a completion-required milestone described without a completed action) | Does not confirm |

### 2.2 Status resolution order (conservative)

```
contradicted  →  proposed/future  →  unclear (completion_required but not completed)  →  confirmed
```

* Patterns live in `trl_framework.yaml → evidence_status_patterns` (contradicted / proposed / completion / results) and are matched against a lower-cased, accent-folded copy of the sentence.
* Sections matter: content inside a `future_work` section is treated as proposed unless clearly completed.
* A milestone with **both** supporting and contradicting excerpts becomes `unclear` (conflicting evidence), not confirmed.

### 2.3 Proposed ≠ performed ≠ documented results

Three tiers, in increasing strength:

1. **proposed** — planned work (captured as evidence, weighted 0 for confirmation)
2. **performed** — completed action (*was conducted*, *we demonstrated*, *has been validated*)
3. **documented results** — completed action + reported numbers (*results show…*, *measured…*, *agreed with…*)

Only tiers 2–3 can confirm a milestone; tier 3 raises relevance most.

### 2.4 Absence of evidence

`not_found` milestone summaries explicitly state: *"Absence of evidence is not proof that the activity never happened."* The system never converts "not mentioned" into "did not happen".

## 3. Features

Two families, concatenated (`features.py`, versioned by `EVIDENCE_FEATURE_VERSION = 1`):

### 3.1 Text features — TF-IDF

* word 1–2 grams, `max_features=15000`, `min_df=2`, `max_df=0.95`, `sublinear_tf`, unicode accents stripped
* fitted **on the training split only** for candidate selection; the **saved bundle's vectorizer is refit on train+val** (train+val only — the held-out test split is never seen). It travels inside the model bundle and is only `transform`ed at inference
* input corpus = cleaned sentence text joined by spaces (identical at train & serve)

### 3.2 Evidence features (81 dimensions)

* per evidence-category counts by status (`cat::<id>::confirmed/proposed/contradicted`) — 10 categories × 3
* per-milestone status indicators (`ms::<id>::confirmed/proposed/contradicted/not_found`) — 9 × 4
* scalars: total/confirmed counts & ratios, coverage, contradicted/proposed/unclear counts, future-tense & negated ratios, milestones per status, results-section ratio, defining-hit total

These are computed by the deterministic pipeline, so they are identical in training and serving.

## 4. Hybrid prediction

### 4.1 Rule-based prior (`rules.py`)

1. Assess each milestone from evidence (§2).
2. `supported_level` = highest milestone with `status = confirmed`.
3. Prior distribution:

```
if supported_level exists:   p(l) ∝ exp(−|l − supported| / τ)
     τ = 1.0 (coverage ≥ 0.5)  else  1.7;  widened further when contradictions exist
else (nothing confirmed):    p(l) ∝ 0.72^(l−1)      ← skeptical, favours low readiness
```

Normalised to sum to 1 over levels 1–9.

### 4.2 ML classifier

* Candidates (config `training.yaml`): **LogisticRegression** (baseline, always) and **XGBoost** when data ≥ `min_samples_for_boosting` (LightGBM only if `lgbm` is added to `models.candidates`, or on demand via `--model lgbm`).
* Selection by **validation macro-F1**; the winner is retrained on train+val and saved.
* Output: 9-class probability vector aligned to labels 1–9.

### 4.3 Combination

```
p_hybrid(l) = 0.55 · p_ml(l) + 0.45 · p_rule(l)          (normalised)
predicted   = argmax_l p_hybrid(l)
```

Without a usable model: `mode = "rule_only"`, `p_hybrid = p_rule`.

### 4.4 Alternatives

Levels other than the prediction are reported when `p ≥ 0.12`, or `p ≥ 0.08` for adjacent levels (max 3), each with a human-readable reason (*milestone evidence supports this level*, *ML classifier favoured this level*, …).

## 5. Confidence & guardrails

```
base  = 0.55·max(p_ml) + 0.45·rule_conf        (hybrid)
        or rule_conf-based formula             (rule_only)
        rule_conf = 0.35 + 0.45·coverage + 0.20·(no contradictions ? 1 : 0.5)
conf  = base · (0.55 + 0.45·coverage_up_to_prediction)
if ML level ≠ rule level:  conf ×= 0.85
```

Then the guardrails (all reported, never hidden):

| Guardrail | Effect |
|---|---|
| prediction > confirmed_level + 2 | warning *unsupported high-level claim*; confidence capped below `low_confidence_threshold − 0.02` |
| **milestone explicitly contradicted** | that level's probability is multiplied by `contradiction_penalty` (0.25) in the final distribution — an explicit "has not been…" demotes the prediction |
| **predicted level's own milestone not confirmed** | warning naming the milestone; confidence capped at `threshold − 0.01` → `low_confidence: true` |
| coverage < 0.20 (or no confirmed level with prediction ≥ 5) | `low_confidence: true` + warning |
| contradictions / planned-work detected | warnings propagated from the rules engine |

`low_confidence_threshold = 0.45` (configurable in YAML).

## 6. Verification & gap analysis

* **Verification** (`services/verification.py`) — lists the excerpts backing the predicted level, all contradictions, statements where planned work might be mistaken for done, and human-readable concerns; sets `unsupported_high_level_claim`.
* **Gap analysis** (`services/gap_analysis.py`) — completed/missing/unclear/contradicted milestones over the chain up to the next target; recommendations are emitted **only** for milestones that are not confirmed, each with `address_labels` + `address_statuses`, actions, validation experiments, documentation items, and a priority (high = next target).

## 7. Training procedure

```
training/prepare_data.py   load (CSV/TSV/JSON/JSONL via dataset_adapter.yaml)
                           validate: empty/too-short/invalid-label/duplicate reporting
                           stratified split 70/15/15 (seed 42)
training/train_model.py    featurise with production pipeline (progress printed)
                           fit TF-IDF on train only
                           train candidates → val macro-F1 → select
                           retrain winner on train+val → models/trl_model.joblib
training/evaluate_model.py held-out test split → models/metrics.json
                           (accuracy, macro/weighted F1, per-class P/R/F1,
                            confusion matrix, classification report)
```

Reproducibility: fixed seeds, config YAML stored inside the bundle, provenance in `model_metadata.json`.

## 8. Evaluation honesty

* `GET /api/model/performance` reads **only** `models/metrics.json` written by `evaluate_model.py`.
* If no evaluation exists → `available: false`, `mode: "unavailable"`, with instructions. **Metrics are never fabricated.**
* Dataset type is carried everywhere:

| `dataset_type` | `mode` | Meaning |
|---|---|---|
| `synthetic_demo` | `demonstration` | Generated documents; proves the pipeline, **not** a benchmark |
| `official` / `user_dataset` | `trained_evaluation` | Real labelled data you provided |

* The bundled synthetic model reaches ~1.0 test scores because the generator's templates are class-separable — that number appears only labelled as *demonstration*.

## 9. Optional extensions (not enabled by default)

* **Semantic embeddings** — `sentence-transformers` is an optional hook; TF-IDF is the specified fallback (torch is not installed by default).
* **OCR** — `pytesseract` + Tesseract binary for scanned PDFs; the app degrades gracefully with a warning when absent.
* **Calibration** — probability calibration (Platt/isotonic) can be added in `train_model.py` if the official dataset is large enough.

## 10. Configurable knobs (`trl_framework.yaml → assessment_rules`)

| Key | Default | Role |
|---|---|---|
| `ml_weight` / `rule_weight` | 0.55 / 0.45 | hybrid mixture |
| `rule_prior_tau_confirmed/uncertain` | 1.0 / 1.7 | prior width |
| `evidence_coverage_good` | 0.5 | τ switch |
| `low_confidence_threshold` | 0.45 | confidence cut-off |
| `min_evidence_coverage` | 0.20 | coverage cut-off |
| `max_levels_above_confirmed` | 2 | unsupported-claim guard |
| `disagreement_penalty` | 0.85 | ML↔rules disagreement |
| `alternative_*` | 0.12 / 0.08 / 3 | alternative levels |
