# Token Guardian

Unified AI cost optimization and intelligent routing system.

## Overview

Token Guardian is a single pipeline that:
- **Classifies** queries with confidence scoring
- **Routes** requests to optimal models with safety fallbacks
- **Optimizes** prompts (refinement, caching, compaction)
- **Monitors** token usage, costs, and efficiency

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│   Query     │────►│  Classifier  │────►│   Router     │
│             │     │ (confidence) │     │ (model sel) │
└─────────────┘     └──────────────┘     └──────┬───────┘
                                                │
                        ┌────────────────────────┘
                        ▼
                ┌──────────────┐     ┌──────────────┐
                │   Optimizer  │────►│   Monitor    │
                │(refine/cache)│     │(tokens/cost) │
                └──────────────┘     └──────────────┘
```

## Quick Start

### Installation

```bash
# Clone and install
git clone <repo>
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
tokenguardian status               # Show status, PID, decisions
tokenguardian restart [--live]     # Restart daemon

# Testing
tokenguardian dry-run [--query "..."]  # Test routing without executing
tokenguardian classify [--query "..."]  # Classify a query
tokenguardian optimize [--query "..."]  # Optimize a prompt

# Monitoring
tokenguardian stats                # Show usage statistics
tokenguardian logs [--tail 20]     # Show daemon logs

# Maintenance
tokenguardian doctor               # Validate configuration
tokenguardian install              # Install CLI
```

## Configuration

### Config Locations

- **User**: `~/.tokenguardian/`
- **System**: `/etc/tokenguardian/` (requires sudo)

User config overrides system config.

### Config Files

#### `guardian.yaml`
Core optimization settings:
- Refinement (fluff word removal)
- Caching (TTL, directory)
- Compaction (batching)
- Audit settings

#### `models.yaml`
Model definitions and costs:
- Model capabilities
- Cost per 1M tokens
- Fallback chain

#### `routing.yaml`
Routing rules:
- Classification → model mappings
- Keywords per classification
- Confidence threshold (default: 0.80)
- Safe fallback model

## Safety Features

### Confidence-Based Fallback

If classification confidence < 0.80 (configurable), the system routes to the safe fallback model instead of the preferred model.

```
Query: "General question about AI"
  Classification: general
  Confidence: 0.10  ← Below threshold!
  ⚠ FALLBACK: Routes to openai/gpt-5-mini instead of preferred minimax/MiniMax-M2.1
```

### Safe Fallback Model

Default: `openai/gpt-5-mini` - a mid-tier model that handles most queries reliably.

## Modes

### Shadow Mode (Default)

- Classifies and routes queries
- Logs all decisions
- **Does NOT modify actual behavior**
- Safe for testing and validation

### Live Mode

- Executes routing decisions
- Applies optimizations
- Modifies actual AI traffic

## Monitoring

### Stats

```
tokenguardian stats
```

Shows:
- Total tokens processed
- Total cost (USD)
- Cache hit rate
- Tokens by model
- Actions breakdown

### Audit Log

Located at `~/.tokenguardian/audit/YYYY-MM-DD.jsonl`

Each entry includes:
- Timestamp
- Classification + confidence
- Model selected
- Fallback trigger
- Token diff
- Cost estimate

## Architecture

```
/tokenguardian/
  tokenguardian.py      # CLI entry point
  install.sh           # Installation script
  README.md            # This file
  config/
    guardian.yaml       # Optimization config
    models.yaml         # Model definitions
    routing.yaml        # Routing rules
  src/
    core/
      classifier.py     # Query classification
      optimizer.py       # Prompt optimization
      monitor.py        # Token monitoring
      pipeline.py       # Unified pipeline
    daemon/
      daemon.py         # Supervisor daemon
```

## Requirements

- Python 3.8+
- PyYAML (optional, for config files)

## License

MIT
