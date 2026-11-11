# TRL INSIGHT — API Documentation

Base URL (local): `http://localhost:8000`
Interactive docs: `http://localhost:8000/api/docs` (Swagger UI)

All request/response bodies are JSON (`multipart/form-data` only for upload).
Error responses have the shape:

```json
{ "detail": "Human readable message", "code": "machine_readable_code" }
```

Common status codes: `400` validation, `404` not found, `409` conflict
(missing extraction), `413` file too large, `415` unsupported type,
`422` extraction/validation failure, `500` internal error.

---

## 1. `GET /api/health`

```json
{
  "status": "ok",
  "app": "TRL INSIGHT",
  "version": "1.0.0",
  "environment": "development",
  "model_available": true,
  "model_mode": "LogisticRegression+TFIDF",
  "database": "C:/.../backend/data/trl_insight.db",
  "time": "2026-11-07T10:33:26.913254+00:00"
}
```

## 2. `POST /api/documents/upload`

`multipart/form-data`, field name **`file`**. Allowed: `.pdf`, `.docx`, `.txt`
(max 25 MB by default, configurable via `TRL_MAX_UPLOAD_SIZE_MB`).

Response `200`:

```json
{
  "id": "doc_52347d352094451a",
  "filename": "doc_52347d352094451a.txt",
  "original_name": "field_report.txt",
  "file_type": "txt",
  "size_bytes": 5321,
  "page_count": 1,
  "char_count": 2981,
  "uploaded_at": "2026-11-07T10:00:00+00:00",
  "preview_text": "Solar-Powered Membrane Distillation Unit...",
  "preview_pages": [ { "page": 1, "text": "...", "chars": 2981 } ],
  "headings": ["Introduction and Scientific Principles", "..."],
  "has_tables": false,
  "ocr_used": false,
  "warnings": [],
  "extraction_method": "text",
  "metadata": {}
}
```

Notes:
- `page_count` is `0` for DOCX (no fixed pagination) — page references are
  replaced by `paragraph N` / `table N` locations. Never invented.
- `preview_text` is the extracted text (first 4000 characters).

## 3. `GET /api/documents/{id}`

Metadata for a previously uploaded document (`DocumentInfo`):

```json
{
  "id": "doc_52347d352094451a",
  "filename": "doc_52347d352094451a.txt",
  "original_name": "field_report.txt",
  "file_type": "txt",
  "size_bytes": 5321,
  "page_count": 1,
  "char_count": 2981,
  "uploaded_at": "2026-11-07T10:00:00+00:00"
}
```

`404` → `{ "detail": "Document not found.", "code": "not_found" }`

## 4. `POST /api/assessments/analyze`

```json
{
  "document_id": "doc_52347d352094451a",
  "technology_name": "Solar Membrane Distillation Unit",
  "domain": "Water Treatment",
  "organization": "Test Lab",
  "description": "Solar-driven membrane distillation for off-grid water treatment."
}
```

Response `200` — the full `AssessmentResult`:

