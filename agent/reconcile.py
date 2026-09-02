"""Reconcile the decisions log against what the broker actually holds.

Added 2026-09-02. The dashboard and the nightly report both derived "premium collected" and
"collateral held" by summing `SUBMITTED` rows out of `logs/decisions.jsonl`. A `SUBMITTED` row
only means the CLI accepted an order -- it says nothing about whether that order ever filled.
On PA3W2J1H6I3X seven `SUBMITTED` rows produced three actually-held contracts, so the log-only
arithmetic reported $921.90 of premium and $201,500 of collateral against a real book holding
$274 and $94,500. Anything a judge reads has to come from `position_list`, not from our own
record of what we asked for.

Every function here is pure: broker rows in, numbers out. No I/O, no CLI, no clock.
"""

from __future__ import annotations

from agent.candidates import SHARES_PER_CONTRACT, parse_occ_symbol


def short_put_positions(positions: list[dict]) -> list[dict]:
    """Open short puts only, each annotated with its parsed strike/expiration/underlying.

    Long options are excluded (they owe no collateral and cost premium rather than earning
    it); equity legs are excluded; anything whose symbol will not parse as OCC is skipped
    rather than crashing the dashboard.
    """
    out = []
    for position in positions or []:
        if position.get("asset_class") != "us_option":
            continue
        try:
            qty = float(position.get("qty", 0))
        except (TypeError, ValueError):
            continue
        if qty >= 0:
            continue
        symbol = position.get("symbol", "")
        try:
            parsed = parse_occ_symbol(symbol)
        except ValueError:
            continue
        if parsed["type"] != "put":
            continue

        def _num(key: str) -> float:
            try:
                return float(position.get(key) or 0)
            except (TypeError, ValueError):
                return 0.0

        contracts = int(abs(qty))
        out.append(
            {
                "symbol": symbol,
                "underlying": parsed["root"],
                "strike": parsed["strike_price"],
                "expiration_date": parsed["expiration_date"],
                "contracts": contracts,
                "avg_entry_price": _num("avg_entry_price"),
                "current_price": _num("current_price"),
                "unrealized_pl": _num("unrealized_pl"),
                "premium_received": _num("avg_entry_price") * SHARES_PER_CONTRACT * contracts,
                "collateral": parsed["strike_price"] * SHARES_PER_CONTRACT * contracts,
            }
        )
    return out


def reconcile_attribution(positions: list[dict], official_decisions: list[dict]) -> dict:
    """Broker-truth P&L attribution, with the log kept alongside for the audit trail.

    `premium_collected`, `collateral_held`, `mtm_unrealized` and `open_positions` all come
    from `positions`. The log-derived figures are retained under explicit `*_submitted_log`
    names so the gap between "what the agent asked for" and "what the broker did" stays
    visible rather than being quietly reconciled away -- that gap is itself evidence about
    the agent's behaviour.
    """
    held = short_put_positions(positions)
    held_symbols = {p["symbol"] for p in held}

    premium_collected = sum(p["premium_received"] for p in held)
    collateral_held = sum(p["collateral"] for p in held)
    mtm_unrealized = sum(p["unrealized_pl"] for p in held)

    premium_by_underlying: dict[str, float] = {}
    for p in held:
        premium_by_underlying[p["underlying"]] = (
            premium_by_underlying.get(p["underlying"], 0.0) + p["premium_received"]
        )

    submitted = [d for d in (official_decisions or []) if d.get("outcome") == "SUBMITTED"]
    premium_submitted_log = 0.0
    unfilled = []
    for d in submitted:
        selected = d.get("selected") or {}
        try:
            premium_submitted_log += (
                float(selected.get("premium_per_share") or 0)
                * SHARES_PER_CONTRACT
                * int(selected.get("contracts") or 1)
            )
        except (TypeError, ValueError):
            pass
        symbol = selected.get("symbol")
        if symbol and symbol not in held_symbols:
            unfilled.append(symbol)

    return {
        # --- broker truth ---
        "premium_collected": round(premium_collected, 2),
        "collateral_held": round(collateral_held, 2),
        "mtm_unrealized": round(mtm_unrealized, 2),
        "open_positions": len(held),
        "premium_by_underlying": {k: round(v, 2) for k, v in premium_by_underlying.items()},
        # --- audit trail: what we asked for vs what stuck ---
        "orders_submitted": len(submitted),
        "orders_open": len([d for d in submitted if (d.get("selected") or {}).get("symbol") in held_symbols]),
        "premium_submitted_log": round(premium_submitted_log, 2),
        "unfilled_or_closed": sorted(set(unfilled)),
        "positions": held,
    }
