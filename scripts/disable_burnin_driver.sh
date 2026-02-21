#!/usr/bin/env bash
set -euo pipefail

BASE="/home/sparky/.openclaw/workspace/tokenguardian"

echo "[*] Stopping burn-in + supervisor (if running)"
pkill -f tg_supervisor.py || true
pkill -f tg-burnin-driver.py || true

echo "[*] Clearing driver latch files"
rm -f "$BASE/driver.status" "$BASE/driver.lock" || true

echo "[*] Done. Token Guardian daemon can be run independently:"
echo "    cd $BASE && source venv/bin/activate && python3 tokenguardian.py start --live"
