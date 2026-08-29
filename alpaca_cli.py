#!/usr/bin/env python3
"""
Python-based Alpaca CLI for server deployment.

Replaces the Go binary for environments where it's not available.
Uses Alpaca REST API directly with urllib (no external dependencies).

Supports:
- doctor: Check connectivity
- account get: Get account info
- position list: List positions
- data latest-quote: Get latest quote
- data option chain: Get option chain
- order submit: Submit orders
"""

from __future__ import annotations

import json
import os
import urllib.request
import urllib.error
import sys
from pathlib import Path


def load_dotenv():
    """Load environment variables from .env file."""
    env_path = Path(".env")
    if not env_path.exists():
        env_path = Path("/home/amanah/hackathon/.env")
    
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    # Only set if not already in environment
                    if key not in os.environ:
                        os.environ[key] = value


# Load .env on module import
load_dotenv()


class AlpacaPythonCli:
    """Python implementation of Alpaca CLI functionality."""
    
    def __init__(self):
        self.base_url = "https://paper-api.alpaca.markets"
        self.data_url = "https://data.alpaca.markets"
        
        # Support both naming conventions
        self.api_key = os.environ.get("ALPACA_API_KEY") or os.environ.get("ALPACA_API_KEY_ID")
        self.api_secret = os.environ.get("ALPACA_SECRET_KEY") or os.environ.get("ALPACA_SECRET_KEY_ID")
        
        # Load OAuth token from config if available
        self.oauth_token = self._load_oauth_token()
    
    def _load_oauth_token(self) -> str | None:
        """Load OAuth token from Alpaca config directory."""
        config_dir = Path.home() / ".config" / "alpaca"
        if not config_dir.exists():
            return None
        
        # Check for profiles
        profiles_file = config_dir / "profiles.yaml"
        if profiles_file.exists():
            # Simple YAML parsing for token
            content = profiles_file.read_text()
            for line in content.split("\n"):
                if "token:" in line.lower():
                    return line.split(":")[-1].strip().strip('"').strip("'")
        
        return None
    
    def _get_headers(self) -> dict[str, str]:
        """Get authentication headers."""
        if self.oauth_token:
            return {
                "Authorization": f"Bearer {self.oauth_token}",
                "Content-Type": "application/json"
            }
        elif self.api_key and self.api_secret:
            return {
                "APCA-API-KEY-ID": self.api_key,
                "APCA-API-SECRET-KEY": self.api_secret,
                "Content-Type": "application/json"
            }
        else:
            return {"Content-Type": "application/json"}
    
    def _api_request(self, url: str, method: str = "GET", data: dict = None) -> dict | str:
        """Make API request to Alpaca."""
        headers = self._get_headers()
        
        req_data = None
        if data:
            req_data = json.dumps(data).encode("utf-8")
        
        req = urllib.request.Request(
            url,
            data=req_data,
            headers=headers,
            method=method
        )
        
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                result = response.read().decode("utf-8")
                try:
                    return json.loads(result)
                except json.JSONDecodeError:
                    return result
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8")
            try:
                error_json = json.loads(error_body)
                return {"error": error_json, "status_code": e.code}
            except:
                return {"error": error_body, "status_code": e.code}
        except Exception as e:
            return {"error": str(e)}
    
    def doctor(self) -> dict:
        """Check CLI configuration and connectivity."""
        print("Alpaca CLI (Python) 1.0.0")
        print(f"  Python: {sys.version.split()[0]}")
        print(f"  OS/Arch: linux/amd64")
        print()
        print(f"Config: {Path.home() / '.config' / 'alpaca'}")
        print(f"  {'✓' if self.oauth_token or (self.api_key and self.api_secret) else '✗'} Credentials configured")
        print()
        print("Connectivity:")
        print(f"  Trading: {self.base_url}")
        
        # Test trading API
        result = self._api_request(f"{self.base_url}/v2/account")
        trading_ok = "error" not in result
        print(f"  {'✓' if trading_ok else '✗'} trading API: {'connected' if trading_ok else 'failed'}")
        
        print(f"  Data: {self.data_url}")
        
        # Test data API
        data_result = self._api_request(f"{self.data_url}/v2/stocks/AAPL/trades/latest")
        data_ok = "error" not in data_result
        print(f"  {'✓' if data_ok else '✗'} data API: {'connected' if data_ok else 'failed'}")
        
        print()
        if trading_ok and data_ok:
            print("All checks passed.")
            return {"ok": True}
        else:
            print("Some checks failed.")
            return {"ok": False, "error": "API connection failed"}
    
    def account_get(self) -> dict:
        """Get account information."""
        return self._api_request(f"{self.base_url}/v2/account")
    
    def position_list(self) -> list:
        """List positions."""
        result = self._api_request(f"{self.base_url}/v2/positions")
        if isinstance(result, list):
            return result
        return []
    
    def latest_quote(self, symbol: str) -> dict:
        """Get latest quote."""
        return self._api_request(f"{self.data_url}/v2/stocks/{symbol}/quotes/latest")
    
    def option_chain(
        self,
        underlying: str,
        option_type: str = "put",
        expiration_date_gte: str = None,
        expiration_date_lte: str = None,
    ) -> dict:
        """Get option chain."""
        url = f"{self.data_url}/v1/options/snapshots/{underlying}"
        return self._api_request(url)
    
    def order_submit(
        self,
        symbol: str,
        side: str,
        qty: int,
        order_type: str,
        limit_price: float = None,
        time_in_force: str = "day",
        client_order_id: str = None,
    ) -> dict:
        """Submit an order."""
        data = {
            "symbol": symbol,
            "side": side,
            "qty": str(qty),
            "type": order_type,
            "time_in_force": time_in_force,
        }
        
        if limit_price:
            data["limit_price"] = str(limit_price)
        
        if client_order_id:
            data["client_order_id"] = client_order_id
        
        return self._api_request(
            f"{self.base_url}/v2/orders",
            method="POST",
            data=data
        )


