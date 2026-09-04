# Amanah Trader — One-Page Write-up

> P&L window Mon Aug 31 09:30 ET → Thu Sep 3 close. All figures broker-confirmed via `position_list`, not derived from submitted orders.

**Problem.** Most AI trading agents optimise only for P&L. Real mandates don't work that way — a trader who must refuse a profitable trade because it violates ethics, religion, or policy is not failing, they are governing. No current agent can *prove* it would refuse.

**Solution.** A deterministic ranker filters live Alpaca option chains (1–7 DTE, 2–7% OTM, bid ≥ $0.70, spread ≤ 15% of mid); the top 10 form a shortlist. Featherless `Qwen/Qwen3.8-27B` then selects **one index** and writes a rationale — it cannot invent a strike, premium, expiry, or symbol. On malformed output or refusal the pipeline falls back to rank 0 and logs that it did. Then six pure, fail-closed gates decide, with no LLM override:

| Gate | Rule |
|---|---|
| **Shariah** | Curated 15-symbol universe, MSCI Islamic scoring. Unlisted ⇒ FAIL, always. |
| **Structure** | Cash-secured only, checked net of collateral already committed to open puts. |
| **Gharar** | Two-sided live price, bounded spread/expiry/IV, delivery capacity assured. |
| **Maysir** | A funded commitment to acquire a screened asset below market — not a wager. |
| **Riba** | The *account*: positive cash, no broker credit, no borrowed stock, nothing accruing interest. |
| **Risk** | 40% position cap, 10 orders/day, 3% daily-loss cap. |

Only a unanimous `PASS` reaches `alpaca order submit`. Every decision — rejections and LLM failures included — appends to `logs/decisions.jsonl` with full evidence.

**Why Shariah.** It is demanding, externally verifiable, and rests on three prohibitions — *riba*, *gharar*, *maysir* — that map onto machine-checkable conditions. An agent that enforces these can enforce any mandate.

**Results** (`PA3W2J1H6I3X`). Equity **$100,418.59 (+0.42%)**; premium collected **$817.00**; $98,050 collateral against $101,056 cash; 4 open positions (NVDA, AAPL, 2× INTC puts). 42 official decisions — 11 submitted, 8 refused, **0 manual interventions**. The refusals: 3 × `position_size_cap` (MSFT at 49% of equity against the 40% cap) and 5 × `orders_today_cap`.

Wednesday's session shows the full lifecycle unattended: at 09:35 ET a cron job bought-to-close three expiring legs (2× AAPL put, 1× GOOGL put), freeing $94,500 in collateral; by 09:37 ET the same pipeline had already opened a new NVDA put with that freed cash — no gap where a human needed to step in. Of the 11 orders submitted since Monday, 4 remain open; the rest either never filled or were fully filled and already closed by that script. `/api/metrics` publishes `orders_submitted` beside `orders_open` and names every non-open contract in `unfilled_or_closed`, rather than counting submissions as revenue.

**Adversarial evidence.** `docs/backtest/gate-stress-report.md` — 20 deterministic scenarios run against the real gate functions, byte-identical on every run. **19 refusals, 1 allowed**: the richest premium on the board on an unlisted symbol, a naked put, a one-sided quote, a −20% overnight gap, an overdrawn account, and the exact 2×-levered book that existed in production on 2026-09-02.

**The juristic position.** Options are named in the gharar and maysir literature as *prohibited*, and AAOIFI generally prohibits conventional options. `docs/shariah/position-cash-secured-puts.md` states that against itself, argues the objections turn on *naked* positions and *pure* speculation, and maps every narrowing condition to the gate enforcing it. It is an engineering rationale, **not a fatwa**, and says so.

**Technology.** Python standard library only (`urllib`, `subprocess`) — no SDK. Alpaca CLI transport (official Go binary locally; this repo's `alpaca_cli.py` on the VPS) drives every account, options-chain, and order call against the paper account (`PA3W2J1H6I3X`, options level 3). `agent/scheduler.py` runs under systemd, hourly, 09:30–16:00 ET with `zoneinfo`; a separate cron job runs the same CLI at open to buy-to-close anything expiring, so both legs of the position lifecycle — open and close — are unattended. 83 tests. If no Alpaca executable is reachable the agent halts rather than assume an account.

**Result.** +0.42%, on a book that is fully cash-secured and has never been overridden by a human. The number is small and it is honest. The point is not the number but the property: the same agent that chased premium refused three trades for breaching its size mandate and throttled five more against its own limit, with nobody in the loop. That is autonomous trading with a conscience — *Amanah*.

---

**Links:** `https://amanahtrader.uk/hackathon/` · GitHub (this repo)

**Prior work disclosure:** Concept and an earlier prototype at `github.com/SalmonIsFish/Ai_Finance_Syariah` (pre-hackathon, 5 weeks). This repository is from-scratch during the event window (Aug 28–Sep 4, 2026) per organizer confirmation.
