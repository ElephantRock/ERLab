"""Deterministic result-marker value reconciliation for empirical papers.

The synthesis contract passes authoritative strings
``[RESULT-N] metric = value (role=..., direction=...)`` to every synthesis
route. The numeric-fidelity validator (``evaluation.claim_result_validator``)
blocks a paper when a number rendered beside a ``[RESULT-N]`` marker differs
from the marker's persisted ``observed_value`` within its tight tolerance —
including the dropped-leading-decimal corruption observed live in
run_6395d309b07a (``333333 [RESULT-1]`` against a persisted ``0.333333``).

This module is the producer-side guarantee for the synthesis-output-fidelity
remediation: after synthesis, every marker-adjacent number is reconciled to
the exact persisted value, and an unrepairable mismatch fails closed instead
of shipping.

Scope guard (owner-frozen remediation): this changes synthesis OUTPUT
fidelity only. Validator semantics, thresholds, marker identities/roles,
experiment execution, and result persistence are untouched. The validator
remains the acceptance oracle — this module imports the validator's own
adjacency patterns and agreement test, so it repairs exactly (and only) what
the oracle would block, and anything the oracle accepts passes through
unmodified.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from types import SimpleNamespace

from backend.pipeline.evaluation import claim_result_validator as crv
from backend.pipeline.evaluation.conclusion_support import (
    evaluate_conclusion_support,
)

logger = logging.getLogger(__name__)

# Authoritative marker strings are produced by
# PaperSynthesisStage._format_result_marker:
#   "[RESULT-1] baseline_accuracy = 0.333333 (role=baseline, direction=...)"
_MARKER_STRING_RE = re.compile(
    r"^\[(?P<bracket>RESULT-\d+)\]\s*"
    r"(?P<metric>[^=]+?)\s*=\s*"
    r"(?P<value>[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)"
)


class ResultMarkerFidelityError(RuntimeError):
    """Empirical paper text could not be reconciled to persisted results.

    Raised fail-closed: an unrepairable marker-adjacent number, or an
    empirical conclusion that remains unbacked after the corrective
    re-synthesis, aborts the empirical paper instead of shipping text that
    the evaluation gates would block.
    """


@dataclass
class MarkerValue:
    """One authoritative marker parsed from its contract string."""

    bracket: str  # "[RESULT-1]"
    metric_name: str
    value_text: str  # exact authoritative token, e.g. "0.333333"
    observed_value: float


@dataclass
class MarkerFidelityReport:
    """Outcome of one reconciliation pass over a synthesized paper."""

    checked: int = 0
    repairs: list[str] = field(default_factory=list)
    violations: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.violations


def parse_marker_strings(result_markers: list[str]) -> list[MarkerValue]:
    """Parse the authoritative ``[RESULT-N] metric = value`` strings."""
    parsed: list[MarkerValue] = []
    for raw in result_markers or []:
        m = _MARKER_STRING_RE.match(raw.strip())
        if not m:
            raise ResultMarkerFidelityError(
                f"unparseable authoritative result marker string: {raw!r}"
            )
        parsed.append(
            MarkerValue(
                bracket=f"[{m.group('bracket')}]",
                metric_name=m.group("metric").strip(),
                value_text=m.group("value"),
                observed_value=float(m.group("value")),
            )
        )
    return parsed


def _norm_digits(token: str) -> str:
    """Digits of a numeric token with separators and leading zeros dropped.

    ``0.333333`` → ``333333``; ``333333`` → ``333333``. Sign is preserved
    as a prefix so a flipped sign never normalizes into the positive
    authoritative value.
    """
    stripped = token.replace(".", "").replace(",", "").replace("%", "")
    return stripped.lstrip("0") or "0"


def _is_sanctioned_corruption(
    token: str, marker: MarkerValue, *, percentified: bool
) -> bool:
    """True iff the token is one of the two sanctioned corruption shapes.

    Sanctioned (deterministically repairable to the authoritative value):
      - dropped decimal point: ``0.333333`` rendered as ``333333``
        (token equals the authoritative digits with the point removed);
      - percentified form: ``33.3333%`` against ``0.333333``
        (float(token) == observed_value * 100).

    Everything else — sign flips, decimal-position shifts such as
    ``3.33333``, truncated values — fails closed.
    """
    if token[:1] in ("-", "+"):
        return False
    bare = token.rstrip("%")
    if percentified:
        try:
            return abs(
                float(bare) - marker.observed_value * 100
            ) <= abs(marker.observed_value * 100) * 1e-6 + 1e-9
        except ValueError:
            return False
    dropped = (
        marker.value_text.replace(".", "").replace(",", "").lstrip("0") or "0"
    )
    return (
        token.replace(".", "").replace(",", "").lstrip("0") == dropped
        and token.lstrip("-+").find(".") == -1
    )


def _repair_span(match: re.Match, value_text: str) -> str:
    """Rebuild one validator adjacency match with the exact value token.

    Replaces the rendered number — and a directly attached '%' when the
    token was percentified — with the authoritative value text, preserving
    any surrounding markdown emphasis from the original match.
    """
    text = match.group(0)
    num_start = match.start("num") - match.start()
    num_end = match.end("num") - match.start()
    prefix = text[:num_start]
    suffix = text[num_end:]
    # A percentifier directly attached to the number is dropped: the
    # authoritative value is a fraction, and "0.333333%" would be wrong.
    suffix = re.sub(r"^\s*%", "", suffix)
    return f"{prefix}{value_text}{suffix}"


def reconcile_marker_values(
    paper_md: str,
    markers: list[MarkerValue],
) -> tuple[str, MarkerFidelityReport]:
    """Repair marker-adjacent numbers to the exact persisted values.

    Uses the validator's own adjacency patterns and agreement test: a
    rendered number the oracle accepts is left untouched; one it would
    block is repaired when (and only when) its normalized digits match the
    authoritative value (dropped decimal point / percentified form);
    anything else is reported as a violation for fail-closed handling.
    Repairs are collected first and applied back-to-front so earlier
    spans stay valid.
    """
    report = MarkerFidelityReport()
    if not markers or not paper_md:
        return paper_md, report

    by_bracket = {m.bracket: m for m in markers}
    text = paper_md

    # ── Numbers immediately BEFORE the marker (validator pattern) ──
    repairs: list[tuple[int, int, str, str]] = []  # (start, end, fixed, desc)
    for m in crv._NUM_BEFORE_RE.finditer(text):
        marker = next(
            (mk for b, mk in by_bracket.items() if b in m.group(0)), None
        )
        if marker is None:
            continue
        report.checked += 1
        token = m.group("num")
        try:
            rendered = float(token)
            if crv._values_agree(rendered, marker.observed_value):
                continue
        except ValueError:
            pass
        if _is_sanctioned_corruption(
            token, marker, percentified="%" in m.group(0)
        ):
            repairs.append(
                (
                    m.start(),
                    m.end(),
                    _repair_span(m, marker.value_text),
                    f"{marker.bracket}: rendered {token!r} repaired to "
                    f"{marker.value_text!r}",
                )
            )
        else:
            report.violations.append(
                f"{marker.bracket}: rendered {token!r} cannot be reconciled "
                f"to persisted {marker.value_text!r}"
            )
    for start, end, fixed, desc in sorted(repairs, key=lambda r: -r[0]):
        text = text[:start] + fixed + text[end:]
        report.repairs.append(desc)

    # ── Numbers immediately AFTER the marker (validator pattern) ──
    # Run on the repaired text so spans reflect any before-marker fixes.
    repairs = []
    for bracket, marker in by_bracket.items():
        # Oracle parity: the validator's own after-marker pattern, filtered
        # to this bracket (the validator scans generically and filters by
        # marker index the same way).
        for m in crv._NUM_AFTER_RE.finditer(text):
            if bracket not in m.group(0):
                continue
            report.checked += 1
            token = m.group("num")
            try:
                rendered = float(token)
                if crv._values_agree(rendered, marker.observed_value):
                    continue
            except ValueError:
                continue
            if _is_sanctioned_corruption(
                token, marker, percentified="%" in m.group(0)
            ):
                repairs.append(
                    (
                        m.start(),
                        m.end(),
                        _repair_span(m, marker.value_text),
                        f"{bracket}: rendered {token!r} repaired to "
                        f"{marker.value_text!r}",
                    )
                )
            else:
                report.violations.append(
                    f"{bracket}: rendered {token!r} cannot be reconciled to "
                    f"persisted {marker.value_text!r}"
                )
    for start, end, fixed, desc in sorted(repairs, key=lambda r: -r[0]):
        text = text[:start] + fixed + text[end:]
        report.repairs.append(desc)

    if report.repairs:
        logger.info(
            "Result-marker reconciliation: %d value(s) repaired (%s)",
            len(report.repairs),
            "; ".join(report.repairs[:5]),
        )
    if report.violations:
        logger.error(
            "Result-marker reconciliation: %d unrepairable mismatch(es) (%s)",
            len(report.violations),
            "; ".join(report.violations[:5]),
        )
    return text, report


def empirical_claim_violations(
    paper_md: str, markers: list[MarkerValue]
) -> list[str]:
    """Empirical conclusions in abstract/conclusion lacking marker backing.

    Reuses the canonical shared rule (``evaluation.conclusion_support``)
    read-only — the same detector the evaluation gate applies — so a
    violation here is exactly a violation the gate would block on.
    """
    pseudo = [
        SimpleNamespace(marker_index=int(m.bracket[len("[RESULT-"):-1]))
        for m in markers
    ]
    assessment = evaluate_conclusion_support(paper_md, pseudo)
    return list(assessment.indicators or [])


def build_correction_instruction(violations: list[str]) -> str:
    """The corrective block injected into a bounded re-synthesis attempt."""
    quoted = " | ".join(violations[:5])
    return (
        "## Corrective Requirement (GROUND TRUTH INVARIANTS violation)\n"
        "Your previous draft violated the marker-fidelity invariants. "
        f"Detected: {quoted}. Every empirical assertion about observed "
        "findings MUST carry its [RESULT-N] marker in the same sentence, "
        "with the metric value copied character-for-character from the "
        "Experiment Ground Truth block (e.g. 0.333333 — never 333333, "
        "33.3333%, or a rounded variant). Sentences that cannot carry a "
        "marker MUST be restated as hypotheses or expectations, not as "
        "observations."
    )
