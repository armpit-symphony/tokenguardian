#!/usr/bin/env python3
"""
Token Guardian Daily Usage Report Generator
Work Order: #TG-BILLING-PROFILES

Generates daily usage report with billing profile columns:
- billed_cost (actual incremental cost)
- payg_equivalent_cost (OpenClaw estimate)
- cost_source
"""

import json
import glob
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.billing import BillingResolver


def generate_daily_report(date: str = None, output_dir: str = None):
    """
    Generate daily usage report for a specific date.
    
    Args:
        date: Date in YYYY-MM-DD format (defaults to today UTC)
        output_dir: Output directory for report
    """
    if date is None:
        date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    
    if output_dir is None:
        # If TG_CONFIG_DIR is set (isolated instances), write reports under its reports/ dir
        import os
        tg_dir = os.environ.get('TG_CONFIG_DIR')
        if tg_dir:
            output_dir = Path(tg_dir) / 'reports'
        else:
            output_dir = Path.home() / ".tokenguardian" / "default" / "data"
    
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize billing resolver
    billing = BillingResolver()
    
    # Aggregate usage by provider/model
    usage = {}
    
    for filepath in glob.glob("/home/sparky/.openclaw/agents/main/sessions/*.jsonl"):
        if filepath.endswith('.deleted.') or filepath.endswith('.lock'):
            continue
        
        with open(filepath, 'r') as f:
            for line in f:
                try:
                    data = json.loads(line)
                    if data.get('type') != 'message':
                        continue
                    
                    msg = data.get('message', {})
                    timestamp = data.get('timestamp', '')
                    
                    # Check if date matches
                    if not timestamp.startswith(date):
                        continue
                    
                    # Only process entries with usage data
                    u = msg.get('usage', {})
                    if not u or 'cost' not in u:
                        continue
                    
                    provider = msg.get('provider', 'unknown')
                    model = msg.get('model', 'unknown')
                    key = (provider, model)
                    
                    if key not in usage:
                        usage[key] = {
                            'events': [],
                            'requests': 0,
                            'input_tokens': 0,
                            'output_tokens': 0,
                            'cache_tokens': 0,
                            'billed_cost': 0.0,
                            'payg_equivalent_cost': 0.0,
                            'cost_sources': set()
                        }
                    
                    # Resolve billing
                    resolved = billing.resolve_cost(provider, model, u)
                    
                    usage[key]['events'].append(resolved)
                    usage[key]['requests'] += 1
                    usage[key]['input_tokens'] += u.get('input', 0)
                    usage[key]['output_tokens'] += u.get('output', 0)
                    usage[key]['cache_tokens'] += u.get('cacheRead', 0) + u.get('cacheWrite', 0)
                    
                    if resolved['billed_cost'] is not None:
                        usage[key]['billed_cost'] += resolved['billed_cost']
                    if resolved['payg_equivalent_cost'] is not None:
                        usage[key]['payg_equivalent_cost'] += resolved['payg_equivalent_cost']
                    usage[key]['cost_sources'].add(resolved['cost_source'])
                    
                except json.JSONDecodeError:
                    continue
    
    # Generate markdown report
    output_file = output_dir / f"DAILY_USAGE_{date}.md"
    
    with open(output_file, 'w') as f:
        f.write(f"# Token Guardian - Daily Model Usage Report\n")
        f.write(f"# Date: {date} UTC\n")
        f.write(f"# Generated: {datetime.now(timezone.utc).isoformat()}\n")
        f.write(f"\n")
        f.write("## Summary\n")
        f.write(f"\n")
        f.write("| Metric | Value |\n")
        f.write("|--------|-------|\n")
        
        total_requests = sum(u['requests'] for u in usage.values())
        total_input = sum(u['input_tokens'] for u in usage.values())
        total_output = sum(u['output_tokens'] for u in usage.values())
        total_cache = sum(u['cache_tokens'] for u in usage.values())
        total_billed = sum(u['billed_cost'] for u in usage.values())
        total_payg = sum(u['payg_equivalent_cost'] for u in usage.values())
        
        f.write(f"| Total Requests | {total_requests} |\n")
        f.write(f"| Total Input Tokens | {total_input:,} |\n")
        f.write(f"| Total Output Tokens | {total_output:,} |\n")
        f.write(f"| Total Cache Tokens | {total_cache:,} |\n")
        f.write(f"| Billed Cost (Incremental) | ${total_billed:.5f} |\n")
        f.write(f"| PAYG Equivalent Cost | ${total_payg:.5f} |\n")
        f.write(f"| Cost Source | subscription + openclaw_estimate |\n")
        f.write(f"\n")
        f.write("## Billing Notes\n")
        f.write(f"\n")
        f.write("- **billed_cost**: Actual incremental cost (0 for subscription providers like MiniMax)\n")
        f.write("- **payg_equivalent_cost**: What this usage would cost under PAYG rates (from OpenClaw)\n")
        f.write("- **MiniMax**: Subscription bucket (coding_plan) - billed_cost = $0.00\n")
        f.write(f"\n")
        f.write("## Usage by Provider/Model\n")
        f.write(f"\n")
        f.write("| provider | model | requests | input_tokens | output_tokens | cache_tokens | billed_cost | payg_equivalent_cost | cost_source |\n")
        f.write("|----------|-------|----------|--------------|---------------|--------------|-------------|---------------------|-------------|\n")
        
        for (provider, model), stats in sorted(usage.items()):
            cost_source = ' + '.join(stats['cost_sources']) if stats['cost_sources'] else 'unknown'
            f.write(f"| {provider} | {model} | {stats['requests']} | {stats['input_tokens']:,} | {stats['output_tokens']:,} | {stats['cache_tokens']:,} | ${stats['billed_cost']:.5f} | ${stats['payg_equivalent_cost']:.5f} | {cost_source} |\n")
        
        f.write("|----------|-------|----------|--------------|---------------|--------------|-------------|---------------------|-------------|\n")
        f.write(f"| **TOTAL** | | **{total_requests}** | **{total_input:,}** | **{total_output:,}** | **{total_cache:,}** | **${total_billed:.5f}** | **${total_payg:.5f}** | |\n")
        f.write(f"\n")
        f.write("## Methodology\n")
        f.write(f"\n")
        f.write(f"- **Source**: OpenClaw session JSONL files\n")
        f.write(f"- **Date Filter**: {date} UTC\n")
        f.write(f"- **Billing Resolution**: Via config/billing.yaml\n")
        f.write(f"- **PAYG Rates**: OpenClaw usage.cost.total (internal estimate)\n")
        f.write(f"\n")
    
    print(f"Report generated: {output_file}")
    return str(output_file)


if __name__ == '__main__':
    date = sys.argv[1] if len(sys.argv) > 1 else None
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None
    generate_daily_report(date, output_dir)
