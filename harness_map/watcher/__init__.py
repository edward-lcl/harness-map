"""Watcher package — fetches, diffs, emits PromptArtifact + PromptChangeEvent."""
from .orchestrator import Orchestrator, RunSummary, main

__all__ = ["Orchestrator", "RunSummary", "main"]