```json
{
  "id": "asm_e35106b49dde4c50",
  "document_id": "doc_52347d352094451a",
  "created_at": "2026-11-07T10:05:00+00:00",
  "framework_version": "1.0.0",
  "metadata": {
    "technology_name": "Solar Membrane Distillation Unit",
    "domain": "Water Treatment",
    "organization": "Test Lab",
    "description": "...",
    "filename": "field_report.txt"
  },
  "prediction": {
    "predicted_trl": 7,
    "level_name": "System prototype demonstrated in operational environment",
    "level_category": "System Development",
    "level_description": "The system prototype is demonstrated in an operational environment...",
    "confidence": 0.75,
    "low_confidence": false,
    "evidence_coverage": 0.857,
    "probabilities": [ { "level": 1, "probability": 0.0021 }, "... x9" ],
    "alternatives": [
      { "level": 6, "probability": 0.1765, "reason": "adjacent level with non-trivial probability" }
    ],
    "rule_level": 7,
    "ml_level": null,
    "model_mode": "rule_only",
    "warnings": ["No compatible trained model is available - ..."],
    "method": "Rule engine only: milestone evidence status + configurable TRL assessment rules"
  },
  "evidence": [
    {
      "id": "e001",
      "statement": "Laboratory tests were conducted on the integrated prototype using a controlled test bench.",
      "category": "laboratory_testing",
      "category_label": "Laboratory testing",
      "status": "confirmed",
      "stance": "supporting",
      "source_document": "field_report.txt",
      "page_number": 1,
      "location": "page 1",
      "section": "methods",
      "milestone": "m4",
      "milestone_label": "Technology validated in laboratory",
      "supports_milestone": true,
      "relevance": 0.55,
      "is_proposed": false,
      "future_tense": false,
      "negated": false
    }
  ],
  "evidence_summary": {
    "total": 22, "confirmed": 12, "proposed": 1, "contradicted": 0, "unclear": 9,
    "by_category": [ { "category": "scientific_principles", "label": "Scientific principles",
                       "count": 2, "confirmed": 2, "proposed": 0, "contradicted": 0, "unclear": 0 } ],
    "coverage": 0.857
  },
  "milestones": [
    { "id": "m1", "trl": 1, "label": "Basic principles observed", "status": "confirmed",
      "evidence_count": 2, "supporting": 2, "contradicting": 0, "proposed": 0,
      "summary": "Confirmed by 2 excerpt(s) (pages 1).", "evidence_ids": ["e004", "e011"] }
  ],
  "verification": {
    "predicted_trl": 7,
    "evidence_backing": [ "EvidenceItem ..." ],
    "contradictions": [],
    "proposed_mistaken_for_done": [ "EvidenceItem ..." ],
    "unsupported_high_level_claim": false,
    "concerns": ["1 statement(s) describe TRL 7+ activities as planned/future work..."],
    "summary": "TRL 7 is supported by 1 confirmed excerpt(s) (pages 1)."
  },
  "gap_analysis": {
    "current_trl": 7,
    "current_name": "System prototype demonstrated in operational environment",
    "next_trl": 8,
    "next_name": "System complete and qualified",
    "completed_milestones": [ "MilestoneStatus ..." ],
    "missing_milestones": [],
    "unclear_milestones": [ "MilestoneStatus ..." ],
    "contradicted_milestones": [],
    "recommendations": [
      {
        "id": "rec_qualification",
        "title": "Complete qualification and acceptance testing",
        "addresses": ["m8"],
        "address_labels": ["System complete and qualified"],
        "address_statuses": ["unclear"],
        "actions": ["Execute the qualification test campaign against ..."],
        "validation_experiments": ["Qualification, reliability and acceptance tests ..."],
        "documentation": ["Qualification test reports, certificates ..."],
        "priority": "high"
      }
    ],
    "documentation_requirements": ["Qualification test reports, certificates ..."],
    "summary": "Current supported readiness: TRL 7 (...). Next target: TRL 8 (...)."
  },
  "model": { "available": false, "name": "", "version": "", "mode": "rule_only",
             "dataset_type": "none", "trained_at": null },
  "processing": { "extraction_method": "pymupdf", "pages": 3, "sentences": 48,
                  "evidence_items": 22, "ocr_used": false, "duration_ms": 42 }
}
```

Key enumerations:

| Field | Values |
|---|---|
| `evidence[].status` | `confirmed`, `proposed`, `contradicted`, `unclear` |
| `evidence[].stance` | `supporting`, `contradicting`, `insufficient` |
| `milestones[].status` | `confirmed`, `not_found`, `contradicted`, `unclear` |
| `prediction.model_mode` | `hybrid`, `rule_only` |
| `prediction.predicted_trl` | `1..9` |

## 5. `GET /api/assessments`

