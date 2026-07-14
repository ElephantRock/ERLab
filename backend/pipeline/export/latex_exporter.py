"""LaTeX exporter for research proposals."""

from pathlib import Path

from jinja2 import Template

from backend.pipeline.constants import AI_HONESTY_BADGE_BRIEF
from backend.pipeline.synthesis.proposal_synthesizer import ResearchProposal

TEMPLATE = r"""\documentclass[11pt,a4paper]{article}
\usepackage[utf8]{inputenc}
\usepackage{amsmath,amssymb}
\usepackage{graphicx}
\usepackage{hyperref}
\usepackage{booktabs}
\usepackage{geometry}
\geometry{margin=1in}

\title{ {{ title }} }
\author{Elephant Rock Research Platform}
\date{\today}

\begin{document}
\maketitle

\begin{abstract}
{{ abstract }}
\end{abstract}

\section{Introduction}
{{ introduction }}

\section{Related Work}
{{ related_work }}

\section{Proposed Method}
{{ proposed_method }}

\section{Expected Contributions}
{{ expected_contributions }}

\section{Evaluation Plan}
{{ evaluation_plan }}

\section{Timeline}
{{ timeline }}

{% if risk_mitigation %}
\section{Risk Mitigation}
{{ risk_mitigation }}

{% endif %}
\section*{References}
\begin{thebibliography}{99}
{% for ref in references %}
\bibitem{ref{{ loop.index }}} {{ ref }}
{% endfor %}
\end{thebibliography}

\vspace{1em}
\noindent\textit{\small AI_HONESTY_BADGE}

\end{document}
"""


class LatexExporter:
    def export(self, proposal: ResearchProposal, output_path: str | None = None, venue: str | None = None) -> str:
        """Export proposal to LaTeX. Returns the LaTeX string.

        Args:
            proposal: ResearchProposal to export.
            output_path: Optional file path to write .tex output.
            venue: Optional venue name (e.g. "IEEE", "ACM", "NeurIPS").
                   When provided, uses venue template instead of generic TEMPLATE.
        """
        if venue:
            from backend.pipeline.export.venue_templates import get_venue_template
            venue_tpl = get_venue_template(venue)
            # Build template from venue config
            preamble = venue_tpl.preamble()
            latex = self._render_with_venue(proposal, preamble, venue_tpl)
        else:
            latex = self._render_generic(proposal)

        # Insert AI honesty badge (A-05, HB-04)
        latex = latex.replace("AI_HONESTY_BADGE", AI_HONESTY_BADGE_BRIEF)

        if output_path:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            Path(output_path).write_text(latex, encoding="utf-8")

        return latex

    def _render_generic(self, proposal: ResearchProposal) -> str:
        """Render using the default generic TEMPLATE."""
        template = Template(TEMPLATE)

        # STOPGAP: render quarantined view so exported files reflect redaction.
        sections = self._render_quarantined(proposal)
        if "references" not in sections:
            sections["references"] = []

        # Format structured references into citation strings
        sections["references"] = [self._format_ref(r) for r in sections["references"]]
        # Format structured evaluation plan into a string
        sections["evaluation_plan"] = self._format_eval(sections.get("evaluation_plan", ""))

        # Escape LaTeX special characters in section content
        for key, value in sections.items():
            if isinstance(value, str):
                sections[key] = self._escape_latex(value)

        return template.render(**sections)

    def _render_with_venue(self, proposal: ResearchProposal, preamble: str, venue_tpl) -> str:
        """Render using a venue-specific preamble and body from paper markdown."""
        # Check for full paper in metadata
        metadata = {}
        if hasattr(proposal, 'metadata') and proposal.metadata:
            if isinstance(proposal.metadata, str):
                try:
                    import json
                    metadata = json.loads(proposal.metadata)
                except (json.JSONDecodeError, TypeError):
                    metadata = {}
            elif isinstance(proposal.metadata, dict):
                metadata = proposal.metadata

        full_paper = metadata.get("full_paper")
        if full_paper and isinstance(full_paper, dict):
            paper_md = full_paper.get("paper_markdown", "")
        else:
            paper_md = proposal.to_markdown() if hasattr(proposal, "to_markdown") else ""

        # Convert markdown body to LaTeX
        from backend.pipeline.export.md_to_latex import MarkdownToLatexConverter
        converter = MarkdownToLatexConverter()
        body = converter.convert(paper_md)

        title = self._escape_latex(
            proposal.title if hasattr(proposal, 'title') else "Research Proposal"
        )

        return (
            f"{preamble}\n\n"
            f"\\title{{{title}}}\n"
            f"\\author{{Elephant Rock Research Platform}}\n"
            f"\\date{{\\today}}\n\n"
            f"\\begin{{document}}\n"
            f"\\maketitle\n\n"
            f"{body}\n\n"
            f"\\vspace{{1em}}\n"
            f"\\noindent\\textit{{\\small AI_HONESTY_BADGE}}\n"
            f"\\end{{document}}\n"
        )

    @staticmethod
    def _render_quarantined(proposal) -> dict:
        """Return proposal.sections with quarantined citations redacted.

        Mirrors MarkdownExporter._render_quarantined. Fail-soft: returns the
        raw sections copy on any error or when no quarantine metadata exists.
        """
        sections = proposal.sections.copy()
        try:
            from backend.pipeline.quarantine import render_quarantined_view
            metadata = getattr(proposal, "metadata", None)
            if isinstance(metadata, str):
                import json as _json
                try:
                    metadata = _json.loads(metadata)
                except (ValueError, TypeError):
                    metadata = None
            if isinstance(metadata, dict):
                audit = metadata.get("citation_audit") or {}
                quarantined = audit.get("quarantined") or []
                if quarantined:
                    return render_quarantined_view(sections, quarantined)
        except Exception:
            pass
        return sections

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
                    parts.append(f"\\textbf{{{header}}}: " + ", ".join(str(v) for v in items))
            if eval_plan.get("ablation_design"):
                parts.append(f"\\textbf{{Ablation Design}}: {eval_plan['ablation_design']}")
            return "\n\n".join(parts)
        return str(eval_plan) if eval_plan else ""

    @staticmethod
    def _escape_latex(text: str) -> str:
        """Escape LaTeX special characters in prose, preserving math regions."""
        replacements = {
            "&": r"\&",
            "%": r"\%",
            "$": r"\$",
            "#": r"\#",
            "_": r"\_",
            "{": r"\{",
            "}": r"\}",
            "~": r"\textasciitilde{}",
            "^": r"\^{}",
        }

        # Split into prose and math segments, preserving math untouched.
        # Handles $...$ (inline) and $$...$$ (display) math.
        segments: list[str] = []
        i = 0
        while i < len(text):
            # Check for $$ (display math)
            if text[i : i + 2] == "$$":
                end = text.find("$$", i + 2)
                if end != -1:
                    segments.append(text[i : end + 2])  # math — no escape
                    i = end + 2
                    continue
            # Check for $ (inline math)
            if text[i] == "$":
                end = text.find("$", i + 1)
                if end != -1:
                    segments.append(text[i : end + 1])  # math — no escape
                    i = end + 1
                    continue
            # Prose character — escape it
            ch = text[i]
            segments.append(replacements.get(ch, ch))
            i += 1

        return "".join(segments)
