"""Classification, trends, and rankings for normalized violation datasets."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable

from ..data.schema import ViolationDataset, ViolationRecord
from .rules import MAJOR_VIOLATION_RULES, PEDESTRIAN_RIGHTS_RULES, CategoryRule


def _number(value: float | int) -> int | float:
    """Return JSON-friendly counts on Python versions where ``int`` lacks is_integer."""
    numeric = float(value)
    return int(numeric) if numeric.is_integer() else round(numeric, 2)


def _period_key(record: ViolationRecord, period: str) -> str | None:
    if record.roc_year is None or record.month is None:
        return None
    if period == "quarter":
        return f"{record.roc_year}年第{(record.month - 1) // 3 + 1}季"
    return f"{record.roc_year}年{record.month:02d}月"


class MajorViolationAnalysisService:
    """Apply versioned policy rules without changing the normalized source data."""

    def __init__(self, dataset: ViolationDataset):
        self.dataset = dataset

    def records_for_period(self, start_date: str | None = None, end_date: str | None = None) -> list[ViolationRecord]:
        if start_date and end_date and start_date > end_date:
            raise ValueError("起日不可晚於迄日。")
        return [
            record for record in self.dataset.records
            if record.violation_date
            and (not start_date or record.violation_date >= start_date)
            and (not end_date or record.violation_date <= end_date)
        ]

    @staticmethod
    def _matches(records: Iterable[ViolationRecord], rule: CategoryRule) -> list[ViolationRecord]:
        return [record for record in records if rule.matches(record)]

    @staticmethod
    def _ranking(records: Iterable[ViolationRecord], field: str, top: int) -> list[dict[str, Any]]:
        totals: dict[str, float] = defaultdict(float)
        for record in records:
            raw_value = getattr(record, field)
            label = (
                f"{raw_value:02d}時" if field == "hour" and isinstance(raw_value, int)
                else str(raw_value or "").strip()
            )
            if label:
                totals[label] += record.count
        return [
            {"value": value, "count": _number(count)}
            for value, count in sorted(totals.items(), key=lambda item: (-item[1], item[0]))[:top]
        ]

    @staticmethod
    def _trend(records: Iterable[ViolationRecord], period: str) -> list[dict[str, Any]]:
        totals: dict[str, float] = defaultdict(float)
        for record in records:
            key = _period_key(record, period)
            if key:
                totals[key] += record.count
        ordered = sorted(totals, key=lambda key: tuple(int(part) for part in key.replace("第", "").replace("年", " ").replace("月", "").replace("季", "").split()))
        previous: float | None = None
        result = []
        for key in ordered:
            count = totals[key]
            result.append({
                "value": key,
                "count": _number(count),
                "delta": None if previous is None else _number(count - previous),
                "rate": None if previous in (None, 0) else round((count - previous) / previous, 4),
            })
            previous = count
        return result

    def _category(self, records: list[ViolationRecord], rule: CategoryRule, *, top: int, period: str) -> dict[str, Any]:
        matched = self._matches(records, rule) if rule.available else []
        return {
            "key": rule.key,
            "label": rule.label,
            "available": rule.available,
            "basis": rule.basis,
            "rowCount": len(matched),
            "count": _number(sum(record.count for record in matched)),
            "road": self._ranking(matched, "road", top),
            "district": self._ranking(matched, "district", top),
            "hour": self._ranking(matched, "hour", top),
            "trend": self._trend(matched, period),
        }

    def analyze(self, options: dict[str, Any] | None = None) -> dict[str, Any]:
        options = options or {}
        top = min(100, max(1, int(options.get("top", 20))))
        period = str(options.get("period", "month"))
        if period not in {"month", "quarter"}:
            raise ValueError("趨勢期間僅支援 month 或 quarter。")
        records = self.records_for_period(options.get("startDate"), options.get("endDate"))
        major = [self._category(records, rule, top=top, period=period) for rule in MAJOR_VIOLATION_RULES]
        pedestrian = [self._category(records, rule, top=top, period=period) for rule in PEDESTRIAN_RIGHTS_RULES]
        available_major = [item for item in major if item["available"]]
        return {
            "period": {"start": options.get("startDate"), "end": options.get("endDate")},
            "ruleVersion": "2026-08-11",
            "rule": "以標準化法條欄位套用嚴格口徑；第44條同時列入重大違規與行人路權，兩組總計不可相加。",
            "metrics": {
                "periodRows": len(records),
                "periodCount": _number(sum(record.count for record in records)),
                "majorAvailableCategories": len(available_major),
                "majorTotal": _number(sum(item["count"] for item in available_major)),
                "pedestrianTotal": _number(sum(item["count"] for item in pedestrian)),
            },
            "major": major,
            "pedestrian": pedestrian,
            "allRoad": self._ranking(records, "road", top),
            "allHour": self._ranking(records, "hour", top),
            "unclassified": {
                "rowCount": len([record for record in records if not any(rule.matches(record) for rule in MAJOR_VIOLATION_RULES if rule.available) and not any(rule.matches(record) for rule in PEDESTRIAN_RIGHTS_RULES)]),
                "note": "未分類不代表無違規；僅表示未落入目前九大重大違規或五大行人路權嚴格口徑。",
            },
        }
