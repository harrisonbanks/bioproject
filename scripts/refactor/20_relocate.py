# scripts/refactor/20_relocate.py
"""Step 2: relocate to the src layout (Architecture Instructions §2).

Moves (git mv, history preserved):
  app/biointel/            -> src/biointel/
  app/cli.py               -> src/biointel/interfaces/cli.py
  app/<diagnostic>.py x10  -> scripts/
  app/PROJECT_STATUS.md,
  app/README.md            -> docs/
  app/data/                -> data/            (untracked; filesystem move)
Creates: pyproject.toml, .python-version, src/biointel/__main__.py,
  src/biointel/interfaces/__init__.py, tests/unit/test_match_canon.py,
  tests/unit/test_config_require.py, requirements.lock
Edits: every relative import -> absolute `biointel.` import (§5.1);
  config.py data root -> <repo-root>/data; sys.path.insert lines removed
  from scripts (§11.1); "python cli.py" in help/messages -> "python -m
  biointel"; .gitignore app/data/ line dropped.
Deletes: app/requirements.txt (superseded by pyproject.toml); app/ once empty.

Override recorded per Architecture Instructions §1: uv (§3.2-3.4, §10) is
NOT used; environment is venv + pip. Editable install is
`python -m pip install -e .`; pinned versions are `pip freeze` ->
requirements.lock, committed.

Ends with the step-0 regression check through the new entry point
(`python -m biointel predict` / `pairs-full-exact`).
Reverse before commit: git reset --hard HEAD ; git clean -fd ; move data/ back to app/data/.
"""
from __future__ import annotations
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # refactor tooling only; not src/
import _regress as R

ROOT = R.ROOT
APP = ROOT / "app"
SRC = ROOT / "src" / "biointel"

DIAGNOSTICS = ["check_exhibits.py", "check_names.py", "check_ocf.py", "check_one.py",
               "cleanup_feed_junk.py", "debug_fit.py", "summary.py", "text_diag.py",
               "migrate_from_excel.py", "suggest_aliases.py"]

PYPROJECT = '''[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "biointel"
version = "0.81"
description = "Bioindustry Intelligence Platform: biopharma M&A target screen, buyer-target pairing, FDA event study"
requires-python = ">=3.13"
dependencies = [
    "numpy>=2.0",
    "scikit-learn>=1.5",
    "scipy>=1.13",
    "requests>=2.31",
    "openpyxl>=3.1",
]

[project.optional-dependencies]
ner = ["spacy>=3.7"]
dev = ["ruff>=0.5", "mypy>=1.10", "pytest>=8"]

[tool.setuptools.packages.find]
where = ["src"]

[tool.ruff]
line-length = 100
target-version = "py313"

[tool.ruff.lint]
select = ["E", "F", "W", "I"]

[tool.mypy]
python_version = "3.13"
strict = false
ignore_missing_imports = true

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = ["integration: requires network or real data; excluded from the default run"]
addopts = "-m 'not integration'"
'''

MAIN_PY = '''"""Entry point: python -m biointel <command> [args]."""
import sys

from biointel.interfaces.cli import main

if __name__ == "__main__":
    sys.exit(main(sys.argv))
'''

TEST_CANON = '''"""Unit tests for biointel.match.canon (pure function, no I/O)."""
from biointel.match import canon


def test_canon_uppercases_and_strips_legal_suffix():
    assert canon("Pfizer Inc.") == "PFIZER"


def test_canon_removes_apostrophes_and_descriptors():
    assert canon("Dr. Reddy's Labs") == "DR REDDYS"


def test_canon_expands_ampersand():
    assert canon("AT&T") == "AT AND T"


def test_canon_none_is_empty():
    assert canon(None) == ""


def test_canon_never_returns_empty_for_nonempty_input():
    assert canon("Inc") == "INC"
'''

TEST_REQUIRE = '''"""Unit tests for biointel.config.require (fail-fast settings)."""
import pytest

from biointel import config


def test_require_raises_naming_the_missing_variable(monkeypatch):
    monkeypatch.delenv("BIOINTEL_TEST_UNSET", raising=False)
    with pytest.raises(RuntimeError, match="BIOINTEL_TEST_UNSET"):
        config.require("BIOINTEL_TEST_UNSET")


def test_require_returns_value_when_set(monkeypatch):
    monkeypatch.setenv("BIOINTEL_TEST_SET", "value")
    assert config.require("BIOINTEL_TEST_SET") == "value"
'''


def git(*args: str) -> None:
    r = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"git {' '.join(args)} failed:\n{r.stderr}")


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")


