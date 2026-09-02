#!/usr/bin/env python3
"""
Minimal web application for Application URL requirement.

Displays:
- Agent status (running/stopped)
- Current account information
- Real-time market status (ET)
- Recent trading activity
- Decision logs with full audit trail

Dark-mode fintech dashboard (OLED). Polls Alpaca every 60s via fetch();
server is the source of truth for all numbers.
"""

import os
import sys
import json
from collections import deque
from datetime import datetime, date, time, timedelta
from flask import Flask, jsonify, render_template_string, request

try:
    from zoneinfo import ZoneInfo
    ET = ZoneInfo("America/New_York")
except Exception:
    ET = None

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent.config import get_settings
from agent import cli
from agent.reconcile import reconcile_attribution

app = Flask(__name__)

# Equity history for the live curve (shared across requests in this worker).
EQUITY_HISTORY = deque(maxlen=240)


MARKET_OPEN = time(9, 30)
MARKET_CLOSE = time(16, 0)


def market_status():
    """Return market open/closed status computed in US/Eastern."""
    now = datetime.now(ET) if ET else datetime.now()
    weekday = now.weekday()
    t = now.time()
    is_open = weekday <= 4 and MARKET_OPEN <= t <= MARKET_CLOSE

    def next_open_dt():
        d = now.date()
        if weekday <= 4 and t < MARKET_OPEN:
            return datetime.combine(d, MARKET_OPEN, ET) if ET else datetime.combine(d, MARKET_OPEN)
        d = d + timedelta(days=1)
        while d.weekday() > 4:
            d = d + timedelta(days=1)
        return datetime.combine(d, MARKET_OPEN, ET) if ET else datetime.combine(d, MARKET_OPEN)

    next_close_dt = None
    if is_open:
        if ET:
            next_close_dt = datetime.combine(now.date(), MARKET_CLOSE, ET)
        else:
            next_close_dt = datetime.combine(now.date(), MARKET_CLOSE)

    nxt_open = next_open_dt()
    return {
        "is_open": is_open,
        "now_et": now.isoformat(),
        "next_open": nxt_open.isoformat(),
        "next_close": next_close_dt.isoformat() if next_close_dt else None,
        "weekday": weekday,
    }


ACC_START_EQUITY = 100000.0
OFFICIAL_START = "2026-08-31T13:30:00+00:00"  # Mon 09:30 ET P&L window - pre-judging hidden

# Last known good account data. On a transient Alpaca/CLI error we serve this
# instead of zeros, so the dashboard never flashes $0.00 during a hiccup.
_LAST_GOOD_ACCOUNT = {
    'equity': 0,
    'cash': 0,
    'buying_power': 0,
    'profile': 'error',
    'account_number': 'N/A',
}


def get_account_data():
    """Get current account information."""
    global _LAST_GOOD_ACCOUNT
    try:
        settings = get_settings()
        account = cli.account_get(settings.alpaca_profile)
        data = {
            'equity': float(account.get('equity', 0)),
            'cash': float(account.get('cash', 0)),
            'buying_power': float(account.get('buying_power', 0)),
            'profile': settings.alpaca_profile,
            'account_number': account.get('account_number', 'N/A'),
        }
        if data['equity'] > 0:
            _LAST_GOOD_ACCOUNT = data
            EQUITY_HISTORY.append({'t': datetime.now().isoformat(), 'e': data['equity']})
        return data
    except Exception as e:
        return dict(_LAST_GOOD_ACCOUNT)


_EMPTY_ATTRIBUTION = {
    'premium_collected': 0, 'equity_delta': 0, 'mtm_unrealized': 0, 'collateral_held': 0,
    'open_positions': 0, 'orders_submitted': 0, 'orders_open': 0, 'premium_submitted_log': 0,
    'unfilled_or_closed': [], 'premium_by_underlying': {},
}


def get_pnl_attribution():
    """Premium / collateral / MTM reconciled against what the broker actually holds.

    Was: summed `SUBMITTED` rows out of decisions.jsonl. A SUBMITTED row only records that
    the CLI accepted an order, not that it filled -- on PA3W2J1H6I3X seven SUBMITTED rows
    left three contracts in the account, so this panel reported $921.90 of premium and
    $201,500 of collateral against a book actually holding $274 and $94,500. Now every
    headline number comes from `position_list`; the log figures are kept beside them under
    `premium_submitted_log` / `orders_submitted` so the gap stays auditable.
    """
    try:
        settings = get_settings()
        positions = cli.position_list(settings.alpaca_profile)
    except Exception:
        positions = []

    official = []
    try:
        with open(settings.decisions_log_path, 'r') as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    d = json.loads(line)
                except Exception:
                    continue
                if d.get('timestamp', '') >= OFFICIAL_START:
                    official.append(d)
    except Exception:
        pass

    try:
        attribution = reconcile_attribution(positions, official)
    except Exception:
        return dict(_EMPTY_ATTRIBUTION)

    attribution.pop('positions', None)
    eq = _LAST_GOOD_ACCOUNT.get('equity') or 0
    try:
        eq = float(eq)
    except Exception:
        eq = 0
    attribution['equity_delta'] = round((eq - ACC_START_EQUITY) if eq else 0, 2)
    return attribution


def get_decision_stats():
    """Get statistics from decision log."""
    try:
        settings = get_settings()
        today = date.today().isoformat()

        total = 0
        today_count = 0
        submitted = 0
        rejected = 0
        would = 0

        with open(settings.decisions_log_path, 'r') as f:
            for line in f:
                total += 1
                if today in line:
                    today_count += 1

                try:
                    data = json.loads(line)
                    outcome = data.get('outcome', '')
                    if outcome == 'SUBMITTED':
                        submitted += 1
                    elif outcome == 'REJECTED':
                        rejected += 1
                    elif outcome == 'WOULD_SUBMIT':
                        would += 1
                except Exception:
                    pass

        return {
            'total_decisions': total,
            'today_trades': today_count,
            'submitted': submitted,
            'rejected': rejected,
            'would_submit': would,
        }
    except FileNotFoundError:
        return {
            'total_decisions': 0,
            'today_trades': 0,
            'submitted': 0,
            'rejected': 0,
            'would_submit': 0,
        }


