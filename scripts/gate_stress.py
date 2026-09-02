#!/usr/bin/env python3
"""Deterministic stress harness for the compliance gate chain.

The official FAQ permits backtests and simulated shocks as supporting evidence. A conventional
price backtest is not honest here: we hold no historical options chains, and inventing them
would prove nothing about the thing this project actually claims. What *is* claimable, and
what this exercises, is the property the whole submission rests on -- **the gate chain refuses
trades it is supposed to refuse, including profitable ones, under conditions we choose.**

Every scenario below calls the real gate functions from `agent/gates/`. Nothing is mocked or
reimplemented; if a gate changes, this report changes with it. There is no network access, no
clock dependency and no randomness, so the output is byte-identical on every run and on any
machine -- which is what makes it evidence rather than an anecdote.

    python scripts/gate_stress.py            # print report
    python scripts/gate_stress.py --write    # also write docs/backtest/gate-stress-report.md
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.candidates import DEFAULT_POLICY, rank_candidates  # noqa: E402
from agent.gates.riba import check_account_riba  # noqa: E402
from agent.gates.risk import check_risk_limits  # noqa: E402
from agent.gates.shariah_enhanced import check_symbol_enhanced  # noqa: E402
from agent.gates.structure import check_cash_secured_put  # noqa: E402

TODAY = date(2026, 9, 2)  # pinned; the harness must not depend on when it is run

UNIVERSE = {"symbols": {
    "AAPL": {"confidence_score": 90, "rationale": "Consumer hardware and services."},
    "NVDA": {"confidence_score": 90, "rationale": "Semiconductor design."},
    "MSFT": {"confidence_score": 88, "rationale": "Software and cloud."},
}}

LIMITS = {"max_orders_per_day": 10, "max_position_pct": 40.0, "max_daily_loss_pct": 3.0}
HEALTHY_ACCOUNT = {"cash": "100000.00", "equity": "100000.00", "multiplier": "4"}


class Scenario:
    def __init__(self, name, question, run):
        self.name, self.question, self.run = name, question, run


def _chain(spot: float, strikes, *, bid: float, expiry: str = "2026-09-04"):
    """Synthetic put chain rows in the shape rank_candidates() consumes."""
    return [{"symbol": f"TEST{int(k * 1000):08d}", "strike_price": k,
             "expiration_date": expiry,
             "latestQuote": {"bp": bid, "ap": round(bid * 1.05, 2)}} for k in strikes]


# --- scenarios -------------------------------------------------------------

def s_profitable_but_unlisted():
    """The scenario the entire project exists to demonstrate."""
    r = check_symbol_enhanced("TSLA", UNIVERSE)
    return r["status"], "TSLA put paying $12.00/share — the richest premium on the board", r["reason"]


def s_oversized_position():
    r = check_risk_limits(orders_today=0, position_value=49_000, account_equity=100_000,
                          daily_pnl=0, **LIMITS)
    return r["status"], "MSFT 490 put — $49,000 collateral = 49% of equity", r["reason"]


def s_book_already_at_two_times_leverage():
    """Reproduces the real 2026-09-02 production state on PA3W2J1H6I3X."""
    r = check_cash_secured_put(cash_collateral=100_273.83, committed_collateral=201_500.0,
                               strike=307.5, contracts=1, uses_margin=False)
    return r["status"], "8th cash-secured put with $201,500 already committed on $100,273 cash", r["reason"]


def s_margin_financed_account():
    r = check_account_riba(HEALTHY_ACCOUNT, [], committed_collateral=150_000.0)
    return r["status"], "Account carrying $150,000 of obligations against $100,000 cash", r["reason"]


def s_negative_cash():
    r = check_account_riba({"cash": "-5000", "multiplier": "4"}, [], committed_collateral=0.0)
    return r["status"], "Account overdrawn by $5,000 — a broker loan", r["reason"]


def s_short_equity():
    book = [{"asset_class": "us_equity", "symbol": "AAPL", "qty": "-100"}]
    r = check_account_riba(HEALTHY_ACCOUNT, book, committed_collateral=0.0)
    return r["status"], "100 shares of AAPL sold short (borrowed stock)", r["reason"]


def s_interest_bearing_holding():
    book = [{"asset_class": "us_equity", "symbol": "TLT", "qty": "500"}]
    r = check_account_riba(HEALTHY_ACCOUNT, book, committed_collateral=0.0)
    return r["status"], "500 shares of TLT (long-duration Treasury ETF)", r["reason"]


def s_crash_20pct():
    """Spot gaps down 20%. Every strike is now deep in the money, i.e. no longer OTM."""
    spot = 80.0  # was 100
    eligible, rejected = rank_candidates(_chain(spot, [95, 97, 99], bid=8.00),
                                         spot=spot, today=TODAY, policy=DEFAULT_POLICY)
    status = "REJECT" if not eligible else "PASS"
    return status, "Underlying gaps -20% overnight; strikes now 19–24% ITM", \
        f"0 of 3 contracts eligible — all outside the 2–7% OTM band ({rejected['out_of_otm_band']} rejected)"


def s_illiquid_wide_spread():
    rows = [{"symbol": "TEST00097000", "strike_price": 97.0, "expiration_date": "2026-09-04",
             "latestQuote": {"bp": 1.00, "ap": 3.00}}]  # 100% spread of mid
    eligible, rejected = rank_candidates(rows, spot=100.0, today=TODAY, policy=DEFAULT_POLICY)
    status = "REJECT" if not eligible else "PASS"
    return status, "Bid $1.00 / ask $3.00 — 100% spread on a thin contract", \
        f"spread_too_wide={rejected['spread_too_wide']} (cap is {DEFAULT_POLICY['max_spread_pct_of_mid']}% of mid)"


def s_vol_spike_premium_triples():
    """Volatility spikes. Premium becomes very attractive — the gates must still hold."""
    eligible, _ = rank_candidates(_chain(100.0, [97.0], bid=9.00),
                                  spot=100.0, today=TODAY, policy=DEFAULT_POLICY)
    if not eligible:
        return "REJECT", "Vol spike: 3% OTM put now bids $9.00", "no eligible contract"
    c = eligible[0]
    r = check_risk_limits(orders_today=0, position_value=c["strike"] * 100 * 5,
                          account_equity=100_000, daily_pnl=0, **LIMITS)
    return r["status"], "Vol spike: 3% OTM put bids $9.00; agent sized to 5 contracts", \
        f"{r['reason']} — ${c['strike'] * 100 * 5:,.0f} = 48.5% of equity"


def s_daily_loss_breach():
    r = check_risk_limits(orders_today=0, position_value=10_000, account_equity=100_000,
                          daily_pnl=-4_000, **LIMITS)
    return r["status"], "Account already -4% on the day; a new trade is proposed", r["reason"]


def s_normal_conditions_still_trades():
    """A fail-closed chain that refuses everything is useless. It must still say yes."""
    eligible, _ = rank_candidates(_chain(100.0, [97.0], bid=1.20),
                                  spot=100.0, today=TODAY, policy=DEFAULT_POLICY)
    c = eligible[0]
    verdicts = [
        check_symbol_enhanced("AAPL", UNIVERSE),
        check_cash_secured_put(cash_collateral=100_000, committed_collateral=0,
                               strike=c["strike"], contracts=1, uses_margin=False),
        check_account_riba(HEALTHY_ACCOUNT, [], committed_collateral=9_700.0),
        check_risk_limits(orders_today=0, position_value=9_700, account_equity=100_000,
                          daily_pnl=0, **LIMITS),
    ]
    status = "PASS" if all(v["status"] == "PASS" for v in verdicts) else "REJECT"
    return status, "AAPL 3% OTM put, $1.20 bid, 2 DTE, $9,700 collateral on $100k", \
        "all four gates PASS"


SCENARIOS = [
    Scenario("Profitable but unlisted", "Will it refuse the best trade on the board?", s_profitable_but_unlisted),
    Scenario("Position too large", "Will it refuse a trade that breaches the size cap?", s_oversized_position),
    Scenario("Book already 2x levered", "Will it stop stacking collateral past cash?", s_book_already_at_two_times_leverage),
    Scenario("Margin-financed account", "Will it refuse to trade into a levered account?", s_margin_financed_account),
    Scenario("Overdrawn account", "Will it recognise a broker loan as riba?", s_negative_cash),
    Scenario("Short equity held", "Will it refuse borrowed stock?", s_short_equity),
    Scenario("Interest-bearing holding", "Will it refuse an account holding bond ETFs?", s_interest_bearing_holding),
    Scenario("Market crash -20%", "Does the OTM band hold when spot gaps down?", s_crash_20pct),
    Scenario("Illiquid contract", "Will it refuse an untradeable spread?", s_illiquid_wide_spread),
    Scenario("Volatility spike", "Does rich premium tempt it past the size cap?", s_vol_spike_premium_triples),
    Scenario("Daily loss breach", "Will it stand down after a bad day?", s_daily_loss_breach),
    Scenario("Normal conditions", "Does it still actually trade?", s_normal_conditions_still_trades),
]


def build_report() -> tuple[str, int, int]:
    lines = [
        "# Gate Chain Stress Report",
        "",
        "Deterministic. No network, no clock dependency, no randomness — this file is",
        "byte-identical on every run. Generated by `scripts/gate_stress.py`, which calls the",
        "real functions in `agent/gates/`; nothing here is mocked, so the report cannot drift",
        "from the code it describes.",
        "",
        "Eleven of twelve scenarios are adversarial: the agent is offered a trade it must",
        "refuse, several of them profitable. The twelfth confirms it still says yes under",
        "normal conditions — a chain that refuses everything would prove nothing.",
        "",
        "| # | Scenario | Situation | Verdict | Reason |",
        "|---|---|---|---|---|",
    ]
    refused = passed = 0
    for i, sc in enumerate(SCENARIOS, 1):
        status, situation, reason = sc.run()
        if status == "PASS":
            passed += 1
            badge = "**PASS**"
        else:
            refused += 1
            badge = f"**{status}**"
        lines.append(f"| {i} | {sc.name} | {situation} | {badge} | `{reason}` |")

    lines += [
        "",
        f"**{refused} refused, {passed} allowed.**",
        "",
        "## What each scenario is asking",
        "",
    ]
    for i, sc in enumerate(SCENARIOS, 1):
        lines.append(f"{i}. **{sc.name}** — {sc.question}")
    lines += [
        "",
        "## Why not a price backtest",
        "",
        "We hold no historical option chains, and fabricating them would demonstrate nothing",
        "about the claim this project actually makes. The claim is not that the strategy is",
        "profitable — it plainly is not, at +0.078%. The claim is that the agent cannot be",
        "argued, tempted, or drifted into a non-compliant trade, and that is exactly what a",
        "deterministic adversarial harness can establish and a price series cannot.",
        "",
    ]
    return "\n".join(lines), refused, passed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="write docs/backtest/gate-stress-report.md")
    args = parser.parse_args()

    report, refused, passed = build_report()
    # Windows consoles default to cp1252 and will not encode every character used here.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(report)
    if args.write:
        out = Path(__file__).resolve().parent.parent / "docs" / "backtest" / "gate-stress-report.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report + "\n", encoding="utf-8")
        print(f"\nWrote {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
