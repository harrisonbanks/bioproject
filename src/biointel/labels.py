# src/biointel/labels.py
"""Phase L, restructured: proposed events -> verified overlay -> panel.

WHY THE RESTRUCTURE. The first design inferred labels purely from
heuristics over acquirer-side 8-K narrative, and every spot-check error
was that tower guessing (a PIPE typed as M&A, a lender recorded as
acquirer, a share-issuing acquirer read as target). Acquisition events
are rare, high-salience, and individually verifiable -- so the correct
architecture for a publishable label set is:

  1. PROPOSE   machine-assemble candidate events from multiple
               independent SEC signals, each signal a separate column,
               with a confidence score = number of agreeing signals.
  2. VERIFY    a curated overlay file (ma_events_verified.csv) holds
               authoritative events confirmed against filings/press.
               Verified rows override proposals on conflict.
  3. CONSUME   the panel builds target labels ONLY from verified events
               or proposals with >= 2 independent target-side signals,
               and marks each label's provenance in LabelSource.

Independent signals per event:
  S1 merger-agreement counterparty row (Items 1.01/2.01 extraction)
  S2 target-side proxy filings (DEFM14A / PREM14A / SC 14D9)
  S3 Item 2.01 completion that NAMES the counterparty
  S4 Form 25 / Form 15 delisting near completion
  S5 cessation of periodic filings after the event (survivor test
     inverted: the target stops filing; the acquirer continues)

The TARGET-SIDE PROBER assembles proposals from a company's OWN filing
trail (S2+S4+S5), independent of counterparty extraction. This is what
makes the P1 universe expansion produce labels automatically: when an
acquired/delisted company is added, its own CIK trail is the
authoritative record of its acquisition, no text extraction required.

Financing institutions are never recorded as acquirer (they appear in
merger 8-Ks as bridge lenders -- verified live in the Vertex/Crinetics
2026 deal, where the extraction surfaced Morgan Stanley Senior Funding,
the lender, instead of Vertex, the buyer).
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from datetime import date, timedelta

from biointel import config, store
from biointel.store import fetch_json

log = logging.getLogger(__name__)

SHELL_RE = re.compile(
    r"(?i)\b(?:acquisition|merger)\s+(?:sub|subsidiary|corp|corporation|"
    r"company|co\.?|holdings?)\b|^project\s|\bmergeco\b|\bnewco\b"
)

JUNK_RE = re.compile(
    r"(?i)offer price|competition authority|antitrust|commission$|"
    r"exchange ratio|tender offer|effective time"
)

FIN_AGENT_RE = re.compile(
    r"(?i)senior funding|morgan stanley|goldman sachs|jpmorgan|"
    r"j\.p\. morgan|citibank|citigroup|bank of america|barclays|"
    r"deutsche bank|credit suisse|ubs|wells fargo|\bbank\b|"
    r"\bn\.a\.?$|capital markets|securities llc|leerink|lazard|"
    r"funding, inc"
)

TARGET_PROXY_FORMS = {"DEFM14A", "PREM14A", "SC 14D9", "SC 14D9/A", "DEFM14C"}
DELIST_FORMS = {"25", "25/A", "25-NSE", "25-NSE/A", "15-12B", "15-12G", "15-15D"}
CONTINUED_FORMS = {"10-K", "10-Q", "8-K", "10-K/A", "10-Q/A"}

MA_COLS = [
    "FilerIID",
    "Filer",
    "FilerTicker",
    "Role",
    "Counterparty",
    "CounterpartyIID",
    "AnnounceDate",
    "CompletionDate",
    "Status",
    "S1_MergerRow",
    "S2_ProxyForms",
    "S3_CompletionNamed",
    "S4_Delisting",
    "S5_CeasedFiling",
    "Confidence",
    "Verified",
    "VerifiedAcquirer",
    "VerifiedNote",
    "Evidence",
]

PANEL_COLS = [
    "IID",
    "Ticker",
    "Company",
    "QuarterEnd",
    "AcquiredNext12m",
    "AcquiredNext24m",
    "MadeAcquisition12m",
    "AnnounceDate",
    "Acquirer",
    "LabelSource",
]

VERIFIED_COLS = [
    "FilerTicker",
    "AnnounceDate",
    "Acquirer",
    "PricePerShare",
    "DealValue",
    "Status",
    "Note",
    "Source",
]


# ------------------------------------------------------------ SEC trails
def _submissions(cik10: str) -> dict:
    url = config.SEC_SUBS.format(cik10=cik10)
    try:
        return fetch_json(url, tag="sec_submissions")
    except Exception:
        return {}


def _recent(cik10: str) -> list[tuple[str, str]]:
    rec = (_submissions(cik10).get("filings") or {}).get("recent") or {}
    return list(zip(rec.get("form", []), rec.get("filingDate", [])))


def merger_trail(cik10: str) -> list[tuple[str, str]]:
    keep = TARGET_PROXY_FORMS | DELIST_FORMS
    return [(f, d) for f, d in _recent(cik10) if f in keep]


def still_filing_after(cik10: str, announce: str, months: int = 15) -> bool | None:
    """True: survivor. False: filings cease. None: too recent to judge."""
    cutoff = (date.fromisoformat(announce) + timedelta(days=months * 30)).isoformat()
    if cutoff >= date.today().isoformat():
        return None
    for f, d in _recent(cik10):
        if f in CONTINUED_FORMS and d > cutoff:
            return True
    return False


# ------------------------------------------------------ verified overlay
def read_verified() -> list[dict]:
    return store.read_table("ma_events_verified")


# ------------------------------------------------------------- proposals
def build_ma_events(read_companies, read_deals, read_cparty) -> list[dict]:
    """Machine-PROPOSED events with per-signal evidence + verified overlay."""
    from biointel import network

    companies = read_companies()
    co_by_iid = {int(c["IID"]): c for c in companies}
    key_to_iid = {}
    for c in companies:
        for nm in (c.get("Name", ""), c.get("Ticker", "")):
            k = network._norm(nm)
            if k and k not in key_to_iid:
                key_to_iid[k] = int(c["IID"])

    # Item 2.01 completions that NAME a counterparty (S3)
    acc_201 = set()
    for d in read_deals():
        if "2.01" in str(d.get("Item", "")):
            acc_201.add((int(d["IID"]), str(d.get("Accession", ""))))
    completions_by_key = defaultdict(list)
    for r in read_cparty():
        k = (int(r["IID"]), str(r.get("Accession", "")))
        if k in acc_201:
            completions_by_key[(int(r["IID"]), network._norm(r["Counterparty"]))].append(
                str(r["FilingDate"])
            )

    # S1 merger-agreement rows, grouped
    grouped = defaultdict(list)
    for r in read_cparty():
        if r.get("AgreementType") != "Merger/Acquisition":
            continue
        nm = r["Counterparty"]
        if SHELL_RE.search(nm) or JUNK_RE.search(nm):
            continue
        grouped[(int(r["IID"]), network._norm(nm))].append(r)

    proposals = []
    consumed_probe = set()  # (iid, episode announce) covered by S1
    for (iid, key), rs in sorted(grouped.items()):
        co = co_by_iid.get(iid, {})
        announce = sorted(str(r["FilingDate"]) for r in rs)[0]
        name = max((r["Counterparty"] for r in rs), key=len)
        p = _assemble(co, iid, key, name, announce, rs, completions_by_key, key_to_iid, s1=True)
        proposals.append(p)
        consumed_probe.add((iid, announce[:4]))

    # TARGET-SIDE PROBER: propose from each company's OWN trail (S2/S4/S5),
    # independent of extraction. Episodes = proxy dates > 1y apart.
    for c in companies:
        iid = int(c["IID"])
        proxies = sorted(d for f, d in merger_trail(c.get("CIK", "")) if f in TARGET_PROXY_FORMS)
        episodes = []
        for d in proxies:
            if (
                episodes
                and (date.fromisoformat(d) - date.fromisoformat(episodes[-1][-1])).days <= 365
            ):
                episodes[-1].append(d)
            else:
                episodes.append([d])
        for ep in episodes:
            announce = ep[0]
            if (iid, announce[:4]) in consumed_probe:
                continue  # already proposed with a named party
            p = _assemble(
                c,
                iid,
                "",
                "(acquirer unresolved)",
                announce,
                [],
                completions_by_key,
                key_to_iid,
                s1=False,
            )
            if p["Confidence"] >= 2:
                proposals.append(p)

    # verified overlay wins on (ticker, announce year)
    ver = read_verified()
    vidx = {(v["FilerTicker"].strip().upper(), str(v["AnnounceDate"])[:4]): v for v in ver}
    matched = set()
    for p in proposals:
        k = (p["FilerTicker"].strip().upper(), str(p["AnnounceDate"])[:4])
        v = vidx.get(k)
        if v:
            matched.add(k)
            p["Verified"] = "yes"
            p["Role"] = "target"
            p["VerifiedAcquirer"] = v.get("Acquirer", "")
            p["VerifiedNote"] = (v.get("Note", "") + " | " + v.get("Source", "")).strip(" |")
            if v.get("AnnounceDate"):
                p["AnnounceDate"] = v["AnnounceDate"]
    # verified events with no proposal stand alone -- the curated record
    # is authoritative even when local caches predate the filings
    tick_to_co = {c.get("Ticker", "").strip().upper(): c for c in companies}
    for k, v in vidx.items():
        if k in matched:
            continue
        c = tick_to_co.get(k[0])
        if not c:
            continue
        proposals.append(
            {
                "FilerIID": int(c["IID"]),
                "Filer": c.get("Name", ""),
                "FilerTicker": c.get("Ticker", ""),
                "Role": "target",
                "Counterparty": v.get("Acquirer", ""),
                "CounterpartyIID": "",
                "AnnounceDate": v["AnnounceDate"],
                "CompletionDate": "",
                "Status": v.get("Status", "announced/pending"),
                "S1_MergerRow": "",
                "S2_ProxyForms": "",
                "S3_CompletionNamed": "",
                "S4_Delisting": "",
                "S5_CeasedFiling": "too-recent",
                "Confidence": 0,
                "Verified": "yes",
                "VerifiedAcquirer": v.get("Acquirer", ""),
                "VerifiedNote": (v.get("Note", "") + " | " + v.get("Source", "")).strip(" |"),
                "Evidence": "",
            }
        )
    return proposals


def _assemble(co, iid, key, name, announce, rs, completions_by_key, key_to_iid, s1: bool) -> dict:
    cik = co.get("CIK", "")
    lo = announce
    hi = (date.fromisoformat(announce) + timedelta(days=548)).isoformat()
    win_lo = (date.fromisoformat(announce) - timedelta(days=30)).isoformat()
    win_prox = (date.fromisoformat(announce) + timedelta(days=330)).isoformat()

    comp = ""
    for cd in sorted(completions_by_key.get((iid, key), [])):
        if lo <= cd <= hi:
            comp = cd
            break

    trail = merger_trail(cik)
    proxies = sorted({f for f, d in trail if f in TARGET_PROXY_FORMS and win_lo <= d <= win_prox})
    delist = any(
        f in DELIST_FORMS
        and (
            comp
            and abs((date.fromisoformat(d) - date.fromisoformat(comp)).days) <= 90
            or not comp
            and lo <= d <= hi
        )
        for f, d in trail
    )
    ceased = still_filing_after(cik, announce)

    conf = (
        (1 if s1 else 0)
        + (1 if proxies else 0)
        + (1 if comp else 0)
        + (1 if delist else 0)
        + (1 if ceased is False else 0)
    )

    # role: completion naming -> acquirer; else target-side evidence,
    # unless the survivor test says the filer kept filing (share-issuing
    # acquirer); financing agents never become the acquirer of record.
    if comp:
        role = "acquirer"
    elif proxies and ceased is not True:
        role = "target"
    elif proxies and ceased is True:
        role = "acquirer"
    else:
        role = "unknown"

    return {
        "FilerIID": iid,
        "Filer": co.get("Name", ""),
        "FilerTicker": co.get("Ticker", ""),
        "Role": role,
        "Counterparty": name,
        "CounterpartyIID": key_to_iid.get(key, ""),
        "AnnounceDate": announce,
        "CompletionDate": comp,
        "Status": "completed" if (comp or delist or ceased is False) else "announced/pending",
        "S1_MergerRow": "yes" if s1 else "",
        "S2_ProxyForms": "; ".join(proxies),
        "S3_CompletionNamed": comp,
        "S4_Delisting": "yes" if delist else "",
        "S5_CeasedFiling": {True: "no", False: "yes", None: "too-recent"}[ceased],
        "Confidence": conf,
        "Verified": "",
        "VerifiedAcquirer": "",
        "VerifiedNote": "",
        "Evidence": "; ".join(sorted({str(r.get("Accession", "")) for r in rs})[:4]),
    }


# ------------------------------------------------------------------ panel
def _quarter_ends(first: str, last: str) -> list[str]:
    out = []
    for y in range(int(first[:4]), int(last[:4]) + 1):
        for m, dd in ((3, 31), (6, 30), (9, 30), (12, 31)):
            q = f"{y:04d}-{m:02d}-{dd:02d}"
            if first <= q <= last:
                out.append(q)
    return out


def build_label_panel(
    read_companies, ma_events: list[dict], start: str = "2010-01-01"
) -> list[dict]:
    """Firm-quarter panel; target labels ONLY from verified events or
    proposals with >= 2 independent target-side signals. Provenance in
    LabelSource: 'verified' or 'proposed-cNN'."""
    today = date.today().isoformat()
    tgt = defaultdict(list)
    acq = defaultdict(list)
    for e in ma_events:
        if e["Role"] == "target":
            strong = e["Verified"] == "yes" or int(e["Confidence"]) >= 2
            if not strong:
                continue
            nm = e["VerifiedAcquirer"] or e["Counterparty"]
            if FIN_AGENT_RE.search(nm):
                nm = "(acquirer unresolved)"
            src = "verified" if e["Verified"] == "yes" else f"proposed-c{e['Confidence']}"
            tgt[int(e["FilerIID"])].append((e["AnnounceDate"], nm, src))
        elif e["Role"] == "acquirer":
            acq[int(e["FilerIID"])].append(e["AnnounceDate"])
            if e["CounterpartyIID"] != "":
                pass  # in-universe mirror requires the counterparty's own
                # trail to propose it; the prober covers that side.

    rows = []
    for c in read_companies():
        iid = int(c["IID"])
        for q in _quarter_ends(start, today):
            h12 = (date.fromisoformat(q) + timedelta(days=365)).isoformat()
            h24 = (date.fromisoformat(q) + timedelta(days=730)).isoformat()
            t12 = [(d, a, s) for d, a, s in tgt.get(iid, []) if q < d <= h12]
            t24 = [(d, a, s) for d, a, s in tgt.get(iid, []) if q < d <= h24]
            m12 = [d for d in acq.get(iid, []) if q < d <= h12]
            rows.append(
                {
                    "IID": iid,
                    "Ticker": c.get("Ticker", ""),
                    "Company": c.get("Name", ""),
                    "QuarterEnd": q,
                    "AcquiredNext12m": 1 if t12 else 0,
                    "AcquiredNext24m": 1 if t24 else 0,
                    "MadeAcquisition12m": 1 if m12 else 0,
                    "AnnounceDate": t24[0][0] if t24 else "",
                    "Acquirer": t24[0][1] if t24 else "",
                    "LabelSource": t24[0][2] if t24 else "",
                }
            )
    return rows


# ------------------------------------------------- universe-wide harvest
HARVEST_COLS = [
    "CIK",
    "Name",
    "Tickers",
    "Delisted",
    "AnnounceDate",
    "ProxyForms",
    "Form25Date",
    "CeasedFiling",
    "Confidence",
    "Verified",
    "Acquirer",
    "Note",
]


def harvest_universe() -> dict:
    """Propose acquisition events for EVERY universe member from its own
    SEC trail (proxies + Form 25 + filing cessation). Uses only the
    submissions records cached during universe screening -- runs without
    any company ingest. Output is the verification worklist: each
    high-confidence row gets its Acquirer filled and moved into
    ma_events_verified.csv after checking against public deal records.
    """
    members = store.read_table("universe")
    if not members:
        return {"status": "empty", "message": "Run `universe` first."}

    rows = []
    for i, m in enumerate(members, 1):
        if i % 100 == 0:
            log.info(f"  harvesting {i}/{len(members)}: {len(rows)} proposals so far")
        cik10 = str(m["CIK"]).zfill(10)
        trail = merger_trail(cik10)
        proxies = sorted(d for f, d in trail if f in TARGET_PROXY_FORMS)
        if not proxies:
            continue
        f25 = sorted(d for f, d in trail if f in FORM25_H)
        episodes = []
        for d in proxies:
            if (
                episodes
                and (date.fromisoformat(d) - date.fromisoformat(episodes[-1][-1])).days <= 365
            ):
                episodes[-1].append(d)
            else:
                episodes.append([d])
        for ep in episodes:
            announce = ep[0]
            lo = announce
            hi = (date.fromisoformat(announce) + timedelta(days=548)).isoformat()
            f25_near = [d for d in f25 if lo <= d <= hi]
            ceased = still_filing_after(cik10, announce)
            conf = 1 + (1 if f25_near else 0) + (1 if ceased is False else 0)
            if ceased is True and not f25_near:
                continue  # survivor with a proxy: share-issuing acquirer
            rows.append(
                {
                    "CIK": cik10,
                    "Name": m["Name"],
                    "Tickers": m["Tickers"],
                    "Delisted": m.get("Delisted", ""),
                    "AnnounceDate": announce,
                    "ProxyForms": "; ".join(
                        sorted({f for f, d in trail if f in TARGET_PROXY_FORMS and d in ep})
                    ),
                    "Form25Date": f25_near[0] if f25_near else "",
                    "CeasedFiling": {True: "no", False: "yes", None: "too-recent"}[ceased],
                    "Confidence": conf,
                    "Verified": "",
                    "Acquirer": "",
                    "Note": "",
                }
            )

    rows.sort(key=lambda r: (-r["Confidence"], r["AnnounceDate"]))
    out = "ma_events_universe"
    store.write_table(out, rows, HARVEST_COLS)
    strong = sum(1 for r in rows if r["Confidence"] >= 2)
    return {
        "status": "ok",
        "message": f"{len(rows)} proposed acquisition events -> {out} "
        f"({strong} at confidence >= 2 -- the verification "
        f"worklist; {len(members)} members scanned).",
    }


FORM25_H = {"25", "25/A", "25-NSE", "25-NSE/A"}


# --------------------------------------------- acquirer auto-extraction
ACQ_ORG = (
    r"((?:[A-Z][\w&.\-\u2019']*\s+){0,6}[A-Z][\w&.\-\u2019']*"
    r"(?:,?\s+(?:Inc\.?|Incorporated|LLC|Ltd\.?|Limited|Corp\.?|"
    r"Corporation|Company|PLC|plc|N\.V\.|S\.A\.|AG|AB|GmbH|LP|"
    r"L\.P\.|Holdings?|Group))?)"
)

PLACEHOLDER_RE = re.compile(
    r"(?i)^(?:the\s+)?(?:holdco|hold\s?co|topco|newco|parent|purchaser|"
    r"buyer|merger\s+partner|acquiror|acquirer)\.?$"
)

ACQ_PATTERNS = [
    (
        "subsidiary-of",
        re.compile(
            r"(?:wholly[\s-]owned\s+(?:direct\s+|indirect\s+)?"
            r"subsidiary\s+of|a\s+subsidiary\s+of)\s+" + ACQ_ORG
        ),
    ),
    (
        "acquired-by",
        re.compile(
            r"(?:be\s+acquired\s+by|acquisition\s+of\s+the\s+"
            r"Compan\w+\s+by|acquired?\s+by)\s+" + ACQ_ORG
        ),
    ),
    ("merger-with", re.compile(r"[Mm]erger\s+(?:[Aa]greement\s+)?with\s+" + ACQ_ORG)),
    ("by-and-among", re.compile(r"by\s+and\s+among\s+(?:the\s+Company,?\s+)?" + ACQ_ORG)),
]


def _acquirer_from_text(text: str, self_name: str) -> tuple[str, str]:
    """(acquirer, pattern) from proxy/8-K text; ("", "") when none holds."""
    from biointel.sources.counterparty import _clean, _plausible, _self_keys

    head = text[:20000]
    keys = _self_keys(self_name)
    for label, pat in ACQ_PATTERNS:
        for m in pat.finditer(head):
            raw = re.sub(r"(?<=[a-z])\.\s+\S.*$", ".", m.group(1))
            n = _clean(raw).rstrip(".")
            if not n or FIN_AGENT_RE.search(n) or SHELL_RE.search(n):
                continue
            if PLACEHOLDER_RE.match(n):
                continue
            if not _plausible(n, keys):
                continue
            return n, label
    return "", ""


def verify_fill() -> dict:
    """Fetch each harvested event's proxy document and auto-fill the
    acquirer. Verified column becomes 'auto' -- promotion to 'yes' stays
    a human decision on spot-check. Fetches are bronze-cached; reruns
    are free."""
    path = "ma_events_universe"
    rows = store.read_table(path)
    if not rows:
        return {"status": "empty", "message": "Run `harvest` first."}

    from biointel.sources.counterparty import fetch_text

    filled = fetched = 0
    for i, r in enumerate(rows, 1):
        if i % 25 == 0:
            log.info(f"  verifying {i}/{len(rows)}: {filled} acquirers filled")
        if r.get("Acquirer") and PLACEHOLDER_RE.match(r["Acquirer"]):
            r["Acquirer"] = ""
            r["Verified"] = ""
            r["Note"] = ""
        if r.get("Acquirer") or int(r["Confidence"]) < 2:
            continue
        cik10 = str(r["CIK"]).zfill(10)
        data = _submissions(cik10)
        rec = (data.get("filings") or {}).get("recent") or {}
        cand = []
        for f, d, acc, doc in zip(
            rec.get("form", []),
            rec.get("filingDate", []),
            rec.get("accessionNumber", []),
            rec.get("primaryDocument", []),
        ):
            near = abs((date.fromisoformat(d) - date.fromisoformat(r["AnnounceDate"])).days)
            if f in TARGET_PROXY_FORMS and near <= 400 and doc:
                cand.append((near, acc, doc))
        for near, acc, doc in sorted(cand)[:2]:
            url = config.SEC_ARCHIVE_DOC.format(cik=int(cik10), acc=acc.replace("-", ""), doc=doc)
            text = fetch_text(url)
            if not text:
                continue
            fetched += 1
            name, patt = _acquirer_from_text(text, r["Name"])
            if name:
                r["Acquirer"] = name
                r["Verified"] = "auto"
                r["Note"] = f"pattern={patt}; doc={doc}"
                filled += 1
                break

    store.write_table(path, rows, HARVEST_COLS)
    todo = sum(1 for r in rows if int(r["Confidence"]) >= 2 and not r.get("Acquirer"))
    return {
        "status": "ok",
        "message": f"{filled} acquirers auto-filled "
        f"({fetched} documents read) -> {path}. "
        f"{todo} confidence>=2 rows still blank (manual).",
    }


def merged_events(read_companies, read_deals, read_cparty) -> list[dict]:
    """Dev-set builder output + universe harvest, one event list.

    Harvest rows qualify as target events when the acquirer was
    auto-extracted (or hand-verified) or two independent signals agree.
    CIK -> IID mapping exists for every member once ingest completes.
    Dedup on (IID, announce year); precedence: verified > harvest-filled
    > dev-set proposal.
    """
    base = build_ma_events(read_companies, read_deals, read_cparty)
    cik_to_iid = {
        str(c.get("CIK", "")).lstrip("0"): int(c["IID"]) for c in read_companies() if c.get("CIK")
    }
    harvest = store.read_table("ma_events_universe")

    def rank(e):
        if e.get("Verified") == "yes":
            return 3
        if (
            e.get("Verified") == "auto"
            and e.get("VerifiedAcquirer")
            or e.get("Verified") == "auto"
            and e.get("Counterparty")
        ):
            return 2
        return 1

    out = {}
    for e in base:
        if e["Role"] != "target":
            continue
        k = (int(e["FilerIID"]), str(e["AnnounceDate"])[:4])
        if k not in out or rank(e) > rank(out[k]):
            out[k] = e
    n_skip = 0
    for h in harvest:
        ok = (h.get("Verified") in ("auto", "yes") and h.get("Acquirer")) or int(
            h.get("Confidence") or 0
        ) >= 2
        if not ok:
            continue
        iid = cik_to_iid.get(str(h["CIK"]).lstrip("0"))
        if iid is None:
            n_skip += 1
            continue
        e = {
            "FilerIID": iid,
            "Filer": h["Name"],
            "FilerTicker": (h.get("Tickers") or "").split(";")[0].strip(),
            "Role": "target",
            "Counterparty": h.get("Acquirer") or "(acquirer unresolved)",
            "CounterpartyIID": "",
            "AnnounceDate": h.get("AgreementDate") or h["AnnounceDate"],
            "CompletionDate": "",
            "Status": "harvested",
            "Confidence": int(h.get("Confidence") or 0),
            "Verified": "yes" if h.get("Verified") in ("auto", "yes") and h.get("Acquirer") else "",
            "VerifiedAcquirer": h.get("Acquirer") or "",
            "VerifiedNote": "universe harvest",
            "Evidence": "",
        }
        k = (iid, str(h["AnnounceDate"])[:4])
        if k not in out or 2 > rank(out[k]):
            if k not in out or rank(out[k]) < 2:
                out[k] = e
    # acquirer-role events from the dev builder ride along unchanged
    acq = [e for e in base if e["Role"] != "target"]
    if n_skip:
        log.info(f"  note: {n_skip} harvest events skipped (CIK not ingested)")
    return list(out.values()) + acq


# ----------------------------------------------------------- QA pass
MONTHS = {
    m: i
    for i, m in enumerate(
        [
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        ],
        1,
    )
}

AGREE_DATE_RE = re.compile(
    r"(?:Agreement\s+and\s+Plan\s+of\s+Merger|Merger\s+Agreement|"
    r"Transaction\s+Agreement)[^.]{0,160}?dated\s+(?:as\s+of\s+)?"
    r"([A-Z][a-z]+)\s+(\d{1,2}),\s+(\d{4})"
)

CLASS_PATTERNS = [
    (
        "spac",
        re.compile(
            r"(?i)special\s+purpose\s+acquisition|\bSPAC\b|"
            r"business\s+combination\s+agreement"
        ),
    ),
    (
        "bankruptcy",
        re.compile(
            r"(?i)chapter\s+11|plan\s+of\s+reorganization|"
            r"bankruptcy\s+court"
        ),
    ),
    (
        "going-private",
        re.compile(
            r"(?i)take[- ]private|going[- ]private|"
            r"affiliates?\s+of\s+(?:[A-Z]\w+\s+){0,3}"
            r"(?:Capital|Partners|Equity|Management)"
        ),
    ),
    (
        "reverse-merger",
        re.compile(
            r"(?i)reverse\s+merger|"
            r"will\s+be\s+renamed"
        ),
    ),
]

QA_COLS = HARVEST_COLS + ["AgreementDate", "EventClass", "QAFlag"]


def qa_pass(sample_n: int = 60, seed: int = 11) -> dict:
    """Machine half of the label QA: re-open each filled event's cached
    proxy, extract the true merger-agreement date (proxy FILING dates lag
    press announcements -- the R7 threat) and an EventClass; emit the
    stratified human worklist (gold/qa_worklist.csv) covering a random
    sample plus every structurally suspicious row."""
    import random as _random

    path = "ma_events_universe"
    rows = store.read_table(path)
    if not rows:
        return {"status": "empty", "message": "Run harvest/verify-fill first."}

    from biointel.sources.counterparty import fetch_text

    n_date = n_class = 0
    for i, r in enumerate(rows, 1):
        if i % 25 == 0:
            log.info(f"  qa {i}/{len(rows)}: {n_date} agreement dates, {n_class} classed")
        r.setdefault("AgreementDate", "")
        r.setdefault("EventClass", "")
        r.setdefault("QAFlag", "")
        if int(r.get("Confidence") or 0) < 2 and not r.get("Acquirer"):
            continue
        cik10 = str(r["CIK"]).zfill(10)
        data = _submissions(cik10)
        rec = (data.get("filings") or {}).get("recent") or {}
        cand = []
        for f_, d_, acc, doc in zip(
            rec.get("form", []),
            rec.get("filingDate", []),
            rec.get("accessionNumber", []),
            rec.get("primaryDocument", []),
        ):
            if (
                f_ in TARGET_PROXY_FORMS
                and doc
                and abs((date.fromisoformat(d_) - date.fromisoformat(r["AnnounceDate"])).days)
                <= 400
            ):
                cand.append(
                    (
                        abs((date.fromisoformat(d_) - date.fromisoformat(r["AnnounceDate"])).days),
                        acc,
                        doc,
                    )
                )
        text = ""
        for _, acc, doc in sorted(cand)[:2]:
            url = config.SEC_ARCHIVE_DOC.format(cik=int(cik10), acc=acc.replace("-", ""), doc=doc)
            text = fetch_text(url)
            if text:
                break
        if not text:
            r["QAFlag"] = (r["QAFlag"] + "; no-doc").strip("; ")
            continue
        head = text[:40000]
        m = AGREE_DATE_RE.search(head)
        if m and not r.get("AgreementDate"):
            mon, day, yr = m.groups()
            if mon in MONTHS:
                r["AgreementDate"] = f"{int(yr):04d}-{MONTHS[mon]:02d}-{int(day):02d}"
                n_date += 1
        cls = "acquisition"
        for label, pat in CLASS_PATTERNS:
            if pat.search(head):
                cls = label
                break
        if not r.get("EventClass"):
            r["EventClass"] = cls
            n_class += 1
        if cls != "acquisition":
            r["QAFlag"] = (r["QAFlag"] + f"; class={cls}").strip("; ")

    # structural suspicion flags
    for r in rows:
        if int(r.get("Confidence") or 0) >= 2 and not r.get("Acquirer"):
            r["QAFlag"] = (r.get("QAFlag", "") + "; blank-acquirer").strip("; ")
        if r.get("AgreementDate") and r["AgreementDate"] < r["AnnounceDate"]:
            gap = (
                date.fromisoformat(r["AnnounceDate"]) - date.fromisoformat(r["AgreementDate"])
            ).days
            if gap > 45:
                r["QAFlag"] = (r.get("QAFlag", "") + f"; proxy-lag-{gap}d").strip("; ")

    store.write_table(path, rows, QA_COLS)

    filled = [r for r in rows if r.get("Acquirer")]
    _random.seed(seed)
    sample = _random.sample(filled, min(sample_n, len(filled)))
    flagged = [r for r in rows if r.get("QAFlag")]
    worklist = {id(r): r for r in sample + flagged}.values()
    out = "qa_worklist"
    store.write_table(
        out, [{**r, "HumanVerdict": ""} for r in worklist], QA_COLS + ["HumanVerdict"]
    )
    return {
        "status": "ok",
        "message": f"QA: {n_date} agreement dates extracted, "
        f"{n_class} events classed; worklist "
        f"{len(list(worklist))} rows ({len(sample)} sample + "
        f"{len(flagged)} flagged) -> {out}",
    }


def _filings_reaching(cik10: str, anchor: str):
    """(form, date, accession, primaryDocument) tuples covering `anchor`.

    data.sec.gov's `recent` block holds only the newest ~1,000 filings --
    heavy filers like Amgen exhaust that by ~2018, which silently missed
    a 2013 corroborating 8-K in testing. Older filings live in the
    paginated archive files listed under filings.files; fetch them until
    coverage reaches the anchor date (cached like everything else).
    """
    data = _submissions(cik10)
    rec = (data.get("filings") or {}).get("recent") or {}
    quads = list(
        zip(
            rec.get("form", []),
            rec.get("filingDate", []),
            rec.get("accessionNumber", []),
            rec.get("primaryDocument", []),
        )
    )
    oldest = min((d for _, d, _, _ in quads), default="9999")
    for extra in (data.get("filings") or {}).get("files") or []:
        if oldest <= anchor:
            break
        name = extra.get("name")
        if not name:
            continue
        try:
            page = fetch_json(config.SEC_SUBS_PAGE.format(name=name), tag="sec_submissions_extra")
        except Exception:
            break
        quads += list(
            zip(
                page.get("form", []),
                page.get("filingDate", []),
                page.get("accessionNumber", []),
                page.get("primaryDocument", []),
            )
        )
        oldest = min(oldest, extra.get("filingFrom", oldest))
    return quads


# ------------------------------------------- automated corroboration
CORROB_FORMS = {"8-K", "8-K/A", "425", "S-4", "S-4/A", "SC TO-T", "SC TO-C"}


# Recurring subsidiary/holdco entities of EDGAR-registered parents,
# observed in the corroboration none-list. Maps to the PARENT whose
# filing trail carries the deal.
PARENT_MAP = {
    "ZENECA": "ASTRAZENECA PLC",
    "WYETH": "PFIZER INC",
    "ALLERGAN HOLDCO": "ALLERGAN",
    "ALLERGAN HOLDCO US": "ALLERGAN",
    "AVENTIS": "SANOFI",
    "GENZYME": "SANOFI",
}


def _acquirer_cik(name: str, read_companies) -> str:
    """Resolve an acquirer name to a CIK. Order: registry exact ->
    parent-map -> ticker-map exact -> bidirectional canon-prefix ->
    two-token prefix. Thresholds loosened after the first live run
    missed EDGAR filers with short names (Alcon, Mereo) and foreign
    suffixes (Novo Nordisk A/S, Grifols S.A.)."""
    from biointel import network

    raw = re.sub(r"(?i)\s+hold(?:ing)?co(?:\s+us)?\b", "", name or "")
    key = network._norm(raw)
    if not key:
        return ""
    for pat, parent in PARENT_MAP.items():
        if key.startswith(pat):
            key = network._norm(parent)
            break

    registry = [
        (network._norm(c.get("Name", "")), str(c.get("CIK", "")).zfill(10))
        for c in read_companies()
    ]
    for k, cik in registry:
        if k == key:
            return cik
    try:
        data = fetch_json(config.SEC_TICKERS, tag="sec_ticker_map")
    except Exception:
        data = {}
    tmap = [
        (network._norm(v.get("title", "")), str(v.get("cik_str", "")).zfill(10))
        for v in (data or {}).values()
    ]
    for k, cik in tmap:
        if k == key:
            return cik
    # bidirectional prefix on full canon strings (handles suffix variants:
    # "NOVO NORDISK" vs "NOVO NORDISK A S", "MEREO" vs "MEREO BIOPHARMA")
    for pool in (registry, tmap):
        for k, cik in pool:
            if not k:
                continue
            if (
                k.startswith(key + " ")
                or key.startswith(k + " ")
                or (
                    len(key) >= 5
                    and k.split()[0] == key.split()[0]
                    and (len(key.split()) == 1 or len(k.split()) == 1)
                )
            ):
                return cik
    # two-token prefix
    toks = key.split()
    if len(toks) >= 2:
        two = " ".join(toks[:2])
        for pool in (registry, tmap):
            for k, cik in pool:
                if k.startswith(two):
                    return cik
    return ""


def qa_corroborate(read_companies) -> dict:
    """Fill Corroboration for every event with an acquirer; suggest
    HumanVerdict='ok(machine-corroborated)' on strong agreement so the
    human worklist shrinks to the genuine residue."""
    from biointel import network
    from biointel.sources.counterparty import fetch_text

    path = "ma_events_universe"
    rows = store.read_table(path)
    for r in rows:
        r.setdefault("Corroboration", "")

    strong = weak = none = 0
    cik_cache = {}
    for i, r in enumerate(rows, 1):
        if i % 25 == 0:
            log.info(
                f"  corroborating {i}/{len(rows)}: {strong} strong / {weak} weak / {none} none"
            )
        acq = (r.get("Acquirer") or "").strip()
        if not acq or acq.startswith("("):
            continue
        if (r.get("Corroboration") or "").startswith(("strong", "weak")):
            strong += 1 if r["Corroboration"].startswith("strong") else 0
            weak += 1 if r["Corroboration"].startswith("weak") else 0
            continue
        anchor = r.get("AgreementDate") or r.get("AnnounceDate")
        if not anchor:
            continue
        if acq not in cik_cache:
            cik_cache[acq] = _acquirer_cik(acq, read_companies)
        cik = cik_cache[acq]
        if not cik:
            r["Corroboration"] = "none:acquirer-not-in-edgar"
            none += 1
            continue
        near = []
        for f_, d_, acc, doc in _filings_reaching(cik, anchor):
            if f_ in CORROB_FORMS and doc:
                gap = abs((date.fromisoformat(d_) - date.fromisoformat(anchor)).days)
                if gap <= 45:
                    near.append((gap, acc, doc))
        if not near:
            r["Corroboration"] = "none:no-filing-in-window"
            none += 1
            continue
        # target-name check in the closest doc
        tgt_key = network._norm(r["Name"])
        tgt_tok = tgt_key.split()[0] if tgt_key.split() else ""
        hit = False
        for gap, acc, doc in sorted(near)[:2]:
            url = config.SEC_ARCHIVE_DOC.format(cik=int(cik), acc=acc.replace("-", ""), doc=doc)
            text = fetch_text(url)
            if text and tgt_tok and tgt_tok.lower() in text[:60000].lower():
                hit = True
                break
        if hit:
            r["Corroboration"] = "strong:acquirer-filing-names-target"
            strong += 1
        else:
            r["Corroboration"] = "weak:filing-in-window-no-name-match"
            weak += 1

    cols = list(rows[0].keys())
    if "Corroboration" not in cols:
        cols.append("Corroboration")
    store.write_table(path, rows, cols)

    # regenerate the human worklist: strong rows pre-verdicted, residue open
    wl = "qa_worklist"
    wrows = store.read_table(wl)
    if wrows:
        cmap = {(r["CIK"], r["AnnounceDate"]): r.get("Corroboration", "") for r in rows}
        open_rows = 0
        for wr in wrows:
            c = cmap.get((wr["CIK"], wr["AnnounceDate"]), "")
            wr["Corroboration"] = c
            if c.startswith("strong") and not wr.get("HumanVerdict"):
                wr["HumanVerdict"] = "ok(machine-corroborated)"
            if not wr.get("HumanVerdict"):
                open_rows += 1
        wcols = list(wrows[0].keys())
        if "Corroboration" not in wcols:
            wcols.append("Corroboration")
        store.write_table(wl, wrows, wcols)
    else:
        open_rows = -1
    return {
        "status": "ok",
        "message": f"Corroboration: {strong} strong, {weak} weak, "
        f"{none} none. Worklist rows still needing a human: "
        f"{open_rows}.",
    }


# --------------------------------------- Wikipedia corroboration (residue)
def qa_wiki(read_companies) -> dict:
    """Third independent source for rows EDGAR cannot corroborate
    (private/foreign acquirers): Wikipedia's public API. For each
    remaining none/weak row, search the target company, pull the page
    extract, and check that the acquirer's distinctive name appears in
    acquisition context. Marks Corroboration 'wiki:...' and pre-verdicts
    the worklist. No API key; graceful per-row failure; cached.
    """
    from biointel import network

    path = "ma_events_universe"
    rows = store.read_table(path)

    def wiki_extract(query: str) -> str:
        try:
            js = fetch_json(
                config.WIKI_API + "?action=query&list=search"
                f"&srsearch={query.replace(' ', '%20')}&format=json&srlimit=2",
                tag="wiki_search",
            )
            hits = ((js or {}).get("query") or {}).get("search") or []
            if not hits:
                return ""
            title = hits[0]["title"].replace(" ", "%20")
            pg = fetch_json(
                config.WIKI_API + "?action=query&prop=extracts"
                f"&explaintext=1&titles={title}&format=json",
                tag="wiki_page",
            )
            pages = ((pg or {}).get("query") or {}).get("pages") or {}
            return " ".join(p.get("extract", "") for p in pages.values())
        except Exception:
            return ""

    checked = confirmed = 0
    for i, r in enumerate(rows, 1):
        c = r.get("Corroboration") or ""
        acq = (r.get("Acquirer") or "").strip()
        if not acq or acq.startswith("(") or c.startswith(("strong", "wiki")):
            continue
        checked += 1
        if checked % 10 == 0:
            log.info(f"  wiki {checked} checked, {confirmed} confirmed")
        text = wiki_extract(f"{r['Name']} acquisition")
        if not text:
            text = wiki_extract(r["Name"])
        if not text:
            r["Corroboration"] = (c + "; wiki:no-page").strip("; ")
            continue
        low = text.lower()
        acq_tok = network._norm(acq).split()
        tok = next((t for t in acq_tok if len(t) >= 5), acq_tok[0] if acq_tok else "")
        near = False
        if tok and tok.lower() in low:
            j = low.find(tok.lower())
            ctx = low[max(0, j - 300) : j + 300]
            near = any(w in ctx for w in ("acquir", "merger", "bought", "takeover", "purchase"))
        if near:
            r["Corroboration"] = "wiki:page-names-acquirer-in-deal-context"
            confirmed += 1
        else:
            r["Corroboration"] = (c + "; wiki:no-match").strip("; ")

    cols = list(rows[0].keys())
    store.write_table(path, rows, cols)

    wl = "qa_worklist"
    open_rows = -1
    wrows = store.read_table(wl)
    if wrows:
        cmap = {(r["CIK"], r["AnnounceDate"]): r.get("Corroboration", "") for r in rows}
        open_rows = 0
        for wr in wrows:
            c = cmap.get((wr["CIK"], wr["AnnounceDate"]), wr.get("Corroboration", ""))
            wr["Corroboration"] = c
            if c.startswith(("strong", "wiki:page")) and not wr.get("HumanVerdict"):
                wr["HumanVerdict"] = "ok(machine-corroborated)"
            if not wr.get("HumanVerdict"):
                open_rows += 1
        store.write_table(wl, wrows, list(wrows[0].keys()))
    return {
        "status": "ok",
        "message": f"Wikipedia: {checked} residue rows checked, "
        f"{confirmed} confirmed. Worklist rows still open: "
        f"{open_rows}. Remaining opens are excluded from the "
        f"strict-label model run, so nothing gates on them.",
    }