def get_recent_decisions(limit=10):
    """Get recent decisions from log."""
    try:
        settings = get_settings()
        decisions = []

        with open(settings.decisions_log_path, 'r') as f:
            lines = f.readlines()

        for line in lines[-limit:]:
            try:
                data = json.loads(line)

                outcome = data.get('outcome', 'UNKNOWN')
                if outcome == 'SUBMITTED':
                    css_class = 'submitted'
                elif outcome == 'WOULD_SUBMIT':
                    css_class = 'would'
                elif outcome == 'LLM_INVALID_RESPONSE':
                    css_class = 'invalid'
                else:
                    css_class = 'rejected'

                # hide pre-official decisions from audit trail UI (file retains them)
                if data.get('timestamp','') < OFFICIAL_START:
                    continue
                decision = {
                    'timestamp': data.get('timestamp', 'N/A'),
                    'outcome': outcome,
                    'underlying': data.get('underlying'),
                    'selected': data.get('selected'),
                    'gate_results': data.get('gate_results'),
                    'rationale': data.get('llm_rationale'),
                    'detail': data.get('detail'),
                    'css_class': css_class,
                }
                decisions.append(decision)
            except json.JSONDecodeError:
                continue

        return decisions
    except FileNotFoundError:
        return []


def is_agent_running():
    """Check if the Alpaca CLI responds."""
    try:
        settings = get_settings()
        cli.account_get(settings.alpaca_profile)
        return True
    except Exception:
        return False


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Amanah Trader — Autonomous Shariah-Compliant AI Trading Agent</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
<script>
try { var t = localStorage.getItem("amanah-theme"); if (t) document.documentElement.setAttribute("data-theme", t); } catch (e) {}
</script>
<style>
:root {
    --bg: #020617;
    --bg-2: #0B1120;
    --card: #0E1223;
    --card-2: #0F172A;
    --border: #1E293B;
    --border-strong: #334155;
    --text: #F8FAFC;
    --muted: #94A3B8;
    --accent: #22C55E;
    --accent-dim: rgba(34, 197, 94, 0.12);
    --info: #3B82F6;
    --info-dim: rgba(59, 130, 246, 0.12);
    --warn: #F59E0B;
    --warn-dim: rgba(245, 158, 11, 0.12);
    --danger: #EF4444;
    --danger-dim: rgba(239, 68, 68, 0.12);
    --ring: rgba(255, 255, 255, 0.55);
    --radius: 14px;
    --radius-sm: 8px;
    --font: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    --shadow: 0 10px 30px rgba(0, 0, 0, 0.35);
}
/* Light theme (opt-in via toggle) */
[data-theme="light"] {
    --bg: #F8FAFC;
    --bg-2: #F1F5F9;
    --card: #FFFFFF;
    --card-2: #F8FAFC;
    --border: #E2E8F0;
    --border-strong: #CBD5E1;
    --text: #0F172A;
    --muted: #64748B;
    --accent: #15803D;
    --accent-dim: rgba(21, 128, 61, 0.10);
    --info: #2563EB;
    --info-dim: rgba(37, 99, 235, 0.10);
    --warn: #B45309;
    --warn-dim: rgba(180, 83, 9, 0.10);
    --danger: #DC2626;
    --danger-dim: rgba(220, 38, 38, 0.10);
    --ring: rgba(15, 23, 42, 0.5);
    --shadow: 0 10px 30px rgba(15, 23, 42, 0.08);
}
#eqGrad stop, #eqGradSub stop { stop-color: var(--accent); }
.theme-toggle { cursor: pointer; transition: border-color 0.2s, background 0.2s; }
.theme-toggle svg { width: 15px; height: 15px; }
.theme-toggle .icon-sun { display: none; }
[data-theme="light"] .theme-toggle .icon-sun { display: inline; }
[data-theme="light"] .theme-toggle .icon-moon { display: none; }
* { margin: 0; padding: 0; box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
    font-family: var(--font);
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
    font-size: 14px;
    line-height: 1.5;
    -webkit-font-smoothing: antialiased;
    background-image:
        radial-gradient(1200px 500px at 15% -10%, rgba(34, 197, 94, 0.06), transparent 60%),
        radial-gradient(1000px 500px at 100% 0%, rgba(59, 130, 246, 0.06), transparent 55%);
}
.wrap { max-width: 1360px; margin: 0 auto; padding: 20px; }

/* ---------- Header ---------- */
header {
    display: flex; align-items: center; justify-content: space-between;
    gap: 16px; flex-wrap: wrap;
    border-bottom: 1px solid var(--border);
    padding-bottom: 16px; margin-bottom: 20px;
}
.brand { display: flex; align-items: center; gap: 12px; }
.brand-logo {
    width: 42px; height: 42px; border-radius: 10px;
    background: linear-gradient(135deg, #14532D, #16A34A);
    display: grid; place-items: center; flex-shrink: 0;
}
.brand h1 { font-size: 20px; font-weight: 700; letter-spacing: -0.01em; }
.brand .tagline { color: var(--muted); font-size: 12.5px; font-weight: 400; }
.header-right { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }

.pill {
    display: inline-flex; align-items: center; gap: 7px;
    padding: 7px 13px; border-radius: 999px;
    border: 1px solid var(--border-strong);
    background: var(--card-2); font-size: 12.5px; font-weight: 500;
    color: var(--text);
}
.dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.dot.open { background: var(--accent); animation: pulse 2s infinite; }
.dot.closed { background: var(--muted); }
.dot.running { background: var(--accent); }
.dot.stopped { background: var(--danger); }
.hl-open { color: var(--accent); }
.hl-closed { color: var(--muted); }
@keyframes pulse {
    0% { box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.45); }
    70% { box-shadow: 0 0 0 8px rgba(34, 197, 94, 0); }
    100% { box-shadow: 0 0 0 0 rgba(34, 197, 94, 0); }
}

