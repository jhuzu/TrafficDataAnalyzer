#!/usr/bin/env python3
"""Offline localhost traffic-accident analysis UI."""
import io
import json
import logging
import shutil
import tempfile
from email import policy
from email.parser import BytesParser
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
from modules.major_violation import MajorViolationAnalysisService, load_violation_workbooks

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
    raw = handler.rfile.read(content_length)
    message = BytesParser(policy=policy.default).parsebytes(
        b"MIME-Version: 1.0\r\nContent-Type: "
        + handler.headers.get("Content-Type", "").encode()
        + b"\r\n\r\n"
        + raw
    )
    uploads = []
    for part in message.iter_attachments():
        if part.get_param("name", header="content-disposition") in field_names:
            upload = type("Upload", (), {})()
            upload.filename = Path(part.get_filename() or "").name
            upload.file = io.BytesIO(part.get_payload(decode=True) or b"")
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
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            token = str(body.get("token", ""))
            if self.path == "/clear":
                SESSIONS.delete(token)
                return self.send_json(200, {"cleared": True})

            session = SESSIONS.get(token)
            if not session:
                raise ValueError("資料已失效，請重新載入檔案。")
            dataset = session["dataset"]
            service = session["service"]

            if self.path == "/major-violation/analyze":
                if session.get("module") != "major-violation":
                    raise ValueError("此 Session 不屬於重大違規分析，請重新載入資料。")
                return self.send_json(200, service.analyze(body))

            if self.path == "/generate-pptx":
                generated = PRESENTATIONS.generate(
                    dataset,
                    variant_key=body.get("variant", "modern"),
                    period=body.get("period", "115年1月1日至8月31日"),
                )
                return self.send_file(
                    200, generated.content, generated.content_type, generated.filename
                )

            if self.path == "/map-points":
                return self.send_json(200, service.map_points(body))

            if self.path == "/raw":
                return self.send_json(200, service.raw_page(body))

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
