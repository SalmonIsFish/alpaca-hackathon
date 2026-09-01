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

def get_metrics(path: str = "logs/decisions.jsonl") -> dict:
    """Metrics for /api/metrics — same source as report()."""
    decs = load_decisions(path)
    total = len(decs)
    by_outcome = Counter(d.get("outcome") for d in decs)
    official = [d for d in decs if d.get("timestamp","") >= OFFICIAL_START]
    off_by = Counter(d.get("outcome") for d in official)
    rej = defaultdict(int)
    for d in official:
        if d.get("outcome")=="REJECTED":
            for k,v in (d.get("gate_results") or {}).items():
                if v.get("status")!="PASS":
                    rej[k]+=1
    fall = sum(1 for d in official if d.get("llm_fallback"))
    premium_total = 0.0
    premium_by_underlying = Counter()
    for d in official:
        if d.get("outcome")=="SUBMITTED":
            sel=d.get("selected") or {}
            try:
                premium_total += float(sel.get("premium_per_share") or 0)*100*int(sel.get("contracts") or 1)
                premium_by_underlying[d.get("underlying") or "???"] += float(sel.get("premium_per_share") or 0)*100*int(sel.get("contracts") or 1)
            except Exception:
                pass
    gate_pass_rate = round((off_by.get("SUBMITTED",0)+off_by.get("WOULD_SUBMIT",0))/max(1,len(official))*100,1) if official else 0
    return {
        "total": total, "official": len(official), "by_outcome": dict(by_outcome), "official_by_outcome": dict(off_by),
        "rejected_by_gate": dict(rej), "llm_fallback": fall, "premium_collected": round(premium_total,2),
        "premium_by_underlying": dict(premium_by_underlying), "gate_pass_rate_pct": gate_pass_rate,
        "last5": official[-5:],
    }


def report(path: str = "logs/decisions.jsonl", write_artifact: bool = True):
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
        eq=None
    # nightly markdown artifact B
    if write_artifact:
        try:
            metrics = get_metrics(path)
            out_dir = Path(path).parent
            out_file = out_dir / f"report-{date.today().isoformat()}.md"
            # attribution
            premium = metrics["premium_collected"]
            eq_val = eq if eq is not None else 0
            delta = eq_val - 100000 if eq_val else 0
            mtm = delta - premium if eq_val else 0
            lines = [
                f"# Nightly Report {date.today().isoformat()}",
                f"Official decisions: {metrics['official']} (gate pass {metrics['gate_pass_rate_pct']}%)",
                f"Outcomes: {metrics['official_by_outcome']}",
                f"Rejected by gate: {metrics['rejected_by_gate']}",
                f"LLM fallback: {metrics['llm_fallback']}",
                f"Premium collected (SUBMITTED ≥ OFFICIAL_START): ${premium:.2f}",
                f"Premium by underlying: {metrics['premium_by_underlying']}",
                f"Live equity: {eq_val:.2f} (Δ {delta:+.2f}, {delta/100000*100:+.2f}%) MTM unrealized: {mtm:+.2f}",
                f"Cap: 10, target_otm 3%, min_premium 0.70, universe 15 (INTC/PFE/KO low-strike)",
            ]
            for d in metrics["last5"]:
                sel=d.get("selected") or {}
                lines.append(f"- {d.get('timestamp')[11:19]} {d.get('outcome')} {d.get('underlying') or '-'} {sel.get('symbol','-')} prem {sel.get('premium_per_share')}")
            out_file.write_text("\n".join(lines))
            print(f"Wrote {out_file}")
        except Exception as e:
            print(f"Artifact write failed: {e}")

if __name__ == "__main__":
    report()
