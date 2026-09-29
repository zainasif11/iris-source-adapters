"""Atomic JSONL staging and optional transactional PostGIS staging."""

import json
import os
import tempfile
from pathlib import Path
from typing import Sequence
from uuid import UUID, uuid4

from .contract import CanonicalRecord


class JsonlStaging:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def load(self, records: Sequence[CanonicalRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", newline="\n", dir=self.path.parent,
                prefix=f".{self.path.name}.", suffix=".tmp", delete=False,
            ) as output:
                temporary_path = output.name
                for record in records:
                    output.write(json.dumps(record.to_dict(), sort_keys=True, allow_nan=False) + "\n")
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary_path, self.path)
        finally:
            if temporary_path and os.path.exists(temporary_path):
                os.unlink(temporary_path)
        return len(records)


class PostgresStaging:
    """Load a validated batch into the schema created by sql/001_staging.sql.

    psycopg is imported only for this sink so the fixture run has no dependencies.
    """

    def __init__(self, dsn: str, batch_id: UUID | None = None):
        if not dsn:
            raise ValueError("a PostgreSQL DSN is required")
        self.dsn = dsn
        self.batch_id = batch_id or uuid4()

    def load(self, records: Sequence[CanonicalRecord]) -> int:
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError("install the postgres extra: pip install -e '.[postgres]'") from exc
        statement = """
            INSERT INTO iris.staging_records (
                batch_id, country_code, source_id, record_id, region_code,
                source_date, fetched_at, attributes, geom, crs,
                completeness, units, uncertainty
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s::jsonb, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326), %s,
                %s, %s::jsonb, %s::jsonb
            )
        """
        rows = [
            (
                self.batch_id, record.country_code, record.source_id, record.record_id,
                record.region_code, record.source_date, record.fetched_at,
                json.dumps(record.attributes, allow_nan=False),
                json.dumps(record.geom, allow_nan=False) if record.geom is not None else None,
                record.crs, record.completeness,
                json.dumps(record.units, allow_nan=False),
                json.dumps(record.uncertainty, allow_nan=False),
            )
            for record in records
        ]
        with psycopg.connect(self.dsn) as connection:
            with connection.cursor() as cursor:
                cursor.executemany(statement, rows)
        return len(records)
