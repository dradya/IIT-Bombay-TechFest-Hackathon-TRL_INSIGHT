"""Configurable dataset adapter (CSV / TSV / JSON / JSONL).

Reads ``config/dataset_adapter.yaml`` so an official competition dataset
can be integrated by changing column names only - never by rewriting
application code. Produces validated records ``{id, text, trl, ...}``
plus a validation report describing every dropped row.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from training.common import CONFIG_DIR, load_yaml

DEFAULT_CONFIG = CONFIG_DIR / "dataset_adapter.yaml"


@dataclass
class DatasetConfig:
    text_column: str = "text"
    label_column: str = "trl"
    id_column: str = "id"
    domain_column: str = "domain"
    organization_column: str = "organization"
    technology_column: str = "technology_name"
    label_patterns: list[str] = field(
        default_factory=lambda: [
            r"^\s*(?:trl)?[\s_#-]*([1-9])\s*(?:/\s*9|of\s*9)?\s*$",
            r"^\s*trl[\s_-]*([1-9])\b",
            r"\b([1-9])\s*/\s*9\b",
            r"\b([1-9])\b",
        ]
    )
    allowed_labels: list[int] = field(default_factory=lambda: list(range(1, 10)))
    encoding: str = "utf-8"
    encoding_fallbacks: list[str] = field(
        default_factory=lambda: ["utf-8-sig", "cp1252", "latin-1"]
    )
    min_text_chars: int = 120
    max_text_chars: int = 200000
    deduplicate: bool = True
    drop_invalid_labels: bool = True
    filters: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_yaml(cls, path: str | Path | None = None) -> "DatasetConfig":
        raw = load_yaml(Path(path) if path else DEFAULT_CONFIG)
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        kwargs = {k: v for k, v in raw.items() if k in known and k != "version"}
        return cls(**kwargs)


@dataclass
class ValidationReport:
    total_rows: int = 0
    kept_rows: int = 0
    dropped_empty_text: int = 0
    dropped_too_short: int = 0
    dropped_invalid_label: int = 0
    dropped_duplicate: int = 0
    dropped_filtered: int = 0
    truncated: int = 0
    label_counts: dict[str, int] = field(default_factory=dict)
    issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_rows": self.total_rows,
            "kept_rows": self.kept_rows,
            "dropped_empty_text": self.dropped_empty_text,
            "dropped_too_short": self.dropped_too_short,
            "dropped_invalid_label": self.dropped_invalid_label,
            "dropped_duplicate": self.dropped_duplicate,
            "dropped_filtered": self.dropped_filtered,
            "truncated": self.truncated,
            "label_counts": self.label_counts,
            "issues": self.issues,
        }


def _read_frame(path: Path, config: DatasetConfig) -> pd.DataFrame:
    suffix = path.suffix.lower()
    encodings = [config.encoding, *config.encoding_fallbacks]
    last_error: Exception | None = None
    for encoding in dict.fromkeys(encodings):
        try:
            if suffix in {".csv", ".tsv"}:
                sep = "\t" if suffix == ".tsv" else ","
                return pd.read_csv(path, sep=sep, encoding=encoding)
            if suffix == ".json":
                return pd.read_json(path, encoding=encoding)
            if suffix in {".jsonl", ".ndjson"}:
                records = [
                    json.loads(line)
                    for line in path.read_text(encoding=encoding).splitlines()
                    if line.strip()
                ]
                return pd.DataFrame(records)
            if suffix in {".parquet"}:
                try:
                    return pd.read_parquet(path)
                except ImportError as exc:
                    raise ValueError(
                        "Reading Parquet requires an extra engine "
                        "(pip install pyarrow). Export the dataset as CSV/JSON "
                        "instead, or install the dependency."
                    ) from exc
        except (UnicodeDecodeError, ValueError) as exc:
            last_error = exc
            continue
    raise ValueError(
        f"Could not read dataset {path.name} with encodings {encodings}: {last_error}"
    )


def parse_label(value: Any, config: DatasetConfig) -> int | None:
    """Parse a TRL label in any of the configured formats."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        label = int(value)
        return label if label in config.allowed_labels else None
    text = str(value).strip()
    if not text:
        return None
    for pattern in config.label_patterns:
        try:
            match = re.search(pattern, text, re.IGNORECASE)
        except re.error:
            continue
        if match:
            try:
                label = int(match.group(1))
            except (IndexError, ValueError):
                continue
            if label in config.allowed_labels:
                return label
    return None


def load_dataset(
    source: str | Path, config: DatasetConfig | None = None
) -> tuple[pd.DataFrame, ValidationReport]:
    """Load + validate a dataset into records ``{id, text, trl, ...}``."""
    config = config or DatasetConfig()
    path = Path(source)
    if not path.is_file():
        raise FileNotFoundError(f"Dataset not found: {path}")

    frame = _read_frame(path, config)
    report = ValidationReport(total_rows=len(frame))

    if config.text_column not in frame.columns:
        raise ValueError(
            f"Text column '{config.text_column}' not found. Available columns: "
            f"{list(frame.columns)}. Update config/dataset_adapter.yaml "
            "(text_column) to match your dataset."
        )
    if config.label_column not in frame.columns:
        raise ValueError(
            f"Label column '{config.label_column}' not found. Available columns: "
            f"{list(frame.columns)}. Update config/dataset_adapter.yaml "
            "(label_column) to match your dataset."
        )

    # Optional configured filters
    for column, expected in (config.filters or {}).items():
        if column in frame.columns:
            frame = frame[frame[column] == expected]
        else:
            report.issues.append(f"Filter column '{column}' missing; filter skipped.")
    report.total_rows = len(frame)

    records: list[dict[str, Any]] = []
    seen_text: set[str] = set()

    for index, row in frame.iterrows():
        raw_text = row[config.text_column]
        if raw_text is None or (isinstance(raw_text, float) and pd.isna(raw_text)):
            report.dropped_empty_text += 1
            continue
        text = str(raw_text).strip()
        if not text:
            report.dropped_empty_text += 1
            continue
        if len(text) > config.max_text_chars:
            text = text[: config.max_text_chars]
            report.truncated += 1
        if len(text) < config.min_text_chars:
            report.dropped_too_short += 1
            continue

        label = parse_label(row[config.label_column], config)
        if label is None:
            if config.drop_invalid_labels:
                report.dropped_invalid_label += 1
                continue

        if config.deduplicate:
            key = re.sub(r"\s+", " ", text.lower())
            if key in seen_text:
                report.dropped_duplicate += 1
                continue
            seen_text.add(key)

        record: dict[str, Any] = {
            "id": str(row[config.id_column]) if config.id_column in frame.columns
            else f"row_{index}",
            "text": text,
            "trl": label,
            "source": path.name,
        }
        for extra in (
            config.domain_column,
            config.organization_column,
            config.technology_column,
        ):
            if extra in frame.columns and not pd.isna(row[extra]):
                record[extra] = str(row[extra])
        records.append(record)

    report.kept_rows = len(records)
    counts: dict[str, int] = {}
    for record in records:
        key = str(record["trl"])
        counts[key] = counts.get(key, 0) + 1
    report.label_counts = dict(sorted(counts.items(), key=lambda kv: int(kv[0])))

    if report.kept_rows == 0:
        report.issues.append("No valid rows survived validation.")
    if len(report.label_counts) < 2:
        report.issues.append(
            "Fewer than two distinct labels present - training requires at "
            "least two TRL classes."
        )

    return pd.DataFrame(records), report
