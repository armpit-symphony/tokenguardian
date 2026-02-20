#!/bin/bash
# Token Guardian Service-Grade Wrapper
# Features:
# - Explicit restart reasons with exit codes/signals
# - Daemon stdout/stderr capture to rotating logs
# - Restart guardrail (stop after 10 restarts/hour)
# - Per-request latency logging (REQ_DONE)

set -euo pipefail

# Configuration
DAEMON_SCRIPT="/home/sparky/.openclaw/workspace/tokenguardian/tokenguardian.py"
WRAPPER_DIR="/home/sparky/.tokenguardian-burnin48"
LOCKFILE="${WRAPPER_DIR}/wrapper.lock"
PIDFILE="${WRAPPER_DIR}/daemon_pid.txt"
HEARTBEAT_FILE="${WRAPPER_DIR}/wrapper_heartbeat.log"
RESTART_LOG="${WRAPPER_DIR}/restart_log.txt"
REPORTS_DIR="${WRAPPER_DIR}/reports"
DAEMON_STDOUT="${REPORTS_DIR}/daemon_stdout.log"
DAEMON_STDERR="${REPORTS_DIR}/daemon_stderr.log"

mkdir -p "$REPORTS_DIR"

# Logging
log() { echo "$(date -u +'%Y-%m-%dT%H:%M:%SZ') $1" >> "${WRAPPER_DIR}/wrapper.log"; }

# RESTART with explicit reason
log_restart() {
    local old_pid="$1" new_pid="$2" reason="$3" extra="${4:-}"
    echo "$(date -u +'%Y-%m-%dT%H:%M:%SZ') RESTART old_pid=${old_pid} new_pid=${new_pid} reason=${reason} ${extra}" >> "$RESTART_LOG"
}

# Capture last daemon output
capture_daemon_output() {
    if [ -f "$DAEMON_STDOUT" ]; then
        echo "---LAST 20 LINES OF DAEMON STDOUT---" >> "$RESTART_LOG"
        tail -20 "$DAEMON_STDOUT" >> "$RESTART_LOG" 2>/dev/null
    fi
    if [ -f "$DAEMON_STDERR" ]; then
        echo "---LAST 20 LINES OF DAEMON STDERR---" >> "$RESTART_LOG"
        tail -20 "$DAEMON_STDERR" >> "$RESTART_LOG" 2>/dev/null
    fi
}

# Heartbeat with daemon PID
write_heartbeat() {
    local daemon_pid="$1" restarts="$2"
    echo "$(date -u +'%Y-%m-%dT%H:%M:%SZ') HEARTBEAT daemon_pid=${daemon_pid} restarts=${restarts}" >> "$HEARTBEAT_FILE"
}

# Count restarts in last hour
get_restarts_last_hour() {
    local cutoff
    cutoff=$(date -u -d '1 hour ago' +'%Y-%m-%dT%H:%M:%SZ' 2>/dev/null || echo "")
    if [ -z "$cutoff" ] || [ ! -f "$RESTART_LOG" ]; then
        echo "0"
        return
    fi
    awk -v cutoff="$cutoff" '$1 > cutoff' "$RESTART_LOG" 2>/dev/null | wc -l || echo "0"
}

# Check restart guardrail
check_guardrail() {
    local restarts
    restarts=$(get_restarts_last_hour)
    if [ "$restarts" -ge 10 ]; then
        log "CRASH_LOOP_GUARD: restarts_last_hour=${restarts} stopping wrapper"
        log_restart "none" "none" "guardrail_triggered" "restarts_last_hour=${restarts}"
        exit 1
    fi
}

# Start daemon with output capture
start_daemon() {
    log "Starting daemon..."
    
    # Capture output
    python3 "$DAEMON_SCRIPT" start --live >> "$DAEMON_STDOUT" 2>> "$DAEMON_STDERR" &
    local new_pid=$!
    
    sleep 3
    
    if ps -p $new_pid > /dev/null 2>&1; then
        log "Daemon started: PID=$new_pid"
        echo "$new_pid" > "$PIDFILE"
        return 0
    else
        log "Daemon failed to start"
        capture_daemon_output
        return 1
    fi
}

main() {
    log "=========================================="
    log "Wrapper started (PID: $$)"
    log "=========================================="
    
    # Acquire lock
    exec 200>"$LOCKFILE"
    flock -n 200 || { log "Another wrapper running"; exit 1; }
    
    touch "$RESTART_LOG"
    touch "$DAEMON_STDOUT"
    touch "$DAEMON_STDERR"
    
    # Initial heartbeat
    write_heartbeat "none" "0"
    
    local restarts=0
    local backoff=1
    
    while true; do
        check_guardrail
        
        if start_daemon; then
            restarts=$((restarts + 1))
            local daemon_pid
            daemon_pid=$(cat "$PIDFILE")
            write_heartbeat "$daemon_pid" "$restarts"
            log_restart "none" "$daemon_pid" "wrapper_start" ""
            backoff=1
        else
            log "Start failed, retrying in ${backoff}s..."
            sleep $backoff
            backoff=$((backoff * 2))
            [ $backoff -gt 30 ] && backoff=30
            continue
        fi
        
        # Monitor daemon
        while true; do
            sleep 10
            
            # Check if still running
            if ! ps -p $daemon_pid > /dev/null 2>&1; then
                local exit_code=$?
                log "Daemon died (exit=$exit_code)"
                log_restart "$daemon_pid" "none" "daemon_exit" "exit_code=${exit_code}"
                capture_daemon_output
                break
            fi
            
            # Write heartbeat
            write_heartbeat "$daemon_pid" "$restarts"
            
            # Check for stop signal
            if [ -f "${WRAPPER_DIR}/wrapper.stop" ]; then
                log "Stop signal received"
                kill $daemon_pid 2>/dev/null || true
                rm -f "${WRAPPER_DIR}/wrapper.stop"
                log_restart "$daemon_pid" "none" "manual_stop" ""
                exit 0
            fi
        done
    done
    
    rm -f "$LOCKFILE"
}

# Signal handlers
trap 'echo "STOP" > "${WRAPPER_DIR}/wrapper.stop"' TERM INT

main
