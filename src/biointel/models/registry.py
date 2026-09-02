# src/biointel/models/registry.py
"""The registry: three models, their implementations and evaluations, and
the exact tables and columns each may read (P2, enforced by the harness).

Declarations were derived from the code (traced reads on a fixture run,
cross-checked against the column literals in each module) on 2026-08-31.
A read outside a declaration stops the run with InputViolation; the fix is
to correct the declaration when the read is legitimate, never to disable
the check.

Price-derived columns (PRICE_DERIVED) and the event_study table may not
appear in a fitted M&A implementation's inputs; tests/unit/test_models.py
asserts this. A hand-written screen may read them (P2) and declares them
openly. Legacy code (P7) is not registered.
"""

from __future__ import annotations

from biointel.models.base import Entry, Inputs

PRICE_DERIVED = (
    "PriceQ",
    "MarketCap",
    "Drawdown52w",
    "CAR12m_mean",
    "Drift12m_mean",
    "FDAEventsWithCAR12m",
)
EVENT_REACTION_TABLES = ("event_study", "event_study_summary")
MA_LABEL_TABLES = ("ma_events", "ma_events_universe", "ma_events_verified", "label_panel")

# ---------------------------------------------------------------- shared declarations
_TRIALS_TEXT = ("IID", "Conditions", "Drugs", "Interventions", "StartDate")
_MA_EVENTS_TARGETS = ("FilerIID", "Role", "AnnounceDate", "VerifiedAcquirer", "Counterparty")
_MA_EVENTS_LABELS = ("FilerIID", "Role", "AnnounceDate", "Verified")
_FEATURE_PANEL_SIZE = ("IID", "QuarterEnd", "Revenue", "TTMBasis")

# Fundamentals the fitted screen may read from feature_panel: no price column.
_FEATURE_PANEL_FUNDAMENTALS = (
    "IID",
    "QuarterEnd",
    "Currency",
    "CashSTI",
    "Revenue",
    "RnD",
    "TotalAssets",
    "RunwayMonths",
    "HasApprovedDrug",
    "LeadPhase",
    "TrialsPh3",
    "TrialsTotal",
    "TrialsStarted12m",
    "Approvals12m",
    "Rejections12m",
    "RelDeal",
    "RelInUniverse",
    "dCash4q",
    "dShares4q",
    "RnDIntensity",
    "CashToAssets",
    "AgeYears",
    "Ph3Started24m",
    "FirstApprovalRecent24m",
    "HotTA",
    "FDAEventsEver",
)

# The scorecard is hand-written (not trained); P2 lets it read any attribute
# and requires the inputs to be declared. It reads two price-derived columns.
SCORECARD_INPUTS: Inputs = {
    "model_panel": (
        "IID",
        "Ticker",
        "Company",
        "QuarterEnd",
        "Currency",
        "Revenue",
        "TTMBasis",
        "RunwayMonths",
        "OrigApprovalsEver",
        "LeadPhase",
        "TrialsPh3",
        "Approvals12m",
        "RelDeal",
        "RelInUniverse",
        "CAR12m_mean",  # price-derived (event reaction); permitted for a hand scorecard, declared
        "MarketCap",  # price-derived (size); permitted for a hand scorecard, declared
        "AcquiredNext12m",
        "Acquirer",
        "AnnounceDate",
    ),
    "trials": _TRIALS_TEXT,
    "relationships": ("IID", "PartnerIID"),
}

FITTED_INPUTS: Inputs = {
    "feature_panel": _FEATURE_PANEL_FUNDAMENTALS,
    "ma_events": _MA_EVENTS_LABELS,
    "ma_events_universe": ("CIK", "AnnounceDate", "AgreementDate", "Corroboration"),
    "companies": ("IID", "CIK"),
    "trials": (
        "IID",
        "Conditions",
        "StartDate",
        "Phase",
        "Status",
        "PrimaryCompletion",
        "CompletionDate",  # fallback when PrimaryCompletion is blank (improve.engineer)
    ),
    "pair_feature": ("IID", "YearEnd", "MaxSimToAcq"),
    "activist_13d": ("IID", "Date"),
}

