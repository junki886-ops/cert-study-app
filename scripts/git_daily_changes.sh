#!/usr/bin/env bash
set -euo pipefail

DAY="${1:-$(date +%F)}"
NEXT_DAY="$(date -j -v+1d -f "%Y-%m-%d" "${DAY}" +%F 2>/dev/null || date -d "${DAY} +1 day" +%F)"

echo "Git changes for ${DAY}"
echo

git log \
  --since="${DAY} 00:00" \
  --until="${NEXT_DAY} 00:00" \
  --date=short \
  --pretty=format:'%h %ad %s' \
  --stat
