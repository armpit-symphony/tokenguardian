#!/usr/bin/env python3
"""
Real-Time Proof-of-Work Test for Token Guardian v0.1.0 Isolated Instance
Runs 30 prompts across categories and captures routing decisions.
"""
import sys
import json
import os
from datetime import datetime
from pathlib import Path

# Add tokenguardian to path
sys.path.insert(0, '/home/sparky/.openclaw/workspace/tokenguardian')

from src.core.pipeline import create_pipeline

# Test prompt set (30 total)
PROMPTS = [
    # Coding (10)
    ("coding", "Write a Python function to merge two sorted lists"),
    ("coding", "Create a REST API endpoint for user authentication in Node.js"),
    ("coding", "Debug the memory leak in this C++ application"),
    ("coding", "Implement binary search algorithm in Go"),
    ("coding", "Build a Docker container for a Python web application"),
    ("coding", "Write SQL query to find duplicate records"),
    ("coding", "Create a GraphQL resolver for user profiles"),
    ("coding", "Implement rate limiter middleware in Express.js"),
    ("coding", "Refactor this legacy JavaScript code to use async/await"),
    ("coding", "Write unit tests for the authentication module"),
    
    # Data Analysis (10)
    ("data_analysis", "Analyze customer churn trends from the sales dataset"),
    ("data_analysis", "Calculate average order value by customer segment"),
    ("data_analysis", "Find correlation between marketing spend and revenue"),
    ("data_analysis", "Generate quarterly business report from raw data"),
    ("data_analysis", "Create a dashboard showing monthly active users"),
    ("data_analysis", "Calculate conversion funnel drop-off rates"),
    ("data_analysis", "Find top-selling products by region"),
    ("data_analysis", "Analyze A/B test results for the landing page"),
    ("data_analysis", "Calculate customer lifetime value prediction"),
    ("data_analysis", "Generate lead scoring model insights"),
    
    # Creative (5)
    ("creative", "Write a blog post about sustainable energy innovations"),
    ("creative", "Create a short story about a time traveler"),
    ("creative", "Draft marketing copy for a new SaaS product launch"),
    ("creative", "Write a poem about coding in the moonlight"),
    ("creative", "Create a social media caption for a tech conference"),
    
    # Vague/Ambiguous (5)
    ("vague", "Tell me about technology"),
    ("vague", "I have a question about computers"),
    ("vague", "Discuss the future"),
    ("vague", "Something about programming help"),
    ("vague", "Give me information"),
]

def classify_tier(confidence, fallback_reason):
    """Convert confidence/reason to tier label"""
    if confidence >= 0.80:
        return "DIRECT"
    elif "_OK" in fallback_reason:
        return "LOW_BAND_SPECIALIST"
    elif "VAGUE" in fallback_reason:
        return "VAGUE_SAFE_ROUTE"
    elif "VERY_LOW" in fallback_reason:
        return "SAFE_FALLBACK"
    else:
        return "OTHER"

