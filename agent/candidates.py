"""Deterministic cash-secured-put candidate generation and ranking.

rank_candidates() is pure (no I/O) -- fixed-input, fixed-output, fully unit-testable.
generate_candidates()/build_shortlist() wire it to the live `alpaca data option chain` /
`alpaca data latest-quote` commands.

Verified against real authenticated output on 2026-08-29 (testing account PA3V2Y8L0TCX):
`option chain`'s "snapshots" is a DICT keyed by OCC symbol (e.g. "AAPL260902P00205000"), not a
list, and per-contract entries carry no strike_price/expiration_date fields -- those are only
encoded in the OCC symbol itself, hence _parse_occ_symbol() below. Quote data lives under
latestQuote.bp/ap exactly as first guessed. `latest-quote`'s response nests the actual bid/ask
under a "quote" key, not top-level -- also fixed here after checking real output.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta

from agent import cli

DEFAULT_POLICY = {
    "min_dte": 1,
    "max_dte": 7,
    "target_otm_pct": 4.0,
    "min_otm_pct": 2.0,
    "max_otm_pct": 7.0,
    "min_premium_per_share": 0.05,
    "max_spread_pct_of_mid": 15.0,
    # Sizing target, not a hard cap -- the risk gate (MAX_POSITION_PCT) is the hard backstop.
    # 35%, not something tighter: this universe is $190-500+/share, so 1 contract of a
    # cash-secured put already costs 20-35% of a $100k account structurally (verified against
    # real candidates 2026-08-29) -- a tighter target would reject 1-contract trades outright,
    # not make them safer.
    "target_position_pct": 35.0,
}

SHARES_PER_CONTRACT = 100


_OCC_RE = re.compile(r"^(?P<root>[A-Z]+)(?P<date>\d{6})(?P<type>[CP])(?P<strike>\d{8})$")


def parse_occ_symbol(symbol: str) -> dict:
    """AAPL260902P00205000 -> root AAPL, expiration 2026-09-02, type put, strike 205.0."""
    match = _OCC_RE.match(symbol)
    if not match:
        raise ValueError(f"not a recognizable OCC option symbol: {symbol!r}")
    yy, mm, dd = match["date"][:2], match["date"][2:4], match["date"][4:]
    expiration_date = f"20{yy}-{mm}-{dd}"
    strike_price = int(match["strike"]) / 1000
    option_type = "call" if match["type"] == "C" else "put"
    return {
        "root": match["root"],
        "expiration_date": expiration_date,
        "type": option_type,
        "strike_price": strike_price,
    }


def _snapshots_to_rows(snapshots: dict) -> list[dict]:
    """`option chain`'s "snapshots" is {OCC_symbol: {latestQuote, latestTrade, greeks, ...}}.
    Flatten into rows carrying symbol/strike/expiration_date alongside the raw snapshot."""
    rows = []
    for symbol, snapshot in snapshots.items():
        try:
            parsed = parse_occ_symbol(symbol)
        except ValueError:
            continue
        rows.append({"symbol": symbol, **parsed, **snapshot})
    return rows


def _extract_quote(contract: dict) -> tuple[float | None, float | None]:
    """Bid/ask from a flattened chain row's latestQuote -- confirmed against real output:
    latestQuote.bp / latestQuote.ap."""
    quote = contract.get("latestQuote") or {}
    bid = quote.get("bp")
    ask = quote.get("ap")
    return (float(bid) if bid is not None else None, float(ask) if ask is not None else None)


def rank_candidates(
    chain: list[dict], *, spot: float, today: date, policy: dict
) -> tuple[list[dict], dict]:
    """Pure. chain rows expected to carry: symbol, strike_price, expiration_date, and a quote
    (see _extract_quote). Returns (eligible_sorted, rejected_counts)."""
    eligible: list[dict] = []
    rejected = {
        "expired_or_out_of_dte_window": 0,
        "out_of_otm_band": 0,
        "no_live_bid": 0,
        "premium_below_floor": 0,
        "spread_too_wide": 0,
    }

    for row in chain:
        strike = float(row["strike_price"])
        expiration = datetime.strptime(row["expiration_date"], "%Y-%m-%d").date()
        dte = (expiration - today).days

        if dte < policy["min_dte"] or dte > policy["max_dte"]:
            rejected["expired_or_out_of_dte_window"] += 1
            continue

        otm_pct = ((spot - strike) / spot) * 100
        if otm_pct < policy["min_otm_pct"] or otm_pct > policy["max_otm_pct"]:
            rejected["out_of_otm_band"] += 1
            continue

        bid, ask = _extract_quote(row)
        if bid is None or bid <= 0:
            rejected["no_live_bid"] += 1
            continue

        if bid < policy["min_premium_per_share"]:
            rejected["premium_below_floor"] += 1
            continue

        mid = (bid + ask) / 2 if ask else bid
        spread_pct = ((ask - bid) / mid * 100) if (ask and mid) else 0.0
        if spread_pct > policy["max_spread_pct_of_mid"]:
            rejected["spread_too_wide"] += 1
            continue

        eligible.append(
            {
                "symbol": row.get("symbol"),
                "strike": strike,
                "expiration_date": row["expiration_date"],
                "dte": dte,
                "otm_pct": otm_pct,
                "bid": bid,
                "ask": ask,
                "premium_per_share": bid,
            }
        )

    eligible.sort(
        key=lambda c: (
            abs(c["otm_pct"] - policy["target_otm_pct"]),
            -c["dte"],
            -c["premium_per_share"],
            c["symbol"],
        )
    )
    return eligible, rejected


def generate_candidates(
    underlying: str,
    *,
    cash_available: float,
    equity: float,
    policy: dict | None = None,
    profile: str,
) -> list[dict]:
    policy = policy or DEFAULT_POLICY
    today = date.today()
    quote_response = cli.latest_quote(underlying, profile=profile)
    inner_quote = quote_response.get("quote", {})
    spot = float(inner_quote.get("ap") or inner_quote.get("bp"))

    gte = today.isoformat()
    lte = (today + timedelta(days=policy["max_dte"])).isoformat()
    chain_response = cli.option_chain(
        underlying,
        option_type="put",
        expiration_date_gte=gte,
        expiration_date_lte=lte,
        profile=profile,
    )
    chain = _snapshots_to_rows(chain_response.get("snapshots", {}))
    chain = [r for r in chain if r.get("type") == "put"]  # cash-secured puts only
    ranked, _ = rank_candidates(chain, spot=spot, today=today, policy=policy)

    target_value = equity * (policy["target_position_pct"] / 100)
    sized = []
    for candidate in ranked:
        cost_per_contract = candidate["strike"] * SHARES_PER_CONTRACT
        max_affordable = int(cash_available // cost_per_contract)
        if max_affordable < 1:
            continue  # can't afford even 1 contract -- not a candidate at all
        # size toward the target, but never below 1 (options are integer contracts) and
        # never above what's actually affordable
        contracts = max(1, min(max_affordable, int(target_value // cost_per_contract)))
        sized.append(
            {
                **candidate,
                "underlying": underlying,
                "contracts": contracts,
                "cash_required": contracts * cost_per_contract,
            }
        )
    return sized


def build_shortlist(
    universe_symbols: list[str],
    *,
    cash_available: float,
    equity: float,
    policy: dict | None = None,
    profile: str,
    cap: int = 8,
) -> list[dict]:
    """Loop the whole curated universe, not one hardcoded symbol -- the agent decides *what*
    to consider, which is what makes candidate generation part of the autonomy story."""
    pooled: list[dict] = []
    for symbol in universe_symbols:
        try:
            pooled.extend(
                generate_candidates(
                    symbol,
                    cash_available=cash_available,
                    equity=equity,
                    policy=policy,
                    profile=profile,
                )
            )
        except (cli.AlpacaCliError, KeyError, ValueError, TypeError):
            continue
    return pooled[:cap]
