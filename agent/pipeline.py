"""Orchestration: doctor check -> account state -> shortlist -> LLM propose -> gates -> CLI
submit (or dry-run) -> log. Entry point for both manual invocation and (later) cron.
"""

from __future__ import annotations

import argparse
import uuid
from datetime import date

from agent import candidates, cli, evidence, llm
from agent.config import get_settings
from agent.gates import risk, structure
from agent.gates.shariah_enhanced import check_symbol_enhanced, load_enhanced_universe


def committed_put_collateral(positions: list[dict]) -> float:
    """Collateral already owed by open SHORT PUT positions, in dollars.

    Pure -- takes `alpaca position list` output, returns a number. Short puts carry a
    strike x 100 x contracts obligation that lives entirely outside the `cash` balance the
    broker reports (selling a put *credits* cash), so without this the structure gate compares
    each new trade against a balance that looks untouched no matter how much is already
    committed. That is how PA3W2J1H6I3X reached $201,500 of collateral on $100,273 of cash
    with seven consecutive "PASS: cash_secured" decisions logged.

    Long puts and equity legs are ignored: neither creates a cash-securing obligation.
    """
    total = 0.0
    for position in positions or []:
        if position.get("asset_class") != "us_option":
            continue
        try:
            qty = float(position.get("qty", 0))
        except (TypeError, ValueError):
            continue
        if qty >= 0:
            continue  # long options owe nothing
        try:
            parsed = candidates.parse_occ_symbol(position.get("symbol", ""))
        except ValueError:
            continue
        if parsed["type"] != "put":
            continue
        total += parsed["strike_price"] * candidates.SHARES_PER_CONTRACT * abs(qty)
    return total


def run_pipeline(*, underlying: str | None, dry_run: bool, profile: str | None = None) -> dict:
    settings = get_settings()
    active_profile = profile or settings.alpaca_profile

    doctor_result = cli.doctor(active_profile)
    if not doctor_result["ok"]:
        return evidence.log_decision(
            {"outcome": "DOCTOR_CHECK_FAILED", "detail": doctor_result["stdout"]},
            path=settings.decisions_log_path,
        )

    account = cli.account_get(active_profile)
    positions = cli.position_list(active_profile)
    committed_collateral = committed_put_collateral(positions)

    universe = load_enhanced_universe(settings.shariah_universe_path)
    symbols_dict = universe.get("symbols", universe)
    symbols = [underlying] if underlying else list(symbols_dict)
    cash_available = float(account.get("cash", 0))
    equity = float(account.get("equity", 0))

    # Deployable capital, not the raw balance. Two independent ceilings:
    #   uncommitted cash -- keeps the book-wide cash-secured invariant true (see
    #     gates/structure.py), and
    #   options buying power -- what the broker will actually let us open; sizing off `cash`
    #     alone had us proposing $27-33k trades against $23,095 of real capacity, which the
    #     broker would simply have bounced.
    options_buying_power = float(
        account.get("options_buying_power") or account.get("buying_power") or 0
    )
    deployable_cash = max(0.0, min(cash_available - committed_collateral, options_buying_power))

    shortlist = candidates.build_shortlist(
        symbols, cash_available=deployable_cash, equity=equity, profile=active_profile, cap=10
    )
    if not shortlist:
        return evidence.log_decision(
            {
                "outcome": "NO_CANDIDATES",
                "symbols_considered": symbols,
                "deployable_cash": deployable_cash,
                "committed_collateral": committed_collateral,
            },
            path=settings.decisions_log_path,
        )

    # Diversity guard: don't re-buy same underlying today (prevents 2x AAPL 14:05/14:06)
    today_decisions = evidence.todays_decisions(settings.decisions_log_path, today=date.today())
    already_traded = {d.get("underlying") for d in today_decisions if d.get("outcome") == "SUBMITTED" and d.get("underlying")}
    if already_traded:
        filtered = [c for c in shortlist if c["underlying"] not in already_traded]
        if filtered:
            shortlist = filtered

    account_snapshot = {"cash": cash_available, "equity": equity}
    proposal = llm.propose_trade(shortlist, account_snapshot, settings)

    # Deterministic fallback: if LLM is down/slow OR declines, still trade top-ranked
    # Gates remain hard safety net — LLM only proposes, never decides compliance.
    fallback_used = False
    if proposal["status"] != "OK":
        fallback_used = True
        proposal = {
            "status": "OK",
            "no_trade": False,
            "selected_index": 0,
            "rationale": f"Fallback: LLM {proposal['status']} — selected top-ranked candidate deterministically.",
        }
    elif proposal.get("no_trade"):
        fallback_used = True
        proposal = {
            "status": "OK",
            "no_trade": False,
            "selected_index": 0,
            "rationale": f"Fallback: LLM declined ({proposal.get('rationale','')}) — selected top-ranked deterministically.",
        }

    selected = shortlist[proposal["selected_index"]]

    orders_today = sum(1 for d in today_decisions if d.get("outcome") == "SUBMITTED")
    # Real daily P&L vs 100000 start (web_app.py:79 ACC_START) - was hardcoded 0 before
    daily_pnl_pct = ((equity - 100000.0) / 100000.0 * 100) if equity else 0

    gate_results = {
        "shariah": check_symbol_enhanced(selected["underlying"], universe),
        "structure": structure.check_cash_secured_put(
            cash_collateral=cash_available,
            committed_collateral=committed_collateral,
            strike=selected["strike"],
            contracts=selected["contracts"],
            uses_margin=False,
        ),
        "risk": risk.check_risk_limits(
            orders_today=orders_today,
            max_orders_per_day=settings.max_orders_per_day,
            position_value=selected["cash_required"],
            account_equity=account_snapshot["equity"] or 1,
            max_position_pct=settings.max_position_pct,
            daily_pnl=daily_pnl_pct,
            max_daily_loss_pct=settings.max_daily_loss_pct,
        ),
    }

    record = {
        "underlying": selected["underlying"],
        "candidates_considered": len(shortlist),
        "llm_rationale": proposal.get("rationale", ""),
        "selected": selected,
        "gate_results": gate_results,
        "llm_fallback": fallback_used,
        "committed_collateral": committed_collateral,
        "deployable_cash": deployable_cash,
    }

    if not all(g["status"] == "PASS" for g in gate_results.values()):
        record["outcome"] = "REJECTED"
        return evidence.log_decision(record, path=settings.decisions_log_path)

    client_order_id = f"amanah-{uuid.uuid4().hex[:12]}"
    if dry_run:
        record["outcome"] = "WOULD_SUBMIT"
        record["client_order_id"] = client_order_id
    else:
        order = cli.order_submit(
            symbol=selected["symbol"],
            side="sell",
            qty=selected["contracts"],
            order_type="limit",
            limit_price=selected["premium_per_share"],
            time_in_force="day",
            client_order_id=client_order_id,
            profile=active_profile,
        )
        record["outcome"] = "SUBMITTED"
        record["order_id"] = order.get("id")
        record["client_order_id"] = client_order_id

    return evidence.log_decision(record, path=settings.decisions_log_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one pipeline cycle.")
    parser.add_argument("--underlying", default=None, help="Restrict to one symbol (debugging)")
    parser.add_argument("--dry-run", action="store_true", help="Log WOULD_SUBMIT, never submit")
    parser.add_argument("--profile", default=None, help="Override ALPACA_PROFILE")
    args = parser.parse_args()

    result = run_pipeline(underlying=args.underlying, dry_run=args.dry_run, profile=args.profile)
    print(result)


if __name__ == "__main__":
    main()
