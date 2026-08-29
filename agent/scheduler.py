"""Scheduler for autonomous pipeline execution during market hours.

Simple scheduler that runs the trading pipeline at specified intervals during
market hours (9:30am - 4:00pm ET, Monday-Friday). Uses a background thread to
avoid blocking and provides clean start/stop functionality.
"""

from __future__ import annotations

import threading
import time
from datetime import datetime, time as dt_time
from typing import Callable

from agent.pipeline import run_pipeline
from agent.config import get_settings


class TradingScheduler:
    """Simple scheduler for trading pipeline execution.
    
    Runs the pipeline at specified intervals during market hours.
    Market hours: Monday-Friday, 9:30am - 4:00pm ET
    """
    
    def __init__(
        self,
        interval_minutes: int = 60,
        market_open: dt_time = dt_time(9, 30),
        market_close: dt_time = dt_time(16, 0),
        dry_run: bool = False,
        profile: str | None = None,
    ):
        """Initialize scheduler.
        
        Args:
            interval_minutes: How often to run the pipeline (default: 60 min)
            market_open: Market open time (default: 9:30am ET)
            market_close: Market close time (default: 4:00pm ET)
            dry_run: If True, never submit actual orders
            profile: Alpaca profile to use (None = use ALPACA_PROFILE env var)
        """
        self.interval_minutes = interval_minutes
        self.market_open = market_open
        self.market_close = market_close
        self.dry_run = dry_run
        self.profile = profile
        
        self._running = False
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
    
    def _is_market_hours(self) -> bool:
        """Check if current time is within market hours (ET)."""
        try:
            from zoneinfo import ZoneInfo
            ET = ZoneInfo("America/New_York")
            now = datetime.now(ET)
        except Exception:
            now = datetime.now()
        
        # Check if weekday (Monday=0, Friday=4)
        if now.weekday() > 4:  # Saturday or Sunday
            return False
        
        # Check if within market hours
        current_time = now.time()
        return self.market_open <= current_time <= self.market_close
    
    def _run_cycle(self) -> None:
        """Execute one pipeline cycle."""
        print(f"[{datetime.now()}] Starting pipeline cycle...")
        
        try:
            result = run_pipeline(
                underlying=None,
                dry_run=self.dry_run,
                profile=self.profile,
            )
            
            # Log the outcome
            outcome = result.get("outcome", "UNKNOWN")
            underlying = result.get("underlying", "N/A")
            print(f"[{datetime.now()}] Pipeline completed: {outcome} ({underlying})")
            
        except Exception as e:
            print(f"[{datetime.now()}] Pipeline error: {e}")
            import traceback
            traceback.print_exc()
    
    def _scheduler_loop(self) -> None:
        """Main scheduler loop running in background thread."""
        print(f"[{datetime.now()}] Scheduler started")
        print(f"  Market hours: {self.market_open} - {self.market_close} ET")
        print(f"  Interval: {self.interval_minutes} minutes")
        print(f"  Dry run: {self.dry_run}")
        
        # Run immediately on start if during market hours
        if self._is_market_hours():
            self._run_cycle()
        
        while not self._stop_event.is_set():
            # Sleep in small increments to allow quick shutdown
            for _ in range(self.interval_minutes * 6):  # Check every 10 seconds
                if self._stop_event.is_set():
                    break
                time.sleep(10)
            
            if self._stop_event.is_set():
                break
            
            # Check if during market hours
            if self._is_market_hours():
                self._run_cycle()
            else:
                print(f"[{datetime.now()}] Outside market hours, skipping cycle")
        
        print(f"[{datetime.now()}] Scheduler stopped")

    def start(self) -> None:
        """Start the scheduler in a background thread."""
        if self._running:
            print("Scheduler already running")
            return
        
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self._thread.start()
        print("Scheduler started in background thread")
    
    def stop(self) -> None:
        """Stop the scheduler gracefully."""
        if not self._running:
            print("Scheduler not running")
            return
        
        print("Stopping scheduler...")
        self._stop_event.set()
        self._running = False
        
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        
        print("Scheduler stopped")
    
    def is_running(self) -> bool:
        """Check if scheduler is currently running."""
        return self._running


def run_scheduler(
    interval_minutes: int = 60,
    dry_run: bool = False,
    profile: str | None = None,
) -> TradingScheduler:
    """Create and start a scheduler with the given configuration.
    
    Args:
        interval_minutes: How often to run the pipeline
        dry_run: If True, never submit actual orders
        profile: Alpaca profile to use
    
    Returns:
        Started TradingScheduler instance
    """
    scheduler = TradingScheduler(
        interval_minutes=interval_minutes,
        dry_run=dry_run,
        profile=profile,
    )
    scheduler.start()
    return scheduler


if __name__ == "__main__":
    # Example: Run scheduler for testing
    import argparse
    
    parser = argparse.ArgumentParser(description="Run trading scheduler")
    parser.add_argument("--interval", type=int, default=60, help="Interval in minutes")
    parser.add_argument("--dry-run", action="store_true", help="Dry run mode")
    parser.add_argument("--profile", default=None, help="Alpaca profile")
    args = parser.parse_args()
    
    print("=" * 60)
    print("ALPACA TRADING SCHEDULER")
    print("=" * 60)
    
    scheduler = run_scheduler(
        interval_minutes=args.interval,
        dry_run=args.dry_run,
        profile=args.profile,
    )
    
    print("\nScheduler is running. Press Ctrl+C to stop.")
    print("=" * 60)
    
    try:
        # Keep main thread alive
        while scheduler.is_running():
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\nReceived interrupt signal")
    finally:
        scheduler.stop()
        print("Scheduler shutdown complete")
