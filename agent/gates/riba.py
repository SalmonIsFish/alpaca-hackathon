"""Deterministic account-level Riba gate.

The other three gates judge a *proposed trade*. This one judges the *account it would land in* --
because a cash-secured put can be individually impeccable and still be booked into an account
that is financing itself with interest, which is the thing Riba actually prohibits.

Written 2026-09-02. `README.md` and `BUILD_PLAN.md` had described a four-stage chain since
kickoff, but only three gates existed; this closes that gap rather than quietly editing the
claim down to three.

The central distinction is between margin being *available* and margin being *used*. Alpaca
reports `multiplier: 4` and `shorting_enabled: true` on the judged account -- that is the
account type the broker issued, and it cannot be changed from here. What can be asserted, and
what actually matters, is that the account is *operating* as a cash account: positive settled
cash, every obligation covered by that cash rather than by broker credit, no borrowed stock,
and nothing held that pays or accrues interest.

Pure: dicts in, verdict out. No I/O, no clock, no network.
"""

from __future__ import annotations

SHARES_PER_CONTRACT = 100

# Instruments whose entire return is interest. Held long, these earn riba directly; this is a
# deliberately small, explicit list rather than a heuristic, because a fail-closed gate must be
# auditable. Anything not listed is caught by the Shariah universe screen upstream -- the
# agent can only ever trade symbols on that curated list, so this is defence in depth.
INTEREST_BEARING_SYMBOLS = frozenset({
    "BIL", "SHV", "SGOV", "SHY", "GOVT", "TLT", "IEF", "IEI", "TLH",
    "AGG", "BND", "BNDX", "LQD", "HYG", "JNK", "TIP", "VTIP",
    "VGSH", "VGIT", "VGLT", "ICSH", "NEAR", "MINT", "JPST", "USFR",
})


def _to_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def check_account_riba(
    account: dict,
    positions: list[dict],
    *,
    committed_collateral: float,
) -> dict:
    """Assert the account is operating interest-free, whatever the broker permits.

    `committed_collateral` is the total strike obligation of open short puts (see
    pipeline.committed_put_collateral) -- passed in rather than recomputed so this module stays
    pure and the two gates cannot disagree about the same number.
    """
    cash = _to_float(account.get("cash"))

    # 1. Negative cash is a broker loan, and a broker loan accrues interest. This is the
    #    unambiguous case: it is not a risk signal, it is the prohibited thing itself.
    if cash < 0:
        return {
            "status": "REJECT",
            "reason": "negative_cash_balance_is_an_interest_bearing_loan",
            "cash": cash,
        }

    # 2. Obligations must be met out of cash, not out of credit. An account can show positive
    #    cash while its open positions are financed on margin -- that is exactly the state the
    #    structure gate's per-trade check failed to catch before 2026-09-02.
    if committed_collateral > cash:
        return {
            "status": "REJECT",
            "reason": "positions_financed_on_margin_not_cash",
            "committed_collateral": committed_collateral,
            "cash": cash,
            "shortfall": round(committed_collateral - cash, 2),
        }

    # 3. Short equity requires borrowing shares, which carries a borrow fee -- interest by
    #    another name -- and sells what is not owned. Short *options* are permitted here: the
    #    put is fully cash-secured, which is what makes it a sale of obligation rather than a
    #    leveraged short.
    for position in positions or []:
        if position.get("asset_class") == "us_equity" and _to_float(position.get("qty")) < 0:
            return {
                "status": "REJECT",
                "reason": "short_equity_position_requires_borrowing",
                "symbol": position.get("symbol"),
                "qty": position.get("qty"),
            }

    # 4. Nothing held may be an instrument whose return *is* interest.
    for position in positions or []:
        symbol = (position.get("symbol") or "").upper()
        if symbol in INTEREST_BEARING_SYMBOLS:
            return {
                "status": "REJECT",
                "reason": "interest_bearing_instrument_held",
                "symbol": symbol,
            }

    return {
        "status": "PASS",
        "reason": "account_operating_interest_free",
        "cash": cash,
        "committed_collateral": committed_collateral,
        "uncommitted_cash": round(cash - committed_collateral, 2),
        # Recorded, not enforced: the broker issued a margin-capable account and that is not
        # ours to change. The gate's claim is that we do not *use* it -- checks 1-2 above are
        # what make that claim true, and logging the capability keeps the evidence honest
        # rather than implying we were handed a cash account.
        "broker_margin_available": account.get("multiplier") not in (None, "1", 1),
    }
