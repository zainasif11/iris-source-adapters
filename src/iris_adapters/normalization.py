"""Source-independent conversion into the canonical record shape."""

from collections.abc import Mapping
from datetime import date, datetime, timezone

from .contract import CanonicalRecord, SourceRecord
from .geometry import normalize_geometry


def _date_string(value: date | str) -> str:
    if isinstance(value, datetime):
        raise ValueError("source_date must be a date, not a datetime")
    if isinstance(value, date):
        return value.isoformat()
    if not isinstance(value, str):
        raise ValueError("source_date must be an ISO date")
    parsed = date.fromisoformat(value)
    if parsed.isoformat() != value:
        raise ValueError("source_date must use YYYY-MM-DD")
    return value


def _timestamp_string(value: datetime | str) -> str:
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("fetched_at must have a timezone")
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def normalize(record: SourceRecord) -> CanonicalRecord:
    meta = record.metadata
    for name, value in (
        ("attributes", record.attributes),
        ("units", meta.units),
        ("uncertainty", meta.uncertainty),
    ):
        if not isinstance(value, Mapping):
            raise ValueError(f"{name} must be an object")
    geom = normalize_geometry(record.geometry)
    return CanonicalRecord(
        record_id=record.record_id,
        country_code=meta.country_code,
        region_code=meta.region_code,
        source_id=meta.source_id,
        source_date=_date_string(meta.source_date),
        fetched_at=_timestamp_string(meta.fetched_at),
        attributes=dict(record.attributes),
        geom=geom,
        crs=meta.crs,
        completeness=meta.completeness,
        units=dict(meta.units),
        uncertainty=dict(meta.uncertainty),
    )
