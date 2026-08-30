"""Shared regression check for the refactor scripts.

Runs `predict` and `pairs-full-exact` through the live CLI, hashes their
gold outputs, and compares to docs/regression_baseline.txt. Works before
and after the src-layout move: it locates the CLI by probing both
layouts. Run from anywhere; paths are resolved from this file.
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "docs" / "regression_baseline.txt"
ARTIFACTS = ["ma_predictions.csv", "pair_full_exact_report.txt"]


def layout() -> tuple[list[str], Path, Path]:
    """Return (cli_argv_prefix, cwd, gold_dir) for whichever layout exists."""
    if (ROOT / "app" / "cli.py").exists():
        return ([sys.executable, "cli.py"], ROOT / "app", ROOT / "app" / "data" / "gold")
    if (ROOT / "src" / "biointel").exists():
        return ([sys.executable, "-m", "biointel"], ROOT, ROOT / "data" / "gold")
    sys.exit("No recognizable layout: neither app/cli.py nor src/biointel exists.")


def run_cli(*args: str) -> None:
    prefix, cwd, _ = layout()
    r = subprocess.run(prefix + list(args), cwd=cwd)
    if r.returncode != 0:
        sys.exit(f"cli {' '.join(args)} exited {r.returncode}")


def hashes() -> dict[str, str]:
    _, _, gold = layout()
    out = {}
    for name in ARTIFACTS:
        p = gold / name
        if not p.exists():
            sys.exit(f"missing artifact {p}")
        out[name] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def regenerate() -> dict[str, str]:
    run_cli("predict")
    run_cli("pairs-full-exact")
    return hashes()


def write_baseline(h: dict[str, str]) -> None:
    BASELINE.parent.mkdir(parents=True, exist_ok=True)
    BASELINE.write_text("".join(f"{k}  {v}\n" for k, v in sorted(h.items())), encoding="utf-8")


def read_baseline() -> dict[str, str]:
    if not BASELINE.exists():
        sys.exit(f"no baseline at {BASELINE}; run 00_baseline.py first")
    return dict(
        line.split()[::-1][::-1]
        for line in BASELINE.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )


def check() -> None:
    base = read_baseline()
    now = regenerate()
    bad = [k for k in base if base[k] != now.get(k)]
    for k in sorted(base):
        print(f"  {'MATCH' if k not in bad else 'DIFF '}  {k}")
    if bad:
        sys.exit("REGRESSION: outputs changed; do not commit. git checkout -- . to revert.")
    print("REGRESSION CHECK PASSED")
