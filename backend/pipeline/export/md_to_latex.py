"""Markdown-to-LaTeX converter for arbitrary proposal text.

Converts markdown headings, bold, italic, lists, code blocks,
tables, and links to their LaTeX equivalents.
"""
from __future__ import annotations

import re
import logging

from backend.pipeline.constants import AI_HONESTY_BADGE_BRIEF

logger = logging.getLogger(__name__)


class MarkdownToLatexConverter:
    """Convert arbitrary Markdown text to LaTeX source.

    Handles: headings, bold, italic, inline code, code blocks,
    unordered/ordered lists, tables, and links.
    Graceful on malformed input (HB-01).
    """

    def convert(self, markdown: str) -> str:
        """Convert markdown string to LaTeX body content."""
        if not markdown:
            return ""

        lines = markdown.split("\n")
        output_lines: list[str] = []
        in_code_block = False
        in_table = False
        in_itemize = False
        in_enumerate = False

        i = 0
        while i < len(lines):
            line = lines[i]

            # Code blocks
            if line.strip().startswith("```"):
                if in_code_block:
                    output_lines.append("\\end{verbatim}")
                    in_code_block = False
                else:
                    # Close any open list
                    in_itemize, in_enumerate = self._close_list(
                        output_lines, in_itemize, in_enumerate)
                    output_lines.append("\\begin{verbatim}")
                    in_code_block = True
                i += 1
                continue

            if in_code_block:
                output_lines.append(line)
                i += 1
                continue

            # Tables
            if "|" in line and line.strip().startswith("|"):
                if not in_table:
                    in_itemize, in_enumerate = self._close_list(
                        output_lines, in_itemize, in_enumerate)
                    output_lines.append("\\begin{tabular}{|l|l|}")
                    output_lines.append("\\hline")
                    in_table = True
                # Check if it's a separator line
                if re.match(r"^\|[\s\-:|]+\|$", line.strip()):
                    i += 1
                    continue
                cells = [c.strip() for c in line.strip("|").split("|")]
                output_lines.append(" & ".join(cells) + " \\\\")
                output_lines.append("\\hline")
                i += 1
                continue
            elif in_table:
                output_lines.append("\\end{tabular}")
                in_table = False

            # Headings
            heading_match = re.match(r"^(#{1,4})\s+(.+)$", line)
            if heading_match:
                in_itemize, in_enumerate = self._close_list(
                    output_lines, in_itemize, in_enumerate)
                level = len(heading_match.group(1))
                title = self._convert_inline(heading_match.group(2))
                latex_cmd = {1: "section", 2: "subsection", 3: "subsubsection", 4: "paragraph"}
                cmd = latex_cmd.get(level, "subsubsection")
                output_lines.append(f"\\{cmd}{{{title}}}")
                i += 1
                continue

            # Unordered lists
            ulist_match = re.match(r"^[\s]*[-*+]\s+(.+)$", line)
            if ulist_match:
                if not in_itemize:
                    output_lines.append("\\begin{itemize}")
                    in_itemize = True
                output_lines.append(f"  \\item {self._convert_inline(ulist_match.group(1))}")
                i += 1
                continue

            # Ordered lists
            olist_match = re.match(r"^[\s]*\d+\.\s+(.+)$", line)
            if olist_match:
                if not in_enumerate:
                    output_lines.append("\\begin{enumerate}")
                    in_enumerate = True
                output_lines.append(f"  \\item {self._convert_inline(olist_match.group(1))}")
                i += 1
                continue

            # Close lists if we get a non-list line
            if in_itemize or in_enumerate:
                in_itemize, in_enumerate = self._close_list(
                    output_lines, in_itemize, in_enumerate)

            # Horizontal rule
            if re.match(r"^[-*_]{3,}\s*$", line):
                output_lines.append("\\noindent\\rule{\\textwidth}{0.4pt}")
                i += 1
                continue

            # Regular paragraph
            if line.strip():
                output_lines.append(self._convert_inline(line))
            else:
                output_lines.append("")

            i += 1

        # Close any remaining environments
        if in_code_block:
            output_lines.append("\\end{verbatim}")
        if in_table:
            output_lines.append("\\end{tabular}")
        in_itemize, in_enumerate = self._close_list(
            output_lines, in_itemize, in_enumerate)

        return "\n".join(output_lines)

    def convert_to_document(self, markdown: str, title: str = "Research Proposal") -> str:
        """Convert markdown to a complete LaTeX document."""
        body = self.convert(markdown)
        return (
            "\\documentclass[11pt,a4paper]{article}\n"
            "\\usepackage[utf8]{inputenc}\n"
            "\\usepackage{amsmath,amssymb}\n"
            "\\usepackage{graphicx}\n"
            "\\usepackage{hyperref}\n"
            "\\usepackage{booktabs}\n"
            "\\usepackage{geometry}\n"
            "\\geometry{margin=1in}\n"
            "\n"
            f"\\title{{{self._escape(title)}}}\n"
            "\\author{Elephant Rock Research Platform}\n"
            "\\date{\\today}\n"
            "\n"
            "\\begin{document}\n"
            "\\maketitle\n"
            "\n"
            f"{body}\n"
            "\n"
            f"\\vspace{{1em}}\\noindent\\textit{{\\small {AI_HONESTY_BADGE_BRIEF}}}"
            "\n"
            "\\end{document}\n"
        )

    @staticmethod
    def _convert_inline(text: str) -> str:
        """Convert inline markdown formatting to LaTeX."""
        # Bold
        text = re.sub(r"\*\*(.+?)\*\*", r"\\textbf{\1}", text)
        # Italic
        text = re.sub(r"\*(.+?)\*", r"\\textit{\1}", text)
        # Inline code
        text = re.sub(r"`([^`]+)`", r"\\texttt{\1}", text)
        # Links
        text = re.sub(r"\[(.+?)\]\((.+?)\)", r"\\href{\2}{\1}", text)
        return text

    @staticmethod
    def _escape(text: str) -> str:
        """Escape LaTeX special characters."""
        for char, replacement in [("&", r"\&"), ("%", r"\%"), ("#", r"\#")]:
            text = text.replace(char, replacement)
        return text

    @staticmethod
    def _close_list(
        lines: list[str], in_itemize: bool, in_enumerate: bool
    ) -> tuple[bool, bool]:
        """Close any open list environments."""
        if in_itemize:
            lines.append("\\end{itemize}")
        if in_enumerate:
            lines.append("\\end{enumerate}")
        return False, False
