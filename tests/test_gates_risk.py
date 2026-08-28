from agent.gates.risk import check_risk_limits


BASE = dict(
    orders_today=0,
    max_orders_per_day=3,
    position_value=1000,
    account_equity=100000,
    max_position_pct=5,
    daily_pnl=0,
    max_daily_loss_pct=3,
)


def test_within_all_limits_passes():
    result = check_risk_limits(**BASE)
    assert result["status"] == "PASS"


def test_orders_today_cap_trips():
    result = check_risk_limits(**{**BASE, "orders_today": 3})
    assert result["status"] == "REJECT"
    assert result["reason"] == "orders_today_cap"


def test_position_size_cap_trips():
    result = check_risk_limits(**{**BASE, "position_value": 6000})
    assert result["status"] == "REJECT"
    assert result["reason"] == "position_size_cap"


def test_daily_loss_cap_trips():
    result = check_risk_limits(**{**BASE, "daily_pnl": -4000})
    assert result["status"] == "REJECT"
    assert result["reason"] == "daily_loss_cap"


def main() -> None:
    test_within_all_limits_passes()
    test_orders_today_cap_trips()
    test_position_size_cap_trips()
    test_daily_loss_cap_trips()
    print("PASS: test_gates_risk")


if __name__ == "__main__":
    main()
