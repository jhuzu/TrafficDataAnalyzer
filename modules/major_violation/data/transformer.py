"""Normalize heterogeneous violation worksheets without applying category rules."""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime, time, timedelta
from typing import Any, Iterable

from .schema import ViolationDataset, ViolationRecord, ViolationSourceInfo


FIELD_ALIASES = {
    "case_id": ("案件編號", "案號", "舉發單號", "舉發通知單號", "通知單號", "違規單號"),
    "violation_date": ("違規日期", "違規年月日", "舉發日期", "發生日期", "日期"),
    "violation_time": ("違規時間", "舉發時間", "發生時間", "時間"),
    "law_article": ("條次", "法條條次", "違規條次", "處罰條次"),
    "law_paragraph": ("項次", "法條項次", "違規項次"),
    "law_clause": ("款次", "法條款次", "違規款次"),
    "law_item": ("目次", "法條目次", "違規目次"),
    "law_text": ("違反法條", "違規法條", "法條", "處罰條例", "違規條文", "違規條款"),
    "secondary_law_text": ("違規條款2", "第二違規條款", "次要違規條款"),
    "description": ("違規事實", "違規事項", "違規內容", "違規名稱", "舉發事實"),
    "road": ("違規路段1", "違規路段一", "違規路段", "路段", "道路", "道路名稱"),
    "road_note": ("違規路段1備註", "違規路段備註", "路段備註"),
    "location": ("違規地點", "舉發地點", "發生地點", "地點", "地址"),
    "district": ("違規行政區1", "違規行政區", "行政區"),
    "enforcement_unit": ("舉發單位", "執法單位", "處理單位", "單位"),
    "enforcement_type": ("舉發類型", "執法類型"),
    "simple_vehicle_type": ("簡式車種", "車種簡稱"),
    "vehicle_type": ("車種", "車輛種類"),
    "alcohol_test_value": ("酒測值", "酒精濃度"),
    "void_status": ("是否作廢", "作廢狀態"),
    "count": ("件數", "數量", "筆數"),
    "latitude": ("緯度", "GPS緯度", "Y座標", "Latitude", "lat"),
    "longitude": ("經度", "GPS經度", "X座標", "Longitude", "lng", "lon"),
}

VIOLATION_PREFERRED_HEADERS = {
    alias for aliases in FIELD_ALIASES.values() for alias in aliases
}

DISPLAY_FIELDS = {
    "violation_date": "違規日期",
    "rule_basis": "法條或違規內容",
    "road": "違規路段",
}


def _key(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).strip().lower()
    return re.sub(r"[\s_]+", "", text)


def _text(value: Any) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return unicodedata.normalize("NFKC", str(value)).strip()


def _number(value: Any, default: float = 1.0) -> float:
    if value in (None, ""):
        return default
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return default


