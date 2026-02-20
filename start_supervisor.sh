#!/bin/bash
# Token Guardian Resilient Supervisor Launcher
# Replaces the old wrapper with proper auto-restart + alerting

set -euo pipefail

SUPERVISOR_SCRIPT="/home/sparky/.openclaw/workspace/tokenguardian/tg_supervisor.py"
LOG_DIR="/home/sparky/.tokenguardian-burnin48/supervisor"
PIDFILE="/home/sparky/.tokenguardian-burnin48/supervisor/supervisor.pid"

# Ensure log directory
mkdir -p "$LOG_DIR"

# Check if already running
if [ -f "$PIDFILE" ]; then
    OLD_PID=$(cat "$PIDFILE")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        echo "Supervisor already running (PID $OLD_PID)"
        exit 0
    fi
    echo "Stale PID file, removing..."
    rm -f "$PIDFILE"
fi

# Start supervisor
echo "Starting Token Guardian supervisor..."
nohup python3 "$SUPERVISOR_SCRIPT" \
    --daemon /home/sparky/.openclaw/workspace/tokenguardian/tokenguardian.py \
    --restart-delay 5 \
    >> "$LOG_DIR/launcher.log" 2>&1 &

echo "Supervisor started in background"