# The robustness suite measures the leak on purpose: it declares the price columns.
ROBUST_INPUTS: Inputs = {
    "feature_panel": _FEATURE_PANEL_FUNDAMENTALS + PRICE_DERIVED,
    "ma_events": _MA_EVENTS_LABELS,
    "ma_events_universe": ("CIK", "AnnounceDate", "AgreementDate", "Corroboration"),
    "companies": ("IID", "CIK"),
}

IMPROVE_INPUTS: Inputs = {
    "feature_panel": _FEATURE_PANEL_FUNDAMENTALS,
    "ma_events": _MA_EVENTS_LABELS,
    "ma_events_universe": ("CIK", "AnnounceDate", "AgreementDate", "Corroboration"),
    "companies": ("IID", "CIK"),
}

MASS_EXACT_INPUTS: Inputs = {
    "trials": _TRIALS_TEXT,
    "feature_panel": _FEATURE_PANEL_SIZE,
    "companies": ("IID", "Name"),
    "ma_events": _MA_EVENTS_TARGETS,
}

ASPECT_MATCH_INPUTS: Inputs = {
    "trials": _TRIALS_TEXT,
    "feature_panel": _FEATURE_PANEL_SIZE,
    "companies": ("IID", "Name", "CIK", "Ticker"),
    "ma_events": _MA_EVENTS_TARGETS + ("FilerTicker", "Filer"),
    "relationships": ("IID", "PartnerIID", "FirstDate"),
    "equity_stakes": ("holder_key", "issuer_key", "percent", "as_of"),
    "stated_priorities": ("entity_key", "stated_at", "category"),
    "assets": ("entity_key", "category", "continuum_step"),
    "events": ("IID", "AppNo", "Outcome"),
    # the Orange Book zip is a bronze artifact (LOE horizon); declared for
    # the record like bronze:prices
    "bronze:orangebook": None,
}

DAILY_BARS_INPUTS: Inputs = {
    "events": None,
    "companies": None,
    # daily prices are bronze files, not a table; declared for the record,
    # enforced once prices become a table (gate 1.4/2.8)
    "bronze:prices": None,
}


