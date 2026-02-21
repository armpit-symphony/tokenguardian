# Token Guardian v2 — GitHub Build Outline

## Goal
Rebuild Token Guardian into a reliable, real-time, cost-aware routing + tracking + budget enforcement layer for OpenClaw agents.

## Non-negotiables
- Classifier is always enabled (not None in daemon).
- Pipeline is live-capable by default (shadow is opt-in).
- Monitoring is event/stream based (no slow file polling).
- Dispatch is real (retries + circuit breaker + failover), not a placeholder.
- Ledger is the source of truth for token/cost/latency attribution.

---

## Architecture (Target)

```
Query → Sanitizer → Classifier → BudgetGuard → Router → Optimizer → Dispatch → Ledger(+Metrics)
```

### Key Upgrades
- Add Sanitizer (PII + injection hygiene)
- Add BudgetGuard (downgrade / safe-only)
- Add Dispatcher with retry/backoff + circuit breaker failover
- Replace polling monitor with streaming ledger writes
- Enable Optimizer (dedup + compaction + TTL cache)

---

## Repo Structure

```
tokenguardian/
├── README.md
├── PROJECT_OUTLINE.md
├── tokenguardian.py               # CLI: route/status/report/doctor
├── config/
│   ├── models.yaml
│   ├── routing.yaml
│   ├── budget.yaml
│   └── guardian.yaml
├── src/
│   ├── core/
│   │   ├── pipeline.py           # sanitize→classify→budget→route→optimize→dispatch→ledger
│   │   ├── sanitizer.py
│   │   ├── classifier.py
│   │   ├── router.py
│   │   ├── optimizer.py
│   │   ├── dispatch.py
│   │   ├── circuit_breaker.py
│   │   ├── health.py
│   │   ├── ledger.py
│   │   ├── budget.py
│   │   ├── report.py
│   │   └── openclaw_client.py   # hooks/events integration
│   └── daemon/
│       ├── daemon.py             # async loop + config reload + graceful shutdown
│       └── metrics.py            # Prometheus + structured logs
├── tests/
│   ├── test_classifier.py
│   ├── test_router.py
│   ├── test_optimizer.py
│   ├── test_dispatch.py
│   ├── test_budget.py
│   └── test_pipeline.py
└── systemd/
    └── tokenguardian.service
```

---

## Milestones

### Milestone 0 — Baseline & Guardrails
**Outcome:** repo builds cleanly; configs validated; "doctor" works.

**Issues:**
- Add dependency + project skeleton (pyproject/requirements, lint, test runner)
- Add config loader + schema validation (Pydantic recommended)
- Implement tokenguardian.py doctor (config validation + provider health pings stubbed)

**Acceptance:**
- `python tokenguardian.py doctor` returns PASS with sample configs.
- Invalid YAML fails with clear errors.

---

### Milestone 1 — Ledger First (Truth Source)
**Outcome:** Every request can write/read cost & usage records without OpenClaw polling.

**Issues:**
- Implement ledger.py JSONL append (atomic writes)
- Implement aggregations: spend by day/week/month; by label; by model
- Add tokenguardian.py status and tokenguardian.py report

**Acceptance:**
- status shows totals from ledger (not estimates-only).
- report --period day --by model|label works.

---

### Milestone 2 — Classifier + Routing Bands (Always-On)
**Outcome:** classification drives routing with non-overlapping confidence bands and "vague" detection.

**Issues:**
- Implement ClassificationResult (label/confidence/vague/token_est)
- Vague detection rules (short queries, entropy/shape)
- Router table by label and confidence tier; safe fallback
- Unit tests for label detection & confidence tiers

**Acceptance:**
- Classifier is instantiated in daemon; never disabled.
- Confidence tiers are simple & deterministic (no overlapping thresholds).

---

### Milestone 3 — Budget Guard (Enforcement)
**Outcome:** Token Guardian can downgrade or force safe-only near limits.

**Issues:**
- Implement budget.yaml parsing (daily/weekly/monthly limits + warn/hard_stop)
- Implement BudgetGuard.check() → ALLOW / DOWNGRADE / SAFE_ONLY
- Integrate into pipeline before routing
- Tests with simulated ledger spend

**Acceptance:**
- 80% limit triggers downgrade behavior; >95% triggers safe-only routing.

---

### Milestone 4 — Optimizer (Savings Engine)
**Outcome:** Dedup + compaction + cache reduces spend reliably without breaking intent.

**Issues:**
- Prompt normalization + SHA/MD5 keying
- Dedup (same normalized prompt → cached response)
- Compaction rules (strip filler, redundant boilerplate)
- TTL cache (SQLite recommended) with label-based TTL
- Metrics: savings_pct, cache_hit rate

**Acceptance:**
- Optimizer is enabled by default (config can tune, not disable silently).
- Cache hits yield zero-dispatch for repeat queries.

---

### Milestone 5 — Dispatch + Circuit Breaker (Reliability)
**Outcome:** Real API dispatch with retries, timeouts, and provider failover.

**Issues:**
- dispatch.py async call wrapper (provider adapters)
- Retry policy: exponential backoff (1s,2s,4s)
- Circuit breaker: CLOSED/OPEN/HALF_OPEN
- Provider health checks used by router (don't route to tripped provider)
- Integration tests with mocked providers

**Acceptance:**
- Third consecutive failure trips breaker and reroutes to fallback model/provider.

---

### Milestone 6 — Unified Pipeline + Daemon (Live by Default)
**Outcome:** End-to-end processing works in live mode; shadow is optional.

**Issues:**
- pipeline.py orchestration (sanitize→classify→budget→route→optimize→dispatch→ledger)
- daemon.py async loop + graceful shutdown
- Config hot reload interval
- Modes: live / shadow / test / debug (shadow logs decisions only)

**Acceptance:**
- Default daemon mode is live-capable (explicitly configured), not shadow-only.

---

### Milestone 7 — OpenClaw Integration Hooks
**Outcome:** OpenClaw can call Token Guardian as a tool/middleware cleanly.

**Issues:**
- openclaw_client.py interface (request/response schema)
- Optional event hook: stream usage events into ledger
- Document integration points + example snippet for OpenClaw agent

**Acceptance:**
- OpenClaw can route queries through Token Guardian and receive (response + telemetry).

---

## GitHub Issues Templates

### Bug
- **Expected:**
- **Actual:**
- **Steps:**
- **Logs:**
- **Config snapshot (redact keys):**

### Feature
- **Problem:**
- **Proposed solution:**
- **Acceptance criteria:**
- **Tests required:**

---

## Definition of Done
- Unit tests for each core module.
- Pipeline integration test (mock providers).
- Doctor command validates config + health.
- Ledger has accurate attribution (tokens/cost/latency/model/label/cache_hit).
- No disabled-by-default core components (classifier/optimizer/pipeline).

---

## Quick "First PR" Plan
1. Implement config loader + schema validation
2. Implement ledger + CLI status/report
3. Add classifier + router + tests
4. Wire pipeline in shadow mode for a day (logs only)
5. Turn on live dispatch with circuit breaker + budget guard
