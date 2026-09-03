# C:\Users\JB\Documents\dev\bioindustry\src\biointel\aspects.py
"""Gate L4: `aspect-match` — the acquirer-pairing implementation that scores
hypothetical target-acquirer pairs from company aspects (Ontology v5 §5.5),
and the forward hit/false-alarm test (§5.6).

METHODOLOGY (rules first, history as test; scope approved 2026-09-02):
the presence rules below derive from analyst reasoning over the Tempus
record (Ontology v5 §2.5) and the §2 literature, never from fitting to
historical deals. The four Tempus-sequence deals (Ambry Genetics, Deep 6
AI, Paige, Personalis) are the reasoning's source and are EXCLUDED from
both evaluations (P19: patterns are tested only on deals they were not
read from); every other historical deal is eligible test evidence.

V1 ASPECT SET (approved 2026-09-02). Derived-method aspects compute from
tables that exist; stated-method aspects read the entity-attribute tables
(equity_stakes, stated_priorities, assets) dated on or before the cutoff
— never the scored deal's own dossier rows, which would leak the outcome.
`consideration_type` describes a consummated deal, not a pre-announcement
pair attribute, so it is recorded as not-evaluable (coverage 0) rather
than scored. Per-aspect coverage is recorded as run metrics in the ledger
(binding amendment 2026-09-02): which aspects carried an evaluation and
which were effectively absent is a queryable fact of the run.

PRESENCE RULES (analyst-stated constants; equal weights, the naive prior
— any weight scheme is a later gate under its own pre-registration):
  therapeutic_area_overlap    raw Jaccard of trial condition/intervention
                              token sets (continuous strength, no threshold)
  prior_commercial_relationship  a relationships edge between the pair with
                              FirstDate on or before the cutoff (undated
                              edges cannot be proven as-of and do not count)
  patent_cliff_pressure       the buyer has >= 1 Orange Book-matched
                              approval whose protection ends within the
                              run's horizon; every horizon in LOE_HORIZONS
                              is reported (sensitivity, nothing selected)
  buyer_financing_capacity    buyer annualized revenue > $2B as of the
                              cutoff (the project's acquirer-side rule)
  prior_equity_stake          an equity_stakes row, holder = buyer,
                              issuer = candidate, as_of <= cutoff
  competing_stakeholder       an equity_stakes row on the candidate from a
                              holder other than the buyer, as_of <= cutoff
  buyer_stated_priority_match a stated_priorities category of the buyer
                              (stated_at <= cutoff) equal to an assets
                              category of the candidate
  continuum_extension         the candidate's assets cover a continuum step
                              the buyer's assets do not (both firms present
                              in assets)

Score per pair = count of aspects present (equal weights). Rank ties take
the midpoint rank, the convention the exact engine established (a fully
tied pool proposes nothing rather than winning free ranks).

PASS MARK (binding, pre-registered 2026-09-02): aspect-match is adopted
beside or over mass-exact only if its paired HR@5 exceeds 0.334 by more
than 2x the pooled repeat standard deviation on shared events and shared
samples; anything weaker ships as a recorded finding and mass-exact
remains the implementation of record. The forward test reports hits@k per
buyer-year against analytical chance (k / candidate-pool size, summed
over evaluable deals) with false alarms beside it; no threshold gates
shipping — the number is the finding.

CANDIDATE POOL (of record, stated in every forward run note): per
buyer-year, universe members with >= 8 trial tokens as of that year-end,
excluding acquirer-side firms (annualized revenue > $2B) and the buyer
itself. chance = k / pool is recomputable from that sentence alone.
"""

from __future__ import annotations

import logging
import statistics
from datetime import date

from biointel import results, store

log = logging.getLogger(__name__)

