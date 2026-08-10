"""JournalWriter: produces research journal per pipeline run.

Accumulates stage-by-stage notes during pipeline execution.
Generates two files at run completion:
- notes.md: Detailed stage-by-stage log
- README.md: Clean summary for human consumption

Inspired by simonw/research methodology.
"""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# Sensitive patterns to scrub
_SENSITIVE_PATTERNS = ["sk-", "api_key", "password", "secret", "token"]


class JournalWriter:
    """Accumulates and writes pipeline run journals."""

    def __init__(self, run_id: str = "", domain: str = "", output_dir: str = "./data/runs") -> None:
        self.run_id = run_id
        self.domain = domain
        self.output_dir = Path(output_dir) / run_id
        self._entries: list[dict] = []
        self._started_at = datetime.utcnow()

    def add_note(self, stage: str, message: str, details: dict | None = None) -> None:
        """Add a stage note to the journal."""
        # Scrub sensitive data (HB-01)
        message = self._scrub(message)
        self._entries.append({
            "timestamp": datetime.utcnow().isoformat(),
            "stage": stage,
            "message": message,
            "details": details or {},
        })

    def write(self) -> tuple[Path, Path]:
        """Write notes.md and README.md. Returns (notes_path, readme_path)."""
        self.output_dir.mkdir(parents=True, exist_ok=True)

        notes_path = self.output_dir / "notes.md"
        readme_path = self.output_dir / "README.md"

        notes_path.write_text(self._generate_notes(), encoding="utf-8")
        readme_path.write_text(self._generate_readme(), encoding="utf-8")

        logger.info("Journal written to %s", self.output_dir)
        return notes_path, readme_path

    def _generate_notes(self) -> str:
        """Generate detailed notes.md."""
        lines = [
            f"# Pipeline Run Journal — {self.run_id}",
            "",
            f"**Domain**: {self.domain}",
            f"**Started**: {self._started_at.isoformat()}",
            f"**Entries**: {len(self._entries)}",
            "",
            "> **AI-Generated Content**: This journal was produced by an automated",
            "> research pipeline (Elephant Rock). All content below was generated",
            "> by AI systems. Verify findings independently.",
            "",
            "---",
            "",
        ]

        current_stage = None
        for entry in self._entries:
            if entry["stage"] != current_stage:
                current_stage = entry["stage"]
                lines.append(f"## {current_stage.replace('_', ' ').title()}")
                lines.append("")

            lines.append(f"- **{entry['timestamp']}**: {entry['message']}")
            if entry["details"]:
                for k, v in entry["details"].items():
                    lines.append(f"  - {k}: {v}")

        return "\n".join(lines)

    def _generate_readme(self) -> str:
        """Generate clean README.md summary."""
        from backend.pipeline.constants import AI_HONESTY_BADGE_BRIEF
        duration = (datetime.utcnow() - self._started_at).total_seconds()

        lines = [
            f"# Research Report — {self.run_id}",
            "",
            "| Field | Value |",
            "|-------|-------|",
            f"| Domain | {self.domain} |",
            f"| Started | {self._started_at.strftime('%Y-%m-%d %H:%M UTC')} |",
            f"| Duration | {duration:.0f}s |",
            f"| Stages | {len(set(e['stage'] for e in self._entries))} |",
            f"| Notes | {len(self._entries)} |",
            "",
            f"> {AI_HONESTY_BADGE_BRIEF}",
            "",
        ]

        # Stage summaries
        stages_seen = []
        for entry in self._entries:
            stage = entry["stage"]
            if stage not in stages_seen:
                stages_seen.append(stage)
                # Find the completion or last message for this stage
                stage_entries = [e for e in self._entries if e["stage"] == stage]
                last_msg = stage_entries[-1]["message"]
                lines.append(f"### {stage.replace('_', ' ').title()}")
                lines.append("")
                lines.append(f"{last_msg}")
                lines.append("")

        return "\n".join(lines)

    @property
    def entries(self) -> list[dict]:
        return self._entries

    @staticmethod
    def _scrub(text: str) -> str:
        """Remove sensitive patterns from text (HB-01)."""
        for pattern in _SENSITIVE_PATTERNS:
            if pattern in text.lower():
                # Replace the sensitive portion
                parts = text.split(pattern)
                text = parts[0] + "[REDACTED]" + "".join(parts[1:])
        return text
