# Token Guardian Daemon Debugging TODO

## Issue
The Token Guardian daemon sometimes has zombie processes and stale stats.

## Symptoms Observed
- Multiple `tokenguardian.py start --live` processes running (PIDs 1252348, 1673853, 1674230)
- Old processes not properly terminated on restart
- Stats file not always synced correctly

## Files Involved
- `/home/sparky/.openclaw/workspace/tokenguardian/tokenguardian.py` - Main CLI
- `/home/sparky/.openclaw/workspace/tokenguardian/src/core/monitor.py` - Monitor with polling
- `/home/sparky/.openclaw/workspace/tokenguardian/tg_supervisor.py` - Resilient supervisor

## Test Plan for Fix
1. Start daemon: `python3 tokenguardian.py start --live`
2. Verify single process: `ps aux | grep tokenguardian`
3. Poll stats: `cat ~/.tokenguardian/stats.json`
4. Force restart (simulate crash or manual restart)
5. Verify: Single new process, stats update correctly
6. Run for 24h and verify no zombie processes

## Potential Fixes
1. Add proper signal handlers for SIGTERM/SIGKILL
2. Use PID file locking to prevent duplicate processes
3. Add health check that verifies process is responsive
4. Log process status on each stats update

## Priority
P2 - Current workaround works (daemon running, stats updating)
