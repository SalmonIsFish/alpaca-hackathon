# Amanah Trader — One-Page Write-up (DRAFT)

> **Status:** Skeleton — fill [BRACKETS] after Thu Sep 3 EOD snapshot (official FAQ). Required submission artifact. Keep to one page when rendered (PDF).
> Official FAQ: `docs.google.com/document/d/13XWsMvW3mFm26xGlBLvdzzJ_eZQ33T4ZrP-vd9eat50` — P&L measured Mon Aug 31 09:30 ET → Thu Sep 3 EOD; Fri Sep 4 reflects assignments only; hosting not required if agent runs autonomously; backtests/simulated shocks allowed as additional evidence.

---

## Amanah Trader: Autonomous AI Trading with Ethical Constraints

**Problem.** Most AI trading agents optimize only for P&L. In real markets, constraints matter — a trader who must refuse a profitable trade because it violates ethics, religious principles, or risk policy is not failing, they are governing. Yet current agents have no auditable way to prove they would refuse.

**Solution.** A three-layer autonomous agent that *must* pass deterministic compliance before any order reaches the broker:

1. **Reasoning** — Quant Agent ranks, Proposer proposes. The deterministic Ranker (`candidates.py:rank_candidates`) filters live Alpaca chains (1–7 DTE, 2–7% OTM, spread ≤12%) and scores by premium yield vs distance to target OTM (4.2%); the top 5 form the Shortlist. Featherless `Qwen/Qwen3.8-27B` (Proposer) then selects one index and writes a 1–3 sentence rationale — it never invents strikes, premiums, or greeks, those are code-verified; on `LLM_INVALID_RESPONSE` we fall back to rank 0 deterministically (ADR-0002).

2. **Compliance** — Gates decide. Three fail-closed Gates run deterministically, no LLM override:
   - *Shariah Screen* — MSCI Islamic 0–100 confidence scoring against a 12-symbol curated universe + 688-symbol Malaysian Shariah databank reference. `PASS` only if ≥70%; `REVIEW`/`FAIL` both block (see `CONTEXT.md`).
   - *Structure Gate* — cash-secured only (`cash_required = strike × 100 × contracts`), no margin, DTE/OTM/spread bands enforced.
   - *Risk Gate* — `MAX_POSITION_PCT=40`, `MAX_ORDERS_PER_DAY=3`, no leverage. Unlike a human-checked system, the agent cannot be talked into an oversized trade.

3. **Execution** — Broker acts. Only `PASS/PASS/PASS` reaches `alpaca order submit` (Python stdlib `urllib` + Alpaca CLI). Every decision — including rejections and LLM failures — is appended to `logs/decisions.jsonl` with full evidence (candidate, gates, rationale, order ID).

**Why Shariah as the constraint.** It is the most demanding, externally verifiable ethical filter: a company is either on the screened universe or it is not, and the screening criteria (business activity, debt/cash ratios) are published (MSCI Islamic). If an agent can enforce this autonomously, it can enforce any mandate. That is the contest's creativity criterion.

**Technology.**

- Python, stdlib-only HTTP (`urllib`) and `subprocess` — no `requests`, no `alpaca-py` SDK, for minimal dependency surface.
- Alpaca via CLI (`alpaca doctor`, `data option chain`, `order submit` — Go binary locally, Python `alpaca_cli.py` on VPS) — per official FAQ, CLI alone satisfies `MCP or CLI`; we chose CLI for cron/autonomy (ADR-0001).
- Featherless AI (OpenAI-compatible) behind Cloudflare — fixed `User-Agent` bypass for bot-block (discovered against live API 2026-08-29).
- Systemd scheduler (`agent/scheduler.py`) — ET-aware (`zoneinfo America/New_York`), 60-min cadence Mon–Fri 09:30–16:00 ET, immediate run on start if within window. Takes ~63s end-to-end (12 symbols × chain + LLM).
- Flask + gunicorn (`-w 1`) + nginx on VPS polling Alpaca every 60s — **optional evidence surface only**; per official FAQ, hosting is *not required* if agent runs autonomously — GitHub + `logs/decisions.jsonl` is sufficient, this is a bonus live view.

**What reached the broker.**

- Testing account `PA3V2Y8L0TCX`: first `SUBMITTED` at [TIMESTAMP] — `[SYMBOL]` `[STRIKE]`put, `[CONTRACTS]`c, premium `$[PREMIUM]`/share, `order_id [ID]`, all gates `PASS` (confidence `[SCORE]%`).
- Dedicated account `PA3W2J1H6I3X` (judged P&L): first fill Mon Aug 31 09:30 ET — [TBD]; week result at **Thu Sep 3 EOD snapshot** (official FAQ — Fri Sep 4 reflects assignments only): equity `$[FINAL]`, P&L `[+/-X.XX]%` vs $100,000, `[N]` trades, `[M]` rejections (e.g., AAPL 93.6% position correctly `REJECTED` by Risk Gate), `0` manual interventions.
- Full audit trail: `logs/decisions.jsonl` — `[TOTAL]` decisions, `[SUBMITTED]` submitted, `[REJECTED]` rejected, `[WOULD_SUBMIT]` dry-runs. Optional backtest appendix (FAQ-allowed simulated shocks Flat-market) included under `docs/backtest/` as additional guardrail evidence, not scored P&L.

**Limitations & Next Steps.** Quant Agent and Risk Gate are intentionally rule-based. We kept a deterministic yield-ranker (premium yield vs OTM vs spread, 40% cap, 3/day) for auditability over a 5-day build; a learned quant and VaR-based risk would be Next Steps with a full backtest harness (ADRs 0002/0003). The tradeoff is explicit — the same determinism that caps P&L is what makes compliance provable.

**Result.** [INSERT FINAL P&L AND ONE-SENTENCE INTERPRETATION — e.g., "+1.2% in 4 sessions, 3 cash-secured puts, 1 gate rejection, fully autonomous, Thu EOD"]. The point is not the number but the property: the same agent that chased premium also provably refused a trade that violated its mandate, without a human in the loop. That is autonomous trading with a conscience — *Amanah*.

---

**Links:** Application URL `https://amanahtrader.uk/hackathon/` · GitHub (this repo) · Video [LINK]

**Prior work disclosure:** Concept and an earlier prototype at `github.com/SalmonIsFish/Ai_Finance_Syariah` (pre-hackathon, 5 weeks). This repository is from-scratch during the event window (Aug 28–Sep 4, 2026) per organizer confirmation.
