#!/usr/bin/env python3
"""Offline localhost traffic-accident analysis UI."""
import io
import json
import logging
import re
import shutil
import tempfile
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote

from core.excel import read_excel_source
from core.session_store import InMemorySessionStore
from modules.accident_analysis import (
    ACCIDENT_PREFERRED_HEADERS,
    AccidentAnalysisService,
    transform_accident_source,
)
from modules.accident_analysis.presentation import AccidentPresentationService
from modules.major_violation import (
    MajorViolationAnalysisService, build_performance, generate_performance_pptx,
    load_performance_statistics, load_performance_targets, load_violation_workbooks,
)

ROOT = Path(__file__).resolve().parent
FRONTEND_ROOT = ROOT / "frontend"
MAX_UPLOAD_BYTES = 100 * 1024 * 1024  # 100 MB
SUPPORTED_UPLOAD_EXTENSIONS = {".xlsx", ".xlsm", ".xls"}
SESSIONS = InMemorySessionStore(ttl_seconds=1800, max_sessions=10)
PRESENTATIONS = AccidentPresentationService(ROOT)
LOGGER = logging.getLogger("traffic_data_analyzer")


def content_disposition(filename: str) -> str:
    """Return an RFC 5987 download header that preserves Chinese filenames."""
    suffix = Path(filename).suffix or ".bin"
    return f"attachment; filename=download{suffix}; filename*=UTF-8''{quote(filename)}"


def parse_uploads(handler, *, field_names: set[str]) -> list[object]:
    content_length = int(handler.headers.get("Content-Length", 0))
    if content_length > MAX_UPLOAD_BYTES:
        raise ValueError(f"檔案大小超過上限（{MAX_UPLOAD_BYTES // 1024 // 1024} MB）。")
    content_type = handler.headers.get("Content-Type", "")
    boundary_marker = "boundary="
    if boundary_marker not in content_type:
        raise ValueError("上傳格式錯誤，缺少 multipart boundary。")
    boundary = content_type.split(boundary_marker, 1)[1].strip().strip('"').encode("ascii")
    raw = handler.rfile.read(content_length)
    uploads = []
    for part in raw.split(b"--" + boundary):
        if not part or part in (b"--\r\n", b"--"):
            continue
        header_block, separator, payload = part.lstrip(b"\r\n").partition(b"\r\n\r\n")
        if not separator:
            continue
        headers = header_block.decode("latin-1")
        disposition = next((line for line in headers.split("\r\n") if line.lower().startswith("content-disposition:")), "")
        name_match = re.search(r'(?:^|;)\s*name="([^"]+)"', disposition)
        filename_match = re.search(r'(?:^|;)\s*filename="([^"]*)"', disposition)
        if name_match and name_match.group(1) in field_names and filename_match:
            filename = filename_match.group(1)
            try:
                filename = filename.encode("latin-1").decode("utf-8")
            except UnicodeDecodeError:
                pass
            upload = type("Upload", (), {})()
            upload.filename = Path(filename).name
            upload.file = io.BytesIO(payload[:-2] if payload.endswith(b"\r\n") else payload)
            if Path(upload.filename).suffix.lower() in SUPPORTED_UPLOAD_EXTENSIONS:
                uploads.append(upload)
            else:
                raise ValueError("請選取 .xlsx 或 .xlsm 檔案；舊版 .xls 請先另存新格式。")
    if uploads:
        return uploads
    raise ValueError("請選取 .xlsx 或 .xlsm 檔案；舊版 .xls 請先另存新格式。")


def parse_upload(handler):
    """Compatibility wrapper for the accident module's one-file endpoint."""
    return parse_uploads(handler, field_names={"file"})[0]


def recover(upload):
    tempdir = Path(tempfile.mkdtemp(prefix="traffic_web_"))
    try:
        suffix = Path(upload.filename).suffix.lower()
        incoming = tempdir / f"input{suffix}"
        with incoming.open("wb") as f:
            shutil.copyfileobj(upload.file, f)
        source = read_excel_source(
            incoming,
            preferred_headers=ACCIDENT_PREFERRED_HEADERS,
            count_field="件數",
        ).to_dict()
        return transform_accident_source(source)
    finally:
        shutil.rmtree(tempdir, ignore_errors=True)


