"""Thin subprocess wrapper around the `alpaca` CLI binary.

Not unit tested (subprocess + live network) -- verified manually against the real testing
account. Every call is scoped to one profile, passed explicitly; nothing here ever reads
ALPACA_LIVE_TRADE or assumes paper mode -- callers must pass the profile that was set up via
`alpaca profile login` (paper by default, per the CLI's own login command).
"""

from __future__ import annotations

import json
import subprocess


class AlpacaCliError(RuntimeError):
    def __init__(self, args: list[str], returncode: int, stdout: str, stderr: str):
        self.args_run = args
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        super().__init__(
            f"alpaca {' '.join(args)} exited {returncode}\nstdout: {stdout}\nstderr: {stderr}"
        )


def run_alpaca(*args: str, profile: str) -> dict | list | str:
    """Run `alpaca <args> --profile <profile>`, return parsed JSON stdout if possible.

    Raises AlpacaCliError on nonzero exit. Falls back to raw stdout text if it isn't valid
    JSON (some commands, e.g. `doctor`, print human-readable diagnostics on stdout).
    """
    full_args = [*args, "--profile", profile]
    result = subprocess.run(
        ["alpaca", *full_args],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise AlpacaCliError(full_args, result.returncode, result.stdout, result.stderr)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return result.stdout


def doctor(profile: str) -> dict:
    """Run `alpaca doctor`. Returns {"ok": bool, "stdout": str} -- does not raise on failure,
    since a failed doctor check (bad profile, no credentials) is exactly what callers need to
    detect and report, not an exception to unwind past."""
    result = subprocess.run(
        ["alpaca", "doctor", "--profile", profile],
        capture_output=True,
        text=True,
        timeout=30,
    )
    return {"ok": result.returncode == 0, "stdout": result.stdout, "stderr": result.stderr}


def account_get(profile: str) -> dict:
    return run_alpaca("account", "get", profile=profile)


def position_list(profile: str) -> list[dict]:
    result = run_alpaca("position", "list", profile=profile)
    return result if isinstance(result, list) else []


def option_chain(
    underlying_symbol: str,
    *,
    option_type: str,
    expiration_date_gte: str,
    expiration_date_lte: str,
    profile: str,
) -> dict:
    """Live quotes/greeks per contract -- use this, not `option contracts` (metadata only,
    no pricing)."""
    return run_alpaca(
        "data",
        "option",
        "chain",
        "--underlying-symbol",
        underlying_symbol,
        "--type",
        option_type,
        "--expiration-date-gte",
        expiration_date_gte,
        "--expiration-date-lte",
        expiration_date_lte,
        profile=profile,
    )


def latest_quote(symbol: str, *, profile: str) -> dict:
    """Underlying spot price (best bid/ask) -- feeds OTM% math in candidates.py."""
    return run_alpaca("data", "latest-quote", "--symbol", symbol, profile=profile)


def order_submit(
    *,
    symbol: str,
    side: str,
    qty: int,
    order_type: str,
    limit_price: float,
    time_in_force: str,
    client_order_id: str,
    profile: str,
) -> dict:
    return run_alpaca(
        "order",
        "submit",
        "--symbol",
        symbol,
        "--side",
        side,
        "--qty",
        str(qty),
        "--type",
        order_type,
        "--limit-price",
        str(limit_price),
        "--time-in-force",
        time_in_force,
        "--client-order-id",
        client_order_id,
        profile=profile,
    )
