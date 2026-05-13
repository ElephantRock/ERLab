"""DAG-based pipeline runner (BATCH-180).

Replaces the tangled orchestrator config layer with:
  - pipeline.yaml  — single source of truth
  - ConfigLoader   — validates and snapshots the YAML
  - StageLogger    — one JSON entry per stage execution
  - DAGRunner      — reads YAML, builds plan, executes stages
"""
from __future__ import annotations

from .config import ConfigLoader

__all__ = ["ConfigLoader"]
