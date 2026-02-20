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

def get_active_sessions():
    """Get active session files"""
    sessions = []
    for f in SESSIONS_DIR.glob("*.jsonl"):
        if ".deleted" not in f.name:
            sessions.append(f)
    return sessions

def count_tokens_in_line(line):
    try:
        data = json.loads(line)
        if data.get("type") == "message":
            msg = data.get("message", {})
            usage = msg.get("usage", {})
            return usage.get("totalTokens", 0)
    except:
        pass
    return 0

def track():
    state = load_state()
    positions = state.get("positions", {})
    
    # Initialize positions for new files
    for f in get_active_sessions():
        if f.name not in positions:
            positions[f.name] = f.stat().st_size
    
    save_state(state)
    
    while True:
        try:
            total_new = 0
            
            for session_file in get_active_sessions():
                name = session_file.name
                current_size = session_file.stat().st_size
                last_pos = positions.get(name, current_size)
                
                # Only read new bytes
                if current_size > last_pos:
                    with open(session_file, 'r') as f:
                        f.seek(last_pos)
                        new_content = f.read()
                        new_lines = new_content.strip().split('\n') if new_content.strip() else []
                    
                    tokens = sum(count_tokens_in_line(line) for line in new_lines)
                    if tokens > 0:
                        total_new += tokens
                        print(f"[{name[:8]}...] +{tokens}")
                    
                    positions[name] = current_size
            
            save_state({"positions": positions, "started": state.get("started")})
            
            if total_new > 0:
                stats = {
                    "last_updated": datetime.now().isoformat(),
                    "tokens_since_start": total_new,
                    "daemon_status": "running"
                }
                with open(STATS_FILE, 'w') as f:
                    json.dump(stats, f, indent=2)
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Total new: +{total_new}")
            
        except Exception as e:
            print(f"Error: {e}")
        
        time.sleep(30)

if __name__ == "__main__":
    print("Token Tracker starting (position-based)...")
    track()
