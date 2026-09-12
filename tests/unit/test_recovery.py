# tests\unit\test_recovery.py
"""R3-0c-ii locking tests.

Specimens are verbatim lines from the artifacts measured by block v57a
(evidence data\\exports\\20260912_v57a_r30ci_exports_inventory_evidence.txt),
per rule 4.20: parsers are written against real captures, never invented shapes.
"""

from __future__ import annotations

import re
from pathlib import Path

from biointel import recovery as R

SRC = Path(__file__).resolve().parents[2] / "src" / "biointel"

# ---- verbatim specimens (v57a inventory) ------------------------------------
TRIAGE = (
    "BLOCK START 2026-09-09T08:48:43.6327217-04:00\r\n"
    "TRIAGE-HUMAN 179 rows (disagreements + undecided):\r\n"
    "S00cc2d2668c01a25 | CIK:1792044 2023-02-27 pipeline_gap | claude-sonnet-5: wrong - The sentence describes enhancing existing platform/capabilities to build a portfolio, which fits \"platform\" category rather than pipeline_gap. | claude-haiku-4-5: correct - ...\r\n"
    "  VERBATIM: Our goal is to enhance our proven scientific capabilities and current global platform to create a durable and higher-margin portfolio of products.\r\n"
    "S00d866a2c5fb2b31 | CIK:1821323 2022-03-14 therapeutic_area | claude-sonnet-5: wrong - ... | claude-haiku-4-5: correct - ...\r\n"
    "  VERBATIM: our goal is to provide functional cures to patients with chronic diseases.\r\n"
)
JUDGED = (
    "JUDGED S00cc2d2668c01a25 wrong; retired 1 relabeled 0\r\n"
    "JUDGED S00d866a2c5fb2b31 wrong; retired 0 relabeled 1 -> commercial_infrastructure\r\n"
    "R2-JUDGED Rbe8c144245887485 wrong\r\n"
    "AUTO-APPLIED 4331 rows across 27 standing clusters; residual carried 411\r\n"
)
WORKSHEET = (
    "key,verdict,ai_reason,company,date,category,sentence,doc_url,note\r\n"
    "S5ce492dddbc5f407,correct,\"reason text\",\"SPRUCE BIOSCIENCES, INC.\",2022-03-14,therapeutic_area,"
    "\"focused on developing therapies for rare endocrine disorders\",https://x,\r\n"
    "S49871924e86b7a90,wrong,\"reason text\",TCR2 THERAPEUTICS INC.,2020-03-30,pipeline_gap,"
    "\"our goal is to obtain Fast Track designation\",https://x,\r\n"
)
# library reference ids share the R + 16 hex shape but are a different namespace
REFERENCES = (
    "ref_id,ref_type,url,doi,pmid,sec_accession\r\n"
    "R41a78f6c5b23f8bf,sec_filing,https://www.sec.gov/x.htm,,,000119312523170765\r\n"
)


def _art(name: str, text: str, sha: str = "a" * 64) -> R.Artifact:
    era, sess = R.era_session_of(name, "2026-09-09T12:00:00+00:00")
    return R.Artifact(name, "/tmp/" + name, len(text), "2026-09-09T12:00:00+00:00", sha, "utf-8", era, sess, text)


# ---- 1. direct evidence parser specimen -------------------------------------
def test_header_verbatim_parser_recovers_key_and_sentence():
    _v, sents = R.parse_block_evidence(_art("20260909_v48i_triage_run_evidence.txt", TRIAGE))
    got = {k: p["sentence"] for k, p, _s in sents}
    assert "S00cc2d2668c01a25" in got
    assert got["S00cc2d2668c01a25"].startswith("Our goal is to enhance")
    assert got["S00d866a2c5fb2b31"].startswith("our goal is to provide functional cures")


def test_worksheet_parser_carries_key_sentence_and_operator_verdict():
    verds, sents = R.parse_worksheet_csv(_art("priorities_worksheet.csv", WORKSHEET))
    assert dict((k, v) for k, v, _s in verds) == {
        "S5ce492dddbc5f407": "correct", "S49871924e86b7a90": "wrong"}
    assert len(sents) == 2


# ---- 2. proposer verdicts are never operator verdicts ------------------------
def test_model_verdicts_in_a_triage_header_are_not_operator_verdicts():
    verds, _s = R.parse_block_evidence(_art("20260909_v48i_triage_run_evidence.txt", TRIAGE))
    assert verds == []  # the header carries "claude-sonnet-5: wrong" and it is ignored