def write(p: Path, s: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(s, encoding="utf-8", newline="\n")


def rel_to_abs_imports(p: Path) -> int:
    """Rewrite `from .x import y` / `from ..x import y` to absolute `biointel...` imports."""
    parts = p.relative_to(SRC.parent).with_suffix("").parts  # ('biointel', 'sources', 'fda')
    package = list(parts[:-1])                                # module's package path
    pat = re.compile(r"^(\s*)from (\.+)([\w.]*) import ", re.M)
    n = 0

    def sub(m: re.Match) -> str:
        nonlocal n
        n += 1
        indent, dots, tail = m.group(1), m.group(2), m.group(3)
        base = package[: len(package) - (len(dots) - 1)]
        target = ".".join(base + ([tail] if tail else []))
        return f"{indent}from {target} import "

    s = read(p)
    s2 = pat.sub(sub, s)
    if s2 != s:
        write(p, s2)
    return n


def main() -> None:
    assert APP.exists() and (APP / "biointel").exists(), "tree is not at the pre-step-2 layout"
    assert not SRC.exists(), "src/biointel already exists"

    # 1. moves (git mv needs existing parent directories)
    for d in ("src", "scripts", "docs"):
        (ROOT / d).mkdir(exist_ok=True)
    git("mv", "app/biointel", "src/biointel")
    (SRC / "interfaces").mkdir()
    git("mv", "app/cli.py", "src/biointel/interfaces/cli.py")
    for f in DIAGNOSTICS:
        git("mv", f"app/{f}", f"scripts/{f}")
    for f in ("PROJECT_STATUS.md", "README.md"):
        git("mv", f"app/{f}", f"docs/{f}")
    if (APP / "data").exists():
        assert not (ROOT / "data").exists(), "data/ already exists at the root"
        shutil.move(str(APP / "data"), str(ROOT / "data"))
    git("rm", "-q", "app/requirements.txt")
    print("  moved: package -> src/, cli -> interfaces/, 10 diagnostics -> scripts/, 2 docs -> docs/, data -> data/")

    # 2. new files
    write(SRC / "interfaces" / "__init__.py", "")
    write(SRC / "__main__.py", MAIN_PY)
    write(ROOT / "pyproject.toml", PYPROJECT)
    write(ROOT / ".python-version", "3.13\n")
    write(ROOT / "tests" / "unit" / "test_match_canon.py", TEST_CANON)
    write(ROOT / "tests" / "unit" / "test_config_require.py", TEST_REQUIRE)
    print("  created: pyproject.toml, .python-version, __main__.py, interfaces/__init__.py, 2 unit tests")

    # 3. edits
    total = 0
    for p in SRC.rglob("*.py"):
        total += rel_to_abs_imports(p)
    print(f"  rewrote {total} relative imports to absolute")

    cfg = SRC / "config.py"
    s = read(cfg)
    old = 'ROOT   = Path(__file__).resolve().parent.parent\n'
    assert s.count(old) == 1, "config.py ROOT line not in expected form"
    s = s.replace(old, 'ROOT   = Path(__file__).resolve().parents[2]   # <repo-root>: src/biointel/config.py\n')
    write(cfg, s)

    n_help = 0
    for p in list(SRC.rglob("*.py")):
        s = read(p)
        if "python cli.py" in s:
            n_help += s.count("python cli.py")
            write(p, s.replace("python cli.py", "python -m biointel"))
    print(f"  config.py data root -> <repo-root>/data; {n_help} 'python cli.py' mentions -> 'python -m biointel'")

    for f in ("text_diag.py", "debug_fit.py"):
        p = ROOT / "scripts" / f
        s = read(p)
        s2 = re.sub(r'^sys\.path\.insert\(0, "\."\)\n', "", s, flags=re.M)
        assert s2 != s, f"{f}: sys.path.insert line not found"
        if not re.search(r"\bsys\.", s2):
            s2 = re.sub(r"^import sys\n", "", s2, count=1, flags=re.M)
            s2 = re.sub(r"^import sys, ", "import ", s2, count=1, flags=re.M)
        write(p, s2)
    gi = ROOT / ".gitignore"
    write(gi, read(gi).replace("app/data/\n", "").rstrip("\n") + "\n*.egg-info/\n")
    print("  sys.path.insert removed from 2 scripts; .gitignore: app/data/ dropped, *.egg-info/ added")

    # 4. app/ must now be empty
    leftovers = [x for x in APP.rglob("*") if x.is_file() and "__pycache__" not in x.parts]
    assert not leftovers, f"app/ still contains: {[str(x.relative_to(ROOT)) for x in leftovers]}"
    if APP.exists():
        shutil.rmtree(APP)
    print("  app/ removed (empty)")

    # 5. install editable + lock
    r = subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-e", str(ROOT)], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"pip install -e failed:\n{r.stdout}\n{r.stderr}")
    r = subprocess.run([sys.executable, "-m", "pip", "freeze", "--exclude-editable"], capture_output=True, text=True)
    write(ROOT / "requirements.lock", r.stdout)
    print(f"  editable install OK; requirements.lock written ({len(r.stdout.splitlines())} pins)")

    # 6. structural checks from a neutral directory (no sys.path help)
    r = subprocess.run([sys.executable, "-c", "import biointel, biointel.interfaces.cli; print(biointel.__file__)"],
                       cwd=str(ROOT.parent), capture_output=True, text=True)
    assert r.returncode == 0 and "src" in r.stdout, f"import biointel failed from outside the repo:\n{r.stderr}"
    r = subprocess.run([sys.executable, "-m", "biointel"], cwd=str(ROOT.parent), capture_output=True, text=True)
    help_lines = [l for l in r.stdout.splitlines() if "python -m biointel " in l]
    assert len(help_lines) >= 45, f"help text unexpectedly short: {len(help_lines)} lines"
    cmds = sorted(set(re.findall(r'cmd == "([\w\-]+)"', read(SRC / "interfaces" / "cli.py"))))
    assert len(cmds) == 55, f"expected 55 commands, found {len(cmds)}"
    print(f"  import from outside the repo OK; help prints {len(help_lines)} command lines; {len(cmds)} dispatched")

    # 7. unit tests
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "tests/unit"], cwd=str(ROOT), capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"pytest failed:\n{r.stdout}\n{r.stderr}")
    print("  pytest tests/unit: " + [l for l in r.stdout.splitlines() if "passed" in l][-1].strip())

    # 8. regression through the new entry point
    R.check()
    print("Next: git add -A ; git commit -m \"Refactor step 2: src layout, pyproject, scripts/docs/data directories\"")


if __name__ == "__main__":
    main()
