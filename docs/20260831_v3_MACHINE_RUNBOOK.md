docs/20260831_v3_MACHINE_RUNBOOK.md

# MACHINE_RUNBOOK v2 — Jason's machine (bioindustry / bioproject)

v2 (end of session 2026-08-29): rows 1.9, 1.10, 1.13, 2.5 updated for the src layout; rows 1.16–1.18 and 2.9–2.10 added; all other rows unchanged from v1.

Structure: per J. Banks message of 2026-08-29 ("MACHINE_RUNBOOK per manual
section 7.1"); the uploaded manual (20260823_OPERATINGMANUAL_NEW.md) has no
section 7.1, so the structure below is a proposal and the content is sourced
line by line to this session's transcript (chat "7_Project assessment",
2026-08-29). Anything without a transcript source is listed under Questions.

## 1. Fixed facts

| # | Convention | Value | Transcript source |
|---|---|---|---|
| 1.1 | Repository root | `C:\Users\JB\Documents\dev\bioindustry` | J. Banks: "jason project dir root is PS C:\Users\JB\Documents\dev\bioindustry>" |
| 1.2 | Remote | `https://github.com/harrisonbanks/bioproject.git`, cloned into root with `git clone <url> .` | paste: "Cloning into '.'... Receiving objects: 100% (62/62)" |
| 1.3 | Repository visibility | public as of 2026-08-29 (anonymous clone from the assistant container succeeded) | assistant `git clone` with no credentials, first tool call of the audit |
| 1.4 | Working branch | `jason/refactor`, created from `main` at b52de01 | paste: "Switched to a new branch 'jason/refactor'" |
| 1.5 | Git identity | `Jason J Banks` / `jasonjbanks01@gmail.com` | paste: `git config user.email` → `jasonjbanks01@gmail.com` |
| 1.6 | Virtual environment | `C:\Users\JB\Documents\dev\bioindustry\.venv`, created with `python -m venv .venv`, activation `.\.venv\Scripts\Activate.ps1` worked without an execution-policy change | paste: prompt changed to `(.venv) PS ...` immediately after activation |
| 1.7 | Python | 3.13 (cp313 wheels installed) | paste: `scikit_learn-1.9.0-cp313-cp313-win_amd64.whl` |
| 1.8 | Installed packages | numpy 2.5.2, scikit-learn 1.9.0, scipy 1.18.1, requests 2.34.2, openpyxl 3.1.5 (+ transitive); spacy NOT installed | paste: "Successfully installed ... numpy-2.5.2 ... scikit-learn-1.9.0 ... scipy-1.18.1 ... requests-2.34.2 ... openpyxl-3.1.5" |
| 1.9 | Code location | `C:\Users\JB\Documents\dev\bioindustry\src\biointel\` (entry `python -m biointel <cmd>`, installed editable into `.venv`) | step-2 commit 55bc9c1 paste; `python -m biointel predict` paste |
| 1.10 | Data location | `C:\Users\JB\Documents\dev\bioindustry\data\` (bronze/silver/gold), git-ignored, regenerated on this machine 2026-08-29 from the public APIs, moved from `app\data` at step 2 | paste: "1357 targets ranked ... -> C:\Users\JB\Documents\dev\bioindustry\data\gold\ma_predictions.csv" |
| 1.11 | Data snapshot facts | 1,379 universe members; 468 M&A events (447 target-role); 1,508 positives; 91,014 firm-quarters; 1,165 FDA events in event study; 1,357 targets ranked, 22 acquirer-side; pairs re-rank 124 events, median rank 80/862, hit@10 0.27 | pastes of `universe`, `labels`, `study-all`, `features`, `predict`, `pairs-full-exact` |
| 1.12 | Layers skipped on this machine | `text-ingest` (skipped by decision: text feature adds nothing, chat 4 v0.55); `cparty-all` (spacy absent → relationships merged 0 deal rows) | J. Banks: "Given that it is completely unuseful can it be skipped" / paste: "0 deal rows merged" |
| 1.19 | Research library (gate L1) | store `data\bronze\library\<aa>\<sha256>.<ext>`; manifest `data\bronze\library\manifest-sha256.txt`; tables references/captures/reference_links; commands `library ...`; meta files are `<name>.meta.json` (no data extension) | paste of 2026-08-31: index 733, verify 0 |
| 1.13 | Regression baseline | `docs\regression_baseline.txt`: `ma_predictions.csv 04061e33…530d`, `pair_full_exact_report.txt 960307e2…e81b` | paste of `Get-Content docs\regression_baseline.txt` |
| 1.14 | Line endings | `.gitattributes` = `* text=auto eol=lf`; no tracked file stored CRLF | paste: `ls-files --eol | Select-String "i/crlf"` → empty |
| 1.16 | Package commands | `& "C:\Users\JB\Documents\dev\bioindustry\.venv\Scripts\python.exe" -m biointel <cmd>`; help prints 49 lines, 55 commands dispatched | step-2 script output paste |
| 1.17 | Dev tools in the venv | pytest, ruff, mypy via `pip install -e ".[dev]"`; `uv` uninstalled | pastes: "7 passed", "45 files reformatted", `pip uninstall uv` |
| 1.18 | Regression hash check, PowerShell-native | `(Get-FileHash "<root>\data\gold\ma_predictions.csv" -Algorithm SHA256).Hash -eq "<baseline>"` → `True`; same for `pair_full_exact_report.txt` | step-2 and step-5 pastes |
| 1.15 | Extraction folder pattern | `C:\Users\JB\Downloads\<zipname>\` (zip extracted by J. Banks; assistant never extracts) | J. Banks: "i will download to C:\Users\JB\Downloads\20260829_v1_biointel_refactor_step0 and will do this way going forward" |

## 2. Command conventions (proven)

| # | Rule | Form | Transcript source |
|---|---|---|---|
| 2.1 | Absolute paths only; no command depends on the current directory | `git -C "C:\Users\JB\Documents\dev\bioindustry" <args>` and `& "C:\Users\JB\Documents\dev\bioindustry\.venv\Scripts\python.exe" "<absolute script path>"` | failure: `Copy-Item ... -Destination .` executed while prompt was in `app\`, scripts landed in `app\scripts\`; rule stated by J. Banks in the standing correction |
| 2.2 | Every command annotated with its expected result on the following `#` line | `# expected: ...` | J. Banks standing correction, item 2; all subsequent blocks pasted back with the annotations intact |
| 2.3 | No inline `python -c` with embedded quotes | PowerShell strips embedded double quotes from arguments to native executables; both single- and double-quoted forms failed | pastes: `SyntaxError: '(' was never closed` (single-quoted) and `Missing type name after '['` (double-quoted) |
| 2.4 | Counting or inspection is done in PowerShell natively or by a script file | `(Select-String -Path ... -Pattern '...' -AllMatches | ForEach-Object { $_.Matches } | ForEach-Object { $_.Groups[1].Value } | Sort-Object -Unique).Count` | paste: returned `55` |
| 2.5 | Refactor scripts are run by the venv python from the repo root path and end with the regression check; they are not idempotent (guard asserts stop a second run without changes) | `& "...\.venv\Scripts\python.exe" "...\scripts\refactor\NN_name.py"` | pastes of steps 0–5; second run of `50_config_logging.py` stopped at its first assert with the tree already edited |
| 2.6 | Commit form | `git -C "<root>" add -A` then `git -C "<root>" commit -m "..."`; `commit -am` does not stage new files | paste: `.gitattributes` left untracked after `commit -am` |
| 2.7 | One block per turn; paste returned before the next block is issued | — | J. Banks: "u move to next step without waiting for test to finish"; "u gave me 10 and 11 without waiting for 10" |
| 2.9 | Delivery is a single file with the deploy path on line 1; Jason downloads to `C:\Users\JB\Downloads\<file>` and the block copies it to the absolute repo path | `Copy-Item -Path "C:\Users\JB\Downloads\NN_name.py" -Destination "<root>\scripts\refactor\NN_name.py" -Force` | steps 1c–5 pastes |
| 2.10 | Commit form for a gate | `git -C "<root>" add -A` → `git -C "<root>" commit -m "..."` → `git -C "<root>" push` | steps 4–5 pastes |
| 2.8 | On any pasted failure: one-line diagnosis naming the evidence, the single next command, its expected result | — | J. Banks standing correction, item 3 |

