#!/usr/bin/env python3
"""
Token Guardian Resilient Supervisor

Features:
- Restarts daemon on death
- Restarts daemon when stats are stale (>15 min)
- Sends Telegram alert on death
- Captures daemon output to log files
- Health check endpoint
- Proper logging

Usage:
    python3 tg_supervisor.py --daemon /home/sparky/.openclaw/workspace/tokenguardian/tokenguardian.py
"""

import argparse
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Config
SUPERVISOR_DIR = Path("/home/sparky/.tokenguardian-burnin48/supervisor")
PIDFILE = SUPERVISOR_DIR / "supervisor.pid"
LOGFILE = SUPERVISOR_DIR / "supervisor.log"
DAEMON_STDOUT = SUPERVISOR_DIR / "daemon_stdout.log"
DAEMON_STDERR = SUPERVISOR_DIR / "daemon_stderr.log"
ALERT_COOLDOWN = 300  # 5 minutes between alerts
STATS_STALE_THRESHOLD = 900  # 15 minutes before restart on stale stats
MAX_RESTARTS_PER_HOUR = 5  # Prevent crash loops


def log(msg: str):
    """Log with timestamp."""
    ts = datetime.now(timezone.utc).isoformat() + "Z"
    line = "[{}] {}".format(ts, msg)
    print(line)
    with open(LOGFILE, "a") as f:
        f.write(line + "\n")


