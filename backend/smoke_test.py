"""Quick end-to-end smoke test of the upload -> analyze pipeline (dev tool)."""
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi.testclient import TestClient

from app.main import app

DOC = """Solar-Powered Membrane Distillation Unit: Field Demonstration Report

1. Introduction and Scientific Principles

The present device operates on the principle of membrane distillation, a
thermally driven separation process in which only water vapour passes
through a hydrophobic microporous membrane. The underlying mechanism is
the vapour pressure difference created across the membrane by a
temperature gradient. A theoretical analysis of the heat and mass transfer
was performed using the governing equations of porous media flow.

2. Technology Concept and Feasibility

We propose a compact solar-driven membrane distillation module intended
for off-grid brackish water treatment. The technology concept integrates
flat-sheet membrane cassettes with a vacuum-assisted condenser. A
feasibility study was carried out to identify the target application and
the design architecture of the unit.

3. Experimental Proof of Concept

A proof-of-concept bench rig was constructed in the laboratory. The
experiment was performed with synthetic saline water at 35 g/L salinity.
Results show a permeate flux of 18.4 L/m2h at a feed temperature of 70 C.
The measured values agreed with the theoretical prediction within 6 percent.

4. Laboratory Validation

Laboratory tests were conducted on the integrated prototype using a
controlled test bench. The component set was characterized for 500 hours
of continuous operation. The membrane module was tested under controlled
conditions and the salt rejection was measured at 99.7 percent.

5. Relevant Environment Testing

The integrated subsystem was then validated in a relevant environment
using a pilot-scale rig installed on the roof of the pilot plant, where
solar irradiance and ambient temperature varied realistically. Simulated
environment conditions were applied during the night cycles. The system
achieved an average flux of 15.1 L/m2h under representative conditions.

6. Prototype Demonstration

A full prototype demonstration was carried out at the semi-field test
site. The integrated prototype was demonstrated in the relevant
environment over a period of three weeks, and all major issues were
logged and corrected.

7. Field Trial in the Operational Environment

A field trial was organised at the customer site in a remote village.
The system prototype was demonstrated in the operational environment
during a 60-day on-site trial. Data from the field trial show stable
operation with only two membrane cleaning events. User feedback was
collected from the village water committee.

8. Future Work

In future work, the system will be deployed for a full commercial
deployment, and qualification testing will be performed to certify the
unit. A certification test campaign is planned for next year.

9. Conclusion

The device has not yet been certified, so it is not yet qualified for
series production. Nevertheless, laboratory and field evidence
demonstrates the readiness of the prototype up to operational
demonstration.
"""


def main() -> None:
    client = TestClient(app)
    files = {"file": ("field_report.txt", io.BytesIO(DOC.encode("utf-8")), "text/plain")}
    response = client.post("/api/documents/upload", files=files)
    print("UPLOAD", response.status_code)
    if response.status_code != 200:
        print(response.json())
        return
    uploaded = response.json()
    print("  doc id:", uploaded["id"], "chars:", uploaded["char_count"])

    payload = {
        "document_id": uploaded["id"],
        "technology_name": "Solar Membrane Distillation Unit",
        "domain": "Water Treatment",
        "organization": "Test Lab",
        "description": "Solar-driven membrane distillation for off-grid water treatment.",
    }
    response = client.post("/api/assessments/analyze", json=payload)
    print("ANALYZE", response.status_code)
    if response.status_code != 200:
        print(response.text[:3000])
        return
    result = response.json()
    pred = result["prediction"]
    print(f"  predicted TRL {pred['predicted_trl']} ({pred['level_name']})")
    print(f"  confidence={pred['confidence']} low={pred['low_confidence']} "
          f"coverage={pred['evidence_coverage']} mode={pred['model_mode']}")
    print(f"  rule_level={pred['rule_level']} ml_level={pred['ml_level']}")
    print(f"  alternatives={pred['alternatives']}")
    print(f"  evidence: {result['evidence_summary']}")
    print("  milestones:")
    for ms in result["milestones"]:
        print(f"    TRL{ms['trl']} {ms['status']:11s} {ms['label'][:45]:45s} {ms['summary'][:70]}")
    print("  warnings:")
    for w in pred["warnings"]:
        print("    -", w)
    print("  verification:", result["verification"]["summary"])
    for c in result["verification"]["concerns"]:
        print("    *", c)
    print("  gap:", result["gap_analysis"]["summary"])
    for rec in result["gap_analysis"]["recommendations"]:
        print(f"    [{rec['priority']}] {rec['title']} -> {rec['address_labels']} ({rec['address_statuses']})")
    print("  sample evidence:")
    for item in result["evidence"][:8]:
        print(f"    {item['status']:12s} p{item['page_number']} {item['relevance']:.2f} "
              f"{item['statement'][:90]}")

    aid = result["id"]
    r = client.get(f"/api/assessments/{aid}/json")
    print("JSON report:", r.status_code, len(r.content), "bytes")
    r = client.get(f"/api/assessments/{aid}/report")
    print("PDF report:", r.status_code, len(r.content), "bytes",
          r.headers.get("content-type"))
    out = Path(__file__).parent / "_smoke_report.pdf"
    if r.status_code == 200:
        out.write_bytes(r.content)
        print("  saved:", out)
    r = client.get("/api/overview")
    ov = r.json()
    print("overview:", ov["total_assessments"], "avg TRL", ov["average_trl"],
          "dist", [d["count"] for d in ov["distribution"]])
    r = client.delete(f"/api/assessments/{aid}")
    print("delete:", r.status_code, r.json())


if __name__ == "__main__":
    main()
