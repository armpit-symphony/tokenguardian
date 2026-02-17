#!/usr/bin/env python3
"""
Token Guardian Daemon - Supervisor Service
Single daemon that manages monitoring, routing, and optimization
"""
import json
import os
import signal
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Dict, List, Optional
import threading

import yaml

# Import metrics
from .metrics import (
    get_metrics, get_content_type,
    update_daemon_info, update_uptime, update_mode,
    track_tokens, track_cost, track_request, track_error,
    daemon_info
)


class MetricsHandler(BaseHTTPRequestHandler):
    """HTTP handler for /metrics endpoint"""
    
    def do_GET(self):
        if self.path == '/metrics':
            self.send_response(200)
            self.send_header('Content-Type', get_content_type())
            self.end_headers()
            self.wfile.write(get_metrics())
        elif self.path == '/health':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'status': 'ok'}).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        """Suppress logging for metrics requests"""
        if args[0].startswith('GET /metrics'):
            return
        print("[HTTP] {}".format(format % args))


def start_metrics_server(port: int = 9090):
    """Start Prometheus metrics HTTP server"""
    server = HTTPServer(('0.0.0.0', port), MetricsHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print("[INFO] Metrics server started on port {}".format(port))
    return server


@dataclass
class DaemonConfig:
    """Daemon configuration - user-writable paths"""
    pid_file: str = '~/.tokenguardian/tokenguardian.pid'
    log_file: str = '~/.tokenguardian/daemon.log'
    config_dir: str = '/etc/tokenguardian'
    user_config_dir: str = '~/.tokenguardian'
    interval: int = 30
    shadow_mode: bool = True
    metrics_port: int = 9090


class TokenGuardianDaemon:
    """Supervisor daemon for Token Guardian"""
    
    def __init__(self, config: DaemonConfig = None):
        """Initialize daemon"""
        self.config = config or DaemonConfig()
        self.running = False
        self.pid = os.getpid()
        
        # Resolve config directories
        self.system_config_dir = Path(self.config.config_dir)
        self.user_config_dir = Path(self.config.user_config_dir).expanduser()
        
        # Ensure directories exist
        self.user_config_dir.mkdir(parents=True, exist_ok=True)
        
        # Pipeline will be initialized when starting
        self.pipeline = None
        self.monitor = None
        self.start_time = None
        
        # Signal handlers
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)
    
    def _handle_shutdown(self, signum, frame):
        """Handle shutdown signals"""
        print("\n[INFO] Received signal {}, shutting down...".format(signum))
        self.running = False
    
    def _load_effective_config(self) -> Dict:
        """Load effective configuration (user overrides system)"""
        config = {}
        
        # Load system config first
        system_guardian = self.system_config_dir / 'guardian.yaml'
        system_models = self.system_config_dir / 'models.yaml'
        system_routing = self.system_config_dir / 'routing.yaml'
        
        # Load user config (overrides)
        user_guardian = self.user_config_dir / 'guardian.yaml'
        user_models = self.user_config_dir / 'models.yaml'
        user_routing = self.user_config_dir / 'routing.yaml'
        
        # Determine which configs exist
        guardian_path = user_guardian if user_guardian.exists() else system_guardian
        models_path = user_models if user_models.exists() else system_models
        routing_path = user_routing if user_routing.exists() else system_routing
        
        return {
            'guardian': str(guardian_path) if guardian_path.exists() else None,
            'models': str(models_path) if models_path.exists() else None,
            'routing': str(routing_path) if routing_path.exists() else None
        }
    
    def _write_pid(self):
        """Write PID file"""
        try:
            with open(self.config.pid_file, 'w') as f:
                f.write(str(self.pid))
        except Exception as e:
            print("[WARN] Could not write PID file: {}".format(e))
    
    def _cleanup_pid(self):
        """Remove PID file"""
        try:
            if Path(self.config.pid_file).exists():
                Path(self.config.pid_file).unlink()
        except Exception:
            pass
    
    def start(self):
        """Start the daemon"""
        if self.running:
            print("[WARN] Daemon already running")
            return
        
        self.running = True
        self.start_time = datetime.now()
        
        # Write PID
        self._write_pid()
        
        print("[INFO] Token Guardian Daemon starting (PID: {})".format(self.pid))
        print("[INFO] Config dir: {}".format(self.user_config_dir))
        print("[INFO] Shadow mode: {}".format(self.config.shadow_mode))
        print("[INFO] Interval: {}s".format(self.config.interval))
        
        # Initialize metrics
        update_daemon_info(version='1.0.0', mode='shadow' if self.config.shadow_mode else 'live')
        update_mode('shadow' if self.config.shadow_mode else 'live')
        
        # Start metrics server
        metrics_port = getattr(self.config, 'metrics_port', 9090)
        self.metrics_server = start_metrics_server(metrics_port)
        
        # Import pipeline and monitor
        from ..core.pipeline import create_pipeline
        from ..core.monitor import Monitor
        
        # Initialize pipeline
        config_paths = self._load_effective_config()
        self.pipeline = create_pipeline(
            str(self.user_config_dir), 
            shadow_mode=self.config.shadow_mode
        )
        
        # Initialize monitor with OpenClaw integration
        self.monitor = Monitor(str(self.user_config_dir))
        
        # Main loop
        cycle = 0
        while self.running:
            try:
                cycle += 1
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                # Update uptime metric
                uptime = (datetime.now() - self.start_time).total_seconds()
                update_uptime(uptime)
                
                # Poll OpenClaw for real token data
                poll_result = self.monitor.update_from_openclaw()
                
                # Get current stats
                stats = self.monitor.get_stats()
                
                # Update metrics from stats
                by_model = stats.get('by_model', {})
                for model, token_count in by_model.items():
                    provider = self._get_provider_for_model(model)
                    track_tokens(model, provider, token_count)
                    # Track cost - simplified calculation
                    cost = self._estimate_cost(model, token_count)
                    if cost > 0:
                        track_cost(model, provider, cost)
                
                # Build status message
                new_tokens = poll_result.get('new_tokens', 0)
                model_str = ", ".join(["{}:{}".format(k, v) for k, v in by_model.items()])
                
                if new_tokens > 0:
                    print("[{}] CYCLE {} | Tokens: {} (+{}) | Cost: ${:.6f} | Models: {}".format(
                        timestamp, cycle, stats['total_tokens'], new_tokens, 
                        stats['total_cost'], model_str))
                else:
                    print("[{}] CYCLE {} | Tokens: {} | Cost: ${:.6f} | Models: {} (no new)".format(
                        timestamp, cycle, stats['total_tokens'], stats['total_cost'], model_str))
                
                # Wait for next cycle
                time.sleep(self.config.interval)
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print("[ERROR] Cycle failed: {}".format(e))
                track_error('daemon', 'internal', type(e).__name__)
                time.sleep(self.config.interval)
        
        self._cleanup_pid()
        print("[INFO] Daemon stopped. Uptime: {}".format(datetime.now() - self.start_time))
    
    def _get_provider_for_model(self, model: str) -> str:
        """Get provider name for a model"""
        # Try to determine provider from model name
        model_lower = model.lower()
        if 'gpt' in model_lower:
            return 'openai'
        elif 'claude' in model_lower:
            return 'anthropic'
        elif 'gemini' in model_lower:
            return 'google'
        elif 'llama' in model_lower or 'mistral' in model_lower:
            return 'self_hosted'
        else:
            return 'unknown'
    
    def _estimate_cost(self, model: str, tokens: int) -> float:
        """Estimate cost for a model (simplified)"""
        # Very rough cost estimates per 1M tokens
        cost_per_million = {
            'gpt-4': 30.0,
            'gpt-4-turbo': 10.0,
            'gpt-3.5-turbo': 0.5,
            'claude-3-opus': 15.0,
            'claude-3-sonnet': 3.0,
            'claude-3-haiku': 0.25,
            'gemini-pro': 0.5,
        }
        
        model_lower = model.lower()
        rate = 1.0  # Default fallback rate
        
        for key, value in cost_per_million.items():
            if key in model_lower:
                rate = value
                break
        
        return (tokens / 1_000_000) * rate
    
    def stop(self):
        """Stop the daemon"""
        self.running = False
    
    def status(self) -> Dict:
        """Get daemon status"""
        # Check if running from PID file
        pid = None
        if Path(self.config.pid_file).exists():
            try:
                with open(self.config.pid_file, 'r') as f:
                    pid = int(f.read().strip())
            except:
                pass
        
        # Check if process is alive
        running = pid and self._is_process_alive(pid)
        
        if not running:
            return {
                'status': 'stopped',
                'pid': pid,
                'mode': 'N/A',
                'config_dir': str(self.user_config_dir)
            }
        
        # Get pipeline status
        mode = 'shadow' if self.config.shadow_mode else 'live'
        
        if self.pipeline:
            status = self.pipeline.get_status()
        else:
            status = {'decisions_logged': 0}
        
        # Check which configs are loaded
        system_loaded = any((self.system_config_dir / cf).exists() for cf in ['guardian.yaml', 'models.yaml', 'routing.yaml'])
        user_loaded = any((self.user_config_dir / cf).exists() for cf in ['guardian.yaml', 'models.yaml', 'routing.yaml'])
        
        return {
            'status': 'running',
            'pid': pid,
            'mode': mode,
            'system_config_loaded': system_loaded,
            'user_config_loaded': user_loaded,
            'system_config_dir': str(self.system_config_dir) if system_loaded else None,
            'user_config_dir': str(self.user_config_dir),
            'decisions_logged': status.get('decisions_logged', 0),
            'uptime': str(datetime.now() - self.start_time) if self.start_time else 'N/A'
        }
    
    def _is_process_alive(self, pid: int) -> bool:
        """Check if process is alive"""
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False
    
    def doctor(self) -> Dict:
        """Validate environment and configuration"""
        results = {
            'checks': [],
            'passed': True
        }
        
        # Check Python version
        py_version = "{}.{}".format(sys.version_info.major, sys.version_info.minor)
        results['checks'].append({
            'name': 'python_version',
            'passed': sys.version_info.major >= 3 and sys.version_info.minor >= 8,
            'message': "Python {}".format(py_version)
        })
        
        # Check config directory
        config_exists = self.user_config_dir.exists()
        results['checks'].append({
            'name': 'config_dir',
            'passed': config_exists,
            'message': "Config dir: {}".format(self.user_config_dir)
        })
        
        # Check config files
        config_files = ['guardian.yaml', 'models.yaml', 'routing.yaml']
        for cf in config_files:
            exists = (self.user_config_dir / cf).exists() or (self.system_config_dir / cf).exists()
            results['checks'].append({
                'name': 'config_{}'.format(cf),
                'passed': exists,
                'message': "{}: {}".format(cf, 'found' if exists else 'missing')
            })
            if not exists:
                results['passed'] = False
        
        # Check write permissions
        try:
            test_file = self.user_config_dir / '.write_test'
            test_file.write_text('test')
            test_file.unlink()
            results['checks'].append({
                'name': 'write_permissions',
                'passed': True,
                'message': 'Write access OK'
            })
        except Exception as e:
            results['passed'] = False
            results['checks'].append({
                'name': 'write_permissions',
                'passed': False,
                'message': 'No write access: {}'.format(e)
            })
        
        # Check log path
        try:
            log_path = Path(self.config.log_file)
            if log_path.parent.exists():
                results['checks'].append({
                    'name': 'log_path',
                    'passed': True,
                    'message': 'Log path OK: {}'.format(self.config.log_file)
                })
            else:
                log_path.parent.mkdir(parents=True, exist_ok=True)
                results['checks'].append({
                    'name': 'log_path',
                    'passed': True,
                    'message': 'Created log dir: {}'.format(log_path.parent)
                })
        except Exception as e:
            results['checks'].append({
                'name': 'log_path',
                'passed': False,
                'message': 'Log path error: {}'.format(e)
            })
        
        return results


