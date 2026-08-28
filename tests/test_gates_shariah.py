from agent.gates.shariah import check_symbol


UNIVERSE = {"AAPL": {"rationale": "test", "added": "2026-08-29"}}


def test_listed_symbol_passes():
    result = check_symbol("AAPL", UNIVERSE)
    assert result["status"] == "PASS"


def test_unlisted_symbol_fails_closed():
    result = check_symbol("TSLA", UNIVERSE)
    assert result["status"] == "REJECT"
    assert result["reason"] == "not_on_curated_list"


def test_case_and_whitespace_normalized():
    result = check_symbol("  aapl  ", UNIVERSE)
    assert result["status"] == "PASS"


def main() -> None:
    test_listed_symbol_passes()
    test_unlisted_symbol_fails_closed()
    test_case_and_whitespace_normalized()
    print("PASS: test_gates_shariah")


if __name__ == "__main__":
    main()
