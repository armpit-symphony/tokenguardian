#!/usr/bin/env python3
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
import sys
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
        interval=args.interval
    )
    
    daemon = TokenGuardianDaemon(config)
    daemon.config.shadow_mode = not args.live
    
    print(f"Starting Token Guardian daemon...")
    print(f"  Config: {config_dir}")
    print(f"  Mode: {'LIVE' if args.live else 'SHADOW'}")
    print(f"  Interval: {args.interval}s")
    
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
    """Show daemon status"""
    from src.daemon.daemon import TokenGuardianDaemon, DaemonConfig
    
    config = DaemonConfig(user_config_dir=get_config_dir())
    daemon = TokenGuardianDaemon(config)
    
    status = daemon.status()
    
    print("\n╔════════════════════════════════════════════════════╗")
    print("║           TOKEN GUARDIAN STATUS               ║")
    print("╚════════════════════════════════════════════════════╝")
    print()
    
    print(f"Status:           {status['status'].upper()}")
    print(f"PID:              {status.get('pid', 'N/A')}")
    print(f"Mode:             {status.get('mode', 'N/A').upper()}")
    print(f"System Config:    {'LOADED' if status.get('system_config_loaded') else 'NOT LOADED'}")
    print(f"User Config:      {'LOADED' if status.get('user_config_loaded') else 'NOT LOADED'}")
    print(f"  System Dir:     {status.get('system_config_dir', 'N/A')}")
    print(f"  User Dir:       {status.get('user_config_dir', 'N/A')}")
    print(f"Decisions Logged: {status.get('decisions_logged', 0)}")
    print(f"Uptime:           {status.get('uptime', 'N/A')}")
    
    # Show last decision if available
    if 'last_decision' in status and status['last_decision']:
        ld = status['last_decision']
        print()
        print("Last Decision:")
        print(f"  Time:   {ld.get('timestamp', 'N/A')}")
        print(f"  Class:  {ld.get('classification', 'N/A')}")
        print(f"  Model:  {ld.get('model', 'N/A')}")
        print(f"  Fallback: {'YES' if ld.get('fallback') else 'NO'}")


def cmd_doctor(args):
    """Validate environment and configuration"""
    from src.daemon.daemon import TokenGuardianDaemon, DaemonConfig
    
    config = DaemonConfig(user_config_dir=get_config_dir())
    daemon = TokenGuardianDaemon(config)
    
    results = daemon.doctor()
    
    print("\n╔════════════════════════════════════════════════════╗")
    print("║           TOKEN GUARDIAN DOCTOR                ║")
    print("╚════════════════════════════════════════════════════╝")
    print()
    
    all_passed = True
    for check in results['checks']:
        icon = "✓" if check['passed'] else "✗"
        print(f"{icon} {check['name']}: {check['message']}")
        if not check['passed']:
            all_passed = False
    
    print()
    if all_passed:
        print("✓ All checks passed")
    else:
        print("✗ Some checks failed - review above")


def cmd_dry_run(args):
    """Dry run - show routing decision without executing"""
    from src.core.pipeline import create_pipeline
    
    config_dir = get_config_dir()
    
    print("\n╔════════════════════════════════════════════════════╗")
    print("║           TOKEN GUARDIAN DRY-RUN                 ║")
    print("╚════════════════════════════════════════════════════╝")
    print()
    
    # Create pipeline in shadow mode
    pipeline = create_pipeline(config_dir, shadow_mode=True)
    
    # Default query if not provided
    if args.query:
        queries = [args.query]
    else:
        queries = [
            "Write a Python function to sort arrays",
            "Analyze sales data from last quarter",
            "Write a creative story about space",
            "Explain why the sky is blue",
            "What's 2+2?",
            "General question about AI",  # Should trigger fallback
        ]
    
    print(f"Mode: SHADOW (decisions logged, not executed)")
    print(f"Confidence Threshold: {pipeline.confidence_threshold}")
    print(f"Safe Fallback: {pipeline.safe_fallback_model}")
    print()
    print("-" * 80)
    
    for query in queries:
        decision = pipeline.process(query)
        
        print(f"\nQuery: {query[:60]}...")
        print(f"  Classification: {decision.classification}")
        print(f"  Confidence:    {decision.confidence:.2f} (threshold: {decision.threshold:.2f})")
        print(f"  Selected:      {decision.selected_model}")
        
        if decision.fallback_triggered:
            print(f"  ⚠ FALLBACK: {decision.fallback_reason}")
        else:
            print(f"  ✓ Normal routing")
        
        if decision.optimization:
            print(f"  Optimization: {decision.optimization.get('action', 'N/A')} "
                  f"(saves {decision.optimization.get('tokens_saved', 0)} tokens)")
    
    print()
    print("-" * 80)
    print(f"\nTotal decisions: {len(pipeline.decision_log)}")
    fallbacks = sum(1 for d in pipeline.decision_log if d.fallback_triggered)
    print(f"Fallbacks triggered: {fallbacks}")