## 3. Known hazards on this machine

| # | Hazard | Handling | Transcript source |
|---|---|---|---|
| 3.1 | PSReadLine is disabled ("PowerShell detected that you might be using a screen reader") | Pasted output may be missing lines; two progress lines of `10_delete.py` were absent from the paste while the assertions behind them provably ran; carried as "output drop, cause unknown, substance verified by rerun" | paste header of document 3; `10_delete.py` paste |
| 3.2 | Windows CSV newline handling | Package opens CSVs with `newline=""` after a `_csv.Error` on Harrison's machine (chat 4, v27); not reproduced here | chat 4 turn 275–276 |
| 3.3 | `.vscode\settings.json` in the repo points at `C:\Users\bocchirock\...\.venv` | Not yet edited on this machine; step-2 item | audit item A.9; open item 12 |
| 3.4 | psql-style hazards | Do not apply to this project (no database) | J. Banks standing correction |

## 4. Questions (no transcript source)

| # | Question |
|---|---|
| 4.1 | Is PSReadLine to be re-enabled (`Import-Module PSReadLine`) to test whether the output drop in 3.1 disappears? |
| 4.2 | Has `.vscode\settings.json` been edited locally, or is VS Code not used on this machine? |
| 4.3 | Was git pre-installed on this machine (the clone succeeded without a `winget` step in the transcript)? |
| 4.4 | Delivery format: the uploaded manual ("Code delivery format", rule 3) says never a zip unless asked and rule 5 requires the deploy path as line 1 of every delivered file; the session used zips at J. Banks's instruction. Which controls going forward? |
