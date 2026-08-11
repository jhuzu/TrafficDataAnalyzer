import os
import subprocess
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from core.runtime import find_node
from core.session_store import InMemorySessionStore
from modules.accident_analysis.presentation import AccidentPresentationService
from tests.test_accident_analysis import dataset
from web_server import content_disposition, recover_major_violations
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
    def test_find_node_uses_common_executable_candidates(self):
        with tempfile.TemporaryDirectory() as tempdir:
            node = Path(tempdir) / "node"
            node.write_text("#!/bin/sh\n", encoding="utf-8")
            node.chmod(0o755)
            with (
                patch.dict(os.environ, {}, clear=True),
                patch("core.runtime.shutil.which", return_value=None),
                patch("core.runtime.NODE_CANDIDATES", (node,)),
            ):
                self.assertEqual(find_node(), node.resolve())

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

    def test_generation_owns_temporary_subprocess_lifecycle(self):
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            presentation = root / "modules" / "accident_analysis" / "presentation"
            templates = root / "modules" / "accident_analysis" / "templates"
            presentation.mkdir(parents=True)
            templates.mkdir(parents=True)
            service = AccidentPresentationService(root)
            variant = service.variants["modern"]
            variant.generator.write_text("", encoding="utf-8")
            variant.template.write_bytes(b"template")

            def fake_run(arguments, **_):
                output = Path(arguments[arguments.index("--output") + 1])
                output.write_bytes(b"generated-pptx")
                return subprocess.CompletedProcess(arguments, 0, "", "")

            with (
                patch(
                    "modules.accident_analysis.presentation.service.find_node",
                    return_value=Path("/usr/bin/node"),
                ),
                patch(
                    "modules.accident_analysis.presentation.service.subprocess.run",
                    side_effect=fake_run,
                ) as run,
            ):
                generated = service.generate(dataset(), "modern", "115年1月1日至2月28日")

            self.assertEqual(generated.content, b"generated-pptx")
            self.assertEqual(generated.filename, "交通事故分析週報_新式版本.pptx")
            self.assertEqual(run.call_count, 1)


if __name__ == "__main__":
    unittest.main()
