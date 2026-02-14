#!/usr/bin/env python3
"""
Token Guardian Daemon - Native Telemetry Collector
Reads OpenClaw session data and tracks real token usage + savings
"""
import json
import logging
import os
import signal
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
import threading

# Configure logging - use TG_CONFIG_DIR if set, else default
import os
if 'TG_CONFIG_DIR' in os.environ:
    LOG_DIR = Path(os.environ['TG_CONFIG_DIR']) / 'logs'
else:
    LOG_DIR = Path.home() / '.tokenguardian' / 'logs'
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'daemon.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('daemon')


@dataclass
class TelemetryRecord:
    """Single telemetry record from OpenClaw"""
    timestamp: str
    model: str
    provider: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost: float
    cache_read_tokens: int = 0
    
    def to_dict(self) -> Dict:
        return {
            'timestamp': self.timestamp,
            'model': self.model,
            'provider': self.provider,
            'prompt_tokens': self.prompt_tokens,
            'completion_tokens': self.completion_tokens,
            'total_tokens': self.total_tokens,
            'cost': self.cost,
            'cache_read_tokens': self.cache_read_tokens
        }


@dataclass
class RoutingRecord:
    """Routing decision record"""
    timestamp: str
    query: str
    label: str
    confidence: float
    tier: str  # DIRECT, LOW_BAND, SAFE
    selected_model: str
    fallback_reason: str
    prompt_tokens: int
    completion_tokens: int
    estimated_cost: float
    cost_avoided: float = 0.0
    
    def to_dict(self) -> Dict:
        return {
            'timestamp': self.timestamp,
            'query': self.query[:200] if self.query else '',
            'label': self.label,
            'confidence': self.confidence,
            'tier': self.tier,
            'selected_model': self.selected_model,
            'fallback_reason': self.fallback_reason,
            'prompt_tokens': self.prompt_tokens,
            'completion_tokens': self.completion_tokens,
            'estimated_cost': self.estimated_cost,
            'cost_avoided': self.cost_avoided
        }


@dataclass
class StatsRollup:
    """Rolling 24-hour statistics"""
    period_start: str
    period_end: str
    total_queries: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    total_cost_avoided: float = 0.0
    cache_hits: int = 0
    by_model: Dict[str, int] = field(default_factory=dict)
    by_label: Dict[str, int] = field(default_factory=dict)
    by_tier: Dict[str, int] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            'period_start': self.period_start,
            'period_end': self.period_end,
            'total_queries': self.total_queries,
            'total_tokens': self.total_tokens,
            'total_cost': round(self.total_cost, 6),
            'total_cost_avoided': round(self.total_cost_avoided, 6),
            'cache_hits': self.cache_hits,
            'by_model': self.by_model,
            'by_label': self.by_label,
            'by_tier': self.by_tier
        }


class ModelCosts:
    """Model cost configuration"""
    COSTS = {
        # Provider: (input_cost_per_1M, output_cost_per_1M)
        'minimax': {'input': 0.50, 'output': 0.50},  # MiniMax-M2.1
        'openai': {'input': 1.50, 'output': 6.00},   # GPT-5 Mini
        'xai': {'input': 3.00, 'output': 15.00},     # Grok-4
        'anthropic': {'input': 3.00, 'output': 15.00},  # Claude
    }
    
    # Baseline costs (what we'd pay without optimization)
    BASELINE = {
        'minimax': {'input': 0.50, 'output': 0.50},
        'openai': {'input': 1.50, 'output': 6.00},
        'xai': {'input': 3.00, 'output': 15.00},
        'anthropic': {'input': 3.00, 'output': 15.00},
    }
    
    # Preferred models per category (cheapest capable)
    PREFERRED = {
        'simple_qa': ('minimax', 'MiniMax-M2.1'),
        'creative': ('openai', 'GPT-5 Mini'),
        'coding': ('xai', 'Grok-4'),
        'data_analysis': ('xai', 'Grok-4'),
        'reasoning': ('xai', 'Grok-4'),
        'general': ('minimax', 'MiniMax-M2.1'),
    }
    
    @classmethod
    def get_cost(cls, provider: str, prompt_tokens: int, completion_tokens: int) -> float:
        """Calculate cost for a request"""
        costs = cls.COSTS.get(provider, cls.COSTS['openai'])
        input_cost = (prompt_tokens / 1_000_000) * costs['input']
        output_cost = (completion_tokens / 1_000_000) * costs['output']
        return input_cost + output_cost
    
    @classmethod
    def get_baseline_cost(cls, provider: str, prompt_tokens: int, completion_tokens: int) -> float:
        """Calculate baseline cost (what we'd pay without optimization)"""
        costs = cls.BASELINE.get(provider, cls.BASELINE['openai'])
        input_cost = (prompt_tokens / 1_000_000) * costs['input']
        output_cost = (completion_tokens / 1_000_000) * costs['output']
        return input_cost + output_cost


