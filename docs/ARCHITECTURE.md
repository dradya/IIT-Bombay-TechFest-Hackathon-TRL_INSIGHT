# TRL INSIGHT — Architecture

This document describes the system components, data flow and storage design of TRL INSIGHT.

## 1. High-level view

```
                    ┌─────────────────────────────────────────────┐
                    │  Frontend (React 19 + TS + Vite + Tailwind) │
                    │  port 5173 (dev) · static / (single-server) │
                    └──────────────────────┬──────────────────────┘
                                           │ HTTP / JSON  (/api/*)
                    ┌──────────────────────▼──────────────────────┐
                    │  FastAPI application (app/main.py)          │
                    │  CORS · request logging · error handlers    │
                    │  optional static mount of frontend/dist     │
                    ├─────────────────────────────────────────────┤
                    │  API layer (app/api/)                       │
                    │   health · documents · assessments · meta   │
                    ├─────────────────────────────────────────────┤
                    │  Services (app/services/)                   │
                    │   ingestion → document_processing →         │
                    │   evidence → verification → gap_analysis →  │
                    │   assessment_service (orchestrator) →       │
                    │   report (JSON + PDF)                       │
                    ├───────────────────────────┬─────────────────┤
                    │  ML layer (app/ml/)        │  Framework      │
                    │   features · rules ·       │  app/config/    │
                    │   predictor (hybrid)       │  trl_framework  │
                    └───────────┬───────────────┴────────┬────────┘
                                │                        │
                     ┌──────────▼─────────┐    ┌─────────▼──────────┐
                     │  SQLite (core/db)  │    │  Model bundle      │
                     │  documents table   │    │  models/           │
                     │  assessments table │    │  trl_model.joblib  │
                     │  data/trl_insight  │    │  model_metadata    │
                     │  .db (WAL)         │    │  metrics.json      │
                     └────────────────────┘    └────────────────────┘
```

## 2. Layers and responsibilities

### 2.1 API layer (`backend/app/api/`)

| Module | Endpoints | Responsibility |
|---|---|---|
| `health.py` | `GET /api/health` | Liveness + model/database status |
| `documents.py` | `POST /api/documents/upload`, `GET /api/documents/{id}` | Validate, store, extract text, return preview |
| `assessments.py` | `POST /analyze`, `GET ""`, `GET/{id}`, `DELETE`, `/{id}/report`, `/{id}/json` | Run pipeline, persist, list/filter, export |
| `meta.py` | `GET /api/overview`, `/api/trl/reference`, `/api/model/performance` | Dashboard stats, framework data, real metrics |

Route modules are assembled in `app/api/router.py` and included by `app/main.py`.

**Error contract:** every error response is `{"detail": "...", "code": "..."}` via custom exception handlers (`HTTPException`, `RequestValidationError`, catch-all).

### 2.2 Services (`backend/app/services/`)

The seven-step pipeline, each a pure function over explicit inputs (easily unit-tested):

1. **`ingestion.py`** — format detection & extraction.
   * PDF → `pymupdf` (page-accurate), tables via `find_tables` with `pdfplumber` fallback, optional OCR.
   * DOCX → `python-docx`, walks body in document order → `paragraph N` / `table N` locators, `page_count = 0`.
   * TXT → encoding detection, `\f` (form-feed) honoured as page breaks, otherwise `line N` locators.
   * Output: `ExtractedDocument` = list of `PageUnit {page, locator, text}` + headings + tables + warnings.
2. **`document_processing.py`** — section segmentation (alias-aware), abbreviation-aware sentence splitting, de-duplication, noise removal, technical keyword ranking. Never rewrites content.
3. **`evidence.py`** — per sentence: category match, milestone match (defining indicators), status resolution (conservative order: contradicted → proposed → unclear → confirmed), relevance scoring. Output: `EvidenceRecord` list.
4. **`verification.py`** — checks whether the *predicted* level is backed by confirmed evidence; reports contradictions, proposed-mistaken-for-done, `unsupported_high_level_claim`.
5. **`gap_analysis.py`** — chain status up to next target level; recommendations only for unconfirmed milestones, each naming addressed milestones + priority.
6. **`assessment_service.py`** — orchestrator (`run_assessment`) producing the exact `AssessmentResult` schema; also (de)serialises extracted documents to `data/extracted/*.json` so re-analysis never re-parses the file.
7. **`report.py`** — canonical JSON + locally-rendered PDF (fpdf2, system TTF with Latin-1 fallback, table API with automatic pagination).

### 2.3 ML layer (`backend/app/ml/`)