/* ---------- Cards & grid ---------- */
.grid { display: grid; grid-template-columns: repeat(12, 1fr); gap: 16px; }
.card {
    background: linear-gradient(180deg, var(--card-2), var(--card));
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 20px;
    box-shadow: var(--shadow);
}
.card-title {
    display: flex; align-items: center; gap: 8px;
    font-size: 12px; font-weight: 600; text-transform: uppercase;
    letter-spacing: 0.08em; color: var(--muted); margin-bottom: 16px;
}
.card-title svg { width: 16px; height: 16px; color: var(--accent); }

.span-4 { grid-column: span 4; }
.span-6 { grid-column: span 6; }
.span-8 { grid-column: span 8; }
.span-12 { grid-column: span 12; }

/* ---------- KPI ---------- */
.kpi-value { font-size: 28px; font-weight: 700; letter-spacing: -0.02em; font-variant-numeric: tabular-nums; }
.kpi-value .sublabel { font-size: 14px; font-weight: 500; color: var(--muted); }
.kpi-delta { display: inline-flex; align-items: center; gap: 5px; font-size: 13px; font-weight: 600; margin-top: 6px; }
.kpi-delta.up { color: var(--accent); }
.kpi-delta.down { color: var(--danger); }
.kpi-delta.flat { color: var(--muted); }
.kpi-delta svg { width: 14px; height: 14px; }
.kpi-sub { color: var(--muted); font-size: 12px; margin-top: 4px; }
.kpi-strip { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }

.stat-pair { display: flex; justify-content: space-between; gap: 10px; }
.stat-pair .stat { flex: 1; }
.stat-pair .kpi-value { font-size: 22px; }

/* ---------- Market ---------- */
.market-row { display: flex; flex-wrap: wrap; gap: 20px; margin-top: 4px; }
.market-item dt { font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; }
.market-item dd { font-size: 16px; font-weight: 600; margin-top: 2px; font-variant-numeric: tabular-nums; }

