"""Optional Docling extraction adapter.

Docling (MIT licence) provides layout-aware parsing with page provenance,
headings, tables and reading order. It is an *optional* enhancement: if the
package is not installed, the model files cannot be loaded or conversion fails,
the caller falls back to the native PyMuPDF / pdfplumber / python-docx
extractors. No content is invented on failure.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

from app.core.logging import get_logger
from app.services.ingestion import ExtractedDocument, PageUnit

logger = get_logger("docling")


def docling_available() -> bool:
    """True when the optional ``docling`` package can be imported."""
    return importlib.util.find_spec("docling") is not None


def _page_of(item: Any) -> int | None:
    for prov in getattr(item, "prov", None) or []:
        page = getattr(prov, "page_no", None)
        if page:
            try:
                return int(page)
            except (TypeError, ValueError):
                continue
    return None


def _label_of(item: Any) -> str:
    label = getattr(item, "label", "")
    return str(getattr(label, "value", label) or "")


def _item_text(item: Any) -> str:
    """Render one Docling item, preferring markdown for tables."""
    label = _label_of(item)
    if label == "table":
        exporter = getattr(item, "export_to_markdown", None)
        if callable(exporter):
            try:
                rendered = exporter()
                if rendered and str(rendered).strip():
                    return str(rendered)
            except Exception as exc:  # noqa: BLE001 - optional exporter
                logger.debug("Docling table export failed: %s", exc)
        data = getattr(item, "data", None)
        table_cells = getattr(data, "table_cells", None) if data is not None else None
        if table_cells:
            try:
                rows: dict[int, list[str]] = {}
                for cell in table_cells:
                    row = int(getattr(cell, "start_row_offset_idx", 0) or 0)
                    rows.setdefault(row, []).append(str(getattr(cell, "text", "") or ""))
                lines = [
                    " | ".join(value for value in values if value).strip()
                    for _, values in sorted(rows.items())
                ]
                return "\n".join(line for line in lines if line)
            except Exception as exc:  # noqa: BLE001
                logger.debug("Docling table cell fallback failed: %s", exc)
    return str(getattr(item, "text", "") or "")


def extract_with_docling(
    path: Path, original_name: str | None = None
) -> ExtractedDocument | None:
    """Convert a PDF/DOCX with Docling. Returns ``None`` on any failure."""
    try:
        from docling.document_converter import DocumentConverter  # type: ignore
    except Exception as exc:  # noqa: BLE001 - optional dependency
        logger.info("Docling is not available (%s); using native extractors", exc)
        return None

    try:
        converter = DocumentConverter()
        result = converter.convert(str(path))
        document = result.document
    except Exception as exc:  # noqa: BLE001 - model download / parse failure
        logger.warning(
            "Docling conversion failed for %s (%s); falling back to native extraction",
            path.name,
            exc,
        )
        return None

    try:
        # Preserve reading order exactly as Docling emits it.
        ordered: list[tuple[int | None, str]] = []
        headings: list[str] = []
        table_count = 0
        for item, _level in document.iterate_items():
            text = _item_text(item).strip()
            if not text:
                continue
            label = _label_of(item)
            page = _page_of(item)
            if label in {"section_header", "title"}:
                if text not in headings and len(headings) < 200:
                    headings.append(text)
            if label == "table":
                table_count += 1
            ordered.append((page, text))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Docling document iteration failed for %s: %s", path.name, exc)
        return None

    if not ordered:
        logger.info("Docling returned no text for %s; using native extractor", path.name)
        return None

    # Group consecutive items that share a page so sentence pagination stays
    # accurate while reading order is preserved.
    units: list[PageUnit] = []
    buffer: list[str] = []
    current_page: int | None = None
    block = 0

    def flush() -> None:
        nonlocal buffer
        body = "\n\n".join(part for part in buffer if part).strip()
        if not body:
            buffer = []
            return
        locator = (
            f"page {current_page}" if current_page is not None
            else f"docling block {block}"
        )
        units.append(
            PageUnit(page=current_page, locator=locator, text=body, chars=len(body))
        )
        buffer = []

    for page, text in ordered:
        if buffer and page != current_page:
            flush()
            block += 1
        current_page = page
        buffer.append(text)
    flush()

    if not units:  # pragma: no cover - defensive
        return None

    metadata: dict[str, Any] = {"parser": "docling"}
    if original_name:
        metadata["original_name"] = original_name
    try:
        exported = document.export_to_dict()
        doc_meta = exported.get("metadata") if isinstance(exported, dict) else None
        if isinstance(doc_meta, dict):
            for key in ("title", "author", "subject"):
                value = doc_meta.get(key)
                if value:
                    metadata[key] = str(value)
    except Exception:  # noqa: BLE001 - metadata is optional
        pass

    return ExtractedDocument(
        filename=path.name,
        file_type=path.suffix.lower().lstrip("."),
        units=units,
        headings=headings,
        table_count=table_count,
        metadata=metadata,
        warnings=[
            "Docling layout parsing preserved page provenance and reading "
            "order; table content is rendered as text."
        ],
        method="docling",
        ocr_used=False,
    )
