"""predict.py - command-line inference through the full production pipeline.

  python training/predict.py --file path/to/report.pdf
  python training/predict.py --file report.docx --json out.json
  python training/predict.py --text "The prototype was demonstrated ..." \
      --technology-name "My Device"

Uses exactly the same ingestion -> evidence -> hybrid prediction -> gap
analysis code as the REST API (no separate inference path).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.assessment_service import run_assessment  # noqa: E402
from app.services.ingestion import (  # noqa: E402
    DocumentValidationError,
    ExtractedDocument,
    PageUnit,
    extract_document,
)
from app.services.report import pdf_report  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="TRL INSIGHT CLI predictor")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--file", type=str, help="Path to a PDF/DOCX/TXT document")
    source.add_argument("--text", type=str, help="Raw document text")
    parser.add_argument("--technology-name", type=str, default="")
    parser.add_argument("--domain", type=str, default="")
    parser.add_argument("--organization", type=str, default="")
    parser.add_argument("--description", type=str, default="")
    parser.add_argument("--json", type=str, default=None,
                        help="Write the full JSON report to this path")
    parser.add_argument("--pdf", type=str, default=None,
                        help="Write the PDF report to this path")
    parser.add_argument("--evidence", type=int, default=8,
                        help="Number of evidence excerpts to print")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    metadata = {
        "technology_name": args.technology_name,
        "domain": args.domain,
        "organization": args.organization,
        "description": args.description,
    }

    if args.file:
        path = Path(args.file)
        try:
            extracted = extract_document(path, path.name)
        except DocumentValidationError as exc:
            print(f"[error] {exc}")
            return 1
        metadata["filename"] = path.name
        if not extracted.units:
            print("[error] No text could be extracted from the document.")
            return 1
    else:
        text = args.text or ""
        extracted = ExtractedDocument(
            filename="command_line_input.txt",
            file_type="txt",
            units=[PageUnit(page=1, locator="page 1", text=text, chars=len(text))],
            method="raw-text",
        )
        metadata["filename"] = "command_line_input.txt"

    result = run_assessment(extracted, metadata=metadata)

    prediction = result["prediction"]
    print("=" * 72)
    print(f"Technology : {result['metadata']['technology_name'] or '(unnamed)'}")
    print(f"Document   : {result['metadata']['filename']}")
    print(f"Predicted  : TRL {prediction['predicted_trl']} - {prediction['level_name']}")
    print(f"Confidence : {prediction['confidence']:.0%}"
          f"{'  [LOW CONFIDENCE]' if prediction['low_confidence'] else ''}")
    print(f"Coverage   : {prediction['evidence_coverage']:.0%}   "
          f"mode={prediction['model_mode']}")
    print(f"Method     : {prediction['method']}")
    if prediction.get("rule_level") is not None:
        print(f"Rule level : TRL {prediction['rule_level']}")
    if prediction.get("ml_level") is not None:
        print(f"ML level   : TRL {prediction['ml_level']}")
    if prediction.get("alternatives"):
        alts = ", ".join(f"TRL {a['level']} ({a['probability']:.0%})"
                         for a in prediction["alternatives"])
        print(f"Alternatives: {alts}")
    for warning in prediction.get("warnings", []):
        print(f"  [warn] {warning}")

    print("-" * 72)
    print("Milestones:")
    for milestone in result["milestones"]:
        print(f"  TRL{milestone['trl']} {milestone['status']:11s} {milestone['label']}")

    summary = result["evidence_summary"]
    print("-" * 72)
    print(f"Evidence: {summary['total']} items "
          f"({summary['confirmed']} confirmed, {summary['proposed']} proposed, "
          f"{summary['contradicted']} contradicted, {summary['unclear']} unclear)")
    for item in result["evidence"][: max(0, args.evidence)]:
        page = f"p{item['page_number']}" if item["page_number"] else item["location"]
        print(f"  [{item['status']:11s}] ({page}, rel={item['relevance']:.2f}) "
              f"{item['statement'][:100]}")

    verification = result.get("verification") or {}
    print("-" * 72)
    print(f"Verification: {verification.get('summary', '')}")
    for concern in verification.get("concerns", []):
        print(f"  * {concern}")

    gap = result.get("gap_analysis") or {}
    print("-" * 72)
    print(f"Gap analysis: {gap.get('summary', '')}")
    for rec in gap.get("recommendations", []):
        labels = ", ".join(rec.get("address_labels", []))
        print(f"  [{rec['priority']:6s}] {rec['title']}  (addresses: {labels})")
    print("=" * 72)

    if args.json:
        Path(args.json).write_bytes(
            json.dumps(result, ensure_ascii=False, indent=2, default=str).encode("utf-8")
        )
        print(f"[done] JSON report -> {args.json}")
    if args.pdf:
        Path(args.pdf).write_bytes(pdf_report(result))
        print(f"[done] PDF report  -> {args.pdf}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
