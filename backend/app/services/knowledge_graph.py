"""Evidence knowledge graph.

Builds a real graph from the assessment's own objects: the technology, its
documents, the nine milestones, the evidence categories that actually appear,
the extracted evidence excerpts and detected contradictions. Nothing is
invented; the node/edge caps only limit rendering size and set ``truncated``.
"""
from __future__ import annotations

from typing import Any

from app.config.framework import Framework
from app.services.evidence import STATUS_CONFIRMED, EvidenceRecord

MAX_EVIDENCE_NODES = 160
MAX_NODES = 260


def _truncate(text: str, limit: int = 110) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def build_knowledge_graph(
    technology_name: str,
    documents: list[dict[str, Any]],
    evidence: list[EvidenceRecord],
    framework: Framework,
    contradictions: dict[str, Any] | None = None,
) -> dict[str, Any]:
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    used_ids: set[str] = set()

    def add_node(node: dict[str, Any]) -> bool:
        if node["id"] in used_ids or len(nodes) >= MAX_NODES:
            return False
        used_ids.add(node["id"])
        nodes.append(node)
        return True

    def add_edge(
        source: str, target: str, kind: str, label: str = ""
    ) -> None:
        if source not in used_ids or target not in used_ids:
            return
        edge_id = f"edge_{len(edges) + 1:04d}"
        edges.append(
            {
                "id": edge_id,
                "source": source,
                "target": target,
                "type": kind,
                "label": label,
            }
        )

    add_node(
        {
            "id": "technology",
            "type": "technology",
            "label": technology_name or "Assessed technology",
            "status": None,
            "metadata": {"kind": "root"},
        }
    )

    for index, document in enumerate(documents):
        document_id = str(document.get("document_id") or f"document_{index}")
        add_node(
            {
                "id": f"document::{document_id}",
                "type": "document",
                "label": _truncate(str(document.get("filename") or document_id), 60),
                "status": None,
                "document_id": document.get("document_id"),
                "weight": 1.0,
                "metadata": {
                    "page_count": document.get("page_count", 0),
                    "char_count": document.get("char_count", 0),
                    "uploaded_at": document.get("uploaded_at"),
                    "evidence_count": document.get("evidence_count", 0),
                },
            }
        )
        add_edge("technology", f"document::{document_id}", "contains", "has document")

    for milestone in framework.milestones:
        add_node(
            {
                "id": f"milestone::{milestone['id']}",
                "type": "milestone",
                "label": f"TRL {milestone.get('trl')}: {milestone.get('label', '')}",
                "status": None,
                "weight": 1.0,
                "metadata": {"trl": milestone.get("trl")},
            }
        )
        add_edge(
            "technology",
            f"milestone::{milestone['id']}",
            "relates_to",
            "readiness chain",
        )

    category_ids = sorted({item.category for item in evidence if item.category})
    for category_id in category_ids:
        category = framework.category(category_id)
        add_node(
            {
                "id": f"category::{category_id}",
                "type": "category",
                "label": _truncate(str(category.get("label", category_id)), 70),
                "status": None,
                "weight": 1.0,
                "metadata": {"category": category_id},
            }
        )
        for milestone in framework.milestones:
            if category_id in [
                c["id"] for c in framework.categories_for_milestone(milestone["id"])
            ]:
                add_edge(
                    f"category::{category_id}",
                    f"milestone::{milestone['id']}",
                    "relates_to",
                    "evidence category",
                )
                break

    truncated = False
    evidence_items = list(evidence)
    if len(evidence_items) > MAX_EVIDENCE_NODES:
        truncated = True
        evidence_items = evidence_items[:MAX_EVIDENCE_NODES]

    added_evidence: set[str] = set()
    for item in evidence_items:
        node_id = f"evidence::{item.id}"
        node = {
            "id": node_id,
            "type": "evidence",
            "label": _truncate(item.statement),
            "status": item.status,
            "document_id": item.document_id,
            "page_number": item.page_number,
            "weight": round(float(item.relevance), 3),
            "metadata": {
                "location": item.location,
                "category": item.category,
                "milestone": item.milestone,
                "evidence_type": item.evidence_type,
                "duplicate_of": item.duplicate_of,
                "outdated": item.outdated,
                "semantic_similarity": item.semantic_similarity,
            },
        }
        if not add_node(node):
            truncated = True
            continue
        added_evidence.add(item.id)
        if item.document_id:
            add_edge(
                f"document::{item.document_id}", node_id, "derived_from", "reports"
            )
        else:
            add_edge("technology", node_id, "derived_from", "self-reported")
        if item.milestone:
            add_edge(
                node_id,
                f"milestone::{item.milestone}",
                "supports" if item.status == STATUS_CONFIRMED else "relates_to",
                item.status,
            )
        if item.category:
            add_edge(
                node_id,
                f"category::{item.category}",
                "relates_to",
                "category",
            )

    for item in evidence_items:
        if item.duplicate_of and item.duplicate_of in added_evidence:
            add_edge(
                f"evidence::{item.id}",
                f"evidence::{item.duplicate_of}",
                "duplicate_of",
                "same claim",
            )

    contradiction_items = list((contradictions or {}).get("items") or [])
    for contradiction in contradiction_items:
        node_id = f"contradiction::{contradiction.get('id')}"
        add_node(
            {
                "id": node_id,
                "type": "contradiction",
                "label": _truncate(
                    str(contradiction.get("explanation", "Contradiction")), 100
                ),
                "status": "contradicted",
                "weight": 1.0,
                "metadata": {
                    "severity": contradiction.get("severity"),
                    "milestone": contradiction.get("milestone"),
                    "type": contradiction.get("type"),
                },
            }
        )
        for source in contradiction.get("sources") or []:
            evidence_id = str(source.get("evidence_id", ""))
            if evidence_id in added_evidence:
                add_edge(
                    f"evidence::{evidence_id}",
                    node_id,
                    "contradicts",
                    "conflicting source",
                )
        milestone_id = contradiction.get("milestone")
        if milestone_id:
            add_edge(
                node_id,
                f"milestone::{milestone_id}",
                "contradicts",
                "unresolved conflict",
            )

    if truncated:
        note = (
            "Evidence nodes are capped for rendering; the assessment itself "
            "contains all extracted excerpts. Duplicate claims are linked with "
            "duplicate_of edges and contradictions connect their real sources."
        )
    else:
        note = (
            "Graph built from the actual documents, milestones and evidence "
            "excerpts. Duplicate claims are linked, and contradiction nodes "
            "connect the exact sources that conflict."
        )

    return {
        "nodes": nodes,
        "edges": edges,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "truncated": truncated,
        "note": note,
    }


def count_graph(nodes: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for node in nodes:
        counts[node["type"]] = counts.get(node["type"], 0) + 1
    return counts


__all__ = ["build_knowledge_graph", "count_graph"]