# ---------------------------------------------------------------- entries
def _entries() -> list[Entry]:
    from biointel import aspects as _asp
    from biointel.models import adapters as a

    return [
        Entry(
            "target-screen",
            "scorecard",
            "predict",
            SCORECARD_INPUTS,
            a.run_scorecard,
            outputs=("ma_predictions",),
            note="hand-written points; what `predict` uses today",
        ),
        Entry(
            "target-screen",
            "fitted",
            "fit",
            FITTED_INPUTS,
            a.run_fitted,
            outputs=("activist_13d",),
            note="trained gradient boosting (gen-2); `develop` reports it, `tune` selects it",
        ),
        Entry(
            "target-screen",
            "develop",
            "evaluation",
            FITTED_INPUTS,
            a.run_develop,
            outputs=("activist_13d",),
            of_impl="fitted",
            note="purged walk-forward development scores",
        ),
        Entry(
            "target-screen",
            "tune",
            "evaluation",
            FITTED_INPUTS,
            a.run_tune,
            outputs=("activist_13d",),
            of_impl="fitted",
            note="GBM grid on the winning spec; persists best_config.json",
        ),
        Entry(
            "target-screen",
            "textsweep",
            "evaluation",
            FITTED_INPUTS,
            a.run_textsweep,
            outputs=("activist_13d",),
            of_impl="fitted",
            note="text-scorer shrinkage sweep (needs a 10-K corpus)",
        ),
        Entry(
            "target-screen",
            "robust",
            "evaluation",
            ROBUST_INPUTS,
            a.run_robust,
            of_impl="fitted",
            note="nine scenarios incl. the deliberately price-inclusive ones (leak diagnostic)",
        ),
        Entry(
            "target-screen",
            "improve",
            "evaluation",
            IMPROVE_INPUTS,
            a.run_improve,
            of_impl="fitted",
            note="logistic vs gradient boosting on the validation window",
        ),
        Entry(
            "acquirer-pairing",
            "mass-exact",
            "predict",
            MASS_EXACT_INPUTS,
            a.run_pairs_full_exact,
            note="adopted engine; full-universe re-rank of true targets",
        ),
        Entry(
            "acquirer-pairing",
            "pairs-exact",
            "evaluation",
            MASS_EXACT_INPUTS,
            a.run_pairs_exact,
            of_impl="mass-exact",
            note="paired MASS-exact vs incumbent test (200 negatives, 20 repeats)",
        ),
        Entry(
            "acquirer-pairing",
            "aspect-match",
            "predict",
            ASPECT_MATCH_INPUTS,
            _asp.run_forward,
            note="hand-built aspect matcher (gate L4); forward hit/false-alarm test (Ontology s5.5-s5.6)",
        ),
        Entry(
            "acquirer-pairing",
            "aspect-paired",
            "evaluation",
            ASPECT_MATCH_INPUTS,
            _asp.run_paired,
            of_impl="aspect-match",
            note="paired aspect-match vs mass-exact (shared events and samples; Tempus-sequence deals excluded)",
        ),
        Entry(
            "fda-event-study",
            "daily-bars",
            "predict",
            DAILY_BARS_INPUTS,
            a.run_daily_bars,
            outputs=("event_study", "event_study_summary"),
            note="abnormal returns around FDA approvals and rejections since 2010",
        ),
    ]


_CACHE: list[Entry] | None = None


def entries() -> list[Entry]:
    global _CACHE
    if _CACHE is None:
        _CACHE = _entries()
    return _CACHE


def models() -> list[str]:
    out: list[str] = []
    for e in entries():
        if e.model not in out:
            out.append(e.model)
    return out


def implementations(model: str) -> list[Entry]:
    return [e for e in entries() if e.model == model and e.run_type != "evaluation"]


def evaluations(model: str) -> list[Entry]:
    return [e for e in entries() if e.model == model and e.run_type == "evaluation"]


def get(model: str, name: str | None = None, eval_name: str | None = None) -> Entry:
    """Resolve `run <model> [--impl name] [--eval eval_name]`."""
    if eval_name:
        for e in evaluations(model):
            if e.name == eval_name:
                return e
        raise KeyError(f"{model} has no evaluation {eval_name!r}")
    impls = implementations(model)
    if not impls:
        raise KeyError(f"unknown model {model!r}")
    if name is None:
        if len(impls) == 1:
            return impls[0]
        raise KeyError(
            f"{model} has {len(impls)} implementations; pass --impl "
            + " | ".join(e.name for e in impls)
        )
    for e in impls:
        if e.name == name:
            return e
    raise KeyError(f"{model} has no implementation {name!r}")


# Existing commands -> registry entry, so every command runs under enforcement.
COMMAND_TO_ENTRY = {
    "predict": ("target-screen", "scorecard", None),
    "develop": ("target-screen", None, "develop"),
    "develop tune": ("target-screen", None, "tune"),
    "develop textsweep": ("target-screen", None, "textsweep"),
    "robust": ("target-screen", None, "robust"),
    "improve": ("target-screen", None, "improve"),
    "pairs-full-exact": ("acquirer-pairing", "mass-exact", None),
    "pairs-aspect": ("acquirer-pairing", None, "aspect-paired"),
    "pairs-aspect forward": ("acquirer-pairing", "aspect-match", None),
    "pairs-exact": ("acquirer-pairing", None, "pairs-exact"),
    "study-all": ("fda-event-study", "daily-bars", None),
}
