# =====================================================================
# TRL INSIGHT — multi-stage Docker build
#   stage 1: build the React frontend (Node)
#   stage 2: Python runtime serving API + built SPA
# Build:  docker build -t trl-insight .
# Run:    docker run --rm -p 8000:8000 trl-insight
# =====================================================================

# ---------------------------------------------------------------------
# Stage 1 — frontend build
# ---------------------------------------------------------------------
FROM node:24-alpine AS frontend-build

WORKDIR /build

# Manifest first for better layer caching
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build


# ---------------------------------------------------------------------
# Stage 2 — backend runtime
# ---------------------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TRL_HOST=0.0.0.0 \
    TRL_PORT=8000 \
    TRL_ENV=production \
    TRL_LOG_LEVEL=INFO

WORKDIR /app

# System deps: PyMuPDF/pdfplumber wheels are self-contained; build tools are
# only needed as a fallback for source builds of pydantic-core etc.
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

# Application source
COPY backend/ ./backend/
# Built frontend (served by FastAPI when frontend/dist exists)
COPY --from=frontend-build /build/dist ./frontend/dist

WORKDIR /app/backend

# Non-root user
RUN useradd --create-home --uid 10001 trl \
    && mkdir -p /app/backend/data /app/backend/models \
    && chown -R trl:trl /app
USER trl

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/api/health || exit 1

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
