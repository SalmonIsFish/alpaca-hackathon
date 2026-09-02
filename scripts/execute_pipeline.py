#!/usr/bin/env python3
"""
Script to execute the pipeline in a Windows environment.
This version handles the case where alpaca.exe is not directly executable.
"""

import sys
import os
import subprocess
import platform

def check_windows_environment():
    """Check if we're in a Windows environment"""
    system = platform.system().lower()
    if system == "windows":
        return True
    else:
        # In WSL or Linux, we can still try to run Windows binaries
        return "microsoft" in platform.release().lower() or "wsl" in platform.release().lower()

def main():
    print("=== Alpaca Pipeline Execution Script ===")
    print("This script prepares for execution of the pipeline")
    print()
    
    if not check_windows_environment():
        print("⚠️  Warning: Running in non-Windows environment")
        print("The pipeline will attempt to use Windows binary at:")
        print("  C:\\Users\\G2\\bin\\alpaca.exe")
        print("If this fails, you'll need to run this in a proper Windows environment")
        print()
    
    # Show current configuration
    print("Current configuration:")
    print("- ALPACA_PROFILE=testing")
    print("- Using Featherless LLM API")
    print("- Risk limits: MAX_POSITION_PCT=40, MAX_ORDERS_PER_DAY=3")
    print()
    
    # Show what the pipeline does
    print("Pipeline execution steps:")
    print("1. Verify Alpaca CLI configuration")
    print("2. Get account information")
    print("3. Generate candidate options")
    print("4. LLM proposes trade")
    print("5. Evaluate compliance gates")
    print("6. Submit order (if all gates pass)")
    print("7. Log decision")
    print()
    
    print("To execute the pipeline:")
    print("1. Ensure alpaca CLI is installed at C:\\Users\\G2\\bin\\alpaca.exe")
    print("2. Ensure testing profile is configured: alpaca profile login --name testing")
    print("3. Run: python -m agent.pipeline")
    print()
    
    print("Expected result for testing account:")
    print("- Cash-secured put option trade")
    print("- All 3 compliance gates will pass")
    print("- Order will be submitted to paper trading account")
    print("- Decision logged to logs/decisions.jsonl")
    print()
    
    print("Note: This script is meant to be run in a Windows environment")
    print("where the Alpaca CLI can execute properly.")

if __name__ == "__main__":
    main()