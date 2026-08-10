"""Multi-layer context compaction for the research pipeline."""

from backend.pipeline.compaction.budget_manager import (
    CompactionRecommendation,
    ContextBudgetManager,
)
from backend.pipeline.compaction.middleware import CompactionMiddleware
from backend.pipeline.compaction.paper_selector import PaperSelector
from backend.pipeline.compaction.summarizer import ContextSummarizer

__all__ = [
    "CompactionMiddleware",
    "CompactionRecommendation",
    "ContextBudgetManager",
    "ContextSummarizer",
    "PaperSelector",
]
