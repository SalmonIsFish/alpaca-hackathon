"""Environment-based configuration. Never prints secret values -- only booleans."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


_load_dotenv(REPO_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    alpaca_profile: str
    featherless_api_key: str
    featherless_model: str
    shariah_universe_path: Path
    max_orders_per_day: int
    max_position_pct: float
    max_daily_loss_pct: float
    decisions_log_path: Path


_REQUIRED = ("FEATHERLESS_API_KEY", "FEATHERLESS_MODEL")


def get_settings() -> Settings:
    missing = [name for name in _REQUIRED if not os.environ.get(name)]
    if missing:
        raise RuntimeError(
            f"Missing required environment variable(s): {', '.join(missing)}. "
            f"Copy .env.example to .env and fill them in."
        )
    return Settings(
        alpaca_profile=os.environ.get("ALPACA_PROFILE", "testing"),
        featherless_api_key=os.environ["FEATHERLESS_API_KEY"],
        featherless_model=os.environ["FEATHERLESS_MODEL"],
        shariah_universe_path=REPO_ROOT
        / os.environ.get("SHARIAH_UNIVERSE_PATH", "data/shariah_universe.json"),
        max_orders_per_day=int(os.environ.get("MAX_ORDERS_PER_DAY", "3")),
        max_position_pct=float(os.environ.get("MAX_POSITION_PCT", "5")),
        max_daily_loss_pct=float(os.environ.get("MAX_DAILY_LOSS_PCT", "3")),
        decisions_log_path=REPO_ROOT / os.environ.get("DECISIONS_LOG_PATH", "logs/decisions.jsonl"),
    )


_ALL_VARS = (
    "ALPACA_PROFILE",
    "ALPACA_LIVE_TRADE",
    "FEATHERLESS_API_KEY",
    "FEATHERLESS_MODEL",
    "SHARIAH_UNIVERSE_PATH",
    "MAX_ORDERS_PER_DAY",
    "MAX_POSITION_PCT",
    "MAX_DAILY_LOSS_PCT",
    "DECISIONS_LOG_PATH",
)


def _main() -> None:
    """Print which config vars are set, as booleans only -- never values."""
    for name in _ALL_VARS:
        print(f"{name}: {'set' if os.environ.get(name) else 'MISSING'}")
    live_trade = os.environ.get("ALPACA_LIVE_TRADE", "").strip().lower()
    if live_trade in ("1", "true", "yes"):
        print("WARNING: ALPACA_LIVE_TRADE is set to a truthy value -- this must stay false/unset.")


if __name__ == "__main__":
    _main()
