# Position paper: cash-secured puts under the three prohibitions

**Status: engineering rationale, not a fatwa.** Written by the system's author, who is not a
qualified Shariah scholar. It sets out the argument this codebase implements, the objections to
that argument, and the point past which no amount of code can settle the question. Nothing here
should be relied on as a religious ruling. Actual reliance requires a qualified adviser and
documented approval, which this project does not have.

---

## The problem, stated against ourselves

Islamic commercial law rests on three prohibitions: **riba** (interest), **gharar** (excessive
contractual uncertainty), and **maysir** (gambling). Options are named in the literature on the
second and third, generally as examples of what is *prohibited*, not what is permitted.

The classical gharar objection to derivatives is that they involve selling what one does not
possess and cannot reliably deliver — the same category as the sale of unharvested crops, fish
still in the sea, or an unborn animal. The maysir objection is that derivative positions
frequently produce a pure zero-sum transfer: one party's gain is definitionally the other's
loss, with no labour, goods, or shared enterprise risk on either side.

**AAOIFI Shariah Standards generally prohibit conventional options outright.** That is the
mainstream contemporary position and this document does not dispute it. A project that claimed
Shariah compliance while quietly routing around AAOIFI would be worth less than one that says
plainly where it stands.

So the honest framing is not *"cash-secured puts are permissible."* It is: **which specific
features of a position drive the classical objections, and can a system enforce their absence
mechanically?**

## Where the objections actually bite

Read the prohibitions closely and both carry qualifiers that are doing real work.

The maysir objection is to ***pure* speculation** and to ***naked*** positions. Islamic law does
not prohibit risk — it prohibits wagering. The distinction it draws is between *maysir* and
***mukhatarah***, lawful commercial risk. Ordinary trade and investment are permitted precisely
because they involve effort, real value creation, and genuine exchange. A merchant who buys
inventory bears substantial risk and is doing nothing wrong.

The gharar objection is to ***excessive*** uncertainty. Jurisprudence explicitly tolerates
minor, unavoidable uncertainty — standard variation in agricultural yield, for instance — and
prohibits ambiguity substantial enough to undermine the fairness of the contract. Again the
line is not risk; it is whether a party can meaningfully evaluate what they are agreeing to.

This matters because a **naked** put and a **fully cash-secured** put are not the same act, even
though they are the same instrument.

| | Naked put | Cash-secured put, as constrained here |
|---|---|---|
| Delivery capacity | None. Cannot buy the shares. | Full purchase price segregated and unencumbered. |
| If assigned | Forced liquidation or margin loan | Acquires the shares, as intended |
| Subject matter | A price movement | An operating business that passed a business-activity screen |
| Strike | Anywhere | Strictly below market — an acquisition discount |
| Economic substance | Wager on direction | Compensation for a binding commitment to buy |
| Leverage | Yes | None. Cash account discipline is separately enforced. |

The strongest available argument is that a fully collateralised short put resembles a binding
promise to purchase at a known price — closer to ***wa'd*** (a unilateral promise) or to
***'urbun*** (a down-payment sale, which several schools permit) than to a wager. The premium is
consideration for making the commitment irrevocable, and the seller genuinely wants the asset at
that price.

**Where that argument is weak,** and this must be said: the premium is received unconditionally
whether or not the sale ever occurs, which is not a feature of a straightforward *wa'd*; the
contract is exchange-traded and typically closed out rather than exercised; and the analogy to
*'urbun* inverts who pays whom. These are real objections. This document does not claim to have
answered them.

## What the code enforces

The argument above is worth nothing as prose. What makes it a property of the system rather than
a claim about it is that each narrowing condition is a deterministic gate that fails closed.

| Condition | Enforced by | Failure mode it prevents |
|---|---|---|
| Underlying is a permissible operating business | `gates/shariah_enhanced.py` | Writing puts on something one could never accept delivery of |
| Full purchase price held, net of all other obligations | `gates/structure.py`, `gates/maysir.py` | A nominally "secured" put actually financed by the rest of the book |
| Price discoverable from a live two-sided market | `gates/gharar.py` | Contracting at a price nobody is making |
| Spread, expiry and implied volatility bounded | `gates/gharar.py` | Terms too ambiguous to evaluate |
| Delivery capacity assured | `gates/gharar.py` | The classical "selling what you cannot deliver" |
| Strike strictly below market | `gates/maysir.py` | Accepted-assignment financing dressed as a purchase |
| Expiry beyond same-session | `gates/maysir.py` | Intraday price wagering |
| No margin, no borrowed stock, no interest-bearing holdings | `gates/riba.py` | Interest entering through the account rather than the trade |

A concrete instance of the gharar gate earning its place: the free-tier options feed returns
contracts quoted `"bp": 0, "bs": 0, "bx": "?"` — no bid, no size, unknown exchange — and outside
market hours entire underlyings return `ask: 0`. The candidate ranker tolerated a missing ask.
Transacting against a one-sided quote is contracting at a price that does not exist, which is
price ambiguity in the most literal sense. That gate was written because of quotes actually
observed in this account's data, not as an abstraction.

## What this does not establish

1. **It is not a ruling.** No qualified scholar has reviewed this system.
2. **It does not overcome AAOIFI.** The mainstream contemporary standard prohibits conventional
   options. The position here is that specific enforced conditions narrow the classical
   objections — not that the prohibition has been met and defeated.
3. **The business-activity screen is a curated list**, hand-scored against MSCI Islamic
   methodology, not live financial-ratio screening from filings.
4. **Exchange-traded options carry structural features** — clearing-house intermediation,
   standardisation, the practice of closing rather than exercising — that this analysis does not
   address at all.
5. **No income purification or zakat calculation** is implemented. A real Islamic fund would
   cleanse incidental non-compliant income and compute a zakat liability. Neither exists here.

## Why build it this way regardless

The project's claim was never that it had solved Islamic finance. It is that **a mandate can be
made machine-enforceable and auditable** — that an autonomous agent can be built which cannot be
argued, tempted, or drifted into violating its constraints, and can produce evidence of every
refusal.

The three prohibitions are a demanding test case precisely *because* they are contested and
externally specified. An agent that enforces them mechanically, states honestly where its
juristic ground is uncertain, and logs every refusal with the rule that produced it, demonstrates
the property in question. A system that quietly asserted compliance would demonstrate the
opposite.

---

**Primary sources referenced:** Qur'an 4:29 (consumption of wealth wrongfully) and 5:90 (maysir
alongside intoxicants); the hadith literature on the sale of fish in the sea and unborn
livestock; AAOIFI Shariah Standards on options and financial derivatives; Securities Commission
Malaysia / Shariah Advisory Council screening methodology; MSCI Islamic Index methodology.
