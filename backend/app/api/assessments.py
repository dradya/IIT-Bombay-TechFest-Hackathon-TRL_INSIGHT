"""Assessment endpoints: analyse, list, retrieve, delete, export and the
TRL INSIGHT 2.0 intelligence endpoints (graph, contradictions, roadmap,
questionnaire, reassessment, expert review, timeline, comparison)."""
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Response

from app.config.framework import get_framework
from app.core.database import (
    AssessmentDocumentRepository,
    AssessmentRepository,
    DocumentRepository,
    EventRepository,
    ReviewRepository,
    dump_json,
    new_id,
    utcnow,
)
from app.core.logging import get_logger
from app.schemas.assessment import (
    AnalyzeRequest,
    AssessmentListResponse,
    AssessmentResult,
    AssessmentSummary,
)
from app.schemas.intelligence import (
    AssessmentTimeline,
    CompareItem,
    CompareResponse,
    ContradictionReport,
    DocumentSummary,
    KnowledgeGraph,
    Questionnaire,
    ReassessRequest,
    ReviewCreate,
    ReviewListResponse,
    ReviewModel,
    TechnologyRoadmap,
    TimelineEvent,
)
from app.services.assessment_service import load_extracted, run_assessment
from app.services.multidoc import DocumentInput, supplemental_evidence
from app.services.report import content_disposition, report_bytes

logger = get_logger("api.assessments")

router = APIRouter(prefix="/api/assessments", tags=["assessments"])


def _review_status(decision: str | None) -> str:
    return {
        "accept": "accepted",
        "override": "overridden",
        "needs_more_evidence": "more_evidence_requested",
    }.get(decision or "", "unreviewed")


def _summary_from_row(
    row: dict[str, Any],
    framework: Any,
    latest_review: dict[str, Any] | None = None,
) -> AssessmentSummary:
    trl = row.get("predicted_trl")
    level_name = framework.level(trl).get("name", "") if trl else ""
    document_count = 1
    raw_documents = row.get("documents_json")
    if raw_documents:
        try:
            parsed = json.loads(raw_documents)
            if isinstance(parsed, list) and parsed:
                document_count = len(parsed)
        except (json.JSONDecodeError, TypeError):
            pass
    decision = (latest_review or {}).get("decision")
    return AssessmentSummary(
        id=row["id"],
        document_id=row.get("document_id"),
        technology_name=row.get("technology_name") or "",
        domain=row.get("domain") or "",
        organization=row.get("organization") or "",
        filename=row.get("filename") or "",
        predicted_trl=trl,
        level_name=level_name,
        confidence=row.get("confidence"),
        low_confidence=bool(row.get("low_confidence")),
        evidence_coverage=row.get("evidence_coverage"),
        model_mode=row.get("model_mode") or "",
        created_at=row.get("created_at") or "",
        document_count=document_count,
        uncertainty_overall=row.get("uncertainty_overall"),
        contradictions_total=int(row.get("contradictions_total") or 0),
        review_status=_review_status(decision),
        latest_review_decision=decision,
    )


def _load_document_inputs(document_ids: list[str]) -> list[DocumentInput]:
    """Load stored extracted text for each document id (order preserved)."""
    doc_repo = DocumentRepository()
    inputs: list[DocumentInput] = []
    for document_id in document_ids:
        document = doc_repo.get(document_id)
        if document is None:
            raise HTTPException(
                404,
                detail={
                    "detail": f"Document '{document_id}' was not found. Upload "
                              "documents first via POST /api/documents/upload.",
                    "code": "document_not_found",
                },
            )
        extracted_path = document.get("extracted_path")
        if not extracted_path:
            raise HTTPException(
                409,
                detail={
                    "detail": f"The extracted text for '{document.get('original_name')}' "
                              "is missing; please upload it again.",
                    "code": "extraction_missing",
                },
            )
        try:
            extracted = load_extracted(extracted_path)
        except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
            logger.error("Could not load extracted text for %s: %s", document_id, exc)
            raise HTTPException(
                409,
                detail={
                    "detail": "Stored extracted text could not be read; please "
                              "upload the document again.",
                    "code": "extraction_unreadable",
                },
            )
        inputs.append(
            DocumentInput(
                extracted=extracted,
                document_id=document["id"],
                filename=document.get("original_name") or extracted.filename,
                uploaded_at=document.get("uploaded_at"),
            )
        )
    return inputs


