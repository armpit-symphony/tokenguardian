# Token Guardian Recovery Runbook

## Quick Status Check

```bash
# Check if everything is healthy
python3 ~/.openclaw/workspace/tokenguardian/tg_healthcheck.py

# View recent cycles
tail -20 ~/.tokenguardian-burnin48/supervisor/daemon_stdout.log

# View supervisor activity
tail -20 ~/.tokenguardian-burnin48/supervisor/supervisor.log
```

## Process Tree

```
systemd (optional) → tg_supervisor.py → tokenguardian.py start
                                    ↑
                          healthcheck cron (every 1 min)
```

## Common Issues & Fixes

### Issue: Supervisor not running

**Symptoms:**
- `ps aux | grep tg_supervisor` shows nothing
- Healthcheck logs "SUPERVISOR_DEAD"

**Fix:**
```bash
# Start supervisor manually
nohup python3 ~/.openclaw/workspace/tokenguardian/tg_supervisor.py \
    --daemon ~/.openclaw/workspace/tokenguardian/tokenguardian.py \
    >> ~/.tokenguardian-burnin48/supervisor/supervisor.log 2>&1 &

# Or if systemd is installed
sudo systemctl start tokenguardian
```

### Issue: Daemon not producing output

**Symptoms:**
- Supervisor shows `STATS_STALE` warnings
- Daemon stdout hasn't been updated in >10 minutes

**Fix:**
```bash
# Check daemon process
ps aux | grep "tokenguardian.py start"

# Force restart via supervisor
pkill -HUP -f "tg_supervisor"

# Or manually kill daemon (supervisor will restart)
pkill -9 -f "tokenguardian.py start"
```

### Issue: Daemon cycling but stats not updating

**Symptoms:**
- Cycles running (CYCLE N appearing every 30s)
- `total_tokens` stuck at same value
- No sessions producing data

**Diagnosis:**
```bash
# Check for active sessions
npx openclaw sessions_list 2>/dev/null | head -20

# Check daemon mode
tail -5 ~/.tokenguardian-burnin48/supervisor/daemon_stdout.log | grep -i mode
```

**Explanation:** Token Guardian only ingests when OpenClaw sessions are active. If no sessions, stats remain static. This is expected behavior.

### Issue: Too many restarts (crash loop)

**Symptoms:**
- Supervisor logs show many restarts in short time
- Alert cooldown triggered

**Fix:**
```bash
# Check for errors in daemon stderr
tail -30 ~/.tokenguardian-burnin48/supervisor/daemon_stderr.log

# Check supervisor for pattern
grep -c "DAEMON_DIED" ~/.tokenguardian-burnin48/supervisor/supervisor.log

# If crash loop, temporarily disable restart
# Edit tg_supervisor.py: set restart_delay = 60
```

## Logs Reference

| Log | Location | Purpose |
|-----|----------|---------|
| Supervisor | `~/.tokenguardian-burnin48/supervisor/supervisor.log` | Supervisor restarts, alerts |
| Daemon stdout | `~/.tokenguardian-burnin48/supervisor/daemon_stdout.log` | Cycle status, health |
| Daemon stderr | `~/.tokenguardian-burnin48/supervisor/daemon_stderr.log` | Errors, tracebacks |
| Healthcheck | `~/.tokenguardian-burnin48/supervisor/healthcheck.log` | Minute-by-minute status |
| Stats | `~/.tokenguardian/stats.json` | Token counts (external) |

## Alert Cooldown

Alerts are throttled to 5 minutes (300s) to prevent spam during crash loops.

To bypass cooldown for testing:
```bash
rm ~/.tokenguardian-burnin48/supervisor/alert_cooldown.txt
```

## Controlled Crash Test

```bash
# 1. Note current state
tail -5 ~/.tokenguardian-burnin48/supervisor/daemon_stdout.log

# 2. Kill daemon
pkill -9 -f "tokenguardian.py start"

# 3. Watch restart
tail -f ~/.tokenguardian-burnin48/supervisor/supervisor.log

# 4. Verify Telegram alert received
```

Expected: Supervisor detects death within 10s, sends alert, restarts daemon within 5s.

## Systemd Commands (if installed)

```bash
# Check status
sudo systemctl status tokenguardian

# Start/Stop/Restart
sudo systemctl start tokenguardian
sudo systemctl stop tokenguardian
sudo systemctl restart tokenguardian

# Enable at boot
sudo systemctl enable tokenguardian

# View logs
journalctl -u tokenguardian -f
```

## File Locations

```
/home/sparky/.openclaw/workspace/tokenguardian/
├── tg_supervisor.py     # Main supervisor
├── tg_healthcheck.py    # Cron health monitor
├── tg_alert.py          # Alert script
├── tokenguardian.py     # CLI entry point
├── tokenguardian.service # Systemd unit (install to /etc/systemd/system/)
└── src/daemon/daemon.py # Daemon core

~/.tokenguardian-burnin48/supervisor/
├── supervisor.log        # Supervisor activity
├── daemon_stdout.log    # Daemon output
├── daemon_stderr.log    # Daemon errors
├── healthcheck.log      # Health status
├── supervisor.pid       # Supervisor PID
├── daemon.pid           # Daemon PID
└── alert_cooldown.txt   # Alert throttle
```

## Recovery Checklist

If system is broken:

1. ☐ Check if supervisor is running
2. ☐ Check if daemon is running
3. ☐ Check daemon output freshness
4. ☐ Review recent errors in daemon_stderr.log
5. ☐ Verify Telegram alerts are working
6. ☐ Confirm stats.json is being updated (if sessions active)

## Contact

For alerts: Telegram @8585118112 (your number)

---
Updated: 2026-02-16
Version: 1.0
