"""Multi-layer context compaction for the research pipeline."""

from backend.pipeline.compaction.middleware import CompactionMiddleware
from backend.pipeline.compaction.paper_selector import PaperSelector
from backend.pipeline.compaction.summarizer import ContextSummarizer
from backend.pipeline.compaction.budget_manager import (
    ContextBudgetManager,
    CompactionRecommendation,
)

__all__ = [
    "CompactionMiddleware",
    "CompactionRecommendation",
    "ContextBudgetManager",
    "ContextSummarizer",
    "PaperSelector",
]
