#!/bin/zsh

set -e
SCRIPT_DIR="${0:A:h}"
PYTHON_BIN="${PYTHON_BIN:-$SCRIPT_DIR/.venv/bin/python}"
if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="$(command -v python3 2>/dev/null || true)"
fi
if [[ -z "$PYTHON_BIN" || ! -x "$PYTHON_BIN" ]]; then
  echo "錯誤：找不到 Python 3。" >&2
  exit 1
fi
if ! "$PYTHON_BIN" -c 'import openpyxl' >/dev/null 2>&1; then
  echo "錯誤：缺少 Excel 匯出依賴。請先雙擊 安裝Python依賴.command。" >&2
  exit 1
fi

if [[ -n "$1" && -f "$1" ]]; then
  INPUT="$1"
else
  INPUT=$(osascript -e 'POSIX path of (choose file with prompt "選取含樞紐分析表的 .xlsm 檔案")' || true)
fi

[[ -z "$INPUT" ]] && exit 0

TEMP_JSON=$(mktemp -t pivot_cache.XXXXXX)
trap 'rm -f "$TEMP_JSON"' EXIT
BASE="${INPUT:r}_完整自動分析"
OUTPUT="${BASE}.xlsx"
if [[ -e "$OUTPUT" ]]; then
  OUTPUT="${BASE}_$(date +%Y%m%d-%H%M%S).xlsx"
fi

"$PYTHON_BIN" "$SCRIPT_DIR/extract_pivot_cache.py" "$INPUT" "$TEMP_JSON"
"$PYTHON_BIN" "$SCRIPT_DIR/build_xlsx.py" "$TEMP_JSON" "$OUTPUT"
osascript -e "display notification \"$(basename "$OUTPUT")\" with title \"完整分析已完成\""
echo "完成：$OUTPUT"
