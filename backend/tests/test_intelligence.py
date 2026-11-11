"""Tests for TRL INSIGHT 2.0 capabilities.

Covers optional-parser fallback, semantic retrieval/caching, multi-document
deduplication and contradictions, uncertainty decomposition, model
explanations, the knowledge graph, roadmap, questionnaire, expert review,
reassessment, timeline and comparison.
"""
from __future__ import annotations

import io
import json
from pathlib import Path

import numpy as np
import pytest

from tests.conftest import SAMPLE_TXT

DOC_A = """Solar Membrane Distillation - Laboratory Report

The underlying scientific principle was studied and the governing equation
was derived for the membrane distillation process.

A proof-of-concept experiment was performed in the laboratory. Results show
a permeate flux of 18.4 L/m2h at a feed temperature of 70 C.

Laboratory tests were conducted on the integrated components and results show
a measured efficiency of 92 percent. The membrane module was tested under
controlled conditions.
"""

DOC_B = """Solar Membrane Distillation - Independent Review

A proof-of-concept experiment was performed in the laboratory. Results show
a permeate flux of 18.4 L/m2h at a feed temperature of 70 C.

Laboratory tests were not conducted on the integrated components because the
test bench was unavailable during the review period.

Qualification testing has not been performed on the final system.
"""


