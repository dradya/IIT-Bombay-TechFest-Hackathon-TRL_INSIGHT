"""API endpoint tests including the complete upload -> assess -> export
workflow, error handling and persistence."""
from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from tests.conftest import SAMPLE_TXT, make_docx, make_pdf


def _upload(client, filename: str, content: bytes):
    return client.post(
        "/api/documents/upload",
        files={"file": (filename, io.BytesIO(content), "application/octet-stream")},
    )


# ----------------------------------------------------------------------
# System endpoints
# ----------------------------------------------------------------------
def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["app"] == "TRL INSIGHT"
    assert isinstance(body["model_available"], bool)


def test_trl_reference(client):
    response = client.get("/api/trl/reference")
    assert response.status_code == 200
    body = response.json()
    assert len(body["levels"]) == 9
    assert [level["level"] for level in body["levels"]] == list(range(1, 10))
    assert body["evidence_statuses"] == [
        "confirmed", "not_found", "contradicted", "unclear"
    ]
    assert len(body["milestones"]) == 9
    assert len(body["evidence_categories"]) >= 8
    assert body["assessment_rules"]["ml_weight"] > 0


def test_model_performance_shape_when_unavailable(client, monkeypatch):
    from app.api import meta as meta_module

    monkeypatch.setattr(meta_module, "read_performance", lambda *a, **k: None)
    response = client.get("/api/model/performance")
    assert response.status_code == 200
    body = response.json()
    assert body["available"] is False
    assert body["mode"] == "unavailable"
    assert body["metrics"] == {}
    assert body["confusion_matrix"] is None
    assert body["note"], "an explanation must be provided when metrics are absent"


def test_overview_empty_state(client):
    response = client.get("/api/overview")
    assert response.status_code == 200
    body = response.json()
    assert body["has_data"] is False
    assert body["total_assessments"] == 0
    assert body["recent"] == []


# ----------------------------------------------------------------------
# Upload validation
# ----------------------------------------------------------------------
def test_upload_rejects_wrong_extension(client):
    response = _upload(client, "malware.exe", b"MZ binary content here")
    assert response.status_code == 415
    assert response.json()["code"] == "unsupported_type"


def test_upload_rejects_empty_file(client):
    response = _upload(client, "empty.txt", b"")
    assert response.status_code == 400
    assert response.json()["code"] in ("empty_file", "invalid_document")


