"""Assessment orchestration: runs the full pipeline end to end.

    ingestion -> cleaning -> evidence extraction -> features
              -> hybrid classification -> verification -> gap analysis

The orchestrator returns a structure that exactly matches the
``AssessmentResult`` API schema, and is the single entry point used by
both the REST API and the CLI predictor.
"""
from __future__ import annotations

import json
import time
from typing import Any

from app.config.framework import Framework, get_framework
from app.core.logging import get_logger
from app.ml.explain import explain_prediction
from app.ml.predictor import ModelBundle, load_model_bundle, predict_hybrid
from app.ml.rules import assess_rules, milestone_summary_for_display
from app.services.contradictions import detect_contradictions
from app.services.document_processing import ProcessedDocument
from app.services.evidence import (
    STATUS_CONFIRMED,
    STATUS_CONTRADICTED,
    STATUS_PROPOSED,
    STATUS_UNCLEAR,
    EvidenceRecord,
    evidence_by_category,
)
from app.services.gap_analysis import build_gap_analysis
from app.services.ingestion import ExtractedDocument
from app.services.knowledge_graph import build_knowledge_graph
from app.services.multidoc import DocumentInput, merge_documents
from app.services.questionnaire import build_questionnaire
from app.services.roadmap import build_roadmap
from app.services.semantic import rank_evidence
from app.services.uncertainty import build_uncertainty
from app.services.verification import verify_prediction

logger = get_logger("assessment")

CONFIDENCE_HIGH = 0.70
CONFIDENCE_MEDIUM = 0.45


def _evidence_summary(
    evidence: list[EvidenceRecord],
    framework: Framework,
    predicted_trl: int,
    milestone_status: dict[str, str],
    *,
    raw_total: int | None = None,
    duplicates: int = 0,
    outdated: int = 0,
    self_reported: int = 0,
) -> dict[str, Any]:
    total = len(evidence)
    counts = {
        STATUS_CONFIRMED: sum(1 for e in evidence if e.status == STATUS_CONFIRMED),
        STATUS_PROPOSED: sum(1 for e in evidence if e.status == STATUS_PROPOSED),
        STATUS_CONTRADICTED: sum(1 for e in evidence if e.status == STATUS_CONTRADICTED),
        STATUS_UNCLEAR: sum(1 for e in evidence if e.status == STATUS_UNCLEAR),
    }
    chain = framework.milestones_up_to(predicted_trl)
    confirmed_chain = sum(
        1 for m in chain if milestone_status.get(m["id"]) == STATUS_CONFIRMED
    )
    coverage = (confirmed_chain / len(chain)) if chain else 0.0
    return {
        "total": total,
        **counts,
        "by_category": evidence_by_category(evidence, framework),
        "coverage": round(coverage, 3),
        "raw_total": total if raw_total is None else raw_total,
        "duplicates": duplicates,
        "outdated": outdated,
        "self_reported": self_reported,
    }


