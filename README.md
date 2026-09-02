# Amanah Trader

An autonomous options-trading agent that **cannot be talked into a non-compliant trade.**

Built for the Alpaca AI Trading Agents Hackathon (lablab.ai, Aug 28 – Sep 4 2026, Options Alpha
Agents track). It trades cash-secured puts on Alpaca paper, unattended, and every order must
first clear a chain of deterministic compliance gates written in plain Python. The language
model participates in the decision — it just has no authority over it.

**Live status page:** <https://amanahtrader.uk/hackathon/>
**Broker:** Alpaca paper trading. No real capital at any point.

---

## The idea

Most trading agents optimise for one thing. Real mandates don't work that way: a fund with an
ethical, religious, or regulatory constraint must sometimes refuse a profitable trade, and a
trader who refuses on those grounds isn't failing — they're governing. The hard part is
*proving* an autonomous agent would refuse.

So the constraint here is Shariah compliance, chosen because it is unusually demanding and
externally verifiable: permissible business activity, no interest-bearing structures, no
margin. And the enforcement is deliberately boring — the screen is a lookup and a set of
inequalities, not a prompt. An LLM cannot argue with an `if` statement.

## Architecture

```
 universe ─► candidate generation ─► shortlist ─► LLM proposes ─► GATES ─► broker
            (deterministic rank)      (cap 10)     (index +        (all      (alpaca
                                                   rationale)      or none)   order submit)
                                           │                          │
                                           └──────────────────────────┴─► logs/decisions.jsonl
```

**1. Candidate generation — deterministic.** `agent/candidates.py` pulls live option chains and
filters to 1–7 DTE, 2–7% out-of-the-money, bid ≥ $0.70, bid-ask spread ≤ 15% of mid. Survivors
are ranked by distance from a 3% OTM target, then by premium. `rank_candidates()` is pure —
fixed input, fixed output, no I/O — which is what makes it testable.

**2. Proposal — the LLM's entire job.** `agent/llm.py` sends the shortlist to Featherless
(`Qwen/Qwen3.8-27B`) and asks for **one index and a one-to-three sentence rationale.** It cannot
invent a strike, a premium, an expiry, or a symbol; it can only point at a row the deterministic
ranker already approved. If it returns malformed JSON, times out, or declines, `agent/pipeline.py`
falls back to rank 0 and records that it did (ADR-0002).

**3. Gates — where compliance actually lives.** All four are pure functions. All fail closed.

| Gate | Rule | Source |
|---|---|---|
| Shariah | Symbol must be in the curated universe; confidence ≥ 70 passes, 50–69 is REVIEW, below that FAILs. **Unlisted ⇒ FAIL, always.** | `agent/gates/shariah_enhanced.py` |
| Structure | Cash-secured puts only. `strike × 100 × contracts` must be covered by cash **not already committed to open short puts.** No margin. | `agent/gates/structure.py` |
| Riba | The *account*, not the trade: positive settled cash, obligations covered by cash rather than broker credit, no borrowed stock, nothing held that accrues interest. | `agent/gates/riba.py` |
| Risk | Max orders/day, max position % of equity, max daily loss %. | `agent/gates/risk.py` |

`pipeline.py` submits only on unanimous `PASS`. Anything else is logged with the failing gate
and the trade is dropped.

**4. Evidence.** Every cycle appends one JSON line to `logs/decisions.jsonl` — candidates
considered, the LLM's rationale, each gate's verdict and reasoning, and the order id if one was
placed. Rejections and LLM failures are logged as loudly as fills. Nobody is watching an
unattended agent at 03:00, so the trail is the accountability.

## Alpaca infrastructure

- **Execution transport is the CLI, not the SDK and not MCP.** Alpaca's own guidance documents
  MCP as interactive/session-bound and recommends the CLI for unattended automation (ADR-0001).
