"""GET /api/health"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter

from app.core.config import settings
from app.ml.predictor import load_model_bundle, model_available
from app.schemas.common import HealthResponse

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    bundle = load_model_bundle()
    return HealthResponse(
        status="ok",
        app=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment=settings.ENV,
        model_available=model_available(),
        model_mode=bundle.model_name if bundle else "rule_only",
        database=str(settings.DB_PATH),
        time=datetime.now(timezone.utc).isoformat(),
    )
