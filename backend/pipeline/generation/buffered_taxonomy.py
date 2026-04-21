"""Buffered error taxonomy for safe parallel writes.

Duck-type replacement for ErrorTaxonomy that collects record() calls
in memory during parallel execution, then flushes to the real taxonomy
after all parallel agents complete. No changes needed to CriticAgent.
"""

from __future__ import annotations

from backend.pipeline.generation.error_taxonomy import ErrorCategory, ErrorTaxonomy


class BufferedErrorTaxonomy:
    """Collects error observations in memory, flushes to real taxonomy later."""

    def __init__(self, source: ErrorTaxonomy) -> None:
        self._source = source
        self._buffer: list[tuple[ErrorCategory, str]] = []

    def classify(self, text: str) -> ErrorCategory | None:
        return self._source.classify(text)

    def format_prompt_section(self) -> str:
        return self._source.format_prompt_section()

    def get_weights(self) -> dict[ErrorCategory, float]:
        return self._source.get_weights()

    def record(self, category: ErrorCategory, description: str) -> None:
        """Buffer the record instead of writing to disk immediately."""
        self._buffer.append((category, description))

    def flush(self) -> None:
        """Flush all buffered records to the real taxonomy."""
        for cat, desc in self._buffer:
            self._source.record(cat, desc)
        self._buffer.clear()

    @property
    def buffer_size(self) -> int:
        return len(self._buffer)
