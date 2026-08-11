#!/usr/bin/env python3
"""Offline localhost traffic-accident analysis UI."""
import io
import json
import math
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from collections import defaultdict
from datetime import date
from email import policy
from email.parser import BytesParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FRONTEND_ROOT = ROOT / "frontend"
ACCIDENT_MODULE_ROOT = ROOT / "modules" / "accident_analysis"
ACCIDENT_PRESENTATION_ROOT = ACCIDENT_MODULE_ROOT / "presentation"
ACCIDENT_TEMPLATE_ROOT = ACCIDENT_MODULE_ROOT / "templates"
SESSIONS = {}
SESSION_TTL = 1800  # 30 minutes
MAX_SESSIONS = 10
MAX_UPLOAD_BYTES = 100 * 1024 * 1024  # 100 MB
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
            if upload.filename.lower().endswith(".xlsm"):
                return upload
    raise ValueError("請選取 .xlsm 檔案。")


def recover(upload):
    tempdir = Path(tempfile.mkdtemp(prefix="traffic_web_"))
    try:
        incoming, cache = tempdir / "input.xlsm", tempdir / "cache.json"
        with incoming.open("wb") as f:
            shutil.copyfileobj(upload.file, f)
        run = subprocess.run(
            [sys.executable, str(ROOT / "extract_pivot_cache.py"), str(incoming), str(cache)],
            capture_output=True,
            text=True,
        )
        if run.returncode:
            raise ValueError(run.stderr.strip() or run.stdout.strip() or "無法讀取 Pivot Cache。")
        return json.loads(cache.read_text(encoding="utf-8"))
    finally:
        shutil.rmtree(tempdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def text(row, pos):
    return "" if pos is None or pos >= len(row) or row[pos] in (None, "") else str(row[pos]).strip()


def number(row, pos):
    try:
        return float(row[pos]) if pos is not None and row[pos] not in (None, "") else 0
    except (ValueError, TypeError):
        return 0


def age_label(value):
    try:
        return f"{int(float(value))}歲"
    except (ValueError, TypeError):
        return "年齡不詳"


def aggregate(rows, pos, count_pos, top):
    totals = defaultdict(float)
    if pos is None:
        return []
    for row in rows:
        key = text(row, pos)
        if key:
            totals[key] += number(row, count_pos)
    return [
        {"value": k, "count": int(v) if v.is_integer() else round(v, 2)}
        for k, v in sorted(totals.items(), key=lambda x: (-x[1], x[0]))[:top]
    ]


def trend(rows, month_pos, count_pos, period, year_pos=None, day_pos=None):
    totals = defaultdict(float)
    for row in rows:
        try:
            month = int(text(row, month_pos))
        except (ValueError, TypeError):
            continue
        if period == "week":
            try:
                year = int(text(row, year_pos)) + 1911 if year_pos is not None else 2026
                day = int(text(row, day_pos)) if day_pos is not None else 1
                key = f"{month:02d}月第{date(year, month, day).isocalendar().week}週"
            except (ValueError, TypeError):
                continue
        else:
            key = f"{month:02d}月" if period == "month" else f"第{(month - 1) // 3 + 1}季"
        totals[key] += number(row, count_pos)
    order = sorted(totals, key=lambda x: tuple(int(n) for n in re.findall(r"\d+", x)))
    out = []
    previous = None
    for key in order:
        val = int(totals[key]) if totals[key].is_integer() else round(totals[key], 2)
        delta = None if previous is None else val - previous
        rate = None if previous in (None, 0) else (val - previous) / previous
        out.append({"value": key, "count": val, "delta": delta, "rate": rate})
        previous = val
    return out


def filter_rows(data, body):
    headers, raw = data["headers"], data["rows"]
    p = {h: i for i, h in enumerate(headers)}
    pattern = body.get("pattern", "all")
    out = []
    for row in raw:
        cause = text(row, p.get("肇事原因"))
        vehicle = text(row, p.get("當事者區分"))
        drink = text(row, p.get("飲酒情形"))
        drug = text(row, p.get("施用毒品情形")) + text(row, p.get("唾液毒品檢測"))
        blob = " ".join((cause, vehicle, drink, drug))
        hit = (
            pattern == "all"
            or (pattern == "alcohol" and ("酒" in blob or "飲酒" in blob))
            or (pattern == "drug" and ("毒" in blob or "違禁物" in blob))
            or (pattern == "pedestrian" and "行人" in blob)
        )
        custom = str(body.get("custom", "")).strip()
        if hit and (not custom or custom in blob):
            out.append(row)
    return p, out


# ---------------------------------------------------------------------------
# TWD97 → WGS84 coordinate conversion
# ---------------------------------------------------------------------------

def twd97_to_wgs84(x, y):
    """Convert TWD97 TM2 (EPSG:3826) easting/northing to WGS84 lat/lng."""
    a = 6378137.0
    f = 1.0 / 298.257222101
    lng0 = math.radians(121.0)
    k0 = 0.9999
    dx = 250000.0
    b = a * (1 - f)
    e2 = (a ** 2 - b ** 2) / a ** 2
    e12 = (a ** 2 - b ** 2) / b ** 2
    x -= dx
    M = y / k0
    mu = M / (a * (1 - e2 / 4 - 3 * e2 ** 2 / 64 - 5 * e2 ** 3 / 256))
    e1 = (1 - math.sqrt(1 - e2)) / (1 + math.sqrt(1 - e2))
    J1 = 3 * e1 / 2 - 27 * e1 ** 3 / 32
    J2 = 21 * e1 ** 2 / 16 - 55 * e1 ** 4 / 32
    J3 = 151 * e1 ** 3 / 96
    J4 = 1097 * e1 ** 4 / 512
    fp = mu + J1 * math.sin(2 * mu) + J2 * math.sin(4 * mu) + J3 * math.sin(6 * mu) + J4 * math.sin(8 * mu)
    C1 = e12 * math.cos(fp) ** 2
    T1 = math.tan(fp) ** 2
    R1 = a * (1 - e2) / (1 - e2 * math.sin(fp) ** 2) ** 1.5
    N1 = a / math.sqrt(1 - e2 * math.sin(fp) ** 2)
    D = x / (N1 * k0)
    Q1 = N1 * math.tan(fp) / R1
    Q2 = D ** 2 / 2
    Q3 = (5 + 3 * T1 + 10 * C1 - 4 * C1 ** 2 - 9 * e12) * D ** 4 / 24
    Q4 = (61 + 90 * T1 + 298 * C1 + 45 * T1 ** 2 - 3 * C1 ** 2 - 252 * e12) * D ** 6 / 720
    lat = fp - Q1 * (Q2 - Q3 + Q4)
    Q5 = D
    Q6 = (1 + 2 * T1 + C1) * D ** 3 / 6
    Q7 = (5 - 2 * C1 + 28 * T1 - 3 * C1 ** 2 + 8 * e12 + 24 * T1 ** 2) * D ** 5 / 120
    lng = lng0 + (Q5 - Q6 + Q7) / math.cos(fp)
    return math.degrees(lat), math.degrees(lng)


def detect_coord_fields(headers):
    """Find latitude/longitude field names in headers."""
    lat_field = lng_field = None
    for name in ("緯度", "GPS緯度", "Y座標", "Y", "lat", "latitude"):
        if name in headers:
            lat_field = name
            break
    for name in ("經度", "GPS經度", "X座標", "X", "lng", "longitude"):
        if name in headers:
            lng_field = name
            break
    return lat_field, lng_field


def parse_coordinate(raw_lat, raw_lng):
    """Parse lat/lng values, auto-detecting WGS84 vs TWD97."""
    lat_f, lng_f = float(raw_lat), float(raw_lng)
    if lat_f == 0 or lng_f == 0:
        return None, None
    # TWD97 values are large (easting ~250000, northing ~2700000)
    if lng_f > 100000 or lat_f > 100000:
        return twd97_to_wgs84(lng_f, lat_f)
    return lat_f, lng_f


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
                data = recover(parse_upload(self))
                token = uuid.uuid4().hex
                SESSIONS[token] = {"data": data, "created": time.time()}
                return self.send_json(200, {
                    "token": token,
                    "fields": data["headers"],
                    "rows": len(data["rows"]),
                })

            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            session = SESSIONS.get(body.get("token"))
            if not session:
                raise ValueError("資料已失效，請重新載入檔案。")
            data = session["data"]
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
                    data_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
                    period = str(body.get("period", "115年1月1日至8月31日")).strip() or "115年1月1日至8月31日"
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

            if self.path == "/heatmap":
                headers = data["headers"]
                lat_field, lng_field = detect_coord_fields(headers)
                if not lat_field or not lng_field:
                    raise ValueError(
                        "資料中找不到經緯度欄位。需要「經度」+「緯度」"
                        "（或「GPS經度」+「GPS緯度」或「X座標」+「Y座標」）。"
                    )
                lat_idx = headers.index(lat_field)
                lng_idx = headers.index(lng_field)
                count_idx = headers.index("件數") if "件數" in headers else None
                road_idx = headers.index("路段") if "路段" in headers else None
                cross_idx = headers.index("交叉路名") if "交叉路名" in headers else None
                cause_idx = headers.index("肇事原因") if "肇事原因" in headers else None
                p_body, filtered = filter_rows(data, body)
                heat_points = []
                markers = []
                road_agg = defaultdict(lambda: {"count": 0, "lats": [], "lngs": []})
                for row in filtered:
                    try:
                        lat, lng = parse_coordinate(row[lat_idx], row[lng_idx])
                    except (ValueError, TypeError, IndexError):
                        continue
                    if lat is None:
                        continue
                    w = number(row, count_idx) if count_idx is not None else 1
                    heat_points.append([lat, lng, w])
                    road = text(row, road_idx)
                    cross = text(row, cross_idx)
                    label = "／".join(x for x in (road, cross) if x) or "未知路段"
                    info = road_agg[label]
                    info["count"] += w
                    info["lats"].append(lat)
                    info["lngs"].append(lng)
                # Aggregate top markers by road/intersection
                top_markers = sorted(road_agg.items(), key=lambda x: -x[1]["count"])[:30]
                for label, info in top_markers:
                    n = len(info["lats"])
                    markers.append({
                        "lat": sum(info["lats"]) / n,
                        "lng": sum(info["lngs"]) / n,
                        "count": int(info["count"]),
                        "label": label,
                    })
                if heat_points:
                    center = [
                        sum(p[0] for p in heat_points) / len(heat_points),
                        sum(p[1] for p in heat_points) / len(heat_points),
                    ]
                else:
                    center = [25.0118, 121.4590]  # Banqiao default
                return self.send_json(200, {
                    "heatPoints": heat_points,
                    "markers": markers,
                    "center": center,
                    "total": len(heat_points),
                    "coordField": f"{lng_field}/{lat_field}",
                })

            if self.path == "/raw":
                query = str(body.get("search", "")).strip().lower()
                page = max(1, int(body.get("page", 1)))
                page_size = min(200, max(10, int(body.get("pageSize", 50))))
                source = data["rows"]
                filters = body.get("filters") or {}
                if filters:
                    source = [
                        row for row in source
                        if all(
                            not allowed
                            or text(row, data["headers"].index(field)) in allowed
                            for field, allowed in filters.items()
                            if field in data["headers"]
                        )
                    ]
                if query:
                    source = [
                        row for row in source
                        if query in " ".join("" if v is None else str(v) for v in row).lower()
                    ]
                total = len(source)
                start = (page - 1) * page_size
                return self.send_json(200, {
                    "headers": data["headers"],
                    "rows": source[start : start + page_size],
                    "total": total,
                    "page": page,
                    "pageSize": page_size,
                })

            p, rows = filter_rows(data, body)
            count_pos = p.get("件數")
            if count_pos is None:
                raise ValueError("來源資料沒有「件數」欄位。")
            top = int(body.get("top", 20))
            total = int(sum(number(r, count_pos) for r in rows))

            road = aggregate(rows, p.get("路段"), count_pos, top)

            inter = []
            route_pos = p.get("路段")
            for row in rows:
                value = "／".join(
                    x for x in (text(row, p.get("路段")), text(row, p.get("交叉路名"))) if x
                )
                if value:
                    rr = list(row)
                    rr[route_pos] = value
                    inter.append(rr)
            intersection = aggregate(inter, route_pos, count_pos, top)

            time_rows = []
            time_pos = p.get("發生時間")
            for row in rows:
                if time_pos is not None:
                    rr = list(row)
                    v = text(row, time_pos)
                    rr[time_pos] = v[:2] + "時" if v[:2].isdigit() else "時間不詳"
                    time_rows.append(rr)

            age_pos = p.get("年齡")
            age_rows = []
            for row in rows:
                if age_pos is not None:
                    rr = list(row)
                    rr[age_pos] = age_label(row[age_pos])
                    age_rows.append(rr)

            labels = {
                "all": "全部資料",
                "alcohol": "酒駕相關",
                "drug": "毒駕相關",
                "pedestrian": "行人相關",
            }
            label = labels.get(body.get("pattern"), "自訂條件")
            cause = aggregate(rows, p.get("肇事原因"), count_pos, top)
            vehicle = aggregate(rows, p.get("當事者區分"), count_pos, top)
            age = aggregate(age_rows, age_pos, count_pos, top)
            time_agg = aggregate(time_rows, time_pos, count_pos, top)
            trends = trend(
                rows, p.get("發生月"), count_pos, body.get("period", "month"),
                p.get("發生年"), p.get("發生日"),
            )

            narrative = f"本轄目前資料{label}，依Excel「件數」欄加總計{total:,}件。"
            if road:
                narrative += f"易肇事路段以{road[0]['value']}計{road[0]['count']:,}件最多；"
            if cause:
                narrative += f"主要肇事原因為{cause[0]['value']}計{cause[0]['count']:,}件；"
            if age:
                narrative += f"年齡層以{age[0]['value']}計{age[0]['count']:,}件最多；"
            if vehicle:
                narrative += f"車種以{vehicle[0]['value']}計{vehicle[0]['count']:,}件為大宗。"

            return self.send_json(200, {
                "metrics": [
                    {"label": "符合條件件數", "value": total},
                    {"label": "路段類別數", "value": len(road)},
                    {"label": "肇因類別數", "value": len(cause)},
                    {"label": "資料列數", "value": len(rows)},
                ],
                "rule": f"目前篩選：{label}；統計單位：Excel「件數」加總。",
                "narrative": narrative,
                "road": road,
                "intersection": intersection,
                "time": time_agg,
                "cause": cause,
                "age": age,
                "vehicle": vehicle,
                "trend": trends,
            })
        except (ValueError, KeyError, json.JSONDecodeError, IndexError) as exc:
            self.send_json(400, {"error": str(exc)})
        except Exception as exc:
            self.send_json(500, {"error": str(exc)})


if __name__ == "__main__":
    print("請在瀏覽器開啟：http://127.0.0.1:8765")
    ThreadingHTTPServer(("127.0.0.1", 8765), Handler).serve_forever()
