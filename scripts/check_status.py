#!/usr/bin/env python3
"""
Simple status checker for the Alpaca trading agent.

Shows current account status, recent trading activity, and scheduler health.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent import cli
from agent.config import get_settings
from datetime import datetime, date
import json


def print_header(title):
    print("=" * 70)
    print(title.center(70))
    print("=" * 70)
    print()


def check_account_status():
    """Check and display account information."""
    print_header("ACCOUNT STATUS")
    
    settings = get_settings()
    print(f"Profile: {settings.alpaca_profile}")
    print(f"Timestamp: {datetime.now()}")
    print()
    
    try:
        account = cli.account_get(settings.alpaca_profile)
        print(f"Account ID: {account.get('account_number', 'N/A')}")
        print(f"Equity: ${float(account.get('equity', 0)):,.2f}")
        print(f"Cash: ${float(account.get('cash', 0)):,.2f}")
        print(f"Buying Power: ${float(account.get('buying_power', 0)):,.2f}")
        print(f"Daytrade Count: {account.get('daytrade_count', 0)}")
        print()
        
        # Check positions
        positions = cli.position_list(settings.alpaca_profile)
        if positions:
            print(f"Open Positions: {len(positions)}")
            for pos in positions[:5]:  # Show first 5
                print(f"  - {pos.get('symbol', 'N/A')}: {pos.get('qty', 0)} shares")
        else:
            print("Open Positions: None")
        print()
        
    except Exception as e:
        print(f"Error retrieving account: {e}")
        print()


def check_trading_activity():
    """Check and display recent trading activity."""
    print_header("TRADING ACTIVITY")
    
    settings = get_settings()
    log_path = settings.decisions_log_path
    
    try:
        with open(log_path, 'r') as f:
            lines = f.readlines()
        
        if not lines:
            print("No trading activity found.")
            print()
            return
        
        # Count today's activity
        today_str = date.today().isoformat()
        today_decisions = [json.loads(line) for line in lines if today_str in line]
        
        print(f"Total Decisions: {len(lines)}")
        print(f"Today's Decisions: {len(today_decisions)}")
        print()
        
        # Show last 5 decisions
        print("Recent Activity:")
        print("-" * 70)
        for line in lines[-5:]:
            try:
                decision = json.loads(line)
                ts = decision.get('timestamp', 'N/A')[:19]
                outcome = decision.get('outcome', 'UNKNOWN')
                underlying = decision.get('underlying', 'N/A')
                
                # Color code outcomes
                if outcome == 'SUBMITTED':
                    symbol = "✅"
                elif outcome == 'WOULD_SUBMIT':
                    symbol = "📝"
                elif outcome == 'REJECTED':
                    symbol = "❌"
                else:
                    symbol = "⚪"
                
                print(f"{symbol} {ts} | {outcome:15} | {underlying}")
                
                # Show gate results if available
                if 'gate_results' in decision:
                    gates = decision['gate_results']
                    all_pass = all(g.get('status') == 'PASS' for g in gates.values())
                    if all_pass:
                        print(f"     Gates: All PASS ✓")
                    else:
                        failed = [k for k, v in gates.items() if v.get('status') != 'PASS']
                        print(f"     Gates: {', '.join(failed)} failed")
                
            except json.JSONDecodeError:
                continue
        
        print()
        
    except FileNotFoundError:
        print(f"No log file found at {log_path}")
        print("The scheduler may not have run yet.")
        print()
    except Exception as e:
        print(f"Error reading log: {e}")
        print()


def check_market_status():
    """Check if market is currently open."""
    print_header("MARKET STATUS")
    
    now = datetime.now()
    market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
    
    is_weekday = now.weekday() < 5
    is_market_hours = market_open <= now <= market_close
    
    if is_weekday and is_market_hours:
        print("🟢 Market is OPEN")
    else:
        print("🔴 Market is CLOSED")
    
    print(f"Current Time: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Day: {now.strftime('%A')}")
    print(f"Market Hours: 9:30 AM - 4:00 PM ET")
    print()


def main():
    """Run all status checks."""
    print("\n")
    print_header("ALPACA TRADING AGENT - STATUS CHECK")
    
    check_market_status()
    check_account_status()
    check_trading_activity()
    
    print_header("STATUS CHECK COMPLETE")
    print("Run this script anytime to check on the trading agent.")
    print("For continuous monitoring, use: tail -f logs/decisions.jsonl")
    print()


if __name__ == "__main__":
    main()
