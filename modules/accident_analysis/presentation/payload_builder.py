"""Build the template-neutral payload shared by every accident PPTX generator."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from ..analysis import AccidentAnalysisService
from ..data import AccidentDataset


SCHEMA_VERSION = "accident-weekly-report/v1"
AGE_RANGES = (
    ("0-17歲", 0, 17),
    ("18-30歲", 18, 30),
    ("31-40歲", 31, 40),
    ("41-50歲", 41, 50),
    ("51-60歲", 51, 60),
    ("61-70歲", 61, 70),
    ("71歲以上", 71, float("inf")),
)


def _clean_number(value: int | float) -> int | float:
    number = float(value)
    return int(number) if number.is_integer() else round(number, 2)


def _rank_items(items: list[dict[str, Any]], total: int | float) -> list[dict[str, Any]]:
    return [
        {
            "rank": index,
            "label": item["value"],
            "count": item["count"],
            "share": item["count"] / total if total else 0,
        }
        for index, item in enumerate(items, 1)
    ]


def _parse_age(dataset: AccidentDataset, row: tuple[Any, ...]) -> float | None:
    raw = dataset.text(row, "年齡").replace("歲", "")
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _parse_hour(raw: str) -> int | None:
    digits = re.sub(r"\D", "", raw or "")
    if not digits:
        return None
    hour = int(digits if len(digits) <= 2 else digits.zfill(4)[:2])
    return hour if 0 <= hour <= 23 else None


def _parse_year(raw: str) -> int | None:
    try:
        return int(float(raw))
    except (TypeError, ValueError):
        return None


def _change(current: int | float, previous: int | float, available: bool) -> dict[str, Any]:
    if not available:
        return {
            "available": False,
            "previous": None,
            "difference": None,
            "rate": None,
            "direction": "unavailable",
            "text": "未提供同期資料",
        }
    difference = current - previous
    direction = "increase" if difference > 0 else "decrease" if difference < 0 else "flat"
    rate = difference / previous if previous else None
    if difference == 0:
        text = "較前期持平"
    else:
        verb = "增加" if difference > 0 else "減少"
        rate_text = f"{abs(rate) * 100:.1f}%" if rate is not None else "無法計算增減率"
        text = f"較前期{verb}{abs(difference):,.0f}件，{rate_text}"
    return {
        "available": True,
        "previous": previous,
        "difference": _clean_number(float(difference)),
        "rate": rate,
        "direction": direction,
        "text": text,
    }


def _period_short(period: str) -> str:
    match = re.fullmatch(r"(.+?年)(\d+)月\d+日至(\d+)月\d+日", period)
    return f"{match.group(1)}{match.group(2)}-{match.group(3)}月" if match else period


def _short_label(value: str, maximum: int = 18) -> str:
    return value if len(value) <= maximum else f"{value[: maximum - 1]}…"


def build_presentation_payload(
    dataset: AccidentDataset,
    period: str = "115年1月1日至8月31日",
) -> dict[str, Any]:
    """Return one versioned statistical payload for all accident deck layouts."""
    period = str(period).strip() or "115年1月1日至8月31日"
    years = sorted(
        {
            year
            for row in dataset.rows
            if (year := _parse_year(dataset.text(row, "發生年"))) is not None
        },
        reverse=True,
    ) if dataset.position("發生年") is not None else []
    current_year = years[0] if years else None
    previous_year = years[1] if len(years) > 1 else None

    current_rows = (
        [row for row in dataset.rows if _parse_year(dataset.text(row, "發生年")) == current_year]
        if current_year is not None and previous_year is not None
        else list(dataset.rows)
    )
    previous_rows = (
        [row for row in dataset.rows if _parse_year(dataset.text(row, "發生年")) == previous_year]
        if previous_year is not None
        else []
    )

    def a1a2(rows: list[tuple[Any, ...]]) -> list[tuple[Any, ...]]:
        selected = dataset.select("事故類別", {"A1", "A2"}, rows, uppercase=True)
        return selected or rows

    rows = a1a2(current_rows)
    prior_rows = a1a2(previous_rows) if previous_rows else []
    current_dataset = dataset.subset(rows)
    analysis = AccidentAnalysisService(current_dataset).analyze(
        {"pattern": "all", "period": "month", "top": 20}
    )
    total = analysis["metrics"][0]["value"]

    a1_rows = dataset.select("事故類別", {"A1"}, rows, uppercase=True)
    a2_rows = dataset.select("事故類別", {"A2"}, rows, uppercase=True)
    previous_a1_rows = dataset.select("事故類別", {"A1"}, prior_rows, uppercase=True)
    previous_a2_rows = dataset.select("事故類別", {"A2"}, prior_rows, uppercase=True)
    a1_total, a2_total = _clean_number(dataset.total(a1_rows)), _clean_number(dataset.total(a2_rows))
    previous_total = _clean_number(dataset.total(prior_rows))
    previous_a1 = _clean_number(dataset.total(previous_a1_rows))
    previous_a2 = _clean_number(dataset.total(previous_a2_rows))

    rankings = {
        "roads": _rank_items(analysis["road"], total),
        "intersections": _rank_items(analysis["intersection"], total),
        "causes": _rank_items(analysis["cause"], total),
        "vehicles": _rank_items(analysis["vehicle"], total),
    }
    a1_analysis = AccidentAnalysisService(dataset.subset(a1_rows)).analyze(
        {"pattern": "all", "period": "month", "top": 2}
    ) if a1_rows else {"road": []}
    rankings["a1Roads"] = _rank_items(a1_analysis["road"], a1_total)

    age_totals: dict[str, float] = defaultdict(float)
    unknown_age = 0.0
    for row in rows:
        age = _parse_age(dataset, row)
        if age is None:
            unknown_age += dataset.number(row, "件數")
            continue
        for label, lower, upper in AGE_RANGES:
            if lower <= age <= upper:
                age_totals[label] += dataset.number(row, "件數")
                break
    age_groups = [
        {
            "label": label,
            "count": _clean_number(age_totals[label]),
            "share": age_totals[label] / total if total else 0,
        }
        for label, _, _ in AGE_RANGES
    ]
    age_groups.sort(key=lambda item: (-item["count"], item["label"]))

    time_totals = [0.0] * 12
    unknown_time = 0.0
    for row in rows:
        hour = _parse_hour(dataset.text(row, "發生時間"))
        if hour is None:
            unknown_time += dataset.number(row, "件數")
        else:
            time_totals[hour // 2] += dataset.number(row, "件數")
    time_buckets = [
        {
            "label": f"{index * 2:02d}-{(index * 2 + 2) % 24:02d}",
            "count": _clean_number(count),
            "share": count / total if total else 0,
        }
        for index, count in enumerate(time_totals)
    ]
    ranked_time_buckets = sorted(
        time_buckets, key=lambda item: (-item["count"], item["label"])
    )

    def incident_time(row: tuple[Any, ...]) -> str:
        month, day = dataset.text(row, "發生月"), dataset.text(row, "發生日")
        date_part = f"{month}月{day}日" if month and day else f"{month}月" if month else ""
        return " ".join(value for value in (date_part, dataset.text(row, "發生時間")) if value)

    def incident_location(row: tuple[Any, ...]) -> str:
        location = "／".join(
            value for value in (dataset.text(row, "路段"), dataset.text(row, "交叉路名")) if value
        )
        return location or dataset.text(row, "其他地點") or "未提供"

    a1_details = [
        {
            "number": index,
            "time": incident_time(row),
            "location": incident_location(row),
            "cause": dataset.text(row, "肇事原因") or "未提供",
            "vehicle": dataset.text(row, "當事者區分") or "未提供",
            "deaths": dataset.text(row, "死亡人數") or "1",
            "notes": dataset.text(row, "備註"),
        }
        for index, row in enumerate(a1_rows[:7], 1)
    ]

    top_road = rankings["roads"][0] if rankings["roads"] else None
    top_cause = rankings["causes"][0] if rankings["causes"] else None
    top_vehicle = rankings["vehicles"][0] if rankings["vehicles"] else None
    top_time = ranked_time_buckets[0] if ranked_time_buckets else None
    road_label = top_road["label"] if top_road else "未提供"
    cause_label = top_cause["label"] if top_cause else "未提供"
    summary = (
        f"本期統計{total:,.0f}件；易肇事路段以{road_label}"
        f"（{(top_road or {}).get('count', 0):,.0f}件）為首，主要肇因為{cause_label}"
        f"（{(top_cause or {}).get('count', 0):,.0f}件），應依熱點與高風險時段持續部署勤務。"
    )
    enforcement = (
        f"建議以{road_label if top_road else '主要熱點路段'}及"
        f"{(top_time or {}).get('label', '高峰時段')}列為優先勤務區段，"
        f"針對{cause_label if top_cause else '主要肇因'}加強宣導、攔查及違規取締。"
    )
    summary_short = (
        f"本期共{total:,.0f}件；首要路段{_short_label(road_label)}"
        f"{(top_road or {}).get('count', 0):,.0f}件；主要肇因"
        f"{_short_label(cause_label)}{(top_cause or {}).get('count', 0):,.0f}件。"
    )
    core_focus = (
        f"{_short_label(cause_label)}及"
        f"{_short_label((top_vehicle or {}).get('label', '主要車種'))}為本期優先關注項目。"
    )

    period_year = re.search(r"(\d{2,3})年", period)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "period": {
            "display": period,
            "short": _period_short(period),
            "year": period_year.group(1) if period_year else str(current_year or ""),
            "currentYear": current_year,
            "previousYear": previous_year,
            "hasComparison": previous_year is not None,
        },
        "overview": {
            "total": total,
            "a1": a1_total,
            "a2": a2_total,
            "previousTotal": previous_total if previous_year is not None else None,
            "previousA1": previous_a1 if previous_year is not None else None,
            "previousA2": previous_a2 if previous_year is not None else None,
            "changes": {
                "total": _change(total, previous_total, previous_year is not None),
                "a1": _change(a1_total, previous_a1, previous_year is not None),
                "a2": _change(a2_total, previous_a2, previous_year is not None),
            },
            "roadCategoryCount": len({dataset.text(row, "路段") for row in rows if dataset.text(row, "路段")}),
        },
        "rankings": rankings,
        "distributions": {
            "ageGroups": age_groups,
            "unknownAge": _clean_number(unknown_age),
            "timeBuckets": time_buckets,
            "rankedTimeBuckets": ranked_time_buckets,
            "unknownTime": _clean_number(unknown_time),
        },
        "a1Details": a1_details,
        "narrative": {
            "summary": summary,
            "summaryShort": summary_short,
            "enforcement": enforcement,
            "coreFocus": core_focus,
        },
        "source": {
            "sourceType": dataset.source_type,
            "rowMode": dataset.row_mode,
            "sheetName": dataset.sheet_name,
            "rowCount": len(dataset.rows),
            "selectedRowCount": len(rows),
            "totalCount": total,
            "warnings": list(dataset.warnings),
        },
    }
