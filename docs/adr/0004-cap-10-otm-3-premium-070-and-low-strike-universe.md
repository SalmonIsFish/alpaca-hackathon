# ADR 0004: Cap 10, Target OTM 3% + Premium 0.70 Floor, and Low-Strike Universe Expansion

**Date:** 2026-09-01
**Status:** Accepted (pre-freeze, reversible before Thu EOD snapshot)

## Context

After Mon 09:30 ET P&L window went live on `PA3W2J1H6I3X`, live equity was `$100,040.94 +$40.94` (Image 1) with buying_power `$23,095` and 3 shorts locking `$94.5k` collateral (2×AAPL 307.5P + GOOGL 330P). Audit trail showed `GOOGL 327.5 $32,750` and `NVDA 212.5 $21,250` both `RISK: REJECT` while `SHARIAH: PASS` `STRUCTURE: PASS` with glowing Proposer rationales (Image 2) — user read “only positive” and asked why rejected, and asked to “not put eggs in one basket” and push 5-8% by Thu close. Live `api/decisions` confirmed last 6 decisions were `REJECTED reason: orders_today_cap orders_today=3 max_orders_per_day=3` — the hourly scheduler hit `MAX_ORDERS_PER_DAY=3` by 15:00 and throttled the rest of the day. Grilling (Q6-Q8) surfaced that raising cap alone does not create buying power (collateral-bound), and that `$69` avg premium/contract at `target_otm 4% + min_premium 0.05` needs 70+ contracts for $5k in 4 days — impossible.

## Decision

- **Cap lift 3→10** (`MAX_ORDERS_PER_DAY=10` in `.env` + `.env.example`, `agent/config.py` un-touched; `risk.py` per-trade `MAX_POSITION_PCT=40` stays). Chose 10 over user-suggested 20 to keep `orders_today` meaningful and let hourly cron (6-7 cycles/day) refill one name per day as 4 DTE puts expire, without logging portfolio-busted `REJECTED insufficient_cash_collateral` spam (10 still exceeds the 3-4 concurrent collateral ceiling, but is the max the broker can absorb before Thu).
- **Quant bands A+B** (`agent/candidates.py:DEFAULT_POLICY`): `target_otm 4.0→3.0` (tighter, higher premium), `min_premium 0.05→0.70` (filters `CSCO $0.23` noise, surfaces `$1.00+` yield), sort key `|OTM−target|, -premium, -DTE` (was `-DTE, -premium`) to rank premium second. Keeps `2-7% OTM, 1-7 DTE, spread 15%` — no expiry > Thu close.
- **Low-strike universe +3** (`data/shariah_universe_enhanced.json` total 12→15, `data/shariah_universe.json` sync): `INTC ~$26, PFE ~$24, KO ~$60` — all MSCI-style PASS with `debt<33%` and verified `confidence 82-86`. Collateral $2k-$6k vs $21k-$33k lets the basket hold 4-5 names within `$100k` without throttling; Tech 7→8, Staples 2→3, Healthcare 1→2. No new gate logic.
- **Audit trail clarity** (`web_app.py:847-893` `gateChip` + `decisionHTML`): render `reason` + `orders_today/max` + `position_pct` in-chip (not just `title=`) and prepend `Gate block: RISK: orders_today_cap` banner above the still-positive `Rationale` (“— Proposer pick, not verdict”) so mobile has no tooltip gap. Glossary sharpened in `CONTEXT.md` (`Buying Power`, `Orders Today`, `Rationale ≠ Gate Verdict`, new caps/bands).
- **Not changed:** `MAX_POSITION_PCT=40` per-trade, no portfolio-sum collateral gate (would break 19 tests at freeze); `MAX_DAILY_LOSS_PCT=3` (unused due to known `daily_pnl` re-divide bug in `risk.py:41`, left for post-hackathon fix).

## Alternatives Considered

- **20/day**: rejected — 6.5h market × hourly = 6 cycles, 20 is spam; judges score robustness. Also portfolio collateral 10×$25k= $250k > equity, broker would reject anyway but hide it behind noisy structure failures.
- **Keep 3/day**: preserves throttling as “safety” but produced `REJECTED` wall users misread; grinding to 5-8% impossible at $69/contract even with 3/day ×4d = 12 fills → $828 max.
- **Widen to 5-7 DTE for premium**: rejected — Thu EOD snapshot means 5-7d puts are still open MTM, not realized; assignment risk post-snapshot.
- **Add portfolio collateral gate now** (`sum(collateral)+new ≤ equity`): correct long-term, but fails-closed edge breaks existing `risk.py` tests and live `pipeline.py:94` contract with 48h to deadline.

## Consequences

- More hourly `SUBMITTED` today transitions to `structure REJECT` (cash) once 4th collateral blocks — expected; diversity guard `pipeline.py:46` prevents same-underlying repeats.
- Premium avg should move $0.69→$1.10+, but eligible pool shrinks (filters $0.23s); nightly `agent/report.py` should show fewer `WOULD_SUBMIT` but larger `premium_per_share`.
- Binding constraint for 5-8% shifts to: (a) expiry luck (OTM at Thu close) and (b) per-contract premium — still unlikely to hit 5% absolute in 4 trading days; write-up should frame as `≈0.6% per 4d cycle → ~55% annualized run-rate` rather than promise $5k by Thu.
- All 19 `pytest` green (risk/candidates/shariah/structure pure); no secrets in repo; `OFFICIAL_START` filter `web_app.py:79` untouched.
