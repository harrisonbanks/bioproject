# src/biointel/models/harness.py
"""Run a registry entry: enforcement on, run type set, call, enforcement off."""

from __future__ import annotations

from biointel import results, store
from biointel.models import registry
from biointel.models.base import Entry


def run_entry(entry: Entry, as_of: str | None = None, params: dict | None = None) -> dict:
    """Execute one registry entry under P2 input enforcement. Any read outside
    the entry's declared inputs (plus its own outputs) raises
    store.InputViolation and nothing is recorded as ok."""
    params = dict(entry.params, **(params or {}))
    with results.run_type(entry.run_type), store.enforce(entry.label, entry.allowed()):
        result = entry.func(as_of, params)
    if isinstance(result, dict):
        result.setdefault("entry", entry.label)
    return result


def run_command(command: str, as_of: str | None = None, params: dict | None = None) -> dict:
    """Existing commands (`predict`, `robust`, ...) routed through the registry."""
    model, impl, ev = registry.COMMAND_TO_ENTRY[command]
    return run_entry(registry.get(model, impl, ev), as_of, params)


def describe() -> list[str]:
    """Lines for the `models` command."""
    lines = []
    for m in registry.models():
        lines.append(m)
        for e in registry.implementations(m):
            lines.append(f"  impl  {e.name:<14} [{e.run_type}]  {e.note}")
            lines.append("        reads: " + _fmt_inputs(e.inputs))
        for e in registry.evaluations(m):
            lines.append(f"  eval  {e.name:<14} of {e.of_impl}  {e.note}")
            lines.append("        reads: " + _fmt_inputs(e.inputs))
    return lines


def _fmt_inputs(inputs) -> str:
    parts = []
    for t, cols in inputs.items():
        parts.append(f"{t}(*)" if cols is None else f"{t}({len(cols)} cols)")
    return ", ".join(parts)
