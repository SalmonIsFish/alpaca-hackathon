from agent.gates.structure import check_cash_secured_put


def test_fully_collateralized_passes():
    result = check_cash_secured_put(
        cash_collateral=20000, strike=190, contracts=1, uses_margin=False
    )
    assert result["status"] == "PASS"


def test_under_collateralized_rejects():
    result = check_cash_secured_put(
        cash_collateral=1000, strike=190, contracts=1, uses_margin=False
    )
    assert result["status"] == "REJECT"
    assert result["reason"] == "insufficient_cash_collateral"


def test_margin_rejects_regardless_of_collateral():
    result = check_cash_secured_put(
        cash_collateral=1_000_000, strike=190, contracts=1, uses_margin=True
    )
    assert result["status"] == "REJECT"
    assert result["reason"] == "margin_not_permitted"


def test_missing_strike_rejects():
    result = check_cash_secured_put(cash_collateral=20000, strike=0, contracts=1, uses_margin=False)
    assert result["status"] == "REJECT"
    assert result["reason"] == "strike_required"


def test_zero_contracts_rejects():
    result = check_cash_secured_put(
        cash_collateral=20000, strike=190, contracts=0, uses_margin=False
    )
    assert result["status"] == "REJECT"
    assert result["reason"] == "contracts_required"




# --- aggregate collateral (added 2026-09-02) ---------------------------------
# Regression cover for the PA3W2J1H6I3X finding: seven trades each logged
# "PASS: cash_secured" while the book as a whole sat at ~2x broker margin.


def test_committed_collateral_blocks_stacking_past_cash():
    """The exact production shape: plenty of raw cash, but it is already spoken for."""
    result = check_cash_secured_put(
        cash_collateral=100_273,
        committed_collateral=201_500,
        strike=307.5,
        contracts=1,
        uses_margin=False,
    )
    assert result["status"] == "REJECT"
    assert result["reason"] == "insufficient_cash_collateral"


def test_committed_collateral_still_passes_when_headroom_remains():
    result = check_cash_secured_put(
        cash_collateral=100_000,
        committed_collateral=30_000,
        strike=190,
        contracts=1,
        uses_margin=False,
    )
    assert result["status"] == "PASS"
    assert result["uncommitted_cash"] == 70_000


def test_committed_collateral_boundary_is_inclusive():
    """Exactly-fully-collateralized is still cash-secured, not a rejection."""
    result = check_cash_secured_put(
        cash_collateral=50_000,
        committed_collateral=31_000,
        strike=190,
        contracts=1,
        uses_margin=False,
    )
    assert result["status"] == "PASS"


def test_committed_collateral_defaults_to_zero():
    """Omitting the argument must behave exactly as the pre-2026-09-02 gate did."""
    result = check_cash_secured_put(
        cash_collateral=20_000, strike=190, contracts=1, uses_margin=False
    )
    assert result["status"] == "PASS"
    assert result["committed_collateral"] == 0.0


def main() -> None:
    test_fully_collateralized_passes()
    test_under_collateralized_rejects()
    test_margin_rejects_regardless_of_collateral()
    test_missing_strike_rejects()
    test_zero_contracts_rejects()
    test_committed_collateral_blocks_stacking_past_cash()
    test_committed_collateral_still_passes_when_headroom_remains()
    test_committed_collateral_boundary_is_inclusive()
    test_committed_collateral_defaults_to_zero()
    print("PASS: test_gates_structure")


if __name__ == "__main__":
    main()