# PARAMETER POLICY (gate L4-P, 2026-09-03). The two constants this module
# shipped with at gate L4 — a Jaccard cut of 0.05 for therapeutic-area
# overlap and a single 5-year patent-cliff horizon — were invented by the
# assistant and had no source. Research 2026-09-03: no canonical Jaccard
# threshold exists (task-specific, must be tested on representative data;
# published values for other tasks run 0.2-0.5), and no empirical LOE-horizon
# optimum was found (industry commentary frames three-to-five-year windows,
# which is commentary, not measurement). Rather than re-tune them against the
# same historical deals — fitting on the test set, the leak class already
# retracted once — both are ELIMINATED:
#   therapeutic_area_overlap now contributes its raw Jaccard value as the
#     aspect's strength. No threshold, so no threshold to source, and the
#     matcher keeps information a cut would discard.
#   the LOE horizon is no longer chosen: every evaluation runs at each value
#     in LOE_HORIZONS and reports all of them side by side as a
#     pre-registered sensitivity. Nothing is selected on results.
# Standing rule: no numeric constant enters a rule without a source line; if
# none exists, the parameter is eliminated or reported as a sensitivity.
LOE_HORIZONS = (3, 5, 7, 10)
TEMPUS_EXCLUDED_DEALS = ("Ambry Genetics", "Deep 6 AI", "Paige", "Personalis")
POOL_DEFINITION = (
    "candidate pool per buyer-year = universe members with >=8 trial tokens "
    "as of the year-end, excluding acquirer-side firms (annualized revenue "
    "> $2B) and the buyer itself; chance = k/pool"
)

ASPECT_ORDER = (
    "therapeutic_area_overlap",
    "prior_commercial_relationship",
    "patent_cliff_pressure",
    "buyer_financing_capacity",
    "prior_equity_stake",
    "competing_stakeholder",
    "buyer_stated_priority_match",
    "continuum_extension",
)
NOT_EVALUABLE = ("consideration_type",)  # deal property, not a pair forecast


# ---------------------------------------------------------------- context
def _norm_key(v: str) -> str:
    """Normalize an entity key for matching: 'CIK:0001717115' -> 'cik:1717115';
    tickers and IIDs case-fold. Digits-only strings stay as themselves."""
    v = str(v or "").strip()
    if ":" in v:
        kind, _, rest = v.partition(":")
        digits = "".join(ch for ch in rest if ch.isdigit()).lstrip("0")
        return f"{kind.strip().lower()}:{digits}"
    return v.casefold()


def _loe(cutoff: str, horizon_years: int) -> dict | None:
    """Buyer LOE urgency at the cutoff, or None when the Orange Book zip is
    absent (coverage 0, never a silent zero)."""
    from biointel.sources.orangebook import loe_urgency

    try:
        return loe_urgency(date.fromisoformat(cutoff), horizon_years=horizon_years)
    except FileNotFoundError:
        return None


class Ctx:
    """Everything aspect scoring needs at one cutoff."""

    __slots__ = (
        "cutoff",
        "tokens",
        "acq_side",
        "rel_pairs",
        "loe",
        "stakes",
        "priorities",
        "asset_steps",
        "asset_cats",
        "aliases",
        "has_rel",
        "has_stakes",
        "has_priorities",
        "has_assets",
    )


def build_ctx(cutoff: str, docs: dict[str, str] | None = None, horizon_years: int = 5) -> Ctx:
    from biointel.pairs import _acquirer_side_iids, _firm_docs

    con = store.connect()
    c = Ctx()
    c.cutoff = cutoff
    docs = docs if docs is not None else _firm_docs(cutoff)
    c.tokens = {i: frozenset(d.split()) for i, d in docs.items()}
    c.acq_side = _acquirer_side_iids(cutoff)

    # entity aliases: IID <-> {iid, cik:digits, ticker} for key-form tolerance
    c.aliases = {}
    for co in store.read_table("companies", con=con):
        iid = str(co["IID"])
        al = {iid}
        cik = _norm_key(f"CIK:{co.get('CIK') or ''}")
        if cik != "cik:":
            al.add(cik)
        tick = str(co.get("Ticker") or "").casefold().strip()
        if tick:
            al.add(tick)
        c.aliases[iid] = frozenset(al)

    c.has_rel = store.has_table("relationships", con)
    c.rel_pairs = set()
    if c.has_rel:
        for r in store.read_table("relationships", con=con):
            fd = str(r.get("FirstDate") or "")[:10]
            if not fd or fd > cutoff:
                continue  # undated or later edges cannot be proven as-of
            a, b = str(r.get("IID") or ""), str(r.get("PartnerIID") or "")
            if a and b:
                c.rel_pairs.add((a, b))
                c.rel_pairs.add((b, a))

    c.loe = _loe(cutoff, horizon_years)

    c.has_stakes = store.has_table("equity_stakes", con)
    c.stakes = []
    if c.has_stakes:
        for r in store.read_table("equity_stakes", con=con):
            as_of = str(r.get("as_of") or "")[:10]
            if as_of and as_of <= cutoff:
                c.stakes.append((_norm_key(r["holder_key"]), _norm_key(r["issuer_key"])))

    c.has_priorities = store.has_table("stated_priorities", con)
    c.priorities = []
    if c.has_priorities:
        for r in store.read_table("stated_priorities", con=con):
            st = str(r.get("stated_at") or "")[:10]
            if st and st <= cutoff:
                c.priorities.append((_norm_key(r["entity_key"]), str(r.get("category") or "")))

    c.has_assets = store.has_table("assets", con)
    c.asset_steps, c.asset_cats = {}, {}
    if c.has_assets:
        for r in store.read_table("assets", con=con):
            k = _norm_key(r["entity_key"])
            step = str(r.get("continuum_step") or "")
            cat = str(r.get("category") or "")
            if step:
                c.asset_steps.setdefault(k, set()).add(step)
            if cat:
                c.asset_cats.setdefault(k, set()).add(cat)
    return c


