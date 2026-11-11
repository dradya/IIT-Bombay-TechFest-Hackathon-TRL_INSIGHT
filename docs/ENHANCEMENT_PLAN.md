# TRL INSIGHT 2.0 — Enhancement Plan

> Phased implementation plan for the competition upgrade. The existing
> pipeline, API routes and 65 backend tests remain the compatibility baseline:
> every change is additive unless a correctness fix is explicitly documented.

## Non-negotiable principles

1. **Honesty over polish.** No fabricated evidence, page references, metrics,
   confidence, calibration, review data or history. Every new number is either
   computed from real inputs or explicitly marked unavailable.
2. **Enhancement, not rebuild.** Existing routes, response fields, exports and
   the single-document workflow keep working.
3. **Graceful degradation.** Docling, sentence-transformers, BGE, SHAP and
   Haystack are optional. The deterministic TF-IDF + keyword + rule pipeline is
   always available on CPU with no network access.
4. **One local demo assessment** is kept. Databases and uploads stay gitignored.

## Phase 1 — Inspection and OSS evaluation (complete)

- Read the full backend, frontend, training, config, docs and tests.
- Confirmed 65 passing tests and a green `tsc -b && vite build` baseline.
- Verified licences and integration constraints for all six requested projects
  (see `docs/OPEN_SOURCE_INTEGRATIONS.md`).
- Decisions: implement Docling, sentence-transformers/BGE, SHAP as optional
  adapters with native fallbacks; use Haystack and OSSTRL as methodological
  references only (not installed).

## Phase 2 — Extraction and retrieval

1. `services/docling_adapter.py`
   - Optional Docling conversion preserving page provenance, headings,
     sections, tables and reading order.
   - `TRL_PARSER=auto|docling|native`; automatic fallback to PyMuPDF/pdfplumber
     and python-docx. Failures are logged and surfaced as extraction warnings,
     never as fabricated content.
2. `services/semantic.py`
   - Backends: configurable sentence-transformers model, optional BGE
     (`FlagEmbedding`), deterministic TF-IDF cosine fallback.
   - Per-text embedding cache on disk, keyed by model + SHA-256(text).
   - Milestone similarity ranking over evidence statements; adds
     `semantic_similarity` / `semantic_milestone` without changing the
     conservative status rules.
3. API: `GET /api/system/capabilities` reports which optional backends are
   actually importable/runnable.

## Phase 3 — Multi-document intelligence

1. Multi-document assessments (`document_ids`), merged evidence with document
   provenance, per-document statistics.
2. Near-duplicate claim grouping (normalised token Jaccard); duplicates remain
   visible but are excluded from rule counts and model features so repeated
   claims are never double-counted.
3. Outdated-evidence detection using real document upload timestamps: a claim
   restated in a newer document supersedes the older copy.
4. Cross-document contradiction detection: explicit confirmed vs contradicted
   evidence for the same milestone, with both sources, an explanation and
   human-verification suggestions.
5. Evidence knowledge graph (`services/knowledge_graph.py`) with technology,
   document, milestone, category, evidence and contradiction nodes/edges.

## Phase 4 — Uncertainty and explainability

1. Uncertainty decomposition in `services/uncertainty.py`:
   model probability, confidence, evidence coverage, documentation completeness,
   source reliability and an explicit overall band. Calibration is reported as
   **not calibrated** unless genuine validation metrics with calibration data
   exist.
2. SHAP explainer (`ml/explain.py`): real SHAP for linear/tree models when the
   optional package is installed; exact linear coefficient attribution otherwise
   (clearly labelled). Model attributions are kept separate from
   source-backed evidence in both the API and UI.
3. Roadmap (`services/roadmap.py`) derived only from real gap analysis.
4. Missing-evidence questionnaire and reassessment flow. Expert answers are
   labelled `self_reported`; they only confirm a milestone when the reviewer
   supplies a source reference. The original AI result is never overwritten.

## Phase 5 — Expert review and history

1. `assessment_reviews` and `assessment_events` tables; reviews never mutate the
   stored AI prediction, which is returned as an immutable snapshot.
2. Review decisions: accept, override (with reviewed TRL), request more
   evidence. Review history is append-only.
3. Assessment timeline combining creation, reassessments and reviews.
4. Assessment comparison endpoint for 2–3 assessments.

## Phase 6 — Frontend

Named components:

`TRLProgressionScale`, `TRLDistributionChart`, `EvidenceCard`,
`EvidenceTable`, `EvidenceKnowledgeGraph`, `ConfidenceIndicator`,
`EvidenceCoverageIndicator`, `ContradictionAlert`, `MissingMilestoneCard`,
`TechnologyRoadmap`, `DocumentComparisonViewer`, `SHAPExplanationChart`,
`AssessmentTimeline`, `ExpertReviewPanel`, `MultiDocumentUploader`,
`AssessmentProcessingTimeline`.

- Multi-step workspace: documents → details → review → analysis.
- Detail page tabs: overview, evidence, knowledge graph, explainability,
  contradictions, roadmap, documents/timeline, expert review.
- Overview/History/Explorer/Model Performance/Settings upgraded with the new
  data and explicit empty/unavailable states.

## Phase 7 — Verification and packaging

1. Add tests for every new capability (unit + API workflow). Keep all 65
   original tests green.
2. Run: backend pytest, `tsc -b`, `vite build`, route smoke tests and a full
   upload → multi-document analysis → report → review → reassess flow.
3. Update README, docs and `PROJECT_STATE.md`.
4. Produce `TRL_INSIGHT_2.0.zip` excluding caches, dependencies, databases and
   uploads.
