"""Adapter for the deterministic source-native JSONL fixture."""

import json
from pathlib import Path
from typing import Any, Iterable

from ..contract import SourceAdapter, SourceMetadata, SourceRecord


class JsonlFixtureAdapter(SourceAdapter):
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def extract(self) -> Iterable[dict[str, Any]]:
        with self.path.open(encoding="utf-8") as source:
            for line_number, line in enumerate(source, start=1):
                if line.strip():
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError as exc:
                        raise ValueError(f"invalid JSON on fixture line {line_number}") from exc
                    if not isinstance(row, dict):
                        raise ValueError(f"fixture line {line_number} must be an object")
                    yield row

    def map_record(self, raw: dict[str, Any]) -> SourceRecord:
        metadata = SourceMetadata(
            source_id=raw["source_id"],
            source_date=raw["source_date"],
            fetched_at=raw["fetched_at"],
            country_code=raw["country_code"],
            region_code=raw.get("region_code"),
            crs=raw.get("crs"),
            completeness=raw["completeness"],
            units=raw["units"],
            uncertainty=raw["uncertainty"],
        )
        return SourceRecord(
            record_id=raw["record_id"],
            metadata=metadata,
            attributes=raw["attributes"],
            geometry=raw.get("geometry"),
        )
