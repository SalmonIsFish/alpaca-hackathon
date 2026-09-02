"""Deterministic maysir gate: refuses positions that are wagers rather than commerce.

Maysir (qimar) is gambling -- acquiring wealth by chance rather than by productive effort or
genuine exchange. It is prohibited in the Qur'an (5:90) alongside intoxicants. The objection is
structural, not moral squeamishness about risk: a wager is a zero-sum transfer that creates no
value, where one party's gain is definitionally the other's loss, and neither has contributed
labour, goods, or shared enterprise risk.

Islamic commercial law draws a firm line between maysir and *mukhatarah* -- lawful commercial
risk. Ordinary trade and investment are permitted precisely because they involve effort, real
value creation, and the exchange of actual goods or services. Risk alone was never the problem.

**Where a short put sits on that line.** The gharar and maysir literature both name options,
but the qualifiers matter and this gate is built on them: the prohibited case is *pure
speculation* and *naked* positions. A naked put is a wager -- the seller has no capacity or
intention to take delivery and is transacting purely on price direction. A fully cash-secured
put written on a screened operating business, at a strike below market, is a different act: a
commitment to acquire a real productive asset at a price one has already set aside the money to
pay, compensated for making that commitment binding.

This gate does not assert that argument succeeds -- see
`docs/shariah/position-cash-secured-puts.md`, which states the objection, the conditions that
narrow it, and the fact that it remains contested. What this gate does is make the narrowing
conditions machine-enforced rather than asserted, so the distinction between the two cases is a
property of the system rather than a claim in a README.

Pure: dicts in, verdict out. No I/O, no clock, no network.
"""

from __future__ import annotations

SHARES_PER_CONTRACT = 100

# Below this, the position is a same-session price bet rather than a commitment to acquire.
# Intraday expiry is where premium selling most resembles a wager on a coin already in the air.
MIN_DTE_FOR_GENUINE_COMMITMENT = 1


def _to_float(value, default=None):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def check_maysir(
    candidate: dict,
    *,
    spot: float,
    cash_available: float,
    committed_collateral: float = 0.0,
    underlying_is_screened: bool,
    min_dte: int = MIN_DTE_FOR_GENUINE_COMMITMENT,
) -> dict:
    """Reject a position that is a wager rather than a funded commitment to acquire.

    `underlying_is_screened` comes from the Shariah business-activity gate -- passed in rather
    than recomputed, so the two gates cannot disagree about the same symbol.
    """
    symbol = candidate.get("symbol")
    strike = _to_float(candidate.get("strike"))
    contracts = int(candidate.get("contracts") or 0)

    # 1. The thing acquired must be a real productive asset. Writing puts on something that
    #    failed the business-activity screen is speculation on a price, not a wish to own a
    #    business -- there is no version of this trade where taking delivery is acceptable.
    if not underlying_is_screened:
        return {
            "status": "REJECT",
            "reason": "underlying_not_a_permissible_asset_to_acquire",
            "symbol": symbol,
        }

    # 2. Naked vs covered is the whole distinction. Capacity to take delivery must survive
    #    every obligation already outstanding -- otherwise the position is only nominally
    #    secured and is in substance a directional bet financed by the rest of the book.
    if not strike or strike <= 0 or contracts <= 0:
        return {"status": "REJECT", "reason": "position_not_specified", "symbol": symbol}
    obligation = strike * SHARES_PER_CONTRACT * contracts
    uncommitted = cash_available - committed_collateral
    if uncommitted < obligation:
        return {
            "status": "REJECT",
            "reason": "position_is_naked_not_a_funded_commitment",
            "symbol": symbol,
            "obligation": obligation,
            "uncommitted_cash": round(uncommitted, 2),
        }

    # 3. The strike must be a price at which acquiring the asset is genuinely attractive --
    #    i.e. below where it trades now. Writing puts above market is not a wish to buy at a
    #    discount; it is accepting a near-certain assignment in exchange for premium, which is
    #    a financing transaction wearing the clothes of a purchase commitment.
    spot_f = _to_float(spot)
    if not spot_f or spot_f <= 0:
        return {"status": "REJECT", "reason": "underlying_price_unknown", "symbol": symbol}
    if strike >= spot_f:
        return {
            "status": "REJECT",
            "reason": "strike_at_or_above_market_not_an_acquisition_discount",
            "symbol": symbol,
            "strike": strike,
            "spot": spot_f,
        }

    # 4. A commitment needs duration. Zero-day expiry collapses the acquisition rationale into
    #    a same-session bet on where the price closes.
    dte = candidate.get("dte")
    if dte is None or int(dte) < min_dte:
        return {
            "status": "REJECT",
            "reason": "expiry_too_short_to_be_a_commitment",
            "symbol": symbol,
            "dte": dte,
            "min_dte": min_dte,
        }

    discount_pct = (spot_f - strike) / spot_f * 100
    return {
        "status": "PASS",
        "reason": "funded_commitment_to_acquire_a_screened_asset",
        "symbol": symbol,
        "obligation": obligation,
        "acquisition_discount_pct": round(discount_pct, 2),
        "would_take_delivery": True,
        "dte": int(dte),
    }
