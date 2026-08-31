# src/biointel/models/base.py
"""The contract every registered implementation and evaluation satisfies."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

# table -> tuple of allowed columns, or None for every column of the table.
Inputs = dict[str, tuple[str, ...] | None]

RUN_TYPES = ("predict", "fit", "evaluation")


@dataclass(frozen=True)
class Entry:
    """One runnable thing in the registry.

    model      the question, e.g. "target-screen"
    name       the implementation or evaluation name, e.g. "scorecard", "robust"
    run_type   "predict" (produces the model's output), "fit" (trains and
               persists), "evaluation" (measures an implementation)
    inputs     tables and columns the code may read while it runs (enforced)
    outputs    tables the code writes; readable back during the run
    func       callable(as_of, params) -> result dict with "status" and,
               on success, "run_id"
    of_impl    for evaluations: the implementation being evaluated
    note       one line for `models`
    """

    model: str
    name: str
    run_type: str
    inputs: Inputs
    func: Callable[[str | None, dict], dict]
    outputs: tuple[str, ...] = ()
    of_impl: str = ""
    note: str = ""
    params: dict = field(default_factory=dict)

    @property
    def label(self) -> str:
        return f"{self.model}/{self.name}"

    def allowed(self) -> Inputs:
        """Inputs plus outputs (readable without column restriction)."""
        d: Inputs = dict(self.inputs)
        for t in self.outputs:
            d.setdefault(t, None)
        return d