def _entity_rows(keyed: dict, aliases: frozenset) -> set:
    out: set = set()
    for k in aliases:
        out |= keyed.get(k, set())
    return out


def pair_aspects(buyer: str, cand: str, ctx: Ctx) -> dict[str, tuple[bool, bool]]:
    """aspect -> (evaluable, present) for one hypothetical pair at the
    context's cutoff. Evaluable means the underlying data existed for this
    pair; the value is the aspect's strength in [0, 1] — 1.0/0.0 for the
    binary rules, and the raw Jaccard for therapeutic_area_overlap, which
    carries no threshold (gate L4-P). Coverage counts a value > 0 as
    present, so the recorded coverage metric keeps its meaning."""
    b_al = ctx.aliases.get(buyer, frozenset({buyer}))
    c_al = ctx.aliases.get(cand, frozenset({cand}))
    out: dict[str, tuple[bool, float]] = {}

    tb, tc = ctx.tokens.get(buyer), ctx.tokens.get(cand)
    if tb and tc:
        j = len(tb & tc) / len(tb | tc)
        out["therapeutic_area_overlap"] = (True, j)  # raw strength, no cut
    else:
        out["therapeutic_area_overlap"] = (False, 0.0)

    out["prior_commercial_relationship"] = (ctx.has_rel, float((buyer, cand) in ctx.rel_pairs))

    if ctx.loe is None:
        out["patent_cliff_pressure"] = (False, 0.0)
    else:
        row = ctx.loe.get(buyer)
        out["patent_cliff_pressure"] = (row is not None, float(bool(row and row[1] >= 1)))

    out["buyer_financing_capacity"] = (True, float(buyer in ctx.acq_side))

    if ctx.has_stakes and ctx.stakes:
        held = any(h in b_al and i in c_al for h, i in ctx.stakes)
        third = any(i in c_al and h not in b_al for h, i in ctx.stakes)
        out["prior_equity_stake"] = (True, float(held))
        out["competing_stakeholder"] = (True, float(third))
    else:
        out["prior_equity_stake"] = (False, 0.0)
        out["competing_stakeholder"] = (False, 0.0)

    if ctx.has_priorities and ctx.priorities and ctx.has_assets and ctx.asset_cats:
        b_cats = {cat for k, cat in ctx.priorities if k in b_al}
        c_cats: set = set()
        for k in c_al:
            c_cats |= ctx.asset_cats.get(k, set())
        out["buyer_stated_priority_match"] = (True, float(bool(b_cats & c_cats)))
    else:
        out["buyer_stated_priority_match"] = (False, 0.0)

    b_steps: set = set()
    c_steps: set = set()
    for k in b_al:
        b_steps |= ctx.asset_steps.get(k, set())
    for k in c_al:
        c_steps |= ctx.asset_steps.get(k, set())
    if ctx.has_assets and b_steps and c_steps:
        out["continuum_extension"] = (True, float(bool(c_steps - b_steps)))
    else:
        out["continuum_extension"] = (False, 0.0)
    return out


def pair_score(buyer: str, cand: str, ctx: Ctx) -> float:
    """Equal-weight sum of aspect strengths (the naive prior, unchanged)."""
    return sum(v for _ev, v in pair_aspects(buyer, cand, ctx).values())