* **`features.py`** — versioned feature layout (`EVIDENCE_FEATURE_VERSION`): TF-IDF corpora + 81 evidence/milestone features; `combine_features` stacks them (sparse-aware, batch-capable).
* **`rules.py`** — milestone assessment (`confirmed/not_found/contradicted/unclear`), rule-based prior distribution peaked at the highest confirmed milestone (skeptical prior when none), warnings.
* **`predictor.py`** — hybrid combination, confidence computation, guardrails, alternatives, model bundle loading (mtime-cached `joblib`, compatibility check on framework + feature versions).

### 2.4 Framework (`backend/app/config/`)

`trl_framework.yaml` (data, not code) + `framework.py` (cached typed accessor). Contains levels, milestones, categories, status patterns, text-processing settings, assessment rules, recommendation templates.

### 2.5 Core (`backend/app/core/`)

* `config.py` — settings from env (optional `.env` loader), dirs auto-created.
* `logging.py` — single logger namespace `trl.*`.
* `database.py` — SQLite wrapper (WAL, FK on) + `DocumentRepository` / `AssessmentRepository`. All SQL lives here so PostgreSQL can be swapped in without touching business logic.

## 3. Data flow — one assessment

```
upload ──► validate ──► store file (data/uploads/doc_xxx.pdf)
                    └─► extract (PDF/DOCX/TXT) ──► data/extracted/doc_xxx.json
                    └─► documents row

analyze(document_id)
   └─► load extracted JSON
       └─► clean_document            (sentences + sections)
       └─► extract_evidence          (EvidenceRecord list)
       └─► assess_rules              (milestones + prior)
       └─► predict_hybrid            (ML bundle? 0.55/0.45 → TRL + confidence)
       └─► verify_prediction         (backing / concerns)
       └─► build_gap_analysis        (missing milestones + recommendations)
       └─► assessments row (result_json)
       └─► AssessmentResult JSON to client

report ──► read result_json ──► PDF/JSON bytes (on demand, no storage needed)
```

## 4. Storage

### SQLite schema (`backend/data/trl_insight.db`)

```sql
documents    (id, filename, original_name, file_type, size_bytes, page_count,
              char_count, uploaded_at, storage_path, extracted_path, metadata_json)

assessments  (id, document_id → documents.id, technology_name, domain,
              organization, description, predicted_trl, confidence,
              low_confidence, evidence_coverage, model_mode, result_json,
              created_at)
              + indexes on (predicted_trl), (created_at), (domain)
```

* `result_json` holds the complete `AssessmentResult` → retrieval and report generation are a single read.
* List endpoints project only summary columns (JOIN with `documents` for filename) for fast history pages.
* Connections are opened per operation (event-loop safe); WAL mode for concurrent reads.

### Filesystem layout

```
backend/data/
├── trl_insight.db        SQLite database
├── uploads/              original files (doc_id + ext)
├── extracted/            extracted text JSON (re-analysis source)
├── raw/                  raw datasets (synthetic CSV or yours)
└── processed/            train/val/test.csv + dataset_stats.json

backend/models/
├── trl_model.joblib      vectorizer + classifier + metadata (versioned)
├── model_metadata.json   training provenance
└── metrics.json          real evaluation output (GET /api/model/performance)
```

## 5. Model bundle

```json
{
  "vectorizer": "<TfidfVectorizer fitted on train split>",
  "classifier": "<LogisticRegression | XGBClassifier | LGBMClassifier>",
  "labels": [1..9],
  "model_name": "LogisticRegression+TFIDF",
  "model_version": "1.0.0",
  "trained_at": "...", "dataset_type": "synthetic_demo|official|user_dataset",
  "feature_version": 1, "framework_version": "1.0.0",
  "feature_names": ["cat::...", "ms::...", scalars...],
  "val_metrics": {...}, "training_config": {...}, "candidates": [...]
}
```

Compatibility gate: `feature_version` **and** `framework_version` must match the running code, otherwise the bundle is ignored (with a warning) and rules-only mode is used — never a silent mismatch.

## 6. Concurrency & caching

* Model bundle cached by file mtime (`lru_cache`) → retraining is picked up on next request without restart.
* Framework config cached per process (`lru_cache`).
* Pipeline is stateless per request; SQLite writes are short transactions.

## 7. Security & reliability notes

* Upload validation: extension allow-list, size limit (default 25 MB), empty-file check; stored under generated IDs (no user-controlled paths).
* All inputs validated by Pydantic; SQL is parameterised everywhere.
* CORS restricted to configured origins (localhost Vite ports by default).
* Pipeline failures return a controlled 500 with `code: analysis_failed` (logged with traceback), never a stack trace to the client.
* No external network calls at runtime — no API keys, no telemetry.

## 8. Frontend architecture (`frontend/`)

