# scripts/refactor/40_ruff.py
"""Step 4: adopt ruff as linter and formatter (decision 2026-08-29).

1. pipeline.py: drop the orphan "CRSP integration" banner left by step 1
   and hoist the mid-file `import re` to the import block (the only E402
   in src/).
2. `ruff check --fix` (safe fixes only: unused imports, import order,
   trailing newlines) then `ruff format` over src/, scripts/, tests/.
3. pyproject.toml [tool.ruff.lint]: ignore E501 (long lines, mostly
   strings and tables) and E741 (single-letter names in numeric code);
   everything else stays visible. Remaining findings after this step are
   reported, not hidden.
4. .vscode/settings.json: Ruff as the Python formatter with format-on-save,
   so editor and CLI share the pyproject configuration.
Ends with pytest tests/unit and the step-0 regression check.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # refactor tooling only; not src/
import _regress as R

ROOT = R.ROOT
SRC = ROOT / "src" / "biointel"
TARGETS = ["src", "scripts", "tests"]


def run(*args: str) -> str:
    r = subprocess.run([sys.executable, "-m", *args], cwd=str(ROOT), capture_output=True, text=True)
    return (r.stdout + r.stderr).strip()


def main() -> None:
    # 1. pipeline.py banner + import hoist
    p = SRC / "pipeline.py"
    s = p.read_text(encoding="utf-8")
    old = "# ---------------------------------------------------- CRSP integration\n# ---------------------------------------------------- 10-K text (Phase D)\nimport re\n"
    assert s.count(old) == 1, "pipeline.py banner/import block not in expected form"
    s = s.replace(
        old, "# ---------------------------------------------------- 10-K text (Phase D)\n"
    )
    assert s.count("import csv\n") == 1
    s = s.replace("import csv\n", "import csv\nimport re\n", 1)
    p.write_text(s, encoding="utf-8", newline="\n")
    print("  pipeline.py: orphan CRSP banner removed; `import re` hoisted")

    # 2. pyproject ruff ignores
    pp = ROOT / "pyproject.toml"
    t = pp.read_text(encoding="utf-8")
    old = '[tool.ruff.lint]\nselect = ["E", "F", "W", "I"]\n'
    assert t.count(old) == 1, "pyproject [tool.ruff.lint] block not in expected form"
    t = t.replace(
        old, '[tool.ruff.lint]\nselect = ["E", "F", "W", "I"]\nignore = ["E501", "E741"]\n'
    )
    pp.write_text(t, encoding="utf-8", newline="\n")

    # 3. ruff fix + format
    out = run("ruff", "check", *TARGETS, "--fix")
    print("  ruff check --fix: " + out.splitlines()[-1])
    out = run("ruff", "format", *TARGETS)
    print("  ruff format: " + out.splitlines()[-1])
    out = run("ruff", "check", *TARGETS, "--statistics")
    print("  remaining findings (visible, not hidden):")
    for line in out.splitlines():
        if re.match(r"\s*\d+\s", line):
            print("    " + line.strip())

    # 4. VS Code: ruff as formatter
    vs = ROOT / ".vscode" / "settings.json"
    cfg = json.loads(vs.read_text(encoding="utf-8"))
    cfg["[python]"] = {"editor.defaultFormatter": "charliermarsh.ruff", "editor.formatOnSave": True}
    vs.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8", newline="\n")
    print("  .vscode/settings.json: Ruff formatter, format on save")

    # 5. tests + regression
    out = run("pytest", "-q", "tests/unit")
    assert "passed" in out and "failed" not in out, f"pytest:\n{out}"
    print("  pytest tests/unit: " + [l for l in out.splitlines() if "passed" in l][-1].strip())
    R.check()
    print(
        'Next: git add -A ; git commit -m "Refactor step 4: ruff lint fixes and formatting; Ruff as editor formatter"'
    )


if __name__ == "__main__":
    main()