def _persist_assessment(
    *,
    result: dict[str, Any],
    assessment_id: str,
    created_at: str,
    metadata: dict[str, Any],
    document_ids: list[str],
    parent_assessment_id: str | None = None,
    reassessment_reason: str | None = None,
) -> None:
    prediction = result.get("prediction") or {}
    uncertainty = result.get("uncertainty") or {}
    contradictions = result.get("contradictions") or {}
    AssessmentRepository().create(
        id=assessment_id,
        document_id=document_ids[0] if document_ids else None,
        technology_name=metadata.get("technology_name", ""),
        domain=metadata.get("domain", ""),
        organization=metadata.get("organization", ""),
        description=metadata.get("description", ""),
        predicted_trl=prediction.get("predicted_trl"),
        confidence=prediction.get("confidence"),
        low_confidence=1 if prediction.get("low_confidence") else 0,
        evidence_coverage=prediction.get("evidence_coverage"),
        model_mode=prediction.get("model_mode"),
        result_json=dump_json(result),
        created_at=created_at,
        parent_assessment_id=parent_assessment_id,
        documents_json=dump_json(document_ids),
        reassessment_reason=reassessment_reason,
        uncertainty_overall=uncertainty.get("overall"),
        contradictions_total=int(contradictions.get("total", 0) or 0),
    )
    AssessmentDocumentRepository().link(assessment_id, result.get("documents") or [])


def _analyze_documents(
    *,
    request: AnalyzeRequest,
    document_ids: list[str],
    parent_assessment_id: str | None = None,
    reassessment_reason: str | None = None,
    supplemental: list[Any] | None = None,
) -> dict[str, Any]:
    framework = get_framework()
    inputs = _load_document_inputs(document_ids)
    metadata: dict[str, Any] = {
        "technology_name": request.technology_name.strip(),
        "domain": request.domain.strip(),
        "organization": request.organization.strip(),
        "description": request.description.strip(),
        "filename": (
            inputs[0].filename
            if len(inputs) == 1
            else f"{len(inputs)} documents"
        ),
        "uploaded_at": inputs[0].uploaded_at,
    }

    assessment_id = new_id("asm_")
    created_at = utcnow()
    try:
        result = run_assessment(
            metadata=metadata,
            framework=framework,
            assessment_id=assessment_id,
            document_id=inputs[0].document_id,
            created_at=created_at,
            documents=inputs,
            supplemental=supplemental,
            parent_assessment_id=parent_assessment_id,
            reassessment_reason=reassessment_reason,
        )
    except Exception as exc:  # noqa: BLE001 - surface as a controlled 500
        logger.exception("Assessment pipeline failed for %s", document_ids)
        raise HTTPException(
            500,
            detail={"detail": f"Analysis failed: {exc}", "code": "analysis_failed"},
        )

    result["framework_version"] = framework.version
    _persist_assessment(
        result=result,
        assessment_id=assessment_id,
        created_at=created_at,
        metadata=metadata,
        document_ids=document_ids,
        parent_assessment_id=parent_assessment_id,
        reassessment_reason=reassessment_reason,
    )
    return result


@router.post("/analyze", response_model=AssessmentResult)
def analyze(request: AnalyzeRequest) -> dict[str, Any]:
    """Run the full multi-document -> evidence -> TRL pipeline."""
    document_ids: list[str] = []
    for value in [request.document_id, *request.document_ids]:
        value = (value or "").strip()
        if value and value not in document_ids:
            document_ids.append(value)
    if not document_ids:
        raise HTTPException(
            422,
            detail={
                "detail": "At least one document id is required.",
                "code": "validation_error",
            },
        )

    result = _analyze_documents(request=request, document_ids=document_ids)
    EventRepository().create(
        assessment_id=result["id"],
        kind="created",
        title="Assessment created",
        description=(
            f"Analyzed {len(document_ids)} document(s); predicted TRL "
            f"{result['prediction']['predicted_trl']}."
        ),
        metadata_json=dump_json(
            {
                "document_ids": document_ids,
                "predicted_trl": result["prediction"]["predicted_trl"],
                "confidence": result["prediction"]["confidence"],
            }
        ),
    )
    return result


