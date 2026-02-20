#!/usr/bin/env python3
"""
OpenClaw Client for Token Guardian

Polls OpenClaw for session token data and model usage.
"""

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional


class OpenClawClient:
    """Client to fetch session data from OpenClaw."""
    
    def __init__(self):
        self.last_total_tokens = 0
    
    def get_sessions(self) -> List[Dict]:
        """Fetch active sessions from OpenClaw."""
        try:
            result = subprocess.run(
                ["npx", "openclaw", "sessions", "--json"],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                return data.get("sessions", [])
        except Exception as e:
            print("[ERROR] Failed to fetch sessions: {}".format(e))
        return []
    
    def get_active_sessions(self) -> List[Dict]:
        """Get sessions with token usage."""
        sessions = self.get_sessions()
        return [s for s in sessions if s.get("totalTokens", 0) > 0]
    
    def poll_for_updates(self) -> Dict:
        """
        Poll OpenClaw for session updates.
        
        Returns: dict with token data aggregated by model
        """
        sessions = self.get_active_sessions()
        
        total_tokens = sum(s.get("totalTokens", 0) for s in sessions)
        by_model = {}
        
        for session in sessions:
            model = session.get("model", "unknown")
            tokens = session.get("totalTokens", 0)
            if model not in by_model:
                by_model[model] = 0
            by_model[model] += tokens
        
        # Calculate new tokens since last poll
        new_tokens = 0
        if self.last_total_tokens > 0:
            new_tokens = total_tokens - self.last_total_tokens
        
        self.last_total_tokens = total_tokens
        
        return {
            "total_tokens": total_tokens,
            "new_tokens": max(0, new_tokens),
            "session_count": len(sessions),
            "by_model": by_model,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "sessions": sessions
        }


if __name__ == "__main__":
    client = OpenClawClient()
    print("Testing OpenClaw Client...")
    
    data = client.poll_for_updates()
    print("Total tokens: {}".format(data["total_tokens"]))
    print("New tokens: {}".format(data["new_tokens"]))
    print("By model: {}".format(data["by_model"]))
    print("Active sessions: {}".format(data["session_count"]))