def _coordinate(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _date_parts(value: Any) -> tuple[str | None, int | None, int | None, int | None]:
    parsed: date | None = None
    if isinstance(value, datetime):
        parsed = value.date()
    elif isinstance(value, date):
        parsed = value
    elif isinstance(value, (int, float)) and 20000 <= float(value) <= 80000:
        parsed = date(1899, 12, 30) + timedelta(days=int(float(value)))
    else:
        text = _text(value)
        digits = re.sub(r"\D", "", text)
        try:
            if re.fullmatch(r"\d{7}", digits):
                parsed = date(int(digits[:3]) + 1911, int(digits[3:5]), int(digits[5:7]))
            elif re.fullmatch(r"\d{8}", digits):
                parsed = date(int(digits[:4]), int(digits[4:6]), int(digits[6:8]))
            else:
                match = re.search(r"(\d{2,4})\D+(\d{1,2})\D+(\d{1,2})", text)
                if match:
                    year, month, day = (int(part) for part in match.groups())
                    parsed = date(year + 1911 if year < 1911 else year, month, day)
        except ValueError:
            parsed = None
    if parsed is None:
        return None, None, None, None
    roc_year = parsed.year - 1911 if parsed.year >= 1912 else None
    return parsed.isoformat(), roc_year, parsed.month, parsed.day


def _time_parts(value: Any) -> tuple[str | None, int | None]:
    parsed: time | None = None
    if isinstance(value, datetime):
        parsed = value.time()
    elif isinstance(value, time):
        parsed = value
    elif isinstance(value, (int, float)) and 0 <= float(value) < 1:
        seconds = round(float(value) * 86400) % 86400
        parsed = time(seconds // 3600, seconds % 3600 // 60, seconds % 60)
    else:
        text = _text(value)
        colon = re.search(r"(\d{1,2}):(\d{1,2})(?::(\d{1,2}))?", text)
        try:
            if colon:
                hour, minute, second = colon.groups()
                parsed = time(int(hour), int(minute), int(second or 0))
            else:
                digits = re.sub(r"\D", "", text)
                if 1 <= len(digits) <= 2:
                    parsed = time(int(digits), 0)
                elif 3 <= len(digits) <= 4:
                    padded = digits.zfill(4)
                    parsed = time(int(padded[:2]), int(padded[2:4]))
                elif 5 <= len(digits) <= 6:
                    padded = digits.zfill(6)
                    parsed = time(int(padded[:2]), int(padded[2:4]), int(padded[4:6]))
        except ValueError:
            parsed = None
    if parsed is None:
        return None, None
    return parsed.strftime("%H:%M:%S"), parsed.hour


def _law_part(value: Any, unit: str) -> str:
    text = _text(value)
    if not text:
        return ""
    match = re.search(rf"(?:第)?\s*(\d+(?:[-之]\d+)?)\s*{unit}", text)
    if match:
        return _normalize_law_number(match.group(1))
    plain = re.fullmatch(r"\s*(\d+(?:[-之]\d+)?)\s*", text)
    return _normalize_law_number(plain.group(1)) if plain else ""


def _normalize_law_number(value: str) -> str:
    parts = re.split(r"[-之]", value)
    return "-".join(str(int(part)) for part in parts)


def _resolve_headers(headers: list[str]) -> dict[str, str]:
    available = {_key(header): header for header in headers}
    resolved: dict[str, str] = {}
    for canonical, aliases in FIELD_ALIASES.items():
        match = next((available[_key(alias)] for alias in aliases if _key(alias) in available), None)
        if match is not None:
            resolved[canonical] = match
    return resolved


def transform_violation_source(
    source: dict[str, Any],
    *,
    source_name: str = "未命名來源",
    source_id: str = "source-1",
) -> ViolationDataset:
    """Normalize one generic Excel source without classifying violations."""
    raw_headers = source.get("headers") or []
    if not isinstance(raw_headers, (list, tuple)) or not raw_headers:
        raise ValueError("重大違規資料沒有可用的欄位名稱。")
    headers = [_text(header) for header in raw_headers]
    if any(not header for header in headers) or len(set(headers)) != len(headers):
        raise ValueError("重大違規資料包含空白或重複欄位名稱。")
    raw_rows = source.get("rows") or []
    if not isinstance(raw_rows, (list, tuple)):
        raise ValueError("重大違規資料列格式錯誤。")

    positions = {header: index for index, header in enumerate(headers)}
    mapping = _resolve_headers(headers)
    mapped_headers = set(mapping.values())
    width = len(headers)

    def value(row: list[Any], canonical: str) -> Any:
        header = mapping.get(canonical)
        return row[positions[header]] if header is not None else None

    invalid_dates = 0
    invalid_times = 0
    records: list[ViolationRecord] = []
    for record_number, raw_row in enumerate(raw_rows, start=1):
        if not isinstance(raw_row, (list, tuple)):
            raise ValueError("重大違規資料中存在無法辨識的資料列。")
        row = (list(raw_row) + [None] * width)[:width]
        if not any(cell not in (None, "") for cell in row):
            continue

        raw_date = value(row, "violation_date")
        violation_date, roc_year, month, day = _date_parts(raw_date)
        if raw_date not in (None, "") and violation_date is None:
            invalid_dates += 1
        raw_time = value(row, "violation_time")
        violation_time, hour = _time_parts(raw_time)
        if raw_time not in (None, "") and violation_time is None:
            invalid_times += 1

        law_text = _text(value(row, "law_text"))
        secondary_law_text = _text(value(row, "secondary_law_text"))
        description = _text(value(row, "description"))
        combined_rule_text = " ".join(
            part for part in (law_text, secondary_law_text, description) if part
        )
        article = _law_part(value(row, "law_article"), "條") or _law_part(combined_rule_text, "條")
        paragraph = _law_part(value(row, "law_paragraph"), "項") or _law_part(combined_rule_text, "項")
        clause = _law_part(value(row, "law_clause"), "款") or _law_part(combined_rule_text, "款")
        item = _law_part(value(row, "law_item"), "目") or _law_part(combined_rule_text, "目")
        extra_fields = tuple(
            (header, row[index])
            for index, header in enumerate(headers)
            if header not in mapped_headers and row[index] not in (None, "")
        )
        records.append(ViolationRecord(
            source_id=source_id,
            source_file=source_name,
            source_sheet=_text(source.get("sheetName") or source.get("sheet_name")) or None,
            source_record_number=record_number,
            case_id=_text(value(row, "case_id")),
            violation_date=violation_date,
            roc_year=roc_year,
            month=month,
            day=day,
            violation_time=violation_time,
            hour=hour,
            law_article=article,
            law_paragraph=paragraph,
            law_clause=clause,
            law_item=item,
            law_text=law_text,
            secondary_law_text=secondary_law_text,
            description=description,
            road=_text(value(row, "road")),
            road_note=_text(value(row, "road_note")),
            location=_text(value(row, "location")),
            district=_text(value(row, "district")),
            enforcement_unit=_text(value(row, "enforcement_unit")),
            enforcement_type=_text(value(row, "enforcement_type")),
            simple_vehicle_type=_text(value(row, "simple_vehicle_type")),
            vehicle_type=_text(value(row, "vehicle_type")),
            alcohol_test_value=_text(value(row, "alcohol_test_value")),
            void_status=_text(value(row, "void_status")),
            count=_number(value(row, "count"), 1.0),
            latitude=_coordinate(value(row, "latitude")),
            longitude=_coordinate(value(row, "longitude")),
            extra_fields=extra_fields,
        ))

    missing: list[str] = []
    if "violation_date" not in mapping:
        missing.append(DISPLAY_FIELDS["violation_date"])
    if not any(field in mapping for field in ("law_article", "law_text", "description")):
        missing.append(DISPLAY_FIELDS["rule_basis"])
    if "road" not in mapping and "location" not in mapping:
        missing.append(DISPLAY_FIELDS["road"])

    warnings = [_text(item) for item in (source.get("warnings") or []) if _text(item)]
    if "count" not in mapping:
        warnings.append("來源沒有件數欄，每筆標準化資料暫按1件計算。")
    if invalid_dates:
        warnings.append(f"有{invalid_dates}筆違規日期無法標準化，已保留為空值。")
    if invalid_times:
        warnings.append(f"有{invalid_times}筆違規時間無法標準化，已保留為空值。")
    if missing:
        warnings.append(f"缺少建議欄位：{'、'.join(missing)}。")
    source_info = ViolationSourceInfo(
        source_id=source_id,
        file_name=source_name,
        sheet_name=_text(source.get("sheetName") or source.get("sheet_name")) or None,
        source_type=_text(source.get("sourceType") or source.get("source_type") or "unknown"),
        row_mode=_text(source.get("rowMode") or source.get("row_mode") or "unknown"),
        status="loaded",
        raw_row_count=len(records),
        mapped_fields=tuple(sorted(mapping)),
        field_mapping=tuple(sorted(mapping.items())),
        missing_fields=tuple(missing),
        warnings=tuple(dict.fromkeys(warnings)),
    )
    return ViolationDataset(
        records=tuple(records),
        sources=(source_info,),
        warnings=source_info.warnings,
    )


def merge_violation_datasets(
    datasets: Iterable[ViolationDataset],
    *,
    extra_sources: Iterable[ViolationSourceInfo] = (),
) -> ViolationDataset:
    """Merge normalized sources while deliberately preserving duplicate rows."""
    records: list[ViolationRecord] = []
    sources: list[ViolationSourceInfo] = []
    warnings: list[str] = []
    for dataset in datasets:
        records.extend(dataset.records)
        sources.extend(dataset.sources)
        warnings.extend(dataset.warnings)
    sources.extend(extra_sources)
    for source in extra_sources:
        warnings.extend(source.warnings)
    if len(sources) > 1:
        warnings.append("多份來源已合併，但尚未跨檔去重；目前保留每一筆原始資料列。")
    return ViolationDataset(
        records=tuple(records),
        sources=tuple(sources),
        warnings=tuple(dict.fromkeys(warnings)),
        deduplication_status="not_applied",
    )
