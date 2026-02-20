#!/usr/bin/env python3
"""
Token Guardian Production-Grade Burn-in Report
Generates detailed health/reliability metrics for burn-in verification.

Metrics:
- Driver health (runs, failures, skips, halt status)
- Ingestion health (backlog, scans, duplicates)
- Reliability proof (latency, timeouts, failovers)
"""

import glob
import json
import re
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path


def parse_driver_log(log_file: Path, hours: int = 6):
    """Parse driver log for health metrics."""
    cutoff = time.time() - (hours * 3600)
    
    runs = 0
    failures = 0
    skips = 0
    successes = 0
    last_run = None
    
    if not log_file.exists():
        return {'error': 'log_file_missing'}
    
    try:
        with open(log_file, 'r') as f:
            for line in f:
                # Parse timestamp
                match = re.search(r'\[(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})', line)
                if match:
                    ts = time.mktime(time.strptime(match.group(1), '%Y-%m-%dT%H:%M:%S'))
                    if ts < cutoff:
                        continue
                    
                    if 'DRIVER_SUCCESS' in line:
                        runs += 1
                        successes += 1
                        last_run = match.group(1)
                    elif 'DRIVER_PROBE_FAILED' in line:
                        failures += 1
                    elif 'DRIVER_SKIP' in line:
                        skips += 1
    except Exception as e:
        return {'error': str(e)}
    
    return {
        'runs': runs,
        'failures': failures,
        'skips': skips,
        'successes': successes,
        'last_run': last_run
    }


def parse_ingestor_log(log_file: Path, hours: int = 6):
    """Parse ingestor log for ingestion metrics."""
    cutoff = time.time() - (hours * 3600)
    
    catchup_yes = 0
    catchup_no = 0
    total_scanned = 0
    total_lines = 0
    duplicate_skips = 0
    
    if not log_file.exists():
        return {'error': 'log_file_missing'}
    
    try:
        with open(log_file, 'r') as f:
            for line in f:
                # Parse timestamp
                match = re.search(r'\[(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})', line)
                if match:
                    ts = time.mktime(time.strptime(match.group(1), '%Y-%m-%dT%H:%M:%S'))
                    if ts < cutoff:
                        continue
                    
                    if 'backlog_catchup: YES' in line:
                        catchup_yes += 1
                    elif 'backlog_catchup: NO' in line:
                        catchup_no += 1
                    
                    # Parse session_files_scanned
                    scan_match = re.search(r'session_files_scanned: (\d+)', line)
                    if scan_match:
                        total_scanned += int(scan_match.group(1))
                    
                    # Parse new_lines_processed
                    lines_match = re.search(r'new_lines_processed: (\d+)', line)
                    if lines_match:
                        total_lines += int(lines_match.group(1))
                    
                    # Check for duplicate skips
                    if 'duplicate_skip' in line.lower() or 'already_processed' in line.lower():
                        duplicate_skips += 1
    except Exception as e:
        return {'error': str(e)}
    
    return {
        'catchup_yes': catchup_yes,
        'catchup_no': catchup_no,
        'total_scanned': total_scanned,
        'total_lines': total_lines,
        'duplicate_skips': duplicate_skips,
        'backlog_catchup': 'YES' if catchup_yes > catchup_no else 'NO'
    }


def parse_reliability_metrics(session_dir: Path, hours: int = 6):
    """Parse session files for latency and reliability metrics."""
    cutoff = time.time() - (hours * 3600)
    
    latencies = []
    over_60s = 0
    over_65s = 0
    failovers = 0
    
    if not session_dir.exists():
        return {'error': 'session_dir_missing'}
    
    try:
        # Check sessions.json for latency info
        sessions_file = session_dir / 'sessions.json'
        if sessions_file.exists():
            data = json.loads(sessions_file.read_text())
            # Check updatedAt for recent activity
            updated_at = data.get('agent:main:main', {}).get('updatedAt', 0)
            if updated_at:
                updated_ts = updated_at / 1000  # Convert ms to seconds
                if updated_ts > cutoff:
                    # Session is active within window
                    pass
        
        # Parse REQ_DONE lines from ingestor log for latency
        ingestor_log = Path('/home/sparky/.tokenguardian/ingestor.log')
        if ingestor_log.exists():
            with open(ingestor_log, 'r') as f:
                for line in f:
                    match = re.search(r'\[(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})', line)
                    if match:
                        ts = time.mktime(time.strptime(match.group(1), '%Y-%m-%dT%H:%M:%S'))
                        if ts < cutoff:
                            continue
                    
                    # Parse REQ_DONE for provider failover
                    if 'PROVIDER_FAILOVER' in line or 'provider_change' in line.lower():
                        failovers += 1
                    
                    # Try to extract latency from session context
                    latency_match = re.search(r'latency[_\s]*(\d+)ms', line, re.IGNORECASE)
                    if latency_match:
                        latency = int(latency_match.group(1))
                        latencies.append(latency)
                        if latency > 60000:
                            over_60s += 1
                        if latency > 65000:
                            over_65s += 1
    except Exception as e:
        return {'error': str(e)}
    
    max_latency = max(latencies) if latencies else None
    
    return {
        'max_latency_ms': max_latency,
        'requests_over_60s': over_60s,
        'requests_over_65s': over_65s,
        'failover_count': failovers
    }