* **Vite + React 19 + TypeScript (strict)**, Tailwind CSS v4 via `@tailwindcss/vite`.
* `services/api.ts` — typed `fetch` wrapper (`apiGet/apiPost/apiUpload/apiDelete/downloadFile`) throwing `ApiError {status, detail, code}`.
* `types/index.ts` — interfaces mirroring the Pydantic schemas 1:1 (snake_case JSON preserved).
* `hooks/useApi.ts` — generic loading/error/refetch hook.
* Pages: Overview · New Assessment (upload wizard) · Assessment Result · History · Technology Explorer · TRL Reference · Model Performance · Settings.
* Dev proxy: `/api → http://127.0.0.1:8000` (works in dev and when the built SPA is served by the backend).
* Design: light enterprise-analytics theme; every chart/statistic comes from a real API field; empty states when `has_data: false`.

## 9. Extension points

| Goal | Where |
|---|---|
| Adapt TRL rules/keywords to a domain | `app/config/trl_framework.yaml` |
| New document format | add extractor in `services/ingestion.py` + `ALLOWED_EXTENSIONS` in `app/core/config.py` |
| New evidence status or category | YAML + status maps in `services/evidence.py` |
| Swap storage to PostgreSQL | reimplement repositories in `core/database.py` |
| Different model family | `training/train_model.py` candidates + `config/training.yaml` |
| New report section | `services/report.py` |

## 10. TRL INSIGHT 2.0 architecture

2.0 extends the 1.0 pipeline instead of replacing it. Every new block is
optional in the stored `result_json`, so older records keep loading and
exporting.

### 10.1 Additional services

| Module | Responsibility |
|---|---|
| `services/docling_adapter.py` | Lazy Docling import and structured parsing (headings, tables, page provenance, reading order); raises a typed error so ingestion can fall back to native extractors. |
| `services/semantic.py` | Embedding backend selection (`sentence-transformers` → `bge` → `tfidf`), on-disk cache, milestone/evidence similarity. |
| `services/multidoc.py` | Merge documents, normalise text, detect duplicate claim groups and outdated/superseded evidence, build per-document provenance. |
| `services/contradictions.py` | Explicit confirmed-vs-negative conflicts at milestone, category and duplicate-group level, with both sources and human-verification steps. |
| `services/knowledge_graph.py` | Technology/document/milestone/category/evidence/contradiction nodes and real relationship edges. |
| `services/uncertainty.py` | Honest decomposition: model probability, confidence, coverage, completeness, source reliability, overall band; `calibrated=False` without a genuine artefact. |
| `ml/explain.py` | Real SHAP values for the actual classifier, exact linear-coefficient fallback, explicit "not source evidence" warning. |
| `services/roadmap.py` | Milestone-linked phases from real gap-analysis recommendations; no invented dates or costs. |
| `services/questionnaire.py` | Targeted missing/unclear-milestone questions and self-reported evidence for reassessment. |
| `services/capabilities.py` | Runtime capability discovery for Settings and `GET /api/system/capabilities`. |

### 10.2 Multi-document flow

```
POST /api/assessments/analyze { document_ids: [..] }
  └─► extract each document (Docling or native)
      └─► merge sentences & locators (never paraphrase)
          └─► deduplicate repeated claims (count unique evidence)
              └─► detect outdated/superseded copies
                  └─► evidence extraction + milestone rules
                      └─► hybrid prediction + uncertainty + SHAP
                          └─► contradictions + knowledge graph
                              └─► roadmap + questionnaire
                                  └─► store result_json + document links
```

`documents`, `assessment_documents`, `assessment_reviews` and
`assessment_events` are additive tables/columns. Migrations run in place on
startup (`_ASSESSMENT_MIGRATIONS`), so an existing 1.0 database is preserved.

### 10.3 Expert review and reassessment

* Reviews are append-only rows in `assessment_reviews`; the stored AI result
  is never updated.
* `POST /{id}/reassess` creates a **new** assessment with
  `parent_assessment_id` and `reassessment_reason`; questionnaire answers enter
  the pipeline as `self_reported` evidence.
* `assessment_events` drives the timeline (`created`, `analysis`, `review`,
  `reassessment`).

### 10.4 Frontend 2.0

New named components (all driven by real API fields):

`TRLProgressionScale`, `TRLDistributionChart`, `EvidenceCard`, `EvidenceTable`,
`EvidenceKnowledgeGraph`, `ConfidenceIndicator`, `EvidenceCoverageIndicator`,
`ContradictionAlert`, `MissingMilestoneCard`, `TechnologyRoadmap`,
`DocumentComparisonViewer`, `SHAPExplanationChart`, `AssessmentTimeline`,
`ExpertReviewPanel`, `MultiDocumentUploader`, `AssessmentProcessingTimeline`.

The detail page uses accessible tabs (overview, evidence, knowledge graph,
explainability, contradictions, roadmap & gaps, documents & timeline, expert
review) and renders explicit unavailable states for legacy records. The shell
adds a Ctrl/Cmd+K command palette and a review-queue notification.