# ---------------------------------------------------------------- events
def resolved_events() -> tuple[list[tuple[str, str, str]], list[str]]:
    """Target-role events with a registry-resolved acquirer, exactly the
    resolution pairs_full_exact uses, minus the Tempus-sequence exclusion
    (approved 2026-09-02). Returns (events, excluded-descriptions)."""
    from biointel import network

    name_to_iid = {}
    for co in store.read_table("companies"):
        name_to_iid[network._norm(co.get("Name", ""))] = str(co["IID"])
    excluded_names = {network._norm(n) for n in TEMPUS_EXCLUDED_DEALS}
    events, excluded = [], []
    for e in store.read_table("ma_events"):
        if e.get("Role") != "target" or not e.get("AnnounceDate"):
            continue
        acq_raw = e.get("VerifiedAcquirer") or e.get("Counterparty") or ""
        acq = network._norm(acq_raw)
        filer_norm = network._norm(e.get("Filer") or "")
        tick = str(e.get("FilerTicker") or "").strip().upper()
        if "tempus" in acq or tick == "PSNL" or filer_norm in excluded_names:
            excluded.append(f"{e.get('Filer') or tick} <- {acq_raw} ({e['AnnounceDate']})")
            continue
        aid = name_to_iid.get(acq) or next(
            (
                v
                for k, v in name_to_iid.items()
                if k and acq and (k.startswith(acq + " ") or acq.startswith(k + " "))
            ),
            None,
        )
        if aid:
            events.append((aid, str(e["FilerIID"]), str(e["AnnounceDate"])))
    return events, excluded


# ---------------------------------------------------------------- paired protocol
def _midpoint_rank(sims, t_val) -> float:
    greater = sum(1 for s in sims if s > t_val)
    ties = sum(1 for s in sims if s == t_val)
    return greater + (ties + 1.0) / 2.0


