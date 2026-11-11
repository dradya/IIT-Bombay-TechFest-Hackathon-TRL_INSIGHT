"""Model performance and TRL reference schemas."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ClassMetric(BaseModel):
    precision: float
    recall: float
    f1: float
    support: int


class ModelPerformanceResponse(BaseModel):
    available: bool = False
    mode: str = "unavailable"
    note: str = ""
    model_name: str | None = None
    model_version: str | None = None
    trained_at: str | None = None
    dataset_type: str | None = None
    dataset_source: str | None = None
    n_train: int | None = None
    n_test: int | None = None
    class_distribution: dict[str, int] = Field(default_factory=dict)
    metrics: dict[str, float] = Field(default_factory=dict)
    per_class: dict[str, ClassMetric] = Field(default_factory=dict)
    confusion_matrix: dict[str, Any] | None = None
    classification_report: dict[str, Any] | None = None


class TRLReferenceResponse(BaseModel):
    version: str
    meta: dict[str, Any] = Field(default_factory=dict)
    levels: list[dict[str, Any]] = Field(default_factory=list)
    milestones: list[dict[str, Any]] = Field(default_factory=list)
    evidence_categories: list[dict[str, Any]] = Field(default_factory=list)
    evidence_statuses: list[str] = Field(default_factory=list)
    assessment_rules: dict[str, Any] = Field(default_factory=dict)