class OpenClawTelemetry:
    """Read OpenClaw session telemetry"""
    
    def __init__(self, session_path: str = None):
        self.session_path = session_path or os.environ.get(
            'OPENCLAW_SESSION',
            str(Path.home() / '.openclaw' / 'agents' / 'main' / 'sessions')
        )
        self._last_position = 0
        self._session_files: Dict[str, int] = {}
        self._discover_session_files()
    
    def _discover_session_files(self):
        """Find active session files and initialize positions from file sizes"""
        session_dir = Path(self.session_path)
        if not session_dir.exists():
            logger.warning(f"Session directory not found: {session_dir}")
            return
        
        for f in session_dir.glob('*.jsonl'):
            if not f.name.endswith('.deleted'):
                # Initialize from actual file size (skip existing content)
                self._session_files[str(f)] = f.stat().st_size
                logger.info(f"Found session file: {f.name} (position: {f.stat().st_size})")
    
    def read_new_records(self) -> List[TelemetryRecord]:
        """Read new telemetry records from session files"""
        records = []
        
        for session_file, last_pos in self._session_files.items():
            try:
                file_size = Path(session_file).stat().st_size
                if last_pos >= file_size:
                    # No new content
                    continue
                
                with open(session_file, 'r') as f:
                    f.seek(last_pos)
                    new_content = f.read()
                    new_pos = f.tell()
                    
                    if not new_content.strip():
                        continue
                    
                    for line in new_content.strip().split('\n'):
                        if line:
                            record = self._parse_line(line, session_file)
                            if record:
                                records.append(record)
                    
                    self._session_files[session_file] = new_pos
                    
            except Exception as e:
                logger.error(f"Error reading {session_file}: {e}")
        
        return records
    
    def _parse_line(self, line: str, session_file: str) -> Optional[TelemetryRecord]:
        """Parse a single JSONL line"""
        try:
            data = json.loads(line)
            
            # Only process assistant messages with usage data
            if data.get('type') != 'message':
                return None
            
            msg = data.get('message', {})
            if not isinstance(msg, dict):
                return None
            
            # Check if this is an assistant response (has usage)
            usage = msg.get('usage', {})
            if not usage:
                return None
            
            # Extract provider and model - they exist as separate fields
            provider = msg.get('provider', 'unknown')
            model = msg.get('model', 'unknown')
            
            # Fallback to parsing 'api' field if provider/model not present
            api_raw = msg.get('api', '')
            if provider == 'unknown' and isinstance(api_raw, str) and api_raw:
                if '/' in api_raw:
                    parts = api_raw.split('/')
                    provider = parts[0] if len(parts) > 1 else 'unknown'
                    model = api_raw
                else:
                    provider = api_raw.replace('-messages', '').replace('-completions', '')
                    model = msg.get('model', 'unknown')
            
            # Extract timestamp
            timestamp = data.get('timestamp', datetime.now().isoformat())
            
            # Extract token usage
            prompt_tokens = usage.get('input', 0)
            completion_tokens = usage.get('output', 0)
            cache_read = usage.get('cacheRead', 0)
            total_tokens = usage.get('totalTokens', prompt_tokens + completion_tokens)
            cost = usage.get('cost', {}).get('total', 0.0)
            
            # Extract user query from parent message
            query = self._extract_query(data, session_file)
            
            return TelemetryRecord(
                timestamp=timestamp,
                model=model,
                provider=provider,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                cost=cost,
                cache_read_tokens=cache_read
            )
            
        except json.JSONDecodeError:
            return None
        except Exception as e:
            logger.debug(f"Parse error: {e}")
            return None
    
    def _extract_query(self, assistant_msg: dict, session_file: str) -> str:
        """Extract the user query that prompted this response"""
        try:
            parent_id = assistant_msg.get('parentId')
            if not parent_id:
                return ""
            
            # Read backward in session file to find parent
            with open(session_file, 'r') as f:
                lines = f.readlines()
            
            for i, line in enumerate(lines):
                if parent_id in line:
                    data = json.loads(line)
                    if data.get('type') == 'message':
                        msg = data.get('message', {})
                        if msg.get('role') == 'user':
                            content = msg.get('content', [])
                            if isinstance(content, list):
                                for item in content:
                                    if item.get('type') == 'text':
                                        return item.get('text', '')[:500]
                            elif isinstance(content, str):
                                return content[:500]
                    break
            
            return ""
            
        except Exception:
            return ""