def paired(negatives: int = 200, repeats: int = 20, seed: int = 7) -> dict:
    """Aspect-match beside MASS-exact on identical events and shared sampled
    negatives (P10); Tempus-sequence deals excluded; per-aspect coverage
    recorded as run metrics; the pre-registered pass mark applied."""
    import random as _r

    import numpy as np

    from biointel.pairs import _acquirer_side_iids, _count_matrix, _firm_docs, _mass_exact_scores

    events, excluded = resolved_events()

    cache: dict[tuple, tuple] = {}

    def get(cutoff: str, horizon: int = LOE_HORIZONS[0]):
        if (cutoff, horizon) in cache:
            return cache[(cutoff, horizon)]
        docs = _firm_docs(cutoff)
        ids = sorted(docs)
        pos = {i: k for k, i in enumerate(ids)}
        acq_side = _acquirer_side_iids(cutoff)
        if len(ids) >= 3:
            M = _count_matrix(docs, ids)
            v = np.sqrt(np.asarray(M.power(2).sum(axis=0)).ravel())
            v[v <= 0] = 1.0
            Xw = M.multiply(1.0 / np.sqrt(v))
            lam = np.asarray((Xw @ Xw.T).todense())
            row_norms = np.sqrt(np.asarray(M.power(2).sum(axis=1)).ravel())
        else:
            lam, row_norms = None, None
        ctx = build_ctx(cutoff, docs, horizon_years=horizon)
        cache[(cutoff, horizon)] = (ids, pos, acq_side, lam, row_norms, ctx)
        return cache[(cutoff, horizon)]

    ev = []
    for aid, tid, ann in events:
        cutoff = f"{int(ann[:4]) - 1}-12-31"
        ids, pos, acq_side, lam, _n, _c = get(cutoff)
        if (
            lam is not None
            and aid in pos
            and tid in pos
            and len([i for i in ids if i not in acq_side and i not in (aid, tid)]) >= negatives
        ):
            ev.append((aid, tid, ann, cutoff))
    if not ev:
        return {"status": "empty", "message": "No evaluable events."}

    # Sensitivity, not selection (gate L4-P): the paired evaluation is
    # repeated at every LOE horizon and all results are reported. MASS-exact
    # does not read the LOE table, so it is scored once at the first horizon.
    scores: dict[str, tuple[list, list]] = {"MASS-exact": ([], [])}
    for h in LOE_HORIZONS:
        scores[f"aspect-match@{h}y"] = ([], [])
    coverage = {a: [0, 0] for a in ASPECT_ORDER}  # aspect -> [evaluable, present]

    for horizon in LOE_HORIZONS:
        first = horizon == LOE_HORIZONS[0]
        name = f"aspect-match@{horizon}y"
        for rep in range(repeats):
            _r.seed(seed + rep)  # identical samples across horizons and engines
            hits = {name: [0, 0, 0], "MASS-exact": [0, 0, 0]}
            for aid, tid, _ann, cutoff in ev:
                ids, pos, acq_side, lam, row_norms, ctx = get(cutoff, horizon)
                cands = [i for i in ids if i not in acq_side and i not in (aid, tid)]
                sample = _r.sample(cands, negatives) + [tid]
                sims_a = []
                for c in sample:
                    asp = pair_aspects(aid, c, ctx)
                    sims_a.append(sum(v for _e, v in asp.values()))
                    if first and rep == 0:
                        for a, (evb, val) in asp.items():
                            coverage[a][0] += int(evb)
                            coverage[a][1] += int(val > 0)
                pairs_scored = [(name, sims_a)]
                if first:
                    rows = [pos[c] for c in sample]
                    pairs_scored.append(
                        (
                            "MASS-exact",
                            list(_mass_exact_scores(None, lam, row_norms, pos[aid], rows)),
                        )
                    )
                for m, sims in pairs_scored:
                    rank = _midpoint_rank(sims, sims[-1])
                    h = hits[m]
                    h[2] += 1
                    h[0] += rank <= 5
                    h[1] += rank <= 10
            for m, (h5, h10, n) in hits.items():
                if n and (first or m != "MASS-exact"):
                    scores[m][0].append(h5 / n)
                    scores[m][1].append(h10 / n)

    run = results.start(
        "pairs-aspect",
        "pairs-aspect",
        [
            "trials",
            "feature_panel",
            "companies",
            "ma_events",
            "relationships",
            "equity_stakes",
            "stated_priorities",
            "assets",
            "events",
        ],
        {
            "negatives": negatives,
            "repeats": repeats,
            "seed": seed,
            "loe_horizons": ",".join(str(h) for h in LOE_HORIZONS),
        },
    )
    run.metric("_", "n_events", len(ev))
    run.metric("_", "excluded_tempus_deals", len(excluded))
    for m, (h5s, h10s) in scores.items():
        if not h5s:
            continue
        run.metric(m, "hr5_mean", statistics.mean(h5s))
        run.metric(m, "hr5_sd", statistics.pstdev(h5s))
        run.metric(m, "hr10_mean", statistics.mean(h10s))
    m5 = scores["MASS-exact"][0]
    benchmark = 0.334  # HR@5 of record for mass-exact (Implementation Plan v22)
    run.metric("passmark", "benchmark_hr5", benchmark)
    # The pre-registered mark is applied at every horizon; adoption requires it
    # to hold, and the horizon that held is named. Nothing is selected by
    # picking the best horizon after the fact: all are recorded.
    adopted_any = 0
    for h in LOE_HORIZONS:
        a5 = scores[f"aspect-match@{h}y"][0]
        pooled = ((statistics.pstdev(a5) ** 2 + statistics.pstdev(m5) ** 2) / 2.0) ** 0.5
        beat = int(statistics.mean(a5) > benchmark + 2.0 * pooled)
        run.metric("passmark", f"pooled_sd_{h}y", pooled)
        run.metric("passmark", f"beats_mark_{h}y", beat)
        adopted_any = max(adopted_any, beat)
    run.metric("passmark", "adopted", adopted_any)
    for a in ASPECT_ORDER:
        run.metric(a, "evaluable_pairs", coverage[a][0])
        run.metric(a, "present_pairs", coverage[a][1])
    for a in NOT_EVALUABLE:
        run.metric(a, "evaluable_pairs", 0)
        run.metric(a, "present_pairs", 0)

    text = render_paired(run.record())
    p = store.write_export("pair_aspect_report.txt", text)
    run.artefact(p)
    note = (
        "Tempus-sequence deals excluded (rules-source, P19): "
        + "; ".join(TEMPUS_EXCLUDED_DEALS)
        + f". Pass mark pre-registered 2026-09-02: HR@5 > {benchmark} + 2x pooled repeat sd."
    )
    run_id = results.finish(run, note=note)
    log.info(text)
    log.info(f"run {run_id} recorded")
    return {"status": "ok", "message": text, "run_id": run_id}


