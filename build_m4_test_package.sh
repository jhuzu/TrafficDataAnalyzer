#!/bin/zsh

set -euo pipefail
SCRIPT_DIR="${0:A:h}"
DEFAULT_NAME="TrafficDataAnalyzer_M4_測試版_20260811"
DESTINATION="${1:-$SCRIPT_DIR/generated/$DEFAULT_NAME}"
ARCHIVE_PATH="${DESTINATION}.zip"

if [[ -e "$DESTINATION" || -e "$ARCHIVE_PATH" ]]; then
  echo "目標已存在：$DESTINATION 或 $ARCHIVE_PATH" >&2
  exit 1
fi

mkdir -p "$DESTINATION"
rsync -a \
  --exclude='.git/' \
  --exclude='.venv*' \
  --exclude='outputs/' \
  --exclude='generated/' \
  --exclude='tmp/' \
  --exclude='__pycache__/' \
  --exclude='*.pyc' \
  --exclude='.DS_Store' \
  "$SCRIPT_DIR/" "$DESTINATION/TrafficDataAnalyzer/"

chmod +x "$DESTINATION/TrafficDataAnalyzer/"*.command
ditto -c -k --sequesterRsrc --keepParent "$DESTINATION/TrafficDataAnalyzer" "$ARCHIVE_PATH"

echo "資料夾：$DESTINATION/TrafficDataAnalyzer"
echo "測試包：$ARCHIVE_PATH"
