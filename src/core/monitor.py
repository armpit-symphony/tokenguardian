#!/usr/bin/env python3
"""
Token Guardian Core - Monitor Module
Token tracking, cost estimation, and usage monitoring
"""
import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

import yaml


@dataclass
class TokenRecord:
    """Record of token usage"""
    timestamp: str
    tokens: int
    cost: float
    model: str
    action: str


@dataclass
class UsageStats:
    """Aggregated usage statistics"""
    total_tokens: int = 0
    total_cost: float = 0.0
    cache_hits: int = 0
    cache_misses: int = 0
    requests_processed: int = 0
    refinements: int = 0
    by_model: Dict[str, int] = field(default_factory=dict)
    by_action: Dict[str, int] = field(default_factory=dict)


class Monitor:
    """Token usage monitoring and cost tracking"""
    
    def __init__(self, config_path: str = None):
        """Initialize monitor with configuration"""
        self.config_dir = Path('~/.tokenguardian').expanduser()
        self.stats_file = self.config_dir / 'stats.json'
        self.audit_dir = self.config_dir / 'audit'
        
        # Ensure directories exist
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.audit_dir.mkdir(parents=True, exist_ok=True)
        
        # Load models config for cost calculations
        self.models = {}
        self._load_models()
        
        # Initialize or load stats
        self.stats = self._load_stats()
        
        # Token records
        self.records: List[TokenRecord] = []
    
    def _load_models(self):
        """Load model costs from config"""
        config_path = self.config_dir / 'models.yaml'
        system_path = Path('/etc/tokenguardian/models.yaml')
        
        # Try user config first, then system
        if config_path.exists():
            self._load_models_from_file(str(config_path))
        elif system_path.exists():
            self._load_models_from_file(str(system_path))
        else:
            # Default costs
            self.models = {
                'minimax/MiniMax-M2.1': {'input': 0.50, 'output': 0.50},
                'openai/gpt-5-mini': {'input': 1.50, 'output': 6.00},
                'xai/grok-4': {'input': 3.00, 'output': 15.00},
                'openai/gpt-5.2': {'input': 10.00, 'output': 30.00},
            }
    
    def _load_models_from_file(self, path: str):
        """Load model definitions from YAML"""
        try:
            with open(path, 'r') as f:
                config = yaml.safe_load(f)
            
            if 'models' in config:
                for model_name, model_config in config['models'].items():
                    cost = model_config.get('cost', {'input': 1.0, 'output': 1.0})
                    self.models[model_name] = {
                        'input': cost.get('input', 1.0),
                        'output': cost.get('output', 1.0)
                    }
                    
        except Exception as e:
            print(f"[WARN] Failed to load models from {path}: {e}")
    
    def _load_stats(self) -> UsageStats:
        """Load stats from file"""
        if self.stats_file.exists():
            try:
                with open(self.stats_file, 'r') as f:
                    data = json.load(f)
                
                return UsageStats(
                    total_tokens=data.get('total_tokens', 0),
                    total_cost=data.get('estimated_cost', 0.0),
                    cache_hits=data.get('cache_hits', 0),
                    requests_processed=data.get('requests_processed', 0)
                )
            except Exception:
                pass
        
        return UsageStats()
    
    def _save_stats(self):
        """Save stats to file"""
        data = {
            'last_updated': datetime.now().isoformat(),
            'total_tokens': self.stats.total_tokens,
            'estimated_cost': self.stats.total_cost,
            'cache_hits': self.stats.cache_hits,
            'requests_processed': self.stats.requests_processed,
            'by_model': self.stats.by_model,
            'by_action': self.stats.by_action
        }
        
        with open(self.stats_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def estimate_cost(self, tokens: int, model: str, is_output: bool = False) -> float:
        """Estimate cost for token usage"""
        if model not in self.models:
            # Default cost
            return tokens * 0.00001
        
        model_costs = self.models[model]
        rate = model_costs.get('output' if is_output else 'input', 1.0)
        
        return tokens * rate / 1_000_000
    
    def record_usage(self, 
                    tokens: int, 
                    model: str, 
                    action: str = 'unknown',
                    is_output: bool = False):
        """Record token usage"""
        cost = self.estimate_cost(tokens, model, is_output)
        
        # Update stats
        self.stats.total_tokens += tokens
        self.stats.total_cost += cost
        self.stats.requests_processed += 1
        
        # Track by model
        if model not in self.stats.by_model:
            self.stats.by_model[model] = 0
        self.stats.by_model[model] += tokens
        
        # Track by action
        if action not in self.stats.by_action:
            self.stats.by_action[action] = 0
        self.stats.by_action[action] += 1
        
        # Record
        record = TokenRecord(
            timestamp=datetime.now().isoformat(),
            tokens=tokens,
            cost=cost,
            model=model,
            action=action
        )
        self.records.append(record)
        
        # Save periodically (every 10 records)
        if len(self.records) % 10 == 0:
            self._save_stats()
            self._write_audit_record(record)
    
    def record_cache_hit(self):
        """Record a cache hit"""
        self.stats.cache_hits += 1
        self._save_stats()
    
    def _write_audit_record(self, record: TokenRecord):
        """Write single audit record"""
        audit_file = self.audit_dir / f"{datetime.now().strftime('%Y-%m-%d')}.jsonl"
        
        with open(audit_file, 'a') as f:
            f.write(json.dumps({
                'timestamp': record.timestamp,
                'tokens': record.tokens,
                'cost': record.cost,
                'model': record.model,
                'action': record.action
            }) + '\n')
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current statistics"""
        return {
            'total_tokens': self.stats.total_tokens,
            'total_cost': self.stats.total_cost,
            'cache_hits': self.stats.cache_hits,
            'requests': self.stats.requests_processed,
            'by_model': self.stats.by_model,
            'by_action': self.stats.by_action,
            'last_updated': datetime.now().isoformat()
        }
    
    def get_efficiency_report(self) -> Dict[str, Any]:
        """Generate efficiency report"""
        total = self.stats.total_tokens
        refined = self.stats.by_action.get('refined', 0)
        cached = self.stats.by_action.get('cached', 0)
        
        cache_rate = (self.stats.cache_hits / self.stats.requests_processed * 100) if self.stats.requests_processed > 0 else 0
        
        return {
            'total_tokens_processed': total,
            'refinements': refined,
            'cache_hits': self.stats.cache_hits,
            'cache_rate_percent': f"{cache_rate:.1f}%",
            'total_cost_usd': f"${self.stats.total_cost:.6f}",
            'tokens_per_request': f"{total / max(self.stats.requests_processed, 1):.1f}"
        }


def get_monitor_stats(config_dir: str = None) -> Dict[str, Any]:
    """Convenience function to get monitor stats"""
    monitor = Monitor(config_dir)
    return monitor.get_stats()


if __name__ == '__main__':
    # Test monitor
    monitor = Monitor()
    
    # Record some test data
    monitor.record_usage(100, 'xai/grok-4', 'refined')
    monitor.record_usage(50, 'openai/gpt-5-mini', 'routed')
    monitor.record_usage(200, 'minimax/MiniMax-M2.1', 'cached')
    monitor.record_cache_hit()
    
    print("Monitor Test Results")
    print("=" * 80)
    print("\nCurrent Stats:")
    stats = monitor.get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    print("\nEfficiency Report:")
    report = monitor.get_efficiency_report()
    for key, value in report.items():
        print(f"  {key}: {value}")
