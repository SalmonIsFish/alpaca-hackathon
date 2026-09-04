#!/usr/bin/env python3
"""
Setup wizard for configuring Alpaca credentials on the server.

This script helps configure the server for autonomous trading by:
1. Setting up Alpaca API credentials
2. Configuring the scheduler
3. Starting the services
"""

import os
import sys
import subprocess
from pathlib import Path


def print_header(title):
    print("=" * 70)
    print(title.center(70))
    print("=" * 70)
    print()


def check_current_config():
    """Check what's currently configured."""
    env_file = Path(".env")
    
    if not env_file.exists():
        print("❌ No .env file found")
        return False
    
    with open(env_file) as f:
        content = f.read()
    
    has_api_key = "ALPACA_API_KEY=" in content and "your_api_key" not in content
    has_oauth = "ALPACA_PROFILE=" in content
    has_featherless = "FEATHERLESS_API_KEY=" in content and "your_featherless" not in content
    
    print("Current configuration:")
    print(f"  ✓ OAuth Profile: {'Yes' if has_oauth else 'No'}")
    print(f"  ✓ API Keys: {'Yes' if has_api_key else 'No'}")
    print(f"  ✓ Featherless: {'Yes' if has_featherless else 'No'}")
    print()
    
    return has_api_key or has_oauth


def setup_api_keys():
    """Guide user through API key setup."""
    print("📋 API Key Setup")
    print("-" * 70)
    print("To get your API keys:")
    print("1. Go to https://alpaca.markets/")
    print("2. Log into your account")
    print("3. Go to 'Your API Keys' section")
    print()
    
    api_key = input("Enter your Alpaca API Key: ").strip()
    api_secret = input("Enter your Alpaca Secret Key: ").strip()
    
    if not api_key or not api_secret:
        print("❌ Invalid keys provided")
        return False
    
    # Update .env file
    env_file = Path(".env")
    with open(env_file) as f:
        lines = f.readlines()
    
    # Replace or add API keys
    new_lines = []
    api_key_added = False
    api_secret_added = False
    
    for line in lines:
        if line.startswith("ALPACA_API_KEY="):
            new_lines.append(f"ALPACA_API_KEY={api_key}\n")
            api_key_added = True
        elif line.startswith("ALPACA_SECRET_KEY="):
            new_lines.append(f"ALPACA_SECRET_KEY={api_secret}\n")
            api_secret_added = True
        else:
            new_lines.append(line)
    
    if not api_key_added:
        new_lines.append(f"ALPACA_API_KEY={api_key}\n")
    if not api_secret_added:
        new_lines.append(f"ALPACA_SECRET_KEY={api_secret}\n")
    
    with open(env_file, "w") as f:
        f.writelines(new_lines)
    
    print("✅ API keys saved to .env")
    return True


def setup_oauth():
    """Instructions for OAuth setup."""
    print("📋 OAuth Setup")
    print("-" * 70)
    print("To set up OAuth on the server:")
    print("1. SSH into the server with X11 forwarding:")
    print("   ssh -X -i ~/.ssh/<your_key> <user>@<your_server_ip>")
    print()
    print("2. Run: alpaca profile login --name testing")
    print("   (This will open a browser for OAuth)")
    print()
    print("3. After login, test with: ./alpaca doctor")
    print()
    input("Press Enter when you've completed OAuth setup...")
    return True


def test_connection():
    """Test Alpaca connection."""
    print("🧪 Testing connection...")
    
    result = subprocess.run(
        ["python3", "alpaca_cli.py", "doctor"],
        capture_output=True,
        text=True,
        env={**os.environ, **load_env()}
    )
    
    print(result.stdout)
    
    if "All checks passed" in result.stdout:
        print("✅ Connection successful!")
        return True
    else:
        print("❌ Connection failed")
        return False


def load_env():
    """Load environment variables from .env."""
    env = {}
    if os.path.exists(".env"):
        with open(".env") as f:
            for line in f:
                if "=" in line and not line.startswith("#"):
                    key, value = line.strip().split("=", 1)
                    env[key] = value
    return env


def start_scheduler():
    """Start the trading scheduler."""
    print("🚀 Starting scheduler...")
    
    result = subprocess.run(
        ["sudo", "systemctl", "start", "hackathon-scheduler"],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        print("✅ Scheduler started")
        print()
        print("Status:")
        subprocess.run(["sudo", "systemctl", "status", "hackathon-scheduler", "--no-pager"])
        return True
    else:
        print(f"❌ Failed to start: {result.stderr}")
        return False


def main():
    print_header("AMANAH TRADER - SERVER SETUP WIZARD")
    
    # Check current config
    has_config = check_current_config()
    
    if not has_config:
        print("You need to configure Alpaca credentials.")
        print()
        print("Choose setup method:")
        print("1. API Keys (recommended for servers)")
        print("2. OAuth (requires browser)")
        print()
        
        choice = input("Enter choice (1 or 2): ").strip()
        
        if choice == "1":
            if not setup_api_keys():
                print("Setup failed. Please try again.")
                sys.exit(1)
        elif choice == "2":
            if not setup_oauth():
                print("Setup failed. Please try again.")
                sys.exit(1)
        else:
            print("Invalid choice")
            sys.exit(1)
    
    # Test connection
    if not test_connection():
        print("Connection test failed. Please check your credentials.")
        sys.exit(1)
    
    # Ask to start scheduler
    print()
    start = input("Start the trading scheduler? (y/n): ").strip().lower()
    
    if start == "y":
        if start_scheduler():
            print()
            print_header("SETUP COMPLETE!")
            print("Your trading agent is now running autonomously!")
            print()
            print("Dashboard: https://amanahtrader.uk/hackathon/")
            print("Monitor: sudo journalctl -u hackathon-scheduler -f")
        else:
            print("Failed to start scheduler")
    else:
        print()
        print("Setup complete. Start manually with:")
        print("  sudo systemctl start hackathon-scheduler")


if __name__ == "__main__":
    main()
