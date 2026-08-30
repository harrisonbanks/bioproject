# scripts/refactor/17_fixes.py
"""Step 1c: two small fixes before the relocation gate.

1. `coverage` crashed with KeyError 'tag' (paste, 2026-08-29): the Orange
   Book manifest written by orangebook._download has no `tag` field while
   cli.py's coverage loop reads m['tag'] unconditionally. Fix both ends:
   the writer adds "tag": "orangebook"; the reader uses m.get('tag', '-')
   so the manifest already cached on the operator machine also prints.
2. .vscode/settings.json hard-codes C:\\Users\\bocchirock\\...\\.venv;
   replaced with ${workspaceFolder}, which VS Code resolves per clone.

Ends with the step-0 regression check (neither change touches the
predict / pairs-full-exact path: coverage is a separate CLI branch and
the manifest is only read by coverage_report).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # refactor tooling only; not src/
import _regress as R

ROOT = R.ROOT
APP = ROOT / "app"
PKG = APP / "biointel"

EDITS = [
    (
        PKG / "sources" / "orangebook.py",
        """        f'{{"url": "{r.url}", "status": {r.status_code}, \'""",
        """        f'{{"tag": "orangebook", "url": "{r.url}", "status": {r.status_code}, \'""",
    ),
    (
        APP / "cli.py",
        """            print(f"  {m['fetched_at']}  {m['tag']:<22} {m['status']}  {m['url'][:90]}")""",
        """            print(f"  {m['fetched_at']}  {m.get('tag', '-'):<22} {m['status']}  {m['url'][:90]}")""",
    ),
    (
        ROOT / ".vscode" / "settings.json",
        '''"& 'C:\\\\Users\\\\bocchirock\\\\Documents\\\\dev\\\\bioindustry\\\\.venv\\\\Scripts\\\\Activate.ps1'"''',
        '''"& '${workspaceFolder}\\\\.venv\\\\Scripts\\\\Activate.ps1'"''',
    ),
]


def main() -> None:
    for p, old, new in EDITS:
        s = p.read_text(encoding="utf-8")
        assert s.count(old) == 1, (
            f"{p.relative_to(ROOT)}: expected exactly one occurrence of the target line"
        )
        p.write_text(s.replace(old, new), encoding="utf-8", newline="\n")
        print(f"  patched {p.relative_to(ROOT)}")
    import ast

    ast.parse((PKG / "sources" / "orangebook.py").read_text(encoding="utf-8"))
    ast.parse((APP / "cli.py").read_text(encoding="utf-8"))
    import json

    json.loads((ROOT / ".vscode" / "settings.json").read_text(encoding="utf-8"))
    print("  orangebook.py and cli.py parse; settings.json is valid JSON")
    R.check()
    print(
        'Next: git add -A ; git commit -m "Refactor step 1c: coverage manifest tag; portable VS Code venv path"'
    )


if __name__ == "__main__":
    main()
