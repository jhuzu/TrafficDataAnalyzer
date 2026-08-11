import unittest

from modules.accident_analysis import AccidentAnalysisService, transform_accident_source


HEADERS = [
    "事故類別",
    "發生年",
    "發生月",
    "發生日",
    "發生時間",
    "路段",
    "交叉路名",
    "肇事原因",
    "年齡",
    "當事者區分",
    "飲酒情形",
    "施用毒品情形",
    "唾液毒品檢測",
    "件數",
    "緯度",
    "經度",
]

ROWS = [
    ["A2", 115, 1, 5, "0830", "文化路", "民生路", "未依規定讓車", 25, "普通重型機車", "經檢測有酒精反應", "", "", 2, 25.01, 121.45],
    ["A1", 115, 2, 10, "1740", "民生路", "", "行人未依規定", None, "行人", "", "", "", 1, 25.02, 121.46],
    ["A2", 115, 2, 12, "1800", "文化路", "民生路", "未保持安全距離", 40, "自用小客車", "", "施用毒品", "", 3, 25.03, 121.47],
]


def dataset():
    return transform_accident_source({
        "headers": HEADERS,
        "rows": ROWS,
        "sourceType": "worksheet",
        "rowMode": "aggregated",
        "sheetName": "事故明細",
        "warnings": [],
    })


class AccidentTransformerTests(unittest.TestCase):
    def test_raw_source_gets_count_contract(self):
        transformed = transform_accident_source({
            "headers": ["事故類別", "路段"],
            "rows": [["A2", "文化路"], ["A1", "民生路"]],
            "sourceType": "worksheet",
            "rowMode": "raw",
        })
        self.assertEqual(transformed.headers[-1], "件數")
        self.assertEqual([row[-1] for row in transformed.rows], [1, 1])
        self.assertEqual(transformed.row_mode, "raw")

    def test_source_contract_round_trips_for_presentations(self):
        transformed = dataset()
        payload = transformed.to_source_dict()
        self.assertEqual(payload["headers"], HEADERS)
        self.assertEqual(payload["rows"], ROWS)
        self.assertEqual(payload["sourceType"], "worksheet")


class AccidentAnalysisServiceTests(unittest.TestCase):
    def setUp(self):
        self.service = AccidentAnalysisService(dataset())

    def test_basic_rankings_trend_and_narrative(self):
        result = self.service.analyze({"pattern": "all", "period": "month", "top": 20})
        self.assertEqual(result["metrics"][0]["value"], 6)
        self.assertEqual(result["metrics"][3]["value"], 3)
        self.assertEqual(result["road"][0], {"value": "文化路", "count": 5})
        self.assertEqual(result["intersection"][0], {"value": "文化路／民生路", "count": 5})
        self.assertEqual(result["time"][0], {"value": "18時", "count": 3})
        self.assertEqual(result["age"][0], {"value": "40歲", "count": 3})
        self.assertEqual(result["trend"], [
            {"value": "01月", "count": 2, "delta": None, "rate": None},
            {"value": "02月", "count": 4, "delta": 2, "rate": 1.0},
        ])
        self.assertIn("加總計6件", result["narrative"])

    def test_common_accident_patterns_use_same_count_semantics(self):
        cases = {"alcohol": 2, "drug": 3, "pedestrian": 1}
        for pattern, expected in cases.items():
            with self.subTest(pattern=pattern):
                result = self.service.analyze({"pattern": pattern, "period": "month", "top": 10})
                self.assertEqual(result["metrics"][0]["value"], expected)

    def test_raw_page_search_and_filters(self):
        searched = self.service.raw_page({"search": "A1", "page": 1, "pageSize": 20})
        self.assertEqual(searched["total"], 1)
        self.assertEqual(searched["rows"][0][0], "A1")
        filtered = self.service.raw_page({
            "filters": {"路段": ["文化路"]}, "page": 1, "pageSize": 20
        })
        self.assertEqual(filtered["total"], 2)

    def test_map_marker_aggregation(self):
        result = self.service.map_points({"pattern": "all"})
        self.assertEqual(result["total"], 3)
        self.assertEqual(result["coordField"], "經度/緯度")
        self.assertEqual(result["markers"][0]["label"], "文化路／民生路")
        self.assertEqual(result["markers"][0]["count"], 5)
        self.assertAlmostEqual(result["markers"][0]["lat"], 25.02)


if __name__ == "__main__":
    unittest.main()
