"""LaTeX exporter for research proposals."""

from pathlib import Path

from jinja2 import Template

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

\end{document}
"""


class LatexExporter:
    def export(self, proposal: ResearchProposal, output_path: str | None = None) -> str:
        """Export proposal to LaTeX. Returns the LaTeX string."""
        template = Template(TEMPLATE)

        sections = proposal.sections.copy()
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

        latex = template.render(**sections)

        if output_path:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            Path(output_path).write_text(latex, encoding="utf-8")

        return latex

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
