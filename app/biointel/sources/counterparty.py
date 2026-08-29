"""Extract counterparty names and agreement types from 8-K filings.

REWRITE (v2), built and validated against 1,062 real cached filings in
data/bronze/sec_filing_doc/ -- not invented text. Three changes from the
failed version, each addressing a diagnosed junk class:

1. SECTION BOUNDING. Extraction runs ONLY inside the Item 1.01 / 1.02 /
   2.01 sections and the exhibit-index description lines. The old version
   scanned the whole document, which is how director names (Item 5.02),
   bylaw amendments (Item 5.03) and boilerplate reached the output.

2. EXHIBIT DESCRIPTIONS FIRST. The Material Contracts Corpus (Stanford,
   2025) parses the agreement documents, not the narrative. The nearest
   cached equivalent is the exhibit-index line, which is written like:
       10.1  License Agreement, dated October 24, 2023, by and between
             Shuttle Pharmaceuticals Holdings, Inc. and Georgetown
             University.
   Type, date and both parties in one sentence, in legal register.

3. ORG-ONLY NER plus MCC-style generic exclusions. PERSON/NORP/FAC labels
   are dropped (director names were a junk class), and entities matching
   generic legal/regulatory patterns -- "Delaware General Corporation
   Law", "Regulation S-K", "Audit Committee", exchanges, the SEC itself --
   are excluded, following the corpus paper's tuned exclusion list.

An Item 1.01 with no counterparty is a CORRECT empty result: equity-plan
amendments and bylaw changes are material agreements with no other party.
Hit rate below 100% is expected and honest.

Public API unchanged: extract(), fetch_text(), strip_html(),
agreement_type() -- pipeline.py needs no modification.
"""
from __future__ import annotations
import html
import re

from ..store import fetch_json

# Agreement types worth distinguishing. A licensing deal and a credit
# facility are both Item 1.01 events but very different partnerships.
AGREEMENT_TYPES = [
    ("License",        ["license agreement", "licensing agreement", "sublicense"]),
    ("Collaboration",  ["collaboration", "co-development", "codevelopment",
                        "research agreement", "research collaboration",
                        "joint development", "development agreement",
                        "option agreement", "joint venture"]),
    ("Supply/Manufacturing", ["supply agreement", "manufacturing agreement",
                              "manufacture and supply", "toll manufacturing",
                              "commercial supply"]),
    ("Distribution/Commercial", ["distribution agreement", "commercialization agreement",
                                 "co-promotion", "promotion agreement",
                                 "marketing agreement"]),
    ("Asset purchase", ["asset purchase agreement", "purchase and sale agreement"]),
    ("Merger/Acquisition", ["merger agreement", "agreement and plan of merger",
                            "plan of merger", "tender offer"]),
    ("Stake purchase",  ["share purchase agreement", "stock purchase agreement"]),
    ("Financing",      ["securities purchase agreement", "underwriting agreement",
                        "credit agreement", "loan and security", "loan agreement",
                        "placement agency", "note purchase", "at the market",
                        "sales agreement", "royalty purchase", "revenue interest",
                        "equity distribution", "term loan", "subscription agreement"]),
    ("Settlement/Legal", ["settlement agreement", "settlement and license"]),
    ("Lease",          ["lease agreement", "sublease"]),
    ("Employment",     ["employment agreement", "separation agreement",
                        "retention agreement", "consulting agreement"]),
]

STOP = {
    "the company", "the registrant", "the parties", "the agreement", "the board",
    "the sec", "the securities", "this agreement", "the closing", "certain",
    "each", "such", "any", "all", "no", "if", "exhibit", "item", "form",
    "current report", "united states", "delaware", "new york", "california",
    "common stock", "the effective date", "an",
}

ROLE_WORDS = {
    "administrative agent", "collateral agent", "agent", "lessor", "lessee",
    "landlord", "tenant", "purchaser", "purchasers", "seller", "sellers",
    "borrower", "borrowers", "lender", "lenders", "issuer", "investor",
    "investors", "guarantor", "guarantors", "trustee", "underwriter",
    "underwriters", "placement agent", "sales agent", "escrow agent",
    "administrative agents", "counterparty", "licensee", "licensor",
    "buyer", "buyers", "holder", "holders", "subscriber", "subscribers",
    "the purchaser", "the seller", "the borrower", "the lender",
    "the issuer", "the investor", "the investors", "the guarantor",
    "the lessor", "the lessee", "the parties hereto", "parent", "merger sub",
}

