"""STEP 8 - Report generation (JSON + PDF).

The JSON report is the canonical, machine-readable output. The PDF report
is rendered locally with fpdf2 (no external services) and includes the
technology details, predicted TRL, confidence, evidence table with page
references, missing milestones, recommendations and model metadata.
"""
from __future__ import annotations

import io
import json
import re
import unicodedata
from pathlib import Path
from typing import Any
from urllib.parse import quote

from app.core.logging import get_logger

logger = get_logger("report")

_FONT_CANDIDATES = [
    # Windows
    ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
    ("C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/segoeuib.ttf"),
    # Linux
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
     "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
     "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
    # macOS
    ("/System/Library/Fonts/Supplemental/Arial.ttf",
     "/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
]


def _register_font(pdf: Any) -> tuple[str, bool]:
    """Register a unicode TTF if available. Returns (family, unicode_ok)."""
    for regular, bold in _FONT_CANDIDATES:
        if Path(regular).is_file():
            try:
                pdf.add_font("UI", "", regular)
                pdf.add_font("UI", "I", regular)  # italic falls back to regular
                if Path(bold).is_file():
                    pdf.add_font("UI", "B", bold)
                else:  # pragma: no cover
                    pdf.add_font("UI", "B", regular)
                return "UI", True
            except Exception as exc:  # noqa: BLE001 - font rejected
                logger.debug("Font %s rejected: %s", regular, exc)
                continue
    return "Helvetica", False


def _sanitize(text: str, unicode_ok: bool) -> str:
    if unicode_ok:
        return str(text)
    return str(text).encode("latin-1", errors="replace").decode("latin-1")


# Characters that are illegal in filenames on Windows/macOS/Linux or that
# would break an HTTP header value.
_UNSAFE_FILENAME = re.compile(r'[\x00-\x1f\x7f/\\:*?"<>|]+')
_WHITESPACE = re.compile(r"\s+")


def _clean_label(text: str) -> str:
    """Sanitise a download basename while keeping human-readable Unicode."""
    value = _UNSAFE_FILENAME.sub("-", str(text))
    value = _WHITESPACE.sub(" ", value).strip(" .-_")
    return value[:150] or "assessment"


def content_disposition(filename: str) -> str:
    """Build an RFC 6266/5987 attachment header.

    The header must stay ASCII (Starlette encodes headers as latin-1), so it
    carries a quoted ASCII fallback plus a percent-encoded ``filename*`` with
    the original Unicode name. This keeps downloads working for technology
    names that contain accents, non-Latin scripts, quotes or slashes.
    """
    cleaned = _clean_label(filename)
    ascii_name = (
        unicodedata.normalize("NFKD", cleaned)
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    ascii_name = _clean_label(ascii_name)
    suffix = ""
    if "." in cleaned:
        suffix = "." + cleaned.rsplit(".", 1)[-1].lower()
    if suffix and not ascii_name.lower().endswith(suffix):
        ascii_name = f"{ascii_name}{suffix}"
    quoted = quote(cleaned, safe="")
    return f'attachment; filename="{ascii_name}"; filename*=UTF-8\'\'{quoted}'


def json_report(result: dict[str, Any]) -> bytes:
    """Canonical JSON report (UTF-8)."""
    return json.dumps(result, ensure_ascii=False, indent=2, default=str).encode("utf-8")


def pdf_report(result: dict[str, Any]) -> bytes:
    """Render the assessment as a paginated PDF report."""
    from fpdf import FPDF

    prediction = result.get("prediction", {})
    metadata = result.get("metadata", {})
    evidence = result.get("evidence", [])
    milestones = result.get("milestones", [])
    gap = result.get("gap_analysis") or {}
    verification = result.get("verification") or {}
    model = result.get("model", {})
    processing = result.get("processing", {})
    summary = result.get("evidence_summary", {})

    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_margins(15, 15, 15)
    family, unicode_ok = _register_font(pdf)
    pdf.set_font(family, "", 10)

    def text(value: Any) -> str:
        return _sanitize("" if value is None else str(value), unicode_ok)

    def mc(w: float, h: float, value: str) -> None:
        """multi_cell that returns the cursor to the left margin afterwards."""
        pdf.multi_cell(w, h, value, new_x="LMARGIN", new_y="NEXT")

    # ------------------------------------------------------------------
    # Header
    # ------------------------------------------------------------------
    pdf.add_page()
    pdf.set_font(family, "B", 18)
    pdf.set_text_color(15, 32, 60)
    pdf.cell(0, 10, text("TRL INSIGHT"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font(family, "", 11)
    pdf.set_text_color(60, 76, 96)
    pdf.cell(0, 6, text("Technology Readiness Assessment Report"),
             new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pdf.set_draw_color(20, 140, 140)
    pdf.set_line_width(0.6)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(4)

    def section(title: str) -> None:
        pdf.ln(2)
        pdf.set_font(family, "B", 12)
        pdf.set_text_color(15, 32, 60)
        pdf.cell(0, 8, text(title), new_x="LMARGIN", new_y="NEXT")
        pdf.set_draw_color(20, 140, 140)
        pdf.set_line_width(0.3)
        pdf.line(15, pdf.get_y(), 195, pdf.get_y())
        pdf.ln(2)
        pdf.set_font(family, "", 9.5)
        pdf.set_text_color(30, 30, 30)

    def kv(label: str, value: Any) -> None:
        pdf.set_font(family, "B", 9.5)
        pdf.cell(46, 6, text(label))
        pdf.set_font(family, "", 9.5)
        mc(0, 6, text(value))

    # ------------------------------------------------------------------
    # 1. Technology details
    # ------------------------------------------------------------------
    section("1. Technology details")
    kv("Technology", metadata.get("technology_name") or "(not specified)")
    kv("Domain", metadata.get("domain") or "(not specified)")
    kv("Organisation", metadata.get("organization") or "(not specified)")
    kv("Source document", metadata.get("filename") or "-")
    kv("Assessment ID", result.get("id", "-"))
    kv("Date", result.get("created_at", "-"))
    if metadata.get("description"):
        kv("Description", metadata["description"])
    if processing.get("pages"):
        kv("Pages analysed", processing.get("pages"))
    kv("Extraction", processing.get("extraction_method", "-"))

    # ------------------------------------------------------------------
    # 2. Prediction
    # ------------------------------------------------------------------
    section("2. Prediction")
    level = int(prediction.get("predicted_trl", 0))
    pdf.set_font(family, "B", 26)
    pdf.set_text_color(20, 120, 120)
    pdf.cell(34, 14, text(f"TRL {level}"))
    pdf.set_font(family, "B", 13)
    pdf.set_text_color(15, 32, 60)
    pdf.cell(0, 14, text(prediction.get("level_name", "")),
             new_x="LMARGIN", new_y="NEXT")
    pdf.set_font(family, "", 9.5)
    pdf.set_text_color(30, 30, 30)
    if prediction.get("level_description"):
        mc(0, 5, text(prediction["level_description"]))
        pdf.ln(1)
    confidence = float(prediction.get("confidence", 0) or 0)
    coverage = float(prediction.get("evidence_coverage", 0) or 0)
    kv("Confidence", f"{confidence:.0%}"
       + ("  (LOW CONFIDENCE - treat as uncertain)" if prediction.get("low_confidence") else ""))
    kv("Evidence coverage", f"{coverage:.0%}")
    kv("Prediction mode", prediction.get("model_mode", "-"))
    kv("Method", prediction.get("method", "-"))
    if prediction.get("rule_level") is not None:
        kv("Evidence-confirmed level", f"TRL {prediction['rule_level']}")
    if prediction.get("ml_level") is not None:
        kv("ML classifier level", f"TRL {prediction['ml_level']}")
    alternatives = prediction.get("alternatives") or []
    if alternatives:
        kv(
            "Alternative plausible levels",
            ", ".join(
                f"TRL {a['level']} ({float(a['probability']):.0%})"
                for a in alternatives
            ),
        )

    # TRL scale
    pdf.ln(2)
    pdf.set_font(family, "B", 9.5)
    pdf.cell(0, 6, text("TRL scale (predicted level highlighted)"),
             new_x="LMARGIN", new_y="NEXT")
    box_w = 180 / 9
    x0, y0 = 15, pdf.get_y() + 1
    for i in range(1, 10):
        if i == level:
            pdf.set_fill_color(20, 140, 140)
            pdf.set_text_color(255, 255, 255)
        elif i <= level:
            pdf.set_fill_color(205, 230, 230)
            pdf.set_text_color(30, 60, 60)
        else:
            pdf.set_fill_color(238, 240, 244)
            pdf.set_text_color(120, 130, 140)
        pdf.set_draw_color(255, 255, 255)
        pdf.rect(x0 + (i - 1) * box_w, y0, box_w, 8, style="DF")
        pdf.set_xy(x0 + (i - 1) * box_w, y0 + 1)
        pdf.set_font(family, "B", 9)
        pdf.cell(box_w, 6, str(i), align="C")
    pdf.set_xy(15, y0 + 9)
    pdf.set_text_color(30, 30, 30)
    pdf.set_font(family, "", 8)
    pdf.cell(0, 4, text("1 = basic principles   ...   9 = proven in operation"),
             new_x="LMARGIN", new_y="NEXT")

    warnings = prediction.get("warnings") or []
    if warnings:
        section("3. Warnings and caveats")
        for warning in warnings:
            pdf.set_font(family, "", 9.5)
            mc(0, 5, text(f"- {warning}"))
        pdf.ln(1)

    # ------------------------------------------------------------------
    # Evidence table
    # ------------------------------------------------------------------
    section("Evidence table (traceable excerpts)")
    if evidence:
        from fpdf.fonts import FontFace

        heading_style = FontFace(emphasis="BOLD", color=(255, 255, 255),
                                 fill_color=(15, 32, 60))
        shown = evidence[:60]
        with pdf.table(
            col_widths=(86, 34, 16, 26, 10),
            text_align=("LEFT", "CENTER", "CENTER", "CENTER", "CENTER"),
            headings_style=heading_style,
            line_height=3.6,
            first_row_as_headings=True,
        ) as table:
            header = table.row()
            for label in ("Excerpt", "Category", "Page", "Status", "Rel."):
                header.cell(label)
            for item in shown:
                excerpt = item.get("statement", "")
                if len(excerpt) > 160:
                    excerpt = excerpt[:157] + "..."
                page = item.get("page_number")
                page_text = str(page) if page else (item.get("location", "") or "-")
                row = table.row()
                row.cell(excerpt)
                row.cell((item.get("category_label") or item.get("category", ""))[:34])
                row.cell(str(page_text)[:14])
                row.cell(item.get("status", ""))
                row.cell(f"{float(item.get('relevance', 0)):.2f}")
        if len(evidence) > 60:
            pdf.set_font(family, "I", 8)
            pdf.cell(0, 5, text(f"(showing 60 of {len(evidence)} evidence items)"),
                     new_x="LMARGIN", new_y="NEXT")
    else:
        pdf.set_font(family, "I", 9.5)
        mc(0, 5, text(
            "No evidence items were extracted from this document."
        ))

    # ------------------------------------------------------------------
    # Milestones
    # ------------------------------------------------------------------
    section("Milestone status")
    if milestones:
        from fpdf.fonts import FontFace

        heading_style = FontFace(emphasis="BOLD", color=(255, 255, 255),
                                 fill_color=(15, 32, 60))
        with pdf.table(
            col_widths=(10, 56, 22, 90),
            text_align=("CENTER", "LEFT", "CENTER", "LEFT"),
            headings_style=heading_style,
            line_height=3.8,
            first_row_as_headings=True,
        ) as table:
            header = table.row()
            for label in ("TRL", "Milestone", "Status", "Summary"):
                header.cell(label)
            for ms in milestones:
                ms_summary = ms.get("summary", "")
                if len(ms_summary) > 150:
                    ms_summary = ms_summary[:147] + "..."
                row = table.row()
                row.cell(str(ms.get("trl", "")))
                row.cell(ms.get("label", ""))
                row.cell(ms.get("status", ""))
                row.cell(ms_summary)

    # ------------------------------------------------------------------
    # Gap analysis
    # ------------------------------------------------------------------
    if gap:
        section("Gap analysis and recommendations")
        pdf.set_font(family, "", 9.5)
        mc(0, 5, text(gap.get("summary", "")))
        pdf.ln(1)
        if gap.get("next_trl"):
            kv("Next target", f"TRL {gap['next_trl']} - {gap.get('next_name', '')}")
        missing = gap.get("missing_milestones") or []
        unclear = gap.get("unclear_milestones") or []
        completed = gap.get("completed_milestones") or []
        kv("Completed milestones",
           ", ".join(f"TRL {m['trl']} {m['label']}" for m in completed) or "none")
        kv("Missing milestones",
           ", ".join(f"TRL {m['trl']} {m['label']}" for m in missing) or "none")
        kv("Unclear milestones",
           ", ".join(f"TRL {m['trl']} {m['label']}" for m in unclear) or "none")
        pdf.ln(1)
        for index, rec in enumerate(gap.get("recommendations") or [], start=1):
            if pdf.get_y() > 245:
                pdf.add_page()
            pdf.set_font(family, "B", 10)
            pdf.set_text_color(20, 120, 120)
            addresses = ", ".join(rec.get("address_labels") or [])
            mc(0, 5, text(f"{index}. {rec.get('title', '')}"))
            pdf.set_font(family, "", 8.5)
            pdf.set_text_color(90, 100, 110)
            status_txt = ", ".join(
                f"{label} [{status}]"
                for label, status in zip(
                    rec.get("address_labels") or [],
                    rec.get("address_statuses") or [],
                    strict=False,
                )
            )
            mc(0, 4.5, text(f"Addresses: {status_txt or addresses}"))
            pdf.set_text_color(30, 30, 30)
            pdf.set_font(family, "", 9)
            for action in rec.get("actions", []):
                mc(0, 4.8, text(f"  - {action}"))
            for experiment in rec.get("validation_experiments", []):
                mc(0, 4.8, text(f"  * Validation: {experiment}"))
            pdf.ln(1)

        docs = gap.get("documentation_requirements") or []
        if docs:
            pdf.set_font(family, "B", 9.5)
            pdf.cell(0, 6, text("Documentation requirements"),
                     new_x="LMARGIN", new_y="NEXT")
            pdf.set_font(family, "", 9)
            for doc_req in docs:
                mc(0, 4.8, text(f"  - {doc_req}"))

    # ------------------------------------------------------------------
    # Verification
    # ------------------------------------------------------------------
    if verification:
        section("Evidence verification")
        pdf.set_font(family, "", 9.5)
        mc(0, 5, text(verification.get("summary", "")))
        for concern in verification.get("concerns", []):
            mc(0, 5, text(f"- {concern}"))

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------
    section("Model and assessment metadata")
    kv("Model", f"{model.get('name') or 'none'} v{model.get('version') or '-'}")
    kv("Model mode", model.get("mode", "-"))
    kv("Dataset type", model.get("dataset_type", "-"))
    kv("Trained at", model.get("trained_at") or "n/a")
    kv("Framework version", str(result.get("framework_version", "-")))
    kv("Evidence items", f"{summary.get('total', 0)} "
       f"({summary.get('confirmed', 0)} confirmed, "
       f"{summary.get('proposed', 0)} proposed, "
       f"{summary.get('contradicted', 0)} contradicted, "
       f"{summary.get('unclear', 0)} unclear)")
    kv("Sentences analysed", processing.get("sentences", "-"))
    kv("Processing time", f"{processing.get('duration_ms', 0)} ms")
    pdf.ln(4)
    pdf.set_font(family, "I", 7.5)
    pdf.set_text_color(120, 130, 140)
    mc(0, 4, text(
        "Generated locally by TRL INSIGHT. Evidence excerpts and page "
        "references are taken directly from the source document; proposed "
        "or future-tense statements are never counted as completed "
        "evidence."
    ))

    return bytes(pdf.output())


def write_reports(result: dict[str, Any], out_dir: str | Path) -> dict[str, str]:
    """Write JSON + PDF reports for an assessment; returns file paths."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = str(result.get("id", "assessment"))
    json_path = out_dir / f"{stem}.json"
    pdf_path = out_dir / f"{stem}.pdf"
    json_path.write_bytes(json_report(result))
    try:
        pdf_path.write_bytes(pdf_report(result))
    except Exception as exc:  # noqa: BLE001 - PDF is a secondary output
        logger.error("PDF report generation failed: %s", exc)
        return {"json": str(json_path), "pdf": ""}
    return {"json": str(json_path), "pdf": str(pdf_path)}


def report_bytes(result: dict[str, Any], fmt: str) -> tuple[bytes, str, str]:
    """Return (payload, media_type, filename) for the requested format."""
    stem = _clean_label(str(result.get("id", "assessment")))
    tech = (result.get("metadata", {}) or {}).get("technology_name", "")
    label = _clean_label(f"{tech}_{stem}" if tech else stem)
    if fmt == "pdf":
        return pdf_report(result), "application/pdf", f"{label}.pdf"
    return json_report(result), "application/json", f"{label}.json"