# ---- 3. historically wrong and suppressed key still recovers -----------------
def test_wrong_suppressed_key_recovers_to_its_original_sentence():
    arts = [_art("20260909_v48i_triage_run_evidence.txt", TRIAGE, "b" * 64),
            _art("20260910_v48ah_rulings_and_run_evidence.txt", JUDGED, "c" * 64)]
    maps, _stats = R.resolve(arts)
    m = next(x for x in maps if x.reviewed_key == "S00cc2d2668c01a25")
    assert m.verdict == "wrong"
    assert m.sentence.startswith("Our goal is to enhance")
    assert m.status == R.SRC_JUDGING


# ---- 4. multi-artifact provenance is preserved -------------------------------
def test_sentence_source_and_verdict_source_are_both_retained():
    arts = [_art("20260909_v48i_triage_run_evidence.txt", TRIAGE, "b" * 64),
            _art("20260910_v48ah_rulings_and_run_evidence.txt", JUDGED, "c" * 64)]
    maps, _stats = R.resolve(arts)
    m = next(x for x in maps if x.reviewed_key == "S00cc2d2668c01a25")
    files = {s.filename for s in m.evidence_sources}
    hashes = {s.sha256 for s in m.evidence_sources}
    roles = {s.role for s in m.evidence_sources}
    assert files == {"20260909_v48i_triage_run_evidence.txt", "20260910_v48ah_rulings_and_run_evidence.txt"}
    assert hashes == {"b" * 64, "c" * 64}
    assert roles == {"sentence", "verdict"}
    assert all(s.raw_lines for s in m.evidence_sources)


# ---- 5. relabel preserves all three identities -------------------------------
def test_relabel_keeps_reviewed_and_resulting_identity_separate():
    arts = [_art("20260909_v48i_triage_run_evidence.txt", TRIAGE, "b" * 64),
            _art("20260910_v48ah_rulings_and_run_evidence.txt", JUDGED, "c" * 64)]
    maps, _stats = R.resolve(arts)
    m = next(x for x in maps if x.reviewed_key == "S00d866a2c5fb2b31")
    assert m.original_category == "therapeutic_area"
    assert m.resulting_category == "commercial_infrastructure"
    assert m.resulting_key == R.s_key("CIK:1821323", "2022-03-14", "commercial_infrastructure")
    assert m.resulting_key != m.reviewed_key


# ---- 6. R-key exact statement recovery via the surviving table ----------------
def test_r_key_resolves_by_exact_statement_from_the_table_map():
    import hashlib
    ent, date, cat, stmt = "CIK:1", "2024-05-16", "commercial_infrastructure", "launching commercial sales"
    rkey = "R" + hashlib.sha256(f"{ent}|{date}|{cat}|{stmt}".encode()).hexdigest()[:16]
    arts = [_art("20260911_v51h_r2_verdicts_evidence.txt", f"R2-JUDGED {rkey} wrong\r\n", "d" * 64)]
    maps, _stats = R.resolve(arts, table_map={rkey: {"sentence": stmt, "category": cat,
                                                     "entity_key": ent, "stated_at": date}})
    m = next(x for x in maps if x.reviewed_key == rkey)
    assert m.status == R.SRC_TABLE
    assert m.sentence == stmt


# ---- 7. conflicting direct evidence is held, not chosen ----------------------
def test_conflicting_sentences_for_one_key_are_held_as_ambiguous():
    a = _art("20260909_v48i_triage_run_evidence.txt", TRIAGE, "b" * 64)
    alt = TRIAGE.replace("Our goal is to enhance our proven scientific capabilities",
                         "A materially different sentence for the same key")
    b = _art("20260909_v48q_boundary_sweep_triage_evidence.txt", alt, "e" * 64)
    maps, _stats = R.resolve([a, b])
    m = next(x for x in maps if x.reviewed_key == "S00cc2d2668c01a25")
    assert m.status == R.SRC_AMBIGUOUS
    assert m.reason == R.R_CONFLICT_SENTENCE


