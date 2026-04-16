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

\section*{References}
\begin{itemize}
{% for ref in references %}
\item {{ ref }}
{% endfor %}
\end{itemize}

\end{document}
"""


class LatexExporter:
    def export(self, proposal: ResearchProposal, output_path: str | None = None) -> str:
        """Export proposal to LaTeX. Returns the LaTeX string."""
        template = Template(TEMPLATE)

        sections = proposal.sections.copy()
        if "references" not in sections:
            sections["references"] = []

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
    def _escape_latex(text: str) -> str:
        """Escape LaTeX special characters."""
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
        for old, new in replacements.items():
            text = text.replace(old, new)
        return text
