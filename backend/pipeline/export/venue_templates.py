"""Venue-specific LaTeX templates for paper export.

Provides document-class, preamble, and package configurations for
IEEE, ACM, NeurIPS, and Generic venues. Templates are self-contained
string templates (A-03), not file dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class VenueTemplate:
    """Configuration for a venue-specific LaTeX template."""

    name: str
    document_class: str
    packages: list[str] = field(default_factory=list)
    preamble_extra: str = ""
    max_pages: int | None = None

    def preamble(self) -> str:
        """Generate the LaTeX preamble from this template."""
        lines = [self.document_class]
        for pkg in self.packages:
            lines.append(f"\\usepackage{{{pkg}}}")
        if self.preamble_extra:
            lines.append(self.preamble_extra)
        return "\n".join(lines)


# ── Preset Templates ───────────────────────────────────────

IEEE_TEMPLATE = VenueTemplate(
    name="IEEE",
    document_class=r"\documentclass[conference]{IEEEtran}",
    packages=[
        "cite",
        "amsmath",
        "amssymb",
        "amsfonts",
        "algorithmic",
        "graphicx",
        "textcomp",
    ],
    preamble_extra=r"""
\IEEEoverridecommandlockouts
""",
    max_pages=8,
)

ACM_TEMPLATE = VenueTemplate(
    name="ACM",
    document_class=r"\documentclass[sigconf]{acmart}",
    packages=[
        "ACM-Reference-Format",
    ],
    preamble_extra=r"""
\acmConference[Conference'26]{ACM Conference}{2026}{City, Country}
\copyrightyear{2026}
\copyright{\acmCopyright{2026}}
""",
    max_pages=10,
)

NEURIPS_TEMPLATE = VenueTemplate(
    name="NeurIPS",
    document_class=r"\documentclass{neurips_2026}",
    packages=[
        "inputenc",
        "fontenc",
        "hyperref",
        "url",
        "booktabs",
        "amsfonts",
        "nicefrac",
        "microtype",
        "graphicx",
    ],
    preamble_extra=r"""
\usepackage{icml2026}
""",
    max_pages=9,
)

GENERIC_TEMPLATE = VenueTemplate(
    name="Generic",
    document_class=r"\documentclass[11pt,a4paper]{article}",
    packages=[
        "inputenc",
        "amsmath",
        "amssymb",
        "graphicx",
        "hyperref",
        "booktabs",
        "geometry",
    ],
    preamble_extra=r"\geometry{margin=1in}",
    max_pages=None,
)

# ── Lookup ──────────────────────────────────────────────────

VENUE_TEMPLATES: dict[str, VenueTemplate] = {
    "IEEE": IEEE_TEMPLATE,
    "ACM": ACM_TEMPLATE,
    "NeurIPS": NEURIPS_TEMPLATE,
    "Generic": GENERIC_TEMPLATE,
}


def get_venue_template(name: str) -> VenueTemplate:
    """Return a venue template by name, defaulting to Generic."""
    return VENUE_TEMPLATES.get(name, GENERIC_TEMPLATE)
