"""Step 1: delete dead code and duplicate files; isolate rejected engines.

Everything removed here was identified in the 2026-08-29 code audit and
is cross-referenced to PROJECT_STATUS.md entries. No logic is edited:
files are removed with `git rm`, functions are cut at their AST line
ranges, and the four rejected pairing engines move verbatim from
pairs.py to baselines.py (the paper's measured baselines, kept but out
of the shipped path). The step ends with the regression check from
step 0 and refuses to finish if either output hash changed.

Run from anywhere: python scripts/refactor/10_delete.py
Reverse: git checkout -- . ; git clean -fd  (before commit)
"""
from __future__ import annotations
import ast
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # refactor tooling only; not src/
import _regress as R

ROOT = R.ROOT
APP = ROOT / "app"
PKG = APP / "biointel"

# ---------------------------------------------------------------- file removals
REMOVE_PATHS = [
    # fossil first-port tree; every file superseded by app/ (audit A.2, A.3)
    ROOT / "biointel",
    # Excel workbook binary (112 KB), the Python port replaces it (audit A.3)
    APP / "20260724_securitymaster_v03.xlsm",
    # in-package copies of root scripts; identical bytes (audit A.4)
    PKG / "migrate_from_excel.py",
    PKG / "suggest_aliases.py",
    # in-package README is a stale prefix of app/README.md (audit A.3)
    PKG / "README.md",
    # second requirements file; merged into app/requirements.txt below (audit A.6)
    PKG / "requirements.txt",
]

# merged, ASCII, unpinned floors (the UTF-16 pip-freeze file is replaced)
REQUIREMENTS = """numpy>=2.0
scikit-learn>=1.5
scipy>=1.13
requests>=2.31
openpyxl>=3.1
"""

# ---------------------------------------------------------------- function removals
DEAD_FUNCS = {
    PKG / "pipeline.py": ["crsp_import"],                       # retired, PROJECT_STATUS v0.4x
    PKG / "sources" / "counterparty.py": ["ner_status"],        # never called
    PKG / "study.py": ["_pair_by_date"],                        # never called
    PKG / "sources" / "patents.py": [                           # bulk route dead, v0.71-0.73
        "_ranged_head", "probe", "_download_resumable", "_rows",
        "_company_canon_map", "build_from_local", "_find_local", "ingest",
    ],
}
DEAD_CONSTS = {
    PKG / "sources" / "patents.py": ["ODP_API_KEY", "S3_BASE", "ODP_SEARCH",
                                     "BULK_FILES", "PROBE_MARKER", "OUT_COLS"],
}
PATENTS_DOC = '''"""Patent layer: firm-technology substrate from Google Patents Public
Datasets on BigQuery (adopted route, PROJECT_STATUS v0.73).

`patents-sql` writes gold/patents_bigquery.sql with match.canon()
reproduced in SQL; the operator runs it in the BigQuery console and
drops the CSV export into data/bronze/patents_bulk/; `patents-import`
consumes that export into silver/patents.csv (IID, PatentId, dates,
CPCSubclass). The earlier PatentSearch API and USPTO bulk-download
routes are dead (v0.70-0.72) and were removed in refactor step 1.

JOIN. Assignee names match companies.csv Name/FDAAliases via
match.canon() exact equality, so failures are missing, never wrong.
"""'''

# ---------------------------------------------------------------- pairs -> baselines
MOVE_TO_BASELINES = ["evaluate_pairs", "_pair_features", "supervised_pairs",
                     "pairs_protocol", "_patent_docs", "_target_docs",
                     "pairs_substrates"]
BASELINES_HEADER = '''"""Rejected pairing engines, retained as the paper's measured baselines.

Moved verbatim from pairs.py in refactor step 1. None of these is on
the shipped path: `predict` uses the MASS-exact engine in pairs.py.
Ledger (PROJECT_STATUS 0.5 / v0.67 / v0.75 / v0.79):
  evaluate_pairs    cosine similarity, HR@5 0.216
  supervised_pairs  ranker, top-10 wash, median worse
  pairs_protocol    cosine / MASS-inspired 0.222 / latent-SVD 0.143 / hybrid
  pairs_substrates  paired trials vs patents (0.055) vs targets (0.120): nulls
"""
from __future__ import annotations
import csv as _csv
import re
from collections import defaultdict
from datetime import date, timedelta

from . import config
from .pairs import (_acquirer_side_iids, _firm_docs, _sim_matrix,
                    _size_factor, _tfidf_matrix)

'''

