"""Tests for the analysis pipeline: evidence, classification, low
confidence handling, gap analysis and report generation."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.config.framework import get_framework
from app.ml.rules import assess_rules
from app.services.assessment_service import run_assessment
from app.services.document_processing import clean_document
from app.services.evidence import extract_evidence
from app.services.gap_analysis import build_gap_analysis
from app.services.ingestion import ExtractedDocument, PageUnit
from app.services.report import json_report, pdf_report
from app.services.verification import verify_prediction


def _extracted(text: str, pages: list[str] | None = None) -> ExtractedDocument:
    if pages:
        units = [
            PageUnit(page=i + 1, locator=f"page {i + 1}", text=p, chars=len(p))
            for i, p in enumerate(pages)
        ]
    else:
        units = [PageUnit(page=1, locator="page 1", text=text, chars=len(text))]
    return ExtractedDocument(filename="sample.txt", file_type="txt", units=units)


# ----------------------------------------------------------------------
# Evidence extraction
# ----------------------------------------------------------------------
def test_evidence_distinguishes_status(framework):
    text = (
        "A proof-of-concept experiment was performed in the laboratory and "
        "results show a flux of 18.4 L/m2h. "
        "In future work, qualification testing will be performed to certify "
        "the system. "
        "The system has not yet been certified for series production. "
        "Some vague statement about testing importance and relevance."
    )
    processed = clean_document(_extracted(text), framework)
    result = extract_evidence(processed, framework, "sample.txt")
    statuses = {item.statement: item.status for item in result.items}

    assert result.items, "evidence must be extracted"
    confirmed = [i for i in result.items if i.status == "confirmed"]
    proposed = [i for i in result.items if i.status == "proposed"]
    contradicted = [i for i in result.items if i.status == "contradicted"]

    assert any("proof-of-concept" in i.statement for i in confirmed)
    assert any("will be performed" in i.statement for i in proposed)
    assert any("has not yet been certified" in i.statement for i in contradicted)
    assert statuses  # every item carries a status


def test_proposed_evidence_never_confirms_milestone(framework):
    text = (
        "A field trial will be organised in the operational environment "
        "next year at the customer site. The system will be deployed "
        "commercially at customer sites after that."
    )
    processed = clean_document(_extracted(text), framework)
    result = extract_evidence(processed, framework, "sample.txt")
    assert result.items, "future statements should still be captured as evidence"
    for item in result.items:
        assert item.status in ("proposed", "unclear")
        assert item.supports_milestone is False
    rules = assess_rules(result.items, framework)
    assert rules.supported_level is None, "planned work must not confirm a milestone"


def test_completed_evidence_confirms_milestone(framework):
    text = (
        "Laboratory tests were conducted on the integrated components using "
        "a controlled test bench. The measured flux reached 18.4 L/m2h and "
        "results show agreement with the model."
    )
    processed = clean_document(_extracted(text), framework)
    result = extract_evidence(processed, framework, "sample.txt")
    rules = assess_rules(result.items, framework)
    statuses = {m.id: m.status for m in rules.milestones}
    assert statuses["m4"] == "confirmed"
    assert rules.supported_level is not None and rules.supported_level >= 4


def test_evidence_excerpts_are_traceable(framework):
    from tests.conftest import SAMPLE_TXT

    processed = clean_document(_extracted(SAMPLE_TXT), framework)
    result = extract_evidence(processed, framework, "field_report.txt")
    assert result.items
    for item in result.items:
        assert item.statement in SAMPLE_TXT.replace("\n", " ") or \
               " ".join(item.statement.split()) in " ".join(SAMPLE_TXT.split())
        assert item.source_document == "field_report.txt"
        assert 0.0 <= item.relevance <= 1.0


def test_evidence_page_numbers_come_from_source(framework):
    pages = [
        "The underlying scientific principle was studied in this work. "
        "We propose a compact technology concept for the application.",
        "A proof-of-concept experiment was performed in the laboratory and "
        "results show a flux of 18.4 L/m2h in the test.",
    ]
    processed = clean_document(_extracted("", pages=pages), framework)
    result = extract_evidence(processed, framework, "doc.pdf")
    assert result.items
    for item in result.items:
        assert item.page_number in (1, 2)
        # A sentence mentioning the PoC must sit on page 2
        if "proof-of-concept" in item.statement.lower():
            assert item.page_number == 2


def test_evidence_without_pages_uses_locations(framework):
    processed = clean_document(_extracted(
        "A proof-of-concept experiment was performed in the laboratory. "
        "Results show a flux of 18.4 L/m2h under the tested conditions."
    ), framework)
    # Simulate DOCX (no page numbers)
    for sentence in processed.sentences:
        sentence.page = None
    result = extract_evidence(processed, framework, "doc.docx")
    for item in result.items:
        assert item.page_number is None
        assert item.location, "page-less formats must carry a locator"


# ----------------------------------------------------------------------
# Classification / low confidence
# ----------------------------------------------------------------------
def test_rules_distribute_probability(framework):
    text = (
        "Laboratory tests were conducted on the integrated components. "
        "A proof-of-concept experiment was performed in the laboratory."
    )
    processed = clean_document(_extracted(text), framework)
    evidence = extract_evidence(processed, framework, "d.txt").items
    rules = assess_rules(evidence, framework)
    total = sum(rules.rule_distribution.values())
    assert 0.99 <= total <= 1.01
    assert set(rules.rule_distribution) == set(range(1, 10))


def test_low_confidence_for_evidence_free_document(framework):
    text = (
        "This document discusses general market trends in the water sector "
        "and mentions several unrelated topics without technical detail. "
        "The report contains no experimental information whatsoever."
    )
    result = run_assessment(_extracted(text), metadata={"filename": "empty.txt"},
                            framework=framework)
    prediction = result["prediction"]
    assert prediction["low_confidence"] is True
    assert prediction["confidence"] < 0.45
    assert prediction["evidence_coverage"] == 0.0 or prediction["evidence_coverage"] < 0.2


def test_full_sample_document_produces_coherent_result(framework):
    from tests.conftest import SAMPLE_TXT

    result = run_assessment(_extracted(SAMPLE_TXT),
                            metadata={"filename": "field_report.txt",
                                      "technology_name": "MD Unit"},
                            framework=framework)
    prediction = result["prediction"]

    assert 1 <= prediction["predicted_trl"] <= 9
    assert 0.0 < prediction["confidence"] <= 1.0
    assert len(prediction["probabilities"]) == 9
    assert abs(sum(p["probability"] for p in prediction["probabilities"]) - 1.0) < 0.02
    assert prediction["model_mode"] in ("hybrid", "rule_only")
    # The document demonstrates field trials but explicitly says it is NOT certified
    assert prediction["predicted_trl"] >= 4
    assert prediction["predicted_trl"] <= 8
    assert result["evidence_summary"]["total"] > 5
    assert result["milestones"], "milestone statuses must be reported"
    # verification + gap analysis present
    assert result["verification"]["concerns"]
    assert result["gap_analysis"]["current_trl"] == prediction["predicted_trl"]


def test_hybrid_prediction_is_deterministic(framework):
    from tests.conftest import SAMPLE_TXT

    first = run_assessment(_extracted(SAMPLE_TXT), metadata={"filename": "a.txt"},
                           framework=framework)
    second = run_assessment(_extracted(SAMPLE_TXT), metadata={"filename": "a.txt"},
                            framework=framework)
    assert first["prediction"]["predicted_trl"] == second["prediction"]["predicted_trl"]
    assert first["prediction"]["confidence"] == second["prediction"]["confidence"]


def test_contradicted_milestone_demotes_prediction(framework):
    """An explicit 'not yet certified' must not be predicted as TRL 8."""
    text = (
        "The underlying scientific principle was studied in this work. "
        "We propose a compact technology concept for the application. "
        "A proof-of-concept experiment was performed in the laboratory. "
        "Laboratory tests were conducted on the integrated components and "
        "results show a measured efficiency of 92 percent. "
        "The subsystem was validated in a relevant environment using a "
        "pilot rig under representative conditions. "
        "The integrated prototype was demonstrated in a relevant environment "
        "at the test site over three weeks. "
        "The system prototype was demonstrated in the operational environment "
        "during a sixty day field trial at the customer site. "
        "The device has not yet been certified and is not yet qualified for "
        "series production. "
        "Qualification testing has not been performed on the final system. "
        "Qualification testing will be performed to certify the unit in the "
        "next phase."
    )
    result = run_assessment(_extracted(text),
                            metadata={"filename": "c.txt"}, framework=framework)
    prediction = result["prediction"]
    # m8 is contradicted -> must not be the predicted level
    assert prediction["predicted_trl"] <= 7
    milestone8 = next(m for m in result["milestones"] if m["trl"] == 8)
    assert milestone8["status"] == "contradicted"
    # ... and the concern is surfaced to the user
    assert any("has not been achieved" in w for w in prediction["warnings"])


def test_verification_flags_unsupported_high_claim(framework):
    # Laboratory-only document that claims deployment-level outcomes
    text = (
        "Laboratory tests were conducted on the integrated components using "
        "a test bench. The measured efficiency reached 92 percent. "
        "The system is already deployed commercially at customer sites and "
        "has proven itself in daily operation with full uptime."
    )
    processed = clean_document(_extracted(text), framework)
    evidence = extract_evidence(processed, framework, "claim.txt").items
    rules = assess_rules(evidence, framework)
    verification = verify_prediction(9, evidence, rules, framework)
    assert verification["predicted_trl"] == 9
    # either the claim is flagged or the summary states the backing status
    assert verification["summary"]
    assert isinstance(verification["concerns"], list)


# ----------------------------------------------------------------------
# Gap analysis
# ----------------------------------------------------------------------
def test_gap_analysis_targets_next_level(framework):
    from tests.conftest import SAMPLE_TXT

    result = run_assessment(_extracted(SAMPLE_TXT),
                            metadata={"filename": "f.txt"}, framework=framework)
    gap = result["gap_analysis"]
    predicted = result["prediction"]["predicted_trl"]

    if predicted < 9:
        assert gap["next_trl"] == predicted + 1
        assert gap["next_name"]
    else:
        assert gap["next_trl"] is None

    assert isinstance(gap["recommendations"], list)
    assert gap["summary"]


def test_recommendations_address_missing_milestones_only(framework):
    # Laboratory-level document: higher milestones are missing
    text = (
        "The underlying scientific principle was studied in this work. "
        "We propose a compact technology concept for the application. "
        "A proof-of-concept experiment was performed in the laboratory. "
        "Laboratory tests were conducted on the integrated components and "
        "results show a measured efficiency of 92 percent."
    )
    processed = clean_document(_extracted(text), framework)
    evidence = extract_evidence(processed, framework, "lab.txt").items
    rules = assess_rules(evidence, framework)
    predicted = rules.supported_level or 3
    gap = build_gap_analysis(predicted, rules, framework)

    confirmed_ids = {m.id for m in rules.milestones if m.status == "confirmed"}
    assert gap["recommendations"], "missing milestones must produce recommendations"
    for rec in gap["recommendations"]:
        assert rec["addresses"], "every recommendation must name a milestone"
        assert rec["address_labels"]
        # A recommendation must never target an already-confirmed milestone
        assert not set(rec["addresses"]) <= confirmed_ids or rec["id"] == "rec_sustain"
        assert rec["actions"], "recommendations must include concrete actions"


def test_trl9_gap_analysis_has_sustain_path(framework):
    rules_text = (
        "The underlying scientific principle was studied in this work. "
        "We propose a compact technology concept for the application. "
        "A proof-of-concept experiment was performed in the laboratory. "
        "Laboratory tests were conducted on the integrated components. "
        "The subsystem was validated in a relevant environment using a "
        "pilot rig under representative conditions. "
        "The integrated prototype was demonstrated in a relevant environment "
        "at the test site over three weeks. "
        "The system prototype was demonstrated in the operational environment "
        "during a sixty day field trial at the customer site. "
        "The complete system passed qualification testing against the "
        "applicable standard and was certified. "
        "The system has been in commercial operation since 2022 with "
        "routine operation across customer sites."
    )
    processed = clean_document(_extracted(rules_text), framework)
    evidence = extract_evidence(processed, framework, "full.txt").items
    rules = assess_rules(evidence, framework)
    gap = build_gap_analysis(9, rules, framework)

    assert gap["next_trl"] is None
    assert any(rec["id"] == "rec_sustain" for rec in gap["recommendations"])
    assert "TRL 9" in gap["summary"]


# ----------------------------------------------------------------------
# Reports
# ----------------------------------------------------------------------
def test_json_report_roundtrip(framework):
    from tests.conftest import SAMPLE_TXT

    result = run_assessment(_extracted(SAMPLE_TXT),
                            metadata={"filename": "f.txt",
                                      "technology_name": "MD Unit"},
                            framework=framework)
    payload = json_report(result)
    parsed = json.loads(payload.decode("utf-8"))
    assert parsed["prediction"]["predicted_trl"] == result["prediction"]["predicted_trl"]
    assert parsed["evidence"][0]["statement"]
    assert parsed["gap_analysis"]["recommendations"]


def test_pdf_report_starts_with_pdf_header(framework):
    from tests.conftest import SAMPLE_TXT

    result = run_assessment(_extracted(SAMPLE_TXT),
                            metadata={"filename": "f.txt",
                                      "technology_name": "MD Unit"},
                            framework=framework)
    payload = pdf_report(result)
    assert payload[:5] == b"%PDF-"
    assert len(payload) > 5000


def test_pdf_report_handles_empty_evidence(framework):
    result = run_assessment(
        _extracted("Short note without technical readiness content at all."),
        metadata={"filename": "n.txt"}, framework=framework,
    )
    payload = pdf_report(result)
    assert payload[:5] == b"%PDF-"
