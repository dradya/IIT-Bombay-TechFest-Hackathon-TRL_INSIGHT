# TRL INSIGHT

**AI-powered Technology Readiness Assessment & evidence-based gap analysis**

TRL INSIGHT reads unstructured technical documents (PDF / DOCX / TXT), extracts *real* traceable evidence, predicts a Technology Readiness Level (TRL 1–9) with a hybrid ML + rules pipeline, verifies that the prediction is actually backed by documented evidence, and produces an actionable gap analysis with recommendations — plus a downloadable PDF/JSON report.

**TRL INSIGHT 2.0** adds multi-document assessments, duplicate/contradiction/outdated-evidence handling, semantic retrieval, an interactive evidence knowledge graph, uncertainty decomposition, SHAP model explanations, a technology roadmap, a missing-evidence questionnaire with linked reassessment, and an append-only expert-review workflow. Every optional integration is lazy-loaded with a working native fallback.

> Built for the **Techfest IIT Bombay × APCTT UN ESCAP "AI for Technology Readiness"** hackathon.
> Works fully locally — **no paid APIs, no external LLMs, no internet required at runtime.**

---

## Table of contents

1. [What it does](#1-what-it-does)
1b. [TRL INSIGHT 2.0 capabilities](#1b-trl-insight-20-capabilities)
2. [Architecture](#2-architecture)
3. [The assessment pipeline](#3-the-assessment-pipeline)
4. [The TRL framework (data-driven)](#4-the-trl-framework-data-driven)
5. [Quick start — Windows](#5-quick-start--windows)
6. [Quick start — Linux / macOS](#6-quick-start--linux--macos)
7. [Manual setup (no scripts)](#7-manual-setup-no-scripts)
8. [Training the model](#8-training-the-model)
9. [Using the official competition dataset](#9-using-the-official-competition-dataset)
10. [Running the tests](#10-running-the-tests)
11. [Example API requests](#11-example-api-requests)
12. [Project structure](#12-project-structure)
13. [Design principles & guarantees](#13-design-principles--guarantees)
14. [Limitations](#14-limitations)
15. [Troubleshooting](#15-troubleshooting)

---

## 1. What it does

| Step | Capability |
|------|-----------|
| **1. Ingestion** | Upload PDF (page-accurate extraction), DOCX (paragraph/table locators), TXT (line locators). Tables, headings and metadata are captured. |
| **2. Evidence extraction** | Every candidate excerpt is classified: **confirmed / proposed / contradicted / unclear**, with category, milestone, relevance and a *source location*. |
| **3. TRL prediction** | Hybrid classifier: ML probability (0.55) × rule-based milestone prior (0.45) → TRL 1–9 with full probability distribution. |
| **4. Explainability** | Evidence backing, contradictions, alternative plausible levels, explicit warnings, confidence guardrails. |
| **5. Gap analysis** | Completed / missing / unclear milestones, next target TRL, prioritised recommendations each tied to the missing milestone(s). |
| **6. Reliability** | Validation, graceful degradation (rule-only mode without a model), controlled error responses. |
| **7. History** | SQLite persistence: list, search, filter, re-open, delete assessments. |
| **8. Reports** | JSON (canonical) + PDF (locally rendered, no external service). |
| **9. Frontend** | React + TypeScript + Vite SPA: overview, wizard, result view, history, explorer, TRL guide, model performance, settings. |
| **10. UI** | Premium deep-navy + luminous-teal design system with route transitions, accessible controls and responsive layouts — but **never** at the cost of model quality: no fake charts, no fake history, no fabricated metrics. |
| **11. Multi-document (2.0)** | Attach up to 6 documents; claims are deduplicated, repeated evidence is not double-counted, and per-document provenance is preserved. |
| **12. Intelligence (2.0)** | Cross-document contradictions, outdated-evidence detection, evidence knowledge graph, milestone similarity/retrieval, uncertainty decomposition and SHAP model attribution. |
| **13. Workflow (2.0)** | Missing-evidence questionnaire, linked reassessment (the original AI result is immutable), roadmap, document comparison and append-only expert review. |

### The distinctions the system enforces

* **evidence confirmed** — the document states an activity *was performed* (and ideally reports results)
* **not found** — no supporting excerpt exists in *this* document (absence of evidence ≠ proof of absence)
* **explicitly contradicted** — the document says it has *not* happened
* **unclear / insufficient** — mentioned but not enough information
* **proposed ≠ performed ≠ documented results** — future-tense statements (`will be tested`, `plans to`, `under development`, a "Future Work" section) **never** confirm a milestone
* **no fabricated data** — page numbers only exist for formats that have pages; quotes are verbatim excerpts; metrics come from a real evaluation run or the API says *"unavailable"*

---

## 1b. TRL INSIGHT 2.0 capabilities

2.0 is an **enhancement, not a rebuild**. All 1.0 routes, stored assessments and
exports keep working; pre-2.0 records show explicit "not available" states
instead of fabricated 2.0 blocks.

| Area | What 2.0 adds | Honesty rule |
|---|---|---|
| Ingestion | Optional Docling adapter with page provenance, headings, tables and reading order; PyMuPDF/pdfplumber/python-docx fallback | Extraction method is reported truthfully (`docling` or `native`); tables/headings are never invented |
| Retrieval | Configurable sentence-transformers/BGE embeddings, CPU inference, on-disk cache, milestone similarity ranking | TF-IDF cosine remains the always-available fallback; the active backend is shown in Settings |
| Multi-document | Duplicate detection, repeated-claim grouping, outdated supersession, per-document contribution | Duplicates are linked, never counted twice; provenance is stored per document |
| Contradictions | Explicit completed-vs-negative conflicts with both sources, explanation and human-verification steps | Proposed or vague text is never promoted to a contradiction |
| Knowledge graph | Interactive SVG graph of technology → documents → milestones → categories → evidence → contradictions | Nodes/edges come from stored evidence and real relationships only |
| Uncertainty | Separate model probability, prediction confidence, evidence coverage, completeness and source reliability | `calibrated: false` unless a genuine held-out calibration dataset exists |
| Explainability | Real SHAP values from the actual classifier; exact linear attribution fallback | Model attributions are labelled as **not source evidence** and cannot confirm a milestone |
| Roadmap & questionnaire | Milestone-linked phases, targeted missing-evidence questions, answers stored as self-reported evidence | No schedule, cost or completion date is implied; self-reported answers stay labelled |
| Expert review | Append-only review history with accept/override/request-evidence decisions | The original AI prediction is immutable; reviews never overwrite it |
| Comparison | 2–3 stored assessments side by side with a real milestone-status matrix and document provenance | Higher TRL is explicitly not presented as automatically better |

Optional OSS integrations are evaluated in
[`docs/OPEN_SOURCE_INTEGRATIONS.md`](docs/OPEN_SOURCE_INTEGRATIONS.md): Docling
(MIT), sentence-transformers (Apache-2.0), FlagEmbedding/BGE (MIT) and SHAP (MIT)
are optional adapters. Haystack was evaluated but not integrated, and OSSTRL is
a methodological reference only — no third-party code is vendored. The current
environment runs with native parsing, TF-IDF retrieval and SHAP installed.

## 2. Architecture

```
┌──────────────────────────────┐        ┌───────────────────────────────────────┐
│  React + TS + Vite frontend │  /api  │  FastAPI backend (Python 3.10+)       │
│  (port 5173, dev proxy)     ├──────► │  (port 8000)                          │
│  Overview · Wizard · Result │        │                                       │
│  History · Explorer · Guide │        │  ingestion → cleaning → evidence →    │
│  Performance · Settings     │        │  features → hybrid ML+rules →         │
└──────────────────────────────┘        │  verification → gap analysis →       │
                                        │  JSON/PDF report                     │
                                        └──────┬───────────────┬────────────────┘
                                               │               │
                                        ┌──────▼──────┐ ┌──────▼──────────────┐
                                        │  SQLite DB  │ │ Model bundle        │
                                        │  (history)  │ │ TF-IDF + evidence   │
                                        └─────────────┘ │ features + LR/XGB   │
                                                        │ (joblib, versioned) │
                                                        └─────────────────────┘
```

* **Single-server mode:** if `frontend/dist` exists, the backend serves the built SPA at `/` (one process, one port).
* **Dev mode:** Vite dev server on 5173 proxies `/api` → 8000.

Full details: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) · API contract: [`docs/API_DOCUMENTATION.md`](docs/API_DOCUMENTATION.md)

---

## 3. The assessment pipeline

1. **Ingestion** — format detection, text extraction with *real* source locators (PDF pages; DOCX paragraphs/tables; TXT lines or form-feed pages), heading detection, optional OCR for scanned PDFs.
2. **Cleaning & segmentation** — section segmentation, abbreviation-aware sentence splitting, de-duplication, noise removal. Excerpts are never paraphrased.
3. **Evidence extraction** — keyword/indicator matching against the framework, status resolution in conservative order: `contradicted → proposed/future → unclear → confirmed`.
4. **Feature engineering** — TF-IDF (1–2 grams, fitted on training data only, travels inside the model bundle) + 81 deterministic evidence/milestone features (versioned layout).
5. **Hybrid classification** — `P(trl) = 0.55·ML + 0.45·rule prior`; the rule prior peaks at the highest *evidence-confirmed* milestone (skeptical prior when nothing is confirmed).
6. **Verification** — is the predicted level itself backed? Flags `unsupported_high_level_claim`, lists contradictions and proposed-mistaken-for-done excerpts.
7. **Gap analysis** — chain status up to the next target level, recommendations generated only for milestones that are *not* confirmed, each naming the milestone(s) it addresses.
8. **Reporting** — JSON + PDF (evidence table with page references, milestone table, recommendations, model metadata).

**Confidence guardrails:** if the predicted level's own milestone isn't confirmed, confidence is capped below the low-confidence threshold and a warning is shown. Predictions more than 2 levels above the evidence-confirmed level are flagged as unsupported.

Methodology details: [`docs/MODEL_METHODOLOGY.md`](docs/MODEL_METHODOLOGY.md)

---

## 4. The TRL framework (data-driven)

Everything domain-specific lives in **`backend/app/config/trl_framework.yaml`** (no code changes needed):

* 9 TRL levels — definitions, examples, requirements, progression criteria
* 9 milestones (m1–m9) with *defining indicators* and `completion_required` flags
* 10 evidence categories with keywords and section hints
* status patterns (contradicted / proposed / completion / results)
* assessment rules (weights, thresholds, guardrails)
* recommendation templates (actions, validation experiments, documentation)

Edit the YAML to adapt the rules to another domain or a revised specification.

---

## 5. Quick start — Windows

Prerequisites: **Python 3.10+** and **Node.js 18+** on PATH.

```bat
:: one-time setup (venv + deps + frontend deps + demo model)
scripts\setup.bat

:: start everything (backend :8000, frontend :5173)
scripts\start.bat
```

Then open **http://localhost:5173**.

Other scripts:

```bat
scripts\start_backend.bat   :: API only  → http://localhost:8000/api/docs
scripts\start_frontend.bat  :: UI only   → http://localhost:5173
scripts\train.bat           :: retrain the model (synthetic demo by default)
scripts\train.bat --source data\raw\official.csv   :: train on your dataset
```

---

## 6. Quick start — Linux / macOS

```bash
chmod +x scripts/*.sh
./scripts/setup.sh     # venv + deps + frontend deps + demo model
./scripts/start.sh     # backend :8000 + frontend :5173
```

---

## 7. Manual setup (no scripts)

```bash
# 1. Python environment
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. Frontend
cd frontend && npm install && cd ..

# 3. Train the demonstration model (recommended)
cd backend
python training/prepare_data.py --synthetic --samples 60
python training/train_model.py
python training/evaluate_model.py
cd ..

# 4a. Dev mode — two terminals
#  backend:  cd backend && python -m uvicorn app.main:app --reload --port 8000
#  frontend: cd frontend && npm run dev

# 4b. Single-server mode — build the SPA, then run only the backend
cd frontend && npm run build && cd ..
cd backend && python -m uvicorn app.main:app --port 8000
# → open http://localhost:8000
```

---

## 8. Training the model

Three scripts (all in `backend/training/`):

```bash
# 1. Load/validate/split data  → data/processed/{train,val,test}.csv
python training/prepare_data.py --synthetic --samples 60

# 2. Train (LR baseline + XGBoost candidate, selected by val macro-F1)
python training/train_model.py            # or --model lr|xgb|lgbm

# 3. Evaluate on the HELD-OUT test split → models/metrics.json
python training/evaluate_model.py
```

* The vectorizer used for **candidate selection** is fitted on the training split only; the **saved bundle's** vectorizer is refit on train+val — the held-out test split is never seen (no test leakage).
* Training reuses the *production* cleaning/evidence pipeline, so there is no train/serve skew.
* Without a model the API still works in **rule_only** mode.

> **Honesty note:** the bundled synthetic demo dataset yields perfect test scores because the templates are separable. Those metrics are labelled `mode: "demonstration"` everywhere and are **not** a competition or real-world benchmark. Train on the official dataset for genuine numbers (see below).

---

## 9. Using the official competition dataset

The dataset adapter is configuration-only — **no code changes**:

1. Place your file, e.g. `backend/data/raw/official_dataset.csv`
2. Edit `backend/config/dataset_adapter.yaml`:

```yaml
text_column: document        # ← your text column name
label_column: trl_label      # ← your label column name
# label patterns already accept: 7, "7", "TRL 7", "7/9", "TRL 7 of 9"
```

3. Train:

```bat
scripts\train.bat --source data\raw\official_dataset.csv --dataset-type official
```

```bash
./scripts/train.sh --source data/raw/official_dataset.csv --dataset-type official
```

The evaluation then reports `mode: "trained_evaluation"`.

> **We never claim access to any private/official dataset.** The adapter exists so that *you* can plug the competition data in when you have it. Details: [`docs/DATASET_GUIDE.md`](docs/DATASET_GUIDE.md)

---

## 10. Running the tests

```bash
cd backend
python -m pytest
```

**Current result: `81 passed`** covering:

* ingestion (PDF page numbers, DOCX paragraph locators, TXT line locators, validation errors)
* evidence status resolution (proposed never confirms; contradictions detected; traceable excerpts)
* classification (probability distribution sums to 1, low-confidence guardrails)
* gap analysis (recommendations only for unconfirmed milestones, TRL 9 sustain path)
* reports (JSON round-trip, PDF header/size, Unicode-safe PDF filenames, PDF-special-character handling, empty-evidence edge case)
* full API workflow (upload → analyze → list/filter → reports → overview → delete)
* training pipeline (adapter validation, prepare → train → evaluate in temp dirs, bundle load, metrics structure)
* CLI predictor (text input, PDF file, bad-file rejection)
* single-server SPA fallback (deep links return the app shell; unknown `/api/*` stays a JSON 404)
* 2.0 multi-document merge/dedupe/outdated handling, contradiction detection, knowledge graph, uncertainty decomposition, SHAP/linear explanations, roadmap, questionnaire
* 2.0 API workflow (multi-document analyze → graph/contradictions/roadmap/questionnaire → review → reassessment → timeline → compare)
* 2.0 list filters/sorting (domain, TRL range, confidence range, low-confidence, review status, date range, search, whitelisted sorts, pagination)
* 2.0 overview aggregates (TRL/confidence/coverage/domain/review summaries; domain and date scoping)
* legacy pre-2.0 assessments return `409 not_available` for 2.0-only blocks instead of fabricated data

Quick end-to-end smoke test (dev tool):

```bash
cd backend && python smoke_test.py
```

---

## 11. Example API requests

```bash
# health
curl http://localhost:8000/api/health

# upload a document
curl -X POST http://localhost:8000/api/documents/upload \
  -F "file=@path/to/field_report.pdf"

# analyse it
curl -X POST http://localhost:8000/api/assessments/analyze \
  -H "Content-Type: application/json" \
  -d '{"document_id":"doc_...","technology_name":"Solar MD Unit","domain":"Water Treatment"}'

# history + filters
curl "http://localhost:8000/api/assessments?search=Solar&trl_min=4&trl_max=8"

# full result / reports
curl http://localhost:8000/api/assessments/asm_...
curl -OJ http://localhost:8000/api/assessments/asm_.../report   # PDF
curl -OJ http://localhost:8000/api/assessments/asm_.../json     # JSON

# reference data + real model metrics + dashboard stats
curl http://localhost:8000/api/trl/reference
curl http://localhost:8000/api/model/performance
curl http://localhost:8000/api/overview

# 2.0 intelligence (all read from the stored result; 409 for pre-2.0 records)
curl http://localhost:8000/api/assessments/asm_.../graph
curl http://localhost:8000/api/assessments/asm_.../contradictions
curl http://localhost:8000/api/assessments/asm_.../roadmap
curl http://localhost:8000/api/assessments/asm_.../questionnaire
curl http://localhost:8000/api/assessments/asm_.../documents
curl http://localhost:8000/api/assessments/asm_.../timeline
curl http://localhost:8000/api/assessments/asm_.../reviews

# 2.0 comparison, review, reassessment and capabilities
curl "http://localhost:8000/api/assessments/compare?ids=asm_a,asm_b"
curl -X POST http://localhost:8000/api/assessments/asm_.../reviews \
  -H "Content-Type: application/json" \
  -d '{"reviewer_name":"Dr. A","decision":"accept","notes":"Evidence checked."}'
curl -X POST http://localhost:8000/api/assessments/asm_.../reassess \
  -H "Content-Type: application/json" \
  -d '{"reviewer_name":"Dr. A","reason":"New qualification evidence","answers":[]}'
curl http://localhost:8000/api/system/capabilities
```

Interactive Swagger UI: **http://localhost:8000/api/docs**

---

## 12. Project structure

```
TRL_INSIGHT/
├── README.md                     ← you are here
├── requirements.txt              ← Python dependencies (single source)
├── .env.example                  ← optional environment overrides
├── Dockerfile / docker-compose.yml
├── scripts/
│   ├── setup.bat  start.bat  start_backend.bat  start_frontend.bat  train.bat
│   └── setup.sh   start.sh   train.sh
├── docs/
│   ├── API_DOCUMENTATION.md      ← full API contract (1.0 + 2.0)
│   ├── ARCHITECTURE.md
│   ├── MODEL_METHODOLOGY.md
│   ├── DATASET_GUIDE.md
│   ├── ENHANCEMENT_PLAN.md       ← 2.0 phase plan
│   └── OPEN_SOURCE_INTEGRATIONS.md ← OSS licence/evaluation decisions
├── backend/
│   ├── app/
│   │   ├── main.py               ← FastAPI entry (optional static mount)
│   │   ├── api/                  ← health, documents, assessments, meta
│   │   ├── config/               ← trl_framework.yaml + loader
│   │   ├── core/                 ← settings, logging, SQLite + repositories
│   │   ├── ml/                   ← features, rules, hybrid predictor
│   │   ├── schemas/              ← Pydantic API contract (assessment + intelligence)
│   │   ├── services/             ← ingestion, cleaning, evidence, verification,
│   │   │                           gap analysis, assessment, reports,
│   │   │                           docling_adapter, semantic, multidoc,
│   │   │                           contradictions, knowledge_graph, uncertainty,
│   │   │                           roadmap, questionnaire, capabilities
│   │   └── utils/                ← text utilities
│   ├── training/                 ← prepare_data, train_model, evaluate_model,
│   │                               predict (CLI), synthetic_data, adapters
│   ├── config/                   ← dataset_adapter.yaml, training.yaml
│   ├── models/                   ← trl_model.joblib, metadata, metrics.json
│   ├── data/                     ← sqlite db, uploads, extracted, splits
│   ├── tests/                    ← 81 tests
│   └── smoke_test.py
└── frontend/
    ├── src/
    │   ├── pages/                ← Overview, New (5-step workspace), Detail,
    │   │                           History, Explorer, TrlGuide,
    │   │                           ModelPerformance, Settings
    │   ├── components/           ← TRLProgressionScale, TRLDistributionChart,
    │   │                           EvidenceCard/Table/KnowledgeGraph,
    │   │                           Confidence/CoverageIndicator,
    │   │                           ContradictionAlert, MissingMilestoneCard,
    │   │                           TechnologyRoadmap, DocumentComparisonViewer,
    │   │                           SHAPExplanationChart, AssessmentTimeline,
    │   │                           ExpertReviewPanel, MultiDocumentUploader,
    │   │                           AssessmentProcessingTimeline, ...
    │   ├── services/api.ts       ← typed fetch wrapper (1.0 + 2.0 endpoints)
    │   └── types/                ← TS interfaces mirroring the API
    └── vite.config.ts            ← port 5173 + /api proxy
```

---

## 13. Design principles & guarantees

* **Traceability** — every evidence item carries the verbatim excerpt + page/paragraph/line locator from the source file.
* **No invented locators** — DOCX/TXT get paragraph/line locators (`page_count = 0` for DOCX), never fake page numbers.
* **No fabricated quotes or metrics** — excerpts are copied from the document; `GET /api/model/performance` returns `available: false` with an explanation when no evaluation exists.
* **Proposed ≠ performed** — future-tense and "Future Work" statements are captured as `proposed` evidence but never confirm milestones.
* **Absence of evidence ≠ proof of absence** — `not_found` milestone summaries say so explicitly.
* **Skeptical by default** — low-evidence documents produce low-confidence predictions with warnings, not confident guesses.
* **Deterministic** — same document → same result (no sampling, no stochastic LLM calls).
* **Configurable** — framework, dataset mapping and training hyper-parameters are YAML, not code.
* **Duplicates are not double-counted** — repeated claims are linked into duplicate groups; the unique count drives coverage.
* **Uncertainty is decomposed, not invented** — model probability, confidence, coverage, completeness and source reliability are reported separately; `calibrated` stays `false` without genuine validation data.
* **Model explanations ≠ source evidence** — SHAP/linear attributions explain the classifier only; milestone confirmation still requires a verbatim excerpt with a locator.
* **Expert review is append-only** — the stored AI prediction is immutable; review decisions and reassessment children are stored separately.
* **Optional packages degrade visibly** — missing Docling, sentence-transformers, BGE or SHAP produce a reported fallback, never a startup failure or a silent quality claim.
* **Legacy records are honest** — pre-2.0 assessments return `409 not_available` for 2.0-only blocks and render an explicit unavailable state.

---

## 14. Limitations

* **Synthetic demo metrics are not a benchmark.** The bundled model is trained on generated documents; perfect test scores only prove the pipeline works. Use the official dataset for real numbers.
* **Keyword/indicator-based evidence extraction** is interpretable but can miss paraphrases that avoid the framework vocabulary; the TF-IDF branch compensates only when a trained model exists.
* **Domain coverage** of the YAML framework is general-purpose; highly specialised domains may need added keywords/indicators (edit `trl_framework.yaml`).
* **OCR** requires optional `pytesseract` + the Tesseract-OCR binary; image-only PDFs without OCR are rejected with a clear message.
* **`sentence-transformers` embeddings are not installed** by default (torch is heavy); the system degrades to TF-IDF, which is the specified fallback.
* **No LLM summarisation** — recommendations come from templates, which keeps output auditable but less varied than generative text.
* **Single-node storage** — SQLite; the repository layer isolates SQL so PostgreSQL can be swapped in later.
* **Page numbers for DOCX don't exist** (Word has no fixed pagination) — locators are paragraph/table based by design.
* **No calibration artefact is bundled** — the overall reliability score is a transparent composite of real confidence/coverage/completeness/source-quality signals, explicitly labelled "not calibrated".
* **Docling, sentence-transformers, FlagEmbedding/BGE are not installed by default** — the shipped environment uses native parsing and TF-IDF retrieval; install the optional packages for layout-aware parsing or neural embeddings.
* **Haystack is not integrated and OSSTRL code is not reused** — both were evaluated and documented; the existing deterministic pipeline already covers their additive use cases.
* **The knowledge graph is a custom SVG renderer** (React-Flow-equivalent interaction: pan, zoom, drag, inspect) rather than the React Flow dependency.

---

## 15. Troubleshooting

| Symptom | Fix |
|---|---|
| `npm run dev` can't reach the API | Start the backend first (`scripts\start_backend.bat`), check http://localhost:8000/api/health |
| Frontend shows "Backend not reachable" | Backend not running or wrong port; the Vite proxy targets `127.0.0.1:8000` |
| `model_mode: rule_only` in results | Train the model: `scripts\train.bat` (or ignore — rules-only still works) |
| `413 file too large` | Raise `TRL_MAX_UPLOAD_SIZE_MB` in `.env` |
| `415 unsupported type` | Only `.pdf`, `.docx`, `.txt` are accepted |
| `422 no text extracted` | Scanned PDF → install OCR (see `.env.example`) or upload a text-based file |
| Port already in use | `set TRL_PORT=8001` before `scripts\start*.bat` (the scripts honour it), or run uvicorn with `--port 8001`; change the Vite proxy in `frontend/vite.config.ts` accordingly |
| Windows Defender/AV blocks uvicorn | Add an exception for the project folder |
| `pdf` report shows odd characters | The PDF renderer falls back to Latin-1 when no TTF font is found — install/keep default system fonts |

---

## License

MIT — see [`LICENSE`](LICENSE).

## Documentation index

* [`docs/API_DOCUMENTATION.md`](docs/API_DOCUMENTATION.md) — endpoints, payloads, enums
* [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — components, data flow, storage
* [`docs/MODEL_METHODOLOGY.md`](docs/MODEL_METHODOLOGY.md) — features, hybrid math, guardrails
* [`docs/DATASET_GUIDE.md`](docs/DATASET_GUIDE.md) — adapter config, official dataset, honesty labels
* [`docs/ENHANCEMENT_PLAN.md`](docs/ENHANCEMENT_PLAN.md) — TRL INSIGHT 2.0 phase plan
* [`docs/OPEN_SOURCE_INTEGRATIONS.md`](docs/OPEN_SOURCE_INTEGRATIONS.md) — OSS licence, decision and fallback for every integration
* [`PROJECT_STATE.md`](PROJECT_STATE.md) — build state / session notes