# ---------------------------------------------------------------- cli edits
CLI_HELP_REMOVE = ["  python cli.py patents-probe "]
CLI_BRANCH_REMOVE = ["patents-probe", "patents-ingest"]
CLI_IMPORT_REWRITES = [
    ("from biointel.pairs import pairs_substrates",
     "from biointel.baselines import pairs_substrates"),
    ("from biointel.pairs import evaluate_pairs, build_pair_feature",
     "from biointel.baselines import evaluate_pairs\n        from biointel.pairs import build_pair_feature"),
    ("from biointel.pairs import supervised_pairs",
     "from biointel.baselines import supervised_pairs"),
    ("from biointel.pairs import pairs_protocol",
     "from biointel.baselines import pairs_protocol"),
]


def git(*args: str) -> None:
    r = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"git {' '.join(args)} failed:\n{r.stderr}")


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")


def write(p: Path, s: str) -> None:
    p.write_text(s, encoding="utf-8", newline="\n")


def top_level_nodes(src: str) -> list[ast.stmt]:
    return ast.parse(src).body


def cut_nodes(src: str, names: set[str], kinds: tuple) -> tuple[str, dict[str, str]]:
    """Remove top-level defs/assigns whose name is in `names`; return new src and cut text by name."""
    lines = src.splitlines(keepends=True)
    cut: dict[str, str] = {}
    spans: list[tuple[int, int]] = []
    for n in top_level_nodes(src):
        if isinstance(n, ast.FunctionDef) and ast.FunctionDef in kinds and n.name in names:
            nm = n.name
        elif (isinstance(n, ast.Assign) and ast.Assign in kinds and len(n.targets) == 1
              and isinstance(n.targets[0], ast.Name) and n.targets[0].id in names):
            nm = n.targets[0].id
        else:
            continue
        start = (n.decorator_list[0].lineno if n.decorator_list else n.lineno) if isinstance(n, ast.FunctionDef) else n.lineno
        cut[nm] = "".join(lines[start - 1:n.end_lineno])
        spans.append((start - 1, n.end_lineno))
    missing = names - set(cut)
    if missing:
        sys.exit(f"expected names not found: {sorted(missing)}")
    keep = []
    i = 0
    for s, e in sorted(spans):
        keep.extend(lines[i:s]); i = e
        # swallow the blank lines that followed the removed block
        while i < len(lines) and lines[i].strip() == "":
            i += 1
    keep.extend(lines[i:])
    return "".join(keep), cut


def drop_unused_imports(src: str, candidates: list[str]) -> str:
    """Remove `import X` / `from X import a, b` names from `candidates` that no longer appear in the body."""
    t = ast.parse(src)
    body_names = set()
    for n in ast.walk(t):
        if isinstance(n, ast.Name): body_names.add(n.id)
        if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name): body_names.add(n.value.id)
    lines = src.splitlines(keepends=True)
    out = []
    for ln in lines:
        m = re.match(r"^import (\w+)\s*$", ln)
        if m and m.group(1) in candidates and m.group(1) not in body_names:
            continue
        m = re.match(r"^from ([\w.]+) import (.+)$", ln)
        if m:
            names = [x.strip() for x in m.group(2).split(",")]
            kept = [x for x in names if x not in candidates or x in body_names]
            if not kept:
                continue
            if kept != names:
                ln = f"from {m.group(1)} import {', '.join(kept)}\n"
        out.append(ln)
    return "".join(out)


def compile_all() -> None:
    for p in sorted(PKG.rglob("*.py")) + [APP / "cli.py"]:
        ast.parse(read(p), filename=str(p))


