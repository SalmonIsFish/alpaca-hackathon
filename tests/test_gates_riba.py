"""Account-level Riba gate.

Added 2026-09-02 alongside agent/gates/riba.py. Fixtures use the real judged-account shape
(PA3W2J1H6I3X): a margin-capable account (multiplier 4, shorting_enabled) that is nonetheless
operating out of cash -- the distinction the gate exists to assert.
"""

from agent.gates.riba import check_account_riba

JUDGED = {"cash": "100273.83", "equity": "100077.83", "multiplier": "4",
          "shorting_enabled": True, "initial_margin": "94500"}

SHORT_PUT = {"asset_class": "us_option", "symbol": "AAPL260904P00307500", "qty": "-2"}


def test_real_judged_account_passes():
    r = check_account_riba(JUDGED, [SHORT_PUT], committed_collateral=94_500.0)
    assert r["status"] == "PASS"
    assert r["uncommitted_cash"] == 5773.83


def test_margin_capability_alone_does_not_reject():
    """multiplier 4 is the account type the broker issued; using it is what is prohibited."""
    r = check_account_riba(JUDGED, [], committed_collateral=0.0)
    assert r["status"] == "PASS"
    assert r["broker_margin_available"] is True


def test_cash_account_reports_no_margin_availability():
    r = check_account_riba({"cash": "50000", "multiplier": "1"}, [], committed_collateral=0.0)
    assert r["broker_margin_available"] is False


# --- the four prohibitions -------------------------------------------------
def test_negative_cash_is_rejected():
    r = check_account_riba({"cash": "-1200", "multiplier": "4"}, [], committed_collateral=0.0)
    assert r["status"] == "REJECT"
    assert r["reason"] == "negative_cash_balance_is_an_interest_bearing_loan"


def test_positions_financed_beyond_cash_are_rejected():
    """The pre-2026-09-02 production state: $201,500 committed on $100,273 of cash."""
    r = check_account_riba(JUDGED, [SHORT_PUT], committed_collateral=201_500.0)
    assert r["status"] == "REJECT"
    assert r["reason"] == "positions_financed_on_margin_not_cash"
    assert r["shortfall"] == 101_226.17


def test_short_equity_is_rejected():
    book = [{"asset_class": "us_equity", "symbol": "CVX", "qty": "-2"}]
    r = check_account_riba(JUDGED, book, committed_collateral=0.0)
    assert r["status"] == "REJECT"
    assert r["reason"] == "short_equity_position_requires_borrowing"


def test_interest_bearing_holding_is_rejected():
    book = [{"asset_class": "us_equity", "symbol": "TLT", "qty": "10"}]
    r = check_account_riba(JUDGED, book, committed_collateral=0.0)
    assert r["status"] == "REJECT"
    assert r["reason"] == "interest_bearing_instrument_held"
    assert r["symbol"] == "TLT"


def test_interest_bearing_check_is_case_insensitive():
    book = [{"asset_class": "us_equity", "symbol": "tlt", "qty": "10"}]
    assert check_account_riba(JUDGED, book, committed_collateral=0.0)["status"] == "REJECT"


# --- what must stay permitted ---------------------------------------------
def test_long_equity_and_short_options_are_permitted():
    book = [{"asset_class": "us_equity", "symbol": "CVX", "qty": "2"}, SHORT_PUT]
    assert check_account_riba(JUDGED, book, committed_collateral=94_500.0)["status"] == "PASS"


def test_exactly_fully_collateralized_passes():
    r = check_account_riba({"cash": "94500", "multiplier": "4"}, [SHORT_PUT],
                           committed_collateral=94_500.0)
    assert r["status"] == "PASS"
    assert r["uncommitted_cash"] == 0.0


def test_zero_cash_no_positions_passes():
    assert check_account_riba({"cash": "0"}, [], committed_collateral=0.0)["status"] == "PASS"


def test_missing_or_malformed_cash_field_is_treated_as_zero_not_infinite():
    r = check_account_riba({}, [], committed_collateral=1.0)
    assert r["status"] == "REJECT"
    assert r["reason"] == "positions_financed_on_margin_not_cash"


def main() -> None:
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
    print("PASS: test_gates_riba")


if __name__ == "__main__":
    main()
