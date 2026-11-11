"""Overview, TRL reference and model-performance endpoints."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from app.config.framework import get_framework
from app.core.database import AssessmentRepository, ReviewRepository
from app.ml.predictor import read_model_metadata, read_performance
from app.schemas.assessment import (
    ActivityItem,
    AssessmentSummary,
    ConfidenceBuckets,
    CoverageBuckets,
    DomainCount,
    OverviewResponse,
    ReviewSummary,
    TrlCount,
)
from app.schemas.model import ModelPerformanceResponse, TRLReferenceResponse
from app.services.capabilities import get_capabilities

router = APIRouter(prefix="/api", tags=["meta"])


@router.get("/system/capabilities")
def capabilities() -> dict[str, Any]:
    """Actual availability of optional OSS integrations and fallbacks."""
    return get_capabilities()


@router.get("/overview", response_model=OverviewResponse)
def overview(
    domain: str | None = Query(None),
    date_from: str | None = Query(None, description="ISO date or datetime (inclusive)"),
    date_to: str | None = Query(None, description="ISO date or datetime (inclusive)"),
) -> OverviewResponse:
    framework = get_framework()
    repo = AssessmentRepository()
    reviews = ReviewRepository()

    # A bare date is expanded so the whole day is included.
    if date_from and len(date_from) == 10:
        date_from = f"{date_from}T00:00:00"
    if date_to and len(date_to) == 10:
        date_to = f"{date_to}T23:59:59.999999"

    stats = repo.stats(domain=domain, date_from=date_from, date_to=date_to)

    if stats["total"] == 0:
        return OverviewResponse(has_data=False, domains=repo.domains())

    buckets = repo.confidence_buckets(
        domain=domain, date_from=date_from, date_to=date_to
    )
    coverage = repo.coverage_buckets(
        domain=domain, date_from=date_from, date_to=date_to
    )
    review_counts = repo.review_counts(
        domain=domain, date_from=date_from, date_to=date_to
    )
    recent_rows = repo.list(
        domain=domain, date_from=date_from, date_to=date_to, limit=8
    )

    def summary(row: dict[str, Any]) -> AssessmentSummary:
        trl = row.get("predicted_trl")
        document_count = 1
        raw_documents = row.get("documents_json")
        if raw_documents:
            try:
                import json as _json

                parsed = _json.loads(raw_documents)
                if isinstance(parsed, list) and parsed:
                    document_count = len(parsed)
            except (TypeError, ValueError):
                pass
        try:
            latest = reviews.latest(row["id"])
        except Exception:  # pragma: no cover - review lookup is non-critical
            latest = None
        decision = (latest or {}).get("decision")
        review_status = {
            "accept": "accepted",
            "override": "overridden",
            "needs_more_evidence": "more_evidence_requested",
        }.get(decision or "", "unreviewed")
        return AssessmentSummary(
            id=row["id"],
            document_id=row.get("document_id"),
            technology_name=row.get("technology_name") or "",
            domain=row.get("domain") or "",
            organization=row.get("organization") or "",
            filename=row.get("filename") or "",
            predicted_trl=trl,
            level_name=framework.level(trl).get("name", "") if trl else "",
            confidence=row.get("confidence"),
            low_confidence=bool(row.get("low_confidence")),
            evidence_coverage=row.get("evidence_coverage"),
            model_mode=row.get("model_mode") or "",
            created_at=row.get("created_at") or "",
            document_count=document_count,
            uncertainty_overall=row.get("uncertainty_overall"),
            contradictions_total=int(row.get("contradictions_total") or 0),
            review_status=review_status,
            latest_review_decision=decision,
        )

    distribution = [
        TrlCount(trl=level, count=int(stats["distribution"].get(level, 0)))
        for level in range(1, 10)
    ]
    activity = [
        ActivityItem(
            id=row["id"],
            technology_name=row.get("technology_name") or row.get("filename") or "Untitled",
            predicted_trl=row.get("predicted_trl"),
            confidence=row.get("confidence"),
            created_at=row.get("created_at") or "",
        )
        for row in recent_rows[:10]
    ]

    return OverviewResponse(
        has_data=True,
        total_assessments=int(stats["total"]),
        average_trl=round(float(stats["avg_trl"]), 2) if stats["avg_trl"] else None,
        average_confidence=(
            round(float(buckets["average"]), 3) if buckets["average"] else None
        ),
        distribution=distribution,
        confidence=ConfidenceBuckets(
            high=int(buckets["high"]),
            medium=int(buckets["medium"]),
            low=int(buckets["low"]),
            average=round(float(buckets["average"]), 3) if buckets["average"] else None,
        ),
        coverage=CoverageBuckets(
            high=int(coverage["high"]),
            medium=int(coverage["medium"]),
            low=int(coverage["low"]),
            average=round(float(coverage["average"]), 3) if coverage["average"] else None,
        ),
        domain_distribution=[
            DomainCount(domain=str(row["domain"]), count=int(row["n"]))
            for row in repo.domain_distribution(
                domain=domain, date_from=date_from, date_to=date_to
            )
        ],
        reviews=ReviewSummary(**review_counts),
        recent=[summary(row) for row in recent_rows],
        activity=activity,
        domains=repo.domains(),
    )


@router.get("/trl/reference", response_model=TRLReferenceResponse)
def trl_reference() -> TRLReferenceResponse:
    framework = get_framework()
    return TRLReferenceResponse(
        version=framework.version,
        meta=framework.meta,
        levels=framework.levels,
        milestones=framework.milestones,
        evidence_categories=framework.categories,
        evidence_statuses=framework.evidence_statuses,
        assessment_rules=framework.rules,
    )


@router.get("/model/performance", response_model=ModelPerformanceResponse)
def model_performance() -> ModelPerformanceResponse:
    """Real metrics from the last evaluation run, or an explicit empty state."""
    metrics = read_performance()
    if not metrics:
        return ModelPerformanceResponse(
            available=False,
            mode="unavailable",
            note=(
                "No trained model or evaluation data is available yet. "
                "Metrics are never fabricated. To produce genuine metrics, "
                "place a labelled dataset and run: "
                "python training/prepare_data.py --synthetic "
                "&& python training/train_model.py "
                "&& python training/evaluate_model.py"
            ),
        )

    metadata = read_model_metadata() or {}
    per_class = {
        str(label): value
        for label, value in (metrics.get("per_class") or {}).items()
    }
    return ModelPerformanceResponse(
        available=bool(metrics.get("available", True)),
        mode=metrics.get("mode", "trained_evaluation"),
        note=metrics.get("note", ""),
        model_name=metrics.get("model_name") or metadata.get("model_name"),
        model_version=metrics.get("model_version") or metadata.get("model_version"),
        trained_at=metrics.get("trained_at") or metadata.get("trained_at"),
        dataset_type=metrics.get("dataset_type") or metadata.get("dataset_type"),
        dataset_source=metrics.get("dataset_source") or metadata.get("dataset_source"),
        n_train=metrics.get("n_train"),
        n_test=metrics.get("n_test"),
        class_distribution=metrics.get("class_distribution") or {},
        metrics=metrics.get("metrics") or {},
        per_class=per_class,
        confusion_matrix=metrics.get("confusion_matrix"),
        classification_report=metrics.get("classification_report"),
    )
