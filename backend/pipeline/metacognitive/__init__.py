"""Metacognitive strategy — progress tracking, plateau detection, strategy adaptation."""

from backend.pipeline.metacognitive.ledger import LedgerEntry, ProgressLedger
from backend.pipeline.metacognitive.manager import MetacognitiveManager
from backend.pipeline.metacognitive.plateau_detector import PlateauDetector, PlateauResult

__all__ = [
    "LedgerEntry",
    "MetacognitiveManager",
    "PlateauDetector",
    "PlateauResult",
    "ProgressLedger",
]
