# Burn-In Driver (tg-burnin-driver.py)

## What it is

The burn-in driver is a test harness that periodically runs probes to validate stability over time (burn-in window). It is **not required** for Token Guardian to run in production.

It maintains state for monitoring & safety:
- `driver.lock` (flock exclusivity)
- `driver.status` (JSON state: runs/failures/skips/halted)
- `driver.log` (probe logs)

## Why it halts

The driver can latch into a permanent halt state (`"halted": true`) when:
- probe failures exceed the configured maximum (MAX_FAILURES)
- stats are considered stale too many times (MAX_SKIPS)

When latched, it logs:
- `DRIVER_HALTED: driver previously halted` until you clear the status file.

## Do I need it?

**No for production.** Production only needs the daemon:
```bash
python3 tokenguardian.py start --live
```

## Disable burn-in driver but keep Token Guardian LIVE

### Step 1: stop supervisor/driver (if running)
```bash
pkill -f tg_supervisor.py || true
pkill -f tg-burnin-driver.py || true
```

### Step 2: clear latch files (optional but recommended)
```bash
cd /home/sparky/.openclaw/workspace/tokenguardian
rm -f driver.status driver.lock
```

### Step 3: run daemon normally
```bash
source venv/bin/activate
python3 tokenguardian.py start --live
python3 tokenguardian.py status
```

## Re-enable burn-in driver (only during testing)

If you intentionally want burn-in validation again:
- ensure driver.status is not halted
- run the supervisor (or the driver) explicitly
