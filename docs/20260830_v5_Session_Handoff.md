docs/20260830_v5_Session_Handoff.md

# Session handoff v3 — bioproject, 2026-08-30 (refactor complete; design phase opened)

Supersedes docs/20260829_v2_Session_Handoff.md. Structure per J. Banks's
2026-08-29 instruction (attachments, session-start sequence with lineage by
hash, verified state, standing rules, open queue). Every state claim below
was evidenced by a paste in the 2026-08-29 session.

## 1. Required attachments for the next session

0. docs/20260830_v2_Design_Principles.md — P1–P15, binding; read first.
0a. docs/20260830_v3_Ontology_and_Matching_Design.md — ontology for all models (v3: global universe and stubs, price-action attributes, calendar sources of record, manual notes, benchmarks, Model 4).
0b. docs/20260830_v2_FDA_Catalyst_Research.md — Model 2 research synthesis.
0c. docs/20260830_v1_FDA_Catalyst_Product_Design.md — Model 2 requirements (R1–R8, roadmap F1–F9), under review.
1. docs/20260823_OPERATINGMANUAL_NEW.md — process of record.
2. docs/20260829_v2_MACHINE_RUNBOOK.md — Jason's machine conventions (updated for the src layout).
3. This file.
4. Repository access: https://github.com/harrisonbanks/bioproject (public at time of writing), branch jason/refactor.
5. docs/20260829_v1_Python_Project_Architecture_Instructions.md — SUPERSEDED; retained only as the record of what was adopted and then overridden (see §4.6–4.8). Do not apply its rules.

## 2. Session-start sequence

```
git -C "C:\Users\JB\Documents\dev\bioindustry" log --oneline -18
# expected, newest first:
#   <hash>  Docs: Model 2 product design, ontology v3, principles v2, research v2, handoff v5, PROJECT_STATUS v0.84, README
#   320435e Docs: PROJECT_STATUS v0.83 and README (FDA research, ontology v2 linked)
#   e387163 Docs: ontology v2 (shared regulatory-event extension), handoff v4, PROJECT_STATUS v0.83, README; retire ontology v1 and handoff v3
#   0cc5e25 Docs: FDA catalyst price-reaction research synthesis
#   1b85bb1 Docs: design principles, ontology and matching design, handoff v3; PROJECT_STATUS v0.82; README; retire handoff v2
#   9db4cea Docs: standalone system diagram (PNG, SVG)
#   c2cea4d Docs: session handoff v2, machine runbook v2, system diagram
#   da29a85 Refactor step 5: endpoints in config.py; package logging; ruff LF
#   5c16ec8 Refactor step 4: ruff lint fixes and formatting; Ruff as editor formatter
#   55bc9c1 Refactor step 2: src layout, pyproject, scripts/docs/data directories
#   49572ec Refactor step 1c: coverage manifest tag; portable VS Code venv path
#   f0ceeb0 Refactor step 1b: credentials from environment
#   26133aa Refactor step 1: delete dead code and duplicates
#   c5bbf6c Normalize line endings to LF
#   76a3ba3 Refactor step 0: regression baseline
#   b52de01 Initial commit: platform at PROJECT_STATUS v0.68, pre-refactor
git -C "C:\Users\JB\Documents\dev\bioindustry" status --short
# expected: empty
Get-Content "C:\Users\JB\Documents\dev\bioindustry\docs\regression_baseline.txt"
# expected: ma_predictions.csv 04061e33a77056ae6e8519273ca73c6de0329be856e389a8a69be8cb1329530d
#           pair_full_exact_report.txt 960307e2dbb259a3b6e452e005469b3e9cb7a87618a59668654f3905db35e81b
```
No code change is issued until all three outputs are pasted and match.

## 3. Verified state

