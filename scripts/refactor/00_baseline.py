"""Step 0: record the pre-refactor output hashes.

Runs predict and pairs-full-exact on the current unmodified tree and
writes docs/regression_baseline.txt. Every later refactor script reruns
the same two commands and refuses to finish if either hash changes.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # refactor tooling only; not src/
import _regress as R

if __name__ == "__main__":
    h = R.regenerate()
    R.write_baseline(h)
    for k, v in sorted(h.items()):
        print(f"  {k}  {v[:16]}...")
    print(f"baseline written -> {R.BASELINE}")
    print(
        'Next: git add docs/regression_baseline.txt scripts/refactor ; git commit -m "Refactor step 0: regression baseline"'
    )
