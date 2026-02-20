# Token Guardian Burn-In Data Tracker

## Session 1: Initial Fix - 2026-02-20 01:17 UTC

### Changes Applied
1. Fixed `poll_openclaw()` to parse session JSONL files directly
2. Added `timedelta` import for 24h lookback
3. Fixed `_load_stats()` to include `by_model` data
4. Reset stats file with correct attribution

### Before Fix
- Total Tokens: 708,441,690
- Unattributed Gap: 707,145,704 (99.8%)
- Attribution Lag: True

### After Fix
- Total Tokens: 121,842,383
- Unattributed Gap: 0
- Attribution Lag: False

### Model Breakdown (After Fix)
| Model | Tokens | Percentage |
|-------|--------|------------|
| MiniMax M2.1 | 120,645,495 | 99.0% |
| GPT-5 Mini | 1,156,514 | 0.9% |
| Grok-4 | 40,374 | 0.03% |

---

## Session 2: Daemon Restart - 2026-02-20 01:25 UTC

### Stats Update
- Total Tokens: 122,755,432
- New Tokens Since Start: ~675K
- Status: No zombie processes ✅

---

## Git Changes (Uncommitted)

### Modified Files
- `src/core/monitor.py` - Fixed polling logic
- `src/core/daemon.py` - Potential improvements
- `src/core/pipeline.py` - Pipeline fixes
- `tokenguardian.py` - Fixed stats command

### New Files
- `DAEMON_DEBUG_TODO.md` - Debugging notes
- `24h_report.md` - Report template
- Various burn-in test scripts

---

## Next Steps
1. Create GitHub repo: `armpit-symmetry/tokenguardian`
2. Push changes: `git remote add origin git@github.com:armpit-symmetry/tokenguardian.git`
3. Push: `git push -u origin feature/billing-profiles`
