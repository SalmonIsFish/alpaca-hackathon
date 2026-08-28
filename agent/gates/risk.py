"""Deterministic risk-limit gate: three independent hard caps.

Pure function -- callers (pipeline.py) are responsible for computing orders_today and
daily_pnl from the evidence log before calling this. Paper money means no real financial
risk, but these caps stop a bug from spamming the account or doing something embarrassing
mid-demo.
"""

from __future__ import annotations


def check_risk_limits(
    *,
    orders_today: int,
    max_orders_per_day: int,
    position_value: float,
    account_equity: float,
    max_position_pct: float,
    daily_pnl: float,
    max_daily_loss_pct: float,
) -> dict:
    if orders_today >= max_orders_per_day:
        return {
            "status": "REJECT",
            "reason": "orders_today_cap",
            "orders_today": orders_today,
            "max_orders_per_day": max_orders_per_day,
        }

    if account_equity > 0:
        position_pct = (position_value / account_equity) * 100
        if position_pct > max_position_pct:
            return {
                "status": "REJECT",
                "reason": "position_size_cap",
                "position_pct": position_pct,
                "max_position_pct": max_position_pct,
            }

    if account_equity > 0:
        daily_loss_pct = (-daily_pnl / account_equity) * 100
        if daily_loss_pct > max_daily_loss_pct:
            return {
                "status": "REJECT",
                "reason": "daily_loss_cap",
                "daily_loss_pct": daily_loss_pct,
                "max_daily_loss_pct": max_daily_loss_pct,
            }

    return {"status": "PASS", "reason": "within_limits"}