- **Two transports, and it matters which is which.** Locally, `agent/cli.py` shells out to the
  official Alpaca CLI binary (v0.0.14). **On the VPS, `alpaca` is `alpaca_cli.py` in this
  repo** — a small stdlib-`urllib` client implementing the same command surface against the
  Alpaca REST API, because the Go binary wasn't available for that environment. Same commands,
  same API, different implementation; stated plainly here so nobody has to discover it.
- No `alpaca-py`, no `requests`. Standard library plus `subprocess`, and Flask for the status
  page.
- Scheduling is systemd (`hackathon-scheduler`), one cycle per hour during market hours.
- If no Alpaca executable is reachable, the agent **raises and stops.** It does not fall back to
  placeholder account data — an unreachable broker is an error, never a default.

## Results

Judged account `PA3W2J1H6I3X`, official window from Mon Aug 31 09:30 ET.

| | |
|---|---|
| Equity | $100,077.83 (**+0.078%**) |
| Premium collected, broker-confirmed | $274.00 |
| Collateral committed | $94,500 of $100,273 cash |
| Open positions | 2 |

That is a small number and it is the real one. Reported figures come from `position_list`, not
from summing orders the agent submitted — four submitted orders never filled, and an earlier
version of this dashboard counted them as collected premium (`agent/reconcile.py` exists because
of that bug). The gap between submitted and filled is published rather than hidden: `/api/metrics`
reports `orders_submitted` alongside `orders_open` and names every contract that didn't stick.

## Running it

```bash
cp .env.example .env          # then fill in FEATHERLESS_API_KEY and FEATHERLESS_MODEL
alpaca profile login --name testing
python -m agent.pipeline --dry-run     # full cycle, logs WOULD_SUBMIT, never submits
python -m agent.pipeline               # live: submits on unanimous PASS
python -m agent.report                 # reconciled P&L attribution
pytest tests/                          # 49 tests
```

The test suite covers what actually matters: fail-closed on unlisted symbols, margin rejection,
aggregate collateral accounting, the position-size cap, the DTE/OTM/spread filters, and the
reconciliation of submitted-versus-filled orders.

## Known limitations

Stated because a compliance story that hides its own gaps isn't one.

- **The Shariah screen is a curated 15-symbol list**, hand-scored against MSCI Islamic
  methodology — not live financial-ratio screening from filings. Every symbol in it scores ≥ 80,
  so in practice the only rejection path that fires is "not in the universe". That path is the
  one that matters, but the 0–100 banding currently does less work than it looks like.
- **The Riba gate asserts margin is not *used*, not that it is unavailable.** Alpaca issued a
  margin-capable account (`multiplier: 4`) and that cannot be changed from here; the gate proves
  the account operates out of cash regardless, and logs the capability rather than hiding it.
- **Position sizing is capital-constrained, not conviction-weighted.** It targets 35% of equity
  and lands on 1–3 contracts because the universe is $27–$500/share.
- **Free-tier market data** is indicative, not OPRA. Quotes outside market hours are unreliable —
  the agent only acts during the session.

## Prior work disclosure

The concept, architecture, and an earlier working prototype were developed before the event
window at <https://github.com/SalmonIsFish/Ai_Finance_Syariah> (commits 2026-07-21 to
2026-08-26). Per lablab.ai staff guidance at kickoff, prior work may be **disclosed but not
included** — every file in this repository was authored during the event window (Aug 28 –
Sep 4 2026), from understanding rather than by copying. The prior repository's history is public
and timestamped for verification.

## Repository map

| Path | |
|---|---|
| `agent/candidates.py` | chain parsing, filtering, deterministic ranking |
| `agent/gates/` | the three compliance gates — pure, fail-closed |
| `agent/llm.py` | Featherless proposer, bounded to an index + rationale |
| `agent/pipeline.py` | orchestration; collateral accounting; the only place orders are submitted |
| `agent/reconcile.py` | broker-truth P&L attribution |
| `agent/evidence.py` | append-only decision log |
| `docs/adr/` | architecture decision records |
| `web_app.py` | status page and JSON API |

## License

MIT — see [LICENSE](LICENSE).
