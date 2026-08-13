"""Offline Banqiao road and intersection coordinate lookups."""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


def normalize_road_name(value: str) -> str:
    value = "".join(str(value or "").replace("板橋區", "").replace("臺", "台").split())
    for chinese, arabic in (("一段", "1段"), ("二段", "2段"), ("三段", "3段"), ("四段", "4段"), ("五段", "5段")):
        value = value.replace(chinese, arabic)
    return value


@dataclass(frozen=True)
class RoadReference:
    lat: float
    lng: float
    source: str


class BanqiaoRoadReference:
    """Read-only lookup index from the bundled Banqiao road database."""

    def __init__(self, database_path: Path | None = None):
        self.database_path = database_path or Path(__file__).with_name("banqiao_roads.db")
        self.by_road: dict[str, list[tuple[float, float]]] = defaultdict(list)
        self.by_pair: dict[tuple[str, str], list[tuple[float, float]]] = defaultdict(list)
        if self.database_path.is_file():
            self._load()

    def _load(self) -> None:
        connection = sqlite3.connect(f"file:{self.database_path}?mode=ro", uri=True)
        try:
            rows = connection.execute(
                """SELECT i.lat, i.lon, ir.road_name
                   FROM intersections AS i
                   JOIN intersection_roads AS ir ON ir.intersection_id = i.id"""
            ).fetchall()
        finally:
            connection.close()
        roads_by_point: dict[tuple[float, float], list[str]] = defaultdict(list)
        for lat, lng, name in rows:
            normalized = normalize_road_name(name)
            if normalized:
                self.by_road[normalized].append((lat, lng))
                roads_by_point[(lat, lng)].append(normalized)
        for point, roads in roads_by_point.items():
            for road in roads:
                for cross in roads:
                    if road != cross:
                        self.by_pair[(road, cross)].append(point)

    @staticmethod
    def _average(points: list[tuple[float, float]], source: str) -> RoadReference | None:
        if not points:
            return None
        return RoadReference(sum(lat for lat, _ in points) / len(points), sum(lng for _, lng in points) / len(points), source)

    def lookup(self, road: str, intersection: str) -> RoadReference | None:
        normalized_road = normalize_road_name(road)
        normalized_cross = normalize_road_name(intersection)
        if normalized_road and normalized_cross:
            match = self._average(self.by_pair.get((normalized_road, normalized_cross), []), "路段／路口對照")
            if match:
                return match
        return self._average(self.by_road.get(normalized_road, []), "路段代表點")
