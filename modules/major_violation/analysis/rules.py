"""Auditable legal-basis rules for major-violation performance reporting."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from ..data.schema import ViolationRecord


@dataclass(frozen=True)
class CategoryRule:
    """One policy category and the predicate used to include a record."""

    key: str
    label: str
    group: str
    basis: str
    available: bool
    matches: Callable[[ViolationRecord], bool]


def _law(record: ViolationRecord, article: str, paragraph: str = "", clause: str = "") -> bool:
    return (
        record.law_article == article
        and (not paragraph or record.law_paragraph == paragraph)
        and (not clause or record.law_clause == clause)
    )


def _outer_lane(record: ViolationRecord) -> bool:
    text = " ".join((record.law_text, record.secondary_law_text, record.description))
    return _law(record, "33", "1", "3") and any(word in text for word in ("外側車道", "慢速", "大型車"))


MAJOR_VIOLATION_RULES = (
    CategoryRule("alcohol", "酒後駕車", "major", "道路交通管理處罰條例第35條", True,
                 lambda record: _law(record, "35")),
    CategoryRule("red_light", "闖紅燈", "major", "道路交通管理處罰條例第53條第1項", True,
                 lambda record: _law(record, "53", "1")),
    CategoryRule("serious_speeding", "嚴重超速", "major", "尚未提供可核對來源資料", False,
                 lambda record: False),
    CategoryRule("shoulder", "行駛路肩", "major", "道路交通管理處罰條例第33條第1項第9款", True,
                 lambda record: _law(record, "33", "1", "9")),
    CategoryRule("outer_lane", "大型／慢速車未依外側車道", "major",
                 "道路交通管理處罰條例第33條第1項第3款，且條文含外側車道、慢速或大型車", True,
                 _outer_lane),
    CategoryRule("reckless_driving", "蛇行／惡意逼車", "major", "尚未提供可核對來源資料", False,
                 lambda record: False),
    CategoryRule("wrong_way", "逆向行駛", "major", "道路交通管理處罰條例第45條第1項第1、3款", True,
                 lambda record: _law(record, "45", "1", "1") or _law(record, "45", "1", "3")),
    CategoryRule("turning", "轉彎未依規定", "major", "道路交通管理處罰條例第48條", True,
                 lambda record: _law(record, "48")),
    CategoryRule("yield_pedestrian", "汽機車不暫停讓行人", "major", "道路交通管理處罰條例第44條", True,
                 lambda record: _law(record, "44")),
)

PEDESTRIAN_RIGHTS_RULES = (
    CategoryRule("yield_pedestrian", "路口不停讓行人", "pedestrian", "道路交通管理處罰條例第44條", True,
                 lambda record: _law(record, "44")),
    CategoryRule("non_signal_yield", "非號誌路口停讓", "pedestrian", "道路交通管理處罰條例第45條第1項第18款", True,
                 lambda record: _law(record, "45", "1", "18")),
    CategoryRule("pedestrian_violation", "行人違規", "pedestrian", "道路交通管理處罰條例第78條", True,
                 lambda record: _law(record, "78")),
    CategoryRule("road_obstruction", "道路障礙", "pedestrian", "道路交通管理處罰條例第82條", True,
                 lambda record: _law(record, "82")),
    CategoryRule("sidewalk_parking", "人行道／騎樓停車", "pedestrian", "道路交通管理處罰條例第55、56條", True,
                 lambda record: _law(record, "55") or _law(record, "56")),
)

ALL_CATEGORY_RULES = MAJOR_VIOLATION_RULES + PEDESTRIAN_RIGHTS_RULES