DOC_WORDS = {
    "amendment", "first amendment", "second amendment", "third amendment",
    "fourth amendment", "fifth amendment", "agreement", "the amendment",
    "letter agreement", "amended and restated", "schedule", "annex",
    "appendix", "press release", "credit facility", "note", "notes",
    "warrant", "warrants", "indenture", "plan", "effective date",
}

SUFFIX_ONLY = {
    "inc", "inc.", "incorporated", "llc", "l.l.c.", "ltd", "ltd.", "limited",
    "corp", "corp.", "corporation", "company", "co.", "plc", "n.v.", "b.v.",
    "s.a.", "ag", "ab", "gmbh", "lp", "l.p.", "llp", "holdings", "group",
    "pharmaceuticals", "pharma", "therapeutics", "sciences", "technologies",
    "partners", "capital", "bank", "trust", "university", "institute",
}

# MCC-style generic-entity exclusions: patterns that NER tags as ORG but
# are never a contract party. Sourced from the junk classes observed in
# the failed run against these same real filings.
GENERIC_RE = re.compile(
    r"(?i)\b(regulation|rule|section|article|item|form|schedule|annex|"
    r"exhibit|act|law|code|statute|committee|board of directors|"
    r"securities and exchange commission|internal revenue|"
    r"nasdaq|new york stock exchange|nyse|stock market|"
    r"general corporation law|exchange act|securities act)\b")

# Regulators appear constantly in deal prose but are never the party.
REGULATOR_RE = re.compile(
    r"(?i)^(?:the\s+)?(?:u\.?s\.?\s+)?(?:sec|ftc|irs|fda|"
    r"food and drug administration|federal trade commission|"
    r"internal revenue service|department of justice|"
    r"european medicines agency|ema)$")

# Drug/program codes NER mislabels as ORG: IMVT-1401, ALN-AT3, BTK, OTEZLA(R).
DRUG_CODE_RE = re.compile(r"^[A-Z]{2,6}[- ]?\d+[A-Za-z0-9-]*$|[\u00ae\u2122]")

# If ANY word of the candidate is a document/deal-mechanics noun, it is
# contract furniture, not an organisation.
BAD_WORDS = {
    "agreement", "agreements", "amendment", "lease", "sublease", "indenture",
    "warrant", "warrants", "note", "notes", "report", "reports", "statement",
    "statements", "program", "plan", "merger", "closing", "shares", "stock",
    "consideration", "placement", "purchasers", "offering", "loan",
    "facility", "ownership", "products", "date", "exchange",
    "terms", "term", "transactions", "transaction", "combination", "award",
    "awards", "share",
    "counterparties", "time", "license", "licenses", "call", "rights",
    "hereto", "thereto", "units", "securities", "endpoint", "shareholders",
    "stockholders", "space", "owner", "association", "phase",
}

STATE_NAMES = {
    "alabama","alaska","arizona","arkansas","california","colorado",
    "connecticut","delaware","florida","georgia","hawaii","idaho","illinois",
    "indiana","iowa","kansas","kentucky","louisiana","maine","maryland",
    "massachusetts","michigan","minnesota","mississippi","missouri","montana",
    "nebraska","nevada","new hampshire","new jersey","new mexico","new york",
    "north carolina","north dakota","ohio","oklahoma","oregon","pennsylvania",
    "rhode island","south carolina","south dakota","tennessee","texas","utah",
    "vermont","virginia","washington","west virginia","wisconsin","wyoming",
}

