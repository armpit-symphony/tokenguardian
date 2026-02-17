#!/usr/bin/env python3
"""
Token Guardian CLI
Unified command-line interface for the Token Guardian system

Usage:
    tokenguardian start [--live] [--interval SECONDS]
    tokenguardian stop
    tokenguardian status
    tokenguardian restart [--live] [--interval SECONDS]
    tokenguardian dry-run [--query TEXT]
    tokenguardian tail
    tokenguardian doctor
    tokenguardian classify [--query TEXT]
    tokenguardian optimize [--query TEXT] [--no-cache]
    tokenguardian stats
    tokenguardian logs [--tail N]
    tokenguardian install
    tokenguardian help
"""
import argparse
import json
import os
import signal
import sys
import time
from datetime import datetime
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))


def get_config_dir() -> str:
    """Get effective configuration directory"""
    # Check environment variable first (for isolated instances)
    if 'TG_CONFIG_DIR' in os.environ:
        return os.environ['TG_CONFIG_DIR']
    
    user_config = Path('~/.tokenguardian').expanduser()
    system_config = Path('/etc/tokenguardian')
    
    if user_config.exists():
        return str(user_config)
    elif system_config.exists():
        return str(system_config)
    return str(user_config)


def cmd_start(args):
    """Start the Token Guardian daemon"""
    from src.daemon.daemon import TokenGuardianDaemon, DaemonConfig
    
    config_dir = get_config_dir()
    
    config = DaemonConfig(
        config_dir='/etc/tokenguardian',
        user_config_dir=config_dir,
        interval=args.interval,
        metrics_port=args.metrics_port
    )
    
    daemon = TokenGuardianDaemon(config)
    daemon.config.shadow_mode = not args.live
    
    print(f"Starting Token Guardian daemon...")
    print(f"  Config: {config_dir}")
    print(f"  Mode: {'LIVE' if args.live else 'SHADOW'}")
    print(f"  Interval: {args.interval}s")
    print(f"  Metrics Port: {args.metrics_port}")
    
    daemon.start()


def cmd_stop(args):
    """Stop the Token Guardian daemon"""
    from src.daemon.daemon import TokenGuardianDaemon, DaemonConfig
    
    config = DaemonConfig()
    pid_file = Path(config.pid_file)
    
    if pid_file.exists():
        try:
            with open(pid_file, 'r') as f:
                pid = int(f.read().strip())
            
            os.kill(pid, 15)  # SIGTERM
            print(f"Daemon (PID {pid}) stopped")
            
            # Cleanup PID file
            pid_file.unlink(missing_ok=True)
            
        except Exception as e:
            print(f"Error stopping daemon: {e}")
    else:
        print("Daemon not running (no PID file)")


