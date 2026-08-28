"""Deterministic Shariah-compliance gate: a curated symbol allow-list.

Fails closed -- any symbol not explicitly on the list is rejected. This is a deliberately
small, hand-curated substitute for the full SEC-EDGAR-backed screen in the reference project;
see BUILD_PLAN.md for why that full screen is out of scope for this build.
"""

from __future__ import annotations

import json
from pathlib import Path


def load_universe(path: Path) -> dict[str, dict]:
    """Load the curated symbol -> {"rationale": str, "added": "YYYY-MM-DD"} map."""
    data = json.loads(Path(path).read_text())
    return {symbol.strip().upper(): info for symbol, info in data.items()}


def check_symbol(symbol: str, universe: dict[str, dict]) -> dict:
    key = symbol.strip().upper()
    if key in universe:
        return {"status": "PASS", "reason": "on_curated_list", "symbol": key}
    return {"status": "REJECT", "reason": "not_on_curated_list", "symbol": key}
