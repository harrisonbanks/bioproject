# src/biointel/collectors/__init__.py
"""Collector family for the research library (Ontology v5 §3.9): each module
turns one source into references + captures through biointel.library. None is
required; the store is identical whichever door a document came through."""
from . import folder, manual, pipeline_docs, zotero  # noqa: F401
