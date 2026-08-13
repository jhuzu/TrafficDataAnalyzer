"""All statistical and map analysis rules for traffic-accident data."""

from __future__ import annotations

import math
import re
from collections import defaultdict
from datetime import date
from typing import Any, Callable, Iterable

from ..data import AccidentDataset, BanqiaoRoadReference


PATTERN_LABELS = {
    "all": "全部資料",
    "alcohol": "酒駕相關",
    "drug": "毒駕相關",
    "pedestrian": "行人相關",
}

# This project currently analyzes Banqiao traffic data.  Coordinates outside
# this envelope are retained in the dataset, but are not trusted for map plots.
BANQIAO_MAP_BOUNDS = (24.97, 25.04, 121.42, 121.49)


def _clean_number(value: float) -> int | float:
    return int(value) if value.is_integer() else round(value, 2)


def _age_label(value: Any) -> str:
    try:
        return f"{int(float(value))}歲"
    except (ValueError, TypeError):
        return "年齡不詳"


def _twd97_to_wgs84(x: float, y: float) -> tuple[float, float]:
    a = 6378137.0
    f = 1.0 / 298.257222101
    lng0 = math.radians(121.0)
    k0 = 0.9999
    dx = 250000.0
    b = a * (1 - f)
    e2 = (a ** 2 - b ** 2) / a ** 2
    e12 = (a ** 2 - b ** 2) / b ** 2
    x -= dx
    m_value = y / k0
    mu = m_value / (a * (1 - e2 / 4 - 3 * e2 ** 2 / 64 - 5 * e2 ** 3 / 256))
    e1 = (1 - math.sqrt(1 - e2)) / (1 + math.sqrt(1 - e2))
    j1 = 3 * e1 / 2 - 27 * e1 ** 3 / 32
    j2 = 21 * e1 ** 2 / 16 - 55 * e1 ** 4 / 32
    j3 = 151 * e1 ** 3 / 96
    j4 = 1097 * e1 ** 4 / 512
    fp = mu + j1 * math.sin(2 * mu) + j2 * math.sin(4 * mu) + j3 * math.sin(6 * mu) + j4 * math.sin(8 * mu)
    c1 = e12 * math.cos(fp) ** 2
    t1 = math.tan(fp) ** 2
    r1 = a * (1 - e2) / (1 - e2 * math.sin(fp) ** 2) ** 1.5
    n1 = a / math.sqrt(1 - e2 * math.sin(fp) ** 2)
    d_value = x / (n1 * k0)
    q1 = n1 * math.tan(fp) / r1
    q2 = d_value ** 2 / 2
    q3 = (5 + 3 * t1 + 10 * c1 - 4 * c1 ** 2 - 9 * e12) * d_value ** 4 / 24
    q4 = (61 + 90 * t1 + 298 * c1 + 45 * t1 ** 2 - 3 * c1 ** 2 - 252 * e12) * d_value ** 6 / 720
    lat = fp - q1 * (q2 - q3 + q4)
    q5 = d_value
    q6 = (1 + 2 * t1 + c1) * d_value ** 3 / 6
    q7 = (5 - 2 * c1 + 28 * t1 - 3 * c1 ** 2 + 8 * e12 + 24 * t1 ** 2) * d_value ** 5 / 120
    lng = lng0 + (q5 - q6 + q7) / math.cos(fp)
    return math.degrees(lat), math.degrees(lng)


def _parse_coordinate(raw_lat: Any, raw_lng: Any) -> tuple[float | None, float | None]:
    lat_value, lng_value = float(raw_lat), float(raw_lng)
    if lat_value == 0 or lng_value == 0:
        return None, None
    if lng_value > 100000 or lat_value > 100000:
        return _twd97_to_wgs84(lng_value, lat_value)
    return lat_value, lng_value


def _is_banqiao_coordinate(lat: float, lng: float) -> bool:
    min_lat, max_lat, min_lng, max_lng = BANQIAO_MAP_BOUNDS
    return min_lat <= lat <= max_lat and min_lng <= lng <= max_lng


