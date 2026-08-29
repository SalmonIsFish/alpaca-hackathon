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
    cli.position_list(active_profile)  # fetched for future position-aware sizing; not yet used

    universe = load_enhanced_universe(settings.shariah_universe_path)
    symbols_dict = universe.get("symbols", universe)
    symbols = [underlying] if underlying else list(symbols_dict)
    cash_available = float(account.get("cash", 0))
    equity = float(account.get("equity", 0))

    shortlist = candidates.build_shortlist(
        symbols, cash_available=cash_available, equity=equity, profile=active_profile, cap=5
    )
    if not shortlist:
        return evidence.log_decision(
            {"outcome": "NO_CANDIDATES", "symbols_considered": symbols},
            path=settings.decisions_log_path,
        )

    account_snapshot = {"cash": cash_available, "equity": equity}
    proposal = llm.propose_trade(shortlist, account_snapshot, settings)

    # Deterministic fallback: if LLM is down/slow, still trade the top-ranked
    # candidate. The gates remain the hard safety net — LLM only proposes.
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
        return evidence.log_decision(
            {
                "outcome": "NO_TRADE_LLM_DECLINED",
                "candidates_considered": len(shortlist),
                "llm_rationale": proposal.get("rationale", ""),
            },
            path=settings.decisions_log_path,
        )

    selected = shortlist[proposal["selected_index"]]

    today_decisions = evidence.todays_decisions(settings.decisions_log_path, today=date.today())
    orders_today = sum(1 for d in today_decisions if d.get("outcome") == "SUBMITTED")

    gate_results = {
        "shariah": check_symbol_enhanced(selected["underlying"], universe),
        "structure": structure.check_cash_secured_put(
            cash_collateral=cash_available,
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
            daily_pnl=0,  # first-cut: no intraday equity delta tracking yet
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
