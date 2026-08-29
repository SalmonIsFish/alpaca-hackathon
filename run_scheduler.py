#!/usr/bin/env python3
"""
Simple script to run the trading scheduler.

Usage:
    python run_scheduler.py --start          # Start scheduler (60 min interval)
    python run_scheduler.py --start --interval 30  # Start with 30 min interval
    python run_scheduler.py --start --dry-run      # Start in dry-run mode
    python run_scheduler.py --stop           # Stop scheduler
    python run_scheduler.py --status         # Check scheduler status
"""

import argparse
import sys
import time
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent.scheduler import TradingScheduler, run_scheduler


def main():
    parser = argparse.ArgumentParser(
        description="Manage the Alpaca trading scheduler",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_scheduler.py --start                    # Start scheduler (60 min)
  python run_scheduler.py --start --interval 30      # Start (30 min interval)
  python run_scheduler.py --start --dry-run          # Start in dry-run mode
  python run_scheduler.py --stop                     # Stop scheduler
  python run_scheduler.py --status                   # Check status
        """
    )
    
    parser.add_argument("--start", action="store_true", help="Start the scheduler")
    parser.add_argument("--stop", action="store_true", help="Stop the scheduler")
    parser.add_argument("--status", action="store_true", help="Check scheduler status")
    parser.add_argument("--interval", type=int, default=60, help="Trading interval in minutes (default: 60)")
    parser.add_argument("--dry-run", action="store_true", help="Dry run mode (no real orders)")
    parser.add_argument("--profile", default=None, help="Alpaca profile to use")
    
    args = parser.parse_args()
    
    # Ensure at least one action is specified
    if not any([args.start, args.stop, args.status]):
        parser.print_help()
        sys.exit(1)
    
    if args.start:
        print("=" * 70)
        print("ALPACA TRADING SCHEDULER - STARTING")
        print("=" * 70)
        print(f"Configuration:")
        print(f"  Interval: {args.interval} minutes")
        print(f"  Dry run: {args.dry_run}")
        print(f"  Profile: {args.profile or 'default (from env)'}")
        print("=" * 70)
        print()
        
        scheduler = run_scheduler(
            interval_minutes=args.interval,
            dry_run=args.dry_run,
            profile=args.profile,
        )
        
        print("\nScheduler is running. Press Ctrl+C to stop.")
        print("=" * 70)
        
        try:
            # Keep main thread alive
            while scheduler.is_running():
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n\nReceived interrupt signal")
        finally:
            scheduler.stop()
            print("Scheduler shutdown complete")
    
    elif args.stop:
        print("Stop functionality requires the scheduler to be running in the same process.")
        print("To stop a running scheduler, press Ctrl+C in the terminal where it's running.")
        print("Or use: kill <PID> if running in background.")
    
    elif args.status:
        print("Status check requires the scheduler to be running in the same process.")
        print("Check the logs/decisions.jsonl file to see recent trading activity.")
        print("Or check if the process is running with: ps aux | grep run_scheduler")


if __name__ == "__main__":
    main()
