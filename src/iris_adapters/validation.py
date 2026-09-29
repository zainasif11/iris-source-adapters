"""Shared QA rules; adapters cannot bypass these checks."""

import json
import re
from datetime import date, datetime

from .contract import CanonicalRecord
from .country_codes import COUNTRY_CODES

_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
_REGION = re.compile(r"[A-Z0-9][A-Z0-9-]{0,15}\Z")


class ValidationError(ValueError):
    pass


def validate(record: CanonicalRecord) -> None:
    if record.country_code not in COUNTRY_CODES:
        raise ValidationError(f"invalid or missing country_code: {record.country_code!r}")
    for name in ("record_id", "source_id"):
        if not isinstance(getattr(record, name), str) or not _IDENTIFIER.fullmatch(getattr(record, name)):
            raise ValidationError(f"{name} must be a nonempty scoped identifier")
    if record.region_code is not None and (
        not isinstance(record.region_code, str) or not _REGION.fullmatch(record.region_code)
    ):
        raise ValidationError("region_code must be null or an uppercase region identifier")
    try:
        if date.fromisoformat(record.source_date).isoformat() != record.source_date:
            raise ValueError
        if datetime.fromisoformat(record.fetched_at.replace("Z", "+00:00")).utcoffset() is None:
            raise ValueError
    except (TypeError, ValueError) as exc:
        raise ValidationError("source_date or fetched_at is invalid") from exc
    if record.geom is not None and record.crs != "EPSG:4326":
        raise ValidationError("geospatial records require explicit EPSG:4326 CRS")
    if record.geom is None and record.crs is not None:
        raise ValidationError("tabular records must have null CRS")
    if record.completeness not in {"complete", "partial"}:
        raise ValidationError("completeness must be complete or partial")
    if not isinstance(record.attributes, dict) or not all(isinstance(key, str) for key in record.attributes):
        raise ValidationError("attributes must be a JSON object with string keys")
    if not isinstance(record.units, dict) or not all(
        isinstance(key, str) and isinstance(unit, str) and unit.strip()
        for key, unit in record.units.items()
    ):
        raise ValidationError("units must map attribute names to nonempty unit strings")
    if set(record.units) - set(record.attributes):
        raise ValidationError("units references an absent attribute")
    missing_units = {
        key for key, value in record.attributes.items()
        if isinstance(value, (int, float)) and not isinstance(value, bool) and key not in record.units
    }
    if missing_units:
        raise ValidationError(f"numeric attributes need explicit units: {sorted(missing_units)}")
    if not isinstance(record.uncertainty, dict):
        raise ValidationError("uncertainty must be an explicit JSON object")
    try:
        json.dumps(record.to_dict(), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValidationError("canonical record contains non-JSON or non-finite values") from exc