ORG_TAIL = (r"(?:Inc|Inc\.|Incorporated|LLC|L\.L\.C\.|Ltd|Ltd\.|Limited|Corp|Corp\.|"
            r"Corporation|Company|Co\.|PLC|plc|N\.V\.|B\.V\.|S\.A\.|S\.A\.S\.|A/S|"
            r"AG|AB|GmbH|KGaA|LP|L\.P\.|LLP|University|College|Institute|Hospital|"
            r"Foundation|Trust|Holdings|Group|Pharmaceuticals|Pharma|Therapeutics|"
            r"Biosciences|Bioscience|Laboratories|Sciences|Health|Healthcare|"
            r"Technologies|Partners|Capital|Bank|Center|Centre)")

ORG = rf"((?:[A-Z][\w&.\-']*\s+){{0,7}}[A-Z][\w&.\-']*(?:,?\s+{ORG_TAIL})?)"

ITEM_RE = re.compile(r"Item\s+(\d\.\d\d)[.\s]", re.I)
DEAL_SECTIONS = {"1.01", "1.02", "2.01"}


def strip_html(raw: str) -> str:
    """HTML/iXBRL to plain text. 8-Ks are HTML from roughly 2001 onward."""
    s = re.sub(r"(?is)<(script|style|head)[^>]*>.*?</\1>", " ", raw)
    s = re.sub(r"(?i)<br\s*/?>", "\n", s)
    s = re.sub(r"(?i)</(p|div|tr|td|li|h\d)>", "\n", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    s = s.replace("\u00a0", " ").replace("\u2019", "'").replace("\u201c", '"').replace("\u201d", '"')
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n\s*\n+", "\n", s)
    return s.strip()


def deal_sections(text: str) -> list[tuple[str, str]]:
    """(item, section_text) for Items 1.01/1.02/2.01 only.

    A section runs from its heading to the next Item heading. Bounding is
    the core fix: the failed version scanned whole documents and pulled
    director names out of Item 5.02.
    """
    ms = list(ITEM_RE.finditer(text))
    out = []
    for i, m in enumerate(ms):
        item = m.group(1)
        if item not in DEAL_SECTIONS:
            continue
        start = m.end()
        end = ms[i + 1].start() if i + 1 < len(ms) else min(len(text), start + 12000)
        sec = text[start:end]
        if len(sec) > 60:
            out.append((item, sec))
    # dedupe repeated headings (table of contents lists them once more)
    seen, uniq = set(), []
    for item, sec in out:
        k = (item, sec[:120])
        if k in seen:
            continue
        seen.add(k)
        uniq.append((item, sec))
    return uniq


def exhibit_lines(text: str) -> list[str]:
    """Exhibit-index description lines mentioning an agreement.

    Two real shapes:  'EX-10.1 - License Agreement, ...'
                      '10.1 License Agreement, dated ..., by and between ...'
    """
    out = []
    for m in re.finditer(r"(?:EX-)?(?:[1-9]?\d\.\d\d?)\s*[-\u2013 ]\s*([^\n]{15,420})", text):
        desc = m.group(1).strip()
        if re.search(r"(?i)\bagreement\b", desc):
            out.append(desc)
    return out


def agreement_type(text: str) -> str:
    low = text.lower()
    for label, keys in AGREEMENT_TYPES:
        if any(k in low for k in keys):
            return label
    return "Other"


def _clean(name: str) -> str:
    n = re.sub(r"\s+", " ", (name or "")).strip(" ,;:.\u2022-\"'")
    n = re.sub(r"^(?:the|a|an|its|our|certain)\s+", "", n, flags=re.I)
    # leading contract-role prefix: "Administrative Agent and Bank of America"
    n = re.sub(r"^(?:[A-Z][a-z]+\s+)?Agent(?:s)?\s+and\s+", "", n)
    n = re.sub(r"^Company\s+(?:of|and)\s+", "", n)
    n = re.sub(r"\s+(?:dated|effective|pursuant|whereby|under|for|in|on|relating|that|regarding|concerning)\b.*$", "", n, flags=re.I)
    n = re.sub(r"\s*,?\s+as\s+(?:the\s+)?[a-z].*$", "", n)
    n = re.sub(r"\s*\(.*$", "", n)
    return n.strip(" ,;:.")


def _plausible(name: str, self_keys: set[str]) -> bool:
    n = _clean(name)
    low = n.lower().strip(" .,")
    if len(n) < 3 or len(n) > 90:
        return False
    if low in STOP or low in ROLE_WORDS or low in DOC_WORDS or low in SUFFIX_ONLY:
        return False
    if low in STATE_NAMES:
        return False
    if GENERIC_RE.search(n):
        return False
    if REGULATOR_RE.match(low):
        return False
    if DRUG_CODE_RE.search(n):
        return False
    if any(w in BAD_WORDS for w in re.sub(r"[^a-z ]", " ", low).split()):
        return False
    if n[0] in "\"'" or not n[0].isalnum():
        return False
    if n.split()[0].islower():
        return False
    if re.fullmatch(r"[A-Z]{2,4}", n):          # bare acronym: BTK, TICV
        return False
    if re.search(r"\b\d{5}\b", n):              # zip fragment: MA 02421
        return False
    if not re.search(r"[A-Za-z]", n):
        return False
    if '"' in n or "\u201c" in n or n.lstrip()[:1] == '"':
        return False
    if sum(1 for w in n.split() if w[:1].isupper()) < 1:
        return False
    core = [w for w in re.sub(r"[^A-Za-z ]", " ", low).split()
            if w not in SUFFIX_ONLY and len(w) > 1]
    if not core:
        return False
    if any(low.endswith(" " + r) for r in ROLE_WORDS):
        return False
    key = re.sub(r"[^A-Z0-9 ]", "", n.upper())
    key = " ".join(w for w in key.split() if len(w) > 1)
    for sk in self_keys:
        if sk and (key == sk or key.startswith(sk + " ") or sk.startswith(key + " ")):
            return False
    return True


_NLP = None
_NLP_TRIED = False
_NLP_NAME = None


def _nlp():
    """Load spaCy once. Falls back to regex-only if unavailable."""
    global _NLP, _NLP_TRIED, _NLP_NAME
    if _NLP_TRIED:
        return _NLP
    _NLP_TRIED = True
    try:
        import spacy
    except ImportError:
        return None
    for name in ("en_core_web_md", "en_core_web_sm"):
        try:
            _NLP = spacy.load(name, disable=["lemmatizer", "textcat"])
            _NLP_NAME = name
            return _NLP
        except Exception:
            continue
    return None


# Anchors that introduce a counterparty inside a bounded section.
ANCHOR_RE = re.compile(r"(?i)\b(?:by and (?:between|among)|with|from|into)\s")


def _extract_ner(section: str, self_keys: set[str], typ_default: str) -> list[dict]:
    """ORG entities within anchor range, inside ONE bounded section."""
    nlp = _nlp()
    if nlp is None:
        return []
    out, seen = [], set()
    doc = nlp(section[:200_000])
    ents = [(e.start_char, e.text) for e in doc.ents if e.label_ == "ORG"]
    if not ents:
        return []
    anchors = list(ANCHOR_RE.finditer(section))
    for m in anchors:
        ctx = section[max(0, m.start() - 160):m.end() + 300]
        typ = agreement_type(ctx)
        if typ == "Other":
            typ = typ_default
        for pos, name in ents:
            if not (m.end() <= pos <= m.end() + 60):
                continue
            n = _clean(name)
            if not _plausible(n, self_keys):
                continue
            # NER-only rows need extra substance: a legal suffix or 2+ words
            if len(n.split()) < 2 and not re.search(ORG_TAIL, n):
                continue
            if n.lower() in seen:
                continue
            seen.add(n.lower())
            out.append({"Counterparty": n, "AgreementType": typ,
                        "Method": "ner", "Context": ctx[:220].strip()})
    return out


def _self_keys(self_name: str) -> set[str]:
    keys = set()
    if self_name:
        k = re.sub(r"[^A-Z0-9 ]", "", self_name.upper())
        k = " ".join(w for w in k.split()
                     if len(w) > 1 and w not in
                     {"INC", "LLC", "LTD", "CORP", "CO", "COMPANY", "PLC",
                      "HOLDINGS", "PHARMACEUTICALS", "PHARMA", "THERAPEUTICS",
                      "INCORPORATED", "LIMITED", "CORPORATION"})
        if k:
            keys.add(k)
            keys.add(k.split()[0])
    return keys


def extract(text: str, self_name: str = "") -> list[dict]:
    """Counterparties and agreement types from one 8-K document.

    Order of evidence, highest precision first:
      1. exhibit-index description lines ("... by and between A and B")
      2. bounded Item 1.01/1.02/2.01 sections: "by and between/among" lists
      3. bounded sections: "entered into ... with X" / "Agreement with X"
      4. bounded sections: ORG-only NER near anchors
    An empty result on a compensation-plan or bylaws Item 1.01 is correct.
    """
    self_keys = _self_keys(self_name)
    out: list[dict] = []
    seen: set[str] = set()

    def add(name, typ, method, ctx):
        n = _clean(name)
        if not _plausible(n, self_keys):
            return
        key = n.lower()
        if key in seen:
            return
        seen.add(key)
        out.append({"Counterparty": n, "AgreementType": typ,
                    "Method": method, "Context": ctx[:220].strip()})

    # ---- 1. exhibit description lines --------------------------------
    for desc in exhibit_lines(text):
        typ = agreement_type(desc)
        for m in re.finditer(rf"by and (?:between|among)\s+{ORG}\s*(?:,|\s+and\s+)\s*{ORG}"
                             rf"(?:\s*(?:,|\s+and\s+)\s*{ORG})?", desc):
            for g in m.groups():
                if g:
                    add(g, typ, "exhibit-index", desc)

    # ---- 2..4 bounded narrative sections -----------------------------
    for item, sec in deal_sections(text):
        typ_default = ("Merger/Acquisition" if item == "2.01" else "Other")

        for m in re.finditer(rf"by and (?:between|among)\s+{ORG}\s*(?:,|\s+and\s+)\s*{ORG}"
                             rf"(?:\s*(?:,|\s+and\s+)\s*{ORG})?", sec):
            ctx = sec[max(0, m.start() - 160):m.end() + 40]
            typ = agreement_type(ctx)
            if typ == "Other":
                typ = typ_default
            for g in m.groups():
                if g:
                    add(g, typ, "by-and-between", ctx)

        for m in re.finditer(rf"entered into\s+(?:a|an|the)?\s*([^.;]{{0,120}}?)\bwith\s+{ORG}", sec, re.I):
            ctx = sec[max(0, m.start() - 60):m.end() + 60]
            add(m.group(2), agreement_type(m.group(1) or ctx), "entered-into-with", ctx)

        for m in re.finditer(rf"\b([A-Z][\w\- ]{{0,40}}?Agreement)\s+with\s+{ORG}", sec):
            ctx = sec[max(0, m.start() - 60):m.end() + 60]
            add(m.group(2), agreement_type(m.group(1)), "agreement-with", ctx)

        out_ner = _extract_ner(sec, self_keys, typ_default)
        for r in out_ner:
            if r["Counterparty"].lower() in seen:
                continue
            seen.add(r["Counterparty"].lower())
            out.append(r)

    return _merge_fragments(out)


def _merge_fragments(rows: list[dict]) -> list[dict]:
    """Collapse "Sanofi" into "Sanofi-Aventis US LLC". Keep the longest."""
    def core(n):
        k = re.sub(r"[^A-Za-z0-9 ]", " ", n.upper())
        return " ".join(w for w in k.split()
                        if w.lower() not in SUFFIX_ONLY and len(w) > 1)

    best: dict[str, dict] = {}
    for r in sorted(rows, key=lambda r: -len(r["Counterparty"])):
        c = core(r["Counterparty"])
        if not c:
            continue
        hit = None
        for k in best:
            if (c == k or c.startswith(k + " ") or k.startswith(c + " ")
                    or c.endswith(" " + k) or k.endswith(" " + c)):
                hit = k
                break
        if hit is None:
            best[c] = r
    return list(best.values())


def fetch_text(url: str) -> str:
    """Filing document as plain text. Cached in bronze like every fetch."""
    try:
        raw = fetch_json(url, tag="sec_filing_doc", raw_text=True)
    except Exception:
        return ""
    return strip_html(raw if isinstance(raw, str) else str(raw))
