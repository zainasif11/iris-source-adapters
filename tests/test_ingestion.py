import json
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from iris_adapters import SourceAdapter, SourceMetadata, SourceRecord, ingest
from iris_adapters.adapters.csv_fixture import CsvFixtureAdapter
from iris_adapters.adapters.jsonl_fixture import JsonlFixtureAdapter
from iris_adapters.geometry import GeometryError, normalize_geometry
from iris_adapters.pipeline import IngestionError
from iris_adapters.staging import JsonlStaging


ROOT = Path(__file__).resolve().parents[1]


def _read_lines(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _record(**metadata_changes):
    metadata = SourceMetadata(
        source_id="memory-001",
        source_date="2026-09-01",
        fetched_at="2026-09-02T12:00:00+02:00",
        country_code="DE",
        region_code="NW",
        crs="EPSG:4326",
        completeness="complete",
        units={"area_m2": "m2"},
        uncertainty={"position_m": 5},
    )
    return SourceRecord(
        record_id="record-001",
        metadata=replace(metadata, **metadata_changes),
        attributes={"name": "memory parcel", "area_m2": 1200},
        geometry={"type": "Point", "coordinates": (7.1, 51.2)},
    )


class MemoryAdapter(SourceAdapter):
    """A third adapter defined entirely outside the package's shared core."""

    def __init__(self, rows):
        self.rows = rows

    def extract(self):
        yield from self.rows

    def map_record(self, raw):
        return raw


def test_clean_fixture_import_and_canonical_contract(tmp_path):
    destination = tmp_path / "stage.jsonl"
    count = ingest(JsonlFixtureAdapter(ROOT / "fixtures/source_records.jsonl"), JsonlStaging(destination))
    rows = _read_lines(destination)
    assert count == len(rows) == 24
    assert sum(row["geom"] is not None for row in rows) == 20
    assert all(row["country_code"] == "DE" and row["source_id"] == "fixture-001" for row in rows)
    assert all(row["source_date"] == "2026-09-01" and row["fetched_at"].endswith("Z") for row in rows)
    assert all("geom" in row and "geometry" not in row for row in rows)
    assert rows[0]["geom"] == {"type": "Point", "coordinates": [6.87, 50.84]}
    assert all(row["crs"] == "EPSG:4326" for row in rows if row["geom"] is not None)
    assert all(row["crs"] is None for row in rows if row["geom"] is None)


def test_second_csv_adapter_needs_no_core_changes_and_keys_are_country_scoped(tmp_path):
    destination = tmp_path / "csv-stage.jsonl"
    count = ingest(CsvFixtureAdapter(ROOT / "fixtures/second_source.csv"), JsonlStaging(destination))
    rows = _read_lines(destination)
    assert count == 2
    assert {(row["country_code"], row["source_id"], row["record_id"]) for row in rows} == {
        ("DE", "fixture-002", "shared-001"),
        ("NL", "fixture-002", "shared-001"),
    }


def test_new_adapter_is_only_a_subclass(tmp_path):
    destination = tmp_path / "memory.jsonl"
    assert ingest(MemoryAdapter([_record()]), JsonlStaging(destination)) == 1
    row = _read_lines(destination)[0]
    assert row["fetched_at"] == "2026-09-02T10:00:00Z"
    assert row["geom"]["coordinates"] == [7.1, 51.2]


@pytest.mark.parametrize("bad_code", [None, "", "ZZ", "DEU", "de"])
def test_invalid_country_rejects_entire_batch_and_preserves_prior_stage(tmp_path, bad_code):
    destination = tmp_path / "stage.jsonl"
    destination.write_text("previous batch\n", encoding="utf-8")
    rows = [_record(), _record(country_code=bad_code)]
    rows[1] = replace(rows[1], record_id="record-002")
    with pytest.raises(IngestionError, match="country_code"):
        ingest(MemoryAdapter(rows), JsonlStaging(destination))
    assert destination.read_text(encoding="utf-8") == "previous batch\n"


def test_duplicate_key_within_country_rejected(tmp_path):
    with pytest.raises(IngestionError, match="duplicate"):
        ingest(MemoryAdapter([_record(), _record()]), JsonlStaging(tmp_path / "stage.jsonl"))
    assert not (tmp_path / "stage.jsonl").exists()


def test_bad_source_json_rejects_before_staging(tmp_path):
    source = tmp_path / "bad.jsonl"
    first_line = (ROOT / "fixtures/source_records.jsonl").read_text(encoding="utf-8").splitlines()[0]
    source.write_text(first_line + "\nnot-json\n", encoding="utf-8")
    destination = tmp_path / "stage.jsonl"
    with pytest.raises(IngestionError, match="source row 2: extraction failed"):
        ingest(JsonlFixtureAdapter(source), JsonlStaging(destination))
    assert not destination.exists()


@pytest.mark.parametrize(
    "geometry",
    [
        {"type": "Point", "coordinates": [200, 50]},
        {"type": "Point", "coordinates": [7, float("nan")]},
        {"type": "Point", "coordinates": [7, 50, 1]},
        {"type": "Polygon", "coordinates": [[[7, 50], [8, 50], [8, 51], [7, 51]]]},
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [7, 50]}},
    ],
)
def test_invalid_geometry_rejected(geometry, tmp_path):
    bad = replace(_record(), geometry=geometry)
    with pytest.raises(IngestionError):
        ingest(MemoryAdapter([bad]), JsonlStaging(tmp_path / "stage.jsonl"))


def test_geojson_string_normalizes_to_geojson_object():
    assert normalize_geometry('{"type":"Point","coordinates":[7,51]}') == {
        "type": "Point", "coordinates": [7, 51]
    }
    with pytest.raises(GeometryError):
        normalize_geometry("not json")


@pytest.mark.parametrize(
    "record",
    [
        _record(crs=None),
        _record(crs="EPSG:3857"),
        _record(fetched_at="2026-09-02T10:00:00"),
        _record(source_date="2026-09-99"),
        replace(_record(), attributes={"area_m2": 100}, metadata=replace(_record().metadata, units={})),
    ],
)
def test_missing_crs_timestamp_date_or_units_rejected(record, tmp_path):
    with pytest.raises(IngestionError):
        ingest(MemoryAdapter([record]), JsonlStaging(tmp_path / "stage.jsonl"))


def test_cli_one_command_run(tmp_path):
    destination = tmp_path / "cli.jsonl"
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
    completed = subprocess.run(
        [sys.executable, "-m", "iris_adapters", "--output", str(destination)],
        cwd=ROOT, env=env, text=True, capture_output=True, check=True,
    )
    assert "staged 24 validated records" in completed.stdout
    assert len(_read_lines(destination)) == 24
