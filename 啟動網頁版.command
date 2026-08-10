#!/bin/zsh
set -e
SCRIPT_DIR="${0:A:h}"
# 若已有舊版 localhost 服務，先只停止 8765 埠的舊服務，避免瀏覽器仍顯示舊頁面。
OLD_LOCAL_PID="$(lsof -ti tcp:8765 2>/dev/null || true)"
if [[ -n "$OLD_LOCAL_PID" ]]; then
  kill $OLD_LOCAL_PID 2>/dev/null || true
  sleep 0.3
fi
open "http://127.0.0.1:8765"
/usr/bin/python3 "$SCRIPT_DIR/web_server.py"
