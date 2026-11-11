"""Document upload endpoints (ingestion entry point)."""
from __future__ import annotations

import shutil
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.core.config import settings
from app.core.database import DocumentRepository, dump_json, new_id
from app.core.logging import get_logger
from app.schemas.document import DocumentInfo, DocumentUploadResponse, PageText
from app.services.assessment_service import save_extracted
from app.services.ingestion import (
    DocumentValidationError,
    ExtractedDocument,
    extract_document,
    validate_upload,
)

logger = get_logger("api.documents")

router = APIRouter(prefix="/api/documents", tags=["documents"])

PREVIEW_CHARS = 4000
PREVIEW_PAGE_CHARS = 1200


def _preview_payload(extracted: ExtractedDocument) -> tuple[str, list[PageText]]:
    preview = extracted.full_text[:PREVIEW_CHARS]
    pages: list[PageText] = []
    for unit in extracted.units[:6]:
        pages.append(
            PageText(
                page=unit.page or 0,
                text=unit.text[:PREVIEW_PAGE_CHARS],
                chars=len(unit.text),
            )
        )
    return preview, pages


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(file: UploadFile = File(...)) -> DocumentUploadResponse:
    """Validate, store and extract an uploaded PDF/DOCX/TXT document."""
    original_name = file.filename or "uploaded_document"
    data = await file.read()

    try:
        ext = validate_upload(original_name, len(data))
    except DocumentValidationError as exc:
        raise HTTPException(exc.status, detail={"detail": str(exc), "code": exc.code})

    if len(data) == 0:
        raise HTTPException(
            400, detail={"detail": "The uploaded file is empty.", "code": "empty_file"}
        )

    doc_id = new_id("doc_")
    storage_path = settings.UPLOAD_DIR / f"{doc_id}{ext}"
    extracted_path = settings.EXTRACTED_DIR / f"{doc_id}.json"

    try:
        with storage_path.open("wb") as fh:
            fh.write(data)
    except OSError as exc:  # pragma: no cover - disk error
        logger.error("Failed to store upload: %s", exc)
        raise HTTPException(
            500, detail={"detail": "Could not store the uploaded file.", "code": "storage_error"}
        )

    try:
        extracted = extract_document(storage_path, original_name)
    except DocumentValidationError as exc:
        storage_path.unlink(missing_ok=True)
        raise HTTPException(exc.status, detail={"detail": str(exc), "code": exc.code})
    except Exception as exc:  # noqa: BLE001 - unexpected parser failure
        storage_path.unlink(missing_ok=True)
        logger.exception("Extraction failed for %s", original_name)
        raise HTTPException(
            422,
            detail={
                "detail": f"Could not extract text from the document: {exc}",
                "code": "extraction_failed",
            },
        )

    if not extracted.units:
        storage_path.unlink(missing_ok=True)
        raise HTTPException(
            422,
            detail={
                "detail": "No text could be extracted from this document. "
                          "It may be an image-only scan (enable OCR to support those).",
                "code": "no_text_extracted",
            },
        )

    save_extracted(extracted_to_payload(extracted), str(extracted_path))

    repo = DocumentRepository()
    record = repo.create(
        id=doc_id,
        filename=storage_path.name,
        original_name=original_name,
        file_type=ext.lstrip("."),
        size_bytes=len(data),
        page_count=extracted.page_count,
        char_count=extracted.char_count,
        storage_path=str(storage_path),
        extracted_path=str(extracted_path),
        metadata_json=dump_json(extracted.metadata),
    )

    preview, pages = _preview_payload(extracted)
    return DocumentUploadResponse(
        id=record["id"],
        filename=storage_path.name,
        original_name=original_name,
        file_type=ext.lstrip("."),
        size_bytes=len(data),
        page_count=extracted.page_count,
        char_count=extracted.char_count,
        uploaded_at=record["uploaded_at"],
        preview_text=preview,
        preview_pages=pages,
        headings=extracted.headings[:30],
        has_tables=extracted.has_tables,
        ocr_used=extracted.ocr_used,
        warnings=extracted.warnings,
        extraction_method=extracted.method,
        metadata=extracted.metadata,
    )


@router.get("", response_model=list[DocumentInfo])
def list_documents() -> list[DocumentInfo]:
    """List uploaded documents (most recent first) for multi-document selection."""
    return [
        DocumentInfo(
            id=record["id"],
            filename=record["filename"],
            original_name=record["original_name"],
            file_type=record["file_type"],
            size_bytes=record.get("size_bytes", 0),
            page_count=record.get("page_count", 0),
            char_count=record.get("char_count", 0),
            uploaded_at=record["uploaded_at"],
        )
        for record in DocumentRepository().list()
    ]


@router.get("/{document_id}", response_model=DocumentInfo)
def get_document(document_id: str) -> DocumentInfo:
    repo = DocumentRepository()
    record = repo.get(document_id)
    if record is None:
        raise HTTPException(
            404, detail={"detail": "Document not found.", "code": "not_found"}
        )
    return DocumentInfo(
        id=record["id"],
        filename=record["filename"],
        original_name=record["original_name"],
        file_type=record["file_type"],
        size_bytes=record["size_bytes"],
        page_count=record["page_count"],
        char_count=record["char_count"],
        uploaded_at=record["uploaded_at"],
    )


def extracted_to_payload(extracted: ExtractedDocument) -> dict[str, Any]:
    from app.services.assessment_service import extracted_to_dict

    return extracted_to_dict(extracted)
