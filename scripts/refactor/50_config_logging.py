# scripts/refactor/50_config_logging.py
"""Step 5: endpoints into config.py; package print() -> logging.

1. Every HTTP endpoint used by the package is a named constant in
   config.py (twelve-factor config: one place per address). Module-level
   aliases (deals.SUBS_URL, trials.BASE, chembl.API, ...) now point at the
   config constants; inline f-string URLs use .format() on them. Docstring
   mentions are left as documentation.
2. In src/biointel/ (everything except interfaces/cli.py) `print(...)`
   becomes `log.info(...)` with `log = logging.getLogger(__name__)`;
   `flush=True` arguments are dropped (the stream handler flushes per
   record). cli.py configures logging once in main(): INFO, message-only
   format, to stdout, so the console output is unchanged. Standard-library
   guidance: library code logs, the entry point decides what to show.
3. pyproject [tool.ruff.format] line-ending = "lf" so ruff stops writing
   CRLF on Windows (the eight warnings at step 4).
4. ruff check --fix + ruff format, pytest tests/unit, regression check.
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
SRC = ROOT / "src" / "biointel"
CLI = SRC / "interfaces" / "cli.py"

CONFIG_URLS_OLD = 'CTGOV_BASE = "https://clinicaltrials.gov"\n'
CONFIG_URLS_NEW = '''CTGOV_BASE = "https://clinicaltrials.gov"
SEC_BROWSE = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany"
SEC_SUBS_PAGE = "https://data.sec.gov/submissions/{name}"
SEC_ARCHIVE = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}"
SEC_ARCHIVE_DOC = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{doc}"
SEC_XBRL_FACTS = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik10}.json"
FDA_ORANGE_BOOK = "https://www.fda.gov/media/76860/download?attachment"
CHEMBL_API = "https://www.ebi.ac.uk/chembl/api/data"
WIKI_API = "https://en.wikipedia.org/w/api.php"
'''

# (file, old, new, expected occurrences)
URL_EDITS = [
    (SRC / "universe.py",
     '    "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany"\n    "&SIC=',
     '    config.SEC_BROWSE\n    + "&SIC=', 1),
    (SRC / "universe.py",
     'f"https://data.sec.gov/submissions/CIK{cik10}.json", tag="sec_submissions"',
     'config.SEC_SUBS.format(cik10=cik10), tag="sec_submissions"', 1),
    (SRC / "sources" / "chembl.py",
     'API = "https://www.ebi.ac.uk/chembl/api/data"', 'API = config.CHEMBL_API', 1),
    (SRC / "sources" / "deals.py",
     'SUBS_URL = "https://data.sec.gov/submissions/CIK{cik10}.json"', 'SUBS_URL = config.SEC_SUBS', 1),
    (SRC / "sources" / "deals.py",
     'ARCHIVE = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}"', 'ARCHIVE = config.SEC_ARCHIVE', 1),
    (SRC / "sources" / "deals.py",
     'f"https://data.sec.gov/submissions/{name}", tag="sec_submissions_page"',
     'config.SEC_SUBS_PAGE.format(name=name), tag="sec_submissions_page"', 1),
    (SRC / "sources" / "financials.py",
     'FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik10}.json"',
     'FACTS_URL = config.SEC_XBRL_FACTS', 1),
    (SRC / "sources" / "orangebook.py",
     'EOB_URL = "https://www.fda.gov/media/76860/download?attachment"', 'EOB_URL = config.FDA_ORANGE_BOOK', 1),
    (SRC / "sources" / "trials.py",
     'BASE = "https://clinicaltrials.gov"', 'BASE = config.CTGOV_BASE', 1),
    (SRC / "pipeline.py",
     '''f"https://www.sec.gov/Archives/edgar/data/{int(cik10)}/{acc.replace('-', '')}/{doc}"''',
     '''config.SEC_ARCHIVE_DOC.format(cik=int(cik10), acc=acc.replace("-", ""), doc=doc)''', 1),
    (SRC / "labels.py",
     'url = f"https://data.sec.gov/submissions/CIK{cik10}.json"',
     'url = config.SEC_SUBS.format(cik10=cik10)', 1),
    (SRC / "labels.py",
     '''f"https://www.sec.gov/Archives/edgar/data/{int(cik10)}/{acc.replace('-', '')}/{doc}"''',
     '''config.SEC_ARCHIVE_DOC.format(cik=int(cik10), acc=acc.replace("-", ""), doc=doc)''', 2),
    (SRC / "labels.py",
     '''url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace('-', '')}/{doc}"''',
     '''url = config.SEC_ARCHIVE_DOC.format(cik=int(cik), acc=acc.replace("-", ""), doc=doc)''', 1),
    (SRC / "labels.py",
     'f"https://data.sec.gov/submissions/{name}", tag="sec_submissions_extra"',
     'config.SEC_SUBS_PAGE.format(name=name), tag="sec_submissions_extra"', 1),
    (SRC / "labels.py",
     'fetch_json("https://www.sec.gov/files/company_tickers.json", tag="sec_ticker_map")',
     'fetch_json(config.SEC_TICKERS, tag="sec_ticker_map")', 1),
    (SRC / "labels.py",
     '"https://en.wikipedia.org/w/api.php?action=query&list=search"',
     'config.WIKI_API + "?action=query&list=search"', 1),
    (SRC / "labels.py",
     '"https://en.wikipedia.org/w/api.php?action=query&prop=extracts"',
     'config.WIKI_API + "?action=query&prop=extracts"', 1),
]

LOG_MODULES = ["universe.py", "fit.py", "improve.py", "sources/chembl.py", "pairs.py",
               "baselines.py", "pipeline.py", "labels.py"]


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def write(p: Path, s: str) -> None:
    p.write_text(s, encoding="utf-8", newline="\n")


def run(*args: str) -> str:
    r = subprocess.run([sys.executable, "-m", *args], cwd=str(ROOT), capture_output=True, text=True)
    return (r.stdout + r.stderr).strip()


def add_logger(p: Path) -> None:
    """Insert `import logging` and `log = logging.getLogger(__name__)` after the import block."""
    s = read(p)
    tree = ast.parse(s)
    last_import_end = 0
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            last_import_end = node.end_lineno
        elif isinstance(node, ast.Expr) and isinstance(getattr(node, "value", None), ast.Constant):
            continue  # module docstring
        elif last_import_end:
            break
    assert last_import_end, f"{p.name}: no import block found"
    lines = s.splitlines(keepends=True)
    lines.insert(last_import_end, "\nlog = logging.getLogger(__name__)\n")
    s = "".join(lines)
    # `import logging` goes next to the other stdlib imports; ruff --fix sorts it.
    first_import = next(n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom)))
    lines = s.splitlines(keepends=True)
    lines.insert(first_import.lineno - 1, "import logging\n")
    write(p, "".join(lines))


def print_to_log(p: Path) -> int:
    s = read(p)
    n = len(re.findall(r"\bprint\(", s))
    assert n, f"{p.name}: no print() found"
    s = re.sub(r"\bprint\(", "log.info(", s)
    s = re.sub(r",\s*flush=True,?", "", s)
    assert "flush=True" not in s, f"{p.name}: flush=True left behind"
    write(p, s)
    return n


def main() -> None:
    # 1. config constants
    cfg = SRC / "config.py"
    s = read(cfg)
    assert s.count(CONFIG_URLS_OLD) == 1, "config.py CTGOV_BASE line not in expected form"
    write(cfg, s.replace(CONFIG_URLS_OLD, CONFIG_URLS_NEW))
    for name in ("sources/deals.py", "sources/financials.py", "sources/trials.py"):
        p = SRC / name
        s = read(p)
        assert "from biointel import config" not in s
        anchor = "from biointel.store import fetch_json\n"
        assert s.count(anchor) == 1, f"{name}: import anchor not found"
        write(p, s.replace(anchor, "from biointel import config\n" + anchor, 1))
    for p, old, new, k in URL_EDITS:
        s = read(p)
        assert s.count(old) == k, f"{p.relative_to(ROOT)}: expected {k} occurrence(s) of: {old[:60]}"
        write(p, s.replace(old, new))
    for p in SRC.rglob("*.py"):
        if p.name == "config.py":
            continue
        code = "\n".join(l for l in read(p).splitlines() if not l.lstrip().startswith("#"))
        code_no_doc = re.sub(r'"""[\s\S]*?"""', "", code)
        assert not re.search(r"https?://", code_no_doc), f"URL literal still in code: {p.relative_to(ROOT)}"
    print(f"  {len(URL_EDITS)} endpoint sites now reference config.py constants; 9 constants added")

    # 2. print -> logging
    total = 0
    for name in LOG_MODULES:
        p = SRC / name
        total += print_to_log(p)
        add_logger(p)
    s = read(CLI)
    assert s.count("def main(argv):\n") == 1
    s = s.replace("def main(argv):\n",
                  'def main(argv):\n    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)\n', 1)
    assert s.count("import csv\n") == 1
    s = s.replace("import csv\n", "import csv\nimport logging\n", 1)
    write(CLI, s)
    for p in SRC.rglob("*.py"):
        if p != CLI:
            assert not re.search(r"\bprint\(", read(p)), f"print() still in {p.relative_to(ROOT)}"
    print(f"  {total} print() calls in 8 modules -> log.info(); cli.main() configures logging")

    # 3. ruff LF
    pp = ROOT / "pyproject.toml"
    t = read(pp)
    assert "[tool.ruff.format]" not in t
    t = t.replace('[tool.ruff.lint]\n', '[tool.ruff.format]\nline-ending = "lf"\n\n[tool.ruff.lint]\n', 1)
    write(pp, t)

    # 4. lint/format, import smoke, tests, regression
    print("  ruff check --fix: " + run("ruff", "check", "src", "scripts", "tests", "--fix").splitlines()[-1])
    print("  ruff format: " + run("ruff", "format", "src", "scripts", "tests").splitlines()[-1])
    r = subprocess.run([sys.executable, "-c",
                        "import biointel.labels as l, biointel.pipeline, biointel.universe, biointel.improve, "
                        "biointel.fit, biointel.pairs, biointel.baselines, biointel.sources.chembl, "
                        "biointel.interfaces.cli; import logging; assert isinstance(l.log, logging.Logger); print('ok')"],
                       cwd=str(ROOT.parent), capture_output=True, text=True)
    assert r.returncode == 0 and "ok" in r.stdout, f"import smoke failed:\n{r.stderr}"
    print("  all edited modules import; loggers present")
    out = run("pytest", "-q", "tests/unit")
    assert "passed" in out and "failed" not in out, f"pytest:\n{out}"
    print("  pytest tests/unit: " + [l for l in out.splitlines() if "passed" in l][-1].strip())
    R.check()
    print("Next: git add -A ; git commit -m \"Refactor step 5: endpoints in config.py; package logging; ruff LF\"")


if __name__ == "__main__":
    main()
