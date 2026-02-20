#!/usr/bin/env python3
"""
Token Guardian Ingestor - Session JSONL Tailer

Tails OpenClaw session JSONL files and ingests LLM usage data.
- Maintains offsets to avoid duplicates
- Parses usage records from session files
- Emits REQ_DONE logs and updates TG stats
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

# Paths
SESSIONS_DIRS = [
    Path("/home/sparky/.openclaw/agents/main/sessions"),
    Path("/home/sparky/.openclaw/agents/sentinel/sessions"),
    Path("/home/sparky/.openclaw/agents/builder/sessions"),
    Path("/home/sparky/.openclaw/agents/strategist/sessions"),
]
OFFSETS_FILE = Path("/home/sparky/.tokenguardian/state/session_offsets.json")
STATS_FILE = Path("/home/sparky/.tokenguardian/stats.json")


def load_offsets() -> Dict[str, int]:
    """Load byte offsets for each session file."""
    if OFFSETS_FILE.exists():
        try:
            return json.loads(OFFSETS_FILE.read_text())
        except:
            pass
    return {}


def save_offsets(offsets: Dict[str, int]):
    """Save byte offsets."""
    OFFSETS_FILE.parent.mkdir(parents=True, exist_ok=True)
    OFFSETS_FILE.write_text(json.dumps(offsets, indent=2))


def load_stats() -> Dict:
    """Load TG stats."""
    if STATS_FILE.exists():
        try:
            return json.loads(STATS_FILE.read_text())
        except:
            pass
    return {"total_tokens": 0, "decisions": 0, "requests": 0}


def save_stats(stats: Dict):
    """Save TG stats."""
    STATS_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATS_FILE.write_text(json.dumps(stats, indent=2))


def get_model_for_session(session_path: Path, current_model: Dict[str, str]) -> str:
    """Get current model for session from cached state or file."""
    # Check if we have a cached model
    if session_path.name in current_model:
        return current_model[session_path.name]
    
    # Parse file to find latest model_change
    try:
        with open(session_path, 'r') as f:
            for line in f:
                try:
                    record = json.loads(line)
                    if record.get("type") == "model_change":
                        model = record.get("modelId", "unknown")
                        current_model[session_path.name] = model
                        return model
                except:
                    pass
    except:
        pass
    
    return current_model.get(session_path.name, "unknown")


def ingest_session(session_path: Path, offsets: Dict[str, int], current_model: Dict[str, str]) -> Dict:
    """
    Ingest new lines from a session file.
    
    Returns:
        Dict with 'new_lines', 'tokens_added', 'requests_added'
    """
    result = {"new_lines": 0, "tokens_added": 0, "requests_added": 0}
    
    try:
        size = session_path.stat().st_size
        start_offset = offsets.get(str(session_path), 0)
        
        if start_offset >= size:
            return result
        
        with open(session_path, 'r') as f:
            f.seek(start_offset)
            
            for line in f:
                result["new_lines"] += 1
                try:
                    record = json.loads(line)
                    record_type = record.get("type")
                    
                    # Track current model
                    if record_type == "model_change":
                        current_model[session_path.name] = record.get("modelId", "unknown")
                        continue
                    
                    # Process message with usage
                    if record_type == "message":
                        # Usage may be at top level or inside 'message' object
                        usage = record.get("usage") or record.get("message", {}).get("usage", {})
                        total_tokens = usage.get("totalTokens", 0)
                        input_tokens = usage.get("input", 0)
                        output_tokens = usage.get("output", 0)
                        
                        if total_tokens > 0:
                            # Emit REQ_DONE
                            ts = datetime.now(timezone.utc).isoformat()
                            # Provider may be at top level or inside 'message'
                            provider = record.get("provider") or record.get("message", {}).get("provider", "unknown")
                            model = record.get("model") or record.get("message", {}).get("model", current_model.get(session_path.name, "unknown"))
                            session_id = session_path.stem
                            
                            req_line = (
                                f"REQ_DONE: ts={ts} lane={session_id} "
                                f"provider={provider} model={model} "
                                f"input_tokens={input_tokens} output_tokens={output_tokens} "
                                f"total_tokens={total_tokens}"
                            )
                            print(req_line)
                            
                            result["tokens_added"] += total_tokens
                            result["requests_added"] += 1
                            
                except json.JSONDecodeError:
                    pass
            
            # Update offset
            new_offset = f.tell() if 'f' in dir() else size
            offsets[str(session_path)] = size  # Full file
    
    except Exception as e:
        print(f"ERROR ingesting {session_path}: {e}", file=sys.stderr)
    
    return result


def ingest_all():
    """Main ingestion loop - watches ALL session directories."""
    offsets = load_offsets()
    current_model: Dict[str, str] = {}
    stats = load_stats()
    
    total_tokens_before = stats.get("total_tokens", 0)
    total_requests_before = stats.get("requests", 0)
    
    all_tokens = 0
    all_requests = 0
    session_files_scanned = 0
    total_lines_scanned = 0
    tokens_by_lane: Dict[str, int] = {}
    tokens_by_agent: Dict[str, int] = {}
    
    # Process all session directories
    for sessions_dir in SESSIONS_DIRS:
        if not sessions_dir.exists():
            continue
            
        for session_path in sorted(sessions_dir.glob("*.jsonl")):
            # Skip lock files and deleted files
            if ".deleted." in session_path.name or session_path.name.endswith(".lock"):
                continue
                
            session_files_scanned += 1
            size = session_path.stat().st_size
            start_offset = offsets.get(str(session_path), 0)
            
            # Get agent name from parent directory
            agent_name = sessions_dir.parent.name
            
            if start_offset < size:
                result = ingest_session(session_path, offsets, current_model)
                all_tokens += result["tokens_added"]
                all_requests += result["requests_added"]
                total_lines_scanned += result["new_lines"]
                
                # Track tokens by lane
                lane = session_path.stem
                if result["tokens_added"] > 0:
                    tokens_by_lane[lane] = tokens_by_lane.get(lane, 0) + result["tokens_added"]
                    tokens_by_agent[agent_name] = tokens_by_agent.get(agent_name, 0) + result["tokens_added"]
            else:
                # Still count lines even if no new data
                try:
                    with open(session_path, 'r') as f:
                        lines = f.readlines()
                        total_lines_scanned += len(lines)
                except:
                    pass
    
    # Save offsets
    save_offsets(offsets)
    
    # Catch-up report
    tokens_before_run = total_tokens_before
    tokens_after_run = total_tokens_before + all_tokens
    is_catchup = (tokens_after_run - tokens_before_run) > 0 and (tokens_after_run - tokens_before_run) > (all_tokens if all_tokens > 0 else 0)
    
    print("\n=== CATCH-UP REPORT ===")
    print(f"session_files_scanned: {session_files_scanned}")
    print(f"new_lines_processed: {total_lines_scanned}")
    
    # Top 3 lanes by tokens
    if tokens_by_lane:
        top_lanes = sorted(tokens_by_lane.items(), key=lambda x: x[1], reverse=True)[:3]
        print("top_3_lanes_by_tokens:")
        for i, (lane, tokens) in enumerate(top_lanes, 1):
            print(f"  {i}. {lane}: {tokens:,}")
    else:
        print("top_3_lanes_by_tokens: none")
    
    # Tokens by agent
    if tokens_by_agent:
        print("\ntokens_by_agent:")
        for agent, tokens in sorted(tokens_by_agent.items(), key=lambda x: x[1], reverse=True):
            print(f"  - {agent}: {tokens:,}")
    
    # Determine if backlog catch-up occurred
    # Catch-up = processed more than just new data (multiple files/lines)
    backlog_catchup = "YES" if (session_files_scanned > 1 or total_lines_scanned > 100) else "NO"
    print(f"\nbacklog_catchup: {backlog_catchup}")
    print("=== END CATCH-UP ===\n")
    
    # Update stats (always write timestamp for freshness)
    stats["total_tokens"] = total_tokens_before + all_tokens
    stats["requests"] = total_requests_before + all_requests
    stats["decisions"] = stats.get("decisions", 0) + all_requests
    stats["last_ingest_ts"] = datetime.now(timezone.utc).isoformat()
    save_stats(stats)
    
    if all_tokens > 0:
        print(f"STATS_UPDATE: tokens={stats['total_tokens']} requests={stats['requests']}")
    else:
        print(f"STATS_PULSE: tokens={stats['total_tokens']} requests={stats['requests']} (no new data)")
    
    return {"tokens": all_tokens, "requests": all_requests}


def run_once():
    """Run ingestion once (for driver)."""
    result = ingest_all()
    print(f"INGEST_DONE: tokens={result['tokens']} requests={result['requests']}")
    return result


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--once":
        run_once()
    else:
        # Run continuously - watching ALL session directories
        dirs_str = ", ".join([str(d) for d in SESSIONS_DIRS])
        print("INGESTOR_START: watching all session directories:")
        for d in SESSIONS_DIRS:
            print(f"  - {d}")
        while True:
            try:
                ingest_all()
            except Exception as e:
                print(f"INGESTOR_ERROR: {e}")
            import time
            time.sleep(30)
