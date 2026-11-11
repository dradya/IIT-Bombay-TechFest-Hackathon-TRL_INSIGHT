# PROJECT STATE — TRL INSIGHT

> Build state and session notes for the **Techfest IIT Bombay × APCTT UN ESCAP
> "AI for Technology Readiness"** hackathon submission.
> Last updated: 2026-11-11.

---

## 1. Current status

| Area | State |
|---|---|
| Backend (FastAPI) | ✅ complete — 1.0 routes preserved + full 2.0 intelligence API, SQLite persistence, JSON + PDF reports |
| ML pipeline | ✅ hybrid LR/XGBoost + rules, model bundle trained (`backend/models/`) |
| Frontend (React + TS + Vite) | ✅ 9 routes, premium design system, production build passes (`tsc -b && vite build`) |
| Tests | ✅ **81 passed** (`cd backend && python -m pytest -q`) |
| Docs | ✅ README + `docs/{API_DOCUMENTATION,ARCHITECTURE,MODEL_METHODOLOGY,DATASET_GUIDE,ENHANCEMENT_PLAN,OPEN_SOURCE_INTEGRATIONS}.md` |
| Single-server mode | ✅ backend serves `frontend/dist` incl. SPA deep-link fallback |
| Docker | ✅ `Dockerfile` + `docker-compose.yml` (`docker compose up --build`) |
| Git | ⚠️ repository has **no commits** — commit before submitting |

Everything runs fully locally: **no paid APIs, no external LLMs, no network at
runtime.**

## 2. TRL INSIGHT 2.0 upgrade — complete

| Phase | State |
|---|---|
| 1. Inspection + OSS evaluation | ✅ complete — `docs/ENHANCEMENT_PLAN.md`, `docs/OPEN_SOURCE_INTEGRATIONS.md` |
| 2. Docling + semantic retrieval | ✅ complete — optional adapters, TF-IDF fallback, capability report |
| 3. Multi-document intelligence | ✅ complete — merge, dedupe, outdated, contradictions, knowledge graph |
| 4. Uncertainty + SHAP + roadmap + questionnaire | ✅ complete — honest decomposition, real SHAP/linear fallback |
| 5. Expert review + history | ✅ complete — append-only reviews, linked reassessments, timeline, comparison |
| 6. Frontend upgrade | ✅ complete — all 9 pages upgraded, 16 named 2.0 components |
| 7. Verification + `TRL_INSIGHT_2.0.zip` | ✅ complete — backend tests, TypeScript/Vite build, browser routes/workflow |

Backend suite: **81 passed** (65 original + 16 new intelligence/filter tests).
The frontend production build passes. New response blocks are optional so
pre-2.0 stored assessments still load and export normally.

### 2.1 What 2.0 adds

* **Multi-document assessments** (up to 6 documents) with per-document
  provenance, duplicate-claim grouping and outdated/superseded evidence. Repeats
  are linked, not double-counted.
* **Contradiction detection** for explicit completed-vs-negative conflicts, with
  both sources, an explanation and human-verification suggestions.
* **Interactive evidence knowledge graph** (custom SVG, React-Flow-equivalent
  pan/zoom/drag/inspect) over technology → documents → milestones → categories
  → evidence → contradictions.
* **Honest uncertainty decomposition**: model probability, prediction
  confidence, evidence coverage, completeness and source reliability; overall
  reliability is explicitly `calibrated: false`.
* **SHAP model explanations** from the actual LogisticRegression+TFIDF
  classifier, with exact linear attribution fallback and a permanent "not source
  evidence" warning.
* **Technology roadmap** grouped by real gap-analysis priority; no invented
  dates, costs or completion claims.
* **Missing-evidence questionnaire** and **linked reassessment**; answers become
  labelled `self_reported` evidence and never overwrite the parent AI result.
* **Expert review** with append-only accept/override/request-evidence history.
* **Comparison** of 2–3 assessments with a real milestone-status matrix and
  document provenance.
* **Capability report** (`GET /api/system/capabilities`) and a Settings card
  showing the actual active parser/embedding/SHAP backends and fallbacks.

### 2.2 Optional OSS decisions

| Project | Licence | Decision |
|---|---|---|
| Docling | MIT | Optional integration; native PyMuPDF/pdfplumber/python-docx fallback |
| sentence-transformers | Apache-2.0 | Optional embeddings; TF-IDF fallback + on-disk cache |
| FlagEmbedding / BGE | MIT | Optional alternative embeddings; falls back to ST or TF-IDF |
| SHAP | MIT | Optional real attribution; exact linear fallback |
| Haystack | Apache-2.0 | Not integrated (reference only; existing pipeline already covers it) |
| OSSTRL | BSD-2-Clause | Methodological reference only; no code reused |

The shipped environment reports: parser `native`, embeddings `tfidf`,
SHAP installed/enabled, Haystack not installed, OSSTRL not installed. This is
what Settings displays.

## 3. Verified behaviour (do not "improve" without evidence)

These are the honesty guarantees the judges can check:

* Evidence excerpts are **verbatim** with real locators (PDF page, DOCX
  paragraph/table, TXT line). DOCX never gets fake page numbers (`page_count=0`).
* Future-tense statements are captured as `proposed` and **never** confirm a
  milestone.
