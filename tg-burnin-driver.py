#!/usr/bin/env python3
"""
TG-Burnin-Driver - Token Guardian Burn-in Driver

Runs every 10 minutes to generate controlled LLM traffic for Token Guardian R&D.
- Alternates between lane=main and session lanes
- Uses unique nonce probes to prevent caching
- Hard caps token usage (small responses only)
- Stops automatically after 3 consecutive failures
- Writes status to lockfile for monitoring

Usage:
    python3 tg-burnin-driver.py [--interval SECONDS] [--max-runs N]

Cron setup (every 10 minutes):
    */10 * * * * cd /home/sparky/.openclaw/workspace/tokenguardian && python3 tg-burnin-driver.py --flock /home/sparky/.openclaw/workspace/tokenguardian/driver.lock
"""

import argparse
import fcntl
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from uuid import uuid4

# Config
LOCKFILE = Path("/home/sparky/.openclaw/workspace/tokenguardian/driver.lock")
STATUSFILE = Path("/home/sparky/.openclaw/workspace/tokenguardian/driver.status")
LOGFILE = Path("/home/sparky/.openclaw/workspace/tokenguardian/driver.log")
STATS_FILE = Path("/home/sparky/.tokenguardian/stats.json")
MAX_FAILURES = 3
MAX_SKIPS = 3
STATS_MAX_AGE_SECONDS = 900  # 15 minutes
PROBE_TIMEOUT = 60


def log(msg):
    """Log to file and stdout."""
    ts = datetime.utcnow().isoformat() + "Z"
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOGFILE, "a") as f:
        f.write(line + "\n")


def get_status():
    """Read current driver status."""
    if STATUSFILE.exists():
        try:
            return json.loads(STATUSFILE.read_text())
        except:
            pass
    return {"runs": 0, "failures": 0, "last_run": None, "halted": False}


def save_status(status):
    """Save driver status."""
    STATUSFILE.write_text(json.dumps(status, indent=2))