def recover_major_violations(uploads) -> object:
    """Persist one multipart batch briefly, then normalize every workbook together."""
    tempdir = Path(tempfile.mkdtemp(prefix="major_violation_web_"))
    try:
        paths = []
        for index, upload in enumerate(uploads, start=1):
            suffix = Path(upload.filename).suffix.lower()
            incoming_dir = tempdir / f"source_{index:03d}"
            incoming_dir.mkdir()
            incoming = incoming_dir / f"{Path(upload.filename).stem}{suffix}"
            with incoming.open("wb") as file:
                shutil.copyfileobj(upload.file, file)
            paths.append(incoming)
        return load_violation_workbooks(paths)
    finally:
        shutil.rmtree(tempdir, ignore_errors=True)


def recover_performance_targets(upload):
    tempdir = Path(tempfile.mkdtemp(prefix="major_target_web_"))
    try:
        incoming = tempdir / f"target{Path(upload.filename).suffix.lower()}"
        with incoming.open("wb") as file:
            shutil.copyfileobj(upload.file, file)
        return replace(load_performance_targets(incoming, period="week" if upload.period == "week" else "month"), source_name=upload.filename)
    finally:
        shutil.rmtree(tempdir, ignore_errors=True)


def recover_performance_statistics(uploads):
    tempdir = Path(tempfile.mkdtemp(prefix="major_statistics_web_"))
    try:
        paths = []
        for index, upload in enumerate(uploads, 1):
            path = tempdir / f"statistics_{index}{Path(upload.filename).suffix.lower()}"
            with path.open("wb") as file:
                shutil.copyfileobj(upload.file, file)
            paths.append(path)
        statistics = load_performance_statistics(paths)
        return replace(statistics, source_names=tuple(upload.filename for upload in uploads))
    finally:
        shutil.rmtree(tempdir, ignore_errors=True)


def performance_session(token: str) -> tuple[str, dict]:
    """Return an independent weekly-performance session; it never needs big-data upload."""
    session = SESSIONS.get(token) if token else None
    if session and session.get("module") == "major-performance":
        return token, session
    token = SESSIONS.create({"module": "major-performance"})
    return token, SESSIONS.get(token)


# ---------------------------------------------------------------------------
# HTTP Handler
# ---------------------------------------------------------------------------

MIME_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".svg": "image/svg+xml",
    ".json": "application/json; charset=utf-8",
}