def render_paired(rec: dict) -> str:
    m = results.Metrics(rec)
    horizons = [int(x) for x in m.p("loe_horizons").split(",")]
    lines = [
        "ASPECT-MATCH vs MASS-EXACT (paired: %d events, %d negatives, %d repeats, "
        "shared samples; Tempus-sequence deals excluded; therapeutic-area overlap "
        "carries no threshold; LOE horizon reported as a sensitivity, not chosen)"
        % (m.i("_", "n_events"), int(m.p("negatives")), int(m.p("repeats")))
    ]
    names = ["MASS-exact"] + [f"aspect-match@{h}y" for h in horizons]
    for name in names:
        lines.append(
            "%-20s HR@5 %.3f (+/-%.3f)   HR@10 %.3f"
            % (name, m.f(name, "hr5_mean"), m.f(name, "hr5_sd"), m.f(name, "hr10_mean"))
        )
    bench = m.f("passmark", "benchmark_hr5")
    for h in horizons:
        lines.append(
            "pass mark @%dy: HR@5 > %.3f + 2 x pooled sd %.4f -> %s"
            % (
                h,
                bench,
                m.f("passmark", f"pooled_sd_{h}y"),
                "BEATS MARK" if m.i("passmark", f"beats_mark_{h}y") else "does not beat mark",
            )
        )
    lines.append(
        "verdict: %s"
        % ("ADOPTED" if m.i("passmark", "adopted") else "NOT ADOPTED (mass-exact stands)")
    )
    lines.append("aspect coverage (repeat-0 scored pairs; evaluable/present):")
    for a in ASPECT_ORDER + NOT_EVALUABLE:
        lines.append("  %-30s %d / %d" % (a, m.i(a, "evaluable_pairs"), m.i(a, "present_pairs")))
    return "\n".join(lines)


