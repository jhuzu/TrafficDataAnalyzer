#!/usr/bin/env python3
"""Offline localhost traffic-accident analysis UI."""
import io
import json
import shutil
import subprocess
import tempfile
import time
import uuid
from email import policy
from email.parser import BytesParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from core.excel import read_excel_source
from modules.accident_analysis import (
    ACCIDENT_PREFERRED_HEADERS,
    AccidentAnalysisService,
    transform_accident_source,
)
from modules.accident_analysis.presentation import build_presentation_payload

ROOT = Path(__file__).resolve().parent
FRONTEND_ROOT = ROOT / "frontend"
ACCIDENT_MODULE_ROOT = ROOT / "modules" / "accident_analysis"
ACCIDENT_PRESENTATION_ROOT = ACCIDENT_MODULE_ROOT / "presentation"
ACCIDENT_TEMPLATE_ROOT = ACCIDENT_MODULE_ROOT / "templates"
SESSIONS = {}
SESSION_TTL = 1800  # 30 minutes
MAX_SESSIONS = 10
MAX_UPLOAD_BYTES = 100 * 1024 * 1024  # 100 MB
SUPPORTED_UPLOAD_EXTENSIONS = {".xlsx", ".xlsm", ".xls"}
PRESENTATION_VARIANTS = {
    "modern": {
        "label": "新式版本",
        "template": ACCIDENT_TEMPLATE_ROOT / "板橋分局交通事故分析週報_骨架自動填值模板.pptx",
        "generator": ACCIDENT_PRESENTATION_ROOT / "presentation_generator.mjs",
        "filename": "交通事故分析週報_新式版本.pptx",
    },
    "traditional": {
        "label": "傳統版本",
        "template": ACCIDENT_TEMPLATE_ROOT / "交通事故分析_原版樣式_自動填值模板.pptx",
        "generator": ACCIDENT_PRESENTATION_ROOT / "traditional_presentation_generator.mjs",
        "filename": "交通事故分析週報_傳統版本.pptx",
    },
}


def cleanup_sessions():
    """Remove expired sessions and enforce maximum count."""
    now = time.time()
    expired = [k for k, v in SESSIONS.items() if now - v["created"] > SESSION_TTL]
    for k in expired:
        del SESSIONS[k]
    if len(SESSIONS) > MAX_SESSIONS:
        oldest = sorted(SESSIONS, key=lambda k: SESSIONS[k]["created"])
        for k in oldest[: len(SESSIONS) - MAX_SESSIONS]:
            del SESSIONS[k]


def parse_upload(handler):
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
    for part in message.iter_attachments():
        if part.get_param("name", header="content-disposition") == "file":
            upload = type("Upload", (), {})()
            upload.filename = part.get_filename() or ""
            upload.file = io.BytesIO(part.get_payload(decode=True) or b"")
            if Path(upload.filename).suffix.lower() in SUPPORTED_UPLOAD_EXTENSIONS:
                return upload
    raise ValueError("請選取 .xlsx 或 .xlsm 檔案；舊版 .xls 請先另存新格式。")


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
    def log_message(self, *_):
        pass

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
        safe_filename = filename.encode("ascii", "ignore").decode() or "download.pptx"
        self.send_header("Content-Disposition", f'attachment; filename="{safe_filename}"')
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
            cleanup_sessions()

            if self.path == "/load":
                dataset = recover(parse_upload(self))
                token = uuid.uuid4().hex
                SESSIONS[token] = {
                    "dataset": dataset,
                    "service": AccidentAnalysisService(dataset),
                    "created": time.time(),
                }
                return self.send_json(200, {
                    "token": token,
                    "fields": list(dataset.headers),
                    "rows": len(dataset.rows),
                    "sourceType": dataset.source_type,
                    "rowMode": dataset.row_mode,
                    "sheetName": dataset.sheet_name,
                    "warnings": list(dataset.warnings),
                })

            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            session = SESSIONS.get(body.get("token"))
            if not session:
                raise ValueError("資料已失效，請重新載入檔案。")
            dataset = session["dataset"]
            service = session["service"]
            session["created"] = time.time()  # refresh TTL on access

            if self.path == "/generate-pptx":
                variant_key = str(body.get("variant", "modern")).strip().lower()
                variant = PRESENTATION_VARIANTS.get(variant_key)
                if variant is None:
                    raise ValueError("未知的投影片版本，請選擇新式版本或傳統版本。")
                template = variant["template"]
                generator = variant["generator"]
                if not template.is_file():
                    raise ValueError(f"找不到{variant['label']}模板：{template.name}")
                if not generator.is_file():
                    raise ValueError(f"找不到{variant['label']}生成器：{generator.name}")
                node = shutil.which("node") or "/opt/homebrew/bin/node"
                if not Path(node).is_file():
                    raise ValueError("找不到 Node.js，無法生成投影片。請先安裝 Node.js。")
                tempdir = Path(tempfile.mkdtemp(prefix="traffic_ppt_"))
                try:
                    data_path = tempdir / "data.json"
                    output_path = tempdir / "traffic-accident-weekly-report.pptx"
                    period = str(body.get("period", "115年1月1日至8月31日")).strip() or "115年1月1日至8月31日"
                    payload = build_presentation_payload(dataset, period)
                    data_path.write_text(
                        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
                    )
                    run = subprocess.run(
                        [node, str(generator), "--data", str(data_path),
                         "--template", str(template), "--output", str(output_path), "--period", period],
                        capture_output=True,
                        text=True,
                        timeout=120,
                    )
                    if run.returncode or not output_path.is_file():
                        raise ValueError(run.stderr.strip() or run.stdout.strip() or "投影片生成失敗。")
                    return self.send_file(
                        200,
                        output_path.read_bytes(),
                        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                        variant["filename"],
                    )
                finally:
                    shutil.rmtree(tempdir, ignore_errors=True)

            if self.path == "/map-points":
                return self.send_json(200, service.map_points(body))

            if self.path == "/raw":
                return self.send_json(200, service.raw_page(body))

            return self.send_json(200, service.analyze(body))
        except (ValueError, KeyError, json.JSONDecodeError, IndexError) as exc:
            self.send_json(400, {"error": str(exc)})
        except Exception as exc:
            self.send_json(500, {"error": str(exc)})


if __name__ == "__main__":
    print("請在瀏覽器開啟：http://127.0.0.1:8765")
    ThreadingHTTPServer(("127.0.0.1", 8765), Handler).serve_forever()
