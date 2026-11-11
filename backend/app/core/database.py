"""SQLite persistence layer.

Data access is isolated in repository classes so that the storage engine
can be replaced by PostgreSQL later without touching business logic.
Connections are created per operation (SQLite + FastAPI event loop safe)
and ``PRAGMA`` settings are applied for durability.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Iterable

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("database")

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id              TEXT PRIMARY KEY,
    filename        TEXT NOT NULL,
    original_name   TEXT NOT NULL,
    file_type       TEXT NOT NULL,
    size_bytes      INTEGER NOT NULL DEFAULT 0,
    page_count      INTEGER NOT NULL DEFAULT 0,
    char_count      INTEGER NOT NULL DEFAULT 0,
    uploaded_at     TEXT NOT NULL,
    storage_path    TEXT,
    extracted_path  TEXT,
    metadata_json   TEXT
);

CREATE TABLE IF NOT EXISTS assessments (
    id              TEXT PRIMARY KEY,
    document_id     TEXT,
    technology_name TEXT,
    domain          TEXT,
    organization    TEXT,
    description     TEXT,
    predicted_trl   INTEGER,
    confidence      REAL,
    low_confidence  INTEGER NOT NULL DEFAULT 0,
    evidence_coverage REAL,
    model_mode      TEXT,
    result_json     TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    parent_assessment_id TEXT,
    documents_json  TEXT,
    reassessment_reason TEXT,
    uncertainty_overall REAL,
    contradictions_total INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (document_id) REFERENCES documents (id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS assessment_documents (
    assessment_id   TEXT NOT NULL,
    document_id     TEXT,
    filename        TEXT,
    position        INTEGER NOT NULL DEFAULT 0,
    uploaded_at     TEXT,
    page_count      INTEGER NOT NULL DEFAULT 0,
    char_count      INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (assessment_id, position),
    FOREIGN KEY (assessment_id) REFERENCES assessments (id) ON DELETE CASCADE,
    FOREIGN KEY (document_id) REFERENCES documents (id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS assessment_reviews (
    id              TEXT PRIMARY KEY,
    assessment_id   TEXT NOT NULL,
    reviewer_name   TEXT NOT NULL,
    decision        TEXT NOT NULL,
    reviewed_trl    INTEGER,
    ai_trl          INTEGER,
    notes           TEXT NOT NULL DEFAULT '',
    evidence_ids_json TEXT,
    created_at      TEXT NOT NULL,
    FOREIGN KEY (assessment_id) REFERENCES assessments (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS assessment_events (
    id              TEXT PRIMARY KEY,
    assessment_id   TEXT NOT NULL,
    kind            TEXT NOT NULL,
    title           TEXT NOT NULL,
    description     TEXT NOT NULL DEFAULT '',
    actor           TEXT,
    metadata_json   TEXT,
    at              TEXT NOT NULL,
    FOREIGN KEY (assessment_id) REFERENCES assessments (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_assessments_trl ON assessments (predicted_trl);
CREATE INDEX IF NOT EXISTS idx_assessments_created ON assessments (created_at);
CREATE INDEX IF NOT EXISTS idx_assessments_domain ON assessments (domain);
CREATE INDEX IF NOT EXISTS idx_assessment_docs_doc ON assessment_documents (document_id);
CREATE INDEX IF NOT EXISTS idx_reviews_assessment ON assessment_reviews (assessment_id);
CREATE INDEX IF NOT EXISTS idx_events_assessment ON assessment_events (assessment_id);
"""

# Columns added after the initial 1.0 schema. Existing databases are migrated
# in place so no assessment data is lost.
_ASSESSMENT_MIGRATIONS: dict[str, str] = {
    "parent_assessment_id": "TEXT",
    "documents_json": "TEXT",
    "reassessment_reason": "TEXT",
    "uncertainty_overall": "REAL",
    "contradictions_total": "INTEGER NOT NULL DEFAULT 0",
}


# Whitelisted sort keys -> SQL fragments. Never interpolate user input directly.
_ASSESSMENT_SORTS: dict[str, str] = {
    "created_desc": "a.created_at DESC",
    "created_asc": "a.created_at ASC",
    "trl_desc": "a.predicted_trl DESC, a.created_at DESC",
    "trl_asc": "a.predicted_trl ASC, a.created_at DESC",
    "confidence_desc": "a.confidence DESC, a.created_at DESC",
    "confidence_asc": "a.confidence ASC, a.created_at DESC",
    "coverage_desc": "a.evidence_coverage DESC, a.created_at DESC",
}

