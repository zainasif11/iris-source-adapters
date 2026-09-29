"""The only types a new source adapter must implement or construct."""

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from datetime import date, datetime
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class SourceMetadata:
    source_id: str
    source_date: date | str
    fetched_at: datetime | str
    country_code: str
    region_code: str | None
    crs: str | None
    completeness: str
    units: Mapping[str, str]
    uncertainty: Mapping[str, Any]


@dataclass(frozen=True)
class SourceRecord:
    record_id: str
    metadata: SourceMetadata
    attributes: Mapping[str, Any]
    geometry: Mapping[str, Any] | str | None


@dataclass(frozen=True)
class CanonicalRecord:
    record_id: str
    country_code: str
    region_code: str | None
    source_id: str
    source_date: str
    fetched_at: str
    attributes: dict[str, Any]
    geom: dict[str, Any] | None
    crs: str | None
    completeness: str
    units: dict[str, str]
    uncertainty: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SourceAdapter(ABC):
    """Implement extract and map_record; the core handles all later stages.

    extract() yields source-native rows. map_record() maps one such row to
    SourceRecord. No adapter writes to staging or decides QA policy.
    """

    @abstractmethod
    def extract(self) -> Iterable[Any]:
        raise NotImplementedError

    @abstractmethod
    def map_record(self, raw: Any) -> SourceRecord:
        raise NotImplementedError
