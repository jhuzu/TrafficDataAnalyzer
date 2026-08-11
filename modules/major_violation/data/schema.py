"""Immutable normalized data contracts for major-violation records."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class ViolationRecord:
    """One normalized source row; classification is intentionally not applied."""

    source_id: str
    source_file: str
    source_sheet: str | None
    source_record_number: int
    case_id: str
    violation_date: str | None
    roc_year: int | None
    month: int | None
    day: int | None
    violation_time: str | None
    hour: int | None
    law_article: str
    law_paragraph: str
    law_clause: str
    law_item: str
    law_text: str
    secondary_law_text: str
    description: str
    road: str
    road_note: str
    location: str
    district: str
    enforcement_unit: str
    enforcement_type: str
    simple_vehicle_type: str
    vehicle_type: str
    alcohol_test_value: str
    void_status: str
    count: float
    latitude: float | None
    longitude: float | None
    extra_fields: tuple[tuple[str, Any], ...] = ()


@dataclass(frozen=True)
class ViolationSourceInfo:
    """Import status and column mapping for one workbook source."""

    source_id: str
    file_name: str
    sheet_name: str | None
    source_type: str
    row_mode: str
    status: str
    raw_row_count: int
    mapped_fields: tuple[str, ...] = ()
    field_mapping: tuple[tuple[str, str], ...] = ()
    missing_fields: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class ViolationDataset:
    """Merged normalized records from one or more source workbooks."""

    records: tuple[ViolationRecord, ...]
    sources: tuple[ViolationSourceInfo, ...]
    warnings: tuple[str, ...] = ()
    deduplication_status: str = "not_applied"

    @property
    def raw_row_count(self) -> int:
        return len(self.records)

    @property
    def total_count(self) -> float:
        return sum(record.count for record in self.records)

    @property
    def date_range(self) -> tuple[str | None, str | None]:
        dates = sorted(record.violation_date for record in self.records if record.violation_date)
        return (dates[0], dates[-1]) if dates else (None, None)

    @property
    def deduplication_available(self) -> bool:
        return bool(self.records) and all(record.case_id for record in self.records)

    def to_dict(self) -> dict[str, Any]:
        start, end = self.date_range
        return {
            "records": [asdict(record) for record in self.records],
            "sources": [asdict(source) for source in self.sources],
            "warnings": list(self.warnings),
            "rawRowCount": self.raw_row_count,
            "totalCount": self.total_count,
            "dateRange": {"start": start, "end": end},
            "deduplicationStatus": self.deduplication_status,
            "deduplicationAvailable": self.deduplication_available,
        }
