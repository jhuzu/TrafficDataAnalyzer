"""Transform generic Excel data into the accident module's stable dataset."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Iterable, Mapping


ACCIDENT_PREFERRED_HEADERS = {
    "事故類別",
    "發生年",
    "發生月",
    "發生日",
    "發生時間",
    "路段",
    "交叉路名",
    "肇事原因",
    "年齡",
    "當事者區分",
    "件數",
    "飲酒情形",
    "施用毒品情形",
    "唾液毒品檢測",
    "經度",
    "緯度",
    "X座標",
    "Y座標",
}


@dataclass(frozen=True)
class AccidentDataset:
    """Immutable, JSON-serializable accident data used by every consumer."""

    headers: tuple[str, ...]
    rows: tuple[tuple[Any, ...], ...]
    source_type: str = "unknown"
    row_mode: str = "unknown"
    sheet_name: str | None = None
    warnings: tuple[str, ...] = ()
    _positions: Mapping[str, int] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "_positions", MappingProxyType({name: index for index, name in enumerate(self.headers)})
        )

    @property
    def positions(self) -> Mapping[str, int]:
        return self._positions

    def position(self, field: str) -> int | None:
        return self._positions.get(field)

    def text(self, row: tuple[Any, ...], field: str) -> str:
        position = self.position(field)
        if position is None or position >= len(row) or row[position] in (None, ""):
            return ""
        return str(row[position]).strip()

    def number(self, row: tuple[Any, ...], field: str, default: float = 0) -> float:
        position = self.position(field)
        if position is None or position >= len(row) or row[position] in (None, ""):
            return default
        try:
            return float(row[position])
        except (TypeError, ValueError):
            return default

    def total(self, rows: Iterable[tuple[Any, ...]] | None = None, field: str = "件數") -> float:
        """Sum one numeric field with the dataset's normalization rules."""
        return sum(self.number(row, field) for row in (self.rows if rows is None else rows))

    def select(
        self,
        field: str,
        allowed: set[str],
        rows: Iterable[tuple[Any, ...]] | None = None,
        *,
        uppercase: bool = False,
    ) -> list[tuple[Any, ...]]:
        """Select rows by exact text values without duplicating column lookup logic."""
        source = self.rows if rows is None else rows
        if self.position(field) is None:
            return []
        return [
            row
            for row in source
            if (self.text(row, field).upper() if uppercase else self.text(row, field)) in allowed
        ]

    def subset(self, rows: Iterable[tuple[Any, ...]]) -> "AccidentDataset":
        """Create an immutable view-like dataset with identical source metadata."""
        return AccidentDataset(
            headers=self.headers,
            rows=tuple(rows),
            source_type=self.source_type,
            row_mode=self.row_mode,
            sheet_name=self.sheet_name,
            warnings=self.warnings,
        )

    def to_source_dict(self) -> dict[str, Any]:
        """Return the legacy headers/rows contract used by presentation generators."""
        return {
            "headers": list(self.headers),
            "rows": [list(row) for row in self.rows],
            "sourceType": self.source_type,
            "rowMode": self.row_mode,
            "sheetName": self.sheet_name,
            "warnings": list(self.warnings),
        }


def transform_accident_source(source: dict[str, Any]) -> AccidentDataset:
    """Validate shape and normalize metadata without applying analysis rules."""
    raw_headers = source.get("headers") or []
    if not isinstance(raw_headers, (list, tuple)) or not raw_headers:
        raise ValueError("事故資料沒有可用的欄位名稱。")
    headers = [str(value).strip() for value in raw_headers]
    if any(not value for value in headers):
        raise ValueError("事故資料包含空白欄位名稱。")
    if len(set(headers)) != len(headers):
        raise ValueError("事故資料包含重複欄位名稱。")

    raw_rows = source.get("rows") or []
    if not isinstance(raw_rows, (list, tuple)):
        raise ValueError("事故資料列格式錯誤。")
    width = len(headers)
    rows = []
    for raw_row in raw_rows:
        if not isinstance(raw_row, (list, tuple)):
            raise ValueError("事故資料中存在無法辨識的資料列。")
        row = (list(raw_row) + [None] * width)[:width]
        if any(value not in (None, "") for value in row):
            rows.append(row)

    warnings = [str(value) for value in (source.get("warnings") or [])]
    row_mode = str(source.get("rowMode") or source.get("row_mode") or "unknown")
    if "件數" not in headers:
        headers.append("件數")
        rows = [[*row, 1] for row in rows]
        row_mode = "raw"
        warnings.append("事故資料沒有「件數」欄位，已將每列視為 1 件。")

    return AccidentDataset(
        headers=tuple(headers),
        rows=tuple(tuple(row) for row in rows),
        source_type=str(source.get("sourceType") or source.get("source_type") or "unknown"),
        row_mode=row_mode,
        sheet_name=source.get("sheetName") or source.get("sheet_name"),
        warnings=tuple(dict.fromkeys(warnings)),
    )
