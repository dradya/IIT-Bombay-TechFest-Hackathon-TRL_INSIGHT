"""Shared schema primitives."""
from __future__ import annotations

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    detail: str
    code: str | None = None


class HealthResponse(BaseModel):
    status: str
    app: str
    version: str
    environment: str
    model_available: bool
    model_mode: str
    database: str
    time: str
