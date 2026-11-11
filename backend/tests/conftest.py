"""Shared pytest fixtures for the TRL INSIGHT backend test suite.

Tests use an isolated temporary database and upload directories so the
developer's real data is never touched.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config.framework import get_framework  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.core.database import Database, set_db  # noqa: E402

SAMPLE_TXT = """Solar-Powered Membrane Distillation Unit: Technical Report

1. Introduction

The present device operates on the principle of membrane distillation, a
thermally driven separation process in which only water vapour passes
through a hydrophobic microporous membrane. The underlying mechanism is
the vapour pressure difference created across the membrane.

2. Concept

We propose a compact solar-driven membrane distillation module intended
for off-grid brackish water treatment. A feasibility study was carried
out to identify the target application of the unit.

3. Proof of Concept

A proof-of-concept experiment was performed in the laboratory. Results
show a permeate flux of 18.4 L/m2h at a feed temperature of 70 C. The
measured values agreed with the theoretical prediction within 6 percent.

4. Laboratory Validation

Laboratory tests were conducted on the integrated prototype using a
controlled test bench. The membrane module was tested under controlled
conditions and the salt rejection was measured at 99.7 percent.

5. Relevant Environment Testing

The integrated subsystem was validated in a relevant environment using a
pilot-scale rig installed at the pilot plant, where conditions varied
realistically. The system achieved an average flux of 15.1 L/m2h under
representative conditions.

6. Prototype Demonstration

A full prototype demonstration was carried out at the semi-field test
site. The integrated prototype was demonstrated in the relevant
environment over three weeks and all major issues were corrected.

7. Field Trial

A field trial was organised at the customer site. The system prototype
was demonstrated in the operational environment during a 60-day on-site
trial. Data from the field trial show stable operation with only two
membrane cleaning events.

8. Future Work

In future work, the system will be deployed for commercial deployment,
and qualification testing will be performed to certify the unit.

9. Conclusion

The device has not yet been certified, so it is not yet qualified for
series production. Nevertheless, laboratory and field evidence
demonstrates readiness up to operational demonstration.
"""


@pytest.fixture(scope="session")
def framework():
    return get_framework()


@pytest.fixture()
def isolated_env(tmp_path, monkeypatch):
    """Point uploads/extracted files at a temp dir and the DB at a temp file."""
    uploads = tmp_path / "uploads"
    extracted = tmp_path / "extracted"
    uploads.mkdir()
    extracted.mkdir()
    monkeypatch.setattr(settings, "UPLOAD_DIR", uploads)
    monkeypatch.setattr(settings, "EXTRACTED_DIR", extracted)
    db_path = tmp_path / "test.db"
    set_db(Database(str(db_path)))
    return tmp_path


@pytest.fixture()
def client(isolated_env):
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


def make_txt(path: Path, content: str = SAMPLE_TXT) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def make_txt(path: Path, content: str = SAMPLE_TXT) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def make_pdf(path: Path, pages: list[str] | None = None) -> Path:
    """Create a real PDF with fpdf2 (one string per page)."""
    from fpdf import FPDF

    pages = pages or [
        "Principles and Concept\n\n"
        "The underlying scientific principle is described here. We propose a "
        "compact technology concept for water treatment. A feasibility study "
        "was carried out for the intended application.",
        "Experimental Results\n\n"
        "A proof-of-concept experiment was performed in the laboratory. "
        "Laboratory tests were conducted on the integrated components. "
        "Results show a measured flux of 18.4 L/m2h at 70 degrees Celsius.",
        "Field Evaluation\n\n"
        "The system prototype was demonstrated in the operational environment "
        "during a sixty day field trial at the customer site. Data from the "
        "field trial show stable operation over the whole period.",
    ]
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=False)
    for index, content in enumerate(pages):
        pdf.add_page()
        pdf.set_font("Helvetica", size=11)
        pdf.multi_cell(0, 6, content)
        pdf.set_font("Helvetica", size=8)
        pdf.set_xy(15, 275)
        pdf.cell(0, 5, f"Page marker {index + 1}")
    pdf.output(str(path))
    return path


def make_docx(path: Path) -> Path:
    """Create a real DOCX with python-docx (heading + paragraphs + table)."""
    from docx import Document
    from docx.shared import Pt

    doc = docx = Document()
    doc.add_heading("Technology Readiness Report", level=1)
    doc.add_heading("Background", level=2)
    doc.add_paragraph(
        "The underlying scientific principle of the device was studied in "
        "this work. We propose a compact technology concept for water "
        "treatment applications."
    )
    doc.add_heading("Experiments", level=2)
    doc.add_paragraph(
        "A proof-of-concept experiment was performed in the laboratory. "
        "Laboratory tests were conducted on the integrated components and "
        "the measured flux reached 18.4 L/m2h."
    )
    table = doc.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Parameter"
    table.cell(0, 1).text = "Value"
    table.cell(1, 0).text = "Flux"
    table.cell(1, 1).text = "18.4 L/m2h"
    doc.add_paragraph(
        "The subsystem was validated in a relevant environment using a "
        "pilot-scale rig under representative conditions."
    )
    doc.save(str(path))
    return path


def upload(client, filename: str, content: bytes) -> dict:
    response = client.post(
        "/api/documents/upload",
        files={"file": (filename, io.BytesIO(content), "application/octet-stream")},
    )
    assert response.status_code == 200, response.text
    return response.json()