class Handler(BaseHTTPRequestHandler):
    def log_message(self, format_string, *args):
        LOGGER.info("%s - %s", self.address_string(), format_string % args)

    def send_json(self, status_code, body):
        content = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def send_file(self, status_code, content, content_type, filename):
        self.send_response(status_code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Disposition", content_disposition(filename))
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self):
        if self.path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return
        url_path = self.path.split("?")[0].lstrip("/") or "index.html"
        filepath = (FRONTEND_ROOT / url_path).resolve()
        # Prevent path traversal
        if not str(filepath).startswith(str(FRONTEND_ROOT.resolve())):
            self.send_error(403)
            return
        if not filepath.is_file():
            self.send_error(404)
            return
        try:
            content = filepath.read_bytes()
        except OSError:
            self.send_error(404)
            return
        content_type = MIME_TYPES.get(filepath.suffix, "application/octet-stream")
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_POST(self):
        try:
            if self.path == "/load":
                dataset = recover(parse_upload(self))
                token = SESSIONS.create({
                    "dataset": dataset,
                    "service": AccidentAnalysisService(dataset),
                })
                return self.send_json(200, {
                    "token": token,
                    "fields": list(dataset.headers),
                    "rows": len(dataset.rows),
                    "sourceType": dataset.source_type,
                    "rowMode": dataset.row_mode,
                    "sheetName": dataset.sheet_name,
                    "warnings": list(dataset.warnings),
                })

            if self.path == "/major-violation/load":
                dataset = recover_major_violations(parse_uploads(self, field_names={"files", "file"}))
                if not dataset.records:
                    details = " ".join(
                        warning for source in dataset.sources for warning in source.warnings
                    )
                    raise ValueError(f"沒有成功載入任何重大違規資料。{details}")
                token = SESSIONS.create({
                    "module": "major-violation",
                    "dataset": dataset,
                    "service": MajorViolationAnalysisService(dataset),
                })
                start, end = dataset.date_range
                return self.send_json(200, {
                    "token": token,
                    "rows": dataset.raw_row_count,
                    "totalCount": dataset.total_count,
                    "dateRange": {"start": start, "end": end},
                    "deduplicationStatus": dataset.deduplication_status,
                    "warnings": list(dataset.warnings),
                    "sources": [{
                        "fileName": source.file_name,
                        "status": source.status,
                        "rows": source.raw_row_count,
                        "sheetName": source.sheet_name,
                        "warnings": list(source.warnings),
                    } for source in dataset.sources],
                })
            if self.path == "/major-violation/performance-target":
                uploads = parse_uploads(self, field_names={"target"})
                token, session = performance_session(self.headers.get("X-Performance-Token", ""))
                uploads[0].period = self.headers.get("X-Performance-Period", "month")
                targets = recover_performance_targets(uploads[0])
                session["performance_targets"] = targets
                return self.send_json(200, {"token": token, "sourceName": targets.source_name, "units": list(targets.units), "warnings": list(targets.warnings)})
            if self.path == "/major-violation/performance-statistics":
                uploads = parse_uploads(self, field_names={"statistics", "statistic"})
                token, session = performance_session(self.headers.get("X-Performance-Token", ""))
                statistics = recover_performance_statistics(uploads)
                session["performance_statistics"] = statistics
                return self.send_json(200, {"token": token, "sourceNames": list(statistics.source_names), "availableKeys": list(statistics.available_keys), "warnings": list(statistics.warnings)})
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            token = str(body.get("token", ""))
            if self.path == "/clear":
                SESSIONS.delete(token)
                return self.send_json(200, {"cleared": True})

            session = SESSIONS.get(token)
            if not session:
                raise ValueError("資料已失效，請重新載入檔案。")
            dataset = session.get("dataset")
            service = session.get("service")

            if self.path == "/major-violation/analyze":
                if session.get("module") != "major-violation":
                    raise ValueError("此 Session 不屬於重大違規分析，請重新載入資料。")
                return self.send_json(200, service.analyze(body))

            if self.path == "/major-violation/performance":
                targets = session.get("performance_targets")
                if targets is None:
                    raise ValueError("請先提供「績效目標值」Excel。")
                source_dataset = dataset if session.get("module") == "major-violation" else None
                return self.send_json(200, build_performance(source_dataset, targets, body.get("startDate"), body.get("endDate"), session.get("performance_statistics"), body.get("selectedKeys")))

            if self.path == "/major-violation/generate-performance-pptx":
                targets = session.get("performance_targets")
                if targets is None:
                    raise ValueError("請先提供「績效目標值」Excel。")
                source_dataset = dataset if session.get("module") == "major-violation" else None
                performance = build_performance(source_dataset, targets, body.get("startDate"), body.get("endDate"), session.get("performance_statistics"), body.get("selectedKeys"))
                template = ROOT / "modules" / "major_violation" / "templates" / "重大違規績效投影片.pptx"
                if not template.is_file():
                    raise ValueError("找不到重大違規績效投影片模板。")
                with tempfile.TemporaryDirectory(prefix="major_performance_ppt_") as temporary:
                    output = Path(temporary) / "重大違規績效.pptx"
                    generate_performance_pptx(performance, template, output)
                    return self.send_file(200, output.read_bytes(), "application/vnd.openxmlformats-officedocument.presentationml.presentation", "重大交通違規績效.pptx")

            if self.path == "/generate-pptx":
                if dataset is None:
                    raise ValueError("此 Session 沒有事故分析資料。")
                generated = PRESENTATIONS.generate(
                    dataset,
                    variant_key=body.get("variant", "modern"),
                    period=body.get("period", "115年1月1日至8月31日"),
                )
                return self.send_file(
                    200, generated.content, generated.content_type, generated.filename
                )

            if self.path == "/map-points":
                if service is None:
                    raise ValueError("此 Session 沒有事故分析資料。")
                return self.send_json(200, service.map_points(body))

            if self.path == "/raw":
                if service is None:
                    raise ValueError("此 Session 沒有事故分析資料。")
                return self.send_json(200, service.raw_page(body))

            if service is None:
                raise ValueError("此 Session 沒有可分析資料。")
            return self.send_json(200, service.analyze(body))
        except (ValueError, KeyError, json.JSONDecodeError, IndexError) as exc:
            LOGGER.warning("Request rejected on %s: %s", self.path, exc)
            self.send_json(400, {"error": str(exc)})
        except Exception:
            LOGGER.exception("Unhandled request failure on %s", self.path)
            self.send_json(500, {"error": "伺服器處理失敗，請查看啟動視窗的錯誤紀錄。"})


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    print("請在瀏覽器開啟：http://127.0.0.1:8765")
    ThreadingHTTPServer(("127.0.0.1", 8765), Handler).serve_forever()