def run_assessment(
    extracted: ExtractedDocument | None = None,
    metadata: dict[str, Any] | None = None,
    framework: Framework | None = None,
    bundle: ModelBundle | None = None,
    assessment_id: str = "",
    document_id: str | None = None,
    created_at: str = "",
    *,
    documents: list[DocumentInput] | None = None,
    supplemental: list[EvidenceRecord] | None = None,
    parent_assessment_id: str | None = None,
    reassessment_reason: str | None = None,
) -> dict[str, Any]:
    """Execute the complete analysis pipeline.

    ``extracted`` keeps the original single-document call signature working.
    Pass ``documents`` to assess one or more documents together; duplicate
    claims across them are counted once. ``supplemental`` carries clearly
    labelled self-reported questionnaire evidence for reassessments.
    """
    started = time.perf_counter()
    framework = framework or get_framework()
    metadata = metadata or {}

    if documents is None:
        if extracted is None:
            raise ValueError("run_assessment requires an extracted document")
        source_name = metadata.get("filename") or extracted.filename
        documents = [
            DocumentInput(
                extracted=extracted,
                document_id=document_id,
                filename=source_name,
                uploaded_at=metadata.get("uploaded_at"),
            )
        ]
    if not documents:
        raise ValueError("run_assessment requires at least one document")

    # Steps 2 & 3 - cleaning, segmentation and cross-document evidence merge.
    merge = merge_documents(documents, framework)
    evidence: list[EvidenceRecord] = list(merge.unique_evidence)
    if supplemental:
        evidence.extend(supplemental)
    all_evidence: list[EvidenceRecord] = list(merge.all_evidence)
    if supplemental:
        all_evidence.extend(supplemental)

    # Rules over unique milestone evidence (duplicates never double-count).
    rule_result = assess_rules(evidence, framework)

    # Optional semantic retrieval ranks excerpts against milestones. It never
    # changes the conservative status assigned above.
    retrieval = rank_evidence(evidence, framework)

    # Steps 4 & 5 - features + hybrid classification
    if bundle is None:
        bundle = load_model_bundle()
    prediction = predict_hybrid(
        merge.processed, evidence, rule_result, framework, bundle
    )

    # Step 6 - verification
    verification = verify_prediction(
        prediction.predicted_trl, evidence, rule_result, framework
    )

    # Step 7 - gap analysis
    gap = build_gap_analysis(prediction.predicted_trl, rule_result, framework)

    level_info = framework.level(prediction.predicted_trl)
    milestone_status = {m.id: m.status for m in rule_result.milestones}

    uploaded_by_document = {
        document.document_id: document.uploaded_at
        for document in documents
        if document.document_id
    }
    contradictions = detect_contradictions(
        evidence, all_evidence, framework, uploaded_by_document
    )

    extraction_warnings: list[str] = []
    for document in documents:
        extraction_warnings.extend(document.extracted.warnings or [])

    uncertainty = build_uncertainty(
        prediction,
        rule_result,
        evidence,
        framework,
        documents=merge.documents,
        contradictions_total=int(contradictions.get("total", 0) or 0),
        duplicates=merge.duplicates,
        extraction_warnings=extraction_warnings,
    )

    technology_name = str(metadata.get("technology_name") or "")
    roadmap = build_roadmap(gap, framework, prediction.predicted_trl)
    questionnaire = build_questionnaire(
        assessment_id, rule_result, framework, gap
    )
    graph = build_knowledge_graph(
        technology_name,
        merge.documents,
        evidence,
        framework,
        contradictions,
    )
    model_explanation = explain_prediction(
        bundle,
        merge.processed,
        evidence,
        rule_result,
        framework,
        prediction.predicted_trl,
        prediction.ml_probability,
    )

    source_name = metadata.get("filename") or (
        documents[0].filename or documents[0].extracted.filename
    )
    methods = sorted(
        {document.extracted.method for document in documents if document.extracted.method}
    )
    raw_total = len(all_evidence)

    duration_ms = int((time.perf_counter() - started) * 1000)
    self_reported = sum(
        1 for item in evidence if item.evidence_type == "self_reported"
    )
    logger.info(
        "Assessment complete: predicted TRL=%d confidence=%.2f coverage=%.2f "
        "(%d unique/%d raw evidence items, %d document(s), %d contradictions, "
        "%d ms)",
        prediction.predicted_trl,
        prediction.confidence,
        prediction.evidence_coverage,
        len(evidence),
        raw_total,
        len(documents),
        int(contradictions.get("total", 0) or 0),
        duration_ms,
    )

    return {
        "id": assessment_id,
        "document_id": document_id,
        "created_at": created_at,
        "metadata": {
            "technology_name": technology_name,
            "domain": metadata.get("domain", "") or "",
            "organization": metadata.get("organization", "") or "",
            "description": metadata.get("description", "") or "",
            "filename": source_name,
        },
        "prediction": {
            "predicted_trl": prediction.predicted_trl,
            "level_name": level_info.get("name", ""),
            "level_category": level_info.get("category", ""),
            "level_description": level_info.get("description", ""),
            "confidence": prediction.confidence,
            "low_confidence": prediction.low_confidence,
            "evidence_coverage": prediction.evidence_coverage,
            "probabilities": prediction.probabilities,
            "alternatives": prediction.alternatives,
            "rule_level": prediction.rule_level,
            "ml_level": prediction.ml_level,
            "model_mode": prediction.model_mode,
            "model_probability": prediction.ml_probability,
            "warnings": prediction.warnings,
            "method": prediction.method,
        },
        "evidence": [e.to_dict() for e in evidence],
        "evidence_summary": _evidence_summary(
            evidence,
            framework,
            prediction.predicted_trl,
            milestone_status,
            raw_total=raw_total,
            duplicates=merge.duplicates,
            outdated=merge.outdated,
            self_reported=self_reported,
        ),
        "milestones": milestone_summary_for_display(rule_result, evidence),
        "verification": verification,
        "gap_analysis": gap,
        "model": {
            "available": bundle is not None,
            "name": bundle.model_name if bundle else "",
            "version": bundle.model_version if bundle else "",
            "mode": prediction.model_mode,
            "dataset_type": bundle.dataset_type if bundle else "none",
            "trained_at": bundle.trained_at if bundle else None,
        },
        "processing": {
            "extraction_method": "+".join(methods) or "text",
            "pages": sum(document.extracted.page_count for document in documents),
            "sentences": len(merge.processed.sentences),
            "evidence_items": len(evidence),
            "documents": len(documents),
            "duplicates": merge.duplicates,
            "outdated": merge.outdated,
            "ocr_used": any(document.extracted.ocr_used for document in documents),
            "duration_ms": duration_ms,
        },
        # --- additive 2.0 intelligence (all computed from real inputs) ---
        "documents": merge.documents,
        "retrieval": retrieval,
        "contradictions": contradictions,
        "graph": graph,
        "uncertainty": uncertainty,
        "roadmap": roadmap,
        "questionnaire": questionnaire,
        "model_explanation": model_explanation,
        "parent_assessment_id": parent_assessment_id,
        "reassessment_reason": reassessment_reason,
    }