def cmd_classify(args):
    """Classify a query with confidence"""
    from src.core.classifier import Classifier
    
    config_dir = get_config_dir()
    
    print("\n╔════════════════════════════════════════════════════╗")
    print("║           QUERY CLASSIFICATION                   ║")
    print("╚════════════════════════════════════════════════════╝")
    print()
    
    classifier = Classifier(str(Path(config_dir) / 'routing.yaml')) if Path(config_dir).exists() else Classifier()
    
    if args.query:
        queries = [args.query]
    else:
        queries = [
            "Write a Python function to sort arrays",
            "Analyze sales data from last quarter",
            "Write a creative story about space",
            "Explain why the sky is blue",
            "What's 2+2?",
        ]
    
    for query in queries:
        result = classifier.classify(query)
        threshold = 0.80
        
        print(f"\nQuery: {query[:60]}...")
        print(f"  Label:       {result.label}")
        print(f"  Confidence:  {result.confidence:.2f}")
        print(f"  Keywords:    {result.matched_keywords if result.matched_keywords else 'none'}")
        print(f"  Reasoning:   {result.reasoning}")
        
        if result.confidence < threshold:
            print(f"  ⚠ Below threshold ({threshold:.2f}) → would use fallback")
        else:
            print(f"  ✓ Above threshold ({threshold:.2f}) → normal routing")
        
        preferred = classifier.get_preferred_model(result.label)
        fallback = classifier.get_safe_fallback_model()
        print(f"  Preferred:   {preferred}")
        print(f"  Fallback:    {fallback}")


def cmd_optimize(args):
    """Optimize a prompt"""
    from src.core.optimizer import Optimizer
    
    config_dir = get_config_dir()
    
    print("\n╔════════════════════════════════════════════════════╗")
    print("║           PROMPT OPTIMIZATION                      ║")
    print("╚════════════════════════════════════════════════════╝")
    print()
    
    optimizer = Optimizer(str(Path(config_dir) / 'guardian.yaml')) if Path(config_dir).exists() else Optimizer()
    
    if args.query:
        prompts = [args.query]
    else:
        prompts = [
            "Please could you write me a Python function to sort arrays? Thank you very much!",
            "Can you analyze this data for me? I would really appreciate your help!",
            "Explain how quantum computing works",
        ]
    
    for prompt in prompts:
        result = optimizer.optimize(prompt)
        
        print(f"\nOriginal ({len(prompt)} chars):")
        print(f"  {prompt[:70]}...")
        
        print(f"\nRefined ({len(result.refined)} chars):")
        print(f"  {result.refined[:70]}...")
        
        print(f"\n  Tokens saved: {result.tokens_saved} ({result.savings_percent:.1f}%)")
        print(f"  Action:       {result.action_taken}")
        print(f"  Cache hit:    {'YES' if result.cache_hit else 'NO'}")


def cmd_stats(args):
    """Show usage statistics"""
    from src.core.monitor import Monitor
    
    config_dir = get_config_dir()
    
    print("\n╔════════════════════════════════════════════════════╗")
    print("║           USAGE STATISTICS                       ║")
    print("╚════════════════════════════════════════════════════╝")
    print()
    
    monitor = Monitor(str(Path(config_dir)))
    stats = monitor.get_stats()
    
    for key, value in stats.items():
        if isinstance(value, dict):
            print(f"{key}:")
            for k, v in value.items():
                print(f"  {k}: {v}")
        else:
            print(f"{key}: {value}")


def cmd_logs(args):
    """Show daemon logs"""
    config = DaemonConfig()
    log_file = Path(config.log_file)
    
    if log_file.exists():
        with open(log_file, 'r') as f:
            lines = f.readlines()
        
        if args.tail:
            lines = lines[-args.tail:]
        
        for line in lines:
            print(line.rstrip())
    else:
        print(f"Log file not found: {log_file}")


