#!/usr/bin/env python3
"""Nightly report parsing logs/decisions.jsonl - quant/LLM/syariah breakdown.
Run after close: python -m agent.report or python agent/report.py
No I/O beyond reading the log and printing - safe to run even while scheduler is active.
"""
from __future__ import annotations
import json
from collections import Counter, defaultdict
from pathlib import Path
from datetime import date

OFFICIAL_START = "2026-08-31T13:30:00+00:00"

def load_decisions(path: str = "logs/decisions.jsonl") -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    out = []
    for line in p.read_text().splitlines():
        line=line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            pass
    return out

def report(path: str = "logs/decisions.jsonl"):
    decs = load_decisions(path)
    total = len(decs)
    by_outcome = Counter(d.get("outcome") for d in decs)
    official = [d for d in decs if d.get("timestamp","") >= OFFICIAL_START]
    off_by = Counter(d.get("outcome") for d in official)
    print(f"Total decisions: {total} | Official window (>= {OFFICIAL_START}): {len(official)}")
    print(f"  All: {dict(by_outcome)}")
    print(f"  Official: {dict(off_by)}")
    # gate breakdown for REJECTED in official
    rej = defaultdict(int)
    for d in official:
        if d.get("outcome")=="REJECTED":
            for k,v in (d.get("gate_results") or {}).items():
                if v.get("status")!="PASS":
                    rej[k]+=1
    if rej:
        print(f"  REJECTED gates: {dict(rej)}")
    # LLM fallback / invalid
    fall = sum(1 for d in official if d.get("llm_fallback"))
    inv = off_by.get("LLM_INVALID_RESPONSE",0)
    declined = off_by.get("NO_TRADE_LLM_DECLINED",0)
    print(f"  LLM fallback: {fall} | INVALID: {inv} | DECLINED: {declined}")
    # last 5
    print("Last 5 official:")
    for d in official[-5:]:
        sel=d.get("selected") or {}
        print(f"  {d.get('timestamp')[11:19]} {d.get('outcome'):20s} {d.get('underlying') or '-':6s} {sel.get('symbol','-'):22s} otm {sel.get('otm_pct','-')}")
    # P&L vs start - use last official SUBMITTED equity if available
    try:
        from agent.config import get_settings
        from agent import cli
        acc=cli.account_get(get_settings().alpaca_profile)
        eq=float(acc.get("equity",0))
        print(f"Live equity: {eq:.2f} vs 100000 start = {eq-100000:+.2f} ({(eq-100000)/100000*100:+.2f}%)")
    except Exception as e:
        print(f"Live equity: unavailable ({e})")

if __name__ == "__main__":
    report()