class TokenGuardianDaemon:
    """
    Native Token Guardian Daemon
    
    Reads OpenClaw telemetry, classifies queries, and tracks savings.
    """
    
    def __init__(self, 
                 instance: str = 'default',
                 poll_interval: int = 30,
                 config_dir: str = None):
        """
        Initialize daemon
        
        Args:
            instance: Instance name (default, v010)
            poll_interval: Seconds between telemetry polls
            config_dir: Configuration directory
        """
        self.instance = instance
        self.poll_interval = poll_interval
        self.config_dir = Path(config_dir) if config_dir else Path.home() / '.tokenguardian'
        self.instance_dir = self.config_dir / instance
        
        # Create instance directories
        self.data_dir = self.instance_dir / 'data'
        self.run_dir = self.instance_dir / 'run'
        self.log_dir = self.instance_dir / 'logs'
        
        for d in [self.data_dir, self.run_dir, self.log_dir]:
            d.mkdir(parents=True, exist_ok=True)
        
        # Files
        self.telemetry_file = self.data_dir / 'telemetry.jsonl'
        self.routing_file = self.data_dir / 'routing.jsonl'
        self.stats_file = self.data_dir / 'stats_rollup.json'
        self.lock_file = self.run_dir / 'daemon.lock'
        
        # State
        self._running = False
        self._shutdown = False
        self._last_poll = datetime.now()
        
        # Telemetry reader
        self.telemetry = OpenClawTelemetry()
        
        # Stats
        self.stats = StatsRollup(
            period_start=datetime.now().isoformat(),
            period_end=datetime.now().isoformat()
        )
        
        # Classifier - optional, for routing decisions (disabled for now)
        self.classifier = None
        logger.info("Classifier disabled (telemetry collection only)")
        
        # Setup signal handlers
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, shutting down...")
        self._shutdown = True
        self.stop()
    
    def acquire_lock(self) -> bool:
        """Acquire daemon lock, return True if acquired"""
        try:
            with open(self.lock_file, 'w') as f:
                f.write(str(os.getpid()))
            return True
        except Exception:
            return False
    
    def release_lock(self):
        """Release daemon lock"""
        try:
            if self.lock_file.exists():
                self.lock_file.unlink()
        except Exception:
            pass
    
    def is_locked(self) -> bool:
        """Check if daemon is already running"""
        if not self.lock_file.exists():
            return False
        
        try:
            with open(self.lock_file, 'r') as f:
                pid = int(f.read().strip())
            os.kill(pid, 0)  # Check if process exists
            return True
        except (ValueError, ProcessLookupError):
            self.lock_file.unlink()
            return False
    
    def start(self):
        """Start the daemon"""
        if self.is_locked():
            logger.error("Daemon already running")
            return False
        
        if not self.acquire_lock():
            logger.error("Could not acquire lock")
            return False
        
        self._running = True
        logger.info(f"Starting Token Guardian daemon (instance: {self.instance})")
        
        # Load existing stats
        self._load_stats()
        
        # Main loop
        while not self._shutdown:
            try:
                self._poll()
                time.sleep(self.poll_interval)
            except Exception as e:
                logger.error(f"Poll error: {e}")
                time.sleep(5)  # Brief pause on error
        
        self._running = False
        self.release_lock()
        logger.info("Daemon stopped")
    
    def stop(self):
        """Stop the daemon"""
        self._shutdown = True
    
    def _poll(self):
        """Poll telemetry and process records"""
        now = datetime.now()
        
        # Read new telemetry
        records = self.telemetry.read_new_records()
        
        if not records:
            return
        
        logger.info(f"Processing {len(records)} new telemetry records")
        
        for record in records:
            self._process_record(record)
        
        # Update stats
        self.stats.period_end = datetime.now().isoformat()
        self._save_stats()
        
        # Log hourly summary
        if (now - self._last_poll).total_seconds() >= 3600:
            self._log_hourly_summary()
            self._last_poll = now
    
    def _process_record(self, record: TelemetryRecord):
        """Process a single telemetry record"""
        # Append to telemetry file
        with open(self.telemetry_file, 'a') as f:
            f.write(json.dumps(record.to_dict()) + '\n')
        
        # Update stats
        self.stats.total_queries += 1
        self.stats.total_tokens += record.total_tokens
        self.stats.total_cost += record.cost
        self.stats.cache_hits += 1 if record.cache_read_tokens > 0 else 0
        
        # By model
        model_key = f"{record.provider}/{record.model}"
        self.stats.by_model[model_key] = self.stats.by_model.get(model_key, 0) + 1
        
        # Classify query and create routing record
        if self.classifier:
            query = ""  # Would need to extract from session
            result = self.classifier.classify(query)
            
            # Determine tier
            if result.confidence >= 0.80:
                tier = "DIRECT"
            elif result.confidence >= 0.45:
                tier = "LOW_BAND"
            else:
                tier = "SAFE"
            
            # Calculate cost avoided (compared to most expensive model)
            baseline = ModelCosts.get_baseline_cost(
                record.provider,
                record.prompt_tokens,
                record.completion_tokens
            )
            avoided = baseline - record.cost
            
            routing = RoutingRecord(
                timestamp=record.timestamp,
                query=query,
                label=result.label,
                confidence=result.confidence,
                tier=tier,
                selected_model=model_key,
                fallback_reason="",
                prompt_tokens=record.prompt_tokens,
                completion_tokens=record.completion_tokens,
                estimated_cost=record.cost,
                cost_avoided=avoided
            )
            
            # Append routing record
            with open(self.routing_file, 'a') as f:
                f.write(json.dumps(routing.to_dict()) + '\n')
            
            # Update by_label and by_tier
            self.stats.by_label[result.label] = self.stats.by_label.get(result.label, 0) + 1
            self.stats.by_tier[tier] = self.stats.by_tier.get(tier, 0) + 1
            
            # Update cost avoided
            self.stats.total_cost_avoided += avoided
    
    def _load_stats(self):
        """Load existing stats from file"""
        if self.stats_file.exists():
            try:
                with open(self.stats_file, 'r') as f:
                    data = json.load(f)
                    self.stats = StatsRollup(
                        period_start=data.get('period_start', datetime.now().isoformat()),
                        period_end=data.get('period_end', datetime.now().isoformat()),
                        total_queries=data.get('total_queries', 0),
                        total_tokens=data.get('total_tokens', 0),
                        total_cost=data.get('total_cost', 0.0),
                        total_cost_avoided=data.get('total_cost_avoided', 0.0),
                        cache_hits=data.get('cache_hits', 0),
                        by_model=data.get('by_model', {}),
                        by_label=data.get('by_label', {}),
                        by_tier=data.get('by_tier', {})
                    )
                logger.info(f"Loaded stats: {self.stats.total_queries} queries")
            except Exception as e:
                logger.warning(f"Could not load stats: {e}")
    
    def _save_stats(self):
        """Save stats to file"""
        try:
            with open(self.stats_file, 'w') as f:
                json.dump(self.stats.to_dict(), f, indent=2)
        except Exception as e:
            logger.error(f"Could not save stats: {e}")
    
    def _log_hourly_summary(self):
        """Log hourly summary with money metrics"""
        logger.info("=" * 60)
        logger.info("HOURLY SUMMARY")
        logger.info(f"  Queries: {self.stats.total_queries}")
        logger.info(f"  Total Cost: ${self.stats.total_cost:.6f}")
        logger.info(f"  Cost Avoided: ${self.stats.total_cost_avoided:.6f}")
        logger.info(f"  By Model: {self.stats.by_model}")
        logger.info("=" * 60)
    
    def get_stats(self, hours: int = 24) -> Dict:
        """Get stats for specified hours"""
        # Filter stats by time if needed
        return self.stats.to_dict()
    
    def get_money_number(self, hours: int = 1) -> Dict:
        """Get the 'money number' - cost avoided for time period"""
        return {
            'period_hours': hours,
            'cost_avoided': round(self.stats.total_cost_avoided, 6),
            'total_cost': round(self.stats.total_cost, 6),
            'queries': self.stats.total_queries,
            'savings_rate': round(
                (self.stats.total_cost_avoided / (self.stats.total_cost + 0.000001)) * 100, 2
            ) if self.stats.total_cost > 0 else 0
        }


