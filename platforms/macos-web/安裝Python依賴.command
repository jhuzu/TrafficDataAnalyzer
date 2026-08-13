#!/bin/zsh

set -e
PROJECT_ROOT="${0:A:h:h:h}"
PYTHON_BIN="$(command -v python3 2>/dev/null || true)"

if [[ -z "$PYTHON_BIN" || ! -x "$PYTHON_BIN" ]]; then
  osascript -e 'display alert "無法安裝" message "找不到 Python 3。請先安裝 Xcode Command Line Tools，完成後再重新開啟。"'
  exit 1
fi

cd "$PROJECT_ROOT"
"$PYTHON_BIN" -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
osascript -e 'display notification "Python 依賴已安裝完成" with title "TrafficDataAnalyzer"'
echo "安裝完成。現在可雙擊 啟動網頁版.command。"
