"""Normalize explicit EPSG:4326 GeoJSON geometries without guessing a CRS."""

import json
import math
from collections.abc import Mapping
from typing import Any


class GeometryError(ValueError):
    pass


def _position(value: Any) -> list[int | float]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise GeometryError("coordinates must be two-dimensional [longitude, latitude]")
    lon, lat = value
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in value):
        raise GeometryError("coordinates must be finite numbers")
    if not -180 <= lon <= 180 or not -90 <= lat <= 90:
        raise GeometryError("EPSG:4326 coordinates are outside longitude/latitude bounds")
    return [lon, lat]


def _line(value: Any, minimum: int) -> list[list[int | float]]:
    if not isinstance(value, (list, tuple)) or len(value) < minimum:
        raise GeometryError(f"line or ring needs at least {minimum} positions")
    points = [_position(point) for point in value]
    if len({tuple(point) for point in points}) < 2:
        raise GeometryError("line or ring needs distinct positions")
    return points


def _polygon(value: Any) -> list[list[list[int | float]]]:
    if not isinstance(value, (list, tuple)) or not value:
        raise GeometryError("polygon needs at least one ring")
    rings = [_line(ring, 4) for ring in value]
    for ring in rings:
        if ring[0] != ring[-1] or len({tuple(point) for point in ring[:-1]}) < 3:
            raise GeometryError("polygon rings must be closed with three distinct vertices")
    return rings


def normalize_geometry(value: Mapping[str, Any] | str | None) -> dict[str, Any] | None:
    """Return a strict two-dimensional GeoJSON geometry or None.

    Topological checks beyond ring closure are enforced by PostGIS at DB load.
    """
    if value is None:
        return None
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise GeometryError("geometry is not valid GeoJSON") from exc
    if not isinstance(value, Mapping):
        raise GeometryError("geometry must be a GeoJSON object")
    kind = value.get("type")
    if kind == "GeometryCollection":
        if set(value) != {"type", "geometries"}:
            raise GeometryError("GeometryCollection must contain only type and geometries")
        children = value.get("geometries")
        if not isinstance(children, (list, tuple)) or not children:
            raise GeometryError("GeometryCollection needs nonempty geometries")
        normalized = [normalize_geometry(child) for child in children]
        if any(child is None for child in normalized):
            raise GeometryError("GeometryCollection cannot contain null geometry")
        return {"type": kind, "geometries": normalized}
    if set(value) != {"type", "coordinates"}:
        raise GeometryError("geometry must contain only type and coordinates")
    coordinates = value.get("coordinates")
    if kind == "Point":
        result = _position(coordinates)
    elif kind in ("MultiPoint", "LineString"):
        result = _line(coordinates, 2 if kind == "LineString" else 1)
    elif kind == "MultiLineString":
        if not isinstance(coordinates, (list, tuple)) or not coordinates:
            raise GeometryError("MultiLineString needs lines")
        result = [_line(line, 2) for line in coordinates]
    elif kind == "Polygon":
        result = _polygon(coordinates)
    elif kind == "MultiPolygon":
        if not isinstance(coordinates, (list, tuple)) or not coordinates:
            raise GeometryError("MultiPolygon needs polygons")
        result = [_polygon(polygon) for polygon in coordinates]
    else:
        raise GeometryError(f"unsupported GeoJSON geometry type: {kind!r}")
    return {"type": kind, "coordinates": result}
