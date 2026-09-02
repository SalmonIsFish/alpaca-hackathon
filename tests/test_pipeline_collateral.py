"""Cover the pure collateral-accounting helper that feeds the structure gate.

Added 2026-09-02. The judged account PA3W2J1H6I3X had committed $201,500 of short-put
collateral against $100,273 of cash while every decision logged "PASS: cash_secured" --
because nothing ever summed the open book. These fix the shape of that arithmetic.
"""

from agent.pipeline import committed_put_collateral


def _short_put(symbol: str, qty: str) -> dict:
    return {"asset_class": "us_option", "symbol": symbol, "qty": qty, "side": "short"}


def test_empty_and_none_positions_owe_nothing():
    assert committed_put_collateral([]) == 0.0
    assert committed_put_collateral(None) == 0.0


def test_single_short_put_is_strike_times_100_times_contracts():
    # AAPL 307.5 put, 2 contracts -> 307.5 * 100 * 2
    assert committed_put_collateral([_short_put("AAPL260904P00307500", "-2")]) == 61_500.0


def test_sums_the_real_judged_book_to_201500():
    """The seven live PA3W2J1H6I3X short puts as of 2026-09-02."""
    book = [
        _short_put("AAPL260904P00307500", "-2"),
        _short_put("GOOGL260904P00330000", "-1"),
        _short_put("CRM260904P00252500", "-1"),
        _short_put("ADBE260904P00290000", "-1"),
        _short_put("AAPL260904P00317500", "-1"),
        _short_put("NVDA260904P00210000", "-1"),
    ]
    assert committed_put_collateral(book) == 201_500.0


def test_long_puts_owe_nothing():
    """Buying a put costs premium, not collateral -- must not inflate the obligation."""
    assert committed_put_collateral([{**_short_put("AAPL260904P00307500", "2"), "side": "long"}]) == 0.0


def test_short_calls_are_not_cash_secured_put_collateral():
    assert committed_put_collateral([_short_put("AAPL260904C00307500", "-2")]) == 0.0


def test_equity_positions_ignored():
    assert committed_put_collateral([{"asset_class": "us_equity", "symbol": "CVX", "qty": "-2"}]) == 0.0


def test_unparseable_symbol_is_skipped_not_fatal():
    book = [{"asset_class": "us_option", "symbol": "???", "qty": "-1"},
            _short_put("NVDA260904P00210000", "-1")]
    assert committed_put_collateral(book) == 21_000.0


def main() -> None:
    test_empty_and_none_positions_owe_nothing()
    test_single_short_put_is_strike_times_100_times_contracts()
    test_sums_the_real_judged_book_to_201500()
    test_long_puts_owe_nothing()
    test_short_calls_are_not_cash_secured_put_collateral()
    test_equity_positions_ignored()
    test_unparseable_symbol_is_skipped_not_fatal()
    print("PASS: test_pipeline_collateral")


if __name__ == "__main__":
    main()
