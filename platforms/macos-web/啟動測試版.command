#!/bin/zsh

set -e
PROJECT_ROOT="${0:A:h:h:h}"
PYTHON_BIN="${PYTHON_BIN:-$PROJECT_ROOT/.venv/bin/python}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="$(command -v python3 2>/dev/null || true)"
fi
if [[ -z "$PYTHON_BIN" || ! -x "$PYTHON_BIN" ]]; then
  osascript -e 'display alert "無法啟動" message "找不到 Python 3。請先安裝 Xcode Command Line Tools，或安裝 Python 3 後再重新開啟。"'
  exit 1
fi
if ! "$PYTHON_BIN" -c 'import openpyxl, pptx, PIL' >/dev/null 2>&1; then
  osascript -e 'display alert "缺少 Python 依賴" message "請先雙擊 安裝Python依賴.command，完成後再啟動。"'
  exit 1
fi

if lsof -ti tcp:8765 >/dev/null 2>&1; then
  osascript -e 'display alert "無法啟動" message "8765 埠已被其他程式使用。請先關閉另一個交通資料分析工具視窗後再試。"'
  exit 1
fi

cd "$PROJECT_ROOT"
open "http://127.0.0.1:8765"
exec "$PYTHON_BIN" web_server.py