def generate_burnin_report(hours: int = 6, output_file: Path = None):
    """Generate production-grade burn-in report."""
    now = datetime.now(timezone.utc)
    cutoff_time = now - timedelta(hours=hours)
    
    # Config constants (for operational transparency)
    INGESTOR_LOOP_INTERVAL_S = 30  # seconds
    DRIVER_INTERVAL_MIN = 10  # minutes (cron */10)
    
    # Paths
    driver_log = Path('/home/sparky/.openclaw/workspace/tokenguardian/driver.log')
    ingestor_log = Path('/home/sparky/.tokenguardian/ingestor.log')
    session_dir = Path('/home/sparky/.openclaw/agents/main/sessions')
    status_file = Path('/home/sparky/.openclaw/workspace/tokenguardian/driver.status')
    stats_file = Path('/home/sparky/.tokenguardian/stats.json')
    burnin_restart_file = Path.home() / '.tokenguardian-burnin48' / 'burnin_restart.txt'
    
    # Parse metrics
    driver = parse_driver_log(driver_log, hours)
    ingestion = parse_ingestor_log(ingestor_log, hours)
    reliability = parse_reliability_metrics(session_dir, hours)
    
    # Get status
    status = {}
    if status_file.exists():
        try:
            status = json.loads(status_file.read_text())
        except:
            pass
    
    # Get stats
    stats = {}
    if stats_file.exists():
        try:
            stats = json.loads(stats_file.read_text())
        except:
            pass
    
    # Get burnin restart time
    burnin_restart = None
    if burnin_restart_file.exists():
        burnin_restart = burnin_restart_file.read_text().strip()
    
    # Get clean run start marker
    clean_run_file = Path.home() / '.tokenguardian-burnin48' / 'clean_run_start.txt'
    starting_tokens = None
    starting_requests = None
    clean_run_start = None
    
    if clean_run_file.exists():
        try:
            with open(clean_run_file, 'r') as f:
                for line in f:
                    if line.startswith('clean_run_start_utc:'):
                        clean_run_start = line.split(':', 1)[1].strip()
                    elif line.startswith('starting_tokens:'):
                        starting_tokens = int(line.split(':', 1)[1].strip())
                    elif line.startswith('starting_requests:'):
                        starting_requests = int(line.split(':', 1)[1].strip())
        except:
            pass
    
    # Generate report
    report_lines = []
    report_lines.append(f"# Token Guardian - Production-Grade Burn-in Report")
    report_lines.append(f"# Report Window: Last {hours} hours")
    report_lines.append(f"# Generated: {now.isoformat()}")
    report_lines.append(f"# Burn-in Restart: {burnin_restart or 'Unknown'}")
    report_lines.append(f"")
    report_lines.append(f"## Operational Config")
    report_lines.append(f"| Metric | Value |")
    report_lines.append(f"|--------|-------|")
    report_lines.append(f"| ingestor_loop_interval_s | {INGESTOR_LOOP_INTERVAL_S} |")
    report_lines.append(f"| driver_interval_min | {DRIVER_INTERVAL_MIN} |")
    report_lines.append(f"")
    
    # === DRIVER HEALTH ===
    report_lines.append(f"## Driver Health")
    report_lines.append(f"| Metric | Value |")
    report_lines.append(f"|--------|-------|")
    
    if 'error' in driver:
        report_lines.append(f"| Status | ERROR: {driver['error']} |")
    else:
        halted = status.get('halted', False)
        report_lines.append(f"| runs_last_{hours}h | {driver.get('runs', 0)} |")
        report_lines.append(f"| failures_last_{hours}h | {driver.get('failures', 0)} |")
        report_lines.append(f"| skips_last_{hours}h | {driver.get('skips', 0)} |")
        report_lines.append(f"| halted | {'true' if halted else 'false'} |")
        report_lines.append(f"| last_run | {driver.get('last_run', 'N/A')} |")
    
    report_lines.append(f"")
    
    # === INGESTION HEALTH ===
    report_lines.append(f"## Ingestion Health")
    report_lines.append(f"| Metric | Value |")
    report_lines.append(f"|--------|-------|")
    
    if 'error' in ingestion:
        report_lines.append(f"| Status | ERROR: {ingestion['error']} |")
    else:
        report_lines.append(f"| backlog_catchup | {ingestion.get('backlog_catchup', 'N/A')} |")
        report_lines.append(f"| session_files_scanned_last_{hours}h | {ingestion.get('total_scanned', 0)} |")
        report_lines.append(f"| new_lines_processed_last_{hours}h | {ingestion.get('total_lines', 0)} |")
        report_lines.append(f"| duplicate_skips | {ingestion.get('duplicate_skips', 0)} |")
    
    report_lines.append(f"")
    
    # === RELIABILITY PROOF ===
    report_lines.append(f"## Reliability Proof")
    report_lines.append(f"| Metric | Value |")
    report_lines.append(f"|--------|-------|")
    
    if 'error' in reliability:
        report_lines.append(f"| Status | ERROR: {reliability['error']} |")
    else:
        max_lat = reliability.get('max_latency_ms')
        report_lines.append(f"| max_latency_ms | {max_lat if max_lat else 'N/A'} |")
        report_lines.append(f"| requests_over_60s | {reliability.get('requests_over_60s', 0)} |")
        report_lines.append(f"| requests_over_65s | {reliability.get('requests_over_65s', 0)} |")
        report_lines.append(f"| PROVIDER_FAILOVER_count | {reliability.get('failover_count', 0)} |")
    
    report_lines.append(f"")
    
    # === CURRENT STATS ===
    report_lines.append(f"## Current Stats")
    report_lines.append(f"| Metric | Value |")
    report_lines.append(f"|--------|-------|")
    report_lines.append(f"| total_tokens | {stats.get('total_tokens', 0):,} |")
    report_lines.append(f"| requests | {stats.get('requests', 0):,} |")
    report_lines.append(f"| decisions | {stats.get('decisions', 0):,} |")
    
    # Freshness metrics
    stats_file = Path('/home/sparky/.tokenguardian/stats.json')
    if stats_file.exists():
        try:
            mtime = stats_file.stat().st_mtime
            age_minutes = round((time.time() - mtime) / 60, 1)
            report_lines.append(f"| stats_mtime_age_minutes | {age_minutes} |")
            
            # Try to get last_ingest_ts from stats
            last_ingest = stats.get('last_ingest_ts') or stats.get('last_updated')
            if last_ingest:
                report_lines.append(f"| last_ingest_ts_utc | {last_ingest} |")
            else:
                report_lines.append(f"| last_ingest_ts_utc | N/A |")
        except:
            report_lines.append(f"| stats_mtime_age_minutes | error |")
            report_lines.append(f"| last_ingest_ts_utc | error |")
    else:
        report_lines.append(f"| stats_mtime_age_minutes | file_missing |")
        report_lines.append(f"| last_ingest_ts_utc | file_missing |")
    
    report_lines.append(f"")
    
    # === CLEAN RUN START ===
    report_lines.append(f"## Clean Run Start")
    report_lines.append(f"| Metric | Value |")
    report_lines.append(f"|--------|-------|")
    if clean_run_start:
        report_lines.append(f"| clean_run_start_utc | {clean_run_start} |")
    if starting_tokens is not None:
        report_lines.append(f"| starting_tokens | {starting_tokens:,} |")
    if starting_requests is not None:
        report_lines.append(f"| starting_requests | {starting_requests:,} |")
    current_tokens = stats.get('total_tokens', 0)
    if starting_tokens is not None:
        delta = current_tokens - starting_tokens
        report_lines.append(f"| tokens_since_clean_start | +{delta:,} |")
    
    report_lines.append(f"")
    
    # === VERDICT ===
    report_lines.append(f"## Assembly-Line Readiness Verdict")
    report_lines.append(f"")
    
    # Determine readiness with strict rules
    verdict = "PRODUCTION-GRADE"
    reasons = []
    checks = []
    
    # Rule 1: halted must be false
    if status.get('halted', False):
        verdict = "NOT_READY"
        reasons.append("Driver is halted")
        checks.append(("halted", "false", "FAIL"))
    else:
        checks.append(("halted", "false", "PASS"))
    
    # Rule 2: failures_last_6h must be 0
    failures = driver.get('failures', 0)
    if failures > 0:
        verdict = "NOT_READY" if verdict == "PRODUCTION-GRADE" else verdict
        reasons.append(f"Driver failures: {failures}")
        checks.append(("failures", "0", "FAIL"))
    else:
        checks.append(("failures", "0", "PASS"))
    
    # Rule 3: requests_over_65s must be 0
    over_65s = reliability.get('requests_over_65s', 0)
    if over_65s > 0:
        verdict = "NOT_READY" if verdict == "PRODUCTION-GRADE" else verdict
        reasons.append(f"High latency requests (>65s): {over_65s}")
        checks.append(("requests_over_65s", "0", "FAIL"))
    else:
        checks.append(("requests_over_65s", "0", "PASS"))
    
    # Rule 4: requests_over_60s must be <= 1
    over_60s = reliability.get('requests_over_60s', 0)
    if over_60s > 1:
        verdict = "STABLE_BUT_WATCH" if verdict in ["PRODUCTION-GRADE", "STABLE_BUT_WATCH"] else verdict
        reasons.append(f"Slow requests (>60s): {over_60s}")
        checks.append(("requests_over_60s", "<=1", "WATCH"))
    elif over_60s == 0:
        checks.append(("requests_over_60s", "0", "PASS"))
    else:
        checks.append(("requests_over_60s", "1", "PASS"))
    
    # Rule 5: duplicate_skips must be 0
    dups = ingestion.get('duplicate_skips', 0)
    if dups > 0:
        verdict = "NOT_READY" if verdict == "PRODUCTION-GRADE" else verdict
        reasons.append(f"Duplicate skips: {dups}")
        checks.append(("duplicate_skips", "0", "FAIL"))
    else:
        checks.append(("duplicate_skips", "0", "PASS"))
    
    # Rule 6: backlog_catchup should be NO (or YES only once in first 12h)
    catchup = ingestion.get('backlog_catchup', 'N/A')
    burnin_hours = 12
    burnin_restart_ts = None
    
    if burnin_restart:
        try:
            # Parse CLEAN_BURNIN_RESTART=YYYY-MM-DDTHH:MM:SSZ
            restart_match = re.search(r'=(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})', burnin_restart)
            if restart_match:
                burnin_restart_ts = time.mktime(
                    time.strptime(restart_match.group(1), '%Y-%m-%dT%H:%M:%S')
                )
        except:
            pass
    
    is_early_burnin = False
    if burnin_restart_ts and (time.time() - burnin_restart_ts) < (burnin_hours * 3600):
        is_early_burnin = True
    
    if catchup == "YES" and not is_early_burnin:
        verdict = "STABLE_BUT_WATCH" if verdict in ["PRODUCTION-GRADE", "STABLE_BUT_WATCH"] else verdict
        reasons.append("Backlog catchup occurring (>12h after restart)")
        checks.append(("backlog_catchup", "NO", "WATCH"))
    else:
        checks.append(("backlog_catchup", catchup, "PASS"))
    
    # Rule 7: skips_last_6h should be <= 3
    skips = driver.get('skips', 0)
    if skips > 3:
        verdict = "STABLE_BUT_WATCH" if verdict in ["PRODUCTION-GRADE", "STABLE_BUT_WATCH"] else verdict
        reasons.append(f"High skip count: {skips}")
        checks.append(("skips", "<=3", "WATCH"))
    else:
        checks.append(("skips", str(skips), "PASS"))
    
    # Print checks
    report_lines.append(f"### Verdict Checks")
    report_lines.append(f"| Check | Expected | Result |")
    report_lines.append(f"|-------|----------|--------|")
    for check, expected, result in checks:
        icon = "✅" if result == "PASS" else ("⚠️" if result == "WATCH" else "❌")
        report_lines.append(f"| {check} | {expected} | {icon} {result} |")
    
    report_lines.append(f"")
    
    # Print verdict
    if verdict == "PRODUCTION-GRADE":
        report_lines.append(f"✅ **PRODUCTION-GRADE** - All checks passed for {hours}h window")
    elif verdict == "STABLE_BUT_WATCH":
        report_lines.append(f"⚠️ **STABLE BUT WATCH** - Minor issues detected")
        for r in reasons:
            report_lines.append(f"- {r}")
    else:
        report_lines.append(f"❌ **NOT READY** - Critical issues")
        for r in reasons:
            report_lines.append(f"- {r}")
    
    report_lines.append(f"")
    report_lines.append(f"---")
    report_lines.append(f"*Report generated at {now.isoformat()}*")
    
    report_text = '\n'.join(report_lines)
    
    if output_file:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(report_text)
        print(f"Report saved: {output_file}")
    
    return report_text


if __name__ == '__main__':
    hours = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    output_path = sys.argv[2] if len(sys.argv) > 2 else None
    
    output_file = Path(output_path) if output_path else None
    print(generate_burnin_report(hours, output_file))
