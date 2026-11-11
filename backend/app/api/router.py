"""API router assembly."""
from __future__ import annotations

from fastapi import APIRouter

from app.api import assessments, documents, health, meta

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(documents.router)
api_router.include_router(assessments.router)
api_router.include_router(meta.router)