Query parameters (all optional): `search`, `domain`, `trl` (1-9),
`trl_min`, `trl_max`, `confidence_min`, `confidence_max`, `low_confidence`,
`review_status` (`unreviewed|accepted|overridden|more_evidence_requested`),
`date_from`, `date_to` (ISO date or datetime, inclusive), `sort`
(`created_desc|created_asc|trl_desc|trl_asc|confidence_desc|confidence_asc|coverage_desc`),
`limit` (default 200), `offset`.

```json
{
  "items": [
    {
      "id": "asm_...", "document_id": "doc_...",
      "technology_name": "...", "domain": "...", "organization": "...",
      "filename": "field_report.txt",
      "predicted_trl": 7, "level_name": "...",
      "confidence": 0.75, "low_confidence": false,
      "evidence_coverage": 0.857, "model_mode": "rule_only",
      "created_at": "2026-11-07T10:05:00+00:00",
      "document_count": 2, "uncertainty_overall": 0.69,
      "contradictions_total": 0,
      "review_status": "unreviewed", "latest_review_decision": null
    }
  ],
  "total": 1
}
```

## 6. `GET /api/assessments/{id}` → full `AssessmentResult` (same as analyze)

## 7. `DELETE /api/assessments/{id}` → `{ "deleted": true, "id": "asm_..." }`

## 8. `GET /api/assessments/{id}/report` → `application/pdf` (attachment)

## 9. `GET /api/assessments/{id}/json` → `application/json` (attachment)

## 10. `GET /api/trl/reference`

```json
{
  "version": "1.0.0",
  "meta": { "name": "...", "description": "...", "scale_note": "..." },
  "levels": [
    { "level": 1, "name": "Basic principles observed", "category": "Basic Research",
      "description": "...", "examples": ["..."], "requirements": ["..."],
      "progression_criteria": ["..."] }
  ],
  "milestones": [ { "id": "m1", "trl": 1, "label": "...", "description": "...",
                    "completion_required": false, "defining_indicators": ["..."] } ],
  "evidence_categories": [ { "id": "scientific_principles", "label": "...",
                            "description": "...", "primary_milestone": "m1",
                            "secondary_milestones": [], "keywords": ["..."] } ],
  "evidence_statuses": ["confirmed", "not_found", "contradicted", "unclear"],
  "assessment_rules": { "ml_weight": 0.55, "low_confidence_threshold": 0.45, "...": 0 }
}
```

## 11. `GET /api/model/performance`

**When no model has been trained** (metrics are never fabricated):

```json
{
  "available": false,
  "mode": "unavailable",
  "note": "No trained model or evaluation data is available yet. ...",
  "model_name": null, "model_version": null, "trained_at": null,
  "dataset_type": null, "dataset_source": null,
  "n_train": null, "n_test": null,
  "class_distribution": {}, "metrics": {}, "per_class": {},
  "confusion_matrix": null, "classification_report": null
}
```

**After training + evaluation**:

```json
{
  "available": true,
  "mode": "demonstration",
  "note": "Metrics computed on a held-out test split of the SYNTHETIC demonstration dataset. Not a competition benchmark.",
  "model_name": "LogisticRegression+TFIDF",
  "model_version": "1.0.0",
  "trained_at": "2026-11-07T11:00:00+00:00",
  "dataset_type": "synthetic_demo",
  "dataset_source": "data/raw/synthetic_demo_dataset.csv",
  "n_train": 378, "n_test": 81,
  "class_distribution": { "1": 9, "2": 9, "...": 0, "9": 9 },
  "metrics": { "accuracy": 0.617, "macro_f1": 0.588, "weighted_f1": 0.601 },
  "per_class": { "1": { "precision": 0.70, "recall": 0.78, "f1": 0.74, "support": 9 } },
  "confusion_matrix": { "labels": [1,2,3,4,5,6,7,8,9], "matrix": [[7,2,0,...]] },
  "classification_report": { "1": { "precision": 0.7, "...": 0 }, "accuracy": 0.62, "...": 0 }
}
```