# ----------------------------------------------------------------------
# Extracted document (de)serialisation - used to persist uploads
# ----------------------------------------------------------------------
def extracted_to_dict(extracted: ExtractedDocument) -> dict[str, Any]:
    return {
        "filename": extracted.filename,
        "file_type": extracted.file_type,
        "units": [
            {"page": u.page, "locator": u.locator, "text": u.text, "chars": u.chars}
            for u in extracted.units
        ],
        "headings": extracted.headings,
        "table_count": extracted.table_count,
        "metadata": extracted.metadata,
        "warnings": extracted.warnings,
        "method": extracted.method,
        "ocr_used": extracted.ocr_used,
    }


def extracted_from_dict(data: dict[str, Any]) -> ExtractedDocument:
    from app.services.ingestion import PageUnit

    return ExtractedDocument(
        filename=data.get("filename", ""),
        file_type=data.get("file_type", "txt"),
        units=[
            PageUnit(
                page=u.get("page"),
                locator=u.get("locator", ""),
                text=u.get("text", ""),
                chars=int(u.get("chars", 0) or 0),
            )
            for u in data.get("units", [])
        ],
        headings=list(data.get("headings", [])),
        table_count=int(data.get("table_count", 0) or 0),
        metadata=dict(data.get("metadata", {})),
        warnings=list(data.get("warnings", [])),
        method=data.get("method", "text"),
        ocr_used=bool(data.get("ocr_used", False)),
    )


def save_extracted(payload: dict[str, Any], path: str) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False)


def load_extracted(path: str) -> ExtractedDocument:
    with open(path, "r", encoding="utf-8") as fh:
        return extracted_from_dict(json.load(fh))
