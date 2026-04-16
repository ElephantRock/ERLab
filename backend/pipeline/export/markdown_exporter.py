"""Markdown exporter for research proposals."""

from pathlib import Path

from jinja2 import Template

from backend.pipeline.synthesis.proposal_synthesizer import ResearchProposal

TEMPLATE = """# {{ title }}

## Abstract

{{ abstract }}

## 1. Introduction

{{ introduction }}

## 2. Related Work

{{ related_work }}

## 3. Proposed Method

{{ proposed_method }}

## 4. Expected Contributions

{{ expected_contributions }}

## 5. Evaluation Plan

{{ evaluation_plan }}

## 6. Timeline

{{ timeline }}

## References

{% for ref in references %}
- {{ ref }}
{% endfor %}
"""


class MarkdownExporter:
    def export(self, proposal: ResearchProposal, output_path: str | None = None) -> str:
        """Export proposal to Markdown. Returns the markdown string."""
        template = Template(TEMPLATE)

        sections = proposal.sections.copy()
        if "references" not in sections:
            sections["references"] = []

        md = template.render(**sections)

        if output_path:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            Path(output_path).write_text(md, encoding="utf-8")

        return md
