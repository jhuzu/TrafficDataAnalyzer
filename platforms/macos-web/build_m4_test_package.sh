#!/bin/zsh

set -euo pipefail
PROJECT_ROOT="${0:A:h:h:h}"
DEFAULT_NAME="TrafficDataAnalyzer_Mac修正v1.1_20260813"
DESTINATION="${1:-$PROJECT_ROOT/generated/$DEFAULT_NAME}"
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
  "$PROJECT_ROOT/" "$DESTINATION/TrafficDataAnalyzer/"

chmod +x "$DESTINATION/TrafficDataAnalyzer/platforms/macos-web/"*.command
ditto -c -k --sequesterRsrc --keepParent "$DESTINATION/TrafficDataAnalyzer" "$ARCHIVE_PATH"

echo "資料夾：$DESTINATION/TrafficDataAnalyzer"
echo "測試包：$ARCHIVE_PATH"
