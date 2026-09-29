"""Reusable IRIS source-adapter contract and ingestion pipeline."""

from .contract import CanonicalRecord, SourceAdapter, SourceMetadata, SourceRecord
from .pipeline import IngestionError, ingest

__all__ = [
    "CanonicalRecord",
    "IngestionError",
    "SourceAdapter",
    "SourceMetadata",
    "SourceRecord",
    "ingest",
]
