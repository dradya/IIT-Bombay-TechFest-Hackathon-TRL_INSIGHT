"""STEP 1 - Document ingestion (PDF / DOCX / TXT).

Extracts text with page-level (or paragraph/line-level) source locations,
headings, tables where possible, and metadata. Page numbers are only
reported when the format actually has pages - they are never invented.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger
from app.utils.text import is_heading

logger = get_logger("ingestion")

MIN_CHARS_PER_PAGE = 20  # below this a PDF page is treated as scanned


class DocumentValidationError(ValueError):
    """Raised for invalid uploads; carries an API-friendly error code."""

    def __init__(self, message: str, code: str = "invalid_document", status: int = 400):
        super().__init__(message)
        self.code = code
        self.status = status


@dataclass
class PageUnit:
    """A source-located unit of extracted text."""

    page: int | None
    locator: str
    text: str
    chars: int = 0


@dataclass
class ExtractedDocument:
    filename: str
    file_type: str
    units: list[PageUnit] = field(default_factory=list)
    headings: list[str] = field(default_factory=list)
    table_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    method: str = "text"
    ocr_used: bool = False

    @property
    def full_text(self) -> str:
        return "\n\n".join(u.text for u in self.units if u.text.strip())

    @property
    def page_count(self) -> int:
        pages = [u.page for u in self.units if u.page is not None]
        return max(pages) if pages else 0

    @property
    def char_count(self) -> int:
        return len(self.full_text)

    @property
    def has_tables(self) -> bool:
        return self.table_count > 0

    def preview(self, chars: int = 4000) -> str:
        return self.full_text[:chars]


# ----------------------------------------------------------------------
# Validation
# ----------------------------------------------------------------------
def validate_upload(filename: str, size_bytes: int) -> str:
    """Validate name/size/type. Returns the lower-cased extension."""
    if not filename or not filename.strip():
        raise DocumentValidationError("A file name is required.", "missing_filename")
    ext = Path(filename).suffix.lower()
    if ext not in settings.ALLOWED_EXTENSIONS:
        allowed = ", ".join(settings.ALLOWED_EXTENSIONS).upper()
        raise DocumentValidationError(
            f"Unsupported file type '{ext or 'unknown'}'. Allowed types: {allowed}.",
            "unsupported_type",
            status=415,
        )
    if size_bytes <= 0:
        raise DocumentValidationError("The uploaded file is empty.", "empty_file")
    if size_bytes > settings.max_upload_bytes:
        limit_mb = settings.MAX_UPLOAD_SIZE_MB
        raise DocumentValidationError(
            f"File is too large ({size_bytes // (1024 * 1024)} MB). "
            f"Maximum allowed size is {limit_mb} MB.",
            "file_too_large",
            status=413,
        )
    return ext


# ----------------------------------------------------------------------
# PDF
# ----------------------------------------------------------------------
def _import_pymupdf():
    try:
        import pymupdf  # type: ignore

        return pymupdf
    except ImportError:  # pragma: no cover - legacy package name
        try:
            import fitz  # type: ignore

            return fitz
        except ImportError as exc:  # pragma: no cover - defensive
            raise DocumentValidationError(
                "PDF support requires PyMuPDF (pip install PyMuPDF).",
                "missing_dependency",
                status=500,
            ) from exc


def _pdf_tables(page: Any, warnings: list[str]) -> list[str]:
    """Extract table text via PyMuPDF, falling back to pdfplumber."""
    rows_out: list[str] = []
    try:
        finder = getattr(page, "find_tables", None)
        if finder is None:
            raise AttributeError("find_tables unavailable")
        for table in finder().tables:
            rows = table.extract() or []
            for row in rows[:200]:
                cells = [re.sub(r"\s+", " ", str(c or "")).strip() for c in row]
                line = " | ".join(c for c in cells if c)
                if line.strip(" |"):
                    rows_out.append(line)
    except Exception as exc:  # noqa: BLE001 - optional enhancement
        logger.debug("PyMuPDF table extraction failed: %s", exc)
        try:
            import pdfplumber  # type: ignore

            with pdfplumber.open(_LAST_PDF_PATH["path"]) as pdf:
                page_no = int(page.number)
                if 0 <= page_no < len(pdf.pages):
                    for table in pdf.pages[page_no].extract_tables() or []:
                        for row in table[:200]:
                            cells = [str(c or "").strip() for c in row]
                            line = " | ".join(c for c in cells if c)
                            if line.strip(" |"):
                                rows_out.append(line)
        except Exception as exc2:  # noqa: BLE001
            warnings.append(
                "Table extraction unavailable for this PDF "
                f"({type(exc2).__name__}); table cells may be missing from the text."
            )
    return rows_out


_LAST_PDF_PATH: dict[str, str] = {}


def _ocr_page(page: Any, warnings: list[str]) -> str:
    """Optional OCR for scanned pages; degrades gracefully."""
    if not settings.OCR_ENABLED:
        return ""
    try:
        import pytesseract  # type: ignore
        from PIL import Image  # type: ignore
        import io

        if settings.TESSERACT_CMD:
            pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD
        pix = page.get_pixmap(dpi=200)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        return pytesseract.image_to_string(img) or ""
    except ImportError:
        warnings.append(
            "OCR requested but pytesseract/Pillow are not installed "
            "(pip install pytesseract pillow). Scanned pages were skipped."
        )
    except Exception as exc:  # noqa: BLE001 - Tesseract binary missing
        warnings.append(
            f"OCR unavailable ({type(exc).__name__}: {exc}). "
            "Install Tesseract-OCR to enable text extraction from scanned PDFs."
        )
    return ""


def extract_pdf(path: Path) -> ExtractedDocument:
    pymupdf = _import_pymupdf()
    _LAST_PDF_PATH["path"] = str(path)
    warnings: list[str] = []
    headings: list[str] = []
    units: list[PageUnit] = []
    table_count = 0
    ocr_used = False

    doc = pymupdf.open(str(path))
    try:
        meta = doc.metadata or {}
        metadata = {
            k: v for k, v in {
                "title": meta.get("title"),
                "author": meta.get("author"),
                "subject": meta.get("subject"),
                "creator": meta.get("creator"),
                "pages": doc.page_count,
            }.items() if v
        }
        for index, page in enumerate(doc):
            text = page.get_text("text") or ""
            scanned = len(text.strip()) < MIN_CHARS_PER_PAGE
            if scanned:
                ocr_text = _ocr_page(page, warnings)
                if ocr_text.strip():
                    text = ocr_text
                    ocr_used = True
                elif settings.OCR_ENABLED:
                    warnings.append(
                        f"Page {index + 1} appears to be scanned and OCR is unavailable."
                    )
            tables = _pdf_tables(page, warnings)
            if tables:
                table_count += len(tables)
                text = (text + "\n\n" + "\n".join(tables)).strip()
            text = text.strip()
            if not text:
                continue
            units.append(
                PageUnit(page=index + 1, locator=f"page {index + 1}", text=text, chars=len(text))
            )
            for line in text.splitlines():
                if is_heading(line) and len(headings) < 200:
                    h = line.strip()
                    if h not in headings:
                        headings.append(h)
        if not units:
            warnings.append(
                "No extractable text found in the PDF. It may be an image-only "
                "scan - enable OCR support (pytesseract + Tesseract-OCR)."
            )
    finally:
        doc.close()

    return ExtractedDocument(
        filename=path.name,
        file_type="pdf",
        units=units,
        headings=headings,
        table_count=table_count,
        metadata=metadata,
        warnings=warnings,
        method="pymupdf+ocr" if ocr_used else "pymupdf",
        ocr_used=ocr_used,
    )


# ----------------------------------------------------------------------
# DOCX
# ----------------------------------------------------------------------
def extract_docx(path: Path) -> ExtractedDocument:
    try:
        from docx import Document as DocxDocument
        from docx.table import Table as DocxTable
        from docx.text.paragraph import Paragraph as DocxParagraph
    except ImportError as exc:  # pragma: no cover - defensive
        raise DocumentValidationError(
            "DOCX support requires python-docx (pip install python-docx).",
            "missing_dependency",
            status=500,
        ) from exc

    warnings: list[str] = []
    doc = DocxDocument(str(path))
    units: list[PageUnit] = []
    headings: list[str] = []
    table_count = 0
    para_no = 0
    table_no = 0

    # Walk the body in document order to keep paragraph numbering stable.
    body = doc.element.body
    for child in body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            para = DocxParagraph(child, doc)
            text = (para.text or "").strip()
            if not text:
                continue
            para_no += 1
            style = (para.style.name if para.style is not None else "") or ""
            if style.lower().startswith("heading") or style.lower().title() == "Title":
                if text not in headings and len(headings) < 200:
                    headings.append(text)
            units.append(
                PageUnit(page=None, locator=f"paragraph {para_no}", text=text, chars=len(text))
            )
        elif tag == "tbl":
            table_no += 1
            table = DocxTable(child, doc)
            lines: list[str] = []
            for row in table.rows[:300]:
                cells = [re.sub(r"\s+", " ", c.text or "").strip() for c in row.cells]
                line = " | ".join(c for c in cells if c)
                if line.strip(" |"):
                    lines.append(line)
            if lines:
                table_count += 1
                text = "[Table]\n" + "\n".join(lines)
                units.append(
                    PageUnit(page=None, locator=f"table {table_no}", text=text, chars=len(text))
                )

    if not units:
        warnings.append("The DOCX file contains no text.")

    props = doc.core_properties or None
    metadata: dict[str, Any] = {}
    if props is not None:
        for key, value in (
            ("title", getattr(props, "title", None)),
            ("author", getattr(props, "author", None)),
            ("subject", getattr(props, "subject", None)),
        ):
            if value:
                metadata[key] = str(value)

    warnings.append(
        "DOCX files have no fixed pagination: evidence references use "
        "paragraph/table locations instead of page numbers."
    )
    return ExtractedDocument(
        filename=path.name,
        file_type="docx",
        units=units,
        headings=headings,
        table_count=table_count,
        metadata=metadata,
        warnings=warnings,
        method="python-docx",
    )


# ----------------------------------------------------------------------
# TXT
# ----------------------------------------------------------------------
def extract_txt(path: Path) -> ExtractedDocument:
    warnings: list[str] = []
    raw = path.read_bytes()
    text: str | None = None
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            text = raw.decode(encoding)
            break
        except (UnicodeDecodeError, LookupError):
            continue
    if text is None:  # pragma: no cover - latin-1 always succeeds
        text = raw.decode("utf-8", errors="replace")

    units: list[PageUnit] = []
    headings: list[str] = []

    if "\f" in text:  # explicit page breaks are honoured
        pages = text.split("\f")
        for index, page_text in enumerate(pages):
            page_text = page_text.strip()
            if not page_text:
                continue
            units.append(
                PageUnit(
                    page=index + 1,
                    locator=f"page {index + 1}",
                    text=page_text,
                    chars=len(page_text),
                )
            )
    else:
        # No pagination in plain text: use paragraph blocks with line numbers.
        offset_line = 1
        blocks = re.split(r"\n\s*\n", text)
        for block in blocks:
            if not block.strip():
                offset_line += block.count("\n") + 1
                continue
            line_count = block.count("\n") + 1
            units.append(
                PageUnit(
                    page=1,
                    locator=f"line {offset_line}",
                    text=block.strip(),
                    chars=len(block.strip()),
                )
            )
            offset_line += line_count

    for unit in units:
        for line in unit.text.splitlines():
            if is_heading(line) and len(headings) < 200:
                h = line.strip()
                if h not in headings:
                    headings.append(h)

    if not units:
        warnings.append("The text file is empty.")

    return ExtractedDocument(
        filename=path.name,
        file_type="txt",
        units=units,
        headings=headings,
        metadata={"encoding": "detected"},
        warnings=warnings,
        method="text",
    )


# ----------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------
EXTRACTORS = {
    ".pdf": extract_pdf,
    ".docx": extract_docx,
    ".txt": extract_txt,
}


def _parse_with_docling(path: Path, original_name: str | None) -> ExtractedDocument | None:
    """Try the optional Docling adapter; ``None`` means use the native parser."""
    parser = (settings.PARSER or "auto").strip().lower()
    if parser == "native":
        return None
    if path.suffix.lower() not in {".pdf", ".docx"}:
        # Docling's value is layout modelling for paginated/office formats;
        # plain text stays on the deterministic native path.
        return None
    try:
        from app.services.docling_adapter import (
            docling_available,
            extract_with_docling,
        )
    except Exception as exc:  # pragma: no cover - defensive import guard
        logger.debug("Docling adapter unavailable: %s", exc)
        return None
    if parser == "docling" and not docling_available():
        logger.warning(
            "TRL_PARSER=docling but the docling package is not installed; "
            "using the native extractor."
        )
        return None
    if parser == "auto" and not docling_available():
        return None
    return extract_with_docling(path, original_name)


def extract_document(path: str | Path, original_name: str | None = None) -> ExtractedDocument:
    """Extract text from an uploaded document based on its extension.

    Optional Docling parsing is attempted first (when installed and enabled);
    any failure silently falls back to the native extractor so the upload
    workflow never depends on an optional package.
    """
    path = Path(path)
    ext = path.suffix.lower()
    extractor = EXTRACTORS.get(ext)
    if extractor is None:
        raise DocumentValidationError(
            f"Unsupported file type '{ext}'.", "unsupported_type", status=415
        )
    if not path.is_file():
        raise DocumentValidationError("Stored file not found.", "file_not_found", status=404)

    result = _parse_with_docling(path, original_name) or extractor(path)
    if original_name:
        result.metadata["original_name"] = original_name
    logger.info(
        "Extracted %s (%d units, %d chars, method=%s)",
        original_name or path.name,
        len(result.units),
        result.char_count,
        result.method,
    )
    return result
