"""Gharar and maysir gates.

Added 2026-09-02. The system enforced riba but not the other two prohibitions. Fixtures use
shapes seen in real Alpaca chain data -- notably the one-sided quote (`"bp": 0, "bs": 0,
"bx": "?"`) that free-feed snapshots return on thin contracts, and the `ask: 0` that whole
underlyings return outside market hours.
"""

from agent.gates.gharar import check_gharar
from agent.gates.maysir import check_maysir


def candidate(**over):
    base = {"symbol": "AAPL260904P00307500", "strike": 307.5, "dte": 2,
            "bid": 0.70, "ask": 0.75, "contracts": 1, "cash_required": 30_750.0}
    base.update(over)
    return base


CASH = 100_000.0


# ============================ GHARAR ============================

def test_well_specified_contract_passes():
    r = check_gharar(candidate(), cash_available=CASH)
    assert r["status"] == "PASS"
    assert r["delivery_funded"] is True


def test_missing_bid_is_indeterminate_price():
    r = check_gharar(candidate(bid=0), cash_available=CASH)
    assert r["status"] == "REJECT"
    assert r["reason"] == "no_live_bid_price_is_indeterminate"


def test_one_sided_market_is_rejected():
    """Real free-feed shape: ask present, no bid at all -- or the reverse outside hours.

    The ranker tolerates a missing ask (it skips the spread test when ask is falsy), so this
    is a genuine gap the gharar gate closes rather than a duplicate check.
    """
    r = check_gharar(candidate(ask=0), cash_available=CASH)
    assert r["status"] == "REJECT"
    assert r["reason"] == "no_live_ask_price_is_one_sided"

    r = check_gharar(candidate(ask=None), cash_available=CASH)
    assert r["status"] == "REJECT"
    assert r["reason"] == "no_live_ask_price_is_one_sided"


def test_wide_spread_is_price_ambiguity():
    r = check_gharar(candidate(bid=1.00, ask=3.00), cash_available=CASH)
    assert r["status"] == "REJECT"
    assert r["reason"] == "spread_too_wide_price_ambiguous"


def test_distant_expiry_rejected():
    r = check_gharar(candidate(dte=30), cash_available=CASH)
    assert r["status"] == "REJECT"
    assert r["reason"] == "expiry_too_distant_to_assess"


def test_extreme_implied_volatility_rejected():
    r = check_gharar(candidate(implied_volatility=3.5), cash_available=CASH)
    assert r["status"] == "REJECT"
    assert r["reason"] == "implied_volatility_beyond_assessable_range"


def test_absent_iv_is_not_a_rejection():
    """The free feed omits IV on thin contracts; spread and DTE already bound the ambiguity."""
    assert check_gharar(candidate(), cash_available=CASH)["status"] == "PASS"
    assert check_gharar(candidate(implied_volatility=None), cash_available=CASH)["status"] == "PASS"


def test_unfunded_delivery_rejected():
    """The classical objection to derivatives: selling what you cannot deliver."""
    r = check_gharar(candidate(), cash_available=1_000.0)
    assert r["status"] == "REJECT"
    assert r["reason"] == "delivery_capacity_not_assured"


def test_unspecified_terms_rejected():
    assert check_gharar(candidate(strike=0), cash_available=CASH)["reason"] == "strike_not_specified"
    assert check_gharar(candidate(contracts=0), cash_available=CASH)["reason"] == "quantity_not_specified"
    assert check_gharar(candidate(dte=None), cash_available=CASH)["reason"] == "expiry_not_specified"


# ============================ MAYSIR ============================

MAYSIR_OK = {"spot": 316.0, "cash_available": CASH, "underlying_is_screened": True}


def test_funded_commitment_to_screened_asset_passes():
    r = check_maysir(candidate(), **MAYSIR_OK)
    assert r["status"] == "PASS"
    assert r["would_take_delivery"] is True
    assert r["acquisition_discount_pct"] == 2.69


def test_unscreened_underlying_rejected():
    """No version of this trade is acceptable if taking delivery would not be."""
    r = check_maysir(candidate(), spot=316.0, cash_available=CASH, underlying_is_screened=False)
    assert r["status"] == "REJECT"
    assert r["reason"] == "underlying_not_a_permissible_asset_to_acquire"


def test_naked_position_rejected():
    r = check_maysir(candidate(), spot=316.0, cash_available=10_000.0, underlying_is_screened=True)
    assert r["status"] == "REJECT"
    assert r["reason"] == "position_is_naked_not_a_funded_commitment"


def test_nominally_secured_but_committed_elsewhere_is_still_naked():
    """Capacity must survive obligations already outstanding, not just look adequate."""
    r = check_maysir(candidate(), spot=316.0, cash_available=CASH,
                     committed_collateral=94_500.0, underlying_is_screened=True)
    assert r["status"] == "REJECT"
    assert r["reason"] == "position_is_naked_not_a_funded_commitment"


def test_strike_above_market_is_not_an_acquisition():
    r = check_maysir(candidate(strike=320.0), **MAYSIR_OK)
    assert r["status"] == "REJECT"
    assert r["reason"] == "strike_at_or_above_market_not_an_acquisition_discount"


def test_zero_dte_is_a_wager_not_a_commitment():
    r = check_maysir(candidate(dte=0), **MAYSIR_OK)
    assert r["status"] == "REJECT"
    assert r["reason"] == "expiry_too_short_to_be_a_commitment"


def test_unknown_spot_rejected():
    r = check_maysir(candidate(), spot=0, cash_available=CASH, underlying_is_screened=True)
    assert r["status"] == "REJECT"
    assert r["reason"] == "underlying_price_unknown"


def main() -> None:
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
    print("PASS: test_gates_gharar_maysir")


if __name__ == "__main__":
    main()
