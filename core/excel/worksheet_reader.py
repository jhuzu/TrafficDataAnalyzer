"""Dependency-free reader for regular OOXML worksheets (.xlsx/.xlsm)."""

from __future__ import annotations

import io
import posixpath
import re
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .models import ExcelDataSource, ensure_count_field, unique_headers

MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
NS = f"{{{MAIN_NS}}}"
REL = f"{{{REL_NS}}}"
MAX_UNCOMPRESSED_BYTES = 500 * 1024 * 1024
BUILTIN_DATE_FORMATS = set(range(14, 23)) | set(range(27, 37)) | set(range(45, 48)) | set(range(50, 59))


def _column_index(reference: str) -> int:
    letters = re.match(r"[A-Z]+", reference.upper())
    if not letters:
        return 0
    value = 0
    for char in letters.group(0):
        value = value * 26 + ord(char) - 64
    return value - 1


def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    return ["".join(node.text or "" for node in item.iter(f"{NS}t")) for item in root]


def _date_style_indexes(archive: zipfile.ZipFile) -> tuple[set[int], set[int]]:
    if "xl/styles.xml" not in archive.namelist():
        return set(), set()
    root = ET.fromstring(archive.read("xl/styles.xml"))
    custom: dict[int, str] = {}
    num_fmts = root.find(f"{NS}numFmts")
    if num_fmts is not None:
        for item in num_fmts:
            custom[int(item.attrib["numFmtId"])] = item.attrib.get("formatCode", "")
    date_styles: set[int] = set()
    time_only_styles: set[int] = set()
    cell_xfs = root.find(f"{NS}cellXfs")
    if cell_xfs is None:
        return date_styles, time_only_styles
    for index, xf in enumerate(cell_xfs):
        num_fmt_id = int(xf.attrib.get("numFmtId", 0))
        code = custom.get(num_fmt_id, "")
        cleaned = re.sub(r'"[^"]*"|\[[^]]*\]|\\.', "", code.lower())
        is_date = num_fmt_id in BUILTIN_DATE_FORMATS or bool(re.search(r"[ymdhis]", cleaned))
        if is_date:
            date_styles.add(index)
            if not re.search(r"[yd]", cleaned) and bool(re.search(r"[his]", cleaned)):
                time_only_styles.add(index)
    return date_styles, time_only_styles


def _excel_datetime(raw: float, time_only: bool) -> str:
    value = datetime(1899, 12, 30) + timedelta(days=raw)
    if time_only:
        return value.strftime("%H:%M:%S")
    if value.time() == datetime.min.time():
        return value.strftime("%Y-%m-%d")
    return value.strftime("%Y-%m-%d %H:%M:%S")


def _cell_value(
    cell: ET.Element,
    shared: list[str],
    date_styles: set[int],
    time_only_styles: set[int],
) -> Any:
    cell_type = cell.attrib.get("t", "n")
    value_node = cell.find(f"{NS}v")
    raw = value_node.text if value_node is not None else None
    if cell_type == "inlineStr":
        inline = cell.find(f"{NS}is")
        return "" if inline is None else "".join(node.text or "" for node in inline.iter(f"{NS}t"))
    if raw is None:
        return None
    if cell_type == "s":
        try:
            return shared[int(raw)]
        except (IndexError, ValueError):
            return raw
    if cell_type in ("str", "e"):
        return raw
    if cell_type == "b":
        return raw == "1"
    try:
        number = float(raw)
    except ValueError:
        return raw
    style = int(cell.attrib.get("s", 0))
    if style in date_styles:
        return _excel_datetime(number, style in time_only_styles)
    return int(number) if number.is_integer() else number


def _worksheet_paths(archive: zipfile.ZipFile) -> list[tuple[str, str]]:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    targets = {
        rel.attrib["Id"]: rel.attrib["Target"]
        for rel in rels.findall(f"{{{PKG_REL_NS}}}Relationship")
    }
    output: list[tuple[str, str]] = []
    sheets = workbook.find(f"{NS}sheets")
    if sheets is None:
        return output
    names = set(archive.namelist())
    for sheet in sheets:
        target = targets.get(sheet.attrib.get(f"{REL}id", ""), "")
        if not target:
            continue
        path = target.lstrip("/") if target.startswith("/") else posixpath.normpath(posixpath.join("xl", target))
        if path in names:
            output.append((sheet.attrib.get("name", path), path))
    return output


