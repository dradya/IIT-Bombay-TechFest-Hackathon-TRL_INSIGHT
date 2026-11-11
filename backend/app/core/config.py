"""Application settings and environment configuration.

All configuration is read from environment variables (optionally via a
``.env`` file at the project root) so that no source file has to be
edited to run the application locally.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

# backend/ directory (parent of app/)
BASE_DIR = Path(__file__).resolve().parents[2]
# Project root (parent of backend/)
PROJECT_ROOT = BASE_DIR.parent


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader (no external dependency)."""
    if not path.is_file():
        return
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
    except OSError:  # pragma: no cover - defensive
        return


_load_dotenv(PROJECT_ROOT / ".env")
_load_dotenv(BASE_DIR / ".env")


def _bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "") or default)
    except ValueError:
        return default


class Settings:
    """Runtime settings for the TRL INSIGHT backend."""

    # Application
    APP_NAME: str = os.environ.get("TRL_APP_NAME", "TRL INSIGHT")
    APP_VERSION: str = "1.0.0"
    ENV: str = os.environ.get("TRL_ENV", "development")
    DEBUG: bool = _bool("TRL_DEBUG", True)
    LOG_LEVEL: str = os.environ.get("TRL_LOG_LEVEL", "INFO")

    # Server
    HOST: str = os.environ.get("TRL_HOST", "127.0.0.1")
    PORT: int = _int("TRL_PORT", 8000)

    # CORS (comma separated)
    CORS_ORIGINS_RAW: str = os.environ.get(
        "TRL_CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173",
    )

    # Storage
    DATA_DIR: Path = Path(os.environ.get("TRL_DATA_DIR", str(BASE_DIR / "data")))
    MODELS_DIR: Path = Path(os.environ.get("TRL_MODELS_DIR", str(BASE_DIR / "models")))
    CONFIG_DIR: Path = Path(os.environ.get("TRL_CONFIG_DIR", str(BASE_DIR / "config")))
    UPLOAD_DIR: Path | None = None  # resolved below
    EXTRACTED_DIR: Path | None = None
    DB_PATH: Path | None = None

    # Uploads / documents
    MAX_UPLOAD_SIZE_MB: int = _int("TRL_MAX_UPLOAD_SIZE_MB", 25)
    ALLOWED_EXTENSIONS: tuple[str, ...] = (".pdf", ".docx", ".txt")

    # Optional OCR
    OCR_ENABLED: bool = _bool("TRL_OCR_ENABLED", False)
    TESSERACT_CMD: str = os.environ.get("TRL_TESSERACT_CMD", "")

    # Optional OSS integrations (all lazy-loaded with native fallbacks)
    PARSER: str = os.environ.get("TRL_PARSER", "auto").strip().lower()
    SEMANTIC_RETRIEVAL: bool = _bool("TRL_SEMANTIC_RETRIEVAL", True)
    EMBEDDING_BACKEND: str = os.environ.get(
        "TRL_EMBEDDING_BACKEND", "auto"
    ).strip().lower()
    EMBEDDING_MODEL: str = os.environ.get(
        "TRL_EMBEDDING_MODEL",
        "sentence-transformers/all-MiniLM-L6-v2",
    )
    EMBEDDING_CACHE_DIR: Path = Path(
        os.environ.get(
            "TRL_EMBEDDING_CACHE", str(BASE_DIR / "data" / "embeddings")
        )
    )
    SHAP_ENABLED: bool = _bool("TRL_SHAP_ENABLED", True)

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS_RAW.split(",") if o.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    def ensure_dirs(self) -> None:
        for path in (self.DATA_DIR, self.MODELS_DIR, self.CONFIG_DIR,
                     self.UPLOAD_DIR, self.EXTRACTED_DIR,
                     self.EMBEDDING_CACHE_DIR):
            if path is not None:
                path.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.UPLOAD_DIR = settings.DATA_DIR / "uploads"
settings.EXTRACTED_DIR = settings.DATA_DIR / "extracted"
settings.DB_PATH = settings.DATA_DIR / "trl_insight.db"
settings.ensure_dirs()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return settings
