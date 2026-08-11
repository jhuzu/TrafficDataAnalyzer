import tempfile
import unittest
from pathlib import Path

from modules.major_violation import (
    load_violation_workbooks,
    merge_violation_datasets,
    transform_violation_source,
)
from tests.test_excel_sources import make_workbook


class ViolationTransformerTests(unittest.TestCase):
    def test_actual_column_aliases_and_roc_values_are_normalized(self):
        dataset = transform_violation_source({
            "headers": [
                "舉發單號", "違規日期", "違規時間", "違規條款", "違規條款2",
                "違規行政區1", "違規路段1", "違規路段1備註", "舉發單位",
                "舉發類型", "簡式車種", "車種", "酒測值", "是否作廢", "車號",
            ],
            "rows": [[
                "P3315778", 1150105, 812,
                "<331090040> 33條1項09款004目 行駛快速公路違規使用路肩",
                "補充條款", "板橋區", "臺65線", "北向", "板橋分局交通分隊",
                "逕舉-民眾檢舉", "重型機車", "大型重型機車", "0.00", "否", "ABC-123",
            ]],
            "sourceType": "worksheet",
            "rowMode": "raw",
            "sheetName": "工作表1",
        }, source_name="33條.xlsx")

        record = dataset.records[0]
        self.assertEqual(record.violation_date, "2026-01-05")
        self.assertEqual((record.roc_year, record.month, record.day), (115, 1, 5))
        self.assertEqual((record.violation_time, record.hour), ("08:12:00", 8))
        self.assertEqual(
            (record.law_article, record.law_paragraph, record.law_clause, record.law_item),
            ("33", "1", "9", "4"),
        )
        self.assertEqual(record.road, "臺65線")
        self.assertEqual(record.secondary_law_text, "補充條款")
        self.assertIn(("車號", "ABC-123"), record.extra_fields)

    def test_invalid_values_are_retained_as_empty_with_source_warnings(self):
        dataset = transform_violation_source({
            "headers": ["違規日期", "違規時間", "違規條款", "違規路段1"],
            "rows": [["不是日期", "25:99", "45條1項3款", "館前西路"]],
        })
        record = dataset.records[0]
        self.assertIsNone(record.violation_date)
        self.assertIsNone(record.violation_time)
        self.assertEqual(record.count, 1)
        self.assertTrue(any("違規日期無法標準化" in item for item in dataset.warnings))
        self.assertTrue(any("違規時間無法標準化" in item for item in dataset.warnings))

    def test_merge_preserves_duplicates_and_reports_no_deduplication(self):
        source = {
            "headers": ["舉發單號", "違規日期", "違規條款", "違規路段1"],
            "rows": [["P1", 1150101, "45條1項1款", "文化路"]],
        }
        first = transform_violation_source(source, source_name="a.xlsx", source_id="source-1")
        second = transform_violation_source(source, source_name="b.xlsx", source_id="source-2")
        merged = merge_violation_datasets([first, second])
        self.assertEqual(merged.raw_row_count, 2)
        self.assertEqual(merged.deduplication_status, "not_applied")
        self.assertTrue(merged.deduplication_available)
        self.assertTrue(any("尚未跨檔去重" in item for item in merged.warnings))


class ViolationWorkbookLoaderTests(unittest.TestCase):
    def test_multiple_workbooks_keep_source_identity_and_failures(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            valid = root / "valid.xlsx"
            invalid = root / "invalid.xls"
            make_workbook(valid, [("資料", [
                ["舉發單號", "違規日期", "違規時間", "違規條款", "違規路段1"],
                ["P1", 1150101, 1730, "53條1項", "縣民大道1段"],
            ])])
            invalid.write_bytes(b"legacy")
            dataset = load_violation_workbooks([valid, invalid])

        self.assertEqual(dataset.raw_row_count, 1)
        self.assertEqual(dataset.records[0].source_file, "valid.xlsx")
        self.assertEqual(dataset.sources[0].status, "loaded")
        self.assertEqual(dataset.sources[1].status, "failed")
        self.assertIn("另存為 .xlsx 或 .xlsm", dataset.sources[1].warnings[0])


if __name__ == "__main__":
    unittest.main()
