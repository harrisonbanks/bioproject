docs/20260830_v2_FDA_Catalyst_Research.md

# FDA catalyst price-reaction analysis — research synthesis

Bioindustry Intelligence Platform · research note v2 · 2026-08-30 (v2: §6 sources of record decided; §10 product design written)
Purpose: establish the formal name, the evidence base, the thesis, the
event taxonomy, candidate models, decision rules, data sources and the
evaluation protocol for a daily product that forecasts and ranks stock
behaviour around FDA calendar events. This note feeds the product design
document that follows; nothing here is implemented.

Sources are cited inline; peer-reviewed or regulator sources are marked
[A] (academic), [R] (regulator), [P] (practitioner/aggregator, lower
evidential weight, useful for conventions and data). Where a claim rests
on practitioner material only, it is labelled as a hypothesis to test on
our own data, not a finding.

---

## 1. What this analysis is formally called

1. **Event study methodology** — the academic framework (Fama, Fisher,
   Jensen & Roll 1969; Brown & Warner 1985): abnormal return = actual
   return minus expected return from a market or benchmark model, cumulated
   over windows around the event (CAR). Every FDA/clinical-trial stock
   study uses it [A: PLOS One 2013; PMC 2022; ScienceDirect 2006/2025].
   Our `study.py` is an event study against the XBI benchmark.
2. **Event-driven / catalyst investing** — the trading discipline of
   positioning around scheduled, price-moving events; in biotech,
   **"binary event" or "catalyst" trading**, with the sub-pattern known
   as the **"PDUFA run-up"** [P: BiopharmaWatch, RTTNews, pdufa.bio].
3. **Pre-announcement drift (run-up) and post-announcement drift** — the
   academic names for price movement before and after the event; the
   post-event version descends from post-earnings-announcement drift
   (Bernard & Thomas 1989) and is explained by **limited investor
   attention** [A: Hirshleifer, Lim & Teoh, JF 2009].
4. **Implied-move / volatility-premium analysis** — the options-market
   view: the at-the-money straddle prices the expected move; after the
   event the premium collapses ("IV crush") [P: SpotGamma, OAS,
   MarketChameleon].
5. **Cross-sectional catalyst ranking** — no single academic label; the
   closest formal bases are limited-attention/competing-news theory
   (Hirshleifer et al.) and slow-moving arbitrage capital (Duffie, JF 2010
   — from memory, verify before citing in a paper).

So the product is: *a daily event-study-based catalyst forecaster with
cross-sectional ranking under attention and capital constraints.*

## 2. Evidence base (what is established, what is not)

