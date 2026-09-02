"""The stress harness's own claims: deterministic, adversarial, and not vacuous.

Added 2026-09-02. `docs/backtest/gate-stress-report.md` is submission evidence, so the two
properties that make it evidence rather than an anecdote need to hold under test: it must be
reproducible byte-for-byte, and it must not be a chain that trivially refuses everything.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from gate_stress import SCENARIOS, build_report  # noqa: E402


def test_report_is_byte_identical_across_runs():
    """No clock, no randomness, no network — the point of the artifact."""
    assert build_report()[0] == build_report()[0]


def test_every_scenario_is_exercised():
    report, refused, allowed = build_report()
    assert refused + allowed == len(SCENARIOS)
    for sc in SCENARIOS:
        assert sc.name in report


def test_the_chain_refuses_the_profitable_unlisted_trade():
    """The single scenario the whole project exists to demonstrate."""
    status, situation, _ = SCENARIOS[0].run()
    assert status == "FAIL"
    assert "richest premium" in situation


def test_harness_is_not_vacuous():
    """A chain that refuses everything proves nothing. Normal conditions must still PASS."""
    _, _, allowed = build_report()
    assert allowed >= 1
    status, _, reason = SCENARIOS[-1].run()
    assert status == "PASS"
    assert "all four gates PASS" in reason


def test_harness_is_predominantly_adversarial():
    _, refused, _ = build_report()
    assert refused >= 10


def test_all_four_gates_appear_in_refusals():
    """Each gate must be shown actually refusing something, not just present in the chain."""
    report = build_report()[0]
    for reason in (
        "Not in curated universe",                      # shariah
        "insufficient_cash_collateral",                 # structure
        "negative_cash_balance_is_an_interest_bearing_loan",  # riba
        "position_size_cap",                            # risk
    ):
        assert reason in report, reason


def main() -> None:
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
    print("PASS: test_gate_stress")


if __name__ == "__main__":
    main()