def cmd_status(args):
    """Show daemon status - READ ONLY, no daemon instantiation"""
    import subprocess
    from pathlib import Path
    import os
    
    pid_file = Path.home() / '.tokenguardian' / 'tokenguardian.pid'
    
    pid = None
    if pid_file.exists():
        try:
            with open(pid_file, 'r') as f:
                pid = int(f.read().strip())
        except:
            pass
    
    running = False
    mode = "UNKNOWN"
    elapsed = "N/A"
    
    if pid:
        try:
            os.kill(pid, 0)
            running = True
            result = subprocess.run(['ps', '-p', str(pid), '-o', 'etime,args'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                if len(lines) >= 2:
                    elapsed = lines[1].split()[0]
                    args_line = ' '.join(lines[1].split()[1:])
                    mode = "LIVE" if "--live" in args_line else "SHADOW"
        except (ProcessLookupError, OSError):
            running = False
    
    if not running:
        result = subprocess.run(['pgrep', '-f', 'tokenguardian.py start'], 
                              capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            pid = int(result.stdout.strip().split('\n')[0])
            running = True
            mode = "LIVE"
    
    print("")
    print("╔════════════════════════════════════════════════════╗")
    print("║           TOKEN GUARDIAN STATUS               ║")
    print("╚════════════════════════════════════════════════════╝")
    print("")
    print(f"Status:           {'RUNNING' if running else 'STOPPED'}")
    print(f"PID:              {pid if pid else 'N/A'}")
    print(f"Mode:             {mode}")
    print(f"Uptime:           {elapsed}")
    
    # Read burn-in start
    burnin_file = Path.home() / '.tokenguardian-burnin48' / 'burnin_start.txt'
    if burnin_file.exists():
        with open(burnin_file, 'r') as f:
            burnin_start = f.read().strip()
        print(f"Burn-in Start:    {burnin_start}")
    
    # Check wrapper heartbeat
    heartbeat_file = Path.home() / '.tokenguardian-burnin48' / 'wrapper_heartbeat.log'
    if heartbeat_file.exists():
        print(f"Heartbeat:        PRESENT")
    else:
        print(f"Heartbeat:        N/A")


def cmd_doctor(args):
    """Validate environment and configuration"""

    # Handle --providers flag for health check
    if hasattr(args, 'providers') and args.providers:
        from src.core.health import check_providers
        check_providers()
        return
    
    from src.daemon.daemon import TokenGuardianDaemon, DaemonConfig
    
    config = DaemonConfig(user_config_dir=get_config_dir())
    daemon = TokenGuardianDaemon(config)
    
    results = daemon.doctor()
    
    print("\n╔════════════════════════════════════════════════════╗")
    print("║           TOKEN GUARDIAN DOCTOR               ║")
    print("╚════════════════════════════════════════════════════╝")
    
    all_passed = True
    
    for result in results.get('checks', []):
        status = "✓ PASS" if result['passed'] else "✗ FAIL"
        if not result['passed']:
            all_passed = False
        print(f"{status}: {result['name']}")
        print(f"       {result['message']}")
    
    if all_passed:
        print("\n✓ All checks passed!")
    else:
        print("\n✗ Some checks failed. Review above.")
    
    return results


def cmd_classify(args):
    """Classify a query"""
    from src.core.classifier import Classifier
    
    classifier = Classifier()
    result = classifier.classify(args.query)
    
    print("\n╔════════════════════════════════════════════════════╗")
    print("║           QUERY CLASSIFICATION                   ║")
    print("╚════════════════════════════════════════════════════╝")
    print()
    print(f"Query: {args.query}")
    print(f"  Label:       {result.label}")
    print(f"  Confidence:  {result.confidence:.2f}")
    print(f"  Keywords:    {result.keywords}")


def cmd_optimize(args):
    """Optimize a query"""
    from src.core.optimizer import Optimizer
    
    optimizer = Optimizer()
    result = optimizer.optimize(args.query, skip_cache=args.no_cache)
    
    print("\n╔════════════════════════════════════════════════════╗")
    print("║           QUERY OPTIMIZATION                     ║")
    print("╚════════════════════════════════════════════════════╝")
    print()
    print(f"Original: {args.query}")
    print(f"Optimized: {result.optimized_query}")
    print(f"  Saved: {result.tokens_saved} tokens")


def cmd_stats(args):
    """Show usage statistics"""
    from src.core.stats import get_stats
    
    stats = get_stats()
    
    print("\n╔════════════════════════════════════════════════════╗")
    print("║           TOKEN GUARDIAN STATS                   ║")
    print("╚════════════════════════════════════════════════════╝")
    
    for model, count in stats.get('by_model', {}).items():
        print(f"  {model}: {count}")


def cmd_logs(args):
    """Show daemon logs"""
    log_file = Path.home() / '.tokenguardian' / 'daemon.log'
    
    if not log_file.exists():
        print("No logs found.")
        return
    
    lines = args.tail if args.tail else 50
    print(f"Last {lines} log lines:")
    print("-" * 60)
    
    with open(log_file, 'r') as f:
        all_lines = f.readlines()
        for line in all_lines[-lines:]:
            print(line.rstrip())


def cmd_tail(args):
    """Tail the daemon log in real-time"""
    import time
    log_file = Path.home() / '.tokenguardian' / 'daemon.log'
    
    if not log_file.exists():
        print("No logs found. Daemon may not be running.")
        return
    
    print(f"Tailing {log_file} (Ctrl+C to stop)...")
    print("-" * 60)
    
    with open(log_file, 'r') as f:
        f.seek(0, 2)  # Seek to end
        while True:
            line = f.readline()
            if line:
                print(line.rstrip())
            else:
                time.sleep(0.5)


def cmd_install(args):
    """Install Token Guardian as a systemd service"""
    import shutil
    
    service_content = """[Unit]
Description=Token Guardian AI Cost Optimization Daemon
After=network.target

[Service]
Type=simple
User=sparky
WorkingDirectory=/home/sparky/.openclaw/workspace/tokenguardian
ExecStart=/usr/bin/python3 /home/sparky/.openclaw/workspace/tokenguardian/tokenguardian.py start --live
ExecStop=/usr/bin/python3 /home/sparky/.openclaw/workspace/tokenguardian/tokenguardian.py stop
Restart=always
RestartSec=5
Environment=TG_CONFIG_DIR=/home/sparky/.tokenguardian
StandardOutput=journal
StandardError=journal
SyslogIdentifier=tokenguardian
MemoryMax=512M
CPUQuota=50%

[Install]
WantedBy=default.target
"""
    
    service_path = Path('/etc/systemd/system/tokenguardian.service')
    
    try:
        with open(service_path, 'w') as f:
            f.write(service_content)
        
        print(f"Created systemd service at {service_path}")
        print("Run these commands to enable:")
        print("  sudo systemctl daemon-reload")
        print("  sudo systemctl enable tokenguardian")
        print("  sudo systemctl start tokenguardian")
    except PermissionError:
        print("Permission denied. Run with sudo or create as user service:")
        print("  mkdir -p ~/.config/systemd/user")
        print("  Copy content to ~/.config/systemd/user/tokenguardian.service")
        print("  systemctl --user daemon-reload")
        print("  systemctl --user enable tokenguardian")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Token Guardian CLI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  tokenguardian start --live     # Start in live mode
  tokenguardian status           # Show daemon status
  tokenguardian classify --query "Write Python code"  # Classify a query
  tokenguardian doctor --providers  # Check provider configurations
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # Start command
    start_parser = subparsers.add_parser('start', help='Start the daemon')
    start_parser.add_argument('--live', action='store_true', help='Run in live mode (default: shadow)')
    start_parser.add_argument('--interval', type=int, default=30, help='Monitoring interval in seconds')
    start_parser.add_argument('--metrics-port', type=int, default=9090, help='Prometheus metrics port')
    
    # Stop command
    subparsers.add_parser('stop', help='Stop the daemon')
    
    # Status command
    subparsers.add_parser('status', help='Show daemon status')
    
    # Restart command
    restart_parser = subparsers.add_parser('restart', help='Restart the daemon')
    restart_parser.add_argument('--live', action='store_true', help='Run in live mode')
    restart_parser.add_argument('--interval', type=int, default=30, help='Monitoring interval')
    
    # Doctor command
    doctor_parser = subparsers.add_parser('doctor', help='Validate environment')
    doctor_parser.add_argument('--providers', action='store_true', help='Check provider configurations')
    
    # Classify command
    classify_parser = subparsers.add_parser('classify', help='Classify a query')
    classify_parser.add_argument('--query', required=True, help='Query to classify')
    
    # Optimize command
    optimize_parser = subparsers.add_parser('optimize', help='Optimize a query')
    optimize_parser.add_argument('--query', required=True, help='Query to optimize')
    optimize_parser.add_argument('--no-cache', action='store_true', help='Skip cache')
    
    # Stats command
    subparsers.add_parser('stats', help='Show usage statistics')
    
    # Logs command
    logs_parser = subparsers.add_parser('logs', help='Show daemon logs')
    logs_parser.add_argument('--tail', type=int, help='Number of lines to show')
    
    # Tail command
    subparsers.add_parser('tail', help='Tail daemon logs in real-time')
    
    # Install command
    subparsers.add_parser('install', help='Install as systemd service')
    
    # Help command
    subparsers.add_parser('help', help='Show this help message')
    
    args = parser.parse_args()
    
    if args.command == 'help':
        parser.print_help()
        return
    
    if not args.command:
        parser.print_help()
        return
    
    # Route to appropriate command
    commands = {
        'start': cmd_start,
        'stop': cmd_stop,
        'status': cmd_status,
        'restart': cmd_start,
        'doctor': cmd_doctor,
        'classify': cmd_classify,
        'optimize': cmd_optimize,
        'stats': cmd_stats,
        'logs': cmd_logs,
        'tail': cmd_tail,
        'install': cmd_install,
    }
    
    try:
        commands[args.command](args)
    except KeyboardInterrupt:
        print("\nInterrupted.")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
