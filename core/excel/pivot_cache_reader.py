"""Read recoverable Pivot Cache records from OOXML workbooks."""

from __future__ import annotations

import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.etree.ElementTree import ParseError

from .models import ExcelDataSource, ensure_count_field, unique_headers

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def _item_value(node: ET.Element):
    tag = node.tag.rsplit("}", 1)[-1]
    raw = node.attrib.get("v", "")
    if tag == "m":
        return None
    if tag == "b":
        return raw == "1"
    if tag == "n":
        try:
            number = float(raw)
            return int(number) if number.is_integer() else number
        except ValueError:
            return raw
    return raw


def _cache_candidate(
    archive: zipfile.ZipFile,
    definition_name: str,
    preferred_headers: set[str],
    count_field: str,
) -> ExcelDataSource | None:
    suffix = definition_name.rsplit("pivotCacheDefinition", 1)[1].rsplit(".xml", 1)[0]
    records_name = f"xl/pivotCache/pivotCacheRecords{suffix}.xml"
    if records_name not in archive.namelist():
        return None
    try:
        definition = ET.fromstring(archive.read(definition_name))
        records_root = ET.fromstring(archive.read(records_name))
    except ParseError as error:
        raise ValueError(f"Pivot Cache XML 格式損壞，無法解析：{error}") from error

    fields: list[str] = []
    shared: list[list[object]] = []
    cache_fields = definition.find(f"{NS}cacheFields")
    if cache_fields is None:
        return None
    for field in cache_fields:
        fields.append(field.attrib.get("name", ""))
        items = field.find(f"{NS}sharedItems")
        shared.append([_item_value(cell) for cell in items] if items is not None else [])
    headers = unique_headers(fields)
    rows = []
    for record in records_root:
        row = []
        for index, cell in enumerate(record):
            tag = cell.tag.rsplit("}", 1)[-1]
            if tag == "x":
                try:
                    row.append(shared[index][int(cell.attrib["v"])])
                except (IndexError, ValueError):
                    row.append(None)
            else:
                row.append(_item_value(cell))
        rows.append((row + [None] * len(headers))[: len(headers)])
    if not rows:
        return None
    headers, rows, row_mode = ensure_count_field(headers, rows, count_field)
    recognized = len(set(headers) & preferred_headers)
    quality = recognized * 100000 + len(headers) * 100 + min(len(rows), 9999)
    warnings = []
    if row_mode == "raw":
        warnings.append(f"Pivot Cache 沒有「{count_field}」欄位，已將每列視為 1 件。")
    return ExcelDataSource(
        headers=headers,
        rows=rows,
        source_type="pivot-cache",
        row_mode=row_mode,
        warnings=warnings,
        quality_score=quality,
    )


def read_pivot_cache_source(
    source: str | Path,
    preferred_headers: set[str] | None = None,
    count_field: str = "件數",
) -> ExcelDataSource:
    preferred = preferred_headers or set()
    with zipfile.ZipFile(source) as archive:
        definitions = sorted(
            name
            for name in archive.namelist()
            if name.startswith("xl/pivotCache/pivotCacheDefinition") and name.endswith(".xml")
        )
        if not definitions:
            raise ValueError("此檔案未保留可還原的 Pivot Cache。")
        candidates = [
            candidate
            for name in definitions
            if (candidate := _cache_candidate(archive, name, preferred, count_field)) is not None
        ]
    if not candidates:
        raise ValueError("找到 Pivot Cache 定義，但沒有可還原的記錄資料。")
    return max(candidates, key=lambda item: item.quality_score)
