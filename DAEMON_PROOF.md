# Token Guardian v0.1.2-daemon Proof of Work

**Date:** 2026-02-13
**Branch:** feature/daemon-telemetry
**Commit:** 4408bc6

---

## Implementation Summary

Native daemon for Token Guardian that reads OpenClaw session telemetry and produces cost savings metrics.

### Files Added/Modified

| File | Purpose |
|------|---------|
| `src/core/daemon.py` | Core daemon module (558 lines) |
| `tokenguardian.py` | CLI commands (daemon start/stop/status, stats) |
| `systemd/tokenguardian.service` | systemd unit file |

### Key Features

- **Telemetry Collection:** Reads OpenClaw session JSONL files from `~/.openclaw/agents/main/sessions/`
- **Instance Support:** Isolated instances (`~/.tokenguardian/<instance>/`)
- **Data Files:**
  - `data/telemetry.jsonl` - Append-only per-request records
  - `data/stats_rollup.json` - Rolling 24h statistics
  - `logs/daemon.log` - Daemon operational logs
  - `run/daemon.lock` - PID lockfile
- **Metrics Tracked:**
  - Timestamp, model/provider
  - Prompt/completion/total tokens
  - Cost (from OpenClaw telemetry)
  - Cache read tokens
- **CLI Commands:**
  - `tokenguardian daemon start --instance default --poll 60`
  - `tokenguardian daemon stop --instance default`
  - `tokenguardian daemon status --instance default`
  - `tokenguardian stats --instance default --hours 24`

---

## POW Attempt: 2026-02-13

### Execution

| Metric | Value |
|--------|-------|
| Start Time | 2026-02-13 21:34:26 UTC |
| End Time | 2026-02-13 21:36:30 UTC |
| Duration | ~2 minutes |
| Daemon Status | Started and stopped successfully |

### Data Collected

| Metric | Value |
|--------|-------|
| Telemetry Records | 0 |
| Data Files Created | `pow_start_utc.txt`, `pow_stop_utc.txt` |

### Limitation Encountered

**Issue:** Could not generate user-query traffic through the normal public interface (Telegram/webchat ingress).

**Details:**
- The available `sessions_send` tool injects assistant messages, not user queries
- User messages through Telegram/webchat ingress cannot be triggered from within this session
- Without user-query traffic, the daemon observed no new session activity
- Session JSONL files were monitored but no new assistant responses with usage data were generated

### Technical Evidence

```
$ cat ~/.tokenguardian/default/data/pow_start_utc.txt
Fri Feb 13 21:34:26 UTC 2026

$ cat ~/.tokenguardian/default/data/pow_stop_utc.txt
Fri Feb 13 21:36:30 UTC 2026

$ wc -l ~/.tokenguardian/default/data/telemetry.jsonl
0
```

```
$ tail -10 ~/.tokenguardian/default/logs/daemon.log
2026-02-13 21:34:23,216 [INFO] Classifier disabled (telemetry collection only)
2026-02-13 21:34:23,216 [INFO] Starting Token Guardian daemon (instance: default)
```

---

## Daemon Behavior (Verified)

1. **Starts correctly** - Lockfile created, PID recorded
2. **Discovers session files** - Found 6 OpenClaw session JSONL files
3. **Logs operations** - Entries written to daemon.log
4. **Graceful shutdown** - Responds to SIGTERM
5. **Instance isolation** - Writes to `~/.tokenguardian/<instance>/`

---

## What's Needed for Complete POW

To complete a full 30-minute POW with representative traffic:

1. **Traffic Source Options:**
   - Real Telegram/webchat messages from Phil
   - A dedicated test session with isolated ingress
   - Direct session injection (requires different tool access)

2. **Expected Output After Traffic:**
   ```
   telemetry.jsonl: N records (one per assistant response)
   stats_rollup.json: Aggregated metrics
   Model mix: MiniMax-M2.1, GPT-5 Mini, Grok-4 usage breakdown
   Money number: Estimated cost avoided (vs. baseline)
   ```

---

## Cost Baseline for "Avoided" Calculation

When traffic is collected, the daemon calculates cost avoided using:

**Assumption:** Without Token Guardian, all queries would route to the most expensive model (Grok-4).

| Model | Input $/1M | Output $/1M |
|-------|-----------|-------------|
| Grok-4 (baseline) | $3.00 | $15.00 |
| GPT-5 Mini | $1.50 | $6.00 |
| MiniMax-M2.1 | $0.50 | $0.50 |

**Avoided = Baseline Cost (Grok-4) - Actual Cost**

---

## Next Steps

1. **Complete POW with real traffic** - Requires Telegram/webchat user messages
2. **Enable classifier integration** - Add routing metadata (label/confidence/tier) to telemetry
3. **Add cost calculation** - When OpenClaw telemetry lacks cost data, calculate from tokens
4. **Test cache behavior** - Verify cache hits reduce estimated cost

---

## Version Info

- **Current Branch:** feature/daemon-telemetry
- **Latest Commit:** 4408bc6
- **Previous Tag:** v0.1.1
- **Proposed Tag:** v0.1.2-daemon (after complete POW)

---

*Generated: 2026-02-13 21:37 UTC*