* Duplicate claims are grouped; coverage and milestone confirmation use unique
  evidence, not repeated copies.
* Contradiction items always name both sources; planned or vague text is never
  promoted to a contradiction.
* `GET /api/model/performance` returns `available: false` when no evaluation
  exists — metrics are never fabricated.
* Synthetic demo metrics are labelled `mode: "demonstration"` everywhere.
* Uncertainty is decomposed from real signals; `calibrated` stays `false`
  without genuine held-out calibration data.
* SHAP/linear attributions are labelled as model explanations, **not** source
  evidence, and cannot confirm a milestone.
* Expert reviews are append-only; the original AI prediction is immutable.
* Pre-2.0 assessments return `409 not_available` for 2.0-only endpoints and the
  UI renders explicit unavailable states instead of fabricated blocks.
* Deterministic: same document(s) → same result.

## 4. Browser verification (2026-11-11)

Single-server mode at `http://localhost:8000`, fresh backend process serving the
current build:

* Routes `/`, `/new`, `/history`, `/explorer`, `/trl-guide`,
  `/model-performance`, `/settings`, `/assessments/:id` and the 404 route all
  render with **no console errors**.
* Full workflow passed: drop-upload `workflow_sample.txt` → Details → Review →
  Configure → Run assessment → result `asm_0b3d7c59c7b04525`
  ("Adaptive Solar Desalination Module", TRL 7, 61% confidence, 86% coverage,
  overall reliability 69% not calibrated).
* All 2.0 tabs render real populated data: evidence (13 items, 9 confirmed),
  knowledge graph (31 nodes / 53 edges), SHAP explainability, contradictions
  (0 explicit conflicts), roadmap & questionnaire, documents & timeline,
  expert review.
* PDF export generated a valid 86,726-byte report; JSON export generated a
  valid 80,683-byte document containing all 2.0 result blocks.
* Explorer comparison of both stored assessments loads real values, a real
  milestone matrix and honest "no provenance stored" text for the legacy record.
* History deep link `/history?review_status=unreviewed` and
  `?review_status=accepted` filter correctly and show real review counts.
* Expert review recorded in-browser: status changed to Accepted, review history
  appended, AI prediction unchanged.
* Legacy assessment `asm_9428f7df13ba4f39` loads with explicit unavailable
  states for 2.0-only blocks; roadmap derives from stored milestones.

## 5. Known limitations (documented, intentional)

* Synthetic demo dataset scores are **not** a benchmark — train on the official
  dataset for real numbers (`docs/DATASET_GUIDE.md`).
* Evidence extraction is keyword/indicator based (interpretable, can miss
  paraphrases); the TF-IDF branch compensates only when a model is trained.
* OCR needs optional `pytesseract` + the Tesseract binary.
* `sentence-transformers`, Docling and FlagEmbedding/BGE are not installed by
  default (heavy dependencies) — TF-IDF and native parsing are the specified
  fallbacks.
* No calibration artefact is bundled; the overall reliability score is a
  transparent composite, not a statistically calibrated probability.
* Haystack was evaluated but not integrated; OSSTRL inspired methodology only.
* SQLite only; the repository layer isolates SQL for a later PostgreSQL swap.
* The SPA is route-split; the charting vendor chunk still loads with Overview.
* The knowledge graph is a custom SVG renderer, not the React Flow package.

## 6. Rebuild / verify commands

```bat
scripts\setup.bat          :: venv + deps + frontend deps + demo model
scripts\train.bat          :: retrain (synthetic demo)
cd backend && python -m pytest -q       :: 81 passed
cd frontend && npm run build             :: tsc + vite build
scripts\start.bat          :: backend :8000 + frontend :5173
```

Single-server mode (what a judge sees with one command):

```bat
cd frontend && npm run build && cd ..
cd backend && python -m uvicorn app.main:app --port 8000
:: → http://localhost:8000
```

## 7. Packaging

`TRL_INSIGHT_2.0.zip` is created from the project root and **excludes**:
`.git`, `.venv`, `node_modules`, `__pycache__`, `.pytest_cache`, `backend/data`
(SQLite DB, uploads, extracted text, raw/processed datasets), downloaded report
artefacts and `TRL_INSIGHT_2.0.zip` itself. The built `frontend/dist` and the
trained model bundle `backend/models/` **are included** so the archive runs in
single-server mode after `pip install -r requirements.txt`.

Verified archive: **166 entries, 874,867 bytes (0.83 MB)**. Extracting it to a
clean directory and importing `app.main` succeeds, and every `/assets/...`
reference in `frontend/dist/index.html` resolves inside the archive. No
`.git`, `node_modules`, `__pycache__`, `.pytest_cache`, `backend/data`, DB,
`.pyc`, `.env`, `_smoke_report.pdf` or nested-zip entries are present.

## 8. Before you submit

1. `git add -A && git commit` — the repository currently has **no commits**.
2. Re-run the test suite and the frontend build (commands above).
3. Smoke-test the full flow in the browser: multi-document upload → analyze →
   evidence / graph / contradictions / roadmap → expert review → reassessment →
   PDF/JSON export → history filters → delete.
4. If you have the official dataset, train with it and re-check
   `/model-performance` labels switch to `trained_evaluation`.
