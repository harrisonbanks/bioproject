"""Step 1b: remove hard-coded credentials from config.py.

Architecture Instructions 6.1/6.3/11.9: configuration from environment,
secrets never committed, `.env.example` lists names with placeholders.

What changes:
  config.py       USER_AGENT / ALPHA_VANTAGE_KEY literals removed; a
                  six-line loader reads <repo-root>/.env into os.environ
                  (no new dependency); `require(name)` fails fast at the
                  point of use with the missing variable's name (6.4).
  store.py, sources/orangebook.py, sources/alphavantage.py, check_ocf.py
                  read the values through config.require(...).
  .env.example    committed placeholders; .env added to .gitignore.

Deferred, stated per 1.10: Section 6.2 (settings object built in a
composition root and passed down) is step-4 work; until then modules
call config.require() at the I/O boundary.

Regression order: this script ends with the step-0 regression check
BEFORE any .env exists. That is valid because neither `predict` nor
`pairs-full-exact` reads either setting: BIOINTEL_ALPHA_VANTAGE_KEY is
read only in sources/alphavantage.py (add-company path), and the
User-Agent is read only inside HTTP calls in store.fetch_json and
orangebook._download; the predict path reads the Orange Book from the
bronze cache and raises if it is absent rather than downloading
(orangebook._protection_end_by_appno), and score.py / pairs.py do not
import store. Verified by grep of the post-step-1 tree on 2026-08-29.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # refactor tooling only; not src/
import _regress as R

ROOT = R.ROOT
APP = ROOT / "app"
PKG = APP / "biointel"

OLD_CRED_BLOCK = re.compile(
    r"# --- credentials -+\n"
    r"# SEC requires a descriptive User-Agent[^\n]*\n"
    r'USER_AGENT = "[^"]*"\n\n'
    r"# Alpha Vantage free tier[^\n]*\n"
    r'ALPHA_VANTAGE_KEY = "[^"]*"\n'
)
NEW_CRED_BLOCK = '''# --- settings from the environment ----------------------------------------
# Values come from os.environ; <repo-root>/.env is loaded if present
# (names and placeholders in .env.example). Nothing secret lives in code.
_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


def _load_dotenv() -> None:
    if not _ENV_FILE.exists():
        return
    for line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def require(name: str) -> str:
    """Return the environment variable or fail fast naming it (6.4)."""
    v = os.environ.get(name, "")
    if not v:
        raise RuntimeError(
            f"{name} is not set. Copy .env.example to .env at the repository "
            f"root and fill in {name}.")
    return v


_load_dotenv()
'''

ENV_EXAMPLE = """# Copy to .env at the repository root and fill in. .env is git-ignored.
# SEC requires a descriptive User-Agent with a contact email or returns 403.
BIOINTEL_USER_AGENT=Your Name you@example.com
# Alpha Vantage free tier key (25 calls/day); used only by `add`.
BIOINTEL_ALPHA_VANTAGE_KEY=YOUR_KEY_HERE
"""

USE_SITES = [
    (
        PKG / "store.py",
        'hdrs = {"User-Agent": config.USER_AGENT}',
        'hdrs = {"User-Agent": config.require("BIOINTEL_USER_AGENT")}',
    ),
    (
        PKG / "sources" / "orangebook.py",
        'headers={"User-Agent": config.USER_AGENT}',
        'headers={"User-Agent": config.require("BIOINTEL_USER_AGENT")}',
    ),
    (
        PKG / "sources" / "alphavantage.py",
        '"apikey": config.ALPHA_VANTAGE_KEY,',
        '"apikey": config.require("BIOINTEL_ALPHA_VANTAGE_KEY"),',
    ),
    (
        APP / "check_ocf.py",
        'headers={"User-Agent": config.USER_AGENT}',
        'headers={"User-Agent": config.require("BIOINTEL_USER_AGENT")}',
    ),
]


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")


def write(p: Path, s: str) -> None:
    p.write_text(s, encoding="utf-8", newline="\n")


def main() -> None:
    cfg = PKG / "config.py"
    src = read(cfg)
    assert OLD_CRED_BLOCK.search(src), "config.py credentials block not in expected form"
    src = OLD_CRED_BLOCK.sub(NEW_CRED_BLOCK, src, count=1)
    src = src.replace(
        '"""Configuration. Edit USER_AGENT and ALPHA_VANTAGE_KEY before first run."""\nfrom pathlib import Path\n',
        '"""Configuration: paths, endpoints, behaviour; credentials from the environment."""\nimport os\nfrom pathlib import Path\n',
        1,
    )
    assert "import os" in src, "config.py docstring/import header not in expected form"
    write(cfg, src)
    print("  config.py: credentials removed; .env loader + require() added")

    for p, old, new in USE_SITES:
        s = read(p)
        assert s.count(old) == 1, f"{p.name}: expected exactly one occurrence of: {old}"
        write(p, s.replace(old, new))
    print(f"  {len(USE_SITES)} use sites now call config.require(...)")

    write(ROOT / ".env.example", ENV_EXAMPLE)
    gi = ROOT / ".gitignore"
    g = read(gi)
    if ".env\n" not in g + "\n":
        write(gi, g.rstrip("\n") + "\n.env\n")
    print("  .env.example written; .env git-ignored")

    # no credential-shaped literal or the old contact address remains anywhere tracked
    bad = []
    for p in (
        list(ROOT.rglob("*.py"))
        + list(ROOT.rglob("*.md"))
        + [ROOT / ".env.example", ROOT / ".vscode" / "settings.json"]
    ):
        rel = p.relative_to(ROOT).parts
        if (
            any(x.startswith(".") for x in rel[:-1])
            or "data" in rel
            or "refactor" in rel
            or not p.exists()
        ):
            continue  # skip .git/.venv/.vscode dirs, data, and scripts/refactor (the scanner itself)
        t = read(p)
        if re.search(r'ALPHA_VANTAGE_KEY\s*=\s*"[A-Z0-9]{8,}"', t) or "@gmail.com" in t:
            bad.append(str(p.relative_to(ROOT)))
    assert not bad, f"credential-shaped content still present in: {bad}"
    for nm in ("config.USER_AGENT", "config.ALPHA_VANTAGE_KEY"):
        hits = [
            str(p.relative_to(ROOT))
            for p in ROOT.rglob("*.py")
            if not any(x.startswith(".") for x in p.relative_to(ROOT).parts[:-1])
            and "refactor" not in p.parts
            and nm in read(p)
        ]
        assert not hits, f"stale reference to {nm} in {hits}"
    print("  tree scan: no credential literals, no stale references")

    # fail-fast behaves: require() on an unset name raises naming it
    import importlib.util

    spec = importlib.util.spec_from_file_location("biointel.config", cfg)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    try:
        m.require("BIOINTEL_TEST_UNSET_NAME")
    except RuntimeError as e:
        assert "BIOINTEL_TEST_UNSET_NAME" in str(e)
    else:
        sys.exit("require() did not fail fast")
    print("  require() fails fast naming the variable")

    R.check()
    print('Next: git add -A ; git commit -m "Refactor step 1b: credentials from environment"')
    print("Then create <repo-root>\\.env from .env.example with your own values (never committed).")


if __name__ == "__main__":
    main()