`mode` is `trained_evaluation` when a real (official) labelled dataset was used,
`demonstration` for the synthetic dataset, `unavailable` when nothing exists.

## 12. `GET /api/overview`

```json
{
  "has_data": true,
  "total_assessments": 12,
  "average_trl": 4.67,
  "average_confidence": 0.63,
  "distribution": [ { "trl": 1, "count": 0 }, "... x9" ],
  "confidence": { "high": 4, "medium": 6, "low": 2, "average": 0.63 },
  "coverage": { "high": 3, "medium": 7, "low": 2, "average": 0.71 },
  "domain_distribution": [ { "domain": "Water Treatment", "count": 8 } ],
  "reviews": { "unreviewed": 9, "accepted": 2, "overridden": 1,
               "more_evidence_requested": 0, "awaiting_review": 9 },
  "recent": [ "AssessmentSummary ..." ],
  "activity": [ { "id": "asm_...", "technology_name": "...", "predicted_trl": 7,
                  "confidence": 0.75, "created_at": "...", "kind": "assessment" } ],
  "domains": ["Water Treatment", "..."]
}
```

When no assessments exist: `has_data = false` and empty collections — the UI
should render an empty state instead of zeros-as-facts. `domain` and
`date_from`/`date_to` scope every aggregate consistently.

---

# TRL INSIGHT 2.0 endpoints

All 2.0 blocks are additive. A pre-2.0 stored assessment still returns normally
from `GET /api/assessments/{id}`; 2.0-only endpoints return:

```json
{
  "detail": "Evidence graph is not available for this assessment (it was created before TRL INSIGHT 2.0). Re-run the analysis to generate it.",
  "code": "not_available"
}
```

with HTTP `409`.

## 13. `GET /api/assessments/{id}/documents`

Per-document provenance for the assessment. Legacy single-document records are
derived from the stored link instead of inventing counts.

```json
[
  {
    "document_id": "doc_...",
    "filename": "workflow_sample.txt",
    "page_count": 1,
    "char_count": 1812,
    "uploaded_at": "2026-11-10T09:00:00+00:00",
    "extraction_method": "text",
    "evidence_count": 13,
    "confirmed": 9,
    "proposed": 1,
    "contradicted": 1,
    "unclear": 2,
    "duplicates": 0,
    "outdated": 0
  }
]
```

## 14. `GET /api/assessments/{id}/graph`

Real nodes/edges derived from the analysis:

```json
{
  "nodes": [
    { "id": "tech", "type": "technology", "label": "Adaptive Solar Desalination Module" },
    { "id": "doc_...", "type": "document", "label": "workflow_sample.txt" },
    { "id": "m7", "type": "milestone", "label": "System prototype demonstrated in operational environment",
      "status": "confirmed" },
    { "id": "e001", "type": "evidence", "label": "...",
      "status": "confirmed", "document_id": "doc_...", "page_number": 1 }
  ],
  "edges": [
    { "id": "edge_...", "source": "tech", "target": "doc_...", "type": "contains", "label": "document" },
    { "id": "edge_...", "source": "e001", "target": "m7", "type": "supports", "label": "supports" }
  ],
  "node_count": 31,
  "edge_count": 53,
  "truncated": false,
  "note": "..."
}
```

Edge types: `contains`, `supports`, `contradicts`, `duplicate_of`,
`derived_from`, `relates_to`. The graph is truncated only when a configured cap
is reached, and `truncated` says so.

## 15. `GET /api/assessments/{id}/contradictions`

Only explicit conflicts are reported:

```json
{
  "total": 1,
  "by_type": { "explicit_contradiction": 1 },
  "items": [
    {
      "id": "con_001",
      "type": "explicit_contradiction",
      "severity": "high",
      "milestone": "m7",
      "milestone_label": "System prototype demonstrated in operational environment",
      "explanation": "...",
      "sources": [
        { "evidence_id": "e006", "statement": "...", "source_document": "report.txt",
          "page_number": 1, "status": "confirmed", "outdated": false },
        { "evidence_id": "e008", "statement": "...", "source_document": "review.txt",
          "page_number": 2, "status": "contradicted", "outdated": false }
      ],
      "human_verification": ["Ask the responsible engineer to confirm ...", "..."],
      "suggested_action": "Resolve with a dated, signed source ..."
    }
  ],
  "summary": "..."
}
```

## 16. `GET /api/assessments/{id}/roadmap`

Phases group the real gap-analysis recommendations. No schedule, cost or
completion date is implied.

```json
{
  "current_trl": 7,
  "current_name": "System prototype demonstrated in operational environment",
  "target_trl": 8,
  "target_name": "System complete and qualified",
  "phases": [
    {
      "id": "now", "title": "Now", "horizon": "now", "target_trl": 8,
      "summary": "...",
      "items": [
        { "id": "rec_001", "title": "Complete qualification and acceptance testing",
          "milestone": "m8", "status": "unclear", "priority": "high",
          "actions": ["..."], "validation_experiments": ["..."],
          "documentation": ["..."], "success_criteria": ["..."] }
      ]
    }
  ],
  "note": "Phases group the real gap-analysis recommendations by priority ..."
}
```

## 17. `GET /api/assessments/{id}/questionnaire`

Targeted questions for milestones that are missing or unclear:

```json
{
  "assessment_id": "asm_...",
  "generated_at": "2026-11-10T09:00:00+00:00",
  "total": 3,
  "items": [
    { "id": "q_m1", "milestone": "m1", "milestone_label": "Basic principles observed",
      "trl": 1, "status": "not_found", "question": "...", "why_it_matters": "...",
      "expected_document": "Technical principles memo or peer-reviewed publication.",
      "options": ["completed", "planned", "not_applicable", "unknown"] }
  ],
  "note": "Answers are self-reported. They are only treated as confirmed evidence when a source reference is supplied."
}
```

## 18. `GET /api/assessments/{id}/reviews`

Append-only review history plus the immutable AI prediction:

```json
{
  "assessment_id": "asm_...",
  "items": [
    { "id": "rev_...", "assessment_id": "asm_...", "reviewer_name": "Dr. A",
      "decision": "accept", "reviewed_trl": null, "ai_trl": 7,
      "notes": "...", "evidence_ids": ["e001"], "created_at": "..." }
  ],
  "total": 1,
  "ai_prediction": {
    "predicted_trl": 7, "confidence": 0.61, "evidence_coverage": 0.86,
    "model_mode": "hybrid", "created_at": "...", "immutable": true
  },
  "latest_decision": "accept",
  "review_status": "accepted"
}
```

`review_status` values: `unreviewed`, `accepted`, `overridden`,
`more_evidence_requested`.

## 19. `POST /api/assessments/{id}/reviews`

```json
{
  "reviewer_name": "Dr. A",
  "decision": "accept",
  "reviewed_trl": null,
  "notes": "Evidence checked.",
  "evidence_ids": ["e001", "e006"]
}
```

`decision`: `accept`, `override` (requires `reviewed_trl` 1–9) or
`needs_more_evidence`. Returns the created `ReviewModel`. The original
`result_json` is never modified.

## 20. `POST /api/assessments/{id}/reassess`

Creates a **new** assessment linked by `parent_assessment_id`; the parent is
preserved. Answers become clearly labelled `self_reported` evidence.

```json
{
  "reviewer_name": "Dr. A",
  "reason": "New qualification evidence",
  "answers": [
    { "milestone_id": "m8", "status": "completed",
      "evidence_note": "Qualification tests passed.",
      "source_reference": "QTR-2026-14" }
  ]
}
```

Returns the new full `AssessmentResult` with `parent_assessment_id` and
`reassessment_reason`. A `409 documents_unavailable` is returned when the
source documents no longer exist.

