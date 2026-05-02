"""Cross-stage context persistence using the existing MemoryService.

Provides scoped storage for pipeline stage outputs, enabling:
- Context retrieval by later stages within the same run
- Context carry-over between pipeline runs
- State reconstruction on resume after failure

Each output is stored as a MemoryEntry with namespace scoped to the stage
and source_run_id for run isolation.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from backend.pipeline.memory.models import MemoryEntry, MemoryQuery, MemoryType

if TYPE_CHECKING:
    from backend.pipeline.memory.service import MemoryService

logger = logging.getLogger(__name__)

# Stage execution order for determining "prior" stages
_STAGE_ORDER = [
    "literature_search", "ingestion", "gap_analysis", "idea_generation",
    "novelty_checking", "feasibility_scoring", "proposal_synthesis", "export",
]


def _prior_stages(current_stage: str) -> list[str]:
    """Return stage names that execute before current_stage."""
    idx = _STAGE_ORDER.index(current_stage) if current_stage in _STAGE_ORDER else 0
    return _STAGE_ORDER[:idx]


class CrossStageContext:
    """Manages context persistence across pipeline stages and runs.

    Uses existing MemoryService with a dedicated namespace per stage.
    Context is scoped by (run_id, stage_name) for isolation.
    """

    def __init__(self, memory: MemoryService) -> None:
        self._memory = memory

    async def save_stage_output(
        self, run_id: str, stage: str, key: str, data: Any
    ) -> str:
        """Persist a stage output for cross-stage retrieval.

        Args:
            run_id: Pipeline run identifier.
            stage: Stage name (e.g., "gap_analysis").
            key: Output key within the stage (e.g., "gaps", "papers").
            data: Serializable data to persist.

        Returns:
            Memory entry ID.
        """
        namespace = f"cross_stage:{stage}"
        content = json.dumps(data, default=str) if not isinstance(data, str) else data
        entry = MemoryEntry(
            id=self._make_id(run_id, stage, key),
            content=content,
            memory_type=MemoryType.EPISODIC,
            namespace=namespace,
            source_run_id=run_id,
            tags=[stage, key],
        )
        return await self._memory.store(entry)

    async def load_stage_output(
        self, run_id: str, stage: str, key: str
    ) -> Any | None:
        """Load a specific stage output by run, stage, and key."""
        namespace = f"cross_stage:{stage}"
        query = MemoryQuery(
            query=f"{run_id}:{stage}:{key}",
            memory_type=MemoryType.EPISODIC,
            namespace=namespace,
            top_k=1,
        )
        results = await self._memory.recall(query)
        if not results:
            return None
        content = results[0].content
        try:
            return json.loads(content)
        except (json.JSONDecodeError, TypeError):
            return content

    async def load_prior_context(
        self, run_id: str, current_stage: str
    ) -> dict[str, Any]:
        """Load all outputs from stages preceding current_stage.

        Returns:
            Dict keyed by stage name, each containing that stage's
            persisted outputs as a dict keyed by output key.
        """
        prior = {}
        for stage in _prior_stages(current_stage):
            namespace = f"cross_stage:{stage}"
            query = MemoryQuery(
                query=run_id,
                memory_type=MemoryType.EPISODIC,
                namespace=namespace,
                top_k=20,
            )
            results = await self._memory.recall(query)
            if results:
                stage_data = {}
                for entry in results:
                    if entry.source_run_id != run_id:
                        continue
                    try:
                        parsed = json.loads(entry.content)
                        if isinstance(parsed, dict):
                            stage_data.update(parsed)
                        else:
                            for tag in entry.tags:
                                if tag != stage:
                                    stage_data[tag] = parsed
                                    break
                    except (json.JSONDecodeError, TypeError):
                        for tag in entry.tags:
                            if tag != stage:
                                stage_data[tag] = entry.content
                                break
                if stage_data:
                    prior[stage] = stage_data
        return prior

    async def save_run_summary(self, run_id: str, summary: dict) -> str:
        """Persist a run-level summary (used across runs for learning)."""
        entry = MemoryEntry(
            id=self._make_id(run_id, "run", "summary"),
            content=json.dumps(summary, default=str),
            memory_type=MemoryType.SEMANTIC,
            namespace="cross_stage:run_summary",
            source_run_id=run_id,
            tags=["run_summary"],
        )
        return await self._memory.store(entry)

    @staticmethod
    def _make_id(run_id: str, stage: str, key: str) -> str:
        """Stable ID for a (run, stage, key) tuple."""
        import hashlib
        raw = f"cross_stage:{run_id}:{stage}:{key}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]
