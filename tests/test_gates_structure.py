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


def main() -> None:
    test_fully_collateralized_passes()
    test_under_collateralized_rejects()
    test_margin_rejects_regardless_of_collateral()
    test_missing_strike_rejects()
    test_zero_contracts_rejects()
    print("PASS: test_gates_structure")


if __name__ == "__main__":
    main()
