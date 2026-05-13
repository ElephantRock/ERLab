"""STAGE_REGISTRY — maps all 16 stage names to model categories.

DEC-003: The 16 stage names match PipelineOrchestrator._STAGE_ORDER exactly.
Each entry maps a stage to the model category used to execute it:
  - thinking   → LLM reasoning (gap analysis, idea gen, etc.)
  - generation → LLM generation (proposal synthesis, paper synthesis, etc.)
  - embedding  → vector embedding (ingestion, novelty checking)
  - system     → non-LLM (export, mechanical_metrics)
"""
from __future__ import annotations

from typing import Literal

ModelCategory = Literal["thinking", "generation", "embedding", "system"]

StageName = Literal[
    "literature_search",
    "ingestion",
    "gap_analysis",
    "gap_reflection",
    "idea_generation",
    "idea_reflection",
    "novelty_checking",
    "feasibility_scoring",
    "mechanical_metrics",
    "proposal_synthesis",
    "adversarial_review",
    "evaluation",
    "paper_synthesis",
    "citation_audit",
    "proposal_deepening",
    "export",
]

# All 16 stages (DEC-003) with their model category assignments
STAGE_REGISTRY: dict[str, ModelCategory] = {
    "literature_search": "thinking",
    "ingestion": "embedding",
    "gap_analysis": "thinking",
    "gap_reflection": "thinking",
    "idea_generation": "thinking",
    "idea_reflection": "thinking",
    "novelty_checking": "embedding",
    "feasibility_scoring": "thinking",
    "mechanical_metrics": "system",
    "proposal_synthesis": "generation",
    "adversarial_review": "thinking",
    "evaluation": "thinking",
    "paper_synthesis": "generation",
    "citation_audit": "thinking",
    "proposal_deepening": "generation",
    "export": "system",
}

# Ordered list of all 16 stage names (matches _STAGE_ORDER)
ALL_STAGES: list[str] = [
    "literature_search",
    "ingestion",
    "gap_analysis",
    "gap_reflection",
    "idea_generation",
    "idea_reflection",
    "novelty_checking",
    "feasibility_scoring",
    "mechanical_metrics",
    "proposal_synthesis",
    "adversarial_review",
    "evaluation",
    "paper_synthesis",
    "citation_audit",
    "proposal_deepening",
    "export",
]
