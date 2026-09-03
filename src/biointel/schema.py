# C:\Users\JB\Documents\dev\bioindustry\src\biointel\schema.py
# src/biointel/schema.py
"""Schema as code: the written ontology (Ontology and Matching Design v3 §3.5).

One declarative module that names every entity type, attribute group,
relationship type, event class and outcome state, and maps every silver
and gold table the package writes to its columns, key, per-column type
and allowed values. `python -m biointel validate` checks every table that
exists under data/ against this map (gate 0.1, Implementation Plan v2).

This module imports nothing from the rest of the package so that every
other module may import it. Column lists here are the source of record;
tests/unit/test_schema.py asserts that each module's own column constant
is identical to the list declared here, so the two cannot drift.

Column types (the `types` map; a column absent from the map is free text):
  int       integer, blank allowed unless the column is in the key
  float     decimal number, blank allowed
  date      YYYY-MM-DD, blank allowed
  datetime  ISO 8601 date-time, blank allowed
  enum      one of the values listed in `enums` for that column; blank
            is allowed only when "" is listed
  flag01    "0" or "1"
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

SCHEMA_VERSION = "0.11"  # bumped when TABLES or a table declaration changes

# ---------------------------------------------------------------- ontology
# Entity types (Ontology §3.1, §3.1a). `listed` and `has_prices` are the
# registry flags of §3.1a; stubs are rows with listed=0 and has_prices=0.
ENTITY_TYPES = (
    "company",  # listed or private operating company
    "financial_buyer",  # PE, hedge fund, royalty buyer
    "institution",  # academic or research group (Model 4)
    "person",  # optional, manual (Ontology §8 Q4)
    "asset",  # drug program: one per (company, molecule/indication)
    "trial",  # ClinicalTrials.gov record
    "regulatory_event",  # one table for past actions and the forward calendar
    "deal",  # acquisition, licence, partnership
    "patent",  # Orange Book listing or CPC patent
)
REGISTRY_FLAGS = ("listed", "has_prices", "type")

# Attribute groups (Ontology §3.2, §3.2a): name -> (attributes, source tables).
ATTRIBUTE_GROUPS = {
    "identity": (
        ("name", "aliases", "cik", "ticker", "listed", "type", "hq"),
        ("silver/companies.csv", "silver/universe.csv"),
    ),
    "therapeutic_profile": (
        ("diseases_by_trial_count", "phase_mix", "approvals"),
        ("silver/trials.csv", "silver/events.csv"),
    ),
    "mechanism_modality": (
        ("molecular_targets", "modality"),
        ("silver/drug_targets.csv",),
    ),
    "sector": (("sector",), ("silver/companies.csv",)),
    "stage": (
        ("lead_phase", "phase_mix", "first_approval_date"),
        ("silver/trials.csv", "silver/events.csv"),
    ),
    "financial": (
        ("cash", "revenue", "burn", "runway", "market_cap", "valuation"),
        ("silver/financials.csv", "silver/financial_snapshot.csv", "gold/feature_panel.csv"),
    ),
    "ip_position": (
        ("orange_book_expiries", "cpc_classes", "loe_exposure"),
        ("silver/patents.csv",),
    ),
    "relationships": (
        ("partners", "co_sponsors", "counterparties", "investors", "acquirer"),
        ("silver/relationships.csv",),
    ),
    "strategy_intent": (("stated_objectives", "in_play_flags", "rumours"), ()),
    "objectives": (("objective_weights",), ()),
    # §3.2a price-action group (Model 2 inputs; any model may read)
    "price_action": (
        (
            "event_dependence",
            "stage_class",
            "size",
            "capital_position",
            "event_history",
            "sponsor_track_record",
            "designation",
            "peer_set",
            "disclosure_behaviour",
            "listing",
        ),
        ("gold/feature_panel.csv", "gold/event_study.csv"),
    ),
}

# Relationship types (Ontology §3.3, Horizon Scanning H4.2).
RELATIONSHIP_TYPES = (
    "sponsors",
    "co_sponsors",
    "licenses_to",
    "licenses_from",
    "partners_with",
    "acquired",
    "acquired_by",
    "invested_in",
    "founded",
    "supplies",
    "affiliated_with",
    "develops",
    "targets",
    "collaborates_with",
    "presented_at",
    "funded_by",
    # v4 typed edges (Ontology v5 §3.3), names declared at gate L2; the
    # relationships table change (type/date/source columns) lands at 2.10.
    "exclusive_commercial_partner",
    "distributes_for",
    "customer_of",
    "holds_stake_in",
)

# Event classes and outcome states (FDA Catalyst Research v2 §4; binding
# for both models per Ontology §3.6).
EVENT_CLASSES = {
    "regulatory_decision": (
        "approval",
        "approval_narrowed_label",
        "crl",
        "extension",
        "missed_date",
    ),
    "regulatory_meeting": ("positive_vote", "negative_vote", "mixed_vote"),
    "filing_milestone": ("accepted", "refused_to_file", "standard_review", "priority_review"),
    "designation": ("granted",),
    "clinical_readout": ("positive", "negative", "mixed"),
    "post_crl_path": ("type_a_meeting", "resubmission", "class_1", "class_2", "new_pdufa"),
    "post_approval": (
        "label_expansion",
        "safety_communication",
        "boxed_warning",
        "withdrawal",
        "rems_change",
    ),
    "delay_timing": ("pdufa_extension", "review_delay", "government_shutdown"),
    "financing_overlay": ("atm_shelf", "offering"),
    # v4 event classes (Ontology v5 §3.6), declared at gate 1.4 by decision
    # 2026-08-31 so the event table's vocabulary is complete from birth.
    # No outcome states are defined yet and no writer exists at 1.4: the
    # deal/stake classes gain writers at gate L2, reimbursement and non-FDA
    # clearances at their own gates, as the Implementation Plan states.
    "reimbursement_decision": (),
    "regulatory_clearance_non_fda": (),
    "acquisition_announced": (),
    "acquisition_closed": (),
    "acquisition_terminated": (),
    "stake_purchase": (),
    "takeover_interest_reported": (),
}
CRL_DEFICIENCY_TYPES = ("manufacturing_cmc", "efficacy", "safety", "other")
DESIGNATIONS = ("fast_track", "breakthrough", "rmat", "orphan", "priority_review", "accelerated")

# Acquisition objectives (Ontology §4, P4).
OBJECTIVES = ("O1", "O2", "O3", "O4", "O5", "O6", "O7", "O8")

# Deal-aspect vocabulary (Ontology v5 §3.10; gate L2) and the product
# continuum (§3.2 assets attribute group).
ASPECTS = (
    "prior_commercial_relationship",
    "prior_equity_stake",
    "continuum_extension",
    "complementary_data_asset",
    "mechanism_or_target_gap",
    "therapeutic_area_overlap",
    "reimbursement_catalyst",
    "buyer_stated_priority_match",
    "competing_stakeholder",
    "consideration_type",
    "target_revenue_growth",
    "target_profitability",
    "buyer_financing_capacity",
    "patent_cliff_pressure",
    "category_consolidation",
)
ASPECT_METHODS = ("stated", "derived", "manual")
CONTINUUM_STEPS = ("risk", "diagnosis", "treatment_selection", "monitoring")

# ---------------------------------------------------------------- allowed values
# Closed sets defined in code today (source module named per set).
EVENT_KINDS = ("Approval", "Rejection")  # sources/fda.py
APPROVAL_OUTCOMES = ("New drug", "New indication")  # sources/fda.py
ROLES = ("target", "acquirer", "unknown")  # labels._assemble
VERIFIED = ("", "auto", "yes")  # labels.verify_fill / build_ma_events
CEASED = ("yes", "no", "too-recent")  # labels.still_filing_after
REL_KINDS = ("Trial collaboration", "Deal")  # pipeline.build_relationships
AGREEMENT_TYPES = (  # sources/counterparty.AGREEMENT_TYPES labels + fallback
    "License",
    "Collaboration",
    "Supply/Manufacturing",
    "Distribution/Commercial",
    "Asset purchase",
    "Merger/Acquisition",
    "Stake purchase",
    "Financing",
    "Settlement/Legal",
    "Lease",
    "Employment",
    "Other",
)
PARTNER_TYPES = (  # network.TYPE_RULES labels + CLASS_MAP values + fallback
    "CRO",
    "CDMO/Manufacturing",
    "Diagnostics/Lab",
    "Device/Delivery",
    "Imaging",
    "Academic",
    "Foundation/Nonprofit",
    "Government",
    "Industry",
    "Industry (unclassified)",
    "Network",
    "Individual",
    "Other",
)
TTM_BASES = ("", "annual", "annualized-Q1", "annualized-Q2", "annualized-Q3")  # features.py
BENCHMARKS = ("XBI", "none")  # study.py
YES_BLANK = ("", "yes")
LABEL_SOURCE_RE = re.compile(r"^$|^verified$|^proposed-c\d+$")  # labels.build_label_panel


# ---------------------------------------------------------------- table map
@dataclass(frozen=True)
class Table:
    """One CSV written by the package.

    path      relative to the data root, e.g. "silver/events.csv"
    columns   required header, in order (must equal the file header prefix)
    optional  columns that later pipeline stages may append, in order
    key       columns whose tuple must be unique across rows
    types     column -> type tag (see module docstring)
    enums     column -> allowed values
    writer    the command that writes the file (documentation only)
    planned   declared by design but not yet written by any command
    """

    path: str
    columns: tuple[str, ...]
    writer: str = ""
    optional: tuple[str, ...] = ()
    key: tuple[str, ...] = ()
    types: dict[str, str] = field(default_factory=dict)
    enums: dict[str, tuple[str, ...]] = field(default_factory=dict)
    planned: bool = False


_STUDY_METRICS = (
    "CAR_m1_p1",
    "CAR_0_p1",
    "CAR_m5_p5",
    "T0Gap",
    "T0Intraday",
    "AbnVolume",
    "VolShift",
    "Drift10",
)

# fmt: off
COMPANY_COLS = (
    "IID", "Name", "Ticker", "Created", "Description", "CIK", "SIC", "SICDescription",
    "Exchange", "StateOfIncorporation", "FDAAliases", "CTGovName",
)
EVENT_COLS = (
    "IID", "Name", "Event", "Date", "AppNo", "Drug", "Outcome", "Priority", "ClassCode", "SubType",
)
PRICE_COLS = ("IID", "Ticker", "Date", "Open", "High", "Low", "Close", "AdjClose", "Volume")
TRIAL_COLS = (
    "IID", "Company", "NCTId", "Sponsor", "SponsorClass", "Title", "Phase", "Status", "StudyType",
    "Conditions", "Drugs", "Interventions", "Enrollment", "Collaborators", "CollaboratorClasses",
    "CollaboratorCount", "StartDate", "PrimaryCompletion", "CompletionDate", "LastUpdate",
)
FIN_COLS = (
    "IID", "Company", "CIK", "PeriodEnd", "Currency", "Form", "FY", "FP", "Cash",
    "ShortTermInvestments", "Revenue", "RnD", "OpEx", "OperatingIncome", "NetIncome",
    "TotalAssets", "TotalLiabilities", "Equity", "LongTermDebt", "NetCashOperating",
    "SharesOutstanding", "Accession", "Filed",
)
SNAP_COLS = (
    "IID", "Company", "Ticker", "CIK", "CashAsOf", "Cash", "ShortTermInvestments", "TotalCash",
    "Revenue", "RnD", "LongTermDebt", "SharesOutstanding", "NetCashOperating", "OCFAsOf",
    "TTMMethod", "BurnAnnual", "RunwayMonths", "Periods",
)
PARTNER_COLS = (
    "IID", "Ticker", "Company", "Collaborator", "CollaboratorKey", "Type", "CTGovClass", "Trials",
    "Phases", "TherapyAreas", "FirstTrial", "LastTrial",
)
PSUM_COLS = (
    "IID", "Ticker", "Company", "TotalPartners", "Industry (unclassified)", "CRO",
    "CDMO/Manufacturing", "Diagnostics/Lab", "Device/Delivery", "Imaging", "Academic",
    "Foundation/Nonprofit", "Government", "Network", "Other",
)
REL_COLS = (
    "IID", "Ticker", "Company", "Partner", "PartnerKey", "PartnerIID", "PartnerType", "RelKind",
    "AgreementType", "Count", "FirstDate", "LastDate", "TherapyAreas", "Evidence",
)
# Ontology §3.3 typed edge columns: declared here (gate 0.1), added to the
# table at gate 2.10 (decision 2026-08-30).
REL_TYPED_COLS = ("type", "date", "source")
DEAL_COLS = (
    "IID", "Company", "Ticker", "CIK", "FilingDate", "ReportDate", "Item", "EventType", "Form",
    "Accession", "AllItems", "AcceptedAt", "PrimaryDoc", "FilingURL", "IndexURL",
)
CP_COLS = (
    "IID", "Company", "Ticker", "FilingDate", "Item", "EventType", "AgreementType",
    "Counterparty", "Method", "Accession", "FilingURL",
)
UNIVERSE_COLS = (
    "CIK", "Name", "Tickers", "Exchanges", "SIC", "FirstAnnualInWindow", "LastFilingDate",
    "Delisted", "DelistEvidence", "InDevSet", "InclusionRule", "EntryDate",
)
MA_COLS = (
    "FilerIID", "Filer", "FilerTicker", "Role", "Counterparty", "CounterpartyIID", "AnnounceDate",
    "CompletionDate", "Status", "S1_MergerRow", "S2_ProxyForms", "S3_CompletionNamed",
    "S4_Delisting", "S5_CeasedFiling", "Confidence", "Verified", "VerifiedAcquirer",
    "VerifiedNote", "Evidence",
)
VERIFIED_COLS = (
    "FilerTicker", "AnnounceDate", "Acquirer", "PricePerShare", "DealValue", "Status", "Note",
    "Source",
)
HARVEST_COLS = (
    "CIK", "Name", "Tickers", "Delisted", "AnnounceDate", "ProxyForms", "Form25Date",
    "CeasedFiling", "Confidence", "Verified", "Acquirer", "Note",
)
QA_EXTRA_COLS = ("AgreementDate", "EventClass", "QAFlag")
QA_COLS = HARVEST_COLS + QA_EXTRA_COLS
PATENT_COLS = ("IID", "PatentId", "PatentDate", "FilingDate", "CPCSubclass", "AssigneeRaw")
DRUG_TARGET_COLS = (
    "IID", "DrugNameRaw", "ChEMBLId", "ChEMBLName", "TargetName", "TargetType", "FirstSeen",
)
PANEL_COLS = (
    "IID", "Ticker", "Company", "QuarterEnd", "AcquiredNext12m", "AcquiredNext24m",
    "MadeAcquisition12m", "AnnounceDate", "Acquirer", "LabelSource",
)
FEATURE_COLS = (
    "IID", "Ticker", "Company", "QuarterEnd",
    "FinPeriodEnd", "FinAgeDays", "Currency", "Cash", "STI", "CashSTI", "Revenue", "RnD",
    "NetIncome", "TotalAssets", "TotalLiabilities", "Equity", "LongTermDebt",
    "SharesOutstanding", "OCF_TTM", "TTMBasis", "BurnAnnual", "RunwayMonths",
    "TrialsTotal", "TrialsPh1", "TrialsPh2", "TrialsPh3", "TrialsPh4", "LeadPhase",
    "TrialsStarted12m",
    "OrigApprovalsEver", "HasApprovedDrug", "Approvals12m", "Rejections12m",
    "DaysSinceLastFDAEvent",
    "CAR12m_mean", "Drift12m_mean", "FDAEventsWithCAR12m",
    "RelTotal", "RelTrial", "RelDeal", "RelInUniverse", "Deals24m", "LicensesEver", "CollabsEver",
    "dCash4q", "dShares4q", "RnDIntensity", "CashToAssets", "AgeYears", "Ph3Started24m",
    "FirstApprovalRecent24m", "HotTA", "FDAEventsEver",
    "PriceQ", "MarketCap", "Drawdown52w",
)
MODEL_COLS = FEATURE_COLS + (
    "AcquiredNext12m", "AcquiredNext24m", "MadeAcquisition12m", "AnnounceDate", "Acquirer",
    "LabelSource",
)
STUDY_COLS = (
    "IID", "Company", "Ticker", "Event", "Outcome", "Drug", "AppNo", "EventDate", "T0Date",
    "Benchmark", "Beta",
) + _STUDY_METRICS
STUDY_SUMMARY_COLS = ("OutcomeClass", "N") + tuple(
    f"{m}_{s}" for m in _STUDY_METRICS for s in ("mean", "median")
)
PRED_COLS = (
    "Rank", "Ticker", "Company", "QuarterEnd", "TargetScore", "ScoreBreakdown", "Acquirer1",
    "Fit1", "Acquirer2", "Fit2", "Acquirer3", "Fit3", "AcqLOE1", "AcqLOE2", "AcqLOE3",
    "KnownOutcome",
)
PAIR_FEATURE_COLS = ("IID", "YearEnd", "MaxSimToAcq")
ACTIVIST_COLS = ("IID", "Date")
FIT_SCORE_COLS = ("Ticker", "Company", "QuarterEnd", "Score", "AcquiredNext12m")
WINDOW_COLS = (
    "IID", "AppNo", "Drug", "Event", "RelDay", "Date", "Open", "High", "Low", "Close",
    "AdjClose", "Volume", "PctFromT0",
)
CALENDAR_COLS = ("Date", "Stage", "Drug", "Detail", "Status", "Ref", "Source")
# Run ledger (P17; gate 0.3). MLflow's structure: one runs row, and
# key-value rows for params, metrics and artefacts. Append-only tables.
RUN_COLS = (
    "run_id", "model", "version", "command", "run_at", "duration_s", "status", "operator",
    "code_ref", "env_hash", "data_snapshot_hash", "inputs", "objective", "holdout_access",
    "source", "note", "run_type",
)
RUN_PARAM_COLS = ("run_id", "name", "value")
RUN_METRIC_COLS = ("run_id", "group", "name", "value")
RUN_ARTEFACT_COLS = ("run_id", "path", "sha256")
RUN_STATUSES = ("ok", "failed", "empty")
RUN_SOURCES = ("run", "historical-file", "project-status")
RUN_TYPES = ("", "predict", "fit", "evaluation")  # blank: recorded before gate 0.4

# Research library / file room (Ontology v5 §3.9; gate L1) -----------------
REF_TYPES = (
    "sec_filing", "press_release", "news_article", "research_paper",
    "transcript", "investor_letter", "analyst_note", "regulatory_notice",
    "web_page", "video", "dataset", "book", "other",
)
CAPTURE_KINDS = (
    "fetched_html", "fetched_pdf", "fetched_text", "printed_pdf",
    "uploaded_file", "media_file", "captions", "wayback",
)
LINK_ROLES = (
    "subject", "acquirer", "target", "third_party", "comparable",
    "commentary", "author_affiliation",
)
REFERENCE_COLS = (
    "ref_id", "ref_type", "url", "doi", "pmid", "sec_accession", "isbn",
    "title", "authors", "publisher", "published_at", "accessed_at",
    "language", "access", "source_system", "source_key", "added_by",
    "note", "status", "merged_into",
)
CAPTURE_COLS = (
    "capture_id", "ref_id", "kind", "path", "bytes", "ext", "mime",
    "captured_at", "capture_method", "archive_url", "archive_ts",
    "status", "status_reason",
)
REFERENCE_LINK_COLS = (
    "ref_id", "key_type", "entity_key", "role", "added_at", "added_by",
)

# Event table (Ontology §3.6; live since gate 1.4). Date semantics, decided
# 2026-08-31 at the 1.4 scope: `event_date` is the date the action occurred
# (blank on forward rows); `scheduled_date` is the goal or expected date and
# is never used for realized action dates.
EVENT_TABLE_COLS = (
    "event_id", "entity_key", "asset", "indication", "event_class", "event_date",
    "scheduled_date", "disclosure_datetime", "outcome_state", "outcome_subtype",
    "source_url", "provenance", "first_seen", "last_verified",
)
# Forward-row columns (gate 1.5a; optional so 1.4 rows stay conformant).
# A fuzzy timing statement is a range plus its verbatim language, never an
# invented exact date; a moved date inserts a new row and marks the old one
# superseded; confidence_tier is rule-driven by source class.
EVENT_FORWARD_COLS = (
    "scheduled_date_end", "date_precision", "date_raw", "status", "confidence_tier",
)
DATE_PRECISIONS = ("day", "month", "quarter", "half", "year")
EVENT_STATUSES = ("", "superseded")
CONFIDENCE_TIERS = ("", "A", "B", "C", "D")  # A FDA page, B SEC filing, C CT.gov estimate, D aggregator-only
# Mined-candidate ledger (gate 1.5b): one row per text window the miner
# examined, accepted or rejected, with exact grounding (capture hash +
# character offsets into the normalized text), TimeML-style value/precision/
# modifier, ConText-style assertion status, and the rule version — so no
# examined statement is ever discarded and every rule change is diffable.
MINED_CANDIDATE_COLS = (
    "candidate_id", "entity_key", "adsh", "doc", "form", "file_date", "items", "doc_id",
    "char_start", "char_end", "anchor_kind", "anchor_text", "phrase", "phrase_start",
    "date_start", "date_end", "date_precision", "date_mod", "anchored", "assertion",
    "outcome_words", "rule_version", "decision", "reason", "mined_at",
)
ANCHOR_KINDS = ("pdufa", "readout")
ASSERTIONS = ("affirmed", "negated", "historical", "hypothetical")
DATE_MODS = ("", "early", "mid", "late", "approx")
CANDIDATE_DECISIONS = ("accepted", "rejected")
# Human verdicts on ledger candidates (gate 1.5b-eval; reused by the L3 review queue).
CANDIDATE_REVIEW_COLS = (
    "review_id", "candidate_id", "rule_version", "verdict", "reviewer", "note", "reviewed_at",
)
REVIEW_VERDICTS = ("correct", "wrong", "unsure")
# Planned tables (Ontology §3.4, §3.7); built at gates 2.9, 2.10.
MANUAL_ENTITY_COLS = (
    "entity_key", "name", "aliases", "type", "listed", "has_prices", "cik", "ticker", "hq",
    "source", "entered_by", "entered_on", "note",
)
MANUAL_ATTRIBUTE_COLS = (
    "entity_key", "attribute", "value", "valid_from", "source", "entered_by", "entered_on", "note",
)
MANUAL_NOTE_COLS = (
    "note_id", "entity_key", "event_id", "date", "title", "text", "source_url", "entered_by",
    "entered_on", "tags",
)
BENCHMARK_COLS = ("name", "type", "constituents_or_ticker")
# Deal dossier (Ontology v5 §3.10; gate L2). P19: every row carries the
# doc_id (capture hash in the research library) and the span it was read
# from; the seed loader verifies the span occurs in the cited capture.
DEAL_TERM_COLS = ("deal_id", "field", "value", "doc_id", "span")
DEAL_TIMELINE_COLS = ("deal_id", "step_date", "step_type", "description", "doc_id", "span")
DEAL_RATIONALE_COLS = ("deal_id", "seq", "stated_by", "statement", "doc_id", "span")
DEAL_ASPECT_COLS = ("deal_id", "aspect", "value", "method", "confidence", "doc_id", "span")
DEAL_COMPARABLE_COLS = ("deal_id", "comparable_deal_id", "basis", "doc_id", "span")
# Entity attributes v4 (Ontology v5 §3.2; gate L2).
EQUITY_STAKE_COLS = ("holder_key", "issuer_key", "percent", "as_of", "doc_id", "span")
# Gate F1 (Q2, approved 2026-09-02): everything cheap to take from the cover
# page, recorded to the analyst's standard; raw filings stay in the library.
EQUITY_STAKE_F1_COLS = (
    "form", "filing_date", "shares", "owner_name", "accession", "cusip", "item4_text",
)
STATED_PRIORITY_COLS = ("entity_key", "stated_at", "category", "statement", "doc_id", "span")
ASSET_COLS = (
    "entity_key", "product", "category", "continuum_step", "modality", "indications",
    "regulatory_status", "reimbursement_status", "doc_id", "span",
)
# fmt: on

_DATE_COLS_TRIALS = {
    c: "date" for c in ("StartDate", "PrimaryCompletion", "CompletionDate", "LastUpdate")
}
_FIN_NUM = {
    c: "float"
    for c in (
        "Cash",
        "ShortTermInvestments",
        "Revenue",
        "RnD",
        "OpEx",
        "OperatingIncome",
        "NetIncome",
        "TotalAssets",
        "TotalLiabilities",
        "Equity",
        "LongTermDebt",
        "NetCashOperating",
        "SharesOutstanding",
    )
}
_FEATURE_FLOAT = (
    "Cash",
    "STI",
    "CashSTI",
    "Revenue",
    "RnD",
    "NetIncome",
    "TotalAssets",
    "TotalLiabilities",
    "Equity",
    "LongTermDebt",
    "SharesOutstanding",
    "OCF_TTM",
    "BurnAnnual",
    "RunwayMonths",
    "CAR12m_mean",
    "Drift12m_mean",
    "dCash4q",
    "dShares4q",
    "RnDIntensity",
    "CashToAssets",
    "AgeYears",
    "PriceQ",
    "MarketCap",
    "Drawdown52w",
)
_FEATURE_INT = (
    "FinAgeDays",
    "TrialsTotal",
    "TrialsPh1",
    "TrialsPh2",
    "TrialsPh3",
    "TrialsPh4",
    "LeadPhase",
    "TrialsStarted12m",
    "OrigApprovalsEver",
    "HasApprovedDrug",
    "Approvals12m",
    "Rejections12m",
    "DaysSinceLastFDAEvent",
    "FDAEventsWithCAR12m",
    "RelTotal",
    "RelTrial",
    "RelDeal",
    "RelInUniverse",
    "Deals24m",
    "LicensesEver",
    "CollabsEver",
    "Ph3Started24m",
    "FirstApprovalRecent24m",
    "HotTA",
    "FDAEventsEver",
)
_FEATURE_TYPES = {
    "IID": "int",
    "QuarterEnd": "date",
    "FinPeriodEnd": "date",
    "TTMBasis": "enum",
    **{c: "float" for c in _FEATURE_FLOAT},
    **{c: "int" for c in _FEATURE_INT},
}
_LABEL_TYPES = {
    "AcquiredNext12m": "flag01",
    "AcquiredNext24m": "flag01",
    "MadeAcquisition12m": "flag01",
    "AnnounceDate": "date",
}

TABLES: tuple[Table, ...] = (
    # ---- silver -----------------------------------------------------
    Table(
        "silver/universe.csv",
        UNIVERSE_COLS,
        "universe",
        key=("CIK",),
        types={
            "FirstAnnualInWindow": "date",
            "LastFilingDate": "date",
            "EntryDate": "date",
            "Delisted": "enum",
            "InDevSet": "enum",
        },
        enums={"Delisted": YES_BLANK, "InDevSet": YES_BLANK},
    ),
    Table(
        "silver/companies.csv",
        COMPANY_COLS,
        "add / ingest / backfill",
        key=("IID",),
        types={"IID": "int", "Created": "date"},
    ),
    Table(
        "silver/events.csv",
        EVENT_COLS,
        "events / events-all / ingest",
        key=("IID", "Event", "Date", "AppNo"),
        types={"IID": "int", "Date": "date", "Event": "enum"},
        enums={"Event": EVENT_KINDS},
    ),
    Table(
        "silver/trials.csv",
        TRIAL_COLS,
        "trials / trials-all / ingest",
        key=("IID", "NCTId"),
        types={"IID": "int", "CollaboratorCount": "int", **_DATE_COLS_TRIALS},
    ),
    Table(
        "silver/financials.csv",
        FIN_COLS,
        "fin / fin-all / ingest",
        key=("IID", "PeriodEnd"),
        types={"IID": "int", "PeriodEnd": "date", "Filed": "date", **_FIN_NUM},
    ),
    Table(
        "silver/financial_snapshot.csv",
        SNAP_COLS,
        "snapshot",
        key=("IID",),
        types={
            "IID": "int",
            "CashAsOf": "date",
            "OCFAsOf": "date",
            "Periods": "int",
            "RunwayMonths": "float",
            "BurnAnnual": "float",
        },
    ),
    Table(
        "silver/partners.csv",
        PARTNER_COLS,
        "partners",
        key=("IID", "CollaboratorKey"),
        types={
            "IID": "int",
            "Trials": "int",
            "FirstTrial": "date",
            "LastTrial": "date",
            "Type": "enum",
        },
        enums={"Type": PARTNER_TYPES},
    ),
    Table(
        "silver/partner_summary.csv",
        PSUM_COLS,
        "partners",
        key=("IID",),
        types={"IID": "int", **{c: "int" for c in PSUM_COLS[3:]}},
    ),
    Table(
        "silver/deals.csv",
        DEAL_COLS,
        "deals / deals-all / ingest",
        key=("IID", "Accession", "Item"),
        types={
            "IID": "int",
            "FilingDate": "date",
            "ReportDate": "date",
            "AcceptedAt": "datetime",
            "Item": "enum",
        },
        enums={"Item": ("1.01", "1.02", "2.01")},
    ),
    Table(
        "silver/deal_counterparties.csv",
        CP_COLS,
        "cparty / cparty-all",
        key=("IID", "Accession", "Counterparty"),
        types={"IID": "int", "FilingDate": "date", "AgreementType": "enum"},
        enums={"AgreementType": AGREEMENT_TYPES},
    ),
    Table(
        "silver/relationships.csv",
        REL_COLS,
        "relationships",
        optional=REL_TYPED_COLS,  # gate 2.10
        key=("IID", "PartnerKey", "RelKind", "AgreementType"),
        types={
            "IID": "int",
            "PartnerIID": "int",
            "Count": "int",
            "FirstDate": "date",
            "LastDate": "date",
            "RelKind": "enum",
            "AgreementType": "enum",
            "PartnerType": "enum",
        },
        enums={
            "RelKind": REL_KINDS,
            "AgreementType": ("",) + AGREEMENT_TYPES,
            "PartnerType": PARTNER_TYPES,
        },
    ),
    Table(
        "silver/ma_events.csv",
        MA_COLS,
        "labels",
        optional=("deal_id",),  # gate L2: dossier index key; populated from 2.9′
        types={
            "FilerIID": "int",
            "CounterpartyIID": "int",
            "AnnounceDate": "date",
            "CompletionDate": "date",
            "Confidence": "int",
            "Role": "enum",
            "Verified": "enum",
            "S5_CeasedFiling": "enum",
        },
        # S5 is blank on rows that merged_events() builds from the universe
        # harvest (labels.py: no S1-S5 keys on those rows), a fact of the
        # writer, not a data defect; recorded at gate 0.1 from the first live run.
        enums={"Role": ROLES, "Verified": VERIFIED, "S5_CeasedFiling": ("",) + CEASED},
    ),
    Table(
        "silver/ma_events_verified.csv",
        VERIFIED_COLS,
        "hand-curated overlay",
        types={"AnnounceDate": "date"},
    ),
    Table(
        "silver/ma_events_universe.csv",
        HARVEST_COLS,
        "harvest / verify-fill / qa / qa-corroborate",
        optional=QA_EXTRA_COLS + ("Corroboration",),
        key=("CIK", "AnnounceDate"),
        types={
            "AnnounceDate": "date",
            "Form25Date": "date",
            "Confidence": "int",
            "CeasedFiling": "enum",
            "Verified": "enum",
            "AgreementDate": "date",
        },
        enums={"CeasedFiling": CEASED, "Verified": VERIFIED},
    ),
    Table(
        "silver/patents.csv",
        PATENT_COLS,
        "patents-import",
        types={"PatentDate": "date", "FilingDate": "date"},
    ),
    Table(
        "silver/drug_targets.csv",
        DRUG_TARGET_COLS,
        "chembl-ingest",
        key=("IID", "ChEMBLId", "TargetName"),
        types={"IID": "int", "FirstSeen": "date"},
    ),
    # ---- gold -------------------------------------------------------
    Table(
        "gold/label_panel.csv",
        PANEL_COLS,
        "labels",
        key=("IID", "QuarterEnd"),
        types={"IID": "int", "QuarterEnd": "date", **_LABEL_TYPES},
    ),
    Table(
        "gold/feature_panel.csv",
        FEATURE_COLS,
        "features",
        key=("IID", "QuarterEnd"),
        types=_FEATURE_TYPES,
        enums={"TTMBasis": TTM_BASES},
    ),
    Table(
        "gold/model_panel.csv",
        MODEL_COLS,
        "features",
        key=("IID", "QuarterEnd"),
        # label flags may be blank on quarters that have no label_panel row
        # (features.join_with_labels writes '' when the join misses)
        types={
            **_FEATURE_TYPES,
            "AcquiredNext12m": "enum",
            "AcquiredNext24m": "enum",
            "MadeAcquisition12m": "enum",
            "AnnounceDate": "date",
        },
        enums={
            "TTMBasis": TTM_BASES,
            "AcquiredNext12m": ("", "0", "1"),
            "AcquiredNext24m": ("", "0", "1"),
            "MadeAcquisition12m": ("", "0", "1"),
        },
    ),
    Table(
        "gold/event_study.csv",
        STUDY_COLS,
        "study-all",
        key=("IID", "Event", "EventDate", "AppNo"),
        types={
            "IID": "int",
            "EventDate": "date",
            "T0Date": "date",
            "Beta": "float",
            "Event": "enum",
            "Benchmark": "enum",
            **{m: "float" for m in _STUDY_METRICS},
        },
        enums={"Event": EVENT_KINDS, "Benchmark": BENCHMARKS},
    ),
    Table(
        "gold/event_study_summary.csv",
        STUDY_SUMMARY_COLS,
        "study-all",
        key=("OutcomeClass",),
        types={"N": "int", **{c: "float" for c in STUDY_SUMMARY_COLS[2:]}},
    ),
    Table(
        "gold/qa_worklist.csv",
        QA_COLS + ("HumanVerdict",),
        "qa / qa-corroborate / qa-wiki",
        optional=("Corroboration",),
        types={
            "AnnounceDate": "date",
            "Form25Date": "date",
            "Confidence": "int",
            "CeasedFiling": "enum",
            "Verified": "enum",
            "AgreementDate": "date",
        },
        enums={"CeasedFiling": CEASED, "Verified": VERIFIED},
    ),
    Table(
        "gold/pair_feature.csv",
        PAIR_FEATURE_COLS,
        "pairs",
        key=("IID", "YearEnd"),
        types={"IID": "int", "YearEnd": "date", "MaxSimToAcq": "float"},
    ),
    Table(
        "gold/activist_13d.csv",
        ACTIVIST_COLS,
        "develop (cache)",
        types={"IID": "int", "Date": "date"},
    ),
    Table(
        "gold/fit_scores.csv",
        FIT_SCORE_COLS,
        "fit",
        types={"QuarterEnd": "date", "Score": "float", "AcquiredNext12m": "flag01"},
    ),
    Table(
        "gold/ma_predictions.csv",
        PRED_COLS,
        "predict",
        key=("Rank",),
        types={
            "Rank": "int",
            "QuarterEnd": "date",
            "TargetScore": "float",
            "Fit1": "float",
            "Fit2": "float",
            "Fit3": "float",
        },
    ),
    Table(
        "gold/window.csv",
        WINDOW_COLS,
        "window",
        types={"IID": "int", "RelDay": "int", "Date": "date"},
    ),
    # ---- ledger (gold; append-only) ----------------------------------
    Table(
        "gold/runs.csv",
        RUN_COLS,
        "results.record (every model run); ledger-seed (legacy rows)",
        key=("run_id",),
        types={
            "run_at": "datetime",
            "duration_s": "float",
            "status": "enum",
            "source": "enum",
            "holdout_access": "enum",
            "run_type": "enum",
        },
        enums={
            "status": RUN_STATUSES,
            "source": RUN_SOURCES,
            "holdout_access": ("", "yes"),
            "run_type": RUN_TYPES,
        },
    ),
    Table("gold/run_params.csv", RUN_PARAM_COLS, "results.record", key=("run_id", "name")),
    Table(
        "gold/run_metrics.csv", RUN_METRIC_COLS, "results.record", key=("run_id", "group", "name")
    ),
    Table("gold/run_artefacts.csv", RUN_ARTEFACT_COLS, "results.record", key=("run_id", "path")),
    Table(
        "silver/references.csv",
        REFERENCE_COLS,
        "library",
        key=("ref_id",),
        enums={
            "ref_type": REF_TYPES,
            "access": ("", "open", "paywalled", "private"),
            "status": ("active", "retired"),
        },
    ),
    Table(
        "silver/captures.csv",
        CAPTURE_COLS,
        "library",
        key=("capture_id", "ref_id"),
        types={"bytes": "int"},
        enums={"kind": CAPTURE_KINDS, "status": ("active", "retired")},
    ),
    Table(
        "silver/reference_links.csv",
        REFERENCE_LINK_COLS,
        "library",
        key=("ref_id", "key_type", "entity_key", "role"),
        enums={"key_type": ("IID", "CIK"), "role": LINK_ROLES},
    ),
    Table(
        "silver/events_table.csv",
        EVENT_TABLE_COLS,
        "events-migrate (gate 1.4); calendar-forward trials|adcom (1.5a); miner (1.5b)",
        optional=EVENT_FORWARD_COLS,
        key=("event_id",),
        types={
            "event_date": "date",
            "scheduled_date": "date",
            "scheduled_date_end": "date",
            "disclosure_datetime": "datetime",
            "first_seen": "datetime",
            "last_verified": "datetime",
            "event_class": "enum",
            "date_precision": "enum",
            "status": "enum",
            "confidence_tier": "enum",
        },
        enums={
            "event_class": tuple(EVENT_CLASSES),
            "date_precision": ("",) + DATE_PRECISIONS,
            "status": EVENT_STATUSES,
            "confidence_tier": CONFIDENCE_TIERS,
        },
    ),
    Table(
        "silver/deal_terms.csv",
        DEAL_TERM_COLS,
        "dossier-seed (L2); deal analyser (L3)",
        key=("deal_id", "field"),
    ),
    Table(
        "silver/deal_timeline.csv",
        DEAL_TIMELINE_COLS,
        "dossier-seed (L2); deal analyser (L3)",
        key=("deal_id", "step_date", "step_type"),
        types={"step_date": "date"},
    ),
    Table(
        "silver/deal_rationale.csv",
        DEAL_RATIONALE_COLS,
        "dossier-seed (L2); deal analyser (L3)",
        key=("deal_id", "seq"),
        types={"seq": "int"},
    ),
    Table(
        "silver/deal_aspects.csv",
        DEAL_ASPECT_COLS,
        "dossier-seed (L2); deal analyser (L3)",
        key=("deal_id", "aspect"),
        types={"aspect": "enum", "method": "enum", "confidence": "float"},
        enums={"aspect": ASPECTS, "method": ASPECT_METHODS},
    ),
    Table(
        "silver/deal_comparables.csv",
        DEAL_COMPARABLE_COLS,
        "dossier-seed (L2); deal analyser (L3)",
        key=("deal_id", "comparable_deal_id"),
    ),
    Table(
        "silver/equity_stakes.csv",
        EQUITY_STAKE_COLS,
        "dossier-seed (L2); stakes adapter (L3); stakes run (F1)",
        optional=EQUITY_STAKE_F1_COLS,  # gate F1 (Q2): analyst-standard context
        key=("holder_key", "issuer_key", "as_of"),
        types={"percent": "float", "as_of": "date"},
    ),
    Table(
        "silver/stated_priorities.csv",
        STATED_PRIORITY_COLS,
        "dossier-seed (L2); library sources",
        key=("entity_key", "stated_at", "category"),
        types={"stated_at": "date"},
    ),
    Table(
        "silver/assets.csv",
        ASSET_COLS,
        "dossier-seed (L2); manual layer (2.10)",
        key=("entity_key", "product"),
        types={"continuum_step": "enum"},
        enums={"continuum_step": ("",) + CONTINUUM_STEPS},
    ),
    Table(
        "silver/mined_candidates.csv",
        MINED_CANDIDATE_COLS,
        "mine-pdufa run (1.5b); realized/delay writers read it at 1.5c",
        key=("candidate_id",),
        types={
            "file_date": "date",
            "char_start": "int",
            "char_end": "int",
            "phrase_start": "int",
            "date_start": "date",
            "date_end": "date",
            "anchored": "int",
            "mined_at": "datetime",
            "anchor_kind": "enum",
            "date_precision": "enum",
            "date_mod": "enum",
            "assertion": "enum",
            "decision": "enum",
        },
        enums={
            "anchor_kind": ANCHOR_KINDS,
            "date_precision": ("",) + DATE_PRECISIONS,
            "date_mod": DATE_MODS,
            "assertion": ASSERTIONS,
            "decision": CANDIDATE_DECISIONS,
        },
    ),
    Table(
        "silver/candidate_reviews.csv",
        CANDIDATE_REVIEW_COLS,
        "mine-pdufa judge (1.5b-eval); L3 review queue",
        key=("review_id",),
        types={"reviewed_at": "datetime", "verdict": "enum"},
        enums={"verdict": REVIEW_VERDICTS},
    ),
    # ---- planned (declared by design; no writer yet) ----------------
    Table(
        "silver/manual_entities.csv",
        MANUAL_ENTITY_COLS,
        "manual add-entity (2.10); consumers merge at their own gates",
        key=("entity_key",),
    ),
    Table(
        "silver/manual_attributes.csv",
        MANUAL_ATTRIBUTE_COLS,
        "manual add-attribute (2.10); precedence: manual over machine at merged reads",
        key=("entity_key", "attribute"),
        types={"valid_from": "date"},
    ),
    Table(
        "silver/manual_notes.csv",
        MANUAL_NOTE_COLS,
        "manual add-note (2.10)",
        key=("note_id",),
        types={"date": "date"},
    ),
    Table("silver/benchmarks.csv", BENCHMARK_COLS, "gate 2.9 (F9)", planned=True),
)

TABLE_BY_PATH = {t.path: t for t in TABLES}


# ---------------------------------------------------------------- validation
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _check_value(kind: str, v: str, allowed: tuple[str, ...] | None) -> bool:
    if kind == "int":
        return v == "" or re.fullmatch(r"-?\d+(\.0+)?", v) is not None
    if kind == "float":
        if v == "":
            return True
        try:
            float(v)
            return True
        except ValueError:
            return False
    if kind == "date":
        if v == "":
            return True
        if not _ISO_DATE.match(v):
            return False
        try:
            date.fromisoformat(v)
            return True
        except ValueError:
            return False
    if kind == "datetime":
        if v == "":
            return True
        try:
            datetime.fromisoformat(v.replace("Z", "+00:00"))
            return True
        except ValueError:
            return False
    if kind == "flag01":
        return v in ("0", "1")
    if kind == "enum":
        return allowed is not None and v in allowed
    return True


def validate_rows(t: Table, header: list[str], rows, max_examples: int = 3) -> dict:
    """Check a header and an iterable of row lists against a declaration.
    Shared by the CSV path (validate_table) and the database path
    (validate_db). Returns {"path", "status", "rows", "violations"}."""
    viol: list[str] = []
    n = len(t.columns)
    if tuple(header[:n]) != t.columns:
        viol.append(
            f"header: expected {list(t.columns)} as the first {n} columns, got {header[:n]}"
        )
        return {"path": t.path, "status": "violations", "rows": 0, "violations": viol}
    extra = header[n:]
    bad_extra = [c for c in extra if c not in t.optional]
    if bad_extra:
        viol.append(f"header: undeclared columns {bad_extra}")
    idx = {c: i for i, c in enumerate(header)}
    key_idx = [idx[c] for c in t.key if c in idx]
    seen: set[tuple] = set()
    type_bad: dict[str, list[str]] = {}
    n_rows = 0
    for line_no, row in enumerate(rows, start=2):
        n_rows += 1
        if len(row) != len(header):
            viol.append(f"line {line_no}: {len(row)} fields, header has {len(header)}")
            if len(viol) > 50:
                break
            continue
        if key_idx:
            k = tuple(row[i] for i in key_idx)
            if k in seen:
                type_bad.setdefault("__key__", []).append(f"line {line_no}: {k}")
            else:
                seen.add(k)
        for col, kind in t.types.items():
            i = idx.get(col)
            if i is None:
                continue
            v = (row[i] or "").strip()
            if kind == "enum":
                ok = _check_value(kind, v, t.enums.get(col))
            else:
                ok = _check_value(kind, v, None)
            if not ok:
                type_bad.setdefault(col, []).append(f"line {line_no}: {v!r}")
    for col, ex in type_bad.items():
        if col == "__key__":
            viol.append(f"key {list(t.key)}: {len(ex)} duplicate row(s), e.g. {ex[:max_examples]}")
        else:
            viol.append(
                f"column {col} ({t.types[col]}): {len(ex)} bad value(s), e.g. {ex[:max_examples]}"
            )
    return {
        "path": t.path,
        "status": "violations" if viol else "conformant",
        "rows": n_rows,
        "violations": viol,
    }


def validate_table(t: Table, root: Path, max_examples: int = 3) -> dict:
    """Check one CSV table on disk against its declaration (pre-migration
    files and fixtures). Status: conformant, violations, absent, planned."""
    p = root / t.path
    if t.planned:
        return {"path": t.path, "status": "planned", "rows": 0, "violations": []}
    if not p.exists():
        return {"path": t.path, "status": "absent", "rows": 0, "violations": []}
    with p.open(encoding="utf-8", newline="", errors="replace") as f:
        rd = csv.reader(f)
        header = next(rd, None) or []
        return validate_rows(t, header, rd, max_examples)


def validate_db(con, max_examples: int = 3) -> list[dict]:
    """Check every declared table present in the DuckDB database (P16).
    The database already enforces the declared constraints at write time;
    this re-checks stored rows independently, the same way the CSV path did."""
    from biointel import store

    out = []
    for t in TABLES:
        name = store.table_name(t.path)
        if t.planned:
            out.append({"path": name, "status": "planned", "rows": 0, "violations": []})
            continue
        if not store.has_table(name, con):
            out.append({"path": name, "status": "absent", "rows": 0, "violations": []})
            continue
        header = store.table_columns(name, con)
        sel = ", ".join('"' + c.replace('"', '""') + '"' for c in header)
        rows = con.execute(f'SELECT {sel} FROM "{name}" ORDER BY _rowid').fetchall()
        r = validate_rows(t, header, rows, max_examples)
        r["path"] = name
        out.append(r)
    return out


def validate_all(root: Path) -> list[dict]:
    return [validate_table(t, root) for t in TABLES]


def format_report(results: list[dict]) -> str:
    lines = []
    for r in results:
        if r["status"] == "conformant":
            lines.append(f"  OK        {r['path']:<36} {r['rows']:>8,} rows")
        elif r["status"] == "absent":
            lines.append(f"  absent    {r['path']}")
        elif r["status"] == "planned":
            lines.append(f"  planned   {r['path']}")
        else:
            lines.append(f"  VIOLATION {r['path']:<36} {r['rows']:>8,} rows")
            for v in r["violations"]:
                lines.append(f"              - {v}")
    n_ok = sum(1 for r in results if r["status"] == "conformant")
    n_bad = sum(1 for r in results if r["status"] == "violations")
    n_abs = sum(1 for r in results if r["status"] == "absent")
    n_pl = sum(1 for r in results if r["status"] == "planned")
    lines.append(
        f"validate: {n_ok} conformant, {n_bad} with violations, {n_abs} absent, "
        f"{n_pl} planned ({len(results)} declared)"
    )
    return "\n".join(lines)
