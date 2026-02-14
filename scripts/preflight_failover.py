#!/usr/bin/env python3
"""
Token Guardian Pre-Flight Failover Wrapper
Work Order: #TG-REAL-FAILOVER

Usage:
    python3 preflight_failover.py --lane main --timeout 60 --provider minimax -- echo "test"
"""

import sys
import os
import signal
import argparse
import subprocess
import time
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.circuit_breaker import CircuitBreaker, BreakerState, get_breaker


def parse_args():
    """Parse wrapper arguments."""
    parser = argparse.ArgumentParser(
        description='Pre-flight failover wrapper for OpenClaw'
    )
    parser.add_argument(
        '--lane', 
        required=True,
        help='Lane name (main, session:main, session:agent:main:main, nested)'
    )
    parser.add_argument(
        '--timeout',
        type=int,
        default=60,
        help='Timeout for provider calls (default: 60s)'
    )
    parser.add_argument(
        '--provider',
        default='minimax',
        help='Primary provider to check (default: minimax)'
    )
    parser.add_argument(
        '--fallback',
        default='openai/gpt-5-mini',
        help='Fallback provider (default: openai/gpt-5-mini)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Check only, do not execute'
    )
    
    # Everything after -- is the command
    if '--' in sys.argv:
        idx = sys.argv.index('--')
        known, command = sys.argv[:idx], sys.argv[idx+1:]
    else:
        known, command = sys.argv[:1], sys.argv[1:]
    
    args = parser.parse_args(known)
    args.command = command
    
    return args


def check_breaker(provider: str) -> dict:
    """Check circuit breaker state for a provider."""
    breaker = get_breaker(
        provider=provider,
        failure_threshold=2,
        cooldown_seconds=900,
        failover_provider='openai/gpt-5-mini'
    )
    can_proceed = breaker.can_proceed()
    
    return {
        'allowed': can_proceed.allowed,
        'state': can_proceed.state.value,
        'reason': can_proceed.reason,
        'should_failover': not can_proceed.allowed,
        'failover_provider': can_proceed.failover_provider
    }


def emit_failover_log(lane: str, from_provider: str, to_provider: str, reason: str):
    """Emit the required failover log line."""
    log_line = f"PROVIDER_FAILOVER: lane={lane} from={from_provider} to={to_provider} reason={reason}"
    print(f"[FAILOVER] {log_line}", flush=True)
    return log_line


def main():
    """Main pre-flight wrapper entry point."""
    args = parse_args()
    
    if not args.command:
        # Dry-run check only
        print(f"[PREFLIGHT] Lane: {args.lane}")
        print(f"[PREFLIGHT] Primary provider: {args.provider}")
        print(f"[PREFLIGHT] Fallback provider: {args.fallback}")
        print(f"[PREFLIGHT] Mode: DRY-RUN (no command)")
    else:
        print(f"[PREFLIGHT] Lane: {args.lane}")
        print(f"[PREFLIGHT] Primary provider: {args.provider}")
        print(f"[PREFLIGHT] Fallback provider: {args.fallback}")
        print(f"[PREFLIGHT] Command: {' '.join(args.command)}")
    
    # Check circuit breaker
    check_result = check_breaker(args.provider)
    
    print(f"[PREFLIGHT] Breaker state: {check_result['state']}")
    print(f"[PREFLIGHT] Allowed: {check_result['allowed']}")
    
    # Determine if we need failover
    modified_command = list(args.command)
    failover_triggered = False
    reason = "OK"
    
    if check_result['should_failover']:
        failover_triggered = True
        reason = check_result['state']
        
        emit_failover_log(
            lane=args.lane,
            from_provider=args.provider,
            to_provider=args.fallback,
            reason=reason
        )
        
        # Replace provider in command
        for i, arg in enumerate(modified_command):
            if args.provider in arg.lower():
                modified_command[i] = arg.replace(args.provider, args.fallback)
                print(f"[PREFLIGHT] Replaced: {arg} -> {modified_command[i]}")
        
        if '--provider' not in modified_command and '-p' not in modified_command:
            modified_command.extend(['--provider', args.fallback])
    
    if args.dry_run or not args.command:
        print(f"[PREFLIGHT] Dry-run complete")
        return
    
    # Run with timeout
    print(f"[PREFLIGHT] Executing: {' '.join(modified_command)}")
    print(f"[PREFLIGHT] Timeout: {args.timeout}s")
    
    start_time = time.time()
    
    try:
        proc = subprocess.Popen(
            modified_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True
        )
        stdout, stderr = proc.communicate(timeout=args.timeout)
        elapsed = time.time() - start_time
        
        print(f"[PREFLIGHT] Completed in {elapsed:.2f}s (returncode: {proc.returncode})")
        
        if stdout:
            sys.stdout.write(stdout.decode())
        if stderr:
            sys.stderr.write(stderr.decode())
        
        sys.exit(proc.returncode)
        
    except subprocess.TimeoutExpired:
        elapsed = time.time() - start_time
        print(f"[PREFLIGHT] TIMEOUT after {elapsed:.1f}s")
        
        # Record failure
        breaker = get_breaker(
            provider=args.provider,
            failure_threshold=2,
            cooldown_seconds=900,
            failover_provider='openai/gpt-5-mini'
        )
        breaker.record_failure(f"Pre-flight timeout after {args.timeout}s")
        
        emit_failover_log(
            lane=args.lane,
            from_provider=args.provider,
            to_provider=args.fallback,
            reason="TIMEOUT"
        )
        
        sys.exit(1)


if __name__ == '__main__':
    main()
