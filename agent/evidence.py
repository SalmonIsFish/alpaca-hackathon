"""Append-only JSON-Lines evidence trail for every pipeline decision.

JSON Lines chosen over sqlite deliberately -- no schema/migrations to design this week,
trivially appendable and greppable/jq-able, and it's the simplest thing that both writes and
reads back today's history for the risk gate's orders_today/daily_pnl inputs.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path


def log_decision(record: dict, *, path: Path) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    full_record = {"timestamp": datetime.now(timezone.utc).isoformat(), **record}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(full_record) + "\n")
    return full_record


def todays_decisions(path: Path, *, today: date) -> list[dict]:
    if not path.exists():
        return []
    today_str = today.isoformat()
    decisions = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if record.get("timestamp", "").startswith(today_str):
            decisions.append(record)
    return decisions
