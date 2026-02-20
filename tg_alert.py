#!/usr/bin/env python3
"""
Token Guardian Alert Script

Sends alerts with:
- Timestamp
- Last N lines of daemon stdout
- Last N lines of daemon stderr  
- PID and restart count

Usage:
    python3 tg_alert.py "Alert message"
"""

import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Config
SUPERVISOR_DIR = Path("/home/sparky/.tokenguardian-burnin48/supervisor")
DAEMON_STDOUT = SUPERVISOR_DIR / "daemon_stdout.log"
DAEMON_STDERR = SUPERVISOR_DIR / "daemon_stderr.log"
SUPERVISOR_LOG = SUPERVISOR_DIR / "supervisor.log"


def get_daemon_status() -> dict:
    """Get daemon status from PID file."""
    pidfile = SUPERVISOR_DIR / "daemon.pid"
    if not pidfile.exists():
        return {"pid": None, "output_age": None, "last_cycle": None}
    
    try:
        pid = int(pidfile.read_text().strip())
        
        # Get output age
        if DAEMON_STDOUT.exists():
            mtime = DAEMON_STDOUT.stat().st_mtime
            output_age = int((datetime.now(timezone.utc).timestamp() - mtime) / 60)
        else:
            output_age = None
        
        # Get last cycle line
        last_cycle = None
        if DAEMON_STDOUT.exists():
            lines = DAEMON_STDOUT.read_text().split("\n")
            for line in reversed(lines):
                if "CYCLE" in line:
                    last_cycle = line.strip()
                    break
        
        return {
            "pid": pid,
            "output_age": output_age,
            "last_cycle": last_cycle,
        }
    except Exception as e:
        return {"error": str(e)}


def get_last_lines(filepath: Path, n: int = 10) -> str:
    """Get last N lines of a file."""
    if not filepath.exists():
        return "(file not found)"
    
    try:
        lines = filepath.read_text().split("\n")
        return "\n".join(lines[-n:])
    except Exception as e:
        return f"(error reading: {e})"


def main():
    if len(sys.argv) < 2:
        message = "Token Guardian alert (no message provided)"
    else:
        message = sys.argv[1]
    
    status = get_daemon_status()
    
    # Build alert
    lines = [
        "🚨 **TOKEN GUARDIAN ALERT**",
        "",
        f"📅 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        f"📝 {message}",
        "",
    ]
    
    if "error" in status:
        lines.append(f"❌ Status error: {status['error']}")
    else:
        lines.append(f"🔧 PID: {status.get('pid', 'unknown')}")
        if status.get("output_age") is not None:
            lines.append(f"⏱️ Output age: {status['output_age']} minutes")
        if status.get("last_cycle"):
            lines.append(f"📊 Last cycle: {status['last_cycle']}")
        
        lines.append("")
        lines.append("---")
        lines.append("**Last daemon output:**")
        lines.append("```")
        lines.append(get_last_lines(DAEMON_STDOUT, 8))
        lines.append("```")
        
        # Include stderr if non-empty
        stderr = get_last_lines(DAEMON_STDERR, 5)
        if stderr and stderr != "(file not found)":
            lines.append("")
            lines.append("**Errors:**")
            lines.append("```")
            lines.append(stderr)
            lines.append("```")
    
    alert_text = "\n".join(lines)
    
    # Send via Telegram
    cmd = [
        "npx", "openclaw", "message", "send",
        "--channel", "telegram",
        "--target", "8585118112",
        "--message", alert_text,
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            print("Alert sent successfully")
            return 0
        else:
            print(f"Failed to send alert: {result.stderr}")
            return 1
    except Exception as e:
        print(f"Error sending alert: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
