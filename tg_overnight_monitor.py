#!/usr/bin/env python3
"""
Token Guardian Overnight Monitor - FIXED V3

Correctly parses ISO timestamps from supervisor.log.
"""

import subprocess
import re
from datetime import datetime, timezone
from pathlib import Path

LOG_DIR = Path("/home/sparky/.tokenguardian-burnin48/overnight")
STATUS_LOG = LOG_DIR / "overnight.log"
ALERT_COOLDOWN = 1800


def get_daemon_status():
    pidfile = Path("/home/sparky/.tokenguardian-burnin48/supervisor/daemon.pid")
    if not pidfile.exists():
        return {"running": False, "reason": "No PID file"}
    
    try:
        pid = int(pidfile.read_text().strip())
        result = subprocess.run(["ps", "-p", str(pid)], capture_output=True)
        if result.returncode != 0:
            return {"running": False, "reason": "PID not running", "pid": pid}
    except Exception as e:
        return {"running": False, "reason": str(e)}
    
    # Get start time from supervisor.log
    supervisor_log = Path("/home/sparky/.tokenguardian-burnin48/supervisor/supervisor.log")
    start_time = None
    
    if supervisor_log.exists():
        for line in reversed(supervisor_log.read_text().split('\n')):
            if "DAEMON_STARTED" in line and str(pid) in line:
                match = re.search(r'\[([^\]]+)\]', line)
                if match:
                    ts_str = match.group(1)
                    # Normalize: remove Z if followed by +HH:MM
                    ts_str = ts_str.replace('Z', '') if '+' in ts_str else ts_str
                    try:
                        start_time = datetime.fromisoformat(ts_str)
                        break
                    except:
                        pass
    
    # Count cycles
    stdout = Path("/home/sparky/.tokenguardian-burnin48/supervisor/daemon_stdout.log")
    cycles = 0
    if stdout.exists():
        result = subprocess.run(["grep", "-c", "CYCLE", str(stdout)], capture_output=True, text=True)
        cycles = int(result.stdout.strip()) if result.stdout.strip().isdigit() else 0
    
    if start_time:
        uptime = (datetime.now(timezone.utc) - start_time).total_seconds()
        return {
            "running": True,
            "pid": pid,
            "start_time": start_time.isoformat(),
            "uptime_seconds": int(uptime),
            "cycles_completed": cycles,
        }
    
    return {"running": True, "pid": pid}


def check_restart():
    restart_file = LOG_DIR / ".last_pid"
    pidfile = Path("/home/sparky/.tokenguardian-burnin48/supervisor/daemon.pid")
    
    if not pidfile.exists():
        return (True, "No PID file")
    
    try:
        current_pid = int(pidfile.read_text().strip())
    except Exception as e:
        return (True, f"Cannot read PID: {e}")
    
    if not restart_file.exists():
        restart_file.write_text(str(current_pid))
        return (False, "First run")
    
    last_pid = int(restart_file.read_text())
    
    if current_pid != last_pid:
        restart_file.write_text(str(current_pid))
        return (True, f"PID changed: {last_pid} → {current_pid}")
    
    # Check actual start time from supervisor.log
    supervisor_log = Path("/home/sparky/.tokenguardian-burnin48/supervisor/supervisor.log")
    if supervisor_log.exists():
        for line in reversed(supervisor_log.read_text().split('\n')):
            if "DAEMON_STARTED" in line and str(current_pid) in line:
                match = re.search(r'\[([^\]]+)\]', line)
                if match:
                    ts_str = match.group(1)
                    ts_str = ts_str.replace('Z', '') if '+' in ts_str else ts_str
                    try:
                        start_time = datetime.fromisoformat(ts_str)
                        uptime_sec = (datetime.now(timezone.utc) - start_time).total_seconds()
                        if uptime_sec < 600:
                            restart_file.write_text(str(current_pid))
                            return (True, f"Daemon recently started (uptime: {uptime_sec:.0f}s)")
                        return (False, f"Stable (PID {current_pid}, uptime: {uptime_sec/3600:.1f}h)")
                    except:
                        pass
    
    return (False, f"Stable (PID {current_pid})")


def send_alert(message):
    cooldown_file = LOG_DIR / ".alert_cooldown"
    current_ts = datetime.now(timezone.utc).timestamp()
    
    if cooldown_file.exists():
        try:
            if current_ts - float(cooldown_file.read_text().strip()) < ALERT_COOLDOWN:
                return
        except:
            pass
    
    try:
        subprocess.run([
            "python3", "/home/sparky/.openclaw/workspace/tokenguardian/tg_alert.py",
            "--title", "TG OVERNIGHT ALERT", "--message", message
        ], capture_output=True)
        cooldown_file.write_text(str(current_ts))
        print(f"Alert sent: {message}")
    except:
        pass


def main():
    status = get_daemon_status()
    restart_detected, message = check_restart()
    
    STATUS_LOG.parent.mkdir(parents=True, exist_ok=True)
    STATUS_LOG.write_text(f"[{datetime.now()}] {status}\n")
    
    print(f"Status: {status}")
    print(f"Message: {message}")
    
    if restart_detected:
        send_alert(message)


if __name__ == "__main__":
    main()
