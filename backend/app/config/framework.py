"""TRL framework loader.

Reads ``app/config/trl_framework.yaml`` (definitions, milestones, evidence
indicators, progression criteria, assessment rules, recommendation
templates) and exposes it through a small typed accessor. The framework is
data-driven so rules can be adapted without code changes.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

FRAMEWORK_PATH = Path(__file__).resolve().parents[1] / "config" / "trl_framework.yaml"


class Framework:
    """Read-only accessor over the TRL framework configuration."""

    def __init__(self, data: dict[str, Any]):
        self._data = data
        self._levels: dict[int, dict[str, Any]] = {
            int(item["level"]): item for item in data.get("levels", [])
        }
        self._milestones: dict[str, dict[str, Any]] = {
            item["id"]: item for item in data.get("milestones", [])
        }
        self._categories: dict[str, dict[str, Any]] = {
            item["id"]: item for item in data.get("evidence_categories", [])
        }
        self._recommendations: list[dict[str, Any]] = list(
            data.get("recommendation_templates", [])
        )

    # -- raw access -----------------------------------------------------
    @property
    def raw(self) -> dict[str, Any]:
        return self._data

    @property
    def version(self) -> str:
        return str(self._data.get("version", "0"))

    @property
    def meta(self) -> dict[str, Any]:
        return dict(self._data.get("meta", {}))

    @property
    def rules(self) -> dict[str, Any]:
        return dict(self._data.get("assessment_rules", {}))

    @property
    def text_processing(self) -> dict[str, Any]:
        return dict(self._data.get("text_processing", {}))

    @property
    def status_patterns(self) -> dict[str, list[str]]:
        raw = self._data.get("evidence_status_patterns", {}) or {}
        return {
            key: [str(p) for p in (raw.get(key) or [])]
            for key in ("contradicted", "proposed", "completion", "results")
        }

    @property
    def evidence_statuses(self) -> list[str]:
        return list(self._data.get("evidence_statuses", []))

    # -- entities -------------------------------------------------------
    @property
    def levels(self) -> list[dict[str, Any]]:
        return [self._levels[i] for i in sorted(self._levels)]

    @property
    def milestones(self) -> list[dict[str, Any]]:
        return [self._milestones[m["id"]] for m in self._data.get("milestones", [])]

    @property
    def categories(self) -> list[dict[str, Any]]:
        return list(self._categories.values())

    @property
    def recommendations(self) -> list[dict[str, Any]]:
        return self._recommendations

    @property
    def missing_milestone_actions(self) -> dict[str, str]:
        return dict(self._data.get("missing_milestone_actions", {}))

    def level(self, value: int) -> dict[str, Any]:
        return self._levels.get(int(value), {})

    def milestone(self, milestone_id: str) -> dict[str, Any]:
        return self._milestones.get(milestone_id, {})

    def category(self, category_id: str) -> dict[str, Any]:
        return self._categories.get(category_id, {})

    def milestone_ids(self) -> list[str]:
        return [m["id"] for m in self.milestones]

    def milestones_up_to(self, trl: int) -> list[dict[str, Any]]:
        """Milestones whose defining level is <= ``trl`` (the chain)."""
        return [m for m in self.milestones if int(m.get("trl", 0)) <= int(trl)]

    def rule(self, key: str, default: Any = None) -> Any:
        return self.rules.get(key, default)

    def recommendations_for(self, target_trl: int) -> list[dict[str, Any]]:
        return [r for r in self._recommendations if int(r.get("target_trl", 0)) == int(target_trl)]

    def categories_for_milestone(self, milestone_id: str) -> list[dict[str, Any]]:
        out = []
        for cat in self.categories:
            ids = [cat.get("primary_milestone"), *cat.get("secondary_milestones", [])]
            if milestone_id in ids:
                out.append(cat)
        return out


@lru_cache(maxsize=1)
def get_framework() -> Framework:
    if not FRAMEWORK_PATH.is_file():  # pragma: no cover - defensive
        raise FileNotFoundError(f"TRL framework configuration not found: {FRAMEWORK_PATH}")
    with FRAMEWORK_PATH.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):  # pragma: no cover - defensive
        raise ValueError("TRL framework configuration must be a mapping")
    return Framework(data)
