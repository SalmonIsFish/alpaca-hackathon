# Agent instructions — read this first, every session

This repo is a from-scratch build for the Alpaca AI Trading Agents Hackathon (lablab.ai,
Aug 28 – Sep 4 2026). **Before writing or changing anything, read `BUILD_PLAN.md` in full** —
its "Current status" section at the top is the live source of truth for what's built, what's
verified against real data, what's broken, and what to do next. This file only orients you
fast; `BUILD_PLAN.md` has the actual detail and reasoning.

## The five things you must not get wrong

1. **Two Alpaca accounts exist. Do not mix them up.**
   - `PA3W2J1H6I3X` ("Alpaca Hackathon", $100,000) — the dedicated submission account.
     **No orders on this account before Monday Aug 31, 9:30am ET.** This is the only account
     whose P&L counts toward judging.
   - `PA3V2Y8L0TCX` ("Paper Trading", the pre-hackathon `0TCX` account) — the testing account.
     Everything you do this week, until Monday, runs against this one
     (`alpaca profile login --name testing` is already authenticated to it).
2. **Never copy code, data, or exact text from `E:\Github2\Ai_Finance_Syariah`.** It's a
   related older project by the same author, kept as read-only design reference. Every file in
   *this* repo must be authored during the event window — confirmed by organizers 3 separate
   times. Read that repo's `CLAUDE.md` for architectural ideas if useful, then write fresh code
   here from understanding, never by copy-paste.
3. **Never handle Alpaca or Featherless credentials.** They live in `.env` (gitignored, never
   committed). If you need something set, tell the user the exact `.env` line to add — don't
   ask them to paste a key into chat, and don't write one into any file yourself.
4. **The compliance gates (`agent/gates/*.py`) are deterministic and must stay that way.** The
   LLM (Featherless, wired in `agent/llm.py`) proposes a candidate from a pre-filtered
   shortlist and writes a rationale; it never decides compliance or risk limits. Don't blur
   this line even if it seems like it would simplify something.
5. **Run `pytest tests/` before trusting any change to `agent/gates/` or `agent/candidates.py`**
   — 19 tests currently pass, covering exactly the edge cases (fail-closed on unlisted symbols,
   margin rejection, position-size cap, DTE/OTM/spread filters) that matter most here.

## Next action, as of 2026-08-29

**Milestone 2**: run `python -m agent.pipeline` (no `--dry-run`) against the testing account —
the first real paper order this rebuilt pipeline places. Nothing is blocking this; it just
hasn't been run yet. After that, cron wiring is next (see `BUILD_PLAN.md`'s sequence section).

## Conventions already established

- Python, stdlib-only HTTP (`urllib`) and `subprocess` — no `requests`, no `alpaca-py` SDK. The
  Alpaca CLI binary (`C:\Users\G2\bin\alpaca.exe`, already on PATH) is the execution transport,
  not MCP — see `BUILD_PLAN.md` for why.
- Tests are plain `pytest`-compatible files under `tests/`, each also runnable standalone with
  a `main()` that prints `PASS: ...` (matches the older sibling project's convention).
- `.env.example` documents every config var with empty values; real values live only in the
  gitignored `.env`.
- Keep changes scoped and simple — this is a solo hackathon build against a hard deadline
  (Sep 4, 2026, 15:00 UTC), not a production system. Don't add abstractions, providers, or
  config for anything not immediately needed.

## Agent skills

### Issue tracker

Issues tracked in GitHub Issues. See `docs/agents/issue-tracker.md`.

### Triage labels

Five canonical labels mapped 1:1 (needs-triage, needs-info, ready-for-agent, ready-for-human, wontfix). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context layout (one `CONTEXT.md` + `docs/adr/` at repo root). See `docs/agents/domain.md`.
