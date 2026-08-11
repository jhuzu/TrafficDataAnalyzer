"""Select the most useful data source inside an uploaded Excel workbook."""

from __future__ import annotations

import zipfile
from pathlib import Path

from .models import ExcelDataSource
from .pivot_cache_reader import read_pivot_cache_source
from .worksheet_reader import read_worksheet_source

SUPPORTED_EXTENSIONS = {".xlsx", ".xlsm"}


def read_excel_source(
    source: str | Path,
    preferred_headers: set[str] | None = None,
    count_field: str = "件數",
) -> ExcelDataSource:
    path = Path(source)
    suffix = path.suffix.lower()
    if suffix == ".xls":
        raise ValueError("舊版 .xls 尚未支援，請先在 Excel 另存為 .xlsx 或 .xlsm。")
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ValueError("僅支援 .xlsx、.xlsm；舊版 .xls 請先另存新格式。")
    if not zipfile.is_zipfile(path):
        raise ValueError("檔案內容不是有效的 .xlsx 或 .xlsm。")

    candidates: list[ExcelDataSource] = []
    errors: list[str] = []
    for reader in (read_worksheet_source, read_pivot_cache_source):
        try:
            candidates.append(reader(path, preferred_headers, count_field))
        except (ValueError, zipfile.BadZipFile, KeyError) as error:
            errors.append(str(error))
    if not candidates:
        detail = "；".join(dict.fromkeys(errors))
        raise ValueError(f"Excel 中找不到可分析資料。{detail}")

    # A regular source worksheet is preferred on equal quality. A richer Pivot
    # Cache still wins over a small pivot summary displayed on a worksheet.
    return max(
        candidates,
        key=lambda item: (item.quality_score, item.source_type == "worksheet"),
    )
