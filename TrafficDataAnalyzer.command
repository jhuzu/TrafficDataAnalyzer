#!/bin/zsh

set -e
SCRIPT_DIR="${0:A:h}"
NODE_BIN="${NODE_BIN:-$(cd "$SCRIPT_DIR" && /usr/bin/python3 -c 'from core.runtime import find_node; node = find_node(); print(node or "")')}"
if [[ ! -x "$NODE_BIN" ]]; then
  echo "錯誤：找不到 Node.js，請先安裝 Node.js 或設定 NODE_BIN 環境變數。" >&2
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

/usr/bin/python3 "$SCRIPT_DIR/extract_pivot_cache.py" "$INPUT" "$TEMP_JSON"
"$NODE_BIN" "$SCRIPT_DIR/build_xlsx.mjs" "$TEMP_JSON" "$OUTPUT"
osascript -e "display notification \"$(basename "$OUTPUT")\" with title \"完整分析已完成\""
echo "完成：$OUTPUT"
