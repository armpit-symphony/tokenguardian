#!/bin/bash
# Token Guardian v0.1.0 Isolated Instance Wrapper
# Usage: ./run_v010_isolated.sh [command]
#
# Commands:
#   test        Run 223-query test (default)
#   doctor      Validate configuration
#   status      Show daemon status
#   start       Start daemon (shadow mode)
#   stop        Stop daemon
#   dry-run     Test routing for a query

set -e

# Configuration
TG_HOME="$HOME/.tokenguardian-v010"
TG_WORKSPACE="/home/sparky/.openclaw/workspace/tokenguardian"
TG_CONFIG="$TG_HOME/config"

export TG_CONFIG_DIR="$TG_CONFIG"
export TG_CACHE_DIR="$TG_HOME/cache"
export TG_AUDIT_DIR="$TG_HOME/audit"
export TG_LOG_DIR="$TG_HOME/logs"

COMMAND="${1:-test}"

cd "$TG_WORKSPACE"

case "$COMMAND" in
    test)
        echo "Running 223-query test with isolated config..."
        python3 << 'PYEOF'
import sys
sys.path.insert(0, '.')
from src.core.pipeline import create_pipeline
import os

# Read test file
with open('test_shadow_225.py') as f:
    content = f.read()
import re
match = re.search(r'TEST_QUERIES\s*=\s*\[(.*?)\]', content, re.DOTALL)
TEST_QUERIES = []
for line in match.group(1).split('\n'):
    line = line.strip().strip(',').strip("'").strip('"')
    if line and len(line) > 3:
        TEST_QUERIES.append(line)

config_dir = os.environ.get('TG_CONFIG_DIR', '~/.tokenguardian-v010')
pipeline = create_pipeline(config_dir, shadow_mode=True)

direct = low_band = very_low = vague = 0
for q in TEST_QUERIES:
    decision = pipeline.process(q)
    if decision.confidence >= 0.80:
        direct += 1
    elif 'VAGUE' in decision.fallback_reason:
        vague += 1
    elif '_OK' in decision.fallback_reason:
        low_band += 1
    elif 'VERY_LOW' in decision.fallback_reason:
        very_low += 1

print()
print("="*60)
print("TOKEN GUARDIAN v0.1.0 ISOLATED INSTANCE")
print("="*60)
print(f"Config: {config_dir}")
print()
print("METRICS:")
print(f"  SAFE_FALLBACK:        {very_low + vague} ({very_low} VERY_LOW + {vague} VAGUE)")
print(f"  LOW_BAND_SPECIALIST:  {low_band}")
print(f"  DIRECT:               {direct}")
print(f"  SAFE_FALLBACK %:      {(very_low + vague)/len(TEST_QUERIES)*100:.1f}%")
print()
if (very_low + vague)/len(TEST_QUERIES) <= 0.30:
    print("PASS: SAFE_FALLBACK <= 30%")
else:
    print("FAIL: SAFE_FALLBACK > 30%")
PYEOF
        ;;
    doctor)
        echo "Validating isolated configuration..."
        python3 tokenguardian.py doctor
        ;;
    status)
        echo "Daemon status..."
        python3 tokenguardian.py status
        ;;
    start)
        echo "Starting daemon (shadow mode)..."
        python3 tokenguardian.py start --live
        ;;
    stop)
        echo "Stopping daemon..."
        python3 tokenguardian.py stop
        ;;
    dry-run)
        QUERY="${2:-Write a regex to validate email}"
        echo "Testing: $QUERY"
        python3 tokenguardian.py dry-run --query "$QUERY"
        ;;
    help|--help|-h)
        echo "Token Guardian v0.1.0 Isolated Instance"
        echo ""
        echo "Usage: $0 [command]"
        echo ""
        echo "Commands:"
        echo "  test        Run 223-query test (default)"
        echo "  doctor      Validate configuration"
        echo "  status      Show daemon status"
        echo "  start       Start daemon"
        echo "  stop        Stop daemon"
        echo "  dry-run     Test routing for a query"
        echo ""
        echo "Environment:"
        echo "  TG_HOME=$TG_HOME"
        ;;
    *)
        echo "Unknown command: $COMMAND"
        echo "Use: $0 help"
        exit 1
        ;;
esac
