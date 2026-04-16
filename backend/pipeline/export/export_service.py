"""Export service — routes to the correct exporter based on format."""

import logging
from pathlib import Path

from backend.pipeline.export.latex_exporter import LatexExporter
from backend.pipeline.export.markdown_exporter import MarkdownExporter
from backend.pipeline.synthesis.proposal_synthesizer import ResearchProposal

logger = logging.getLogger(__name__)

EXPORTERS = {
    "markdown": (MarkdownExporter, ".md"),
    "latex": (LatexExporter, ".tex"),
    "md": (MarkdownExporter, ".md"),
    "tex": (LatexExporter, ".tex"),
}


class ExportService:
    def __init__(self, output_dir: str = "./data/exports"):
        self._output_dir = output_dir
        self._exporters = {name: cls() for name, (cls, _) in EXPORTERS.items()}

    async def export(
        self,
        proposal: ResearchProposal,
        format: str = "markdown",
        output_path: str | None = None,
    ) -> str:
        """Export proposal to the specified format.

        Args:
            proposal: The proposal to export.
            format: "markdown", "latex", "md", or "tex".
            output_path: Override output path. If None, auto-generates.

        Returns:
            Path to the exported file.
        """
        format = format.lower()
        if format not in self._exporters:
            raise ValueError(f"Unknown format: {format}. Supported: {list(EXPORTERS.keys())}")

        exporter = self._exporters[format]
        _, ext = EXPORTERS[format]

        if output_path is None:
            slug = proposal.title.lower().replace(" ", "-")[:50]
            slug = "".join(c for c in slug if c.isalnum() or c == "-")
            output_path = str(Path(self._output_dir) / f"{slug}{ext}")

        content = exporter.export(proposal, output_path=output_path)
        logger.info("Exported proposal to %s", output_path)

        return output_path