class AccidentAnalysisService:
    """Query and aggregate one immutable accident dataset."""

    def __init__(self, dataset: AccidentDataset, road_reference: BanqiaoRoadReference | None = None):
        self.dataset = dataset
        self.road_reference = road_reference or BanqiaoRoadReference()

    def _event_date(self, row: tuple[Any, ...]) -> date | None:
        try:
            year = int(float(self.dataset.text(row, "發生年")))
            month = int(float(self.dataset.text(row, "發生月")))
            day = int(float(self.dataset.text(row, "發生日")))
            return date(year + 1911 if year < 1911 else year, month, day)
        except (TypeError, ValueError):
            return None

    def _date_range(self, options: dict[str, Any]) -> tuple[date | None, date | None]:
        try:
            start = date.fromisoformat(str(options["startDate"])) if options.get("startDate") else None
            end = date.fromisoformat(str(options["endDate"])) if options.get("endDate") else None
        except ValueError as exc:
            raise ValueError("起訖日格式錯誤，請使用 YYYY-MM-DD。") from exc
        if start and end and start > end:
            raise ValueError("起日不可晚於迄日。")
        if (start or end) and any(self.dataset.position(field) is None for field in ("發生年", "發生月", "發生日")):
            raise ValueError("來源資料缺少「發生年／發生月／發生日」，無法依起訖日篩選。")
        return start, end

    def _filter_rows(self, options: dict[str, Any]) -> list[tuple[Any, ...]]:
        pattern = str(options.get("pattern", "all"))
        custom = str(options.get("custom", "")).strip()
        start_date, end_date = self._date_range(options)
        output = []
        for row in self.dataset.rows:
            event_date = self._event_date(row) if start_date or end_date else None
            if (start_date and (event_date is None or event_date < start_date)) or (
                end_date and (event_date is None or event_date > end_date)
            ):
                continue
            cause = self.dataset.text(row, "肇事原因")
            vehicle = self.dataset.text(row, "當事者區分")
            drink = self.dataset.text(row, "飲酒情形")
            drug = self.dataset.text(row, "施用毒品情形") + self.dataset.text(row, "唾液毒品檢測")
            blob = " ".join((cause, vehicle, drink, drug))
            matches = (
                pattern == "all"
                or (pattern == "alcohol" and ("酒" in blob or "飲酒" in blob))
                or (pattern == "drug" and ("毒" in blob or "違禁物" in blob))
                or (pattern == "pedestrian" and "行人" in blob)
            )
            if matches and (not custom or custom in blob):
                output.append(row)
        return output

    def _aggregate(
        self,
        rows: Iterable[tuple[Any, ...]],
        key: Callable[[tuple[Any, ...]], str],
        top: int,
    ) -> list[dict[str, Any]]:
        totals: dict[str, float] = defaultdict(float)
        for row in rows:
            label = key(row)
            if label:
                totals[label] += self.dataset.number(row, "件數")
        return [
            {"value": label, "count": _clean_number(count)}
            for label, count in sorted(totals.items(), key=lambda item: (-item[1], item[0]))[:top]
        ]

    def _aggregate_field(
        self, rows: Iterable[tuple[Any, ...]], field: str, top: int
    ) -> list[dict[str, Any]]:
        if self.dataset.position(field) is None:
            return []
        return self._aggregate(rows, lambda row: self.dataset.text(row, field), top)

    def _trend(
        self, rows: Iterable[tuple[Any, ...]], period: str
    ) -> list[dict[str, Any]]:
        totals: dict[str, float] = defaultdict(float)
        for row in rows:
            try:
                month = int(self.dataset.text(row, "發生月"))
            except (ValueError, TypeError):
                continue
            if period == "week":
                try:
                    year = (
                        int(self.dataset.text(row, "發生年")) + 1911
                        if self.dataset.position("發生年") is not None
                        else 2026
                    )
                    day = (
                        int(self.dataset.text(row, "發生日"))
                        if self.dataset.position("發生日") is not None
                        else 1
                    )
                    key = f"{month:02d}月第{date(year, month, day).isocalendar().week}週"
                except (ValueError, TypeError):
                    continue
            else:
                key = f"{month:02d}月" if period == "month" else f"第{(month - 1) // 3 + 1}季"
            totals[key] += self.dataset.number(row, "件數")
        order = sorted(totals, key=lambda value: tuple(int(number) for number in re.findall(r"\d+", value)))
        output = []
        previous = None
        for key in order:
            value = _clean_number(totals[key])
            delta = None if previous is None else value - previous
            rate = None if previous in (None, 0) else (value - previous) / previous
            output.append({"value": key, "count": value, "delta": delta, "rate": rate})
            previous = value
        return output

    @staticmethod
    def _prior_year(day: date) -> date:
        """Keep a same-period comparison valid when the prior year is not leap."""
        try:
            return day.replace(year=day.year - 1)
        except ValueError:
            return day.replace(year=day.year - 1, day=28)

    def _year_comparison(self, options: dict[str, Any], total: int | float) -> dict[str, Any] | None:
        start_date, end_date = self._date_range(options)
        if not start_date or not end_date:
            return None
        previous_options = dict(options)
        previous_start = self._prior_year(start_date)
        previous_end = self._prior_year(end_date)
        previous_options.update(startDate=previous_start.isoformat(), endDate=previous_end.isoformat())
        previous_total = _clean_number(self.dataset.total(self._filter_rows(previous_options)))
        difference = _clean_number(float(total) - float(previous_total))
        return {
            "previousPeriod": f"{previous_start.isoformat()} 至 {previous_end.isoformat()}",
            "previousTotal": previous_total,
            "difference": difference,
            "rate": None if previous_total == 0 else (float(total) - float(previous_total)) / float(previous_total),
        }

    def analyze(self, options: dict[str, Any]) -> dict[str, Any]:
        rows = self._filter_rows(options)
        if self.dataset.position("件數") is None:
            raise ValueError("來源資料沒有「件數」欄位。")
        top = int(options.get("top", 20))
        total = _clean_number(self.dataset.total(rows))
        road = self._aggregate_field(rows, "路段", top)
        intersection = self._aggregate(
            rows,
            lambda row: (
                f"{self.dataset.text(row, '路段')}／{self.dataset.text(row, '交叉路名')}"
                if self.dataset.text(row, "路段") and self.dataset.text(row, "交叉路名")
                else ""
            ),
            top,
        ) if self.dataset.position("路段") is not None else []
        time_data = self._aggregate(
            rows,
            lambda row: (
                f"{self.dataset.text(row, '發生時間')[:2]}時"
                if self.dataset.text(row, "發生時間")[:2].isdigit()
                else "時間不詳"
            ),
            top,
        ) if self.dataset.position("發生時間") is not None else []
        age = self._aggregate(
            rows,
            lambda row: _age_label(row[self.dataset.position("年齡")]),
            top,
        ) if self.dataset.position("年齡") is not None else []
        cause = self._aggregate_field(rows, "肇事原因", top)
        vehicle = self._aggregate_field(rows, "當事者區分", top)
        trend = self._trend(rows, str(options.get("period", "month")))
        label = PATTERN_LABELS.get(options.get("pattern"), "自訂條件")
        start_date, end_date = self._date_range(options)
        date_rule = (
            f"；發生日期：{start_date.isoformat() if start_date else '不限'}至{end_date.isoformat() if end_date else '不限'}"
            if start_date or end_date else ""
        )

        narrative = f"本轄目前資料{label}{date_rule}，依Excel「件數」欄加總計{total:,}件。"
        if road:
            narrative += f"易肇事路段以{road[0]['value']}計{road[0]['count']:,}件最多；"
        if cause:
            narrative += f"主要肇事原因為{cause[0]['value']}計{cause[0]['count']:,}件；"
        if age:
            narrative += f"年齡層以{age[0]['value']}計{age[0]['count']:,}件最多；"
        if vehicle:
            narrative += f"車種以{vehicle[0]['value']}計{vehicle[0]['count']:,}件為大宗。"

        return {
            "metrics": [
                {"label": "符合條件件數", "value": total},
                {"label": "路段類別數", "value": len(road)},
                {"label": "肇因類別數", "value": len(cause)},
                {"label": "資料列數", "value": len(rows)},
            ],
            "rule": f"目前篩選：{label}{date_rule}；統計單位：Excel「件數」加總。",
            "narrative": narrative,
            "road": road,
            "intersection": intersection,
            "time": time_data,
            "cause": cause,
            "age": age,
            "vehicle": vehicle,
            "trend": trend,
            "yearComparison": self._year_comparison(options, total),
        }

    def raw_page(self, options: dict[str, Any]) -> dict[str, Any]:
        query = str(options.get("search", "")).strip().lower()
        page = max(1, int(options.get("page", 1)))
        page_size = min(200, max(10, int(options.get("pageSize", 50))))
        source = list(self.dataset.rows)
        filters = options.get("filters") or {}
        if filters:
            source = [
                row
                for row in source
                if all(
                    not allowed or self.dataset.text(row, field) in allowed
                    for field, allowed in filters.items()
                    if self.dataset.position(field) is not None
                )
            ]
        if query:
            source = [
                row
                for row in source
                if query in " ".join("" if value is None else str(value) for value in row).lower()
            ]
        total = len(source)
        start = (page - 1) * page_size
        return {
            "headers": list(self.dataset.headers),
            "rows": [list(row) for row in source[start : start + page_size]],
            "total": total,
            "page": page,
            "pageSize": page_size,
        }

    def map_points(self, options: dict[str, Any]) -> dict[str, Any]:
        lat_field = next(
            (name for name in ("緯度", "GPS緯度", "Y座標", "Y", "lat", "latitude") if self.dataset.position(name) is not None),
            None,
        )
        lng_field = next(
            (name for name in ("經度", "GPS經度", "X座標", "X", "lng", "longitude") if self.dataset.position(name) is not None),
            None,
        )
        if not lat_field or not lng_field:
            raise ValueError(
                "資料中找不到經緯度欄位。需要「經度」+「緯度」"
                "（或「GPS經度」+「GPS緯度」或「X座標」+「Y座標」）。"
            )
        rows = self._filter_rows(options)
        coordinate_count = 0
        coordinate_lat_sum = 0.0
        coordinate_lng_sum = 0.0
        parsed_rows: list[tuple[tuple[Any, ...], float | None, float | None]] = []
        coordinate_roads: dict[tuple[float, float], set[str]] = defaultdict(set)
        for row in rows:
            try:
                lat, lng = _parse_coordinate(
                    self.dataset.text(row, lat_field), self.dataset.text(row, lng_field)
                )
            except (ValueError, TypeError, IndexError):
                continue
            if lat is not None and lng is not None and _is_banqiao_coordinate(lat, lng):
                coordinate_roads[(round(lat, 5), round(lng, 5))].add(self.dataset.text(row, "路段"))

        def is_trusted_coordinate(lat: float | None, lng: float | None) -> bool:
            if lat is None or lng is None or not _is_banqiao_coordinate(lat, lng):
                return False
            # A coordinate shared by many unrelated road names is a known
            # source-data failure, not a genuine multi-road intersection.
            return len(coordinate_roads[(round(lat, 5), round(lng, 5))]) <= 2

        exact_references: dict[tuple[str, str], list[tuple[float, float]]] = defaultdict(list)
        road_references: dict[str, list[tuple[float, float]]] = defaultdict(list)
        for row in rows:
            try:
                lat, lng = _parse_coordinate(
                    self.dataset.text(row, lat_field), self.dataset.text(row, lng_field)
                )
            except (ValueError, TypeError, IndexError):
                lat, lng = None, None
            parsed_rows.append((row, lat, lng))
            if is_trusted_coordinate(lat, lng):
                road = self.dataset.text(row, "路段")
                intersection = self.dataset.text(row, "交叉路名")
                if road:
                    exact_references[(road, intersection)].append((lat, lng))
                    road_references[road].append((lat, lng))

        repaired_count = 0
        referenced_count = 0
        unlocated_count = 0
        suspicious_count = 0
        unlocated_records: list[dict[str, str]] = []
        grouped: dict[tuple[float, float], dict[str, Any]] = defaultdict(
            lambda: {"count": 0.0, "labels": []}
        )
        for row, lat, lng in parsed_rows:
            road = self.dataset.text(row, "路段")
            intersection = self.dataset.text(row, "交叉路名")
            reference = self.road_reference.lookup(road, intersection)
            coordinate_source = reference.source if reference else "Excel X/Y"
            if reference:
                lat, lng = reference.lat, reference.lng
                referenced_count += 1
            if not is_trusted_coordinate(lat, lng):
                if lat is not None and lng is not None and _is_banqiao_coordinate(lat, lng):
                    suspicious_count += 1
                references = exact_references.get((road, intersection)) or road_references.get(road)
                if not references:
                    unlocated_count += 1
                    unlocated_records.append({
                        "caseNumber": self.dataset.text(row, "受理案號") or "未提供",
                        "road": road or "未提供",
                        "intersection": intersection or "未提供",
                    })
                    continue
                lat = sum(point[0] for point in references) / len(references)
                lng = sum(point[1] for point in references) / len(references)
                repaired_count += 1
            count = self.dataset.number(row, "件數")
            coordinate_count += 1
            coordinate_lat_sum += lat
            coordinate_lng_sum += lng
            label = "／".join(
                value
                for value in (
                    self.dataset.text(row, "路段"),
                    self.dataset.text(row, "交叉路名"),
                )
                if value
            ) or "未知路段"
            # Aggregate only matching coordinate cells.  Averaging every
            # incident with the same road name can move a long road's marker
            # somewhere that is not on the road.
            coordinate_key = (round(lat, 5), round(lng, 5))
            info = grouped[coordinate_key]
            info["count"] += count
            if label not in info["labels"]:
                info["labels"].append(label)
            info.setdefault("sources", set()).add(coordinate_source)
        markers = []
        for (lat, lng), info in sorted(grouped.items(), key=lambda item: -item[1]["count"]):
            markers.append({
                "lat": lat,
                "lng": lng,
                "count": int(info["count"]),
                "label": "、".join(info["labels"][:3]),
                "source": "、".join(sorted(info["sources"])),
            })
        center = (
            [coordinate_lat_sum / coordinate_count, coordinate_lng_sum / coordinate_count]
            if coordinate_count
            else [25.0118, 121.4590]
        )
        return {
            "markers": markers,
            "center": center,
            "total": coordinate_count,
            "coordField": f"{lng_field}/{lat_field}",
            "repaired": repaired_count,
            "referenced": referenced_count,
            "unlocated": unlocated_count,
            "unlocatedRecords": unlocated_records,
            "suspicious": suspicious_count,
        }
