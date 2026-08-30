# Amanah Trader

An autonomous options-trading agent that enforces Shariah and risk constraints deterministically before any order reaches Alpaca's paper broker.

## Language

### Core System

**Amanah Trader**:
The entire autonomous system — Ranker → Proposer → Gates → Execution — that scans, reasons, validates, and trades without human approval after deployment.
_Avoid_: Bot, AI trader (generic), autonomous workflow

**Evidence Log**:
The append-only `logs/decisions.jsonl` that records every pipeline run — candidate, Proposer rationale, Gate results, and outcome (`SUBMITTED` / `REJECTED` / `WOULD_SUBMIT` / `LLM_INVALID_RESPONSE`).
_Avoid_: Audit trail (overloaded), decision log (ambiguous)

**Outcome**:
The final status of a pipeline run written to the Evidence Log. Only `PASS/PASS/PASS` across all Gates yields `SUBMITTED`.
_Avoid_: Result, execution status

### Candidates & Ranking

**Candidate**:
A single cash-secured put opportunity derived from a live Alpaca option chain, carrying OCC symbol, strike, expiration, DTE, OTM%, bid/ask, and cash_required.
_Avoid_: Contract, opportunity, trade idea

**Ranker**:
The deterministic pure function `candidates.py:rank_candidates` that filters chains by DTE, OTM band, live bid and spread, then sorts eligible Candidates by distance to target OTM and premium yield.
_Avoid_: Quant agent (when meaning the ranker alone), screener

**Quant Agent**:
The Ranker viewed as the agent responsible for yield optimization — it scores eligible Candidates by premium yield vs assignment risk under the current DTE/OTM/spread bands. Rule-based, no learned model, fully auditable.
_Avoid_: ML quant, AI quant, prediction engine

**Shortlist**:
The top 5 eligible Candidates passed to the Proposer. Empty shortlist yields `NO_CANDIDATES`.
_Avoid_: Top candidates, watchlist

### Reasoning

**Proposer**:
The Featherless LLM (`Qwen/Qwen3.8-27B`) that selects one index from the Shortlist and writes a 1–3 sentence rationale. It never invents prices or strikes and never decides compliance.
_Avoid_: LLM agent, reasoning agent, AI decision-maker

**Rationale**:
The Proposer's natural-language justification for the selected Candidate, logged verbatim in the Evidence Log.
_Avoid_: Explanation, thesis

### Compliance

**Gate**:
A deterministic, fail-closed validator. All Gates must return `PASS` for execution; any other status blocks the order and the LLM cannot override.
_Avoid_: Agent, check, filter, compliance agent

**Shariah Screen**:
The Gate that validates a Candidate's underlying against a 12-symbol curated universe plus a 688-symbol Malaysian Shariah databank reference, using MSCI Islamic 0–100 confidence scoring. `PASS` only if ≥70%; `REVIEW` (50–69) and `FAIL` both block as `REJECTED`.
_Avoid_: Ethical filter, compliance check, halal check, ethical mandate

**Structure Gate**:
The Gate that enforces option-structure constraints: cash-secured put only (`cash_required = strike × 100 × contracts ≤ cash`), no margin, 1–7 DTE, 2–7% OTM, spread ≤12% of mid.
_Avoid_: Structure check, options validation

**Risk Gate**:
The Gate that enforces account-level caps: `MAX_POSITION_PCT=40`, `MAX_ORDERS_PER_DAY=3`, `MAX_DAILY_LOSS_PCT`. It computes `position_pct = cash_required / equity`.
_Avoid_: Risk agent, risk manager, risk check

### Execution

**Cash-Secured Put**:
The only tradable structure: selling a put where cash equal to `strike × 100 × contracts` is held to secure assignment. No multi-leg spreads, no naked exposure.
_Avoid_: CSP (in prose), short put (ambiguous)

**Cash Required**:
`strike × 100 × contracts` for the selected Candidate — the collateral the Structure Gate verifies against available cash.
_Avoid_: Notional, position value (when meaning collateral)

**Client Order ID**:
`amanah-{hex12}` generated per `SUBMITTED`/`WOULD_SUBMIT` and passed to `alpaca order submit` for idempotency.
_Avoid_: Order ID ( Alpaca's server ID is `order_id`)

### Market & Schedule

**Official Window**:
Monday Aug 31 09:30 ET → Thursday Sep 3 EOD (equity snapshot), per the official Alpaca FAQ (`13XWsMvW3mFm26xGlBLvdzzJ_eZQ33T4ZrP-vd9eat50`). Friday Sep 4 reflects assignments only. The dedicated account `PA3W2J1H6I3X` must not trade before this window.
_Avoid_: Scoring window, judging week (ambiguous), P&L week

**Testing Account**:
`PA3V2Y8L0TCX` — the pre-hackathon paper account used for all development and Milestone 2 live proof. Its P&L never counts.
_Avoid_: Paper account (when meaning testing), dev account

**Dedicated Account**:
`PA3W2J1H6I3X` — the $100,000 paper account whose EOD Thu Sep 3 equity is the scored P&L. No orders before Mon 09:30 ET.
_Avoid_: Official account, competition account, production account