def main():
    """Main entry point for daemon"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Token Guardian Daemon')
    parser.add_argument('command', choices=['start', 'stop', 'status', 'stats'],
                       help='Command to run')
    parser.add_argument('--instance', '-i', default='default',
                       help='Instance name (default, v010)')
    parser.add_argument('--poll', '-p', type=int, default=30,
                       help='Poll interval in seconds')
    parser.add_argument('--hours', type=int, default=24,
                       help='Hours for stats (default: 24)')
    
    args = parser.parse_args()
    
    config_dir = os.environ.get('TG_CONFIG_DIR')
    
    daemon = TokenGuardianDaemon(
        instance=args.instance,
        poll_interval=args.poll,
        config_dir=config_dir
    )
    
    if args.command == 'start':
        daemon.start()
    elif args.command == 'stop':
        daemon.stop()
    elif args.command == 'status':
        if daemon.is_locked():
            print(f"Daemon running (instance: {args.instance})")
            stats = daemon.get_stats(args.hours)
            print(f"  Queries: {stats['total_queries']}")
            print(f"  Total Cost: ${stats['total_cost']:.6f}")
            print(f"  Cost Avoided: ${stats['total_cost_avoided']:.6f}")
        else:
            print("Daemon not running")
    elif args.command == 'stats':
        stats = daemon.get_stats(args.hours)
        money = daemon.get_money_number(args.hours)
        print(f"\n=== Token Guardian Stats ({args.hours}h) ===")
        print(f"Total Queries: {stats['total_queries']}")
        print(f"Total Tokens: {stats['total_tokens']}")
        print(f"Total Cost: ${stats['total_cost']:.6f}")
        print(f"Cost Avoided: ${stats['total_cost_avoided']:.6f}")
        print(f"Cache Hits: {stats['cache_hits']}")
        print(f"\n--- By Model ---")
        for model, count in stats.get('by_model', {}).items():
            print(f"  {model}: {count}")
        print(f"\n--- By Label ---")
        for label, count in stats.get('by_label', {}).items():
            print(f"  {label}: {count}")
        print(f"\n--- Savings ---")
        print(f"Cost Avoided ({args.hours}h): ${money['cost_avoided']:.6f}")
        print(f"Savings Rate: {money['savings_rate']}%")


if __name__ == '__main__':
    main()