def main():
    OUT_DIR = os.environ.get('OUT_DIR', '/tmp/pow_test')
    OUT = Path(OUT_DIR).expanduser()
    
    # Create output directory if needed
    OUT.mkdir(parents=True, exist_ok=True)
    
    # Initialize pipeline with isolated config
    config_dir = os.environ.get('TG_CONFIG_DIR', '~/.tokenguardian-v010')
    pipeline = create_pipeline(config_dir, shadow_mode=True)
    
    results = []
    categories = {}
    
    print("="*70)
    print("TOKEN GUARDIAN v0.1.0 PROOF-OF-WORK LIVE TEST")
    print("="*70)
    print(f"Config: {config_dir}")
    print(f"Start: {datetime.now().isoformat()}")
    print()
    
    for expected_label, prompt in PROMPTS:
        decision = pipeline.process(prompt)
        tier = classify_tier(decision.confidence, decision.fallback_reason)
        
        result = {
            "timestamp": datetime.now().isoformat(),
            "prompt": prompt,
            "expected_label": expected_label,
            "actual_label": decision.classification,
            "confidence": decision.confidence,
            "tier": tier,
            "selected_model": decision.selected_model,
            "fallback_reason": decision.fallback_reason
        }
        results.append(result)
        
        # Track by category
        cat = expected_label
        if cat not in categories:
            categories[cat] = {"total": 0, "direct": 0, "low_band": 0, "safe": 0, "vague": 0}
        categories[cat]["total"] += 1
        if tier == "DIRECT":
            categories[cat]["direct"] += 1
        elif tier == "LOW_BAND_SPECIALIST":
            categories[cat]["low_band"] += 1
        elif tier in ["SAFE_FALLBACK", "OTHER"]:
            categories[cat]["safe"] += 1
        elif tier == "VAGUE_SAFE_ROUTE":
            categories[cat]["vague"] += 1
        
        # Print progress
        model_short = decision.selected_model.split('/')[-1] if '/' in decision.selected_model else decision.selected_model
        status_icon = "✓" if tier in ["DIRECT", "LOW_BAND_SPECIALIST"] else "⚠"
        print(f"{status_icon} [{decision.confidence:.2f}] {tier[:8]:8} | {decision.classification[:8]:8} | {model_short:12} | {prompt[:50]}")
    
    print()
    print("-"*70)
    print("SUMMARY BY CATEGORY")
    print("-"*70)
    
    for cat, counts in categories.items():
        print(f"{cat:15} | Total: {counts['total']:2} | DIRECT: {counts['direct']:2} | LOW_BAND: {counts['low_band']:2} | SAFE: {counts['safe']:2}")
    
    # Calculate totals
    total = len(results)
    direct = sum(1 for r in results if r["tier"] == "DIRECT")
    low_band = sum(1 for r in results if r["tier"] == "LOW_BAND_SPECIALIST")
    safe_fallback = sum(1 for r in results if r["tier"] == "SAFE_FALLBACK")
    vague = sum(1 for r in results if r["tier"] == "VAGUE_SAFE_ROUTE")
    other = sum(1 for r in results if r["tier"] == "OTHER")
    
    print()
    print("-"*70)
    print("FINAL TOTALS")
    print("-"*70)
    print(f"DIRECT:              {direct:3} ({direct/total*100:.1f}%)")
    print(f"LOW_BAND_SPECIALIST: {low_band:3} ({low_band/total*100:.1f}%)")
    print(f"SAFE_FALLBACK:       {safe_fallback:3} ({safe_fallback/total*100:.1f}%)")
    print(f"VAGUE_SAFE_ROUTE:    {vague:3} ({vague/total*100:.1f}%)")
    print(f"OTHER:               {other:3} ({other/total*100:.1f}%)")
    print(f"TOTAL:               {total}")
    print()
    
    safe_total = safe_fallback + vague + other
    
    # Save JSONL
    jsonl_path = OUT / "live_run_results.jsonl"
    with open(jsonl_path, 'w') as f:
        for r in results:
            f.write(json.dumps(r) + '\n')
    print(f"✓ Results saved: {jsonl_path}")
    
    # Save summary markdown
    md_path = OUT / "summary_table.md"
    with open(md_path, 'w') as f:
        f.write("# Token Guardian v0.1.0 Live Test Summary\n\n")
        f.write(f"**Date:** {datetime.now().isoformat()}\n\n")
        f.write(f"**Config:** {config_dir}\n\n")
        f.write("## Metrics\n\n")
        f.write("| Tier | Count | Percentage |\n")
        f.write("|------|-------|------------|\n")
        f.write(f"| DIRECT | {direct} | {direct/total*100:.1f}% |\n")
        f.write(f"| LOW_BAND_SPECIALIST | {low_band} | {low_band/total*100:.1f}% |\n")
        f.write(f"| SAFE_FALLBACK | {safe_fallback} | {safe_fallback/total*100:.1f}% |\n")
        f.write(f"| VAGUE_SAFE_ROUTE | {vague} | {vague/total*100:.1f}% |\n")
        f.write(f"| OTHER | {other} | {other/total*100:.1f}% |\n")
        f.write(f"| **TOTAL** | {total} | 100% |\n\n")
        f.write("## Category Breakdown\n\n")
        for cat, counts in categories.items():
            f.write(f"### {cat}\n")
            f.write(f"- Total: {counts['total']}\n")
            f.write(f"- DIRECT: {counts['direct']}\n")
            f.write(f"- LOW_BAND_SPECIALIST: {counts['low_band']}\n")
            f.write(f"- SAFE_FALLBACK: {counts['safe']}\n")
            f.write(f"- VAGUE_SAFE_ROUTE: {counts['vague']}\n\n")
        f.write("## Top 10 Examples\n\n")
        for i, r in enumerate(results[:10], 1):
            f.write(f"{i}. **{r['tier']}** [{r['confidence']:.2f}] `{r['prompt'][:60]}`\n")
            f.write(f"   -> {r['actual_label']} via {r['selected_model']}\n\n")
    print(f"✓ Summary saved: {md_path}")
    
    # Save cache listing
    cache_path = OUT / "cache_listing.txt"
    cache_dir = Path.home() / ".tokenguardian-v010" / "cache"
    with open(cache_path, 'w') as f:
        f.write(f"Cache directory: {cache_dir}\n")
        f.write(f"Contents:\n")
        if cache_dir.exists():
            for item in cache_dir.rglob("*"):
                f.write(f"  {item.relative_to(cache_dir)}\n")
        else:
            f.write("  (cache dir not created yet)\n")
    print(f"✓ Cache listing saved: {cache_path}")
    
    print()
    print("="*70)
    print("TEST COMPLETE")
    print("="*70)
    print(f"Output: {OUT}")
    
    return results

if __name__ == "__main__":
    main()
