import unittest

from modules.major_violation import MajorViolationAnalysisService, transform_violation_source
from modules.major_violation.analysis.service import _number


class MajorViolationAnalysisTests(unittest.TestCase):
    def test_integer_zero_count_is_supported(self):
        self.assertEqual(_number(0), 0)

    def test_strict_rules_classify_and_keep_cross_group_overlap_explicit(self):
        dataset = transform_violation_source({
            "headers": ["違規日期", "違規時間", "違規條款", "違規路段1"],
            "rows": [
                [1150101, 1700, "35條1項 酒後駕車", "文化路"],
                [1150102, 900, "53條1項 闖紅燈", "中山路"],
                [1150103, 800, "33條1項9款 行駛路肩", "臺65線"],
                [1150104, 800, "33條1項3款 大型車未依規定行駛外側車道", "臺65線"],
                [1150105, 1100, "45條1項3款 逆向行駛", "館前西路"],
                [1150106, 1200, "48條2款 轉彎未依規定", "南雅南路"],
                [1150107, 1300, "44條2項 不暫停讓行人", "重慶路"],
                [1150108, 1400, "45條1項18款 非號誌路口停讓", "府中路"],
                [1150109, 1500, "78條1項 行人違規", "四川路"],
                [1150110, 1600, "82條1項 道路障礙", "中山路"],
                [1150111, 1800, "56條1項 人行道停車", "忠孝路"],
                [1150112, 1900, "33條1項3款 大型重機同車道併駛", "臺65線"],
            ],
        })

        result = MajorViolationAnalysisService(dataset).analyze({
            "startDate": "2026-01-01", "endDate": "2026-01-31",
        })
        major = {item["key"]: item for item in result["major"]}
        pedestrian = {item["key"]: item for item in result["pedestrian"]}

        self.assertEqual(result["metrics"]["periodCount"], 12)
        self.assertEqual(result["metrics"]["majorTotal"], 7)
        self.assertEqual(result["metrics"]["pedestrianTotal"], 5)
        self.assertEqual(major["outer_lane"]["count"], 1)
        self.assertEqual(major["serious_speeding"]["available"], False)
        self.assertEqual(major["yield_pedestrian"]["count"], 1)
        self.assertEqual(pedestrian["yield_pedestrian"]["count"], 1)
        self.assertEqual(result["allHour"][0], {"value": "08時", "count": 2})
        self.assertEqual(result["unclassified"]["rowCount"], 1)

    def test_invalid_analysis_options_are_rejected(self):
        dataset = transform_violation_source({
            "headers": ["違規日期", "違規條款"],
            "rows": [[1150101, "35條"]],
        })
        service = MajorViolationAnalysisService(dataset)
        with self.assertRaisesRegex(ValueError, "起日"):
            service.analyze({"startDate": "2026-02-01", "endDate": "2026-01-01"})
        with self.assertRaisesRegex(ValueError, "趨勢期間"):
            service.analyze({"period": "week"})



if __name__ == "__main__":
    unittest.main()