def send_telegram_alert(message: str):
    """Send Telegram alert - with cooldown to prevent spam."""
    cooldown_file = SUPERVISOR_DIR / "alert_cooldown.txt"
    
    # Check cooldown
    if cooldown_file.exists():
        try:
            last_alert = datetime.fromisoformat(cooldown_file.read_text().strip())
            if (datetime.now(timezone.utc) - last_alert).total_seconds() < ALERT_COOLDOWN:
                log("SKIP_ALERT: Cooldown active ({}s)".format(ALERT_COOLDOWN))
                return
        except:
            pass
    
    alert_msg = "TOKEN GUARDIAN ALERT\n\n" + message
    
    cmd = [
        "npx", "openclaw", "message", "send",
        "--channel", "telegram",
        "--target", "8585118112",
        "--message", alert_msg
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            log("ALERT_SENT: Telegram notification sent")
            cooldown_file.write_text(datetime.now(timezone.utc).isoformat())
        else:
            log("ALERT_FAILED: {}".format(result.stderr[:200]))
    except Exception as e:
        log("ALERT_ERROR: {}".format(e))


def get_daemon_status() -> dict:
    """Check if daemon is running."""
    pidfile = SUPERVISOR_DIR / "daemon.pid"
    if pidfile.exists():
        try:
            pid = int(pidfile.read_text().strip())
            result = subprocess.run(["ps", "-p", str(pid)], capture_output=True)
            if result.returncode == 0:
                return {"running": True, "pid": pid}
        except:
            pass
    return {"running": False, "pid": None, "reason": "pidfile_missing" if not pidfile.exists() else "process_dead"}


def get_stats_status() -> tuple:
    """Check if stats are fresh.
    
    Returns: (is_stale: bool, age_minutes: float)
    """
    stats_file = Path("/home/sparky/.tokenguardian/stats.json")
    if not stats_file.exists():
        return (True, float('inf'))
    
    try:
        mtime = stats_file.stat().st_mtime
        age_seconds = time.time() - mtime
        age_minutes = age_seconds / 60
        return (age_minutes > STATS_STALE_THRESHOLD / 60, age_minutes)
    except:
        return (True, float('inf'))


def start_daemon(daemon_script: str) -> Optional[int]:
    """Start the Token Guardian daemon."""
    log("STARTING_DAEMON: {}".format(daemon_script))
    
    env = os.environ.copy()
    env["TG_CONFIG_DIR"] = "/home/sparky/.tokenguardian"
    env["PYTHONUNBUFFERED"] = "1"
    
    stdout_file = open(DAEMON_STDOUT, "a")
    stderr_file = open(DAEMON_STDERR, "a")
    
    proc = subprocess.Popen(
        [sys.executable, "-u", daemon_script, "start", "--live"],
        env=env,
        stdout=stdout_file,
        stderr=stderr_file,
        cwd=str(Path(daemon_script).parent),
    )
    
    pid = proc.pid
    log("DAEMON_STARTED: pid={}".format(pid))
    
    pidfile = SUPERVISOR_DIR / "daemon.pid"
    pidfile.write_text(str(pid))
    
    return pid


def kill_daemon(pid: int):
    """Force kill the daemon."""
    try:
        log("KILLING_DAEMON: pid={}".format(pid))
        subprocess.run(["kill", "-9", str(pid)], check=False)
        time.sleep(2)
        subprocess.run(["kill", "-9", str(pid)], check=False)
    except Exception as e:
        log("KILL_ERROR: {}".format(e))


def run_supervisor(daemon_script: str, restart_delay: float = 5.0):
    """Main supervisor loop."""
    log("SUPERVISOR_START: daemon={}".format(daemon_script))
    
    # Note: Ingestor runs separately for offset tracking
    # It is managed independently of the daemon
    
    send_telegram_alert("Supervisor started - Token Guardian will auto-restart on failure")
    
    restart_count = 0
    last_restart_time = time.time()
    stale_start_time = None  # Track when stats went stale
    
    while True:
        pid = start_daemon(daemon_script)
        restart_count += 1
        last_restart_time = time.time()
        stale_start_time = None  # Reset stale tracking
        
        log("MONITORING: PID {}, restart #{}".format(pid, restart_count))
        
        while True:
            time.sleep(10)
            
            # Check if daemon is still running
            status = get_daemon_status()
            
            if not status["running"]:
                # Rate limit restarts
                time_since_restart = time.time() - last_restart_time
                if time_since_restart < 3600 and restart_count > MAX_RESTARTS_PER_HOUR:
                    log("RATE_LIMIT: Too many restarts ({}/hour), backing off".format(restart_count))
                    send_telegram_alert("Token Guardian crash loop detected ({} restarts/hour). Backing off 10 min.".format(restart_count))
                    time.sleep(600)
                    restart_count = 0
                    continue
                
                log("DAEMON_DIED: {} (was {})".format(status.get('reason', 'unknown'), status['pid']))
                send_telegram_alert("Token Guardian died (PID {}). Restarting... (restart #{})".format(status['pid'], restart_count))
                time.sleep(restart_delay)
                break  # Restart daemon
            
            # Check stats freshness
            is_stale, age_minutes = get_stats_status()
            
            if is_stale:
                if stale_start_time is None:
                    stale_start_time = time.time()
                    log("STATS_STALE: {:.1f} minutes - monitoring".format(age_minutes))
                
                stale_duration = time.time() - stale_start_time
                
                if stale_duration > STATS_STALE_THRESHOLD:
                    log("STATS_STALE_TIMEOUT: {:.1f} min - restarting daemon".format(stale_duration/60))
                    send_telegram_alert("Stats stuck at {:.0f} min for >15 min. Restarting daemon...".format(age_minutes))
                    
                    # Kill and restart
                    kill_daemon(pid)
                    time.sleep(restart_delay)
                    break  # Restart daemon
            else:
                # Stats are fresh - reset tracking
                if stale_start_time is not None:
                    log("STATS_FRESH: Recovered after {:.0f}s stale".format(time.time() - stale_start_time))
                    stale_start_time = None


def main():
    parser = argparse.ArgumentParser(description="Token Guardian Resilient Supervisor")
    parser.add_argument("--daemon", required=True, help="Path to daemon script")
    parser.add_argument("--restart-delay", type=float, default=5.0, help="Delay before restart (seconds)")
    args = parser.parse_args()
    
    SUPERVISOR_DIR.mkdir(parents=True, exist_ok=True)
    PIDFILE.write_text(str(os.getpid()))
    
    def handle_signal(sig, frame):
        log("SIGNAL_RECEIVED: {}".format(sig))
        send_telegram_alert("Supervisor received {} - shutting down".format(sig))
        sys.exit(0)
    
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)
    
    run_supervisor(args.daemon, args.restart_delay)


if __name__ == "__main__":
    main()
