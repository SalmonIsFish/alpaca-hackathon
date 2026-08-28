"""Deterministic cash-secured-put candidate generation and ranking.

rank_candidates() is pure (no I/O) -- fixed-input, fixed-output, fully unit-testable.
generate_candidates()/build_shortlist() wire it to the live `alpaca data option chain` /
`alpaca data latest-quote` commands.

NOTE: the exact field names `alpaca data option chain` returns (bid/ask/last-trade keys,
whether it's `bp`/`ap` Alpaca-snapshot style or something else) have not been verified against
real authenticated output yet -- the CLI wasn't logged in to any account while this was
written. _extract_quote() below is a best-effort first pass and is the one thing to re-check
against real output the moment a profile is authenticated, before trusting generate_candidates
results.
"""

from __future__ import annotations

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
}

SHARES_PER_CONTRACT = 100


def _extract_quote(contract: dict) -> tuple[float | None, float | None]:
    """Best-effort bid/ask extraction -- verify against real `option chain` output."""
    quote = contract.get("latestQuote") or contract.get("latest_quote") or {}
    bid = quote.get("bp") or quote.get("bid_price") or quote.get("bid")
    ask = quote.get("ap") or quote.get("ask_price") or quote.get("ask")
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
    policy: dict | None = None,
    profile: str,
) -> list[dict]:
    policy = policy or DEFAULT_POLICY
    today = date.today()
    quote = cli.latest_quote(underlying, profile=profile)
    spot = float(quote.get("ap") or quote.get("bp") or quote.get("price"))

    gte = today.isoformat()
    lte = (today + timedelta(days=policy["max_dte"])).isoformat()
    chain_response = cli.option_chain(
        underlying,
        option_type="put",
        expiration_date_gte=gte,
        expiration_date_lte=lte,
        profile=profile,
    )
    chain = chain_response.get("snapshots") or chain_response.get("contracts") or []
    ranked, _ = rank_candidates(chain, spot=spot, today=today, policy=policy)

    sized = []
    for candidate in ranked:
        contracts = int(cash_available // (candidate["strike"] * SHARES_PER_CONTRACT))
        if contracts < 1:
            continue
        sized.append(
            {
                **candidate,
                "underlying": underlying,
                "contracts": contracts,
                "cash_required": contracts * SHARES_PER_CONTRACT * candidate["strike"],
            }
        )
    return sized


def build_shortlist(
    universe_symbols: list[str],
    *,
    cash_available: float,
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
                    symbol, cash_available=cash_available, policy=policy, profile=profile
                )
            )
        except (cli.AlpacaCliError, KeyError, ValueError, TypeError):
            continue
    return pooled[:cap]
