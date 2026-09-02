"""The Shariah gate that production actually runs.

Added 2026-09-02. `pipeline.py:14` imports `shariah_enhanced.check_symbol_enhanced`, but the
only Shariah tests in the suite covered `shariah.py` -- a 24-line module no production code
imports. The live 153-line gate had zero coverage, so "19 tests prove the compliance gates"
did not cover the gate that decides real trades. These pin its actual behaviour.
"""

from agent.gates.shariah_enhanced import check_symbol_enhanced

ENHANCED = {"symbols": {
    "AAPL": {"confidence_score": 90, "rationale": "hardware", "sector": "Technology",
             "financial_ratios": {"debt_to_assets": 0.18}},
    "EDGE": {"confidence_score": 85, "rationale": "exactly at the high threshold"},
    "MOD":  {"confidence_score": 70, "rationale": "exactly at the moderate threshold"},
    "REV":  {"confidence_score": 60, "rationale": "needs human review"},
    "BAD":  {"confidence_score": 20, "rationale": "fails the screen"},
}}

BASIC = {"symbols": {"AAPL": {"rationale": "on the curated list", "added": "2026-08-29"}}}


# --- the guarantee the whole pitch rests on --------------------------------
def test_unlisted_symbol_fails_closed():
    r = check_symbol_enhanced("TSLA", ENHANCED)
    assert r["status"] == "FAIL"
    assert r["confidence_score"] == 0
    assert r["recommendation"] == "REJECT"


def test_empty_universe_fails_closed():
    assert check_symbol_enhanced("AAPL", {"symbols": {}})["status"] == "FAIL"


def test_unlisted_is_rejected_even_with_a_populated_universe():
    """No fuzzy matching, no fallback to 'looks like a big tech name'."""
    assert check_symbol_enhanced("AAPL.US", ENHANCED)["status"] == "FAIL"
    assert check_symbol_enhanced("aapl", ENHANCED)["status"] == "FAIL"


# --- confidence banding ----------------------------------------------------
def test_high_confidence_passes():
    r = check_symbol_enhanced("AAPL", ENHANCED)
    assert r["status"] == "PASS"
    assert r["confidence_score"] == 90
    assert r["methodology"] == "MSCI_ISLAMIC"
    assert r["financial_ratios"] == {"debt_to_assets": 0.18}


def test_85_is_the_high_confidence_boundary():
    assert check_symbol_enhanced("EDGE", ENHANCED)["reason"].startswith("HIGH CONFIDENCE")


def test_70_is_the_lowest_passing_score():
    r = check_symbol_enhanced("MOD", ENHANCED)
    assert r["status"] == "PASS"
    assert r["reason"].startswith("MODERATE CONFIDENCE")


def test_review_band_does_not_pass():
    """50-69 is REVIEW. pipeline.py:111 gates on status == 'PASS', so this blocks."""
    r = check_symbol_enhanced("REV", ENHANCED)
    assert r["status"] == "REVIEW"
    assert r["status"] != "PASS"
    assert r["recommendation"] == "REJECT"


def test_low_confidence_fails():
    r = check_symbol_enhanced("BAD", ENHANCED)
    assert r["status"] == "FAIL"
    assert r["recommendation"] == "REJECT"


# --- the un-scored universe still works ------------------------------------
def test_basic_format_falls_back_to_curated_list():
    r = check_symbol_enhanced("AAPL", BASIC)
    assert r["status"] == "PASS"
    assert r["methodology"] == "CURATED_LIST"
    assert r["confidence_score"] == 80


def test_basic_format_still_fails_closed_on_unlisted():
    assert check_symbol_enhanced("TSLA", BASIC)["status"] == "FAIL"


def main() -> None:
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
    print("PASS: test_gates_shariah_enhanced")


if __name__ == "__main__":
    main()
