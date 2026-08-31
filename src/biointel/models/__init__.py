# src/biointel/models/__init__.py
"""Model framework (gate 0.4): registry of models, implementations and
evaluations with declared inputs, and the harness that runs them under
input enforcement (P2) through the run ledger (P17).

Names state the question a model answers:
  target-screen     which companies will be acquired in the next 12 months
  acquirer-pairing  for a given target, which buyer is the likely acquirer
  fda-event-study   how a stock moves around an FDA decision
"""
