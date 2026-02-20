#!/usr/bin/env python3
"""
Token Guardian Health Check + Auto-Start

Cron entry (every minute):
* * * * * python3 /home/sparky/.openclaw/workspace/tokenguardian/tg_healthcheck.py

This ensures the daemon is always running even if supervisor dies.
"""

import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Config
SUPERVISOR_DIR = Path("/home/sparky/.tokenguardian-burnin48/supervisor")
DAEMON_STDOUT = SUPERVISOR_DIR / "daemon_stdout.log"
LOG_FILE = SUPERVISOR_DIR / "healthcheck.log"
ALERT_FILE = SUPERVISOR_DIR / "last_alert.txt"
SUPERVISOR_PID = SUPERVISOR_DIR / "supervisor.pid"
DAEMON_PID = SUPERVISOR_DIR / "daemon.pid"


def log(msg: str):
    """Log with timestamp."""
    ts = datetime.now(timezone.utc).isoformat() + "Z"
    line = f"[{ts}] {msg}"
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def send_alert(message: str):
    """Send Telegram alert (with 15min cooldown)."""
    now = datetime.now(timezone.utc)
    
    if ALERT_FILE.exists():
        try:
            last = datetime.fromisoformat(ALERT_FILE.read_text().strip())
            if (now - last).total_seconds() < 900:  # 15 min
                log(f"SKIP_ALERT: Cooldown active")
                return
        except:
            pass
    
    cmd = [
        "npx", "openclaw", "message", "send",
        "--channel", "telegram",
        "--target", "8585118112",
        "--message", f"🚨 TG HEALTHCHECK\n\n{message}"
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            log("ALERT_SENT")
            ALERT_FILE.write_text(now.isoformat())
        else:
            log(f"ALERT_FAILED: {result.stderr[:100]}")
    except Exception as e:
        log(f"ALERT_ERROR: {e}")


def check_process(pidfile: Path) -> tuple[bool, int]:
    """Check if a PID file exists and process is running."""
    if not pidfile.exists():
        return False, 0
    try:
        pid = int(pidfile.read_text().strip())
        result = subprocess.run(["ps", "-p", str(pid)], capture_output=True)
        return result.returncode == 0, pid
    except:
        return False, 0


def check_daemon_output(max_age_seconds: int = 120) -> tuple[bool, str]:
    """Check if daemon is producing output."""
    if not DAEMON_STDOUT.exists():
        return False, "No daemon stdout file"
    
    try:
        mtime = DAEMON_STDOUT.stat().st_mtime
        age = time.time() - mtime
        if age > max_age_seconds:
            return False, f"Daemon output stale ({age:.0f}s old)"
        
        # Check if output contains cycle logs
        content = DAEMON_STDOUT.read_text()
        if "CYCLE" in content:
            return True, f"Daemon cycling (output {age:.0f}s old)"
        else:
            return True, f"Daemon started ({age:.0f}s old)"
    except Exception as e:
        return False, f"Error checking output: {e}"


def check_supervisor() -> bool:
    """Check if supervisor is running."""
    running, _ = check_process(SUPERVISOR_PID)
    return running


def check_daemon() -> tuple[bool, str]:
    """Check if daemon is running and healthy."""
    running, pid = check_process(DAEMON_PID)
    if not running:
        return False, f"Daemon not running (no PID)"
    
    # Check daemon output
    output_ok, msg = check_daemon_output()
    if not output_ok:
        return False, f"PID {pid} - {msg}"
    
    return True, f"Daemon running (PID {pid}) - {msg}"


def ensure_supervisor():
    """Ensure supervisor is running."""
    supervisor_ok = check_supervisor()
    if not supervisor_ok:
        log("SUPERVISOR_DEAD - starting...")
        send_alert("Supervisor died - restarting")
        subprocess.run(
            ["nohup", "python3", "/home/sparky/.openclaw/workspace/tokenguardian/tg_supervisor.py",
             "--daemon", "/home/sparky/.openclaw/workspace/tokenguardian/tokenguardian.py"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    return supervisor_ok


def ensure_daemon():
    """Ensure daemon is running under supervisor."""
    daemon_ok, msg = check_daemon()
    if not daemon_ok:
        log(f"DAEMON_DEAD: {msg}")
        if "stale" in msg.lower():
            send_alert(f"Daemon stale: {msg}")
        # Supervisor should catch this, but if not, log it
        return False
    return daemon_ok


def main():
    """Main health check."""
    log("=== HEALTH CHECK ===")
    
    # Check supervisor
    supervisor_running = ensure_supervisor()
    log(f"Supervisor: {'running' if supervisor_running else 'dead'}")
    
    # Check daemon
    daemon_running = ensure_daemon()
    log(f"Daemon: {'running' if daemon_running else 'dead'}")
    
    # Final status
    if supervisor_running and daemon_running:
        log("Status: HEALTHY")
    elif supervisor_running:
        log("Status: DEGRADED (supervisor alive, daemon dead)")
    else:
        log("Status: CRITICAL (supervisor dead)")
    
    return 0 if (supervisor_running and daemon_running) else 1


if __name__ == "__main__":
    sys.exit(main())
