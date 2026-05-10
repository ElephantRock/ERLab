"""Markdown exporter for research proposals."""

from pathlib import Path

from jinja2 import Template

from backend.pipeline.constants import AI_HONESTY_BADGE
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

        sections["references"] = [self._format_ref(r) for r in sections["references"]]
        sections["evaluation_plan"] = self._format_eval(sections.get("evaluation_plan", ""))

        md = template.render(**sections)

        # Append AI honesty badge (A-05, HB-04)
        md += AI_HONESTY_BADGE

        if output_path:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            Path(output_path).write_text(md, encoding="utf-8")

        return md

    @staticmethod
    def _format_ref(ref) -> str:
        if isinstance(ref, dict):
            authors = ref.get("authors", "Unknown")
            year = ref.get("year", "n.d.")
            title = ref.get("title", "Untitled")
            venue = ref.get("venue", "")
            doi = ref.get("doi", "")
            url = ref.get("url", "")
            line = f"{authors} ({year}). {title}."
            if venue:
                line += f" {venue}."
            if doi:
                line += f" DOI: {doi}"
            elif url:
                line += f" URL: {url}"
            return line
        return str(ref)

    @staticmethod
    def _format_eval(eval_plan) -> str:
        if isinstance(eval_plan, dict):
            parts = []
            if eval_plan.get("summary"):
                parts.append(eval_plan["summary"])
            for key in ("datasets", "baselines", "metrics"):
                items = eval_plan.get(key)
                if isinstance(items, list) and items:
                    header = key.replace("_", " ").title()
                    parts.append(f"**{header}**: " + ", ".join(str(v) for v in items))
            if eval_plan.get("ablation_design"):
                parts.append(f"**Ablation Design**: {eval_plan['ablation_design']}")
            return "\n\n".join(parts)
        return str(eval_plan) if eval_plan else ""