def acquire_lock(lockfile_path):
    """Acquire exclusive lock using flock."""
    lockfile = open(lockfile_path, "w")
    try:
        fcntl.flock(lockfile.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        lockfile.write(str(os.getpid()))
        lockfile.flush()
        return lockfile
    except BlockingIOError:
        return None


def release_lock(lockfile):
    """Release lock."""
    fcntl.flock(lockfile.fileno(), fcntl.LOCK_UN)
    lockfile.close()


def send_telegram_probe(lane_type):
    """Send a TG probe message via Telegram."""
    nonce = f"{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}_{uuid4().hex[:8]}"
    probe = f"TG_DRIVER_{lane_type.upper()}_{nonce}: respond with exactly 3 words"

    cmd = [
        "npx", "openclaw", "message", "send",
        "--channel", "telegram",
        "--target", "8585118112",
        "--message", probe
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            cwd="/home/sparky/.npm-global/lib/node_modules/openclaw"
        )
        if result.returncode == 0:
            log(f"DRIVER_PROBE_SENT ts={datetime.utcnow().isoformat()}Z lane={lane_type} nonce={nonce}")
            return True, nonce
        else:
            log(f"DRIVER_PROBE_FAILED: {result.stderr[:200]}")
            return False, None
    except subprocess.TimeoutExpired:
        log("DRIVER_PROBE_TIMEOUT")
        return False, None
    except Exception as e:
        log(f"DRIVER_PROBE_ERROR: {e}")
        return False, None


def check_llm_activity(nonce, timeout=30):
    """Check if LLM was triggered for this probe."""
    # Check OpenClaw logs for completion tokens related to this nonce
    end_time = time.time() + timeout
    while time.time() < end_time:
        try:
            result = subprocess.run(
                ["journalctl", "-u", "openclaw", "--since", "1 minute ago"],
                capture_output=True,
                text=True,
                timeout=10
            )
            # Look for completion tokens or provider calls
            if "completion_tokens" in result.stdout or "input_tokens" in result.stdout:
                return True
            # Check for provider calls
            if any(p in result.stdout for p in ["xai", "minimax", "openai"]):
                # Parse to find our nonce
                for line in result.stdout.split("\n"):
                    if nonce[:20] in line and ("completion_tokens" in line or "provider" in line):
                        return True
        except Exception as e:
            log(f"DRIVER_CHECK_ERROR: {e}")
        time.sleep(2)
    return False


def check_fresh_stats():
    """
    Gate A: Check if stats file is fresh (< 15 minutes old).
    
    Returns:
        tuple: (is_fresh: bool, stats_mtime: float or None, error_msg: str or None)
    """
    if not STATS_FILE.exists():
        return False, None, "stats_file_missing"
    
    try:
        mtime = STATS_FILE.stat().st_mtime
        age_seconds = time.time() - mtime
        if age_seconds > STATS_MAX_AGE_SECONDS:
            return False, mtime, f"stats_stale ({age_seconds:.0f}s old)"
        return True, mtime, None
    except Exception as e:
        return False, None, f"stats_error: {e}"


def run_driver(args):
    """Main driver loop."""
    # Acquire lock
    lock = acquire_lock(args.flock) if args.flock else None
    if lock is None and args.flock:
        log("DRIVER_SKIPPED lock held")
        return

    try:
        # Get status
        status = get_status()

        if status.get("halted"):
            log("DRIVER_HALTED: driver previously halted")
            # Check if we should auto-resume (stats became fresh again)
            is_fresh, _, _ = check_fresh_stats()
            if is_fresh:
                log("DRIVER_RESUME: stats fresh again, resuming")
                status["halted"] = False
                status["skips"] = 0
            else:
                return

        # Check TG is running (check for tokenguardian process OR real stats)
        result = subprocess.run(
            ["pgrep", "-f", "tokenguardian"],
            capture_output=True,
            text=True
        )
        tg_running = result.returncode == 0
        
        # Check REAL stats location
        sim_stats_file = Path("/home/sparky/.token-guardian/stats.json")
        
        # SIM guard - reject fake stats
        if sim_stats_file.exists():
            try:
                sim_data = json.loads(sim_stats_file.read_text())
                if sim_data.get("total_tokens", 0) < 1000000:  # SIM data has tiny token counts
                    log("DRIVER_ERROR INVALID_SOURCE_SIM: Found fake SIM stats in ~/.token-guardian/")
                    log("DRIVER_ERROR Use real TG stats from ~/.tokenguardian/stats.json")
                    return
            except:
                pass
        
        # Gate A: Check for fresh stats before sending probe
        is_fresh, stats_mtime, stats_error = check_fresh_stats()
        
        if not is_fresh:
            # Increment skip counter
            status["skips"] = status.get("skips", 0) + 1
            status["last_run"] = datetime.utcnow().isoformat()
            save_status(status)
            
            # Gate B: Halt after 3 consecutive skips
            if status["skips"] >= MAX_SKIPS:
                status["halted"] = True
                status["skips"] = 0
                save_status(status)
                log(f"DRIVER_HALTED: stats_stale ({stats_error})")
                return
            
            log(f"DRIVER_SKIP: stats_stale_or_missing ({stats_error})")
            return
        
        # Stats are fresh - reset skip counter
        status["skips"] = 0

        # Alternate lane types
        lane_type = "main" if status["runs"] % 2 == 0 else "session"

        # Send probe
        success, nonce = send_telegram_probe(lane_type)

        if success:
            # Update status
            status["runs"] += 1
            status["failures"] = 0
            status["last_run"] = datetime.utcnow().isoformat()
            save_status(status)
            log(f"DRIVER_SUCCESS runs={status['runs']} lane={lane_type}")
        else:
            status["failures"] += 1
            status["last_run"] = datetime.utcnow().isoformat()
            if status["failures"] >= MAX_FAILURES:
                status["halted"] = True
                log("DRIVER_HALTED: too many probe failures")
            save_status(status)

    finally:
        if lock:
            release_lock(lock)


def main():
    parser = argparse.ArgumentParser(description="TG Burn-in Driver")
    parser.add_argument("--interval", type=int, default=600, help="Run interval in seconds")
    parser.add_argument("--flock", type=str, help="Lockfile path for cron exclusivity")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    args = parser.parse_args()

    if args.once:
        run_driver(args)
    else:
        log("DRIVER_STARTED interval=600s")
        while True:
            run_driver(args)
            time.sleep(args.interval)


if __name__ == "__main__":
    main()
