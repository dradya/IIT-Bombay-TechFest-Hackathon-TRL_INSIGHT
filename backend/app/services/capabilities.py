"""Runtime capability report for optional integrations.

Every capability is discovered from the actual environment; nothing is
reported as available unless its package can be imported. This powers the
Settings page and the ``GET /api/system/capabilities`` endpoint.
"""
from __future__ import annotations

import importlib.util

from app.core.config import settings
from app.services.docling_adapter import docling_available
from app.services.semantic import select_backend


def _installed(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):  # pragma: no cover - broken install
        return False


def get_capabilities() -> dict:
    parser = (settings.PARSER or "auto").strip().lower()
    docling_ok = docling_available()
    _, embedding_info = select_backend()

    return {
        "parser": {
            "configured": parser,
            "docling_available": docling_ok,
            "active": "docling" if docling_ok and parser in {"auto", "docling"}
            else "native",
            "native_fallback": "PyMuPDF + pdfplumber (PDF), python-docx (DOCX), text (TXT)",
            "note": (
                "Docling is tried first when installed; any failure falls back "
                "to the native extractor."
            ),
        },
        "embeddings": {
            "configured": settings.EMBEDDING_BACKEND,
            "active": embedding_info.backend,
            "model": embedding_info.model,
            "available": embedding_info.available,
            "fallback_reason": embedding_info.fallback_reason,
            "cache": str(settings.EMBEDDING_CACHE_DIR),
            "sentence_transformers_installed": _installed("sentence_transformers"),
            "flag_embedding_installed": _installed("FlagEmbedding"),
            "note": (
                "Retrieval ranking only. The TF-IDF cosine fallback always "
                "works offline and on CPU."
            ),
        },
        "shap": {
            "enabled": settings.SHAP_ENABLED,
            "installed": _installed("shap"),
            "fallback": "exact linear coefficient attribution for linear models",
            "note": (
                "Model feature attributions explain the classifier; they are "
                "never presented as source evidence."
            ),
        },
        "haystack": {
            "installed": _installed("haystack"),
            "integrated": False,
            "reason": (
                "Evaluated and intentionally not integrated: the existing "
                "pipeline already provides source-located evidence, rule "
                "verification and auditable exports. See "
                "docs/OPEN_SOURCE_INTEGRATIONS.md."
            ),
        },
        "osstrl": {
            "installed": _installed("osstrl"),
            "integrated": False,
            "license": "BSD-2-Clause",
            "reason": (
                "Methodological reference only: OSSTRL measures open-source "
                "repository health, while TRL INSIGHT assesses technology "
                "readiness from submitted documents. No code was copied."
            ),
        },
        "semantic_retrieval": {
            "enabled": settings.SEMANTIC_RETRIEVAL,
            "backend": embedding_info.backend,
        },
    }