def main() -> None:
    for p in REMOVE_PATHS:
        if not p.exists():
            sys.exit(f"expected path missing (already deleted? tree not at step 0?): {p}")

    # 1. file removals
    for p in REMOVE_PATHS:
        git("rm", "-r", "-q", str(p.relative_to(ROOT)).replace("\\", "/"))
    write(APP / "requirements.txt", REQUIREMENTS)
    print(f"  removed {len(REMOVE_PATHS)} paths; merged requirements.txt")

    # 2. dead functions and constants
    for p, names in DEAD_FUNCS.items():
        src, _ = cut_nodes(read(p), set(names), (ast.FunctionDef,))
        if p in DEAD_CONSTS:
            src, _ = cut_nodes(src, set(DEAD_CONSTS[p]), (ast.Assign,))
        write(p, src)
        print(f"  {p.relative_to(ROOT)}: cut {len(names)} functions"
              + (f", {len(DEAD_CONSTS[p])} constants" if p in DEAD_CONSTS else ""))

    # 2b. patents.py: replace docstring, drop now-unused imports
    pp = PKG / "sources" / "patents.py"
    src = read(pp)
    t = ast.parse(src)
    ds = t.body[0]
    assert isinstance(ds, ast.Expr) and isinstance(ds.value, ast.Constant), "patents.py has no module docstring"
    lines = src.splitlines(keepends=True)
    src = PATENTS_DOC + "\n" + "".join(lines[ds.end_lineno:])
    src = drop_unused_imports(src, ["io", "zipfile", "json", "requests", "datetime", "timezone", "date"])
    orphan = re.compile(r"# --- operator-supplied credential[^\n]*\n(BULK_DIR[^\n]*\n)(PATENTS_CSV[^\n]*\n)(?:#[^\n]*\n)*?(?=# -+\n# BigQuery route)")
    src, k = orphan.subn(lambda m: m.group(1) + m.group(2) + "\n", src, count=1)
    assert k == 1, "patents.py banner region not found"
    src = src.replace("\n\n\nfrom .. import config", "\n\nfrom .. import config", 1)
    write(pp, src)

    # 3. pairs.py -> baselines.py
    pairs_p = PKG / "pairs.py"
    src, cut = cut_nodes(read(pairs_p), set(MOVE_TO_BASELINES), (ast.FunctionDef,))
    src = drop_unused_imports(src, ["timedelta", "re", "defaultdict"])
    write(pairs_p, src)
    write(PKG / "baselines.py", BASELINES_HEADER + "\n\n".join(cut[n] for n in MOVE_TO_BASELINES))
    print(f"  pairs.py -> baselines.py: moved {len(cut)} functions")

    # 4. cli.py
    cli = APP / "cli.py"
    src = read(cli)
    for h in CLI_HELP_REMOVE:
        n = len(src)
        src = "".join(l for l in src.splitlines(keepends=True) if not l.startswith(h))
        assert len(src) < n, f"help line not found: {h}"
    for cmd in CLI_BRANCH_REMOVE:
        pat = re.compile(rf'    elif cmd == "{cmd}":\n(?:        .*\n|\n)*?(?=    elif cmd == )')
        src, k = pat.subn("", src, count=1)
        assert k == 1, f"cli branch not found: {cmd}"
    for old, new in CLI_IMPORT_REWRITES:
        assert old in src, f"cli import not found: {old}"
        src = src.replace(old, new, 1)
    write(cli, src)
    print("  cli.py: removed 2 dead branches, rerouted 4 baseline imports")

    # 5. structural checks
    compile_all()
    cmds = sorted(set(re.findall(r'cmd == "([\w\-]+)"', read(cli))))
    assert "patents-probe" not in cmds and "patents-ingest" not in cmds
    assert len(cmds) == 55, f"expected 55 commands, found {len(cmds)}"
    stale_global = ("crsp_import", "ner_status", "_pair_by_date", "build_from_local",
                    "_download_resumable", "ODP_API_KEY")
    stale_patents = ("PROBE_MARKER", "BULK_FILES", "S3_BASE", "ODP_SEARCH", "OUT_COLS")
    for p in list(PKG.rglob("*.py")) + [cli]:
        for nm in stale_global + (stale_patents if p.name == "patents.py" else ()):
            assert nm not in read(p), f"stale reference to {nm} in {p.relative_to(ROOT)}"
    print(f"  all modules parse; cli dispatches {len(cmds)} commands")

    # 6. regression
    R.check()
    print("Next: git add -A ; git commit -m \"Refactor step 1: delete dead code and duplicates\"")


if __name__ == "__main__":
    main()