## 21. `GET /api/assessments/{id}/timeline`

```json
{
  "assessment_id": "asm_...",
  "events": [
    { "id": "evt_...", "kind": "created", "title": "Assessment created",
      "description": "...", "at": "...", "actor": null, "metadata": {} },
    { "id": "evt_...", "kind": "review", "title": "Expert review: accept",
      "description": "...", "at": "...", "actor": "Dr. A",
      "metadata": { "decision": "accept", "ai_trl": 7 } }
  ]
}
```

Event kinds: `created`, `analysis`, `review`, `reassessment`.

## 22. `GET /api/assessments/compare?ids=asm_a,asm_b`

Accepts 2–3 comma-separated ids. Returns real stored values plus a milestone
matrix:

```json
{
  "items": [
    { "id": "asm_...", "technology_name": "...", "predicted_trl": 7,
      "confidence": 0.61, "evidence_coverage": 0.86, "uncertainty_overall": 0.69,
      "documents": [ "DocumentSummary ..." ], "milestones": [ "..." ],
      "evidence_total": 13, "contradictions_total": 0, "created_at": "..." }
  ],
  "note": "Values are taken directly from each stored assessment. A higher TRL is not automatically better ..."
}
```

## 23. `GET /api/system/capabilities`

Actual runtime availability of optional integrations. Nothing is reported as
available unless its package can be imported:

```json
{
  "parser": {
    "configured": "auto", "docling_available": false, "active": "native",
    "native_fallback": "PyMuPDF + pdfplumber (PDF), python-docx (DOCX), text (TXT)",
    "note": "..."
  },
  "embeddings": {
    "configured": "auto", "active": "tfidf",
    "model": "word(1,2)+char_wb(3,5) tf-idf cosine",
    "available": true,
    "fallback_reason": "...", "cache": ".../backend/data/embeddings",
    "sentence_transformers_installed": false,
    "flag_embedding_installed": false,
    "note": "..."
  },
  "semantic_retrieval": { "enabled": true, "backend": "tfidf" },
  "shap": { "enabled": true, "installed": true, "fallback": "...", "note": "..." },
  "haystack": { "installed": false, "integrated": false, "reason": "..." },
  "osstrl": { "installed": false, "integrated": false, "license": "BSD-2-Clause", "reason": "..." }
}
```

## 2.0 result blocks added to `AssessmentResult`

`GET /api/assessments/{id}` and `POST /api/analyze` now also return (when the
record was produced by 2.0): `documents`, `retrieval`, `contradictions`, `graph`,
`uncertainty`, `roadmap`, `questionnaire`, `model_explanation`,
`parent_assessment_id`, `reassessment_reason`. The existing 1.0 fields are
unchanged.

`uncertainty` separates real signals and never pretends to be calibrated:

```json
{
  "model_probability": 0.494,
  "confidence": 0.61,
  "coverage": 0.86,
  "completeness": 0.667,
  "reliability": 0.68,
  "overall": 0.69,
  "band": "medium",
  "calibrated": false,
  "calibration_source": null,
  "calibration_note": "No held-out calibration dataset is bundled ...",
  "components": { "confidence": 0.61, "coverage": 0.86, "completeness": 0.667, "reliability": 0.68 },
  "explanation": "..."
}
```

`model_explanation` is SHAP when installed, exact linear attribution otherwise,
and always carries the warning that attributions are not source evidence:

```json
{
  "available": true,
  "method": "shap",
  "target_trl": 7,
  "baseline": -5.338,
  "prediction_probability": 0.494,
  "features": [
    { "feature": "evidence_total", "label": "Total evidence excerpts",
      "value": 13, "contribution": 6.18, "direction": "supports", "kind": "evidence" }
  ],
  "note": "...",
  "warning": "Model feature attributions explain the classifier's decision. They are not source evidence and must not be cited as document support."
}
```