# ---- 8. replay ambiguity is held, and replay never overwrites direct ---------
def test_replay_with_two_equal_length_candidates_is_ambiguous():
    key = R.s_key("CIK:9", "2020-01-01", "platform")
    arts = [_art("20260910_v48ah_rulings_and_run_evidence.txt",
                 f"JUDGED {key} wrong; retired 1 relabeled 0\r\n"
                 f"{key} | CIK:9 2020-01-01 platform\r\n", "f" * 64)]

    def replayer(ent, date):
        return [{"category": "platform", "sentence": "AAAA"}, {"category": "platform", "sentence": "BBBB"}]

    maps, _stats = R.resolve(arts, replayer=replayer)
    m = next(x for x in maps if x.reviewed_key == key)
    assert m.status == R.SRC_AMBIGUOUS
    assert m.reason == R.R_REPLAY_AMBIGUOUS


def test_replay_longest_wins_and_direct_provenance_is_never_overwritten():
    key = R.s_key("CIK:9", "2020-01-01", "platform")
    arts = [_art("20260910_v48ah_rulings_and_run_evidence.txt",
                 f"JUDGED {key} wrong; retired 1 relabeled 0\r\n"
                 f"{key} | CIK:9 2020-01-01 platform\r\n", "f" * 64)]

    def replayer(ent, date):
        return [{"category": "platform", "sentence": "short"},
                {"category": "platform", "sentence": "a much longer candidate sentence"}]

    maps, _stats = R.resolve(arts, replayer=replayer)
    m = next(x for x in maps if x.reviewed_key == key)
    assert m.status == R.SRC_REPLAY
    assert m.sentence == "a much longer candidate sentence"

    # with direct sentence evidence present, replay must not touch the mapping
    direct = [_art("20260909_v48i_triage_run_evidence.txt", TRIAGE, "b" * 64),
              _art("20260910_v48ah_rulings_and_run_evidence.txt", JUDGED, "c" * 64)]
    maps2, _s2 = R.resolve(direct, replayer=lambda e, d: [{"category": "pipeline_gap", "sentence": "REPLAYED"}])
    m2 = next(x for x in maps2 if x.reviewed_key == "S00cc2d2668c01a25")
    assert m2.status == R.SRC_JUDGING
    assert "REPLAYED" not in m2.sentence


# ---- 9. no guessing fallback -------------------------------------------------
def test_verdict_without_any_sentence_evidence_stays_unresolved():
    arts = [_art("20260910_p2h_phaseA_regeneration_evidence.txt",
                 "JUDGED S1111111111111111 wrong; retired 1 relabeled 0\r\n", "g" * 64)]
    maps, _stats = R.resolve(arts)
    m = maps[0]
    assert m.status == R.SRC_UNRESOLVED
    assert m.reason == R.R_NO_SENTENCE
    assert m.sentence == ""


# ---- 10. determinism: same bytes, same parse ---------------------------------
def test_same_artifact_reproduces_the_same_mapping():
    a = _art("20260909_v48i_triage_run_evidence.txt", TRIAGE, "b" * 64)
    b = _art("20260910_v48ah_rulings_and_run_evidence.txt", JUDGED, "c" * 64)
    one, _ = R.resolve([a, b])
    two, _ = R.resolve([a, b])
    assert [(m.reviewed_key, m.sentence, m.verdict, m.status) for m in one] == \
           [(m.reviewed_key, m.sentence, m.verdict, m.status) for m in two]


# ---- 11. namespaces: library ref_id is not a candidate id --------------------
def test_library_ref_ids_are_not_candidate_ids():
    a = _art("library/references.csv", REFERENCES, "h" * 64)
    verds, sents = R.parse_worksheet_csv(a)
    assert verds == [] and sents == []          # no key/sentence columns: refused
    maps, stats = R.resolve([a])
    assert maps == []                            # no candidate id was claimed
    assert stats["unclassified_identifier"] >= 1  # the shape match is reported, not counted


def test_shape_match_alone_never_creates_a_mapping():
    a = _art("20260909_notes.txt", "mentions S0123456789abcdef in prose only\r\n", "i" * 64)
    maps, stats = R.resolve([a])
    assert maps == []
    assert stats["unclassified_identifier"] == 1


# ---- module discipline: recovery.py never writes a table of record ----------
_WRITERS = re.compile(r"store\.(write_table|append_rows|update_rows|add_columns|export_csv|write_export)")


def test_recovery_module_never_calls_a_store_writer():
    text = (SRC / "recovery.py").read_text(encoding="utf-8")
    offenders = [f"{i}: {ln.strip()}" for i, ln in enumerate(text.splitlines(), 1)
                 if _WRITERS.search(ln) and not ln.lstrip().startswith("#")]
    assert not offenders, "recovery.py must be read-only against tables of record:\n" + "\n".join(offenders)
