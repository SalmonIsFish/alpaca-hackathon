"""Deterministic gharar gate: refuses contracts whose terms are not actually knowable.

Gharar is uncertainty or ambiguity in a contract -- where price, quantity, quality, or the
ability to deliver are unknown at the moment of contracting. The prohibition (Qur'an 4:29 and
the hadith literature on selling fish in the sea, unborn livestock, unharvested crops) targets
consent given in ignorance: a contract one party cannot properly evaluate is not a fair
exchange, whatever both parties say.

Classical jurisprudence distinguishes *minor, unavoidable* uncertainty -- tolerated, because all
commerce carries some -- from *excessive* gharar that undermines the fairness of the contract.
This gate encodes that line for one specific instrument.

**The objection this gate does not pretend to dissolve.** Options are routinely named in the
gharar literature as a prohibited category, and AAOIFI standards generally prohibit conventional
options outright. This module does not claim otherwise and does not claim to settle the question.
What it does is enforce the conditions under which the classical objection is weakest -- terms
fully specified, price discoverable from a live two-sided market, delivery certain because it is
fully funded in cash. See `docs/shariah/position-cash-secured-puts.md` for the argument in full,
including where it is contested and what it would take to actually rely on it.

Deliberately narrow: this gate judges *contractual certainty only*. Whether the trade is
speculation is `gates/maysir.py`. Whether the account is interest-free is `gates/riba.py`.

Pure: dicts in, verdict out. No I/O, no clock, no network.
"""

from __future__ import annotations

SHARES_PER_CONTRACT = 100

# A two-sided quote is what makes a price *discoverable* rather than asserted. Real chain
# snapshots from the free feed return contracts with `"bp": 0, "bs": 0, "bx": "?"` -- no bid, no
# size, unknown exchange -- and outside market hours entire underlyings come back with `ask: 0`.
# Transacting against a quote with one side missing is contracting at a price nobody is actually
# making: textbook price ambiguity, and the case that motivated this gate.
MAX_SPREAD_PCT_OF_MID = 15.0

# Uncertainty compounds with time to expiry. The strategy is short-dated by design; this is the
# outer bound past which the terms stop being reasonably assessable.
MAX_DTE = 7

# An implied volatility this high means the market itself cannot agree what the contract is
# worth -- the defining condition of excessive gharar rather than ordinary commercial risk.
MAX_IMPLIED_VOLATILITY = 2.00  # 200% annualised


def _to_float(value, default=None):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def check_gharar(
    candidate: dict,
    *,
    cash_available: float,
    max_spread_pct: float = MAX_SPREAD_PCT_OF_MID,
    max_dte: int = MAX_DTE,
    max_iv: float = MAX_IMPLIED_VOLATILITY,
) -> dict:
    """Reject a contract whose terms are ambiguous, unpriceable, or undeliverable.

    `candidate` is a ranked candidate dict (symbol, strike, dte, bid, ask, contracts,
    cash_required) optionally carrying `implied_volatility` from the chain snapshot.
    """
    symbol = candidate.get("symbol")

    # 1. The subject matter must be fully specified. A contract missing its strike, expiry or
    #    quantity is not underspecified paperwork -- it is not a contract.
    strike = _to_float(candidate.get("strike"))
    contracts = candidate.get("contracts")
    dte = candidate.get("dte")
    if not strike or strike <= 0:
        return {"status": "REJECT", "reason": "strike_not_specified", "symbol": symbol}
    if not contracts or int(contracts) <= 0:
        return {"status": "REJECT", "reason": "quantity_not_specified", "symbol": symbol}
    if dte is None:
        return {"status": "REJECT", "reason": "expiry_not_specified", "symbol": symbol}

    # 2. Price must be discoverable from a live two-sided market, not inferred from one side.
    bid = _to_float(candidate.get("bid"))
    ask = _to_float(candidate.get("ask"))
    if bid is None or bid <= 0:
        return {"status": "REJECT", "reason": "no_live_bid_price_is_indeterminate", "symbol": symbol}
    if ask is None or ask <= 0:
        # The ranker tolerates a missing ask (it skips the spread test when ask is falsy).
        # For gharar purposes a one-sided market is exactly the ambiguity being prohibited.
        return {"status": "REJECT", "reason": "no_live_ask_price_is_one_sided", "symbol": symbol}

    mid = (bid + ask) / 2
    spread_pct = (ask - bid) / mid * 100
    if spread_pct > max_spread_pct:
        return {
            "status": "REJECT",
            "reason": "spread_too_wide_price_ambiguous",
            "symbol": symbol,
            "spread_pct": round(spread_pct, 2),
            "max_spread_pct": max_spread_pct,
        }

    # 3. Time. Beyond the strategy's horizon the terms stop being reasonably assessable.
    if int(dte) > max_dte:
        return {
            "status": "REJECT",
            "reason": "expiry_too_distant_to_assess",
            "symbol": symbol,
            "dte": int(dte),
            "max_dte": max_dte,
        }

    # 4. Where the market itself cannot price the contract, the uncertainty is excessive rather
    #    than ordinary. Absent IV is not a rejection -- the free feed omits it on thin contracts,
    #    and checks 2 and 3 already bound the ambiguity.
    iv = _to_float(candidate.get("implied_volatility"))
    if iv is not None and iv > max_iv:
        return {
            "status": "REJECT",
            "reason": "implied_volatility_beyond_assessable_range",
            "symbol": symbol,
            "implied_volatility": iv,
            "max_implied_volatility": max_iv,
        }

    # 5. Ability to deliver. This is the classical heart of the gharar objection to derivatives:
    #    selling what one cannot deliver. A cash-secured put inverts it -- the obligation is to
    #    BUY, and the cash to buy is already present and unencumbered. Delivery is not uncertain.
    required = strike * SHARES_PER_CONTRACT * int(contracts)
    if cash_available < required:
        return {
            "status": "REJECT",
            "reason": "delivery_capacity_not_assured",
            "symbol": symbol,
            "required": required,
            "cash_available": cash_available,
        }

    return {
        "status": "PASS",
        "reason": "contract_terms_fully_determinate",
        "symbol": symbol,
        "strike": strike,
        "contracts": int(contracts),
        "dte": int(dte),
        "spread_pct": round(spread_pct, 2),
        "delivery_obligation": required,
        "delivery_funded": True,
    }