def test_upload_rejects_oversized_file(client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE_MB", 1)
    response = _upload(client, "big.pdf", b"0" * (2 * 1024 * 1024))
    assert response.status_code == 413
    assert response.json()["code"] == "file_too_large"


def test_upload_txt_returns_preview(client):
    response = _upload(client, "field_report.txt", SAMPLE_TXT.encode("utf-8"))
    assert response.status_code == 200
    body = response.json()
    assert body["id"].startswith("doc_")
    assert body["file_type"] == "txt"
    assert body["char_count"] > 500
    assert "membrane distillation" in body["preview_text"].lower()
    assert body["preview_pages"], "preview pages must be returned"
    assert body["extraction_method"] == "text"


def test_upload_pdf_and_docx(client, tmp_path: Path):
    pdf_path = make_pdf(tmp_path / "sample.pdf")
    docx_path = make_docx(tmp_path / "sample.docx")

    pdf_resp = _upload(client, "sample.pdf", pdf_path.read_bytes())
    assert pdf_resp.status_code == 200
    pdf_body = pdf_resp.json()
    assert pdf_body["page_count"] == 3
    assert pdf_body["preview_pages"][0]["page"] == 1

    docx_resp = _upload(client, "sample.docx", docx_path.read_bytes())
    assert docx_resp.status_code == 200
    docx_body = docx_resp.json()
    assert docx_body["file_type"] == "docx"
    # DOCX has no pagination - must be 0, not a fabricated number
    assert docx_body["page_count"] == 0
    assert any("no fixed pagination" in w.lower() for w in docx_body["warnings"])


def test_upload_missing_file_field(client):
    response = client.post("/api/documents/upload")
    assert response.status_code == 422


# ----------------------------------------------------------------------
# Complete workflow
# ----------------------------------------------------------------------
def test_full_workflow_txt(client):
    # 1. upload
    upload = _upload(client, "field_report.txt", SAMPLE_TXT.encode("utf-8"))
    assert upload.status_code == 200
    document_id = upload.json()["id"]

    # 2. analyze
    analyze = client.post(
        "/api/assessments/analyze",
        json={
            "document_id": document_id,
            "technology_name": "Solar MD Unit",
            "domain": "Water Treatment",
            "organization": "Test Lab",
            "description": "Solar-driven membrane distillation.",
        },
    )
    assert analyze.status_code == 200, analyze.text
    result = analyze.json()
    assessment_id = result["id"]
    assert result["prediction"]["predicted_trl"] in range(1, 10)
    assert result["metadata"]["technology_name"] == "Solar MD Unit"
    assert result["evidence"], "evidence must be returned"
    assert result["gap_analysis"]["recommendations"]

    # every evidence item is fully formed
    for item in result["evidence"]:
        assert item["statement"]
        assert item["status"] in ("confirmed", "proposed", "contradicted", "unclear")
        assert item["stance"] in ("supporting", "contradicting", "insufficient")
        assert 0.0 <= item["relevance"] <= 1.0

    # 3. retrieve
    fetched = client.get(f"/api/assessments/{assessment_id}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == assessment_id

    # 4. list + filters
    listing = client.get("/api/assessments")
    assert listing.status_code == 200
    assert listing.json()["total"] >= 1
    filtered = client.get("/api/assessments", params={"search": "Solar MD"})
    assert filtered.json()["total"] >= 1
    no_match = client.get("/api/assessments", params={"search": "zzz-no-match"})
    assert no_match.json()["total"] == 0
    trl_filter = client.get(
        "/api/assessments",
        params={"trl": result["prediction"]["predicted_trl"]},
    )
    assert trl_filter.json()["total"] >= 1

    # 5. reports
    json_report = client.get(f"/api/assessments/{assessment_id}/json")
    assert json_report.status_code == 200
    assert json_report.headers["content-type"].startswith("application/json")
    parsed = json.loads(json_report.content.decode("utf-8"))
    assert parsed["prediction"]["predicted_trl"] == result["prediction"]["predicted_trl"]
    assert "attachment" in json_report.headers["content-disposition"]

    pdf_report = client.get(f"/api/assessments/{assessment_id}/report")
    assert pdf_report.status_code == 200
    assert pdf_report.headers["content-type"] == "application/pdf"
    assert pdf_report.content[:5] == b"%PDF-"

    # 6. overview now has data
    overview = client.get("/api/overview").json()
    assert overview["has_data"] is True
    assert overview["total_assessments"] >= 1
    assert len(overview["distribution"]) == 9
    assert overview["activity"]

    # 7. delete
    deleted = client.delete(f"/api/assessments/{assessment_id}")
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True
    assert client.get(f"/api/assessments/{assessment_id}").status_code == 404
    # deleting again -> 404
    assert client.delete(f"/api/assessments/{assessment_id}").status_code == 404


def test_full_workflow_pdf_upload(client, tmp_path: Path):
    pdf_path = make_pdf(tmp_path / "sample.pdf")
    upload = _upload(client, "sample.pdf", pdf_path.read_bytes())
    assert upload.status_code == 200
    document_id = upload.json()["id"]

    analyze = client.post(
        "/api/assessments/analyze",
        json={"document_id": document_id, "technology_name": "PDF Tech"},
    )
    assert analyze.status_code == 200, analyze.text
    result = analyze.json()
    # PDF page numbers must survive into the evidence
    paged = [e for e in result["evidence"] if e["page_number"] is not None]
    assert paged, "PDF evidence must carry page numbers"
    assert all(1 <= e["page_number"] <= 3 for e in paged)
    assert result["processing"]["pages"] == 3


# ----------------------------------------------------------------------
# Error handling
# ----------------------------------------------------------------------
def test_analyze_unknown_document(client):
    response = client.post(
        "/api/assessments/analyze", json={"document_id": "doc_does_not_exist"}
    )
    assert response.status_code == 404
    assert response.json()["code"] == "document_not_found"


def test_analyze_validation_error(client):
    response = client.post("/api/assessments/analyze", json={})
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_get_unknown_assessment(client):
    response = client.get("/api/assessments/asm_missing")
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_report_for_missing_assessment(client):
    assert client.get("/api/assessments/asm_missing/report").status_code == 404
    assert client.get("/api/assessments/asm_missing/json").status_code == 404


def test_report_filename_is_safe_for_unicode_names(client):
    """Unicode / punctuation in the technology name must not break the
    Content-Disposition header or the PDF download."""
    upload = _upload(client, "field_report.txt", SAMPLE_TXT.encode("utf-8"))
    document_id = upload.json()["id"]
    analyze = client.post(
        "/api/assessments/analyze",
        json={
            "document_id": document_id,
            "technology_name": 'Unités Solaires / 太阳能 "Mark II"',
        },
    )
    assert analyze.status_code == 200, analyze.text
    assessment_id = analyze.json()["id"]

    for kind, media in (("report", "application/pdf"), ("json", "application/json")):
        response = client.get(f"/api/assessments/{assessment_id}/{kind}")
        assert response.status_code == 200, response.text
        assert response.headers["content-type"].startswith(media)
        disposition = response.headers["content-disposition"]
        # Header values must stay ASCII, keep the quoted fallback and carry
        # the full name percent-encoded per RFC 5987.
        disposition.encode("ascii")
        assert "attachment;" in disposition
        assert 'filename="' in disposition
        assert "filename*=UTF-8''" in disposition
        assert "\n" not in disposition and "\r" not in disposition


def test_report_generation_handles_pdf_special_characters(client):
    """A technology name with characters that are illegal in filenames must
    still produce a valid PDF (and a valid attachment header)."""
    upload = _upload(client, "field_report.txt", SAMPLE_TXT.encode("utf-8"))
    document_id = upload.json()["id"]
    analyze = client.post(
        "/api/assessments/analyze",
        json={"document_id": document_id, "technology_name": 'A/B:C*D?E"F<G>H|I'},
    )
    assert analyze.status_code == 200, analyze.text
    assessment_id = analyze.json()["id"]

    response = client.get(f"/api/assessments/{assessment_id}/report")
    assert response.status_code == 200, response.text
    assert response.content[:5] == b"%PDF-"
    assert response.headers["content-type"] == "application/pdf"
    disposition = response.headers["content-disposition"]
    assert "attachment;" in disposition
    assert "filename*=UTF-8''" in disposition


def test_unknown_route_returns_json_error(client):
    response = client.get("/api/nope")
    assert response.status_code == 404
    assert "detail" in response.json()


# ----------------------------------------------------------------------
# Single-server mode: deep links must return the SPA shell (refresh/share)
# ----------------------------------------------------------------------
def test_spa_deep_link_returns_index(client):
    from app.main import _DIST

    if not (_DIST / "index.html").is_file():
        pytest.skip("frontend/dist not built")
    for path in ("/history", "/assessments/asm_anything", "/settings"):
        response = client.get(path)
        assert response.status_code == 200
        assert 'id="root"' in response.text
    # Unknown API paths must still be JSON 404s, not the SPA shell.
    assert client.get("/api/nope").headers["content-type"].startswith(
        "application/json"
    )


# ----------------------------------------------------------------------
# Analysis of a document without extracted text (409 conflict)
# ----------------------------------------------------------------------
def test_analyze_document_with_missing_extraction(client, monkeypatch):
    upload = _upload(client, "field_report.txt", SAMPLE_TXT.encode("utf-8"))
    document_id = upload.json()["id"]
    from app.core.database import DocumentRepository

    DocumentRepository().update(document_id, extracted_path=None)
    response = client.post(
        "/api/assessments/analyze", json={"document_id": document_id}
    )
    assert response.status_code == 409
    assert response.json()["code"] == "extraction_missing"
