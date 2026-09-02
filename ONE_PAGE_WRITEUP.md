# Amanah Trader — One-Page Write-up

> P&L measured Mon Aug 31 09:30 ET → Thu Sep 3 EOD (official FAQ; Fri Sep 4 reflects assignments only). Figures below are as of Wed Sep 2, 04:00 UTC and are broker-confirmed via `position_list`, not derived from submitted orders.

---

## Amanah Trader: Autonomous AI Trading with Ethical Constraints

**Problem.** Most AI trading agents optimize only for P&L. In real markets, constraints matter — a trader who must refuse a profitable trade because it violates ethics, religious principles, or risk policy is not failing, they are governing. Yet current agents have no auditable way to prove they would refuse.

**Solution.** A three-layer autonomous agent that *must* pass deterministic compliance before any order reaches the broker:

1. **Reasoning — Ranker proposes shortlist, LLM picks one.** The deterministic Ranker (`candidates.py:rank_candidates`) filters live Alpaca chains (1–7 DTE, 2–7% OTM, bid ≥ $0.70, spread ≤ 15% of mid) and sorts by distance from a 3% OTM target, then premium; the top 10 form the Shortlist. Featherless `Qwen/Qwen3.8-27B` then selects **one index** and writes a 1–3 sentence rationale — it cannot invent strikes, premiums, expiries or symbols, only point at a row code already approved. On malformed output, timeout, or refusal we fall back to rank 0 deterministically and log that we did (ADR-0002).

2. **Compliance — Gates decide.** Four pure, fail-closed gates, no LLM override:
   - *Shariah Screen* — curated 15-symbol universe scored 0–100 against MSCI Islamic methodology. ≥70 `PASS`, 50–69 `REVIEW`, below `FAIL`; the pipeline requires `status == "PASS"`, so REVIEW and FAIL both block. **Unlisted symbol ⇒ FAIL, always.**
   - *Structure Gate* — cash-secured puts only (`strike × 100 × contracts`), checked against cash **net of collateral already committed to open short puts**, so the invariant holds across the whole book rather than trade-by-trade. No margin.
   - *Account Riba Gate* — judges the account rather than the trade: settled cash positive, every obligation covered by cash and not broker credit, no borrowed stock, nothing held that accrues interest. Alpaca issued a margin-capable account (`multiplier: 4`); the gate proves we do not *use* it.
   - *Risk Gate* — `MAX_POSITION_PCT=40`, `MAX_ORDERS_PER_DAY=10`, `MAX_DAILY_LOSS_PCT=3`. Unlike a human-checked system, the agent cannot be talked into an oversized trade.

3. **Execution — Broker acts.** Only `PASS/PASS/PASS` reaches `alpaca order submit`. Every decision — including rejections, LLM failures and no-candidate cycles — is appended to `logs/decisions.jsonl` with full evidence. If no Alpaca executable is reachable the agent raises and halts; it never falls back to placeholder account data.

**Why Shariah as the constraint.** It is the most demanding, externally verifiable ethical filter: a company is either on the screened universe or it is not, and the screening criteria (business activity, debt/cash ratios) are published (MSCI Islamic). If an agent can enforce this autonomously, it can enforce any mandate.

**Technology.**

- Python, stdlib-only HTTP (`urllib`) and `subprocess` — no `requests`, no `alpaca-py` SDK.
- Alpaca via CLI (`alpaca doctor`, `data option chain`, `order submit`). **Official Go binary v0.0.14 locally; on the VPS `alpaca` is this repo's `alpaca_cli.py`**, a stdlib-`urllib` client implementing the same command surface against the Alpaca REST API, because the Go binary wasn't available for that environment. Per official FAQ, CLI alone satisfies `MCP or CLI`; we chose CLI for cron/autonomy (ADR-0001).
- Featherless AI (OpenAI-compatible) behind Cloudflare — fixed `User-Agent` bypass for bot-block (discovered against live API 2026-08-29).
- Systemd scheduler (`agent/scheduler.py`) — ET-aware (`zoneinfo America/New_York`), 60-min cadence Mon–Fri 09:30–16:00 ET, immediate run on start if within window. ~63s end-to-end (15 symbols × chain + LLM).
- Flask + gunicorn (`-w 1`) + nginx — **optional evidence surface**; per official FAQ hosting is not required when the agent runs autonomously.
- 49 tests covering fail-closed screening, margin rejection, aggregate collateral, the position cap, DTE/OTM/spread filters, and submitted-vs-filled reconciliation.

**What reached the broker.**

- Testing account `PA3V2Y8L0TCX`: first `SUBMITTED` 2026-08-29T17:57:21Z — `NVDA260902P00222500`, 1 contract, $5.92/share, order `bdccffce-071d`, all gates `PASS`.
- Dedicated account `PA3W2J1H6I3X` (judged): 25 official decisions — **7 SUBMITTED, 8 REJECTED, 6 dry-run, 3 no-candidate, 1 LLM-declined**; gate pass rate 52%. All 8 rejections came from the Risk Gate: MSFT puts at ~$49k collateral = 49% of equity, correctly refused against the 40% cap. **0 manual interventions.**
- Equity **$100,077.83 (+0.078%)**, premium collected **$274.00** broker-confirmed, **$94,500** collateral committed against $100,273 cash, 2 open positions.
- Of 7 submitted orders, **3 contracts actually filled** — the agent was sizing against `cash` while real options buying power was 17× smaller, so four orders never stuck. `/api/metrics` publishes `orders_submitted` beside `orders_open` and names every contract that didn't fill, rather than counting submissions as revenue.

**Limitations & Next Steps.** The Quant Agent and Risk Gate are intentionally rule-based — a deterministic yield-ranker over a learned model, for auditability on a 5-day build (ADRs 0002/0003). The Shariah screen is a hand-scored 15-symbol list, not live ratio screening from filings, and every symbol in it scores ≥80, so the only rejection path that fires in practice is "not in the universe" — that is the path that matters, but the 0–100 banding currently does less work than it appears to. A learned quant, VaR-based risk, and live financial-ratio screening are the next steps. The tradeoff is explicit: the same determinism that caps P&L is what makes compliance provable.

**Result.** +0.078% as of Wed Sep 2, on a book that is fully cash-secured and has never been overridden by a human. The number is small and it is honest — reported from broker positions, with the gap between what the agent submitted and what filled published rather than smoothed. The point is not the number but the property: the same agent that chased premium also provably refused eight trades that violated its mandate, with no human in the loop. That is autonomous trading with a conscience — *Amanah*.

---

**Links:** Application URL `https://amanahtrader.uk/hackathon/` · GitHub (this repo) · Video [LINK]

**Prior work disclosure:** Concept and an earlier prototype at `github.com/SalmonIsFish/Ai_Finance_Syariah` (pre-hackathon, 5 weeks). This repository is from-scratch during the event window (Aug 28–Sep 4, 2026) per organizer confirmation.