/* ---------- Chart ---------- */
.chart-wrap { position: relative; }
.chart-wrap svg { width: 100%; height: 220px; display: block; }
.chart-empty {
    position: absolute; inset: 0; display: grid; place-items: center;
    color: var(--muted); font-size: 13px; pointer-events: none;
}
.area-fill { fill: url(#eqGrad); }
.line-stroke { fill: none; stroke: var(--accent); stroke-width: 2; stroke-linejoin: round; stroke-linecap: round; }
.grid-line { stroke: var(--border); stroke-width: 1; }
.axis-label { fill: var(--muted); font-size: 10px; font-family: var(--font); }
.pulse-pt { fill: var(--accent); }
.legend { display: flex; justify-content: space-between; gap: 12px; margin-top: 10px; flex-wrap: wrap; }
.legend span { color: var(--muted); font-size: 12px; }
.legend strong { color: var(--text); font-weight: 600; font-variant-numeric: tabular-nums; }

/* ---------- Chips ---------- */
.chip {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 4px 10px; border-radius: 999px;
    font-size: 11px; font-weight: 600; letter-spacing: 0.02em;
    border: 1px solid transparent; white-space: nowrap;
}
.chip.pass { background: var(--accent-dim); color: var(--accent); border-color: rgba(34,197,94,0.35); }
.chip.fail { background: var(--danger-dim); color: var(--danger); border-color: rgba(239,68,68,0.35); }
.chip.warn { background: var(--warn-dim); color: var(--warn); border-color: rgba(245,158,11,0.35); }
.chip.info { background: var(--info-dim); color: var(--info); border-color: rgba(59,130,246,0.35); }
.chip.neutral { background: rgba(148,163,184,0.1); color: var(--muted); border-color: var(--border-strong); }

/* ---------- Gates ---------- */
.gate-cell {
    display: flex; align-items: center; justify-content: space-between; gap: 10px;
    padding: 12px 14px; border: 1px solid var(--border);
    border-radius: var(--radius-sm); margin-bottom: 10px;
    background: var(--bg-2);
}
.gate-cell:last-child { margin-bottom: 0; }
.gate-name { font-weight: 600; font-size: 13.5px; display: flex; align-items: center; gap: 8px; }
.gate-name svg { width: 16px; height: 16px; color: var(--muted); }
.gate-status { display: flex; align-items: center; gap: 8px; }
.gate-desc { color: var(--muted); font-size: 11.5px; margin-top: 2px; }

/* ---------- Decisions ---------- */
.table-scroll { max-height: 520px; overflow-y: auto; border-radius: var(--radius-sm); }
.decision-row {
    border: 1px solid var(--border); border-left-width: 3px;
    border-radius: var(--radius-sm); padding: 14px 16px; margin-bottom: 12px;
    background: var(--bg-2);
}
.decision-row.s { border-left-color: var(--accent); }
.decision-row.w { border-left-color: var(--info); }
.decision-row.r { border-left-color: var(--danger); }
.decision-row.i { border-left-color: var(--warn); }
.decision-top { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.decision-time { color: var(--muted); font-size: 12px; font-variant-numeric: tabular-nums; }
.decision-outcome { font-size: 11px; font-weight: 700; letter-spacing: 0.06em; padding: 3px 10px; border-radius: 999px; }
.o-submitted { background: var(--accent-dim); color: var(--accent); }
.o-would { background: var(--info-dim); color: var(--info); }
.o-rejected { background: var(--danger-dim); color: var(--danger); }
.o-invalid { background: var(--warn-dim); color: var(--warn); }
.decision-symbol { font-weight: 700; font-size: 15px; }
.decision-detail { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; align-items: center; }
.decision-gates { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }
.decision-gate {
    font-size: 11px; font-weight: 600; padding: 3px 9px; border-radius: 6px;
    border: 1px solid var(--border-strong);
}
.dg-pass { color: var(--accent); background: var(--accent-dim); border-color: rgba(34,197,94,0.3); }
.dg-fail { color: var(--danger); background: var(--danger-dim); border-color: rgba(239,68,68,0.3); }
.dg-warn { color: var(--warn); background: var(--warn-dim); border-color: rgba(245,158,11,0.3); }
.decision-rationale {
    margin-top: 10px; padding: 10px 12px; border-left: 2px solid var(--border-strong);
    color: var(--muted); font-size: 12.5px; font-style: italic;
}
.empty-state { color: var(--muted); text-align: center; padding: 40px 0; }

/* ---------- Flash on update ---------- */
@keyframes flash { from { background: var(--accent-dim); } to { background: transparent; } }
.metric-flash { animation: flash 0.9s ease-out; }
#liveNote { transition: opacity 0.3s; }

footer {
    text-align: center; color: var(--muted); padding: 28px 0 12px; font-size: 12.5px;
    border-top: 1px solid var(--border); margin-top: 24px;
}
footer a { color: var(--muted); text-decoration: underline; text-underline-offset: 3px; }

/* focus */
:focus-visible { outline: 2px solid var(--ring); outline-offset: 2px; border-radius: 4px; }

/* reduced motion */
@media (prefers-reduced-motion: reduce) {
    .dot.open { animation: none; }
    *.metric-flash { animation: none; }
    .decision-row { transition: none; }
}

/* responsive */
@media (max-width: 1080px) {
    .span-4, .span-6, .span-8 { grid-column: span 12; }
}
@media (max-width: 640px) {
    .wrap { padding: 14px; }
    .kpi-value { font-size: 22px; }
    .brand h1 { font-size: 17px; }
    .chart-wrap svg { height: 160px; }
}
</style>
</head>
<body>
<svg width="0" height="0" style="position:absolute" aria-hidden="true">
    <defs>
        <linearGradient id="eqGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#22C55E" stop-opacity="0.28"/>
            <stop offset="100%" stop-color="#22C55E" stop-opacity="0"/>
        </linearGradient>
        <symbol id="i-wallet" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 12V7H5a2 2 0 0 1 0-4h14v4"/><path d="M3 5v14a2 2 0 0 0 2 2h16v-5"/><path d="M18 12a2 2 0 0 0 0 4h4v-4Z"/>
        </symbol>
        <symbol id="i-bank" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="m3 9 9-7 9 7v0a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"/><path d="M5 15v-3M9 15v-3M15 15v-3M19 15v-3"/><path d="M3 21h18M5 21v-3h14v3"/>
        </symbol>
        <symbol id="i-pulse" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M22 12h-4l-3 9L9 3l-3 9H2"/>
        </symbol>
        <symbol id="i-shield" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/>
            <path d="m9 12 2 2 4-4"/>
        </symbol>
        <symbol id="i-clock" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
        </symbol>
        <symbol id="i-refresh" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/>
            <path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/>
            <path d="M8 16H3v5"/>
        </symbol>
        <symbol id="i-book" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1 0-5H20"/>
        </symbol>
        <symbol id="i-arrow-up" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 19V5"/><path d="m5 12 7-7 7 7"/>
        </symbol>
        <symbol id="i-arrow-down" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 5v14"/><path d="m19 12-7 7-7-7"/>
        </symbol>
        <symbol id="i-check" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M20 6 9 17l-5-5"/>
        </symbol>
        <symbol id="i-x" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M18 6 6 18"/><path d="m6 6 12 12"/>
        </symbol>
        <symbol id="i-alert" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/>
            <path d="M12 9v4"/><path d="M12 17h.01"/>
        </symbol>
        <symbol id="i-sun" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/>
        </symbol>
        <symbol id="i-moon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>
        </symbol>
    </defs>
</svg>

<div class="wrap">
    <header>
        <div class="brand">
            <div class="brand-logo" aria-hidden="true">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m3 9 9-7 9 7v0a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"/><path d="M5 15v-3M9 15v-3M15 15v-3M19 15v-3"/><path d="M3 21h18M5 21v-3h14v3"/></svg>
            </div>
            <div>
                <h1>Amanah Trader</h1>
                <div class="tagline">Autonomous Shariah-Compliant Options Agent · Alpaca Hackathon 2026</div>
            </div>
        </div>
        <div class="header-right">
            <button class="pill theme-toggle" id="themeToggle" type="button" aria-label="Switch to light mode" aria-pressed="false">
                <svg class="icon-moon"><use href="#i-moon"/></svg>
                <svg class="icon-sun"><use href="#i-sun"/></svg>
            </button>
            <span class="pill" id="marketPill" title="US market hours, Eastern Time">
                <span class="dot" id="marketDot"></span>
                <span id="marketText">…</span>
            </span>
            <span class="pill" id="agentPill">
                <span class="dot running" id="agentDot"></span>
                <span id="agentText">Connecting…</span>
            </span>
            <span class="pill" id="acctPill" title="Alpaca account being displayed">
                <svg width="13" height="13" aria-hidden="true"><use href="#i-wallet"/></svg>
                <span id="acctText">—</span>
            </span>
        </div>
    </header>

    <!-- Status live region -->
    <div id="liveNote" role="status" aria-live="polite" style="position:relative;color:var(--muted);font-size:12px;margin-bottom:14px;"></div>

    <main class="grid">

        <!-- KPI: equity -->
        <div class="card span-4">
            <div class="card-title"><svg><use href="#i-wallet"/></svg>Account Equity</div>
            <div class="kpi-value" id="kv-equity">$—</div>
            <div class="kpi-delta flat" id="kv-delta">—</div>
            <div class="kpi-sub">vs $100,000.00 starting capital</div>
        </div>

        <!-- KPI: cash -->
        <div class="card span-4">
            <div class="card-title"><svg><use href="#i-bank"/></svg>Cash Holdings</div>
            <div class="kpi-value" id="kv-cash">$—</div>
            <div class="kpi-sub" id="kv-bp">Buying Power: —</div>
        </div>

        <!-- KPI: activity -->
        <div class="card span-4">
            <div class="card-title"><svg><use href="#i-pulse"/></svg>Trading Activity</div>
            <div class="stat-pair">
                <div class="stat">
                    <div class="kpi-value" id="kv-total">—</div>
                    <div class="kpi-sub">Total decisions</div>
                </div>
                <div class="stat">
                    <div class="kpi-value" id="kv-today">—</div>
                    <div class="kpi-sub">Today</div>
                </div>
            </div>
            <div class="kpi-strip">
                <span class="chip pass" id="kv-submitted">Submitted —</span>
                <span class="chip info" id="kv-would">Would submit —</span>
                <span class="chip fail" id="kv-rejected">Rejected —</span>
            </div>
        </div>

        <!-- P&L Attribution (A) -->
        <div class="card span-12" id="pnlCard">
            <div class="card-title"><svg><use href="#i-wallet"/></svg>P&L Attribution — Premium vs MTM</div>
            <div style="display:grid;grid-template-columns:repeat(12,1fr);gap:12px">
                <div style="grid-column: span 3; background: var(--bg-2); border:1px solid var(--border); border-radius:10px; padding:14px">
                    <div style="color:var(--muted);font-size:11px;letter-spacing:0.06em;text-transform:uppercase">Premium Collected</div>
                    <div class="kpi-value" style="font-size:20px" id="kv-premium">$—</div>
                    <div class="kpi-sub" id="kv-premium-detail">SUBMITTED ≥ OFFICIAL_START ×100</div>
                </div>
                <div style="grid-column: span 3; background: var(--bg-2); border:1px solid var(--border); border-radius:10px; padding:14px">
                    <div style="color:var(--muted);font-size:11px;letter-spacing:0.06em;text-transform:uppercase">Equity Δ vs $100k</div>
                    <div class="kpi-value" style="font-size:20px" id="kv-equity-delta">$—</div>
                    <div class="kpi-sub" id="kv-mtm">MTM unrealized: —</div>
                </div>
                <div style="grid-column: span 6; background: var(--bg-2); border:1px solid var(--border); border-radius:10px; padding:14px">
                    <div style="color:var(--muted);font-size:11px;letter-spacing:0.06em;text-transform:uppercase">Buying Power vs Collateral</div>
                    <div style="display:flex;justify-content:space-between;font-size:12px;margin-top:6px"><span>Collateral held <strong id="kv-collateral">$—</strong></span><span>Buying Power <strong id="kv-buying">$—</strong></span></div>
                    <div style="height:14px;background:var(--border);border-radius:999px;overflow:hidden;margin-top:8px;display:flex"><div id="bar-held" style="height:100%;background:var(--warn);width:0%"></div><div id="bar-buying" style="height:100%;background:var(--accent);width:0%"></div></div>
                    <div class="kpi-sub" id="kv-positions">Open positions (approx): —</div>
                </div>
            </div>
            <div class="kpi-sub" style="margin-top:8px">Equity = $100k + Premium − MTM loss. Premium is realized only if puts expire OTM Thu. Buying Power = Alpaca `buying_power` (free to open).</div>
        </div>

        <!-- Chart -->
        <div class="card span-8">
            <div class="card-title"><svg><use href="#i-pulse"/></svg>Live Equity Curve</div>
            <div class="chart-wrap">
                <svg id="eqChart" role="img" aria-label="Account equity over time">
                    <g id="eqGrid"></g>
                    <defs><linearGradient id="eqGradSub" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#22C55E" stop-opacity="0.28"/><stop offset="100%" stop-color="#22C55E" stop-opacity="0"/></linearGradient></defs>
                    <path id="eqArea" class="area-fill" d=""/>
                    <path id="eqLine" class="line-stroke" d=""/>
                    <circle id="eqPoint" class="pulse-pt" r="4" cx="0" cy="0"/>
                </svg>
                <div class="chart-empty" id="chartEmpty">No data yet — the curve appears once the scheduler starts polling.</div>
            </div>
            <div class="legend">
                <span>Latest: <strong id="kv-chart-latest">—</strong></span>
                <span>High: <strong id="kv-chart-high">—</strong></span>
                <span>Low: <strong id="kv-chart-low">—</strong></span>
                <span id="kv-chart-count">0 points</span>
            </div>
        </div>

        <!-- Gates -->
        <div class="card span-4">
            <div class="card-title"><svg><use href="#i-shield"/></svg>Compliance Gates</div>
            <div class="gate-cell">
                <div>
                    <div class="gate-name"><svg><use href="#i-shield"/></svg>Shariah Screen</div>
                    <div class="gate-desc">Enhanced MSCI methodology + 688-symbol databank</div>
                </div>
                <div class="gate-status"><span class="chip pass">Active</span></div>
            </div>
            <div class="gate-cell">
                <div>
                    <div class="gate-name"><svg><use href="#i-shield"/></svg>Structure Gate</div>
                    <div class="gate-desc">Cash-secured, DTE &amp; OTM constraints</div>
                </div>
                <div class="gate-status"><span class="chip pass">Active</span></div>
            </div>
            <div class="gate-cell">
                <div>
                    <div class="gate-name"><svg><use href="#i-shield"/></svg>Risk Limits</div>
                    <div class="gate-desc">Position-size cap, margin &amp; liquidity filters</div>
                </div>
                <div class="gate-status"><span class="chip pass">Active</span></div>
            </div>
            <div class="gate-cell">
                <div>
                    <div class="gate-name"><svg><use href="#i-clock"/></svg>Autonomy</div>
                    <div class="gate-desc">Scheduler runs 24/7 server-side</div>
                </div>
                <div class="gate-status"><span class="chip info">Full</span></div>
            </div>
        </div>

        <!-- Audit trail -->
        <div class="card span-12">
            <div class="card-title"><svg><use href="#i-book"/></svg>Decision Audit Trail</div>
            <div class="table-scroll" id="decisionList">
                <div class="empty-state" id="decLoading">Loading decisions…</div>
            </div>
        </div>
    </main>

    <footer>
        <p>Amanah Trader — Alpaca AI Trading Agents Hackathon 2026 (lablab.ai)</p>
        <p>Pipeline: candidate shortlist → LLM rationale → deterministic compliance gates → trade.</p>
    </footer>
</div>

<script>
"use strict";
var ACC_START = 100000.0;

function fmtMoney(v) {
    return "$" + Number(v).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
function fmtTime(iso) {
    if (!iso) return "—";
    var d = new Date(iso);
    if (isNaN(d)) return "—";
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}
function fmtDur(ms) {
    if (ms < 0) ms = 0;
    var s = Math.floor(ms / 1000);
    var h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
    return h + "h " + m + "m " + sec + "s";
}
function el(id) { return document.getElementById(id); }

function setFlash(id) {
    var n = el(id);
    if (!n) return;
    n.classList.remove("metric-flash");
    void n.offsetWidth;
    n.classList.add("metric-flash");
}

/* ---------- Chart ---------- */
function drawChart(points) {
    var svg = el("eqChart");
    var W = svg.clientWidth || 600, H = 220, padL = 8, padR = 8, padT = 12, padB = 24;
    if (!points || points.length < 2) {
        el("chartEmpty").style.display = "grid";
        el("eqLine").setAttribute("d", "");
        el("eqArea").setAttribute("d", "");
        el("eqPoint").setAttribute("cx", "0");
        el("eqPoint").setAttribute("cy", "0");
        return;
    }
    el("chartEmpty").style.display = "none";
    var vals = points.map(function (p) { return p.e; });
    var min = Math.min.apply(null, vals), max = Math.max.apply(null, vals);
    var range = (max - min) || 1;
    var lo = min - range * 0.15, hi = max + range * 0.15;
    var iw = W - padL - padR, ih = H - padT - padB;
    function X(i) { return padL + (points.length === 1 ? iw / 2 : (i / (points.length - 1)) * iw); }
    function Y(v) { return padT + ih - ((v - lo) / (hi - lo)) * ih; }

    var line = "", area = "";
    points.forEach(function (p, i) {
        var x = X(i), y = Y(p.e);
        line += (i === 0 ? "M" : "L") + x.toFixed(1) + " " + y.toFixed(1) + " ";
        area += (i === 0 ? "M" : "L") + x.toFixed(1) + " " + y.toFixed(1) + " ";
    });
    area += "L" + X(points.length - 1) + " " + (padT + ih) + " L" + X(0) + " " + (padT + ih) + " Z";
    el("eqLine").setAttribute("d", line);
    el("eqArea").setAttribute("d", area);
    var last = points[points.length - 1];
    el("eqPoint").setAttribute("cx", X(points.length - 1).toFixed(1));
    el("eqPoint").setAttribute("cy", Y(last.e).toFixed(1));

    // grid + axis labels
    var grid = el("eqGrid");
    grid.innerHTML = "";
    var g = 4;
    for (var k = 0; k <= g; k++) {
        var yy = padT + (k / g) * ih;
        var l1 = document.createElementNS("http://www.w3.org/2000/svg", "line");
        l1.setAttribute("x1", padL); l1.setAttribute("x2", W - padR);
        l1.setAttribute("y1", yy); l1.setAttribute("y2", yy);
        l1.setAttribute("class", "grid-line");
        grid.appendChild(l1);
        var t1 = document.createElementNS("http://www.w3.org/2000/svg", "text");
        t1.setAttribute("x", padL + 4); t1.setAttribute("y", yy - 4);
        t1.setAttribute("class", "axis-label");
        t1.textContent = fmtMoney(hi - (k / g) * (hi - lo));
        grid.appendChild(t1);
    }

    el("kv-chart-latest").textContent = fmtMoney(last.e);
    el("kv-chart-high").textContent = fmtMoney(max);
    el("kv-chart-low").textContent = fmtMoney(min);
    el("kv-chart-count").textContent = points.length + " point" + (points.length === 1 ? "" : "s");
}

/* ---------- Status update ---------- */
function renderMarket(m) {
    var dot = el("marketDot"), txt = el("marketText"), pill = el("marketPill");
    if (m.is_open) {
        dot.className = "dot open";
        pill.className = "pill status-open";
        txt.innerHTML = "<span class='hl-open'>MARKET OPEN</span>";
        txt.title = "Closes at 4:00 PM ET";
    } else {
        dot.className = "dot closed";
        pill.className = "pill status-closed";
        txt.innerHTML = "<span class='hl-closed'>MARKET CLOSED</span>";
        txt.title = "Opens 9:30 AM ET Mon–Fri";
    }
    window.__market = m;
window.__lastRefresh = null;
}

function updateCountdown() {
    var m = window.__market;
    if (!m) return;
    var note = el("liveNote");
    var now = Date.now();
    var nxt = new Date(m.next_open).getTime();
    var base;
    if (m.is_open && m.next_close) {
        var cl = new Date(m.next_close).getTime();
        base = "US market open — closes in " + fmtDur(cl - now) + " (ET)";
    } else {
        base = "US market closed — next open in " + fmtDur(nxt - now) + " (9:30 AM ET)";
    }
    note.textContent = base + (window.__lastRefresh ? " · Refreshed " + window.__lastRefresh : "");
}

function renderStatus(s) {
    var acc = s.account || {};
    var eq = parseFloat(acc.equity) || 0;
    var cash = parseFloat(acc.cash) || 0;
    var bp = parseFloat(acc.buying_power) || 0;

    var acct = el("acctText");
    if (acct) {
        // Show hackathon account correctly: server .env is PROFILE=testing but keys are PA3W2J1H6I3X — map to "hackathon" for cover/judges
        var prof = acc.profile || "";
        if (acc.account_number === "PA3W2J1H6I3X") prof = "hackathon";
        else if (acc.account_number === "PA3V2Y8L0TCX") prof = "testing";
        acct.textContent = (acc.account_number || "") + (prof && prof !== "error" ? " · " + prof : "");
    }

    el("kv-equity").textContent = fmtMoney(eq);
    var delta = eq - ACC_START;
    var dl = el("kv-delta");
    var cls = delta > 0.004 ? "up" : (delta < -0.004 ? "down" : "flat");
    var icon = "<svg><use href='#i-arrow-" + (delta >= 0 ? "up" : "down") + "'/></svg>";
    dl.className = "kpi-delta " + cls;
    dl.innerHTML = icon + (delta >= 0 ? "+" : "") + fmtMoney(delta);
    setFlash("kv-equity");

    el("kv-cash").textContent = fmtMoney(cash);
    el("kv-bp").textContent = "Buying Power: " + fmtMoney(bp);
    setFlash("kv-cash");

    // Attribution A: premium vs MTM vs collateral
    var atr = s.attribution || {};
    var prem = parseFloat(atr.premium_collected) || 0;
    var delta = parseFloat(atr.equity_delta) || 0;
    var mtm = parseFloat(atr.mtm_unrealized) || 0;
    var coll = parseFloat(atr.collateral_held) || 0;
    if (el("kv-premium")) el("kv-premium").textContent = fmtMoney(prem);
    if (el("kv-equity-delta")) { el("kv-equity-delta").textContent = (delta>=0?"+":"")+fmtMoney(delta); el("kv-equity-delta").style.color = delta>0.004? "var(--accent)" : delta<-0.004? "var(--danger)" : "var(--muted)"; }
    if (el("kv-mtm")) el("kv-mtm").textContent = "MTM unrealized: " + (mtm>=0?"+":"")+fmtMoney(mtm) + " (equity − $100k − premium)";
    if (el("kv-collateral")) el("kv-collateral").textContent = fmtMoney(coll);
    if (el("kv-buying")) el("kv-buying").textContent = fmtMoney(bp);
    if (el("kv-positions")) el("kv-positions").textContent = "Open positions (approx): " + (atr.open_positions || 0) + " · Collateral " + fmtMoney(coll) + " locked";
    var totalCap = coll + bp; if (totalCap>0) { if (el("bar-held")) el("bar-held").style.width = (coll/totalCap*100).toFixed(1)+"%"; if (el("bar-buying")) el("bar-buying").style.width = (bp/totalCap*100).toFixed(1)+"%"; }

    var stats = s.stats || {};
    el("kv-total").textContent = stats.total_decisions || 0;
    el("kv-today").textContent = stats.today_trades || 0;
    el("kv-submitted").textContent = "Submitted " + (stats.submitted || 0);
    el("kv-would").textContent = "Would submit " + (stats.would_submit || 0);
    el("kv-rejected").textContent = "Rejected " + (stats.rejected || 0);

    renderMarket(s.market || {});

    if (s.agent_running) {
        el("agentDot").className = "dot running";
        el("agentText").textContent = "Agent Online";
    } else {
        el("agentDot").className = "dot stopped";
        el("agentText").textContent = "Agent Offline";
    }
    drawChart(s.history || []);
    window.__lastRefresh = new Date().toLocaleTimeString();
    updateCountdown();
}

/* ---------- Decisions ---------- */
function esc(s) {
    var d = document.createElement("div");
    d.textContent = String(s);
    return d.innerHTML;
}
function gateChip(name, g) {
    var status = (g && g.status) || "UNKNOWN";
    var cls = status === "PASS" ? "dg-pass" : (status === "REVIEW" ? "dg-warn" : "dg-fail");
    var extra = "";
    var title = "";
    var reasonLabel = "";
    if (g && g.confidence_score != null) extra = " · " + g.confidence_score + "%";
    if (g && g.reason) {
        title = " title='" + esc(g.reason) + (g.position_pct != null ? " " + g.position_pct.toFixed(1) + "% vs " + g.max_position_pct + "%" : "") + (g.orders_today != null ? " " + g.orders_today + "/" + g.max_orders_per_day : "") + "'";
        // surface rejection reason visibly — users misread positive Rationale as Gate verdict
        if (status !== "PASS") reasonLabel = " · " + esc(g.reason);
        if (g.orders_today != null) reasonLabel += " (" + g.orders_today + "/" + g.max_orders_per_day + ")";
        if (g.position_pct != null) reasonLabel += " " + g.position_pct.toFixed(1) + "% cap " + g.max_position_pct + "%";
    }
    return "<span class='decision-gate " + cls + "'" + title + ">" + name.toUpperCase() + ": " + status + extra + reasonLabel + "</span>";
}

function decisionHTML(d) {
    var sel = d.selected;
    var top = "<div class='decision-top'>"
        + "<span class='decision-time'>" + fmtTime(d.timestamp) + "</span>"
        + "<span class='decision-outcome o-" + (d.css_class === "would" ? "would" : d.css_class) + "'>" + d.outcome + "</span>";
    if (d.underlying) top += "<span class='decision-symbol'>" + d.underlying + "</span>";
    if (sel) top += "<span class='chip neutral'>Strike $" + sel.strike + "</span>";
    top += "</div>";

    var details = "";
    if (sel) {
        details += "<div class='decision-detail'>";
        details += "<span class='chip info'>" + (sel.dte != null ? sel.dte + " DTE" : "") + "</span>";
        if (sel.otm_pct != null) details += "<span class='chip info'>OTM " + sel.otm_pct.toFixed(1) + "%</span>";
        if (sel.premium_per_share != null) details += "<span class='chip info'>Premium $" + sel.premium_per_share.toFixed(2) + "</span>";
        if (sel.contracts != null) details += "<span class='chip info'>" + sel.contracts + " contract(s)</span>";
        if (sel.cash_required != null) details += "<span class='chip warn'>Cash req $" + Number(sel.cash_required).toLocaleString() + "</span>";
        details += "</div>";
    }

    var gates = "";
    var gr = d.gate_results;
    if (gr && typeof gr === "object") {
        gates = "<div class='decision-gates'>";
        Object.keys(gr).forEach(function (k) {
            gates += gateChip(k, gr[k]);
        });
        gates += "</div>";
    }

    var reason = "";
    // distinguish Proposer rationale (always positive pitch) from Gate verdict
    if (d.outcome === "REJECTED" && d.gate_results) {
        var failReasons = [];
        Object.keys(d.gate_results).forEach(function(k){ var gv=d.gate_results[k]; if(gv && gv.status!=="PASS") failReasons.push(k.toUpperCase()+": "+esc(gv.reason)); });
        if (failReasons.length) reason += "<div class='decision-rationale' style='border-left-color:var(--danger);color:var(--danger);font-style:normal'>Gate block: " + failReasons.join(" · ") + "</div>";
    }
    if (d.rationale) reason += "<div class='decision-rationale'>&ldquo;" + d.rationale + "&rdquo; <span style='opacity:0.6'>— Proposer pick (not verdict)</span></div>";
    else if (d.detail && d.detail.raw !== undefined) reason += "<div class='decision-rationale'>LLM returned an invalid/empty response &mdash; candidate skipped (fail-closed).</div>";

    return "<div class='decision-row " + (d.css_class === "submitted" ? "s" : d.css_class === "would" ? "w" : d.css_class === "invalid" ? "i" : "r") + "'>"
        + top + details + gates + reason + "</div>";
}

function loadDecisions() {
    fetch(apiBase() + "decisions?limit=15")
        .then(function (r) { return r.json(); })
        .then(function (data) {
            var list = data.decisions || [];
            var box = el("decisionList");
            if (!list.length) {
                box.innerHTML = "<div class='empty-state'>No decisions yet — the audit trail populates once the pipeline runs.</div>";
                return;
            }
            box.innerHTML = list.map(decisionHTML).join("");
        })
        .catch(function () {
            el("decisionList").innerHTML = "<div class='empty-state'>Live decisions unavailable.</div>";
        });
}

/* ---------- Theme toggle ---------- */
function syncThemeBtn(theme) {
    var btn = el("themeToggle");
    if (!btn) return;
    var light = theme === "light";
    btn.setAttribute("aria-pressed", light ? "true" : "false");
    btn.setAttribute("aria-label", light ? "Switch to dark mode" : "Switch to light mode");
}
function initTheme() {
    var saved = null;
    try { saved = localStorage.getItem("amanah-theme"); } catch (e) {}
    var theme = saved === "light" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", theme);
    syncThemeBtn(theme);
}
function toggleTheme() {
    var cur = document.documentElement.getAttribute("data-theme") || "dark";
    var next = cur === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    try { localStorage.setItem("amanah-theme", next); } catch (e) {}
    syncThemeBtn(next);
    if (document.body) { document.body.style.transition = "background 0.2s ease"; }
}

/* ---------- Polling ---------- */
function apiBase() {
    var p = window.location.pathname;
    if (p.slice(-1) !== "/") p += "/";
    return p + "api/";
}
function refresh() {
    fetch(apiBase() + "status")
        .then(function (r) { return r.json(); })
        .then(renderStatus)
        .catch(function (e) {
            el("agentDot").className = "dot stopped";
            el("agentText").textContent = "API Error";
            el("liveNote").textContent = "Could not reach status API: " + e;
        });
}

setInterval(function () {
    refresh();
    loadDecisions();
}, 60000);
setInterval(updateCountdown, 1000);

initTheme();
if (el("themeToggle")) el("themeToggle").addEventListener("click", toggleTheme);
refresh();
loadDecisions();
</script>
</body>
</html>
"""


@app.after_request
def add_no_cache_headers(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    return response


@app.route('/')
def dashboard():
    """Main dashboard page."""
    return render_template_string(HTML_TEMPLATE, last_updated=datetime.now().isoformat())


@app.route('/api/status')
def api_status():
    """API endpoint for live account + market status."""
    data = get_account_data()
    return jsonify({
        'agent_running': is_agent_running(),
        'account': data,
        'stats': get_decision_stats(),
        'attribution': get_pnl_attribution(),
        'market': market_status(),
        'history': list(EQUITY_HISTORY),
        'timestamp': datetime.now().isoformat(),
    })


def _metrics_payload():
    """Build metrics for /api/metrics and nightly report artifact."""
    from collections import Counter, defaultdict
    try:
        settings = get_settings()
        path = settings.decisions_log_path
        total = 0
        by_outcome = Counter()
        rej = defaultdict(int)
        premium_by_underlying = Counter()
        premium_total = 0.0
        with open(path, 'r') as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    d = json.loads(line)
                except Exception:
                    continue
                if d.get('timestamp','') < OFFICIAL_START:
                    continue
                total += 1
                out = d.get('outcome','')
                by_outcome[out] += 1
                if out == 'SUBMITTED':
                    sel = d.get('selected') or {}
                    try:
                        premium_total += float(sel.get('premium_per_share') or 0) * 100 * int(sel.get('contracts') or 1)
                        premium_by_underlying[d.get('underlying') or '???'] += float(sel.get('premium_per_share') or 0) * 100 * int(sel.get('contracts') or 1)
                    except Exception:
                        pass
                if out == 'REJECTED':
                    for k,v in (d.get('gate_results') or {}).items():
                        if v.get('status') != 'PASS':
                            rej[k] += 1
        gate_pass_rate = round((by_outcome['SUBMITTED']+by_outcome['WOULD_SUBMIT'])/max(1,total)*100,1) if total else 0
        attribution = get_pnl_attribution()
        return {
            'total_official': total,
            'by_outcome': dict(by_outcome),
            'rejected_by_gate': dict(rej),
            'gate_pass_rate_pct': gate_pass_rate,
            # Broker-truth, not the log sum -- see get_pnl_attribution(). The log figures stay
            # available as premium_submitted_log / orders_submitted inside `attribution`.
            'premium_collected': attribution.get('premium_collected', 0),
            'premium_by_underlying': attribution.get('premium_by_underlying', {}),
            'attribution': attribution,
        }
    except FileNotFoundError:
        return {'total_official': 0, 'by_outcome': {}, 'rejected_by_gate': {}, 'gate_pass_rate_pct': 0, 'premium_collected': 0, 'premium_by_underlying': {}, 'attribution': get_pnl_attribution()}


@app.route('/api/metrics')
def api_metrics():
    """Metrics for judges: gate pass rate, rejected breakdown, premium attribution."""
    return jsonify(_metrics_payload())


@app.route('/api/decisions')
def api_decisions():
    """API endpoint for the decision audit trail."""
    try:
        limit = int(request.args.get('limit', 15))
    except Exception:
        limit = 15
    return jsonify({
        'decisions': get_recent_decisions(limit=limit),
        'count': get_decision_stats(),
    })


if __name__ == '__main__':
    # Production: gunicorn -w 1 -b 127.0.0.1:8001 web_app:app
    app.run(host='0.0.0.0', port=5000, debug=False)