def _read_rows(
    archive: zipfile.ZipFile,
    worksheet_path: str,
    shared: list[str],
    date_styles: set[int],
    time_only_styles: set[int],
) -> list[list[Any]]:
    rows: list[list[Any]] = []
    stream = io.BytesIO(archive.read(worksheet_path))
    for _, element in ET.iterparse(stream, events=("end",)):
        if element.tag != f"{NS}row":
            continue
        values: dict[int, Any] = {}
        for cell in element.findall(f"{NS}c"):
            index = _column_index(cell.attrib.get("r", "A1"))
            values[index] = _cell_value(cell, shared, date_styles, time_only_styles)
        if values:
            width = max(values) + 1
            rows.append([values.get(index) for index in range(width)])
        else:
            rows.append([])
        element.clear()
    return rows


def _header_candidate(
    rows: list[list[Any]], preferred_headers: set[str]
) -> tuple[int, int, int] | None:
    best: tuple[int, int, int] | None = None
    for row_index, row in enumerate(rows[:50]):
        last = max((i for i, value in enumerate(row) if value not in (None, "")), default=-1)
        if last < 1:
            continue
        values = [str(value).strip() for value in row[: last + 1] if value not in (None, "")]
        text_values = [value for value in values if value]
        matches = len(set(text_values) & preferred_headers)
        following = rows[row_index + 1 : row_index + 6]
        density = sum(sum(value not in (None, "") for value in data_row[: last + 1]) for data_row in following)
        score = matches * 1000 + len(text_values) * 20 + density - row_index
        candidate = (score, row_index, last + 1)
        if best is None or candidate > best:
            best = candidate
    return best


def _source_from_sheet(
    sheet_name: str,
    rows: list[list[Any]],
    preferred_headers: set[str],
    count_field: str,
) -> ExcelDataSource | None:
    candidate = _header_candidate(rows, preferred_headers)
    if candidate is None:
        return None
    score, header_index, width = candidate
    headers = unique_headers((rows[header_index] + [None] * width)[:width])
    data_rows: list[list[Any]] = []
    for row in rows[header_index + 1 :]:
        normalized = (row + [None] * width)[:width]
        if any(value not in (None, "") for value in normalized):
            data_rows.append(normalized)
    if not data_rows:
        return None
    headers, data_rows, row_mode = ensure_count_field(headers, data_rows, count_field)
    recognized = len(set(headers) & preferred_headers)
    quality = recognized * 100000 + len(headers) * 100 + min(len(data_rows), 9999)
    warnings = []
    if header_index:
        warnings.append(f"工作表「{sheet_name}」自第 {header_index + 1} 列辨識為欄位名稱。")
    if row_mode == "raw":
        warnings.append(f"工作表沒有「{count_field}」欄位，已將每列視為 1 件。")
    return ExcelDataSource(
        headers=headers,
        rows=data_rows,
        source_type="worksheet",
        row_mode=row_mode,
        sheet_name=sheet_name,
        warnings=warnings,
        quality_score=quality,
    )


def read_worksheet_source(
    source: str | Path,
    preferred_headers: set[str] | None = None,
    count_field: str = "件數",
) -> ExcelDataSource:
    preferred = preferred_headers or set()
    with zipfile.ZipFile(source) as archive:
        if sum(item.file_size for item in archive.infolist()) > MAX_UNCOMPRESSED_BYTES:
            raise ValueError("Excel 解壓後資料量超過 500 MB，已停止讀取。")
        if "xl/workbook.xml" not in archive.namelist():
            raise ValueError("檔案不是有效的 Excel OOXML 活頁簿。")
        shared = _shared_strings(archive)
        date_styles, time_only_styles = _date_style_indexes(archive)
        candidates: list[ExcelDataSource] = []
        for sheet_name, path in _worksheet_paths(archive):
            rows = _read_rows(archive, path, shared, date_styles, time_only_styles)
            candidate = _source_from_sheet(sheet_name, rows, preferred, count_field)
            if candidate is not None:
                candidates.append(candidate)
    if not candidates:
        raise ValueError("找不到具有欄位列與資料列的一般工作表。")
    return max(candidates, key=lambda item: item.quality_score)
