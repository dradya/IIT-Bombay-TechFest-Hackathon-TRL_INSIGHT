"""TRL INSIGHT - FastAPI application entry point.

Run locally with:  uvicorn app.main:app --reload --port 8000
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.config import PROJECT_ROOT, settings
from app.core.database import get_db
from app.core.logging import get_logger

logger = get_logger("main")

app = FastAPI(
    title="TRL INSIGHT API",
    description=(
        "AI-powered Technology Readiness Assessment and evidence-based "
        "gap analysis. Accepts unstructured technical documents, predicts "
        "TRL 1-9, extracts traceable evidence and generates auditable "
        "gap analyses with actionable recommendations."
    ),
    version=settings.APP_VERSION,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_logging(request: Request, call_next):  # type: ignore[no-untyped-def]
    started = time.perf_counter()
    response = await call_next(request)
    duration_ms = int((time.perf_counter() - started) * 1000)
    if request.url.path.startswith("/api"):
        logger.info(
            "%s %s -> %s (%d ms)",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    detail: Any = exc.detail
    if isinstance(detail, dict) and "detail" in detail:
        payload = {"detail": detail["detail"], "code": detail.get("code", "error")}
    elif isinstance(detail, str):
        payload = {"detail": detail, "code": "error"}
    else:
        payload = {"detail": detail, "code": "error"}
    return JSONResponse(status_code=exc.status_code, content=payload)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    messages = []
    for error in exc.errors():
        loc = ".".join(str(part) for part in error.get("loc", []))
        messages.append(f"{loc}: {error.get('msg', 'invalid value')}")
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Validation failed: " + "; ".join(messages),
            "code": "validation_error",
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {exc}", "code": "internal_error"},
    )


app.include_router(api_router)


@app.on_event("startup")
def on_startup() -> None:
    settings.ensure_dirs()
    get_db().init_schema()
    from app.ml.predictor import load_model_bundle

    bundle = load_model_bundle()
    if bundle is not None:
        logger.info(
            "Model loaded: %s v%s (dataset=%s, trained=%s)",
            bundle.model_name,
            bundle.model_version,
            bundle.dataset_type,
            bundle.trained_at,
        )
    else:
        logger.warning(
            "No trained model found in %s - running in rule-only mode. "
            "Run training/train_model.py to enable the ML classifier.",
            settings.MODELS_DIR,
        )
    logger.info("TRL INSIGHT backend ready (env=%s)", settings.ENV)


# ---------------------------------------------------------------------------
# Optional: serve the built frontend (single-server mode)
# ---------------------------------------------------------------------------
_DIST = PROJECT_ROOT / "frontend" / "dist"
if _DIST.is_dir() and (_DIST / "index.html").is_file():
    # NOTE: routes are declared BEFORE the "/" mount — a mount at "/" would
    # otherwise shadow them (Starlette matches mounts in registration order).
    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str) -> Response:
        """Serve the built SPA for any non-API GET path (deep links, refresh)."""
        # Unknown API routes must stay JSON 404s — never the SPA shell.
        if full_path == "api" or full_path.startswith("api/"):
            return JSONResponse(
                status_code=404,
                content={"detail": "Not found.", "code": "not_found"},
            )
        candidate = (_DIST / full_path).resolve()
        if (
            full_path  # "/" itself is handled by the html=True mount below
            and candidate.is_relative_to(_DIST.resolve())
            and candidate.is_file()
        ):
            return FileResponse(candidate)
        return FileResponse(_DIST / "index.html")

    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="frontend")
    logger.info("Serving built frontend from %s", _DIST)