# ---------------------------------------------------------------- forward test
def forward(ks: tuple[int, ...] = (5, 10, 25), k_primary: int = 10, horizon_years: int = 5) -> dict:
    """§5.6: per buyer per year-end, rank the candidate pool from information
    dated on or before that year-end; count hits (deals announced the
    following year with the true target inside top-k) and false alarms
    (proposed top-k pairs that did not happen the following year), both
    against analytical chance. No threshold gates shipping."""
    from collections import Counter

    from biointel.pairs import _firm_docs

    events, excluded = resolved_events()
    if not events:
        return {"status": "empty", "message": "No resolvable events."}
    deals_by_year: dict[int, list[tuple[str, str]]] = {}
    for aid, tid, ann in events:
        deals_by_year.setdefault(int(ann[:4]), []).append((aid, tid))
    buyers = sorted({aid for aid, _t, _a in events})
    years = range(2004, max(deals_by_year) if deals_by_year else 2004)

    hits = {k: 0 for k in ks}
    expected = {k: 0.0 for k in ks}
    false_alarms = 0
    evaluable_deals = 0
    buyer_years = 0
    degenerate = 0
    pools: list[int] = []
    coverage = {a: [0, 0] for a in ASPECT_ORDER}

    for y in years:
        cutoff = f"{y}-12-31"
        docs = _firm_docs(cutoff)
        if not docs:
            continue
        ctx = build_ctx(cutoff, docs, horizon_years=horizon_years)
        ids = sorted(docs)
        next_deals = deals_by_year.get(y + 1, [])
        targets_of = {}
        for aid, tid in next_deals:
            targets_of.setdefault(aid, set()).add(tid)
        for b in buyers:
            if b not in ctx.tokens:
                continue
            cands = [i for i in ids if i not in ctx.acq_side and i != b]
            if len(cands) < max(ks):
                continue
            buyer_years += 1
            pools.append(len(cands))
            sims = []
            for cnd in cands:
                asp = pair_aspects(b, cnd, ctx)
                sims.append(sum(v for _e, v in asp.values()))
                for a, (evb, val) in asp.items():
                    coverage[a][0] += int(evb)
                    coverage[a][1] += int(val > 0)
            counts = Counter(sims)
            # midpoint rank per distinct score value
            rank_of: dict[int, float] = {}
            above = 0
            for val in sorted(counts, reverse=True):
                rank_of[val] = above + (counts[val] + 1.0) / 2.0
                above += counts[val]
            proposed = {c for c, s in zip(cands, sims) if rank_of[s] <= k_primary}
            if not proposed:
                degenerate += 1
            wanted = targets_of.get(b, set())
            for k in ks:
                for t in wanted:
                    if t in cands:
                        expected[k] += k / len(cands)
                        j = cands.index(t)
                        if rank_of[sims[j]] <= k:
                            hits[k] += 1
            evaluable_deals += sum(1 for t in wanted if t in cands)
            false_alarms += len(proposed - wanted)

    run = results.start(
        "pairs-aspect-forward",
        "pairs-aspect forward",
        [
            "trials",
            "feature_panel",
            "companies",
            "ma_events",
            "relationships",
            "equity_stakes",
            "stated_priorities",
            "assets",
            "events",
        ],
        {"k_primary": k_primary, "ks": ",".join(str(k) for k in ks)},
    )
    run.metric("_", "buyers", len(buyers))
    run.metric("_", "buyer_years", buyer_years)
    run.metric("_", "degenerate_buyer_years", degenerate)
    run.metric("_", "evaluable_deals", evaluable_deals)
    run.metric("_", "excluded_tempus_deals", len(excluded))
    run.metric("_", "median_pool", sorted(pools)[len(pools) // 2] if pools else 0)
    for k in ks:
        run.metric("_", f"hits{k}", hits[k])
        run.metric("_", f"expected_hits{k}", expected[k])
    run.metric("_", f"false_alarms{k_primary}", false_alarms)
    for a in ASPECT_ORDER:
        run.metric(a, "evaluable_pairs", coverage[a][0])
        run.metric(a, "present_pairs", coverage[a][1])
    for a in NOT_EVALUABLE:
        run.metric(a, "evaluable_pairs", 0)
        run.metric(a, "present_pairs", 0)

    text = render_forward(run.record())
    p = store.write_export("pair_aspect_forward_report.txt", text)
    run.artefact(p)
    note = (
        POOL_DEFINITION
        + ". Tempus-sequence deals excluded (rules-source, P19): "
        + "; ".join(TEMPUS_EXCLUDED_DEALS)
        + "."
    )
    run_id = results.finish(run, note=note)
    log.info(text)
    log.info(f"run {run_id} recorded")
    return {"status": "ok", "message": text, "run_id": run_id}


def render_forward(rec: dict) -> str:
    m = results.Metrics(rec)
    k = int(m.p("k_primary"))
    lines = [
        "FORWARD HIT/FALSE-ALARM TEST (aspect-match): %d buyers, %d buyer-years "
        "(%d degenerate), %d evaluable deals; median pool %d"
        % (
            m.i("_", "buyers"),
            m.i("_", "buyer_years"),
            m.i("_", "degenerate_buyer_years"),
            m.i("_", "evaluable_deals"),
            m.i("_", "median_pool"),
        )
    ]
    for kk in (int(x) for x in m.p("ks").split(",")):
        lines.append(
            "  hits@%-3d %d  vs chance %.2f"
            % (kk, m.i("_", f"hits{kk}"), m.f("_", f"expected_hits{kk}"))
        )
    lines.append(
        "  false alarms (top-%d proposals not realized next year): %d"
        % (
            k,
            m.i("_", f"false_alarms{k}"),
        )
    )
    lines.append("aspect coverage (scored pairs; evaluable/present):")
    for a in ASPECT_ORDER + NOT_EVALUABLE:
        lines.append("  %-30s %d / %d" % (a, m.i(a, "evaluable_pairs"), m.i(a, "present_pairs")))
    lines.append(POOL_DEFINITION)
    return "\n".join(lines)


# ---------------------------------------------------------------- adapters
def run_paired(as_of: str | None, params: dict) -> dict:
    kw = {}
    for key in ("negatives", "repeats", "seed"):
        if key in params:
            kw[key] = int(params[key])
    return paired(**kw)


def run_forward(as_of: str | None, params: dict) -> dict:
    kw = {}
    if "k_primary" in params:
        kw["k_primary"] = int(params["k_primary"])
    if "ks" in params:
        kw["ks"] = tuple(int(x) for x in str(params["ks"]).split(","))
    return forward(**kw)