def cmd_install(args):
    """Install Token Guardian CLI"""
    import shutil
    
    # Get script directory
    script_dir = Path(__file__).parent
    target_path = Path('/usr/local/bin/tokenguardian')
    
    if target_path.exists():
        print(f"Token Guardian already installed at {target_path}")
    else:
        shutil.copy(script_dir / 'tokenguardian.py', target_path)
        target_path.chmod(0o755)
        print(f"Installed Token Guardian to {target_path}")
    
    # Create config directory
    config_dir = Path('~/.tokenguardian').expanduser()
    config_dir.mkdir(parents=True, exist_ok=True)
    print(f"Config directory: {config_dir}")
    
    # Copy default configs
    if (script_dir / 'config').exists():
        for config_file in (script_dir / 'config').glob('*.yaml'):
            target = config_dir / config_file.name
            if not target.exists():
                shutil.copy(config_file, target)
                print(f"  Copied config: {config_file.name}")
    
    print("\n✓ Installation complete")
    print("Run 'tokenguardian doctor' to validate installation")


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description='Token Guardian - AI Cost Optimization & Routing',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Environment:
  TG_CONFIG_DIR         Override config directory (for isolated instances)
  TG_CACHE_DIR          Override cache directory
  TG_AUDIT_DIR          Override audit directory
  TG_LOG_DIR            Override log directory

Examples:
  tokenguardian status           # Show daemon status
  tokenguardian start --live     # Start in live mode
  tokenguardian dry-run          # Test routing decisions
  tokenguardian doctor           # Validate installation
  tokenguardian help             # Show this help
        """
    )
    
    # Global options for isolated instances
    parser.add_argument('--config-dir', '-c', dest='config_dir',
                       help='Config directory (default: ~/.tokenguardian)')
    
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # start
    start_parser = subparsers.add_parser('start', help='Start daemon')
    start_parser.add_argument('--live', action='store_true', help='Run in live mode (default: shadow)')
    start_parser.add_argument('--interval', '-i', type=int, default=30, help='Monitoring interval')
    
    # stop
    subparsers.add_parser('stop', help='Stop daemon')
    
    # status
    subparsers.add_parser('status', help='Show daemon status')
    
    # restart
    restart_parser = subparsers.add_parser('restart', help='Restart daemon')
    restart_parser.add_argument('--live', action='store_true', help='Run in live mode')
    restart_parser.add_argument('--interval', '-i', type=int, default=30, help='Monitoring interval')
    
    # dry-run
    dry_parser = subparsers.add_parser('dry-run', help='Test routing without executing')
    dry_parser.add_argument('--query', '-q', help='Query to test')
    
    # tail
    tail_parser = subparsers.add_parser('tail', help='Show daemon logs')
    tail_parser.add_argument('--lines', '-n', type=int, default=20, help='Number of lines')
    
    # doctor
    subparsers.add_parser('doctor', help='Validate configuration')
    
    # classify
    class_parser = subparsers.add_parser('classify', help='Classify a query')
    class_parser.add_argument('--query', '-q', help='Query to classify')
    
    # optimize
    opt_parser = subparsers.add_parser('optimize', help='Optimize a prompt')
    opt_parser.add_argument('--query', '-q', help='Prompt to optimize')
    opt_parser.add_argument('--no-cache', action='store_true', help='Skip cache')
    
    # stats
    subparsers.add_parser('stats', help='Show usage statistics')
    
    # logs
    logs_parser = subparsers.add_parser('logs', help='Show daemon logs')
    logs_parser.add_argument('--tail', '-n', type=int, help='Show last N lines')
    
    # install
    subparsers.add_parser('install', help='Install CLI')
    
    # help
    subparsers.add_parser('help', help='Show this help')
    
    args = parser.parse_args()
    
    # Handle isolated config directory
    if hasattr(args, 'config_dir') and args.config_dir:
        os.environ['TG_CONFIG_DIR'] = args.config_dir
    
    if args.command == 'help':
        parser.print_help()
        return
    
    # Route commands
    command_map = {
        'start': cmd_start,
        'stop': cmd_stop,
        'status': cmd_status,
        'restart': cmd_stop,
        'dry-run': cmd_dry_run,
        'tail': cmd_logs,
        'doctor': cmd_doctor,
        'classify': cmd_classify,
        'optimize': cmd_optimize,
        'stats': cmd_stats,
        'logs': cmd_logs,
        'install': cmd_install,
    }
    
    if args.command in command_map:
        command_map[args.command](args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
