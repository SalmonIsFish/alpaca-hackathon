# Build Plan — Alpaca AI Trading Agents Hackathon

**Written:** 2026-08-29, right after kickoff, from a live-relayed Discord Q&A + kickoff stream.
Read this before writing any code in this repo. If you're a fresh session picking this up,
this file plus `README.md` is everything you need to not re-litigate decisions already made.

## Account IDs (confirmed 2026-08-29 — do not mix these up)

- **Dedicated submission account: `PA3W2J1H6I3X`** ("Alpaca Hackathon", $100,000.00 starting
  balance). **Off-limits — no orders — until Monday Aug 31, 9:30am ET.** This is the only
  account whose P&L counts toward judging.
- **Testing account: `PA3V2Y8L0TCX`** ("Paper Trading", the pre-hackathon `0TCX` account
  referenced throughout the old repo's `CLAUDE.md`). Use this for all development/testing this
  week — `alpaca profile login --name testing` should point here. Its existing history (the old
  CVX position, etc.) doesn't matter; it's never used for judging.

## Current status (updated 2026-08-31 14:06 UTC, post-Monday open — read this first if resuming)

**Mon 09:30 ET P&L window LIVE on `PA3W2J1H6I3X`.** First judged fills: `AAPL260904P00307500` 307.5P 4 DTE 2.8% OTM `1ct` `filled 0.70` at `2026-08-31T14:05:17Z` (order `97376869-4e42`) + duplicate `14:06:41` (2ct total, `61.5k` collateral), equity `99982` (`-0.02%`), cash `100069`, `PA3W2J1H6I3X` `buying_power 277k`. Scheduler + app `active` `https://amanahtrader.uk/hackathon/` shows `PA3W2J1H6I3X` only after `web_app.py:79` `OFFICIAL_START` filter.

**3 fixes shipped at open (commit `bb32f31`):**
1. `alpaca_cli.py:183` paginate 4 pages `v1beta1` - page 0 is all `2026-08-31` DTE 0, need p1-2 for `1-7 DTE` (was `NO_CANDIDATES` for 12 symbols)
2. `agent/candidates.py:174` filter `type==put` only + `alpaca_cli.py:298` `type->order_type` + `profile` pop (was calls selected, `TypeError: profile`)
3. `agent/gates/*` still 19/19, `data/shariah_universe.json` 12 symbols, `web_app.py:79` audit hides pre-`13:30Z` testing rows

**Next session plan (after 16:00 ET = 04:00 +08 Tue):** cap `10` candidates per `agent/pipeline.py:37` (user request, keep even though prompt risk), add diversity guard (skip same `underlying` if already `SUBMITTED` today), add `NO_TRADE_LLM_DECLINED` fallback to top-ranked, and nightly `agent/report.py` (see below). Do NOT change `MAX_POSITION_PCT 40` or gates.

**Milestone 1 achieved and committed (2026-08-29).** The full pipeline runs end-to-end against real data on
the testing account: `python -m agent.pipeline --dry-run` → scans the whole curated universe →
LLM (Featherless) proposes a candidate with a real rationale → all three gates evaluate it →
logs to `logs/decisions.jsonl`. Last real run: NVDA 210 put, 1 contract, $21,000 (21% of
equity), all gates PASS, `WOULD_SUBMIT`.

**What's built and verified against real (not guessed) API output:** `agent/config.py`,
`agent/cli.py` (Alpaca CLI subprocess wrapper — `doctor`/`account_get`/`position_list` all
confirmed), `agent/candidates.py` (option-chain parsing fixed twice against real output — see
git log for the OCC-symbol-parsing and sizing-policy fixes), `agent/gates/{shariah,structure,
risk}.py` (19/19 unit tests passing), `agent/evidence.py`, `agent/llm.py` (Featherless call
fixed — see the Cloudflare note below), `agent/pipeline.py`. `data/shariah_universe.json` has
12 curated large-cap symbols with one-line rationales.

**Two real bugs found and fixed this session, worth knowing about if something looks broken:**
1. **Featherless returns HTTP 403 / Cloudflare error 1010 with Python's default `urllib`
   User-Agent** — nothing to do with the API key. Fixed in `llm.py` by setting a real
   User-Agent header. If any *other* HTTP client gets added later (not just `urllib`), check
   its default User-Agent isn't bot-blocked the same way.
2. **Position sizing vs. risk cap conflict**: the curated universe is $190-500+/share, so 1
   contract of a cash-secured put structurally costs 20-35% of a $100k account. Sizing now
   targets 35% of equity (usually lands on exactly 1 contract); `MAX_POSITION_PCT=40` is the
   real backstop (confirmed it still rejects genuinely oversized trades, e.g. a 3-contract
   93.6%-of-equity case). Don't casually tighten `MAX_POSITION_PCT` back toward 5-10% without
   re-checking against real strike prices first — it will silently make every trade impossible
   again, not safer.

**Alpaca CLI is installed** at `C:\Users\G2\bin\alpaca.exe` (v0.0.14, Windows amd64 release
binary — no Go/Homebrew needed) and on PATH. The `testing` profile is authenticated
(`alpaca profile login --name testing`, OAuth, pointed at `PA3V2Y8L0TCX`). Featherless is
configured (`FEATHERLESS_MODEL=Qwen/Qwen3.8-27B` — chosen for cost/quality balance on a small,
structured proposal task; see git log for the reasoning if reconsidering).

**Not done yet — this is where to resume (post-close, Tue 04:00+08):**
- **Cap 10**: raise `agent/pipeline.py:37` `cap 5 -> 10` per user, keep `agent/candidates.py:22` `OTM/spread` as is (quant: 10 shortlist = `~6k` chars > `15s` LLM timeout - compress prompt, test `Qwen/Qwen3.8-27B` with cap 10 dry-runs). Add diversity: skip `underlying` already `SUBMITTED` today (max `3` `MAX_ORDERS_PER_DAY`).
- **Nightly report**: new `agent/report.py` parsing `logs/decisions.jsonl` -> `stats` `NO_CANDIDATES`/`LLM_INVALID`/`rejected_*` + `P&L` vs premium, so quant/LLM know what to tune without guessing.
- **Fallback**: `agent/pipeline.py:52` if `proposal.no_trade` then fallback to `shortlist[0]` (like `LLM_INVALID` fallback) - avoids `13:51:23` stall.
- **Milestone 2 was done** `2026-08-30` on `PA3V2Y8L0TCX` (`bdccffce` NVDA) and now `2026-08-31` on `PA3W2J1H6I3X` (`97376869` AAPL). Scheduler wiring done `hackathon-scheduler.service` ET-aware, but re-test after cap change.
- Hosted status page live `https://amanahtrader.uk/hackathon/` (filter `OFFICIAL_START` done), video/slides/cover image, one-page write-up — still at skeleton.

## Why this repo exists (read this first)

The actual prototype for this idea — a Shariah-compliant Alpaca paper-trading agent with a
deterministic compliance gate chain — was already built at
<https://github.com/SalmonIsFish/Ai_Finance_Syariah>, over ~5 weeks before this hackathon's
kickoff (commits from 2026-07-21 to 2026-08-26). It works: two real fills happened against the
live paper broker, 42 tests pass, it's deployed at `amanahtrader.uk`.

**None of that code can be used here.** Confirmed independently three separate times during
kickoff (a DM to lablab support, a live Discord Q&A answer to someone in an almost identical
situation, and a follow-up bot Q&A): every file in the submission repo must be authored during
the event window (Aug 28 – Sep 4, 2026). Prior work can be *disclosed* (see `README.md`'s
disclosure section) but not *included*. Repo creation/commit dates may be checked by judges —
this repo's first commit is 2026-08-29 00:29 (local/MYT), safely after the Aug 28 11:00 PM MYT
kickoff.

**So: reference the old repo's ideas and docs freely. Never copy its files.** Read `CLAUDE.md`
there as a spec, then write fresh code here from that understanding. If you catch yourself about
to `cp` or paste a block from that repo, stop.

## Confirmed rules (as of kickoff, 2026-08-28/29 — this is the source of truth, not older docs)

- **Repo:** new, empty-at-start, only in-window commits. Can stay **private** until judging,
  must be **public** during the judging period.
- **Alpaca account — corrected 2026-08-29, from Erika Zapanta's (Alpaca) official Google Doc,
  read directly rather than relayed through Discord:** create the dedicated $100k paper account
  now, but **do not trade on it yet**. Use a **separate testing account** for all development
  this weekend. **The dedicated account's trading must begin Monday, August 31, 9:30 a.m. ET** —
  the doc says so explicitly: "Please do not use your testing account for the official P&L
  measurement." An earlier Discord answer implied no hard Monday gate — that was wrong, or at
  least imprecise; trust this doc over that chat answer.
- **Official P&L measurement window: Mon Aug 31 9:30am ET → Fri Sep 4 9:30am ET.** Scored as a
  **snapshot of total account equity** (not cash) at the official hackathon close — so an open
  position at the snapshot moment counts same as a closed one.
- **Judging is not P&L-only.** Two factors: (1) P&L during the official window, judged on total
  equity; (2) "the creativity, autonomy, and robustness of the agent trading workflow." Quoted
  directly: "P&L will be an important factor, but winners will not be selected based on P&L
  alone."
- **UI explicitly not required**, confirmed in writing: "We are primarily evaluating the
  autonomous agent workflow and its trading performance." Reinforces the autonomous-mode pivot
  below — a hosted status page only needs to satisfy the separate Application URL field, not be
  a polished dashboard.
- **MCP vs CLI:** the written requirement is "MCP server **or** CLI" — either satisfies it. One
  Discord answer said "good to incorporate both if possible" (soft, not a hard requirement).
- **Options trading is mandatory** in every strategy, regardless of track.
- **Hosting/Application URL is required even for a fully autonomous, no-UI agent** — "no UI
  needed" was confirmed, but a working Application URL for the demo is still mandatory.
- **One-page write-up required**, separate from video/slides: AI logic, risk gates, Alpaca
  infrastructure implementation.
- **Demo platform text in the Rule Book says Streamlit/Replit/Vercel**, but the actual submission
  form's Application URL field is free-text with no platform restriction — any working public URL
  qualifies (a self-managed VPS is fine; this is how the old project was hosted too).
- **Judging = four criteria:** P&L Performance, Technology Implementation, Creativity &
  Originality, Presentation & Execution.
- **Local/open models are fine** (Ollama etc. explicitly allowed, no model-size restriction) —
  moot for us either way, since the compliance gates are deterministic by design, not LLM-driven.
- **Deadline:** Sep 4, 2026, 15:00 UTC. Manual fallback exists only with prior organizer approval
  — don't plan around it.
- **Featherless AI:** $25 credit via code `ALPACA26`, one redemption per participant, keep the
  code out of anything public (never commit it).
- **New technical resource, not previously listed:** `github.com/alpacahq/alpaca-skills` — check
  before building, may already cover patterns we'd otherwise write from scratch.
- **Market data:** free tier gives an indicative options feed; Algo Trader Plus (paid) gives the
  real OPRA feed. Not automatically granted — participants choose/pay for it themselves if
  wanted. Free tier is fine to start with.

## Strategy pivot: fully autonomous, not human-approval-gated

The old repo's core safety design required a human to type `EXECUTE PAPER` before any broker
submission. **This build drops that step.** Reasoning:

1. Core requirement #1 is literally "autonomous AI trading agents" — a human-confirmation step is
   the opposite of that.
2. Practical: US market open is ~10PM local time for the builder. A human-in-the-loop design
   means being awake at 10PM every trading day for a week. A scheduled/unattended agent doesn't.
3. An Alpaca/lablab answer during kickoff Q&A said the workflow doesn't have to be manually
   confirmed — judging is on the **agentic AI workflow** (the reasoning/decision pipeline), not
   on whether a human clicked something. That makes the reasoning trail *more* important, not
   less, since nobody's watching it happen live.

**What does NOT change:** the deterministic gate chain itself. Shariah gate, option-structure
gate, account Riba gate, and risk limits still run automatically before any order — the agent
just can't be talked into a non-compliant trade, with no human safety net. That's arguably a
stronger pitch for a fully autonomous bot than for a human-approved one.

**Non-negotiable safety valve even in autonomous mode:** hard caps — max orders/day, max position
size, max daily loss — reused as a *concept* from the old repo's risk-limit design (not its code).
Paper money means no real financial risk, but a bug shouldn't be able to spam the account or
produce something embarrassing mid-demo.

## What to reuse as a concept (never as a file)

- The four-stage gate chain shape: Shariah screen → option-structure gate → account Riba gate →
  risk limits, all fail-closed.
- Level 1 option structures: sell covered call / sell cash-secured put only, 1–7 DTE, strike near
  4% OTM (2–7% band), standard 100-share multiplier. No multi-leg spreads.
- **Execution transport decided 2026-08-29, superseding the line this replaced: the Alpaca
  CLI, not MCP.** The official Alpaca Claude Code skills explicitly document MCP as
  interactive/session-bound and recommend the CLI for unattended/cron automation (`alpaca
  doctor`, `alpaca data option chain`, `alpaca order submit`, etc.) — this satisfies "MCP
  server or CLI" and is what's actually implemented in `agent/cli.py`.
- Config-via-`.env` pattern (`os.getenv`), never hardcoded secrets.
- Cron-based scheduling is a solved problem in the old repo (it already cron'd a watchlist scan)
  — proves the pattern, re-implement fresh here rather than treating scheduling as a new risk.
- Fail-closed-on-unknown philosophy for the compliance screen.

## Rebuild scope — what's in, what's cut

**In (build this):**
- Alpaca CLI wrapper, paper-only profile, never touches the dedicated account before Monday.
  ✅ done (`agent/cli.py`).
- Cash-secured put only. ✅ done (`agent/candidates.py`, `agent/gates/structure.py`).
- Simplified Shariah screen: a small curated compliant-symbol list, not live SEC EDGAR scraping.
  ✅ done (`data/shariah_universe.json`, `agent/gates/shariah.py`).
- Automated risk caps (orders/day, position size, daily loss). ✅ done (`agent/gates/risk.py`).
- A reasoning-trace log — this is the evidence trail that stands in for a human watching the
  decision happen. ✅ done (`agent/evidence.py`, `logs/decisions.jsonl`).
- Scheduled/autonomous trigger (cron once the core loop is proven — don't block the first trade
  on this). **Not started** — after Milestone 2.
- Minimal hosted status page for the Application URL requirement. **Not started.**

**Cut (do not attempt this week):**
- Backup/restore tooling, audit-export CLI, cutover pre-flight — production hardening, not judged.
- News room, portfolio-metrics dashboard, Sharpe/Sortino panels — nice-to-have, not core.
- Moomoo legacy path — dead weight, Alpaca only.
- Multi-account resilience, anything from the old repo's "Known limitations" production-scale
  concerns.

## Rough sequence (corrected 2026-08-29 for the real Monday gate)

1. ✅ Dedicated $100k account (`PA3W2J1H6I3X`) and testing account (`PA3V2Y8L0TCX`) both set up.
2. ✅ Alpaca CLI wrapper + account wiring, tested against the **testing** account.
3. ✅ CLI execution transport confirmed working (`order_submit` implemented, not yet called for
   real — that's Milestone 2).
4. ✅ One option structure (cash-secured put), simplified Shariah gate, risk caps — full loop
   proven end-to-end on the testing account (Milestone 1, 2026-08-29).
5. **Next:** Milestone 2 — one real order on the testing account (drop `--dry-run`).
6. Then: wire actual cron scheduling.
7. **Monday Aug 31, 9:30am ET: point execution at the dedicated account and place the first
   trade that counts.** This is the real start line, not kickoff.
8. Trade through Mon–Thu; keep the reasoning-trace log growing — it's evidence for the
   "creativity, autonomy, robustness" half of judging, not just a nice-to-have.
9. Minimal hosted status page live with an Application URL (doesn't need to be a dashboard — UI
   isn't judged).
10. Freeze broker-facing code a day or two before the deadline; finish video/slides/cover
    image/one-page write-up.
11. Submit early — don't wait for Sep 4, 15:00 UTC (= 8:00 AM PDT, confirmed in the doc).

## Open questions (not yet answered — ask if there's another Q&A window)

- Whether there's an end boundary for trading before the deadline, or it runs right up to
  submission.
- Whether the "either MCP or CLI" leniency holds if only one transport is demoed on video.
