# Build Plan — Alpaca AI Trading Agents Hackathon

**Written:** 2026-08-29, right after kickoff, from a live-relayed Discord Q&A + kickoff stream.
Read this before writing any code in this repo. If you're a fresh session picking this up,
this file plus `README.md` is everything you need to not re-litigate decisions already made.

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
- **Alpaca account:** exactly **one** brand-new paper account, created after kickoff, starting
  balance **exactly $100,000**. No need for a separate "testing" account and "submission"
  account — same account, used continuously. Confirmed directly by an Alpaca mentor: **only
  performance on that fresh account counts toward judging** — no hard "must start Monday" gate,
  just has to be the fresh account. More trading days = better track record, no reason to wait.
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
- Dual Alpaca transport idea: REST directly, and the official `alpaca-mcp-server` via MCP — cover
  the "MCP or CLI" requirement with the MCP path since that's proven achievable.
- Config-via-`.env` pattern (`os.getenv`), never hardcoded secrets.
- Cron-based scheduling is a solved problem in the old repo (it already cron'd a watchlist scan)
  — proves the pattern, re-implement fresh here rather than treating scheduling as a new risk.
- Fail-closed-on-unknown philosophy for the compliance screen.

## Rebuild scope — what's in, what's cut

**In (build this):**
- Alpaca REST adapter, paper-only, hardcoded paper host.
- MCP transport wired for at least the execution step.
- One Level 1 option structure only (pick one — cash-secured put is simplest to reason about).
- Simplified Shariah screen: a small curated compliant-symbol list, not live SEC EDGAR scraping.
- Automated risk caps (orders/day, position size, daily loss).
- A `/explain`-style reasoning trace endpoint or log — this is the evidence trail that stands in
  for a human watching the decision happen.
- Scheduled/autonomous trigger (cron once the core loop is proven — don't block the first trade
  on this).
- Minimal hosted status page for the Application URL requirement.

**Cut (do not attempt this week):**
- Backup/restore tooling, audit-export CLI, cutover pre-flight — production hardening, not judged.
- News room, portfolio-metrics dashboard, Sharpe/Sortino panels — nice-to-have, not core.
- Moomoo legacy path — dead weight, Alpaca only.
- Multi-account resilience, anything from the old repo's "Known limitations" production-scale
  concerns.

## Rough sequence

1. Alpaca REST adapter + account wiring against the fresh $100k account.
2. MCP transport for execution.
3. One option structure, simplified Shariah gate, risk caps — get one real trade placed on the
   fresh account as early as possible (no hard start-date gate, every day counts).
4. Wire actual cron scheduling once the manual-trigger version works.
5. Trade regularly through the week; keep the reasoning-trace log growing.
6. Minimal hosted status page live with an Application URL.
7. Freeze broker-facing code a day or two before the deadline; finish video/slides/cover
   image/one-page write-up.
8. Submit early — don't wait for Sep 4, 15:00 UTC.

## Open questions (not yet answered — ask if there's another Q&A window)

- Whether there's an end boundary for trading before the deadline, or it runs right up to
  submission.
- Whether the "either MCP or CLI" leniency holds if only one transport is demoed on video.
