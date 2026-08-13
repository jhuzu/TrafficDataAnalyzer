#!/bin/zsh
set -e
PROJECT_ROOT="${0:A:h:h:h}"
PYTHON_BIN="${PYTHON_BIN:-$PROJECT_ROOT/.venv/bin/python}"
if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="$(command -v python3 2>/dev/null || true)"
fi
if [[ -z "$PYTHON_BIN" || ! -x "$PYTHON_BIN" ]]; then
  echo "錯誤：找不到 Python 3。請先依 README 安裝環境。" >&2
  exit 1
fi
if ! "$PYTHON_BIN" -c 'import openpyxl, pptx, PIL' >/dev/null 2>&1; then
  osascript -e 'display alert "缺少 Python 依賴" message "請先雙擊 安裝Python依賴.command，完成後再啟動。"'
  exit 1
fi
# 若已有舊版 localhost 服務，先只停止 8765 埠的舊服務，避免瀏覽器仍顯示舊頁面。
OLD_LOCAL_PID="$(lsof -ti tcp:8765 2>/dev/null || true)"
if [[ -n "$OLD_LOCAL_PID" ]]; then
  kill $OLD_LOCAL_PID 2>/dev/null || true
  sleep 0.3
fi
open "http://127.0.0.1:8765"
exec "$PYTHON_BIN" "$PROJECT_ROOT/web_server.py"