def run_daemon(config_dir: str = None, shadow_mode: bool = True, interval: int = 30):
    """Convenience function to run daemon"""
    config = DaemonConfig(
        config_dir=config_dir or '/etc/tokenguardian',
        user_config_dir='~/.tokenguardian',
        interval=interval
    )
    
    daemon = TokenGuardianDaemon(config)
    daemon.config.shadow_mode = shadow_mode
    daemon.start()


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Token Guardian Daemon')
    parser.add_argument('command', choices=['start', 'stop', 'status', 'doctor'],
                       help='Command to run')
    parser.add_argument('--config', '-c', default='~/.tokenguardian',
                       help='Configuration directory')
    parser.add_argument('--shadow', action='store_true', default=True,
                       help='Shadow mode (default: True)')
    parser.add_argument('--interval', '-i', type=int, default=30,
                       help='Monitoring interval in seconds')
    
    args = parser.parse_args()
    
    daemon = TokenGuardianDaemon(DaemonConfig(
        config_dir=args.config,
        user_config_dir=args.config,
        interval=args.interval
    ))
    daemon.config.shadow_mode = args.shadow
    
    if args.command == 'start':
        daemon.start()
    elif args.command == 'stop':
        daemon.stop()
    elif args.command == 'status':
        status = daemon.status()
        print(json.dumps(status, indent=2))
    elif args.command == 'doctor':
        results = daemon.doctor()
        print(json.dumps(results, indent=2))
