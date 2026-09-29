"""A second independent adapter showing the documented extension point."""

import csv
from pathlib import Path
from typing import Any, Iterable

from ..contract import SourceAdapter, SourceMetadata, SourceRecord


class CsvFixtureAdapter(SourceAdapter):
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def extract(self) -> Iterable[dict[str, str]]:
        with self.path.open(newline="", encoding="utf-8") as source:
            yield from csv.DictReader(source)

    def map_record(self, raw: dict[str, str]) -> SourceRecord:
        has_geometry = bool(raw["lon"] and raw["lat"])
        geometry: dict[str, Any] | None = None
        if has_geometry:
            geometry = {"type": "Point", "coordinates": [float(raw["lon"]), float(raw["lat"])]}
        metadata = SourceMetadata(
            source_id=raw["source_id"],
            source_date=raw["source_date"],
            fetched_at=raw["fetched_at"],
            country_code=raw["country_code"],
            region_code=raw["region_code"] or None,
            crs=raw["crs"] or None,
            completeness=raw["completeness"],
            units={"area_m2": "m2"},
            uncertainty={"position_m": float(raw["position_m"])} if has_geometry else {},
        )
        return SourceRecord(
            record_id=raw["record_id"],
            metadata=metadata,
            attributes={"name": raw["name"], "area_m2": float(raw["area_m2"])},
            geometry=geometry,
        )