3.1 Layout (commit 55bc9c1): `src/biointel/` package with `interfaces/cli.py` and `__main__.py`; entry point `python -m biointel <cmd>`; `scripts/` holds the ten diagnostics and `scripts/refactor/` (six refactor scripts + `_regress.py`); `docs/` holds PROJECT_STATUS.md, README.md, this handoff; `data/` (git-ignored) holds bronze/silver/gold; `tests/unit/` has two test files (7 tests); `pyproject.toml`, `requirements.lock`, `.python-version`, `.env.example`, `.gitattributes`.
3.2 Removed (26133aa): fossil tree `biointel/biointel1/`, Excel workbook, four duplicate files, dead functions `crsp_import`, `ner_status`, `_pair_by_date`, the dead USPTO bulk route in `patents.py` (8 functions, 6 constants), CLI branches `patents-probe`/`patents-ingest`. Rejected pairing engines live verbatim in `src/biointel/baselines.py`. CLI dispatches 55 commands.
3.3 Credentials (f0ceeb0): none in code. `config.require("BIOINTEL_USER_AGENT")` / `("BIOINTEL_ALPHA_VANTAGE_KEY")` read `<root>\.env` (git-ignored, created locally on Jason's machine with his own user-agent and the existing key).
3.4 Endpoints (da29a85): every HTTP address is a `config.py` constant (15 total); modules reference them. Package logging via `logging.getLogger(__name__)`; `cli.main()` configures INFO to stdout, message-only. 32 `print()` calls converted; `cli.py` keeps its prints; `scripts/` keeps prints.
3.5 Lint (5c16ec8, da29a85): ruff configured in `pyproject.toml` (`select E,F,W,I`; `ignore E501,E741`; `line-ending = "lf"`), 45 files formatted, VS Code set to Ruff formatter with format-on-save. Nine findings deliberately left visible: 5×E402 in `scripts/debug_fit.py` (checkpoint pattern), 2×E731 (`improve.py`, `cli.py` lambdas), 2×F841 (`score.py` `toks`, `study.py` `prev_adj`).
3.6 Regression: at every gate `predict` and `pairs-full-exact` reproduced the step-0 hashes on Jason's regenerated snapshot (1,379 members; 1,357 targets ranked; 22 acquirer-side; pairs median rank 80/862, hit@10 0.27). No model output changed at any step.
3.7 Data: regenerated on Jason's machine 2026-08-29; `text-ingest` skipped by decision; `cparty-all` not run (spacy absent). The data tables are model-agnostic and were not altered.
3.8 Branch pushed: origin/jason/refactor at the docs commit above (9db4cea before it). origin/main = b52de01 (unchanged; no pull request opened yet).
3.11 Decisions of 2026-08-30 (afternoon), recorded as P13–P15 and in ontology v3 / product design v1: global universe with ADRs and stubs; daily bars only, no trading; all event classes at once with delays first-class; cross-event ranking with attribution and no assumption about purpose; no options; benchmarks XBI plus user-defined; calendar sources of record = FDA (past) + SEC EDGAR full-text 8-K mining (forward) + FDA AdCom calendar + CT.gov completion dates, aggregators as cross-check only; manual templated notes; Model 4 = Horizon Scanning (entity discovery from papers/news); Model 3 unassigned.
3.10 Model 2 research note committed (0cc5e25): formal framing (event study; catalyst trading; run-up and post-announcement drift; investor distraction), evidence base, theses T1–T6, event taxonomy, candidate models M2.1–M2.7, rules R1–R8, data gaps (forward calendar is the critical missing asset), evaluation protocol.
3.9 Decisions of 2026-08-30 (recorded as principles P1–P8): tables stay model-agnostic, no split; separation enforced at model input lists; entities neutral; objectives a dimension; manual layer general; model framework with one yardstick; existing models keep purposes; general-case-first requirements. Table split proposal withdrawn; Architecture Instructions superseded (P9).

## 4. Standing rules (agreed 2026-08-29)

4.1 Every machine command names its source (RUNBOOK section, manual section) or is marked a proposal.
4.2 Every done-claim carries pasted evidence or is not made.
4.3 One block per turn, absolute paths, expected result annotated per command, wait for the paste (RUNBOOK 2.1, 2.2, 2.7).
4.4 Secrets redacted to first-4/last-4 in all discussion.
4.5 Deliveries are single files with the deploy path on line 1 (manual, Code delivery format 3 and 5); zips only if asked.
4.6 Package manager: venv + pip only; `uv` is not used (override of Architecture Instructions §3, §10 recorded). Definition-of-done commands run as `& "<root>\.venv\Scripts\python.exe" -m ruff check src scripts tests`, `... -m ruff format --check src scripts tests`, `... -m pytest tests/unit`, plus the two regression hashes.
4.7 No file splits by line count; no domain/services/adapters layering; no `mypy --strict` (Architecture Instructions §4, §5.2, §8.2 dropped by J. Banks 2026-08-29: industry practice, not invented rules).
4.8 Data tables are model-agnostic; separation between the M&A model and the FDA/price model is enforced at each model's input list, never by splitting tables. The hand scorecard in `score.py` may read market cap and event CAR; the paper must describe its inputs accurately.
4.9 Output-drop caveat: pasted terminal output has repeatedly omitted lines (five instances, cause unknown, PSReadLine disabled); substance is verified by status/hash commands, never by the presence of a printed line.

4.10 Design principles P1–P15 are binding and override generic rules in any other document.

## 5. Open queue (priority order)

1. **Key rotation (security).** Alpha Vantage key `HMSY…2P02` and Harrison's email are in git history (b52de01–49572ec) and the repository is public. Harrison: obtain a new key, set repository to private (Settings → General → Change visibility). Jason's `.env` currently uses the existing key; switch when rotated.
2. **Merge decision.** Branch jason/refactor is ready for a pull request into main (https://github.com/harrisonbanks/bioproject/pull/new/jason/refactor). Harrison's machine after merge: `git pull`, recreate `.venv`, `pip install -e ".[dev]"`, create `.env` from `.env.example`, move `app\data` to `data\` (or re-clone and copy data into `data\`). His commands change from `python cli.py X` to `python -m biointel X`.
3. **Review the Ontology and Matching Design (v1)** and its §8 open questions; approve or amend before roadmap step A starts.
3a. **Review the FDA Catalyst Product Design v1** (requirements) and ontology v3 §§3.1a, 3.2a, 3.6–3.8; approve or amend; then roadmap F1 (event table) which shares its schema with ontology step A.
3b. **Model 4 Horizon Scanning design document** — not yet written; scope in ontology v3 §3.8.
4. **Scorecard vs fitted model (design decision, Jason + Harrison; P7).** `predict` ranks by the hand scorecard (`score.target_score`, weights set by judgement); the validated gen-2 model (`improve.py`, 2.2× chance on held-out deals) exists alongside. Decide whether `predict` should rank by the fitted model with the scorecard as explanation, or state the scorecard as the product.
5. **PROJECT_STATUS.md PART 0 is stale** (says v0.68 layout: `app\`, 26 modules, 47 commands, `cli.py` 509 lines). Regenerate from the live tree: `src/biointel` module list, 55 commands, new run form. Not scripted yet.
6. **Two unused variables** (`score.py:toks`, `study.py:prev_adj`) and two lambda assignments are human-review items; not auto-fixed.
7. **spacy** declared as optional group `ner`; install with `pip install -e ".[ner]"` and download the model before `cparty-all`.
8. **MACHINE_RUNBOOK question 4.1** (re-enable PSReadLine to test the output drop) remains open.
9. Roadmap steps A–I of the design document, gated and regression-checked like the refactor; first candidates: A (schema + validate) and D (model framework), which are independent.
