"""Additive schemas for TRL INSIGHT 2.0.

These models describe multi-document provenance, retrieval, contradictions,
knowledge graphs, uncertainty decomposition, model explanations, roadmaps,
questionnaires, expert reviews and history. Every field is computed from real
inputs; fields that cannot be computed are explicitly ``None`` or flagged
unavailable rather than filled with placeholder values.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

EvidenceType = Literal["document", "self_reported"]
ReviewDecision = Literal["accept", "override", "needs_more_evidence"]


class DocumentSummary(BaseModel):
    document_id: str | None = None
    filename: str
    page_count: int = 0
    char_count: int = 0
    uploaded_at: str | None = None
    extraction_method: str = "text"
    evidence_count: int = 0
    confirmed: int = 0
    proposed: int = 0
    contradicted: int = 0
    unclear: int = 0
    duplicates: int = 0
    outdated: int = 0


class RetrievalMatch(BaseModel):
    evidence_id: str
    statement: str
    source_document: str
    page_number: int | None = None
    location: str = ""
    status: str = ""
    similarity: float = 0.0


class MilestoneRetrieval(BaseModel):
    milestone: str
    matches: list[RetrievalMatch] = Field(default_factory=list)


class RetrievalInfo(BaseModel):
    enabled: bool = False
    method: str = "tfidf"
    model: str = ""
    backend: str = "tfidf"
    cached: bool = False
    fallback_reason: str = ""
    by_milestone: list[MilestoneRetrieval] = Field(default_factory=list)
    note: str = ""


class ContradictionSource(BaseModel):
    evidence_id: str
    statement: str
    source_document: str
    document_id: str | None = None
    page_number: int | None = None
    location: str = ""
    status: str
    uploaded_at: str | None = None
    outdated: bool = False


class ContradictionItem(BaseModel):
    id: str
    type: Literal[
        "explicit_contradiction",
        "cross_document_conflict",
        "category_conflict",
        "outdated_conflict",
    ]
    severity: Literal["high", "medium", "low"] = "high"
    milestone: str | None = None
    milestone_label: str | None = None
    category: str | None = None
    category_label: str | None = None
    explanation: str = ""
    sources: list[ContradictionSource] = Field(default_factory=list)
    human_verification: list[str] = Field(default_factory=list)
    suggested_action: str = ""


class ContradictionReport(BaseModel):
    total: int = 0
    by_type: dict[str, int] = Field(default_factory=dict)
    items: list[ContradictionItem] = Field(default_factory=list)
    summary: str = ""


class Uncertainty(BaseModel):
    model_probability: float | None = Field(
        default=None,
        description="Highest probability from the ML branch; null in rule-only mode.",
    )
    confidence: float = Field(ge=0.0, le=1.0)
    coverage: float = Field(ge=0.0, le=1.0)
    completeness: float = Field(
        ge=0.0, le=1.0,
        description="Fraction of the nine milestones with confirmed evidence.",
    )
    reliability: float = Field(
        ge=0.0, le=1.0,
        description="Source/extraction quality signal, not a probability.",
    )
    overall: float = Field(ge=0.0, le=1.0)
    band: Literal["low", "medium", "high"] = "low"
    calibrated: bool = False
    calibration_source: str | None = None
    calibration_note: str = ""
    components: dict[str, float | None] = Field(default_factory=dict)
    explanation: str = ""


class GraphNode(BaseModel):
    id: str
    type: Literal[
        "technology", "document", "milestone", "category", "evidence",
        "contradiction",
    ]
    label: str
    status: str | None = None
    document_id: str | None = None
    page_number: int | None = None
    weight: float = 1.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    type: Literal[
        "contains", "supports", "contradicts", "duplicate_of", "derived_from",
        "relates_to",
    ]
    label: str = ""


class KnowledgeGraph(BaseModel):
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    node_count: int = 0
    edge_count: int = 0
    truncated: bool = False
    note: str = ""


class RoadmapAction(BaseModel):
    id: str
    title: str
    description: str = ""
    milestone: str | None = None
    milestone_label: str | None = None
    status: str = "missing"
    priority: Literal["high", "medium", "low"] = "medium"
    actions: list[str] = Field(default_factory=list)
    validation_experiments: list[str] = Field(default_factory=list)
    documentation: list[str] = Field(default_factory=list)
    success_criteria: list[str] = Field(default_factory=list)


class RoadmapPhase(BaseModel):
    id: str
    title: str
    horizon: Literal["now", "next", "later"]
    target_trl: int | None = None
    summary: str = ""
    items: list[RoadmapAction] = Field(default_factory=list)


class TechnologyRoadmap(BaseModel):
    current_trl: int
    current_name: str = ""
    target_trl: int | None = None
    target_name: str | None = None
    phases: list[RoadmapPhase] = Field(default_factory=list)
    note: str = ""


class QuestionItem(BaseModel):
    id: str
    milestone: str
    milestone_label: str
    trl: int
    status: str
    question: str
    why_it_matters: str = ""
    expected_document: str = ""
    options: list[str] = Field(
        default_factory=lambda: ["completed", "planned", "not_applicable", "unknown"]
    )


class Questionnaire(BaseModel):
    assessment_id: str = ""
    generated_at: str = ""
    total: int = 0
    items: list[QuestionItem] = Field(default_factory=list)
    note: str = (
        "Answers are self-reported. They are only treated as confirmed evidence "
        "when a source reference is supplied."
    )


class ExpertAnswer(BaseModel):
    milestone_id: str
    status: Literal["completed", "planned", "not_applicable", "unknown"] = "unknown"
    evidence_note: str = ""
    source_reference: str = ""


class ReassessRequest(BaseModel):
    answers: list[ExpertAnswer] = Field(default_factory=list)
    reviewer_name: str = ""
    reason: str = ""


class ShapFeature(BaseModel):
    feature: str
    label: str
    value: float
    contribution: float
    direction: Literal["supports", "opposes", "neutral"] = "neutral"
    kind: Literal["text", "evidence"] = "evidence"


class ModelExplanation(BaseModel):
    available: bool = False
    method: str = "unavailable"
    target_trl: int | None = None
    baseline: float | None = None
    prediction_probability: float | None = None
    features: list[ShapFeature] = Field(default_factory=list)
    note: str = ""
    warning: str = (
        "Model feature attributions explain the classifier's decision. They are "
        "not source evidence and must not be cited as document support."
    )


class ReviewCreate(BaseModel):
    reviewer_name: str = Field(min_length=1, max_length=120)
    decision: ReviewDecision = "accept"
    reviewed_trl: int | None = Field(default=None, ge=1, le=9)
    notes: str = Field(default="", max_length=4000)
    evidence_ids: list[str] = Field(default_factory=list)


class ReviewModel(BaseModel):
    id: str
    assessment_id: str
    reviewer_name: str
    decision: ReviewDecision
    reviewed_trl: int | None = None
    ai_trl: int | None = None
    notes: str = ""
    evidence_ids: list[str] = Field(default_factory=list)
    created_at: str


class ReviewListResponse(BaseModel):
    assessment_id: str
    items: list[ReviewModel] = Field(default_factory=list)
    total: int = 0
    ai_prediction: dict[str, Any] = Field(default_factory=dict)
    latest_decision: str | None = None
    review_status: str = "unreviewed"


class TimelineEvent(BaseModel):
    id: str
    kind: Literal["created", "reassessment", "review", "analysis"]
    title: str
    description: str = ""
    at: str
    actor: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AssessmentTimeline(BaseModel):
    assessment_id: str
    events: list[TimelineEvent] = Field(default_factory=list)


class CompareItem(BaseModel):
    id: str
    technology_name: str = ""
    predicted_trl: int | None = None
    confidence: float | None = None
    evidence_coverage: float | None = None
    uncertainty_overall: float | None = None
    documents: list[DocumentSummary] = Field(default_factory=list)
    milestones: list[dict[str, Any]] = Field(default_factory=list)
    evidence_total: int = 0
    contradictions_total: int = 0
    created_at: str = ""


class CompareResponse(BaseModel):
    items: list[CompareItem] = Field(default_factory=list)
    note: str = ""
