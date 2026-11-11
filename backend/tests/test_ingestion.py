"""Tests for STEP 1 - document ingestion (PDF / DOCX / TXT) and validation."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.services.ingestion import (
    DocumentValidationError,
    extract_document,
    validate_upload,
)
from tests.conftest import SAMPLE_TXT, make_docx, make_pdf, make_txt


# ----------------------------------------------------------------------
# TXT
# ----------------------------------------------------------------------
def test_txt_extraction_basic(tmp_path: Path):
    path = make_txt(tmp_path / "sample.txt")
    result = extract_document(path)

    assert result.file_type == "txt"
    assert result.char_count > 500
    assert "membrane distillation" in result.full_text.lower()
    assert result.units, "TXT must produce at least one text unit"
    assert result.units[0].page == 1
    assert result.units[0].locator.startswith("line ")


def test_txt_preserves_line_locations(tmp_path: Path):
    path = make_txt(tmp_path / "sample.txt")
    result = extract_document(path)
    locators = [u.locator for u in result.units]
    assert all(loc.startswith("line ") for loc in locators)
    # Locators must be monotonically increasing
    numbers = [int(loc.split()[1]) for loc in locators]
    assert numbers == sorted(numbers)


def test_txt_form_feed_creates_pages(tmp_path: Path):
    content = "First page content about principles and concepts here.\n\f\n" \
              "Second page content about laboratory tests and results."
    path = tmp_path / "paged.txt"
    path.write_text(content, encoding="utf-8")
    result = extract_document(path)

    assert result.page_count == 2
    assert [u.page for u in result.units] == [1, 2]


# ----------------------------------------------------------------------
# PDF
# ----------------------------------------------------------------------
def test_pdf_extraction_with_page_numbers(tmp_path: Path):
    path = make_pdf(tmp_path / "sample.pdf")
    result = extract_document(path)

    assert result.file_type == "pdf"
    assert result.page_count == 3, "each PDF page must be extracted separately"
    assert len(result.units) == 3
    assert [u.page for u in result.units] == [1, 2, 3]
    assert [u.locator for u in result.units] == ["page 1", "page 2", "page 3"]

    # Content must live on the page it came from
    page1 = result.units[0].text
    page3 = result.units[2].text
    assert "scientific principle" in page1.lower()
    assert "field trial" in page3.lower()
    assert "field trial" not in page1.lower()


def test_pdf_headings_detected(tmp_path: Path):
    path = make_pdf(tmp_path / "sample.pdf")
    result = extract_document(path)
    assert any("Principles" in heading for heading in result.headings)


# ----------------------------------------------------------------------
# DOCX
# ----------------------------------------------------------------------
def test_docx_extraction(tmp_path: Path):
    path = make_docx(tmp_path / "sample.docx")
    result = extract_document(path)

    assert result.file_type == "docx"
    assert "proof-of-concept experiment was performed" in result.full_text
    # DOCX has no fixed pagination: page_count must be 0 (never invented)
    assert result.page_count == 0
    assert any(u.locator.startswith("paragraph ") for u in result.units)
    assert any("no fixed pagination" in w.lower() for w in result.warnings)
    # Headings come from Word heading styles
    assert any("Background" in h or "Experiments" in h for h in result.headings)


def test_docx_table_extracted(tmp_path: Path):
    path = make_docx(tmp_path / "sample.docx")
    result = extract_document(path)
    assert result.table_count >= 1
    table_units = [u for u in result.units if u.locator.startswith("table ")]
    assert table_units and "18.4" in table_units[0].text


# ----------------------------------------------------------------------
# Validation
# ----------------------------------------------------------------------
def test_validate_accepts_allowed_types():
    assert validate_upload("report.pdf", 1024) == ".pdf"
    assert validate_upload("report.docx", 1024) == ".docx"
    assert validate_upload("report.txt", 1024) == ".txt"
    assert validate_upload("REPORT.PDF", 1024) == ".pdf"


def test_validate_rejects_unsupported_type():
    with pytest.raises(DocumentValidationError) as exc:
        validate_upload("malware.exe", 1024)
    assert exc.value.code == "unsupported_type"
    assert exc.value.status == 415


def test_validate_rejects_empty_file():
    with pytest.raises(DocumentValidationError) as exc:
        validate_upload("empty.txt", 0)
    assert exc.value.code == "empty_file"


def test_validate_rejects_oversized_file(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE_MB", 1)
    with pytest.raises(DocumentValidationError) as exc:
        validate_upload("big.pdf", 5 * 1024 * 1024)
    assert exc.value.code == "file_too_large"
    assert exc.value.status == 413


def test_validate_rejects_missing_filename():
    with pytest.raises(DocumentValidationError) as exc:
        validate_upload("", 100)
    assert exc.value.code == "missing_filename"


def test_extract_missing_file_raises(tmp_path: Path):
    with pytest.raises(DocumentValidationError) as exc:
        extract_document(tmp_path / "does_not_exist.pdf")
    assert exc.value.code == "file_not_found"


def test_extract_unsupported_extension(tmp_path: Path):
    path = tmp_path / "data.csv"
    path.write_text("a,b\n1,2", encoding="utf-8")
    with pytest.raises(DocumentValidationError) as exc:
        extract_document(path)
    assert exc.value.code == "unsupported_type"


# ----------------------------------------------------------------------
# Content sanity (no fabricated content)
# ----------------------------------------------------------------------
def test_sample_document_content_is_traceable(tmp_path: Path):
    path = make_txt(tmp_path / "sample.txt")
    raw = path.read_text(encoding="utf-8")
    result = extract_document(path)
    for unit in result.units:
        # Every extracted unit must be traceable to the source file
        assert unit.text[:60] in raw or unit.text.split()[0] in raw
    assert SAMPLE_TXT.splitlines()[0] in raw
