"""Assessment, prediction, evidence, gap-analysis and overview schemas.

These models define the JSON contract of the API and are also used to
serialise stored assessment results.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.intelligence import (
    ContradictionReport,
    DocumentSummary,
    KnowledgeGraph,
    ModelExplanation,
    Questionnaire,
    RetrievalInfo,
    TechnologyRoadmap,
    Uncertainty,
)

EvidenceStatus = Literal[
    "confirmed", "proposed", "contradicted", "unclear"
]
MilestoneStatusValue = Literal[
    "confirmed", "not_found", "contradicted", "unclear"
]
Stance = Literal["supporting", "contradicting", "insufficient"]


# ----------------------------------------------------------------------
# Evidence
# ----------------------------------------------------------------------
class EvidenceItem(BaseModel):
    id: str
    statement: str = Field(description="Exact excerpt from the source document")
    category: str
    category_label: str
    status: EvidenceStatus
    stance: Stance
    source_document: str
    page_number: int | None = Field(
        default=None,
        description="1-based page number; null when the format has no pages "
                    "(DOCX/TXT) and a line/section locator is used instead",
    )
    location: str = Field(default="", description="Section / paragraph / line locator")
    section: str = ""
    milestone: str | None = None
    milestone_label: str | None = None
    supports_milestone: bool = Field(
        default=False,
        description="True when the excerpt matches the defining indicators of "
                    "its milestone in a completed (non-future) statement",
    )
    relevance: float = Field(default=0.0, ge=0.0, le=1.0)
    is_proposed: bool = False
    future_tense: bool = False
    negated: bool = False
    # Additive TRL INSIGHT 2.0 provenance / graph fields
    document_id: str | None = None
    evidence_type: Literal["document", "self_reported"] = "document"
    duplicate_group: str | None = None
    duplicate_of: str | None = None
    duplicate_count: int = 1
    superseded_by: str | None = None
    outdated: bool = False
    semantic_similarity: float | None = None
    semantic_milestone: str | None = None


class EvidenceCategoryCount(BaseModel):
    category: str
    label: str
    count: int
    confirmed: int
    proposed: int
    contradicted: int
    unclear: int


class EvidenceSummary(BaseModel):
    total: int = 0
    confirmed: int = 0
    proposed: int = 0
    contradicted: int = 0
    unclear: int = 0
    by_category: list[EvidenceCategoryCount] = Field(default_factory=list)
    coverage: float = Field(
        default=0.0,
        description="Fraction of milestones up to the predicted TRL with "
                    "confirmed supporting evidence",
    )
    raw_total: int = Field(
        default=0, description="All extracted items before duplicate exclusion"
    )
    duplicates: int = 0
    outdated: int = 0
    self_reported: int = 0


# ----------------------------------------------------------------------
# Milestones
# ----------------------------------------------------------------------
class MilestoneStatusModel(BaseModel):
    id: str
    trl: int
    label: str
    status: MilestoneStatusValue
    evidence_count: int = 0
    supporting: int = 0
    contradicting: int = 0
    proposed: int = 0
    summary: str = ""
    evidence_ids: list[str] = Field(default_factory=list)


# ----------------------------------------------------------------------
# Prediction
# ----------------------------------------------------------------------
class LevelProbability(BaseModel):
    level: int
    probability: float


class AlternativeLevel(BaseModel):
    level: int
    probability: float
    reason: str


class Prediction(BaseModel):
    predicted_trl: int = Field(ge=1, le=9)
    level_name: str
    level_category: str = ""
    level_description: str = ""
    confidence: float = Field(ge=0.0, le=1.0)
    low_confidence: bool = False
    evidence_coverage: float = Field(ge=0.0, le=1.0)
    probabilities: list[LevelProbability] = Field(default_factory=list)
    alternatives: list[AlternativeLevel] = Field(default_factory=list)
    rule_level: int | None = Field(
        default=None,
        description="Highest TRL whose milestone chain is supported by "
                    "confirmed evidence (null when nothing is confirmed)",
    )
    ml_level: int | None = Field(
        default=None, description="Raw ML classifier output (null without a model)"
    )
    model_mode: Literal["hybrid", "rule_only"] = "rule_only"
    warnings: list[str] = Field(default_factory=list)
    method: str = Field(default="", description="Human readable method summary")
    model_probability: float | None = Field(
        default=None,
        description="Highest probability from the ML branch (null in rule-only mode)",
    )


# ----------------------------------------------------------------------
# Verification (Step 6 - evidence verification)
# ----------------------------------------------------------------------
class VerificationResult(BaseModel):
    predicted_trl: int
    evidence_backing: list[EvidenceItem] = Field(default_factory=list)
    contradictions: list[EvidenceItem] = Field(default_factory=list)
    proposed_mistaken_for_done: list[EvidenceItem] = Field(default_factory=list)
    unsupported_high_level_claim: bool = False
    concerns: list[str] = Field(default_factory=list)
    summary: str = ""


# ----------------------------------------------------------------------
# Gap analysis (Step 7)
# ----------------------------------------------------------------------
class Recommendation(BaseModel):
    id: str
    title: str
    addresses: list[str] = Field(
        default_factory=list, description="Milestone ids this recommendation addresses"
    )
    address_labels: list[str] = Field(default_factory=list)
    address_statuses: list[str] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)
    validation_experiments: list[str] = Field(default_factory=list)
    documentation: list[str] = Field(default_factory=list)
    priority: Literal["high", "medium", "low"] = "medium"


class GapAnalysis(BaseModel):
    current_trl: int
    current_name: str
    next_trl: int | None = None
    next_name: str | None = None
    completed_milestones: list[MilestoneStatusModel] = Field(default_factory=list)
    missing_milestones: list[MilestoneStatusModel] = Field(default_factory=list)
    unclear_milestones: list[MilestoneStatusModel] = Field(default_factory=list)
    contradicted_milestones: list[MilestoneStatusModel] = Field(default_factory=list)
    recommendations: list[Recommendation] = Field(default_factory=list)
    documentation_requirements: list[str] = Field(default_factory=list)
    summary: str = ""


# ----------------------------------------------------------------------
# Full assessment result
# ----------------------------------------------------------------------
class ModelInfo(BaseModel):
    available: bool = False
    name: str = ""
    version: str = ""
    mode: Literal["hybrid", "rule_only"] = "rule_only"
    dataset_type: str = "none"
    trained_at: str | None = None


class ProcessingInfo(BaseModel):
    extraction_method: str = ""
    pages: int = 0
    sentences: int = 0
    evidence_items: int = 0
    ocr_used: bool = False
    duration_ms: int = 0
    documents: int = 1
    duplicates: int = 0
    outdated: int = 0


class AssessmentMetadata(BaseModel):
    technology_name: str = ""
    domain: str = ""
    organization: str = ""
    description: str = ""
    filename: str = ""


class AssessmentResult(BaseModel):
    id: str
    document_id: str | None = None
    created_at: str
    metadata: AssessmentMetadata = Field(default_factory=AssessmentMetadata)
    prediction: Prediction
    evidence: list[EvidenceItem] = Field(default_factory=list)
    evidence_summary: EvidenceSummary = Field(default_factory=EvidenceSummary)
    milestones: list[MilestoneStatusModel] = Field(default_factory=list)
    verification: VerificationResult | None = None
    gap_analysis: GapAnalysis | None = None
    model: ModelInfo = Field(default_factory=ModelInfo)
    processing: ProcessingInfo = Field(default_factory=ProcessingInfo)
    # --- additive 2.0 fields (all optional for backward compatibility) ---
    documents: list[DocumentSummary] = Field(default_factory=list)
    retrieval: RetrievalInfo | None = None
    contradictions: ContradictionReport | None = None
    graph: KnowledgeGraph | None = None
    uncertainty: Uncertainty | None = None
    roadmap: TechnologyRoadmap | None = None
    questionnaire: Questionnaire | None = None
    model_explanation: ModelExplanation | None = None
    parent_assessment_id: str | None = None
    reassessment_reason: str | None = None


class AnalyzeRequest(BaseModel):
    document_id: str = ""
    document_ids: list[str] = Field(default_factory=list)
    technology_name: str = ""
    domain: str = ""
    organization: str = ""
    description: str = ""

    @model_validator(mode="after")
    def _require_document(self) -> "AnalyzeRequest":
        ids = [value.strip() for value in [self.document_id, *self.document_ids]]
        if not any(ids):
            raise ValueError(
                "At least one document_id or document_ids entry is required."
            )
        return self


class AssessmentSummary(BaseModel):
    id: str
    document_id: str | None = None
    technology_name: str = ""
    domain: str = ""
    organization: str = ""
    filename: str = ""
    predicted_trl: int | None = None
    level_name: str = ""
    confidence: float | None = None
    low_confidence: bool = False
    evidence_coverage: float | None = None
    model_mode: str = ""
    created_at: str
    # additive 2.0 summary fields
    document_count: int = 1
    uncertainty_overall: float | None = None
    contradictions_total: int = 0
    review_status: str = "unreviewed"
    latest_review_decision: str | None = None


class AssessmentListResponse(BaseModel):
    items: list[AssessmentSummary]
    total: int


# ----------------------------------------------------------------------
# Overview
# ----------------------------------------------------------------------
class TrlCount(BaseModel):
    trl: int
    count: int


class ConfidenceBuckets(BaseModel):
    high: int = 0
    medium: int = 0
    low: int = 0
    average: float | None = None


class CoverageBuckets(BaseModel):
    high: int = 0
    medium: int = 0
    low: int = 0
    average: float | None = None


class DomainCount(BaseModel):
    domain: str
    count: int


class ReviewSummary(BaseModel):
    unreviewed: int = 0
    accepted: int = 0
    overridden: int = 0
    more_evidence_requested: int = 0
    awaiting_review: int = 0


class ActivityItem(BaseModel):
    id: str
    technology_name: str
    predicted_trl: int | None
    confidence: float | None
    created_at: str
    kind: str = "assessment"


class OverviewResponse(BaseModel):
    has_data: bool = False
    total_assessments: int = 0
    average_trl: float | None = None
    average_confidence: float | None = None
    distribution: list[TrlCount] = Field(default_factory=list)
    confidence: ConfidenceBuckets = Field(default_factory=ConfidenceBuckets)
    coverage: CoverageBuckets = Field(default_factory=CoverageBuckets)
    domain_distribution: list[DomainCount] = Field(default_factory=list)
    reviews: ReviewSummary = Field(default_factory=ReviewSummary)
    recent: list[AssessmentSummary] = Field(default_factory=list)
    activity: list[ActivityItem] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)
