"""Windows double-click entry point for the self-contained application build."""
from __future__ import annotations

import os
import sys
import threading
import webbrowser
from http.server import ThreadingHTTPServer
from pathlib import Path


if getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(sys._MEIPASS)))
else:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from web_server import Handler


def main() -> None:
    port = int(os.environ.get("TRAFFIC_DATA_ANALYZER_PORT", "8765"))
    try:
        server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    except OSError as error:
        import ctypes
        ctypes.windll.user32.MessageBoxW(
            0,
            f"{port} 連接埠已被其他程式使用。請先關閉另一個工具視窗後再試。",
            "交通資料分析工具無法啟動",
            0x10,
        )
        raise SystemExit(1) from error
    threading.Timer(0.45, lambda: webbrowser.open(f"http://127.0.0.1:{port}")).start()
    server.serve_forever()


if __name__ == "__main__":
    main()
