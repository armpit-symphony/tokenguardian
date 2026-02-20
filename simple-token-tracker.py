#!/usr/bin/env python3
"""
Simple Token Tracker - Tracks NEW tokens only using file position
"""
import json
import os
import time
from datetime import datetime
from pathlib import Path

SESSIONS_DIR = Path("/home/sparky/.openclaw/agents/main/sessions")
STATE_FILE = Path("/home/sparky/.tokenguardian/tracker_state.json")
STATS_FILE = Path("/home/sparky/.tokenguardian/stats.json")

def load_state():
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"positions": {}, "started": datetime.now().isoformat()}

def save_state(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f)

def load_stats():
    if STATS_FILE.exists():
        with open(STATS_FILE) as f:
            return json.load(f)
    return {}

def save_stats(stats):
    STATS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATS_FILE, 'w') as f:
        json.dump(stats, f, indent=2)

def get_active_sessions():
    sessions = []
    for f in SESSIONS_DIR.glob("*.jsonl"):
        if ".deleted" not in f.name:
            sessions.append(f)
    return sessions

def extract_data(line):
    try:
        data = json.loads(line)
        if data.get("type") == "message":
            msg = data.get("message", {})
            usage = msg.get("usage", {})
            tokens = usage.get("totalTokens", 0)
            model = msg.get("model", msg.get("provider", "unknown"))
            return tokens, model
    except:
        pass
    return 0, None

def track():
    state = load_state()
    positions = state.get("positions", {})
    
    # Initialize positions for new files only (don't reset existing)
    for f in get_active_sessions():
        if f.name not in positions:
            positions[f.name] = f.stat().st_size
    
    save_state(state)
    
    while True:
        try:
            total_new = 0
            by_model = {}
            
            for session_file in get_active_sessions():
                name = session_file.name
                current_size = session_file.stat().st_size
                last_pos = positions.get(name, current_size)
                
                if current_size > last_pos:
                    with open(session_file, 'r') as f:
                        f.seek(last_pos)
                        new_content = f.read()
                        new_lines = new_content.strip().split('\n') if new_content.strip() else []
                    
                    for line in new_lines:
                        tokens, model = extract_data(line)
                        if tokens > 0:
                            total_new += tokens
                            if model:
                                by_model[model] = by_model.get(model, 0) + tokens
                    
                    positions[name] = current_size
            
            save_state({"positions": positions, "started": state.get("started")})
            
            if total_new > 0:
                # LOAD existing stats (don't overwrite!)
                stats = load_stats()
                
                existing_by_model = stats.get("by_model", {})
                for model, tokens in by_model.items():
                    existing_by_model[model] = existing_by_model.get(model, 0) + tokens
                
                stats["by_model"] = existing_by_model
                stats["tokens_since_start"] = stats.get("tokens_since_start", 0) + total_new
                stats["last_updated"] = datetime.now().isoformat()
                stats["daemon_status"] = "running"
                
                save_stats(stats)
                
                print(f"[{datetime.now().strftime('%H:%M:%S')}] +{total_new} tokens | {by_model}")
            
        except Exception as e:
            print(f"Error: {e}")
        
        time.sleep(3600)  # 1 hour

if __name__ == "__main__":
    print("Token Tracker starting (1-hour interval, with model tracking)...")
    track()
