# Token Guardian

Unified AI cost optimization, intelligent routing, and token monitoring for OpenClaw-powered systems.

## Overview

Token Guardian is a single pipeline that:
- **Routes** queries intelligently with the Agent Router
- **Optimizes** prompts (refinement, caching, compaction)
- **Monitors** token usage, costs, and efficiency in real-time

### Key Differentiator: Agent Router Integration

Unlike generic cost trackers, Token Guardian integrates directly with OpenClaw's **Agent Router**:
- Routes queries based on complexity and confidence scoring
- Automatic fallback to safe models when confidence is low
- Unified observability from query → routing → cost tracking
- OpenClaw-native integration (not a separate dashboard)

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│   Query     │────►│  Agent Router │────►│   Model      │
│             │     │(intelligent)  │     │  Selection   │
└─────────────┘     └──────┬───────┘     └──────┬───────┘
                            │
                            ▼
                    ┌──────────────┐     ┌──────────────┐
                    │   Monitor    │────►│   Cost      │
                    │(tokens/cost) │     │  Tracking   │
                    └──────────────┘     └──────────────┘
```

## What Makes Token Guardian Different?

| Feature | Generic Cost Trackers | Token Guardian |
|---------|---------------------|---------------|
| OpenClaw Integration | ❌ | ✅ Native |
| Agent Router | ❌ | ✅ Built-in |
| Real-time Routing | ❌ | ✅ Per-query |
| Confidence Fallback | ❌ | ✅ Automatic |
| Shadow Mode Testing | ⚠️ Partial | ✅ Full pipeline |
| Cost Attribution | Basic | ✅ Per-agent, per-session |

## Use Cases

- **Cost Control**: Stop runaway API bills with budget alerts
- **Routing Optimization**: Route simple queries to cheap models, complex to capable ones
- **Observability**: See exactly what your agents are spending on
- **Fallback Safety**: Low confidence = automatic safe model selection

## Quick Start

### Installation

```bash
# Clone and install
git clone https://github.com/armpit-symphony/tokenguardian.git
cd tokenguardian
./install.sh

# Validate
tokenguardian doctor
```

### Commands

```bash
# Daemon management
tokenguardian start [--live]       # Start daemon (default: shadow mode)
tokenguardian stop                 # Stop daemon
tokenguardian status              # Show status, PID, decisions
tokenguardian restart [--live]    # Restart daemon

# Testing
tokenguardian dry-run [--query "..."]  # Test routing without executing
tokenguardian classify [--query "..."] # Classify a query
tokenguardian optimize [--query "..."] # Optimize a prompt

# Monitoring
tokenguardian stats                # Show usage statistics
tokenguardian logs [--tail 20]     # Show daemon logs

# Maintenance
tokenguardian doctor               # Validate configuration
tokenguardian install              # Install CLI
```

## Architecture

```
/tokenguardian/
  tokenguardian.py      # CLI entry point
  install.sh           # Installation script
  README.md            # This file
  config/
    guardian.yaml       # Optimization config
    models.yaml         # Model definitions & costs
    routing.yaml        # Routing rules
  src/
    core/
      classifier.py     # Query classification
      optimizer.py       # Prompt optimization
      monitor.py        # Token monitoring
      pipeline.py       # Unified pipeline
      router.py         # Agent Router integration
    daemon/
      daemon.py         # Supervisor daemon
```

## Configuration

### Config Locations

- **User**: `~/.tokenguardian/`
- **System**: `/etc/tokenguardian/` (requires sudo)

User config overrides system config.

### `models.yaml`

```yaml
models:
  MiniMax-M2.1:
    provider: minimax
    cost:
      input: 15.00  # per 1M tokens
      output: 60.00
    tier: budget
  
  grok-4:
    provider: xai
    cost:
      input: 0.20
      output: 0.50
    tier: premium

  gpt-5-mini:
    provider: openai
    cost:
      input: 0.15
      output: 0.60
    tier: fallback
```

### `routing.yaml`

```yaml
routing:
  default_fallback: openai/gpt-5-mini
  confidence_threshold: 0.80
  
routes:
  - classification: coding
    preferred: minimax/MiniMax-M2.1
    fallback: openai/gpt-5-mini
  
  - classification: reasoning
    preferred: xai/grok-4
    fallback: openai/gpt-5-mini
```

## OpenClaw Integration

Token Guardian is designed for OpenClaw deployments:

```python
# In your OpenClaw agent
from tokenguardian import AgentRouter

router = AgentRouter()

# Automatic routing based on query type
result = router.route(query, user_tier="premium")
# Returns: {model, confidence, fallback_triggered}
```

### Supported Providers

- **MiniMax M2.1** - Budget primary
- **xAI Grok-4** - Premium reasoning
- **OpenAI GPT-5** - Safe fallback
- **Anthropic Claude** - Coming soon

## Monitoring & Stats

```
$ tokenguardian stats

╔════════════════════════════════════════════╗
║           TOKEN GUARDIAN STATS           ║
╚════════════════════════════════════════════╝

  Total Tokens: 122,080,018
  Estimated Cost: $1,945.72

  By Model:
    minimax/MiniMax-M2.1: 121,558,544 (99.1%)
    openai/gpt-5-mini: 1,156,514 (0.9%)
    xai/grok-4: 40,374 (0.03%)
```

## Safety Features

### Confidence-Based Fallback

If classification confidence < 0.80, the system routes to the safe fallback model:

```
Query: "What is 2+2?"
  Classification: general
  Confidence: 0.10  ← Below threshold!
  ⚠ FALLBACK: Routes to gpt-5-mini instead of MiniMax-M2.1
```

### Shadow Mode

Test routing without modifying actual behavior:
- Classifies queries
- Logs routing decisions
- Shows what _would_ have happened
- Safe for production validation

## License

MIT

---

## Production Setup (Recommended: systemd daemon only)

This runs Token Guardian LIVE and survives reboots without running burn-in driver.

### Quick Start

```bash
cd /home/sparky/.openclaw/workspace/tokenguardian
source venv/bin/activate
python3 tokenguardian.py doctor
```

### Create service user

```bash
sudo useradd --system --no-create-home --shell /usr/sbin/nologin tokenguardian
```

### Install app

```bash
sudo mkdir -p /opt/tokenguardian
sudo chown -R tokenguardian:tokenguardian /opt/tokenguardian
# Copy repo contents into /opt/tokenguardian
```

### Setup venv

```bash
cd /opt/tokenguardian
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Install systemd service

```bash
sudo cp systemd/tokenguardian.service /etc/systemd/system/tokenguardian.service
sudo systemctl daemon-reload
sudo systemctl enable tokenguardian
sudo systemctl start tokenguardian
```

### Check status/logs

```bash
sudo systemctl status tokenguardian --no-pager
sudo journalctl -u tokenguardian -n 200 --no-pager
```

---

## Disable Burn-in Driver (Keep daemon running)

Burn-in driver is a test harness and can latch into `DRIVER_HALTED`. For production, disable it:

```bash
bash scripts/disable_burnin_driver.sh
```

Then run the daemon normally:

```bash
cd /home/sparky/.openclaw/workspace/tokenguardian
source venv/bin/activate
python3 tokenguardian.py start --live
```

See BURNIN_DRIVER.md and TROUBLESHOOTING.md for details.
