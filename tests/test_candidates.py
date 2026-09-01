from datetime import date, timedelta

from agent.candidates import DEFAULT_POLICY, rank_candidates

TODAY = date(2026, 8, 29)
SPOT = 200.0


def _row(strike, dte, bid, ask, symbol="TEST260905P00190000"):
    expiration = (TODAY + timedelta(days=dte)).isoformat()
    return {
        "symbol": symbol,
        "strike_price": strike,
        "expiration_date": expiration,
        "latestQuote": {"bp": bid, "ap": ask},
    }


def test_rejects_outside_dte_window():
    chain = [_row(strike=190, dte=10, bid=0.5, ask=0.55)]
    eligible, rejected = rank_candidates(chain, spot=SPOT, today=TODAY, policy=DEFAULT_POLICY)
    assert eligible == []
    assert rejected["expired_or_out_of_dte_window"] == 1


def test_rejects_outside_otm_band():
    # strike 199 is only 0.5% OTM, band is 2-7%
    chain = [_row(strike=199, dte=5, bid=0.5, ask=0.55)]
    eligible, rejected = rank_candidates(chain, spot=SPOT, today=TODAY, policy=DEFAULT_POLICY)
    assert eligible == []
    assert rejected["out_of_otm_band"] == 1


def test_rejects_no_live_bid():
    chain = [_row(strike=190, dte=5, bid=0, ask=0.55)]
    eligible, rejected = rank_candidates(chain, spot=SPOT, today=TODAY, policy=DEFAULT_POLICY)
    assert eligible == []
    assert rejected["no_live_bid"] == 1


def test_rejects_premium_below_floor():
    chain = [_row(strike=190, dte=5, bid=0.01, ask=0.02)]
    eligible, rejected = rank_candidates(chain, spot=SPOT, today=TODAY, policy=DEFAULT_POLICY)
    assert eligible == []
    assert rejected["premium_below_floor"] == 1


def test_rejects_wide_spread():
    # mid 1.00, spread 40% >>15% cap, bid 0.80 passes premium 0.70 floor
    chain = [_row(strike=190, dte=5, bid=0.80, ask=1.20)]
    eligible, rejected = rank_candidates(chain, spot=SPOT, today=TODAY, policy=DEFAULT_POLICY)
    assert eligible == []
    assert rejected["spread_too_wide"] == 1


def test_accepts_eligible_candidate():
    # strike 192 -> 4% OTM exactly, within DTE window, live bid, tight spread, passes 0.70 floor
    chain = [_row(strike=192, dte=5, bid=0.80, ask=0.84)]
    eligible, rejected = rank_candidates(chain, spot=SPOT, today=TODAY, policy=DEFAULT_POLICY)
    assert len(eligible) == 1
    assert eligible[0]["strike"] == 192
    assert all(v == 0 for v in rejected.values())


def test_deterministic_tie_break_ordering():
    # Two candidates equally close to target OTM (3%) -- 190 (5% OTM) and 194 (3% OTM) are
    # both within the 2-7% band; ranking must be stable across repeated calls.
    chain = [
        _row(strike=190, dte=5, bid=0.80, ask=0.84, symbol="B"),
        _row(strike=194, dte=5, bid=0.85, ask=0.89, symbol="A"),
    ]
    first, _ = rank_candidates(chain, spot=SPOT, today=TODAY, policy=DEFAULT_POLICY)
    second, _ = rank_candidates(chain, spot=SPOT, today=TODAY, policy=DEFAULT_POLICY)
    assert [c["symbol"] for c in first] == [c["symbol"] for c in second]


def main() -> None:
    test_rejects_outside_dte_window()
    test_rejects_outside_otm_band()
    test_rejects_no_live_bid()
    test_rejects_premium_below_floor()
    test_rejects_wide_spread()
    test_accepts_eligible_candidate()
    test_deterministic_tie_break_ordering()
    print("PASS: test_candidates")


if __name__ == "__main__":
    main()
