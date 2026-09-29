"""Source-independent extract -> normalize -> validate -> stage orchestration."""

from typing import Protocol, Sequence

from .contract import CanonicalRecord, SourceAdapter, SourceRecord
from .normalization import normalize
from .validation import validate


class StagingSink(Protocol):
    def load(self, records: Sequence[CanonicalRecord]) -> int: ...


class IngestionError(ValueError):
    """A source row failed before anything was staged."""


def ingest(adapter: SourceAdapter, sink: StagingSink) -> int:
    """Stage one all-or-nothing batch after validating every source row."""
    records: list[CanonicalRecord] = []
    seen: set[tuple[str, str, str]] = set()
    iterator = iter(adapter.extract())
    row_number = 0
    while True:
        try:
            raw = next(iterator)
        except StopIteration:
            break
        except Exception as exc:
            raise IngestionError(f"source row {row_number + 1}: extraction failed: {exc}") from exc
        row_number += 1
        try:
            mapped = adapter.map_record(raw)
            if not isinstance(mapped, SourceRecord):
                raise TypeError("adapter.map_record must return SourceRecord")
            record = normalize(mapped)
            validate(record)
            key = (record.country_code, record.source_id, record.record_id)
            if key in seen:
                raise ValueError(f"duplicate country/source/record key: {key}")
            seen.add(key)
            records.append(record)
        except (TypeError, ValueError, KeyError) as exc:
            raise IngestionError(f"source row {row_number}: {exc}") from exc
    return sink.load(records)
