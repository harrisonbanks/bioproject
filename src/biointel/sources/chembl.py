# src/biointel/sources/chembl.py
"""ChEMBL layer: firm x molecular-target substrate (API route).

WHY. The pairing model's measured blind spot is diversifying deals --
zero disease overlap. Molecular targets sit one layer deeper: firms can
share target biology across different indications. ChEMBL (open access,
no key, no account) curates drug -> mechanism -> target links.

ROUTE (v2). The ChEMBL web services API, queried per drug name with
EXACT case-insensitive synonym equality -- no bulk download (the ~30 GB
sqlite-dump route of v0.76 is retired). Every response caches in bronze
via store.fetch_json, so interrupted runs resume for free and reruns are
instant. Expect a few thousand lookups on first run (roughly an hour at
polite pacing).

MATCHING INVARIANT. Name lookups use iexact filters only -- no fuzzy
search -- so failures are missing, never wrong. Firm -> drug names come
from events.csv (approvals) and trials.csv (Drugs + Drug:/Biological:
interventions), each with a FirstSeen date for as-of construction.

HONESTY GATE. ebi.ac.uk is unreachable from the build environment;
`chembl-probe` runs ONE real lookup (dupilumab -> IL-4R alpha expected)
and unlocks `chembl-ingest` only when the live response parses.
"""

from __future__ import annotations

import logging
import re
import time
from datetime import date

from biointel import config, store
from biointel.store import fetch_json

log = logging.getLogger(__name__)

API = config.CHEMBL_API
CHEMBL_DIR = config.BRONZE / "chembl"
PROBE_MARKER = CHEMBL_DIR / "PROBE_OK"
DRUG_TARGETS_TABLE = "drug_targets"
OUT_COLS = ["IID", "DrugNameRaw", "ChEMBLId", "ChEMBLName", "TargetName", "TargetType", "FirstSeen"]
PACE = 0.35  # seconds between uncached calls; polite, no key


def _drug_norm(s: str) -> str:
    s = re.sub(r"[^A-Z0-9 ]", " ", (s or "").upper())
    return re.sub(r" +", " ", s).strip()


_INTERV_PREFIX = re.compile(r"(?i)^(drug|biological|combination product)\s*:")


def firm_drug_names() -> dict:
    """(IID, normalized drug name) -> earliest date seen."""
    out = {}

    def note(iid, raw, d):
        n = _drug_norm(raw)
        if len(n) < 4 or n.isdigit():
            return
        k = (str(iid), n)
        if d and (k not in out or d < out[k]):
            out[k] = d
        elif k not in out:
            out[k] = ""

    for r in store.read_table("events"):
        if r.get("Drug"):
            note(r["IID"], r["Drug"], (r.get("Date") or "")[:10])
    for r in store.read_table("trials"):
        d = (r.get("StartDate") or "")[:10]
        for part in re.split(r"[;|]", r.get("Drugs") or ""):
            if part.strip():
                note(r["IID"], part, d)
        for part in re.split(r"[;|]", r.get("Interventions") or ""):
            p = part.strip()
            if _INTERV_PREFIX.match(p):
                note(r["IID"], _INTERV_PREFIX.sub("", p), d)
    return out


def _get(path: str, params: dict) -> dict:
    time.sleep(PACE)
    return fetch_json(f"{API}/{path}", params=params, tag="chembl", cache=True)


def _lookup_molecule(name: str):
    """Exact-insensitive synonym match -> (chembl_id, pref_name) or None.
    Falls back to pref_name__iexact. No fuzzy search, ever."""
    for filt in ("molecule_synonyms__molecule_synonym__iexact", "pref_name__iexact"):
        try:
            data = _get("molecule.json", {filt: name, "limit": "1"})
        except Exception:
            return None
        mols = data.get("molecules") or []
        if mols:
            m = mols[0]
            return (m.get("molecule_chembl_id"), m.get("pref_name") or "")
    return None


def _mechanism_targets(chembl_id: str) -> list:
    """[(target_chembl_id, action)] for one molecule."""
    try:
        data = _get("mechanism.json", {"molecule_chembl_id": chembl_id, "limit": "20"})
    except Exception:
        return []
    return [
        (m.get("target_chembl_id"), m.get("action_type") or "")
        for m in (data.get("mechanisms") or [])
        if m.get("target_chembl_id")
    ]


def _target_detail(target_chembl_id: str):
    try:
        data = _get("target.json", {"target_chembl_id": target_chembl_id, "limit": "1"})
    except Exception:
        return None
    ts = data.get("targets") or []
    if ts:
        return (ts[0].get("pref_name") or "", ts[0].get("target_type") or "")
    return None


