#!/usr/bin/env bash
# Renderiza os anúncios gerados em build/ para out/<id>.mp4
#   scripts/render.sh            # todos
#   scripts/render.sh 01 07      # só alguns
set -e
cd "$(dirname "$0")/.."
for d in build/*/; do
  id=$(basename "$d")
  if [ $# -gt 0 ]; then ok=0; for s in "$@"; do [[ $id == $s* ]] && ok=1; done; [ $ok = 1 ] || continue; fi
  echo "== $id"
  (cd "$d" && npx --prefix ../.. hyperframes render --fps 30 --quality standard --workers 4 -o "../../out/$id.mp4" 2>&1 | grep -viE "telemetry|chrome|headless" | tail -3)
done