@router.get("", response_model=AssessmentListResponse)
def list_assessments(
    search: str | None = Query(None, description="Search name/domain/org/description"),
    domain: str | None = Query(None),
    trl: int | None = Query(None, ge=1, le=9),
    trl_min: int | None = Query(None, ge=1, le=9),
    trl_max: int | None = Query(None, ge=1, le=9),
    confidence_min: float | None = Query(None, ge=0.0, le=1.0),
    confidence_max: float | None = Query(None, ge=0.0, le=1.0),
    low_confidence: bool | None = Query(None),
    review_status: str | None = Query(
        None,
        pattern="^(unreviewed|accepted|overridden|more_evidence_requested)$",
    ),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    sort: str = Query(
        "created_desc",
        pattern="^(created_desc|created_asc|trl_desc|trl_asc|confidence_desc|confidence_asc|coverage_desc)$",
    ),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> AssessmentListResponse:
    framework = get_framework()
    repo = AssessmentRepository()
    reviews = ReviewRepository()
    if date_from and len(date_from) == 10:
        date_from = f"{date_from}T00:00:00"
    if date_to and len(date_to) == 10:
        date_to = f"{date_to}T23:59:59.999999"
    filters = dict(
        search=search, domain=domain, trl=trl, trl_min=trl_min, trl_max=trl_max,
        review_status=review_status, date_from=date_from, date_to=date_to,
        confidence_min=confidence_min, confidence_max=confidence_max,
        low_confidence=low_confidence,
    )
    rows = repo.list(**filters, sort=sort, limit=limit, offset=offset)
    total = repo.summary_rows(**filters)
    items = []
    for row in rows:
        try:
            latest = reviews.latest(row["id"])
        except Exception:  # pragma: no cover - review lookup is non-critical
            latest = None
        items.append(_summary_from_row(row, framework, latest))
    return AssessmentListResponse(items=items, total=total)


def _load_assessment(assessment_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    repo = AssessmentRepository()
    record = repo.get(assessment_id)
    if record is None:
        raise HTTPException(
            404, detail={"detail": "Assessment not found.", "code": "not_found"}
        )
    try:
        result = json.loads(record["result_json"])
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        logger.error("Corrupt assessment record %s: %s", assessment_id, exc)
        raise HTTPException(
            500,
            detail={"detail": "Stored assessment is corrupted.", "code": "corrupt_record"},
        )
    return record, result


def _require_block(result: dict[str, Any], key: str, label: str) -> Any:
    value = result.get(key)
    if value is None:
        raise HTTPException(
            409,
            detail={
                "detail": f"{label} is not available for this assessment "
                          "(it was created before TRL INSIGHT 2.0). Re-run the "
                          "analysis to generate it.",
                "code": "not_available",
            },
        )
    return value


@router.get("/compare", response_model=CompareResponse)
def compare_assessments(
    ids: str = Query(..., description="Comma-separated assessment ids (2-3)")
) -> CompareResponse:
    """Compare two or three stored assessments side by side."""
    assessment_ids = [value.strip() for value in ids.split(",") if value.strip()]
    if not 2 <= len(assessment_ids) <= 3:
        raise HTTPException(
            422,
            detail={
                "detail": "Select 2-3 assessments to compare.",
                "code": "validation_error",
            },
        )

    items: list[CompareItem] = []
    for assessment_id in assessment_ids:
        record, result = _load_assessment(assessment_id)
        prediction = result.get("prediction") or {}
        summary = result.get("evidence_summary") or {}
        contradictions = result.get("contradictions") or {}
        uncertainty = result.get("uncertainty") or {}
        documents: list[DocumentSummary] = []
        for document in result.get("documents") or []:
            try:
                documents.append(DocumentSummary(**document))
            except Exception:  # pragma: no cover - legacy document payload
                continue
        items.append(
            CompareItem(
                id=record["id"],
                technology_name=record.get("technology_name") or "",
                predicted_trl=record.get("predicted_trl"),
                confidence=record.get("confidence"),
                evidence_coverage=record.get("evidence_coverage"),
                uncertainty_overall=(
                    record.get("uncertainty_overall")
                    if record.get("uncertainty_overall") is not None
                    else uncertainty.get("overall")
                ),
                documents=documents,
                milestones=result.get("milestones") or [],
                evidence_total=int(summary.get("total", 0) or 0),
                contradictions_total=int(contradictions.get("total", 0) or 0),
                created_at=record.get("created_at") or "",
            )
        )
    return CompareResponse(
        items=items,
        note=(
            "Values are taken directly from each stored assessment. A higher TRL "
            "is not automatically better: check confidence, coverage, "
            "contradictions and the underlying evidence."
        ),
    )


@router.get("/{assessment_id}", response_model=AssessmentResult)
def get_assessment(assessment_id: str) -> dict[str, Any]:
    _, result = _load_assessment(assessment_id)
    return result


@router.delete("/{assessment_id}")
def delete_assessment(assessment_id: str) -> dict[str, Any]:
    deleted = AssessmentRepository().delete(assessment_id)
    if not deleted:
        raise HTTPException(
            404, detail={"detail": "Assessment not found.", "code": "not_found"}
        )
    return {"deleted": True, "id": assessment_id}


@router.get("/{assessment_id}/documents", response_model=list[DocumentSummary])
def assessment_documents(assessment_id: str) -> list[DocumentSummary]:
    record, result = _load_assessment(assessment_id)
    documents = result.get("documents") or []
    if documents:
        out: list[DocumentSummary] = []
        for document in documents:
            try:
                out.append(DocumentSummary(**document))
            except Exception:  # pragma: no cover - legacy payload
                continue
        return out
    # Legacy single-document assessments: derive the summary from the stored link.
    links = AssessmentDocumentRepository().list(assessment_id)
    if links:
        return [
            DocumentSummary(
                document_id=link.get("document_id"),
                filename=link.get("filename") or "",
                page_count=int(link.get("page_count") or 0),
                char_count=int(link.get("char_count") or 0),
                uploaded_at=link.get("uploaded_at"),
            )
            for link in links
        ]
    filename = (result.get("metadata") or {}).get("filename") or ""
    processing = result.get("processing") or {}
    if not filename:
        return []
    return [
        DocumentSummary(
            document_id=record.get("document_id"),
            filename=filename,
            page_count=int(processing.get("pages", 0) or 0),
            char_count=0,
            uploaded_at=None,
            extraction_method=str(processing.get("extraction_method", "text")),
        )
    ]


@router.get("/{assessment_id}/graph", response_model=KnowledgeGraph)
def assessment_graph(assessment_id: str) -> KnowledgeGraph:
    _, result = _load_assessment(assessment_id)
    return KnowledgeGraph(**_require_block(result, "graph", "Evidence graph"))


@router.get("/{assessment_id}/contradictions", response_model=ContradictionReport)
def assessment_contradictions(assessment_id: str) -> ContradictionReport:
    _, result = _load_assessment(assessment_id)
    return ContradictionReport(
        **_require_block(result, "contradictions", "Contradiction analysis")
    )


@router.get("/{assessment_id}/roadmap", response_model=TechnologyRoadmap)
def assessment_roadmap(assessment_id: str) -> TechnologyRoadmap:
    _, result = _load_assessment(assessment_id)
    return TechnologyRoadmap(**_require_block(result, "roadmap", "Technology roadmap"))


@router.get("/{assessment_id}/questionnaire", response_model=Questionnaire)
def assessment_questionnaire(assessment_id: str) -> Questionnaire:
    _, result = _load_assessment(assessment_id)
    return Questionnaire(
        **_require_block(result, "questionnaire", "Missing-evidence questionnaire")
    )


def _review_payload(assessment_id: str) -> ReviewListResponse:
    record, result = _load_assessment(assessment_id)
    rows = ReviewRepository().list(assessment_id)
    items: list[ReviewModel] = []
    for row in rows:
        try:
            evidence_ids = json.loads(row.get("evidence_ids_json") or "[]")
        except (json.JSONDecodeError, TypeError):
            evidence_ids = []
        items.append(
            ReviewModel(
                id=row["id"],
                assessment_id=row["assessment_id"],
                reviewer_name=row["reviewer_name"],
                decision=row["decision"],
                reviewed_trl=row.get("reviewed_trl"),
                ai_trl=row.get("ai_trl"),
                notes=row.get("notes") or "",
                evidence_ids=evidence_ids if isinstance(evidence_ids, list) else [],
                created_at=row["created_at"],
            )
        )
    prediction = result.get("prediction") or {}
    latest = items[-1] if items else None
    return ReviewListResponse(
        assessment_id=assessment_id,
        items=items,
        total=len(items),
        ai_prediction={
            "predicted_trl": prediction.get("predicted_trl"),
            "confidence": prediction.get("confidence"),
            "evidence_coverage": prediction.get("evidence_coverage"),
            "model_mode": prediction.get("model_mode"),
            "created_at": record.get("created_at"),
            "immutable": True,
        },
        latest_decision=latest.decision if latest else None,
        review_status=_review_status(latest.decision if latest else None),
    )


@router.get("/{assessment_id}/reviews", response_model=ReviewListResponse)
def list_reviews(assessment_id: str) -> ReviewListResponse:
    return _review_payload(assessment_id)


@router.post("/{assessment_id}/reviews", response_model=ReviewModel)
def create_review(assessment_id: str, request: ReviewCreate) -> ReviewModel:
    record, result = _load_assessment(assessment_id)
    ai_trl = (result.get("prediction") or {}).get("predicted_trl")
    if request.decision == "override" and request.reviewed_trl is None:
        raise HTTPException(
            422,
            detail={
                "detail": "An override review must include reviewed_trl (1-9).",
                "code": "validation_error",
            },
        )
    row = ReviewRepository().create(
        assessment_id=assessment_id,
        reviewer_name=request.reviewer_name.strip(),
        decision=request.decision,
        reviewed_trl=request.reviewed_trl,
        ai_trl=ai_trl,
        notes=request.notes.strip(),
        evidence_ids_json=dump_json(request.evidence_ids),
    )
    EventRepository().create(
        assessment_id=assessment_id,
        kind="review",
        title=f"Expert review: {request.decision.replace('_', ' ')}",
        description=request.notes.strip() or "Review recorded.",
        actor=request.reviewer_name.strip(),
        metadata_json=dump_json(
            {
                "decision": request.decision,
                "reviewed_trl": request.reviewed_trl,
                "ai_trl": ai_trl,
                "evidence_ids": request.evidence_ids,
            }
        ),
    )
    return ReviewModel(
        id=row["id"],
        assessment_id=assessment_id,
        reviewer_name=row["reviewer_name"],
        decision=row["decision"],
        reviewed_trl=row.get("reviewed_trl"),
        ai_trl=row.get("ai_trl"),
        notes=row.get("notes") or "",
        evidence_ids=request.evidence_ids,
        created_at=row["created_at"],
    )


@router.post("/{assessment_id}/reassess", response_model=AssessmentResult)
def reassess(assessment_id: str, request: ReassessRequest) -> dict[str, Any]:
    """Re-run an assessment with self-reported questionnaire answers.

    The original AI prediction is never overwritten; a new assessment is stored
    with ``parent_assessment_id`` pointing at the original.
    """
    framework = get_framework()
    parent, _parent_result = _load_assessment(assessment_id)

    links = AssessmentDocumentRepository().list(assessment_id)
    document_ids = [
        str(link["document_id"])
        for link in links
        if link.get("document_id")
    ]
    if not document_ids and parent.get("document_id"):
        document_ids = [str(parent["document_id"])]
    if not document_ids:
        raise HTTPException(
            409,
            detail={
                "detail": "The source documents for this assessment are no "
                          "longer available, so it cannot be reassessed.",
                "code": "documents_unavailable",
            },
        )

    answers = [answer for answer in request.answers if answer.status != "unknown"]
    supplemental = supplemental_evidence(answers, framework, assessment_id)
    if answers and not supplemental:
        raise HTTPException(
            422,
            detail={
                "detail": "No usable answers were supplied. Add an evidence note "
                          "or source reference for at least one milestone.",
                "code": "validation_error",
            },
        )

    analyze_request = AnalyzeRequest(
        document_ids=document_ids,
        technology_name=parent.get("technology_name") or "",
        domain=parent.get("domain") or "",
        organization=parent.get("organization") or "",
        description=parent.get("description") or "",
    )
    reason = request.reason.strip() or "Expert reassessment"
    result = _analyze_documents(
        request=analyze_request,
        document_ids=document_ids,
        parent_assessment_id=assessment_id,
        reassessment_reason=reason,
        supplemental=supplemental,
    )

    EventRepository().create(
        assessment_id=result["id"],
        kind="reassessment",
        title="Reassessment created",
        description=reason,
        actor=request.reviewer_name.strip() or None,
        metadata_json=dump_json(
            {
                "parent_assessment_id": assessment_id,
                "answers": len(answers),
                "self_reported_evidence": len(supplemental),
                "predicted_trl": result["prediction"]["predicted_trl"],
            }
        ),
    )
    EventRepository().create(
        assessment_id=assessment_id,
        kind="reassessment",
        title="Reassessment performed",
        description=reason,
        actor=request.reviewer_name.strip() or None,
        metadata_json=dump_json(
            {
                "child_assessment_id": result["id"],
                "predicted_trl": result["prediction"]["predicted_trl"],
            }
        ),
    )
    return result


@router.get("/{assessment_id}/timeline", response_model=AssessmentTimeline)
def assessment_timeline(assessment_id: str) -> AssessmentTimeline:
    record, _ = _load_assessment(assessment_id)
    rows = EventRepository().list(assessment_id)
    events: list[TimelineEvent] = []
    for row in rows:
        try:
            metadata = json.loads(row.get("metadata_json") or "{}")
        except (json.JSONDecodeError, TypeError):
            metadata = {}
        events.append(
            TimelineEvent(
                id=row["id"],
                kind=row["kind"],
                title=row["title"],
                description=row.get("description") or "",
                at=row["at"],
                actor=row.get("actor"),
                metadata=metadata if isinstance(metadata, dict) else {},
            )
        )
    if not any(event.kind == "created" for event in events):
        events.insert(
            0,
            TimelineEvent(
                id=f"created_{assessment_id}",
                kind="created",
                title="Assessment created",
                description="Creation timestamp from the stored assessment record.",
                at=record.get("created_at") or utcnow(),
                metadata={"derived_from_record": True},
            ),
        )
    events.sort(key=lambda event: event.at)
    return AssessmentTimeline(assessment_id=assessment_id, events=events)


@router.get("/{assessment_id}/report")
def download_report(assessment_id: str) -> Response:
    """PDF assessment report (generated on demand)."""
    _, result = _load_assessment(assessment_id)
    try:
        payload, media_type, filename = report_bytes(result, "pdf")
    except Exception as exc:  # noqa: BLE001
        logger.exception("PDF generation failed for %s", assessment_id)
        raise HTTPException(
            500,
            detail={"detail": f"PDF generation failed: {exc}", "code": "report_failed"},
        )
    return Response(
        content=payload,
        media_type=media_type,
        headers={
            "Content-Disposition": content_disposition(filename),
            "Content-Length": str(len(payload)),
            "Cache-Control": "no-store",
        },
    )


@router.get("/{assessment_id}/json")
def download_json(assessment_id: str) -> Response:
    """Canonical JSON assessment output."""
    _, result = _load_assessment(assessment_id)
    payload, media_type, filename = report_bytes(result, "json")
    return Response(
        content=payload,
        media_type=media_type,
        headers={
            "Content-Disposition": content_disposition(filename),
            "Content-Length": str(len(payload)),
            "Cache-Control": "no-store",
        },
    )
