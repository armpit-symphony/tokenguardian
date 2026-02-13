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
from pathlib import Path
from typing import Dict, List, Optional

import yaml


@dataclass
class DaemonConfig:
    """Daemon configuration - user-writable paths"""
    pid_file: str = '~/.tokenguardian/tokenguardian.pid'
    log_file: str = '~/.tokenguardian/daemon.log'
    config_dir: str = '/etc/tokenguardian'
    user_config_dir: str = '~/.tokenguardian'
    interval: int = 30
    shadow_mode: bool = True


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
        self.start_time = None
        
        # Signal handlers
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)
    
    def _handle_shutdown(self, signum, frame):
        """Handle shutdown signals"""
        print(f"\n[INFO] Received signal {signum}, shutting down...")
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
            print(f"[WARN] Could not write PID file: {e}")
    
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
        
        print(f"[INFO] Token Guardian Daemon starting (PID: {self.pid})")
        print(f"[INFO] Config dir: {self.user_config_dir}")
        print(f"[INFO] Shadow mode: {self.config.shadow_mode}")
        print(f"[INFO] Interval: {self.config.interval}s")
        
        # Import pipeline here to avoid circular imports
        from ..core.pipeline import create_pipeline
        from ..core.monitor import Monitor
        
        # Initialize pipeline
        config_paths = self._load_effective_config()
        self.pipeline = create_pipeline(
            str(self.user_config_dir), 
            shadow_mode=self.config.shadow_mode
        )
        
        # Initialize monitor
        self.monitor = Monitor(str(self.user_config_dir))
        
        # Main loop
        cycle = 0
        while self.running:
            try:
                cycle += 1
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                # Log cycle info
                status = self.pipeline.get_status()
                stats = self.monitor.get_stats()
                
                print(f"[{timestamp}] CYCLE {cycle} | Decisions: {status['decisions_logged']} | "
                      f"Tokens: {stats['total_tokens']} | Cost: ${stats['total_cost']:.6f}")
                
                # In a real implementation, this would:
                # 1. Tail OpenClaw session logs
                # 2. Process new queries
                # 3. Dispatch to models
                # For now, we log status
                
                time.sleep(self.config.interval)
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"[ERROR] Cycle failed: {e}")
                time.sleep(self.config.interval)
        
        self._cleanup_pid()
        print(f"[INFO] Daemon stopped. Uptime: {datetime.now() - self.start_time}")
    
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
        py_version = f"{sys.version_info.major}.{sys.version_info.minor}"
        results['checks'].append({
            'name': 'python_version',
            'passed': sys.version_info.major >= 3 and sys.version_info.minor >= 8,
            'message': f"Python {py_version}"
        })
        
        # Check config directory
        config_exists = self.user_config_dir.exists()
        results['checks'].append({
            'name': 'config_dir',
            'passed': config_exists,
            'message': f"Config dir: {self.user_config_dir}"
        })
        
        # Check config files
        config_files = ['guardian.yaml', 'models.yaml', 'routing.yaml']
        for cf in config_files:
            exists = (self.user_config_dir / cf).exists() or (self.system_config_dir / cf).exists()
            results['checks'].append({
                'name': f'config_{cf}',
                'passed': exists,
                'message': f"{cf}: {'found' if exists else 'missing'}"
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
                'message': f'No write access: {e}'
            })
        
        # Check log path
        try:
            log_path = Path(self.config.log_file)
            if log_path.parent.exists():
                results['checks'].append({
                    'name': 'log_path',
                    'passed': True,
                    'message': f'Log path OK: {self.config.log_file}'
                })
            else:
                log_path.parent.mkdir(parents=True, exist_ok=True)
                results['checks'].append({
                    'name': 'log_path',
                    'passed': True,
                    'message': f'Created log dir: {log_path.parent}'
                })
        except Exception as e:
            results['checks'].append({
                'name': 'log_path',
                'passed': False,
                'message': f'Log path error: {e}'
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
