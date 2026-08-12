import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from openpyxl import load_workbook
from pptx import Presentation

from build_xlsx import build_workbook
from core.session_store import InMemorySessionStore
from modules.accident_analysis.presentation import AccidentPresentationService
from tests.test_accident_analysis import dataset
from web_server import content_disposition, parse_uploads, recover_major_violations
from tests.test_excel_sources import make_workbook


class SessionStoreTests(unittest.TestCase):
    def test_expiry_refresh_and_capacity_are_enforced(self):
        now = [100.0]
        store = InMemorySessionStore(ttl_seconds=10, max_sessions=1, clock=lambda: now[0])
        first = store.create({"name": "first"})
        now[0] = 105.0
        self.assertEqual(store.get(first)["name"], "first")
        now[0] = 106.0
        second = store.create({"name": "second"})
        self.assertIsNone(store.get(first))
        self.assertEqual(store.get(second)["name"], "second")
        now[0] = 117.0
        self.assertIsNone(store.get(second))


class RuntimeTests(unittest.TestCase):
    def test_multipart_upload_keeps_chinese_filename_and_binary_xlsx_bytes(self):
        boundary = b"----traffic-boundary"
        payload = b"PK\x03\x04\xe0\xffbinary"
        raw = b"\r\n".join((
            b"--" + boundary,
            'Content-Disposition: form-data; name="target"; filename="115年績效.xlsx"'.encode(),
            b"Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            b"",
            payload,
            b"--" + boundary + b"--",
            b"",
        ))
        handler = type("Handler", (), {"headers": {"Content-Length": str(len(raw)), "Content-Type": f"multipart/form-data; boundary={boundary.decode()}"}, "rfile": BytesIO(raw)})()
        upload = parse_uploads(handler, field_names={"target"})[0]
        self.assertEqual(upload.filename, "115年績效.xlsx")
        self.assertEqual(upload.file.read(), payload)

    def test_chinese_download_filename_uses_utf8_header(self):
        header = content_disposition("交通事故分析週報_新式版本.pptx")
        self.assertIn("filename=download.pptx", header)
        self.assertIn("filename*=UTF-8''", header)
        self.assertIn("%E4%BA%A4%E9%80%9A", header)

    def test_major_violation_batch_keeps_original_filenames(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "第35條.xlsx"
            second = root / "第53條.xlsx"
            make_workbook(first, [("資料", [["違規日期", "違規條款"], [1150101, "35條"]])])
            make_workbook(second, [("資料", [["違規日期", "違規條款"], [1150102, "53條1項"]])])
            uploads = []
            for path in (first, second):
                upload = type("Upload", (), {})()
                upload.filename = path.name
                upload.file = BytesIO(path.read_bytes())
                uploads.append(upload)
            dataset = recover_major_violations(uploads)

        self.assertEqual(dataset.raw_row_count, 2)
        self.assertEqual([source.file_name for source in dataset.sources], ["第35條.xlsx", "第53條.xlsx"])


class PresentationServiceTests(unittest.TestCase):
    def test_unknown_variant_is_rejected_before_subprocess(self):
        with tempfile.TemporaryDirectory() as tempdir:
            service = AccidentPresentationService(Path(tempdir))
            with self.assertRaisesRegex(ValueError, "未知的投影片版本"):
                service.generate(dataset(), "unknown")

    def test_generation_creates_editable_pptx_without_external_runtime(self):
        service = AccidentPresentationService()
        for variant, filename in (("modern", "交通事故分析週報_新式版本.pptx"), ("traditional", "交通事故分析週報_傳統版本.pptx")):
            generated = service.generate(dataset(), variant, "115年1月1日至2月28日")
            self.assertTrue(generated.content.startswith(b"PK"))
            self.assertEqual(generated.filename, filename)
            presentation = Presentation(BytesIO(generated.content))
            self.assertGreaterEqual(len(presentation.slides), 7)
            with ZipFile(BytesIO(generated.content)) as archive:
                slide_xml = b"".join(
                    archive.read(name) for name in archive.namelist()
                    if name.startswith("ppt/slides/slide") and name.endswith(".xml")
                )
            self.assertNotIn(b"{{", slide_xml)


class ExcelExportTests(unittest.TestCase):
    def test_export_creates_formula_driven_workbook(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "analysis.xlsx"
            build_workbook({
                "headers": ["路段", "交叉路名", "發生時間", "肇事原因", "年齡", "當事者區分", "件數"],
                "rows": [["文化路", "中山路", "08:00", "未依規定讓車", 25, "機車", 3]],
            }, output)
            workbook = load_workbook(output, data_only=False)
        self.assertEqual(workbook.sheetnames, ["原始資料", "分析表"])
        self.assertEqual(workbook["原始資料"]["H2"].value[:3], "=IF")
        self.assertTrue(workbook["分析表"]["B6"].value.startswith("=SUMIF"))


if __name__ == "__main__":
    unittest.main()