def probe() -> dict:
    hit = _lookup_molecule("DUPILUMAB")
    if not hit:
        return {
            "status": "fail",
            "message": "PROBE FAILED: dupilumab lookup returned nothing "
            "or the endpoint was unreachable. Paste this "
            "output back.",
        }
    cid, pname = hit
    tgts = _mechanism_targets(cid)
    det = _target_detail(tgts[0][0]) if tgts else None
    if det and det[0]:
        CHEMBL_DIR.mkdir(parents=True, exist_ok=True)
        PROBE_MARKER.write_text(date.today().isoformat())
        return {
            "status": "ok",
            "message": f"PROBE OK: DUPILUMAB -> {cid} ({pname}) -> "
            f"{len(tgts)} mechanism(s), first target "
            f"'{det[0]}' [{det[1]}]. `chembl-ingest` is "
            "unlocked (minutes, ~150 cached calls; re-runs resume).",
        }
    return {
        "status": "fail",
        "message": f"Molecule matched ({cid}) but mechanism/target "
        "parse failed. Raw evidence -- paste back:\n"
        f"mechanisms={tgts!r} target={det!r}",
    }


def _paginate(path: str, params: dict, key: str):
    """Yield records across pages using the API's page_meta envelope."""
    offset = 0
    while True:
        p = dict(params)
        p.update({"limit": "1000", "offset": str(offset)})
        data = _get(path, p)
        recs = data.get(key) or []
        for r in recs:
            yield r
        meta = data.get("page_meta") or {}
        if not meta.get("next") or not recs:
            return
        offset += len(recs)


def _batched_set(resource: str, ids: list, only: str, key: str):
    """Fetch records via the /set/ endpoint in batches of 100."""
    out = []
    for i in range(0, len(ids), 100):
        chunk = ";".join(ids[i : i + 100])
        try:
            data = _get(f"{resource}/set/{chunk}.json", {"only": only})
        except Exception:
            continue
        out.extend(data.get(key) or [])
        if (i // 100) % 10 == 9:
            log.info(f"  {resource}: {i + 100}/{len(ids)}")
    return out


def ingest() -> dict:
    """BULK-INVERTED (v3): pull ChEMBL's full mechanism table (~10
    pages), then the mechanism-bearing molecules' synonyms and the
    targets in /set/ batches, and match OUR drug names locally with the
    same exact normalization. ~100-150 API calls total, minutes not
    hours, all cached."""
    if not PROBE_MARKER.exists():
        return {
            "status": "fail",
            "message": "Refusing: run `python -m biointel chembl-probe` first (rule 0.6.3).",
        }
    log.info("Fetching full mechanism table...")
    mechs = list(_paginate("mechanism.json", {}, "mechanisms"))
    mol2tgt = {}
    for m in mechs:
        cid, tid = m.get("molecule_chembl_id"), m.get("target_chembl_id")
        if cid and tid:
            mol2tgt.setdefault(cid, set()).add(tid)
    mol_ids = sorted(mol2tgt)
    tgt_ids = sorted({t for s in mol2tgt.values() for t in s})
    log.info(
        f"  {len(mechs):,} mechanisms; {len(mol_ids):,} molecules; "
        f"{len(tgt_ids):,} targets. Fetching names in batches..."
    )
    name2mol, mol2name = {}, {}
    for m in _batched_set(
        "molecule", mol_ids, "molecule_chembl_id,pref_name,molecule_synonyms", "molecules"
    ):
        cid = m.get("molecule_chembl_id")
        if not cid:
            continue
        pn = m.get("pref_name") or ""
        mol2name[cid] = pn
        cands = [pn] + [s.get("molecule_synonym") or "" for s in (m.get("molecule_synonyms") or [])]
        for nm in cands:
            n = _drug_norm(nm)
            if len(n) >= 4 and n not in name2mol:
                name2mol[n] = cid
    tgt_detail = {}
    for t in _batched_set("target", tgt_ids, "target_chembl_id,pref_name,target_type", "targets"):
        if t.get("target_chembl_id") and t.get("pref_name"):
            tgt_detail[t["target_chembl_id"]] = (t["pref_name"], t.get("target_type") or "")
    firm_drugs = firm_drug_names()
    n_rows, matched, firms, seen = 0, set(), set(), set()
    rows_out: list[dict] = []
    for (iid, dn), first in sorted(firm_drugs.items()):
        cid = name2mol.get(dn)
        if not cid:
            continue
        for tid in sorted(mol2tgt.get(cid, ())):
            det = tgt_detail.get(tid)
            if not det:
                continue
            key = (iid, cid, det[0])
            if key in seen:
                continue
            seen.add(key)
            rows_out.append(
                {
                    "IID": iid,
                    "DrugNameRaw": dn,
                    "ChEMBLId": cid,
                    "ChEMBLName": mol2name.get(cid, ""),
                    "TargetName": det[0],
                    "TargetType": det[1],
                    "FirstSeen": first,
                }
            )
            n_rows += 1
        matched.add((iid, dn))
        firms.add(iid)
    store.write_table(DRUG_TARGETS_TABLE, rows_out, OUT_COLS)
    return {
        "status": "ok",
        "message": f"drug_targets: {n_rows:,} firm-target rows; "
        f"{len(matched):,} of {len(firm_drugs):,} (firm, "
        f"drug) pairs matched across {len(firms)} firms "
        f"-> table {DRUG_TARGETS_TABLE}",
    }