# Public review status -> latest stored decision.
_REVIEW_STATUS_TO_DECISION = {
    "accepted": "accept",
    "overridden": "override",
    "more_evidence_requested": "needs_more_evidence",
}


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex[:16]}"


class Database:
    """Thin SQLite wrapper (schema management + query helpers)."""

    def __init__(self, path: str | None = None):
        self.path = str(path or settings.DB_PATH)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=30, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        return conn

    def init_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA)
            self._migrate(conn)
        logger.info("Database schema initialised at %s", self.path)

    @staticmethod
    def _migrate(conn: sqlite3.Connection) -> None:
        """Additive migrations for databases created by earlier versions."""
        columns = {
            str(row["name"])
            for row in conn.execute("PRAGMA table_info(assessments)").fetchall()
        }
        for name, ddl in _ASSESSMENT_MIGRATIONS.items():
            if name not in columns:
                conn.execute(f"ALTER TABLE assessments ADD COLUMN {name} {ddl}")
                logger.info("Migrated assessments table: added column %s", name)

    def query(self, sql: str, params: Iterable[Any] = ()) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
        return [dict(r) for r in rows]

    def query_one(self, sql: str, params: Iterable[Any] = ()) -> dict[str, Any] | None:
        rows = self.query(sql, params)
        return rows[0] if rows else None

    def execute(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Cursor:
        with self.connect() as conn:
            cur = conn.execute(sql, tuple(params))
            conn.commit()
            return cur


_db: Database | None = None


def get_db() -> Database:
    global _db
    if _db is None:
        _db = Database()
        _db.init_schema()
    return _db


def set_db(db: Database) -> None:
    """Used by tests to point the app at a temporary database."""
    global _db
    _db = db
    _db.init_schema()


# ----------------------------------------------------------------------
# Repositories (data access only - no business logic)
# ----------------------------------------------------------------------
class DocumentRepository:
    def __init__(self, db: Database | None = None):
        self.db = db or get_db()

    def create(self, **fields: Any) -> dict[str, Any]:
        fields.setdefault("id", new_id("doc_"))
        fields.setdefault("uploaded_at", utcnow())
        fields.setdefault("size_bytes", 0)
        fields.setdefault("page_count", 0)
        fields.setdefault("char_count", 0)
        cols = ", ".join(fields)
        marks = ", ".join("?" for _ in fields)
        self.db.execute(
            f"INSERT INTO documents ({cols}) VALUES ({marks})", list(fields.values())
        )
        return fields

    def get(self, doc_id: str) -> dict[str, Any] | None:
        return self.db.query_one("SELECT * FROM documents WHERE id = ?", (doc_id,))

    def list(self) -> list[dict[str, Any]]:
        return self.db.query("SELECT * FROM documents ORDER BY uploaded_at DESC")

    def update(self, doc_id: str, **fields: Any) -> None:
        if not fields:
            return
        sets = ", ".join(f"{k} = ?" for k in fields)
        self.db.execute(
            f"UPDATE documents SET {sets} WHERE id = ?",
            [*fields.values(), doc_id],
        )

    def delete(self, doc_id: str) -> bool:
        cur = self.db.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
        return cur.rowcount > 0


class AssessmentRepository:
    def __init__(self, db: Database | None = None):
        self.db = db or get_db()

    def create(self, **fields: Any) -> dict[str, Any]:
        fields.setdefault("id", new_id("asm_"))
        fields.setdefault("created_at", utcnow())
        fields.setdefault("low_confidence", 0)
        cols = ", ".join(fields)
        marks = ", ".join("?" for _ in fields)
        self.db.execute(
            f"INSERT INTO assessments ({cols}) VALUES ({marks})", list(fields.values())
        )
        return fields

    def get(self, assessment_id: str) -> dict[str, Any] | None:
        return self.db.query_one(
            "SELECT * FROM assessments WHERE id = ?", (assessment_id,)
        )

    @staticmethod
    def _filters(
        *,
        search: str | None = None,
        domain: str | None = None,
        trl: int | None = None,
        trl_min: int | None = None,
        trl_max: int | None = None,
        review_status: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        confidence_min: float | None = None,
        confidence_max: float | None = None,
        low_confidence: bool | None = None,
    ) -> tuple[list[str], list[Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if search:
            clauses.append(
                "(a.technology_name LIKE ? OR a.domain LIKE ? OR a.organization LIKE ? "
                "OR a.description LIKE ?)"
            )
            like = f"%{search}%"
            params.extend([like, like, like, like])
        if domain:
            clauses.append("a.domain = ?")
            params.append(domain)
        if trl is not None:
            clauses.append("a.predicted_trl = ?")
            params.append(trl)
        if trl_min is not None:
            clauses.append("a.predicted_trl >= ?")
            params.append(trl_min)
        if trl_max is not None:
            clauses.append("a.predicted_trl <= ?")
            params.append(trl_max)
        if confidence_min is not None:
            clauses.append("a.confidence >= ?")
            params.append(confidence_min)
        if confidence_max is not None:
            clauses.append("a.confidence <= ?")
            params.append(confidence_max)
        if low_confidence is not None:
            clauses.append("a.low_confidence = ?")
            params.append(1 if low_confidence else 0)
        if date_from:
            clauses.append("a.created_at >= ?")
            params.append(date_from)
        if date_to:
            clauses.append("a.created_at <= ?")
            params.append(date_to)
        if review_status:
            if review_status == "unreviewed":
                clauses.append(
                    "NOT EXISTS (SELECT 1 FROM assessment_reviews r "
                    "WHERE r.assessment_id = a.id)"
                )
            elif review_status in _REVIEW_STATUS_TO_DECISION:
                clauses.append(
                    "COALESCE((SELECT r.decision FROM assessment_reviews r "
                    "WHERE r.assessment_id = a.id "
                    "ORDER BY r.created_at DESC, r.id DESC LIMIT 1), '') = ?"
                )
                params.append(_REVIEW_STATUS_TO_DECISION[review_status])
        return clauses, params

    def list(
        self,
        search: str | None = None,
        domain: str | None = None,
        trl: int | None = None,
        trl_min: int | None = None,
        trl_max: int | None = None,
        review_status: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        confidence_min: float | None = None,
        confidence_max: float | None = None,
        low_confidence: bool | None = None,
        sort: str = "created_desc",
        limit: int = 500,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        clauses, params = self._filters(
            search=search, domain=domain, trl=trl, trl_min=trl_min,
            trl_max=trl_max, review_status=review_status, date_from=date_from,
            date_to=date_to, confidence_min=confidence_min,
            confidence_max=confidence_max, low_confidence=low_confidence,
        )
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        order = _ASSESSMENT_SORTS.get(sort, _ASSESSMENT_SORTS["created_desc"])
        params.extend([limit, offset])
        return self.db.query(
            "SELECT a.id, a.document_id, a.technology_name, a.domain, "
            "a.organization, a.predicted_trl, a.confidence, a.low_confidence, "
            "a.evidence_coverage, a.model_mode, a.created_at, "
            "a.parent_assessment_id, a.documents_json, a.uncertainty_overall, "
            "a.contradictions_total, "
            "COALESCE(d.original_name, '') AS filename "
            "FROM assessments a LEFT JOIN documents d ON d.id = a.document_id "
            f"{where} ORDER BY {order} LIMIT ? OFFSET ?",
            params,
        )

    def summary_rows(
        self,
        search: str | None = None,
        domain: str | None = None,
        trl: int | None = None,
        trl_min: int | None = None,
        trl_max: int | None = None,
        review_status: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        confidence_min: float | None = None,
        confidence_max: float | None = None,
        low_confidence: bool | None = None,
    ) -> int:
        """Total count matching the same filters as :meth:`list`."""
        clauses, params = self._filters(
            search=search, domain=domain, trl=trl, trl_min=trl_min,
            trl_max=trl_max, review_status=review_status, date_from=date_from,
            date_to=date_to, confidence_min=confidence_min,
            confidence_max=confidence_max, low_confidence=low_confidence,
        )
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        row = self.db.query_one(
            f"SELECT COUNT(*) AS n FROM assessments a {where}", params
        )
        return int(row["n"]) if row else 0

    def count(self) -> int:
        row = self.db.query_one("SELECT COUNT(*) AS n FROM assessments")
        return int(row["n"]) if row else 0

    def stats(
        self,
        domain: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> dict[str, Any]:
        clauses, params = self._filters(
            domain=domain, date_from=date_from, date_to=date_to
        )
        clauses.append("a.predicted_trl IS NOT NULL")
        where = f"WHERE {' AND '.join(clauses)}"
        row = self.db.query_one(
            "SELECT COUNT(*) AS n, AVG(a.predicted_trl) AS avg_trl, "
            "AVG(a.confidence) AS avg_conf "
            f"FROM assessments a {where}",
            params,
        )
        dist = self.db.query(
            "SELECT a.predicted_trl AS trl, COUNT(*) AS n FROM assessments a "
            f"{where} GROUP BY a.predicted_trl ORDER BY trl",
            params,
        )
        low_params = list(params)
        low_clauses = list(clauses)
        low_clauses.append("a.low_confidence = 1")
        low_where = f"WHERE {' AND '.join(low_clauses)}"
        low = self.db.query_one(
            f"SELECT COUNT(*) AS n FROM assessments a {low_where}", low_params
        )
        return {
            "total": int(row["n"] or 0) if row else 0,
            "avg_trl": float(row["avg_trl"] or 0) if row and row["avg_trl"] else None,
            "avg_confidence": float(row["avg_conf"] or 0) if row and row["avg_conf"] else None,
            "distribution": {int(d["trl"]): int(d["n"]) for d in dist},
            "low_confidence": int(low["n"] or 0) if low else 0,
        }

    def confidence_buckets(
        self,
        domain: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> dict[str, float | int]:
        clauses, params = self._filters(
            domain=domain, date_from=date_from, date_to=date_to
        )
        clauses.append("a.predicted_trl IS NOT NULL")
        where = f"WHERE {' AND '.join(clauses)}"
        row = self.db.query_one(
            "SELECT "
            "SUM(CASE WHEN a.confidence >= 0.70 THEN 1 ELSE 0 END) AS high, "
            "SUM(CASE WHEN a.confidence >= 0.45 AND a.confidence < 0.70 THEN 1 ELSE 0 END) AS medium, "
            "SUM(CASE WHEN a.confidence < 0.45 THEN 1 ELSE 0 END) AS low, "
            "AVG(a.confidence) AS avg "
            f"FROM assessments a {where}",
            params,
        )
        row = row or {}
        return {
            "high": int(row.get("high") or 0),
            "medium": int(row.get("medium") or 0),
            "low": int(row.get("low") or 0),
            "average": float(row.get("avg") or 0) if row.get("avg") else None,
        }

    def coverage_buckets(
        self,
        domain: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> dict[str, float | int]:
        clauses, params = self._filters(
            domain=domain, date_from=date_from, date_to=date_to
        )
        clauses.append("a.predicted_trl IS NOT NULL")
        where = f"WHERE {' AND '.join(clauses)}"
        row = self.db.query_one(
            "SELECT "
            "SUM(CASE WHEN a.evidence_coverage >= 0.70 THEN 1 ELSE 0 END) AS high, "
            "SUM(CASE WHEN a.evidence_coverage >= 0.45 AND a.evidence_coverage < 0.70 THEN 1 ELSE 0 END) AS medium, "
            "SUM(CASE WHEN a.evidence_coverage < 0.45 THEN 1 ELSE 0 END) AS low, "
            "AVG(a.evidence_coverage) AS avg "
            f"FROM assessments a {where}",
            params,
        )
        row = row or {}
        return {
            "high": int(row.get("high") or 0),
            "medium": int(row.get("medium") or 0),
            "low": int(row.get("low") or 0),
            "average": float(row.get("avg") or 0) if row.get("avg") else None,
        }

    def domain_distribution(
        self,
        domain: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[dict[str, Any]]:
        clauses, params = self._filters(
            domain=domain, date_from=date_from, date_to=date_to
        )
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        return self.db.query(
            "SELECT COALESCE(NULLIF(a.domain, ''), 'Unspecified') AS domain, "
            f"COUNT(*) AS n FROM assessments a {where} "
            "GROUP BY COALESCE(NULLIF(a.domain, ''), 'Unspecified') "
            "ORDER BY n DESC, domain ASC",
            params,
        )

    def review_counts(
        self,
        domain: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> dict[str, int]:
        clauses, params = self._filters(
            domain=domain, date_from=date_from, date_to=date_to
        )
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self.db.query(
            "SELECT COALESCE((SELECT r.decision FROM assessment_reviews r "
            "WHERE r.assessment_id = a.id "
            "ORDER BY r.created_at DESC, r.id DESC LIMIT 1), '') AS decision, "
            f"COUNT(*) AS n FROM assessments a {where} GROUP BY decision",
            params,
        )
        counts = {"accept": 0, "override": 0, "needs_more_evidence": 0, "": 0}
        for row in rows:
            key = str(row.get("decision") or "")
            counts[key] = counts.get(key, 0) + int(row.get("n") or 0)
        return {
            "unreviewed": counts[""],
            "accepted": counts["accept"],
            "overridden": counts["override"],
            "more_evidence_requested": counts["needs_more_evidence"],
            "awaiting_review": counts[""],
        }

    def domains(self) -> list[str]:
        rows = self.db.query(
            "SELECT DISTINCT domain FROM assessments "
            "WHERE domain IS NOT NULL AND domain != '' ORDER BY domain"
        )
        return [r["domain"] for r in rows]

    def delete(self, assessment_id: str) -> bool:
        cur = self.db.execute(
            "DELETE FROM assessments WHERE id = ?", (assessment_id,)
        )
        return cur.rowcount > 0

    def children(self, parent_id: str) -> list[dict[str, Any]]:
        return self.db.query(
            "SELECT * FROM assessments WHERE parent_assessment_id = ? "
            "ORDER BY created_at ASC",
            (parent_id,),
        )


class AssessmentDocumentRepository:
    """Join table preserving which documents produced an assessment."""

    def __init__(self, db: Database | None = None):
        self.db = db or get_db()

    def link(self, assessment_id: str, documents: list[dict[str, Any]]) -> None:
        self.db.execute(
            "DELETE FROM assessment_documents WHERE assessment_id = ?",
            (assessment_id,),
        )
        for position, document in enumerate(documents):
            self.db.execute(
                "INSERT INTO assessment_documents "
                "(assessment_id, document_id, filename, position, uploaded_at, "
                "page_count, char_count) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    assessment_id,
                    document.get("document_id"),
                    document.get("filename"),
                    position,
                    document.get("uploaded_at"),
                    int(document.get("page_count", 0) or 0),
                    int(document.get("char_count", 0) or 0),
                ),
            )

    def list(self, assessment_id: str) -> list[dict[str, Any]]:
        return self.db.query(
            "SELECT * FROM assessment_documents WHERE assessment_id = ? "
            "ORDER BY position ASC",
            (assessment_id,),
        )


class ReviewRepository:
    """Append-only expert review history. Never mutates the AI result."""

    def __init__(self, db: Database | None = None):
        self.db = db or get_db()

    def create(self, **fields: Any) -> dict[str, Any]:
        fields.setdefault("id", new_id("rev_"))
        fields.setdefault("created_at", utcnow())
        fields.setdefault("notes", "")
        fields.setdefault("evidence_ids_json", "[]")
        cols = ", ".join(fields)
        marks = ", ".join("?" for _ in fields)
        self.db.execute(
            f"INSERT INTO assessment_reviews ({cols}) VALUES ({marks})",
            list(fields.values()),
        )
        return fields

    def list(self, assessment_id: str) -> list[dict[str, Any]]:
        return self.db.query(
            "SELECT * FROM assessment_reviews WHERE assessment_id = ? "
            "ORDER BY created_at ASC, id ASC",
            (assessment_id,),
        )

    def latest(self, assessment_id: str) -> dict[str, Any] | None:
        rows = self.db.query(
            "SELECT * FROM assessment_reviews WHERE assessment_id = ? "
            "ORDER BY created_at DESC, id DESC LIMIT 1",
            (assessment_id,),
        )
        return rows[0] if rows else None

    def delete_for_assessment(self, assessment_id: str) -> None:
        self.db.execute(
            "DELETE FROM assessment_reviews WHERE assessment_id = ?",
            (assessment_id,),
        )


class EventRepository:
    """Append-only assessment activity timeline."""

    def __init__(self, db: Database | None = None):
        self.db = db or get_db()

    def create(self, **fields: Any) -> dict[str, Any]:
        fields.setdefault("id", new_id("evt_"))
        fields.setdefault("at", utcnow())
        fields.setdefault("description", "")
        fields.setdefault("metadata_json", "{}")
        cols = ", ".join(fields)
        marks = ", ".join("?" for _ in fields)
        self.db.execute(
            f"INSERT INTO assessment_events ({cols}) VALUES ({marks})",
            list(fields.values()),
        )
        return fields

    def list(self, assessment_id: str) -> list[dict[str, Any]]:
        return self.db.query(
            "SELECT * FROM assessment_events WHERE assessment_id = ? "
            "ORDER BY at ASC, id ASC",
            (assessment_id,),
        )

    def delete_for_assessment(self, assessment_id: str) -> None:
        self.db.execute(
            "DELETE FROM assessment_events WHERE assessment_id = ?",
            (assessment_id,),
        )


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, default=str)