def _upload(client, filename: str, content: str):
    response = client.post(
        "/api/documents/upload",
        files={
            "file": (
                filename,
                io.BytesIO(content.encode("utf-8")),
                "text/plain",
            )
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


# ----------------------------------------------------------------------
# Capabilities and optional parser fallback
# ----------------------------------------------------------------------
def test_capabilities_report_actual_environment(client):
    response = client.get("/api/system/capabilities")
    assert response.status_code == 200
    body = response.json()
    assert body["parser"]["active"] in {"docling", "native"}
    assert body["embeddings"]["active"] in {
        "tfidf", "sentence-transformers", "bge"
    }
    assert body["semantic_retrieval"]["enabled"] is True
    assert body["haystack"]["integrated"] is False
    assert body["osstrl"]["license"] == "BSD-2-Clause"
    assert "note" in body["shap"]
    find = body["embeddings"]["fallback_reason"]
    assert isinstance(find, str)


def test_docling_failure_falls_back_to_native(tmp_path, monkeypatch):
    from app.core.config import settings
    from app.services import ingestion

    monkeypatch.setattr(settings, "PARSER", "docling")
    monkeypatch.setattr(
        "app.services.docling_adapter.docling_available", lambda: True
    )
    monkeypatch.setattr(
        "app.services.docling_adapter.extract_with_docling",
        lambda *args, **kwargs: None,
    )

    path = tmp_path / "note.txt"
    path.write_text(SAMPLE_TXT, encoding="utf-8")
    extracted = ingestion.extract_document(path)
    assert extracted.method == "text"
    assert extracted.units, "native extractor must still produce content"


def test_semantic_retrieval_ranks_evidence(framework):
    from app.services.document_processing import clean_document
    from app.services.evidence import extract_evidence
    from app.services.ingestion import ExtractedDocument, PageUnit
    from app.services.semantic import rank_evidence

    extracted = ExtractedDocument(
        filename="sample.txt",
        file_type="txt",
        units=[PageUnit(page=1, locator="page 1", text=SAMPLE_TXT, chars=len(SAMPLE_TXT))],
    )
    evidence = extract_evidence(
        clean_document(extracted, framework), framework, "sample.txt"
    ).items
    result = rank_evidence(evidence, framework, preferred="tfidf")
    assert result["enabled"] is True
    assert result["backend"] == "tfidf"
    assert len(result["by_milestone"]) == 9
    assert result["note"]
    for item in evidence:
        assert item.semantic_similarity is not None
        assert -1.0 <= item.semantic_similarity <= 1.0
        assert item.semantic_milestone in {m["id"] for m in framework.milestones}


def test_embedding_cache_is_used(tmp_path, monkeypatch):
    from app.services import semantic

    semantic._CACHE.clear()
    monkeypatch.setattr(
        semantic.settings, "EMBEDDING_CACHE_DIR", tmp_path / "embeddings"
    )
    calls = {"n": 0}

    class Stub:
        name = "stub"
        model = "stub-v1"

        def encode(self, texts):
            calls["n"] += 1
            return np.ones((len(texts), 4), dtype=np.float64)

    first, hit_first = semantic._cached_encode(Stub(), ["alpha", "beta"])
    second, hit_second = semantic._cached_encode(Stub(), ["alpha", "beta"])
    assert calls["n"] == 1
    assert hit_first is False
    assert hit_second is True
    assert np.array_equal(first, second)


# ----------------------------------------------------------------------
# Multi-document dedupe and contradictions
# ----------------------------------------------------------------------
def test_multi_document_dedupe_detects_outdated_copies(framework):
    from app.services.ingestion import ExtractedDocument, PageUnit
    from app.services.multidoc import DocumentInput, merge_documents

    def extracted(name: str, text: str):
        return ExtractedDocument(
            filename=name,
            file_type="txt",
            units=[PageUnit(page=1, locator="page 1", text=text, chars=len(text))],
        )

    documents = [
        DocumentInput(
            extracted=extracted("a.txt", DOC_A),
            document_id="doc_a",
            filename="a.txt",
            uploaded_at="2024-01-01T00:00:00+00:00",
        ),
        DocumentInput(
            extracted=extracted("b.txt", DOC_B),
            document_id="doc_b",
            filename="b.txt",
            uploaded_at="2025-01-01T00:00:00+00:00",
        ),
    ]
    merged = merge_documents(documents, framework)
    assert merged.documents
    assert merged.duplicates >= 1
    assert merged.outdated >= 1
    # The repeated proof-of-concept claim is counted once by the rules.
    repeated = [
        item
        for item in merged.unique_evidence
        if "proof-of-concept experiment was performed" in item.statement.lower()
    ]
    assert len(repeated) == 1
    all_copies = [
        item
        for item in merged.all_evidence
        if "proof-of-concept experiment was performed" in item.statement.lower()
    ]
    assert len(all_copies) >= 2
    assert all(item.duplicate_count >= 2 for item in all_copies)


def test_cross_document_contradiction_names_both_sources(framework):
    from app.services.contradictions import detect_contradictions
    from app.services.ingestion import ExtractedDocument, PageUnit
    from app.services.multidoc import DocumentInput, merge_documents

    def extracted(name: str, text: str):
        return ExtractedDocument(
            filename=name,
            file_type="txt",
            units=[PageUnit(page=1, locator="page 1", text=text, chars=len(text))],
        )

    documents = [
        DocumentInput(
            extracted=extracted("a.txt", DOC_A),
            document_id="doc_a",
            filename="a.txt",
            uploaded_at="2024-01-01T00:00:00+00:00",
        ),
        DocumentInput(
            extracted=extracted("b.txt", DOC_B),
            document_id="doc_b",
            filename="b.txt",
            uploaded_at="2025-01-01T00:00:00+00:00",
        ),
    ]
    merged = merge_documents(documents, framework)
    report = detect_contradictions(
        merged.unique_evidence,
        merged.all_evidence,
        framework,
        {"doc_a": "2024-01-01T00:00:00+00:00", "doc_b": "2025-01-01T00:00:00+00:00"},
    )
    assert report["total"] >= 1
    assert report["items"]
    for item in report["items"]:
        assert len(item["sources"]) == 2
        for source in item["sources"]:
            assert source["statement"]
            assert source["source_document"]
        assert item["human_verification"]
        assert item["explanation"]
    assert report["summary"]


# ----------------------------------------------------------------------
# Uncertainty / explainability
# ----------------------------------------------------------------------
def test_uncertainty_is_decomposed_and_not_calibrated(framework):
    from app.services.assessment_service import run_assessment
    from app.services.ingestion import ExtractedDocument, PageUnit

    extracted = ExtractedDocument(
        filename="field_report.txt",
        file_type="txt",
        units=[PageUnit(page=1, locator="page 1", text=SAMPLE_TXT, chars=len(SAMPLE_TXT))],
    )
    result = run_assessment(
        extracted,
        metadata={"filename": "field_report.txt", "technology_name": "MD"},
        framework=framework,
    )
    uncertainty = result["uncertainty"]
    for key in (
        "confidence", "coverage", "completeness", "reliability", "overall",
        "band", "calibrated", "components", "explanation",
    ):
        assert key in uncertainty
    assert uncertainty["calibrated"] is False
    assert uncertainty["calibration_source"] is None
    assert "not calibrated" in uncertainty["calibration_note"].lower()
    for key in ("confidence", "coverage", "completeness", "reliability", "overall"):
        assert 0.0 <= uncertainty[key] <= 1.0
    assert uncertainty["band"] in {"low", "medium", "high"}
    assert result["prediction"]["model_probability"] is not None


def test_model_explanation_explains_classifier_not_sources(framework):
    from app.services.assessment_service import run_assessment
    from app.services.ingestion import ExtractedDocument, PageUnit

    extracted = ExtractedDocument(
        filename="field_report.txt",
        file_type="txt",
        units=[PageUnit(page=1, locator="page 1", text=SAMPLE_TXT, chars=len(SAMPLE_TXT))],
    )
    result = run_assessment(
        extracted,
        metadata={"filename": "field_report.txt", "technology_name": "MD"},
        framework=framework,
    )
    explanation = result["model_explanation"]
    assert explanation["available"] is True
    assert explanation["method"] in {"shap", "linear_coefficients"}
    assert explanation["features"]
    assert explanation["target_trl"] == result["prediction"]["predicted_trl"]
    assert "not source evidence" in explanation["warning"].lower()
    for feature in explanation["features"]:
        assert feature["direction"] in {"supports", "opposes", "neutral"}
        assert feature["kind"] in {"text", "evidence"}
        assert feature["label"]


# ----------------------------------------------------------------------
# Graph, roadmap, questionnaire
# ----------------------------------------------------------------------
def test_graph_roadmap_and_questionnaire_are_grounded(framework):
    from app.services.assessment_service import run_assessment
    from app.services.ingestion import ExtractedDocument, PageUnit

    extracted = ExtractedDocument(
        filename="field_report.txt",
        file_type="txt",
        units=[PageUnit(page=1, locator="page 1", text=SAMPLE_TXT, chars=len(SAMPLE_TXT))],
    )
    result = run_assessment(
        extracted,
        metadata={"filename": "field_report.txt", "technology_name": "MD"},
        framework=framework,
    )

    graph = result["graph"]
    assert graph["node_count"] == len(graph["nodes"])
    assert graph["edge_count"] == len(graph["edges"])
    types = {node["type"] for node in graph["nodes"]}
    assert {"technology", "milestone", "evidence"} <= types
    assert all(node["label"] for node in graph["nodes"])

    roadmap = result["roadmap"]
    assert roadmap["current_trl"] == result["prediction"]["predicted_trl"]
    assert roadmap["note"]
    for phase in roadmap["phases"]:
        assert phase["horizon"] in {"now", "next", "later"}
        assert phase["items"]
        for item in phase["items"]:
            assert item["actions"]
            assert item["success_criteria"]

    questionnaire = result["questionnaire"]
    confirmed = {
        milestone["id"]
        for milestone in result["milestones"]
        if milestone["status"] == "confirmed"
    }
    for question in questionnaire["items"]:
        assert question["milestone"] not in confirmed
        assert question["question"]
        assert question["expected_document"]


# ----------------------------------------------------------------------
# API workflow: multi-document -> review -> reassess -> timeline -> compare
# ----------------------------------------------------------------------
def test_multi_document_api_workflow(client):
    first = _upload(client, "a.txt", DOC_A)
    second = _upload(client, "b.txt", DOC_B)

    response = client.post(
        "/api/assessments/analyze",
        json={
            "document_ids": [first["id"], second["id"]],
            "technology_name": "Solar MD",
            "domain": "Water",
        },
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assessment_id = result["id"]

    assert len(result["documents"]) == 2
    assert result["processing"]["documents"] == 2
    assert result["processing"]["duplicates"] >= 1
    assert result["evidence_summary"]["duplicates"] >= 1
    assert result["contradictions"]["total"] >= 1
    assert result["graph"]["node_count"] > 0
    assert result["uncertainty"]["calibrated"] is False
    assert result["roadmap"]["phases"]
    assert result["questionnaire"]["total"] >= 1

    for suffix, key in (
        ("documents", None),
        ("graph", "nodes"),
        ("contradictions", "items"),
        ("roadmap", "phases"),
        ("questionnaire", "items"),
        ("timeline", "events"),
    ):
        fetched = client.get(f"/api/assessments/{assessment_id}/{suffix}")
        assert fetched.status_code == 200, f"{suffix}: {fetched.text}"
        body = fetched.json()
        if key:
            assert key in body
        else:
            assert isinstance(body, list) and body

    # Listing exposes the additive summary fields.
    listing = client.get("/api/assessments").json()
    row = next(item for item in listing["items"] if item["id"] == assessment_id)
    assert row["document_count"] == 2
    assert row["contradictions_total"] >= 1
    assert row["uncertainty_overall"] is not None

    # Expert review never mutates the AI prediction.
    review = client.post(
        f"/api/assessments/{assessment_id}/reviews",
        json={
            "reviewer_name": "Dr. Reviewer",
            "decision": "accept",
            "notes": "Checked the lab report and the independent review.",
            "evidence_ids": [result["evidence"][0]["id"]],
        },
    )
    assert review.status_code == 200, review.text
    reviews = client.get(f"/api/assessments/{assessment_id}/reviews").json()
    assert reviews["total"] == 1
    assert reviews["review_status"] == "accepted"
    assert reviews["ai_prediction"]["predicted_trl"] == result["prediction"]["predicted_trl"]
    assert reviews["ai_prediction"]["immutable"] is True

    # Reassess using a real questionnaire item.
    question = result["questionnaire"]["items"][0]
    reassess = client.post(
        f"/api/assessments/{assessment_id}/reassess",
        json={
            "reviewer_name": "Dr. Reviewer",
            "reason": "Follow-up documentation supplied",
            "answers": [
                {
                    "milestone_id": question["milestone"],
                    "status": "completed",
                    "evidence_note": "Completed after the review; documented in the follow-up report.",
                    "source_reference": "Follow-up report, section 3",
                }
            ],
        },
    )
    assert reassess.status_code == 200, reassess.text
    child = reassess.json()
    assert child["id"] != assessment_id
    assert child["parent_assessment_id"] == assessment_id
    assert child["reassessment_reason"] == "Follow-up documentation supplied"
    self_reported = [
        item for item in child["evidence"] if item["evidence_type"] == "self_reported"
    ]
    assert self_reported, "expert answer must appear as clearly-labelled evidence"
    assert all(
        item["source_document"] == "Expert questionnaire (self-reported)"
        for item in self_reported
    )

    # Original prediction is unchanged and child is stored.
    original = client.get(f"/api/assessments/{assessment_id}").json()
    assert original["prediction"]["predicted_trl"] == result["prediction"]["predicted_trl"]
    assert client.get(f"/api/assessments/{child['id']}").status_code == 200

    parent_timeline = client.get(
        f"/api/assessments/{assessment_id}/timeline"
    ).json()
    kinds = {event["kind"] for event in parent_timeline["events"]}
    assert "created" in kinds
    assert "review" in kinds
    assert "reassessment" in kinds

    comparison = client.get(
        "/api/assessments/compare",
        params={"ids": f"{assessment_id},{child['id']}"},
    )
    assert comparison.status_code == 200, comparison.text
    items = comparison.json()["items"]
    assert len(items) == 2
    assert all(item["evidence_total"] >= 1 for item in items)


def test_reassess_requires_documents(client):
    uploaded = _upload(client, "note.txt", DOC_A)
    analysis = client.post(
        "/api/assessments/analyze",
        json={"document_id": uploaded["id"], "technology_name": "Doc Tech"},
    ).json()
    # Remove the document link to simulate lost source documents.
    from app.core.database import DocumentRepository

    DocumentRepository().update(uploaded["id"], extracted_path=None)
    response = client.post(
        f"/api/assessments/{analysis['id']}/reassess",
        json={"answers": [], "reason": "retry"},
    )
    assert response.status_code in (409, 500)


def test_compare_requires_two_to_three_ids(client):
    assert (
        client.get("/api/assessments/compare", params={"ids": "asm_only"}).status_code
        == 422
    )
    assert (
        client.get(
            "/api/assessments/compare", params={"ids": "a,b,c,d"}
        ).status_code
        == 422
    )


def test_override_review_requires_reviewed_trl(client):
    uploaded = _upload(client, "note.txt", DOC_A)
    analysis = client.post(
        "/api/assessments/analyze",
        json={"document_id": uploaded["id"], "technology_name": "Doc Tech"},
    ).json()
    response = client.post(
        f"/api/assessments/{analysis['id']}/reviews",
        json={"reviewer_name": "Reviewer", "decision": "override"},
    )
    assert response.status_code == 422


def test_legacy_blocks_return_clear_conflict(client):
    """Stored assessments without 2.0 blocks must not fabricate data."""
    from app.core.database import AssessmentRepository, new_id, utcnow

    legacy_id = new_id("asm_")
    AssessmentRepository().create(
        id=legacy_id,
        document_id=None,
        technology_name="Legacy",
        domain="",
        organization="",
        description="",
        predicted_trl=3,
        confidence=0.5,
        low_confidence=0,
        evidence_coverage=0.4,
        model_mode="rule_only",
        result_json=json.dumps(
            {
                "id": legacy_id,
                "document_id": None,
                "created_at": utcnow(),
                "metadata": {"technology_name": "Legacy", "filename": "old.txt"},
                "prediction": {
                    "predicted_trl": 3,
                    "confidence": 0.5,
                    "evidence_coverage": 0.4,
                    "model_mode": "rule_only",
                },
                "evidence": [],
                "evidence_summary": {"total": 0},
                "milestones": [],
            }
        ),
        created_at=utcnow(),
    )
    for suffix in ("graph", "contradictions", "roadmap", "questionnaire"):
        response = client.get(f"/api/assessments/{legacy_id}/{suffix}")
        assert response.status_code == 409
        assert response.json()["code"] == "not_available"


# ----------------------------------------------------------------------
# Listing filters, sorting and overview aggregates
# ----------------------------------------------------------------------
def _store_assessment(
    *,
    name: str,
    domain: str,
    trl: int,
    confidence: float,
    coverage: float,
    created_at: str,
    low_confidence: bool = False,
    organization: str = "",
) -> str:
    """Store a minimal, honestly-shaped assessment for list/aggregate tests."""
    from app.core.database import AssessmentRepository, new_id

    assessment_id = new_id("asm_")
    AssessmentRepository().create(
        id=assessment_id,
        document_id=None,
        technology_name=name,
        domain=domain,
        organization=organization,
        description="",
        predicted_trl=trl,
        confidence=confidence,
        low_confidence=1 if low_confidence else 0,
        evidence_coverage=coverage,
        model_mode="hybrid",
        result_json=json.dumps(
            {
                "id": assessment_id,
                "document_id": None,
                "created_at": created_at,
                "metadata": {
                    "technology_name": name,
                    "filename": "",
                    "domain": domain,
                },
                "prediction": {
                    "predicted_trl": trl,
                    "confidence": confidence,
                    "evidence_coverage": coverage,
                    "model_mode": "hybrid",
                },
                "evidence": [],
                "evidence_summary": {"total": 0},
                "milestones": [],
            }
        ),
        created_at=created_at,
    )
    return assessment_id


def _seed_filter_fixture() -> dict[str, str]:
    """Three assessments with distinct domain, TRL, confidence and date."""
    return {
        "water_high": _store_assessment(
            name="Membrane Distillation",
            domain="Water",
            trl=4,
            confidence=0.82,
            coverage=0.80,
            created_at="2026-01-10T09:00:00+00:00",
            organization="IIT Bombay",
        ),
        "energy_mid": _store_assessment(
            name="Perovskite Solar Cell",
            domain="Energy",
            trl=7,
            confidence=0.55,
            coverage=0.50,
            created_at="2026-02-10T09:00:00+00:00",
            organization="NREL",
        ),
        "water_low": _store_assessment(
            name="Brackish Water Sensor",
            domain="Water",
            trl=6,
            confidence=0.35,
            coverage=0.30,
            created_at="2026-03-10T09:00:00+00:00",
            low_confidence=True,
        ),
    }


def test_assessment_list_filters_and_sorting(client):
    ids = _seed_filter_fixture()

    def names(query: str) -> list[str]:
        response = client.get(f"/api/assessments{query}")
        assert response.status_code == 200, response.text
        return [item["technology_name"] for item in response.json()["items"]]

    # Whitelisted sorts use the real stored values.
    assert names("?sort=confidence_asc") == [
        "Brackish Water Sensor",
        "Perovskite Solar Cell",
        "Membrane Distillation",
    ]
    assert names("?sort=confidence_desc")[0] == "Membrane Distillation"
    assert names("?sort=trl_desc") == [
        "Perovskite Solar Cell",
        "Brackish Water Sensor",
        "Membrane Distillation",
    ]
    assert names("?sort=trl_asc")[0] == "Membrane Distillation"
    assert names("?sort=coverage_desc")[0] == "Membrane Distillation"
    assert names("?sort=created_asc")[0] == "Membrane Distillation"
    assert names("?sort=created_desc")[0] == "Brackish Water Sensor"

    # Equality and range filters.
    assert sorted(names("?domain=Water")) == [
        "Brackish Water Sensor",
        "Membrane Distillation",
    ]
    assert sorted(names("?trl_min=5")) == [
        "Brackish Water Sensor",
        "Perovskite Solar Cell",
    ]
    assert names("?trl_max=4") == ["Membrane Distillation"]
    assert sorted(names("?trl=6")) == ["Brackish Water Sensor"]
    assert names("?confidence_min=0.8") == ["Membrane Distillation"]
    assert sorted(names("?confidence_min=0.4&confidence_max=0.6")) == [
        "Perovskite Solar Cell",
    ]
    assert names("?low_confidence=true") == ["Brackish Water Sensor"]
    assert names("?search=perovskite") == ["Perovskite Solar Cell"]
    assert sorted(names("?search=water")) == [
        "Brackish Water Sensor",
        "Membrane Distillation",
    ]
    assert names("?search=iit bombay") == ["Membrane Distillation"]

    # Date filters are inclusive at day boundaries.
    assert sorted(names("?date_from=2026-02-01")) == [
        "Brackish Water Sensor",
        "Perovskite Solar Cell",
    ]
    assert names("?date_to=2026-01-31") == ["Membrane Distillation"]

    # Pagination keeps the filtered total independent of the page window.
    page = client.get("/api/assessments", params={"limit": 1, "offset": 1}).json()
    assert page["total"] == 3
    assert len(page["items"]) == 1

    # Validation is explicit rather than silently ignoring bad input.
    assert client.get("/api/assessments?sort=bogus").status_code == 422
    assert client.get("/api/assessments?review_status=bogus").status_code == 422
    assert client.get("/api/assessments?confidence_min=2").status_code == 422
    assert client.get("/api/assessments?trl_min=0").status_code == 422

    # Reviews are append-only and drive the review-status filter.
    from app.core.database import ReviewRepository

    reviews = ReviewRepository()
    reviews.create(
        assessment_id=ids["water_high"],
        reviewer_name="Dr. A",
        decision="accept",
        ai_trl=4,
    )
    reviews.create(
        assessment_id=ids["energy_mid"],
        reviewer_name="Dr. B",
        decision="override",
        ai_trl=7,
        reviewed_trl=6,
    )
    assert names("?review_status=accepted") == ["Membrane Distillation"]
    assert names("?review_status=overridden") == ["Perovskite Solar Cell"]
    assert names("?review_status=unreviewed") == ["Brackish Water Sensor"]
    assert names("?review_status=more_evidence_requested") == []


def test_overview_filters_and_aggregates(client):
    ids = _seed_filter_fixture()
    from app.core.database import ReviewRepository

    ReviewRepository().create(
        assessment_id=ids["water_high"],
        reviewer_name="Dr. A",
        decision="accept",
        ai_trl=4,
    )

    body = client.get("/api/overview").json()
    assert body["has_data"] is True
    assert body["total_assessments"] == 3
    assert body["average_trl"] == pytest.approx((4 + 7 + 6) / 3, abs=0.01)
    assert body["average_confidence"] == pytest.approx((0.82 + 0.55 + 0.35) / 3, abs=0.001)
    assert [row["count"] for row in body["distribution"] if row["trl"] == 4] == [1]
    assert body["confidence"]["high"] == 1
    assert body["confidence"]["medium"] == 1
    assert body["confidence"]["low"] == 1
    assert body["confidence"]["average"] == pytest.approx(0.573, abs=0.001)
    assert body["coverage"]["high"] == 1
    assert body["coverage"]["medium"] == 1
    assert body["coverage"]["low"] == 1
    assert body["reviews"]["unreviewed"] == 2
    assert body["reviews"]["accepted"] == 1
    assert body["reviews"]["awaiting_review"] == 2
    assert {row["domain"]: row["count"] for row in body["domain_distribution"]} == {
        "Water": 2,
        "Energy": 1,
    }

    # Domain scoping is applied consistently to every aggregate.
    water = client.get("/api/overview", params={"domain": "Water"}).json()
    assert water["total_assessments"] == 2
    assert water["average_trl"] == pytest.approx(5.0)
    assert water["confidence"]["high"] == 1
    assert water["confidence"]["low"] == 1
    assert water["reviews"]["unreviewed"] == 1
    assert water["reviews"]["accepted"] == 1
    assert water["domain_distribution"] == [{"domain": "Water", "count": 2}]

    # Date range scoping.
    recent = client.get("/api/overview", params={"date_from": "2026-02-15"}).json()
    assert recent["total_assessments"] == 1
    assert recent["distribution"] == [
        {"trl": level, "count": 1 if level == 6 else 0} for level in range(1, 10)
    ]

    empty = client.get("/api/overview", params={"domain": "Nonexistent"}).json()
    assert empty["has_data"] is False
    assert empty["total_assessments"] == 0
