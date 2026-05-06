"""Phase 6/7 integration service for PipelineOrchestrator.

Wraps SoulLoader, JournalWriter, and ContextManager into a single
service that can be called from the orchestrator at key lifecycle points.
"""
from __future__ import annotations

import logging
from typing import Any, TYPE_CHECKING

from backend.pipeline.soul_loader import inject_soul, clear_cache
from backend.pipeline.journal.writer import JournalWriter
from backend.pipeline.context.manager import ContextManager, ContextBudget

if TYPE_CHECKING:
    from backend.pipeline.result import PipelineResult

logger = logging.getLogger(__name__)


class PipelineIntegrationService:
    """Centralized Phase 6/7 integration for the pipeline.

    Provides:
    - Soul injection into LLM prompts
    - Journal writing throughout pipeline lifecycle
    - Context management for token budgets

    All methods are fail-safe — they log warnings but never crash (HB-01/02).
    """

    def __init__(self, run_id: str = "", domain: str = "", token_budget: int = 8192) -> None:
        self._run_id = run_id
        self._domain = domain
        self._journal = JournalWriter(run_id=run_id, domain=domain)
        self._context = ContextManager(budget=ContextBudget(max_total_tokens=token_budget))
        self._soul_loaded = False

        # Try loading SOUL.md
        try:
            clear_cache()
            self._soul_loaded = True
            logger.info("PipelineIntegrationService: SOUL.md loaded")
        except Exception as e:
            logger.warning("PipelineIntegrationService: SOUL.md load failed: %s", e)

    def inject_soul_into_prompt(self, system_prompt: str) -> str:
        """Inject SOUL.md philosophy into a system prompt (HB-01: fail-safe)."""
        try:
            return inject_soul(system_prompt)
        except Exception as e:
            logger.warning("Soul injection failed: %s", e)
            return system_prompt

    def journal_note(self, stage: str, message: str, details: dict | None = None) -> None:
        """Add a journal note (HB-02: fail-safe)."""
        try:
            self._journal.add_note(stage, message, details)
        except Exception as e:
            logger.warning("Journal note failed: %s", e)

    def journal_write(self) -> tuple[str, str]:
        """Write journal files. Returns (notes_path, readme_path) as strings."""
        try:
            notes_path, readme_path = self._journal.write()
            self.journal_note("journal", "Journal written successfully")
            return str(notes_path), str(readme_path)
        except Exception as e:
            logger.warning("Journal write failed: %s", e)
            return "", ""

    def build_context(
        self,
        system_prompt: str,
        domain_contexts: list[str] | None = None,
        task_context: str = "",
    ) -> str:
        """Build a token-budgeted context for an LLM call."""
        try:
            self._context.set_system(system_prompt)
            if domain_contexts:
                for dc in domain_contexts:
                    self._context.add_domain(dc)
            if task_context:
                self._context.set_task(task_context)
            return self._context.build()
        except Exception as e:
            logger.warning("Context build failed: %s", e)
            return system_prompt

    @property
    def journal_entries(self) -> int:
        return len(self._journal.entries)

    @property
    def context_manager(self) -> ContextManager:
        return self._context
