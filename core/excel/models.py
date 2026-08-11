"""Stable data contract returned by every Excel reader."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ExcelDataSource:
    headers: list[str]
    rows: list[list[Any]]
    source_type: str
    row_mode: str
    sheet_name: str | None = None
    warnings: list[str] = field(default_factory=list)
    quality_score: int = 0

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload.pop("quality_score", None)
        payload["sourceType"] = payload.pop("source_type")
        payload["rowMode"] = payload.pop("row_mode")
        payload["sheetName"] = payload.pop("sheet_name")
        return payload


def unique_headers(values: list[Any]) -> list[str]:
    """Return non-empty, deterministic header names without collisions."""
    seen: dict[str, int] = {}
    headers: list[str] = []
    for index, value in enumerate(values, start=1):
        base = str(value).strip() if value not in (None, "") else f"未命名欄位{index}"
        seen[base] = seen.get(base, 0) + 1
        headers.append(base if seen[base] == 1 else f"{base} ({seen[base]})")
    return headers


def ensure_count_field(
    headers: list[str], rows: list[list[Any]], count_field: str
) -> tuple[list[str], list[list[Any]], str]:
    """Make raw and aggregated sources share the same count contract."""
    width = len(headers)
    normalized = [(list(row) + [None] * width)[:width] for row in rows]
    if count_field in headers:
        return headers, normalized, "aggregated"
    return [*headers, count_field], [[*row, 1] for row in normalized], "raw"
