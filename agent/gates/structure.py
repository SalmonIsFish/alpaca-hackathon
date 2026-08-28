"""Deterministic option-structure gate: cash-secured put only for this build.

No margin, ever. A put can only be sold to open if settled cash fully collateralizes every
contract at the strike -- the same rule a human options desk would apply, just enforced in
code with no exceptions.
"""

from __future__ import annotations

SHARES_PER_CONTRACT = 100


def check_cash_secured_put(
    *,
    cash_collateral: float,
    strike: float,
    contracts: int,
    uses_margin: bool,
) -> dict:
    if uses_margin:
        return {"status": "REJECT", "reason": "margin_not_permitted"}
    if strike is None or strike <= 0:
        return {"status": "REJECT", "reason": "strike_required"}
    if contracts is None or contracts <= 0:
        return {"status": "REJECT", "reason": "contracts_required"}
    required = contracts * SHARES_PER_CONTRACT * strike
    if cash_collateral >= required:
        return {"status": "PASS", "reason": "cash_secured", "cash_required": required}
    return {
        "status": "REJECT",
        "reason": "insufficient_cash_collateral",
        "cash_required": required,
        "cash_available": cash_collateral,
    }
