"""Prepare auditable tabular payloads for standardized-data exports."""

from __future__ import annotations

from collections import Counter
from typing import Any

from .schema import ViolationDataset, ViolationRecord


STANDARDIZED_HEADERS = (
    "來源檔案", "來源工作表", "來源資料序", "舉發單號",
    "違規日期", "民國年", "月", "日", "違規時間", "時",
    "條", "項", "款", "目", "違規條款", "違規條款2", "違規內容",
    "行政區", "違規路段", "路段備註", "違規地點", "舉發單位", "舉發類型",
    "簡式車種", "車種", "酒測值", "是否作廢", "件數", "緯度", "經度",
)

STANDARD_FIELD_LABELS = {
    "case_id": "舉發單號",
    "violation_date": "違規日期",
    "violation_time": "違規時間",
    "law_article": "條",
    "law_paragraph": "項",
    "law_clause": "款",
    "law_item": "目",
    "law_text": "違規條款",
    "secondary_law_text": "違規條款2",
    "description": "違規內容",
    "district": "行政區",
    "road": "違規路段",
    "road_note": "路段備註",
    "location": "違規地點",
    "enforcement_unit": "舉發單位",
    "enforcement_type": "舉發類型",
    "simple_vehicle_type": "簡式車種",
    "vehicle_type": "車種",
    "alcohol_test_value": "酒測值",
    "void_status": "是否作廢",
    "count": "件數",
    "latitude": "緯度",
    "longitude": "經度",
}


def _row(record: ViolationRecord) -> list[Any]:
    return [
        record.source_file, record.source_sheet, record.source_record_number, record.case_id,
        record.violation_date, record.roc_year, record.month, record.day,
        record.violation_time, record.hour, record.law_article, record.law_paragraph,
        record.law_clause, record.law_item, record.law_text, record.secondary_law_text,
        record.description, record.district, record.road, record.road_note, record.location,
        record.enforcement_unit, record.enforcement_type, record.simple_vehicle_type,
        record.vehicle_type, record.alcohol_test_value, record.void_status, record.count,
        record.latitude, record.longitude,
    ]


def build_standardized_export(
    dataset: ViolationDataset,
    *,
    start_date: str,
    end_date: str,
    reference_total: int | None = None,
) -> dict[str, Any]:
    """Split normalized rows into the requested period and an exclusion audit."""
    inside = [
        record for record in dataset.records
        if record.violation_date and start_date <= record.violation_date <= end_date
    ]
    inside_ids = {id(record) for record in inside}
    outside = [record for record in dataset.records if id(record) not in inside_ids]
    inside_counts = Counter(record.source_id for record in inside)
    outside_counts = Counter(record.source_id for record in outside)

    source_rows = []
    mapping_rows = []
    for source in dataset.sources:
        source_dates = sorted(
            record.violation_date
            for record in dataset.records
            if record.source_id == source.source_id and record.violation_date
        )
        source_rows.append([
            source.file_name,
            {"loaded": "成功", "failed": "失敗"}.get(source.status, source.status),
            source.sheet_name, source.raw_row_count,
            inside_counts[source.source_id], outside_counts[source.source_id],
            source_dates[0] if source_dates else None,
            source_dates[-1] if source_dates else None,
            "、".join(source.missing_fields), " ".join(source.warnings),
        ])
        mapping_rows.extend(
            [source.file_name, STANDARD_FIELD_LABELS.get(canonical, canonical), original]
            for canonical, original in source.field_mapping
        )

    reconciliation = "未提供參考總數"
    if reference_total is not None:
        reconciliation = "一致" if len(inside) == reference_total else f"差異{len(inside) - reference_total:+,}筆"
    return {
        "period": {"start": start_date, "end": end_date},
        "headers": list(STANDARDIZED_HEADERS),
        "insideRows": [_row(record) for record in inside],
        "outsideRows": [_row(record) for record in outside],
        "sourceHeaders": [
            "來源檔案", "狀態", "工作表", "原始資料列", "期間內資料列",
            "期間外資料列", "最早日期", "最晚日期", "缺少欄位", "警告",
        ],
        "sourceRows": source_rows,
        "mappingHeaders": ["來源檔案", "標準欄位", "原始欄位"],
        "mappingRows": mapping_rows,
        "summary": {
            "sourceCount": len(dataset.sources),
            "rawRows": len(dataset.records),
            "insideRows": len(inside),
            "outsideRows": len(outside),
            "referenceTotal": reference_total,
            "reconciliation": reconciliation,
            "deduplicationStatus": dataset.deduplication_status,
        },
        "notes": [
            f"統計期間：{start_date} 至 {end_date}。",
            "期間內資料依違規日期篩選；日期無法辨識者列入期間外資料供檢查。",
            "10份來源已合併，但尚未跨檔去重；每筆仍保留來源檔案與來源資料序。",
            "本輸出僅完成資料標準化，尚未套用九大重大違規或五大行人路權分類規則。",
            "未識別的原始欄位仍保留在程式資料契約中；為避免擴散姓名、地址、車號等個資，本檢查版Excel只輸出分析所需標準欄位。",
            *dataset.warnings,
        ],
    }
