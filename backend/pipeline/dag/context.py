"""StageContext — carries data between DAG stages.

AUTH-02: StageContext fields are append-only. Stages may add but not remove.
AUTH-01: config is an immutable snapshot taken at pipeline start.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any


@dataclass
class StageContext:
    """Shared context passed between DAG stages.

    *config* is frozen on construction (deep copy) so no stage can
    mutate the original pipeline YAML snapshot.
    """

    domain: str = ""
    papers: list = field(default_factory=list)
    gaps: list = field(default_factory=list)
    ideas: list = field(default_factory=list)
    proposals: dict = field(default_factory=dict)
    novelty_reports: dict = field(default_factory=dict)
    feasibility_reports: dict = field(default_factory=dict)
    mechanical_metrics: dict = field(default_factory=dict)
    config: dict = field(default_factory=dict)
    run_id: str = ""
    strategy: str = ""
    log: Any = None  # StageLogger instance

    def __post_init__(self) -> None:
        # Freeze config as an immutable snapshot (AUTH-01)
        object.__setattr__(self, "config", copy.deepcopy(self.config))

    def __setattr__(self, name: str, value: Any) -> None:
        # Config is read-only after construction
        if name == "config" and hasattr(self, "config"):
            raise AttributeError("StageContext.config is read-only (AUTH-01)")
        object.__setattr__(self, name, value)

    # ── count helpers ─────────────────────────────────────────

    @property
    def paper_count(self) -> int:
        return len(self.papers)

    @property
    def gap_count(self) -> int:
        return len(self.gaps)

    @property
    def idea_count(self) -> int:
        return len(self.ideas)

    @property
    def proposal_count(self) -> int:
        return len(self.proposals)