### 2.1 Reaction on the event (established)
- FDA decisions and trial readouts produce statistically significant
  abnormal returns; negative outcomes produce larger and more persistent
  moves than positive ones (asymmetry) [A: PLOS One 2013: medians +0.8% /
  −2.0% on day 0 for large firms; PMC 2022; ScienceDirect 2006: final
  approval +0.35% day 0, +0.44% day 1, "final approval resolves only a
  small degree of uncertainty"]. Our own numbers agree: approvals +0.3%,
  rejections −7% / −22%.
- **Firm size and stage dominate the reaction size**: early-stage biotech
  versus big pharma "had the most impact on abnormal returns, followed by
  disease, outcome, phase, and target accrual" [A: PMC 2022]. Large firms
  have a much lower probability of extreme negative CAR (≤ −10%) on a CRL
  [A: SSRN 6027774, 2026].
- **CRL deficiency type matters**: manufacturing/CMC letters are less
  damaging and more recoverable than efficacy/safety letters; single-day
  declines span 2% (AbbVie) to 75% (Aldeyra) [A: SSRN 2026; P: MedPath,
  RTTNews]. Class 1 resubmission = 2-month review, Class 2 = 6-month [R:
  21 CFR 314.110; P: Assyro]. Practitioner estimate of eventual approval
  after a CRL requiring new trials: ~44% [P: Submarine Catalyst —
  hypothesis].
- **Post-event drift exists and depends on size**: markets under-react to
  failures by large firms and over-react to failures by small firms; a
  strategy on that pattern returned ~40–50% over 100 days in a 92-event
  sample [A: ScienceDirect 2025 — small sample, treat as hypothesis to
  replicate on our 1,165 events].
- **Spillovers**: approvals benefit alliance partners; adverse regulatory
  events spill negatively onto partners [A: ScienceDirect 2006].
  Same-indication competitors: not established in the sources found;
  hypothesis to test with our disease vectors.

### 2.2 Before the event (partly established)
- **Run-up**: practitioner consensus is a 2–8 week run-up of 20–40% for
  small caps [P: BiopharmaWatch, Alpha Breakout Lab]. The only quantified
  cross-sectional figure found: across 1,833 decisions since 2020, the
  median stock was +17.8% at its best point in the 120 trading days
  before the decision but only +1.9% the day before — "the typical run-up
  was largely given back before the answer arrived" [P: pdufa.bio]. Fast
  Track designation announcements show abnormal returns the day *before*
  the announcement (information leakage) [A: Drug Discovery Today 2023].
- **Decision timing**: FDA acts on or before the PDUFA date, often days
  early, and usually after market close or pre-market; companies disclose
  via press release and 8-K within four business days [P: BiopharmaWatch;
  Dan Sfera]. FDA meets its goal date "over 90% of the time" [P: Alpha
  Breakout Lab — verify against PDUFA performance reports, R].
- **Advisory committees**: FDA is not bound but usually follows; negative
  or mixed votes were followed by approval 14–17% of the time in
  2012–2013 [P/A: Evaluate/UBS 2019]. Product-specific AdCom meetings
  produce "statistically significant but usually small negative" price
  effects; general-topic meetings none [A: NBER w14932]. The FDA briefing
  document (posted two business days before) is the strongest predictor
  of the vote [P: Assyro]; UBS found holding through an AdCom vote yields
  negative average return across all companies [P: Evaluate].
- **Options market**: pre-event IV of 150–300% annualized for small
  biotechs, collapsing to ~40% after; the straddle price is the market's
  expected move and is the natural benchmark for any forecast we make
  [P: SpotGamma, OAS, JournalPlus]. Options data is not in our free
  sources; see §6.

### 2.3 Competing events and capital (established in general form)
- **Investor distraction hypothesis**: the immediate price and volume
  reaction to a firm's news is much weaker, and post-announcement drift
  much stronger, when many other firms announce the same day; industry-
  unrelated news distracts more; a trading strategy on this yields
  substantial alphas [A: Hirshleifer, Lim & Teoh, JF 2009]. This is the
  academic basis for the requirement "rank companies competing for the
  same capital in the same window": crowded catalyst windows should show
  muted day-0 reactions and larger drift, which is measurable on our
  event set once a calendar density feature is built.
- Practitioner tools already integrate "the relative timing of competing
  catalysts" with runway estimates [P: FDA Tracker].

### 2.4 Predictive (not just retrospective) work
- A 2023 framework predicted numerical announcement-induced price changes
  from 5,436 clinical-trial announcements (2018–2022) using announcement
  sentiment, a temporal fusion transformer for expected return, a graph
  network for event relationships, and gradient boosting [A: PMC
  10406841]. This is the closest published analogue to the product;
  its components map onto our data (text, relationships graph, fitted
  screen tooling).

## 3. Thesis (to be pre-registered before any measurement)

T1. The size of the price reaction to an FDA calendar event is
    predictable in the cross-section from entity attributes (stage,
    size, single-asset dependence, cash runway, event type, prior CRL
    history, designation) — established for direction and asymmetry,
    testable for magnitude on our 1,165+ events.
T2. Pre-event drift (run-up) is systematic in timing and partly in size,
    and is a function of the same attributes plus market regime (XBI
    trend) and calendar crowding — practitioner-established, academically
    thin; the core thing to measure.
T3. Post-event drift depends on outcome class × firm size (under-reaction
    for large, over-reaction for small) and on CRL deficiency type —
    one academic result to replicate.
T4. Calendar crowding (number and size of same-window catalysts, in and
    out of the sector) mutes day-0 reactions and increases drift — a
    direct application of Hirshleifer et al.; testable.
T5. Peer spillover: same-indication competitors and alliance partners move
    on a firm's decision, in a direction that depends on substitutability
    — partner spillover established, competitor spillover a hypothesis.
T6. Delay events (PDUFA extension, missed goal date, "major amendment")
    carry their own negative reaction and change subsequent run-up —
    practitioner-observed, unmeasured.

## 4. Event taxonomy (calendar events "of all kinds")

| Class | Event | Scheduled? | Outcome states | Public source |
|---|---|---|---|---|
| Regulatory decision | PDUFA goal date (NDA/BLA, sNDA/sBLA) | yes (sponsor-disclosed) | approval · approval with narrowed label/REMS · CRL (by deficiency type) · extension · missed date | sponsor PR/8-K [P calendars]; outcome from Drugs@FDA [R], FDA CRL database (real-time since 2025) [R] |
| Regulatory meeting | Advisory committee | yes (Federal Register) | positive · negative · mixed vote; briefing doc posted T−2 | FDA AdCom calendar [R] |
| Filing milestones | NDA/BLA submission, acceptance (filing decision, day 60), priority review grant, PDUFA date set | announced | accepted/refused-to-file; standard vs priority | sponsor PR/8-K |
| Designations | Fast Track, Breakthrough, RMAT, Orphan, Accelerated approval | unscheduled | granted | sponsor PR; FDA lists [R] |
| Clinical readouts | topline data (Ph1/2/3), interim, DSMB | semi-scheduled (guidance windows; CT.gov primary completion date) | positive · negative · mixed | sponsor PR; CT.gov [R] |
| Post-CRL path | Type A meeting outcome, resubmission, Class 1/2 acceptance, new PDUFA | announced | — | sponsor PR/8-K |
| Post-approval | label expansion, safety communication, boxed warning, withdrawal, REMS change | unscheduled | — | FDA [R] |
| Delay / timing | PDUFA extension (major amendment, +3 months), review delay, government shutdown | announced | — | sponsor PR |
| Financing overlay | ATM/shelf, offering after positive event (dilution) | unscheduled | — | 8-K, S-3 |

Each event row carries: entity, asset, indication, event class, scheduled
date, disclosure date/time (pre-market / after close), outcome state,
outcome sub-type, source URL. Outcome disclosure timing matters because
the tradeable reaction is the next session's open, not the calendar date.

## 5. Models (candidates; each a registered model under P6, one
##    evaluation harness, separate result records)

M2.1 **Reaction magnitude model** (T1, T3): given event class and entity
     attributes, predict the distribution (not a point) of CAR[0,+1] per
     outcome state; gradient boosting on our panel, quantile outputs;
     benchmark = historical class medians.
M2.2 **Run-up model** (T2): predict CAR over [−40,−1] and the day-before
     level; features: attributes, XBI regime, days-to-event, crowding,
     prior events for the same stock, short interest if obtainable.
M2.3 **Post-event drift model** (T3): CAR[+2,+60] conditional on outcome
     state, size, CRL type; replicates the 2025 finding first.
M2.4 **Crowding index** (T4): for each calendar day, count and dollar
     weight of catalysts within ±k days, in-sector and market-wide;
     enters M2.1–M2.3 as a feature and drives the ranking.
M2.5 **Outcome probability prior** (needed by M2.1 to produce an expected
     value): base rates by event class, designation, AdCom vote, prior
     CRL, sponsor track record; calibrated on Drugs@FDA outcomes. Not a
     prediction of the science; a base rate.
M2.6 **Peer spillover model** (T5): expected CAR of partners and
     same-disease competitors given the focal outcome, using
     `relationships.csv` and disease vectors.
M2.7 **Ranking / capital allocation** (T4): per day, rank pending
     catalysts by expected value, dispersion, liquidity, and crowding;
     output a priority list with sizing bands. This is a portfolio-
     construction step, not a prediction model; it consumes M2.1–M2.6.

Baselines every model must beat: (a) historical class median; (b) the
options-implied move where available; (c) "no drift" (zero).

## 6. Data requirements against current holdings

| Need | Have | Gap | Free route |
|---|---|---|---|
| Historical FDA outcomes with dates | `events.csv` (Drugs@FDA approvals, CRLs from openFDA) | CRL deficiency type; sub-types | FDA CRL database (published 2025, real-time) [R]; press-release text |
| Forward calendar (PDUFA, AdCom, readouts) | none | entire forward calendar | sponsor 8-K/PR text mining (we already ingest 8-Ks); FDA AdCom calendar; CT.gov primary completion dates; PDUFA-clock estimation from filing dates (10 / 6 months) |
| Disclosure timestamp (pre-market / after close) | none | needed for the tradeable open | 8-K acceptance timestamp on EDGAR; PR wire time |
| Daily prices, benchmark | `prices.csv` (Yahoo), XBI | survivorship hole for delisted; intraday absent | keep; document hole; delisted names via last available |
| Entity attributes | silver tables | modality, single-asset flag, runway (have), short interest (absent) | manual layer; FINRA short interest (free, bi-monthly) |
| Options implied move | none | benchmark only | not free at scale; manual entry for the live watchlist via the manual layer |
| Calendar crowding | derivable once the calendar exists | — | — |
| Peer sets | disease vectors, `relationships.csv` | — | — |

The forward calendar is the critical new asset. Decision 2026-08-30 (P13):
past decisions from the FDA as built; forward goal dates from sponsor
8-K/press exhibits found via the SEC EDGAR full-text search JSON endpoint
(efts.sec.gov, no key, User-Agent required, undocumented, probe-gated);
AdComs from the FDA calendar; readout windows from CT.gov primary-
completion dates; one aggregator (pdufa.bio, free, source-linked) as a
cross-check only. Paid APIs surveyed (BiopharmaWatch 49-endpoint REST,
BPIQ, RTTNews feeds) are not sources of record.

## 7. Decision rules (candidate rule set, each testable on history)

R1. Never hold an undiversified position through a PDUFA decision for a
    single-asset small cap unless the model's expected value after the
    outcome prior clears a stated threshold (asymmetry: CRL −40–80% vs
    approval gap-up that is often already priced) [P consensus; our
    asymmetry data].
R2. Run-up entry window opens at T−40 to T−10 trading days; exit before
    T−2 by default (the day-before level is historically far below the
    peak) [P: pdufa.bio]; rule parameters fitted on our data, not adopted
    from vendors.
R3. AdCom: reduce exposure before the briefing-document posting (T−2 of
    the meeting), re-evaluate on the document, do not hold through the
    vote by default [P/A: Evaluate/UBS, NBER].
R4. CRL day: classify deficiency type from the letter/PR within the
    session; manufacturing-only CRLs are candidates for post-event
    recovery positions; efficacy/safety CRLs are not [A: SSRN 2026].
R5. Post-approval: expect reversal in the days after a positive event for
    large caps (PLOS 2013 correction) and dilution risk from follow-on
    offerings; treat a filed S-3/ATM as a negative overlay.
R6. Crowding: when more than N catalysts fall in the same window, expect
    muted day-0 moves and larger drift; prefer positions in the least
    crowded windows or size down [A: Hirshleifer].
R7. Delay: a PDUFA extension is treated as a negative event with its own
    reaction model; reset the run-up clock to the new date.
R8. Rank daily: expected value × confidence ÷ crowding, liquidity-
    filtered; publish the top list with the evidence per row.

## 8. Evaluation protocol (pre-registered, same discipline as Model 1)

1. Events: all events in the taxonomy with a resolvable date and outcome;
   split by time (train ≤ 2022, validate 2023–2024, holdout 2025+, single
   access).
2. Metrics: for magnitude — pinball loss on quantiles, calibration of
   sign; for drift — CAR against zero and against class median; for
   ranking — realised return of the top-k list versus equal-weight of all
   pending catalysts and versus XBI; for rules — hit rate and drawdown on
   history with transaction-cost haircut.
3. Leakage rules: no post-event data in any feature; disclosure timestamp
   determines the first tradeable price; delisted survivorship documented.
4. Acceptance: pre-registered thresholds; nulls reported (the run-up may
   not be exploitable after costs — that is a valid finding).

## 9. Risks and limits

- Legal: trading on non-public information is prohibited; the product uses
  public disclosures only and must not ingest anything else; the historical
  studies of pre-announcement leakage are a warning, not a strategy.
- Data: PDUFA dates change; outcome timing is intraday-uncertain; small
  caps are illiquid; free price data has a survivorship hole.
- Statistical: samples per cell (event class × outcome × size) are small;
  quantile forecasts and pooled models are required, and vendor-quoted
  run-up figures are averages over mixed populations.
- Structural: FDA policy shifts (real-time CRL publication, fewer AdComs)
  change the information environment; models must be dated.

## 10. Product design

Requirements are in docs/20260830_v1_FDA_Catalyst_Product_Design.md;
attributes, events, calendar sources, benchmarks and Model 4 are in the
Ontology and Matching Design v3.

## References (abbreviated)
Hirshleifer, Lim, Teoh (2009) JF 64(5). · Hwang (2013) PLOS One 8(8)
e71966. · PMC 9439234 (2022) sponsor stock prices and trial outcomes. ·
Sarkar & de Jong (2006) J. Multinational Fin. Mgmt (market response to FDA
announcements). · Long-term market reactions to FDA Phase III announcements,
Finance Research Letters (2025). · Muralitharan & Banerjee (2026) SSRN
6027774 (CRL reactions). · Fast Track designation event study, Drug
Discovery Today (2023). · NBER w14932 (advisory committee meetings). ·
PMC 10406841 (2023) predictive framework. · FDA press releases on CRL
publication (2025). · 21 CFR 314.110, 314.430. · Practitioner: pdufa.bio,
BiopharmaWatch, RTTNews, Evaluate Vantage (UBS analysis), SpotGamma, OAS.
