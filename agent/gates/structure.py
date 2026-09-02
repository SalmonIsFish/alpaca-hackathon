"""Deterministic option-structure gate: cash-secured put only for this build.

No margin, ever. A put can only be sold to open if settled cash fully collateralizes every
contract at the strike -- the same rule a human options desk would apply, just enforced in
code with no exceptions.

`committed_collateral` added 2026-09-02 after the judged account (PA3W2J1H6I3X) was found
holding $201,500 of short-put collateral against $100,273 of cash -- i.e. running ~2x broker
margin while every individual decision had logged "PASS: cash_secured". The bug was that this
gate only ever saw ONE trade's requirement compared against the FULL account cash balance, so
seven sequential trades each passed in isolation and the aggregate invariant this module's
first paragraph claims was never actually enforced. Cash is now netted against collateral
already committed by open short puts, which makes "no margin, ever" true book-wide rather than
trade-by-trade. Default 0.0 keeps the single-trade signature and its existing tests intact.
"""

from __future__ import annotations

SHARES_PER_CONTRACT = 100


def check_cash_secured_put(
    *,
    cash_collateral: float,
    strike: float,
    contracts: int,
    uses_margin: bool,
    committed_collateral: float = 0.0,
) -> dict:
    if uses_margin:
        return {"status": "REJECT", "reason": "margin_not_permitted"}
    if strike is None or strike <= 0:
        return {"status": "REJECT", "reason": "strike_required"}
    if contracts is None or contracts <= 0:
        return {"status": "REJECT", "reason": "contracts_required"}
    required = contracts * SHARES_PER_CONTRACT * strike
    # Cash still unencumbered by open short puts -- not the raw balance. Short-put premium
    # credits inflate `cash` while the collateral obligation lives outside it, so comparing
    # against the raw balance silently permits stacking past 100% of the account.
    uncommitted = cash_collateral - committed_collateral
    if uncommitted >= required:
        return {
            "status": "PASS",
            "reason": "cash_secured",
            "cash_required": required,
            "committed_collateral": committed_collateral,
            "uncommitted_cash": uncommitted,
        }
    return {
        "status": "REJECT",
        "reason": "insufficient_cash_collateral",
        "cash_required": required,
        "cash_available": uncommitted,
        "committed_collateral": committed_collateral,
    }
