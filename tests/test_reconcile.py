"""Reconciliation of the decisions log against real broker positions.

Added 2026-09-02. Fixtures are the actual PA3W2J1H6I3X discrepancy: seven SUBMITTED rows
claiming $921.90 of premium and $201,500 of collateral, against a book that really held
three contracts worth $274 and $94,500.
"""

from agent.reconcile import reconcile_attribution, short_put_positions


def _pos(symbol, qty, avg, mark="0", upl="0"):
    return {"asset_class": "us_option", "symbol": symbol, "qty": qty,
            "avg_entry_price": avg, "current_price": mark, "unrealized_pl": upl}


def _submitted(symbol, premium, contracts, underlying):
    return {"outcome": "SUBMITTED", "underlying": underlying,
            "selected": {"symbol": symbol, "premium_per_share": premium, "contracts": contracts}}


REAL_BOOK = [
    _pos("AAPL260904P00307500", "-2", "0.695", "0.13", "113"),
    _pos("GOOGL260904P00330000", "-1", "1.35", "1.7", "-35"),
]

REAL_LOG = [
    _submitted("AAPL260904P00307500", 0.67, 1, "AAPL"),
    _submitted("AAPL260904P00307500", 0.67, 1, "AAPL"),
    _submitted("GOOGL260904P00330000", 1.31, 1, "GOOGL"),
    _submitted("CRM260904P00252500", 2.03, 1, "CRM"),
    _submitted("ADBE260904P00290000", 3.05, 1, "ADBE"),
    _submitted("AAPL260904P00317500", 0.74, 1, "AAPL"),
    _submitted("NVDA260904P00210000", 0.75, 1, "NVDA"),
]


def test_premium_comes_from_fills_not_from_submitted_rows():
    r = reconcile_attribution(REAL_BOOK, REAL_LOG)
    # 0.695*100*2 + 1.35*100*1
    assert r["premium_collected"] == 274.0
    assert r["premium_submitted_log"] == 922.00


def test_collateral_counts_only_contracts_actually_held():
    r = reconcile_attribution(REAL_BOOK, REAL_LOG)
    # 307.5*100*2 + 330*100*1 -- not the 201500 the log implied
    assert r["collateral_held"] == 94_500.0


def test_mtm_is_broker_unrealized_not_equity_minus_premium():
    r = reconcile_attribution(REAL_BOOK, REAL_LOG)
    assert r["mtm_unrealized"] == 78.0


def test_submitted_and_still_open_counts_are_both_reported():
    r = reconcile_attribution(REAL_BOOK, REAL_LOG)
    assert r["orders_submitted"] == 7
    assert r["orders_open"] == 3


def test_unfilled_set_is_exactly_the_four_that_never_stuck():
    r = reconcile_attribution(REAL_BOOK, REAL_LOG)
    assert set(r["unfilled_or_closed"]) == {
        "CRM260904P00252500", "ADBE260904P00290000",
        "AAPL260904P00317500", "NVDA260904P00210000",
    }


def test_premium_by_underlying_aggregates_multi_contract_rows():
    r = reconcile_attribution(REAL_BOOK, REAL_LOG)
    assert r["premium_by_underlying"] == {"AAPL": 139.0, "GOOGL": 135.0}


def test_long_options_and_equity_are_excluded():
    book = [
        {"asset_class": "us_equity", "symbol": "CVX", "qty": "2", "avg_entry_price": "207"},
        _pos("AAPL260904P00307500", "2", "0.695"),   # long put
        _pos("AAPL260904C00307500", "-2", "1.00"),   # short call
    ]
    assert short_put_positions(book) == []
    r = reconcile_attribution(book, [])
    assert r["premium_collected"] == 0
    assert r["collateral_held"] == 0


def test_empty_broker_response_reports_zero_not_the_log_total():
    """CLI unreachable must not fall back to the inflated log figure."""
    r = reconcile_attribution([], REAL_LOG)
    assert r["premium_collected"] == 0
    assert r["collateral_held"] == 0
    assert r["open_positions"] == 0
    assert r["premium_submitted_log"] == 922.00


def test_unparseable_symbol_skipped():
    r = reconcile_attribution([{"asset_class": "us_option", "symbol": "??", "qty": "-1"}], [])
    assert r["open_positions"] == 0


def main() -> None:
    test_premium_comes_from_fills_not_from_submitted_rows()
    test_collateral_counts_only_contracts_actually_held()
    test_mtm_is_broker_unrealized_not_equity_minus_premium()
    test_submitted_and_still_open_counts_are_both_reported()
    test_unfilled_set_is_exactly_the_four_that_never_stuck()
    test_premium_by_underlying_aggregates_multi_contract_rows()
    test_long_options_and_equity_are_excluded()
    test_empty_broker_response_reports_zero_not_the_log_total()
    test_unparseable_symbol_skipped()
    print("PASS: test_reconcile")


if __name__ == "__main__":
    main()