def main():
    """CLI entry point mimicking alpaca binary."""
    cli = AlpacaPythonCli()
    
    if len(sys.argv) < 2:
        print("Usage: python alpaca_cli.py <command> [args...]")
        print("Commands: doctor, account, position, data, order")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "doctor":
        result = cli.doctor()
        sys.exit(0 if result.get("ok") else 1)
    
    elif command == "account" and sys.argv[2] == "get":
        result = cli.account_get()
        print(json.dumps(result, indent=2))
    
    elif command == "position" and sys.argv[2] == "list":
        result = cli.position_list()
        print(json.dumps(result, indent=2))
    
    elif command == "data":
        if sys.argv[2] == "latest-quote":
            symbol = sys.argv[4] if len(sys.argv) > 4 else sys.argv[3]
            result = cli.latest_quote(symbol)
            print(json.dumps(result, indent=2))
        
        elif sys.argv[2] == "option" and sys.argv[3] == "chain":
            # Parse args
            underlying = None
            option_type = "put"
            
            i = 4
            while i < len(sys.argv):
                if sys.argv[i] == "--underlying-symbol":
                    underlying = sys.argv[i + 1]
                    i += 2
                elif sys.argv[i] == "--type":
                    option_type = sys.argv[i + 1]
                    i += 2
                else:
                    i += 1
            
            if underlying:
                result = cli.option_chain(underlying, option_type)
                print(json.dumps(result, indent=2))
    
    elif command == "order" and sys.argv[2] == "submit":
        # Parse order args
        kwargs = {}
        i = 3
        while i < len(sys.argv):
            if sys.argv[i].startswith("--"):
                key = sys.argv[i][2:].replace("-", "_")
                if i + 1 < len(sys.argv):
                    kwargs[key] = sys.argv[i + 1]
                    i += 2
                else:
                    i += 1
            else:
                i += 1
        
        result = cli.order_submit(**kwargs)
        print(json.dumps(result, indent=2))
    
    else:
        print(f"Unknown command: {' '.join(sys.argv[1:])}")
        sys.exit(1)


if __name__ == "__main__":
    main()
