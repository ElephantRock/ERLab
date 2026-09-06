"""Productive-1 R5 — deterministic, evidence-derived exact-span numeric patches.

Frozen contract (owner authorization, 2026-08-30): for every
numeric-fidelity mismatch, derive the authorized numeric token span and
the required replacement directly from persisted RESULT evidence; apply
only those patches; prove byte identity outside authorized spans;
preserve all previously passing gates and document structure; then hand
the candidate unchanged to the existing PAC authoritative
evaluation/promotion path.

Why this shape (R4 adjudication, 2026-08-30): section regeneration
destroyed already-passing method-fidelity compliance when a malformed
paper collapsed most of the manuscript into one parser section, and a
scoped replacement introduced a results section that never existed
before. Both defect classes are unrepresentable here: the edit
vocabulary is "replace this exact numeric token with this exact numeric
token" — spans come from the numeric validator's own adjacency regexes,
and replacements come from the persisted observed_value.

Fail-closed with typed reasons at every step; no repair-side LLM call;
no retry loop; no heading or marker mutation.
"""
from __future__ import annotations

import re

# The span vocabulary IS the validator's adjacency grammar: a number
# rendered immediately before a [RESULT-N] marker (optionally with % or
# markdown emphasis between) or immediately after it (optionally with an
# of/=/: joiner). Reusing the validator's compiled patterns guarantees
# the patcher can only touch tokens the authoritative check actually
# reads — no parallel re-implementation that could drift.
from backend.pipeline.evaluation.claim_result_validator import (
    _NUM_AFTER_RE,
    _NUM_BEFORE_RE,
)

# Same tolerance as the validator: exact decimal agreement and nothing
# more (unmodeled unit/scale transforms stay rejected).
_VALUE_TOLERANCE = 1e-6

_MARKER_TOKEN_RE = re.compile(r"\[(RESULT|SOURCE)-(\d+)\]")


class PatchApplicationError(RuntimeError):
    """A patch manifest failed deterministic application — typed, fail-closed.

    Never retried: the caller persists the failure reason and returns a
    blocked candidate. ``kind`` is one of the frozen typed reasons
    (patch_overlap, patch_span_drift, patch_value_invalid).
    """

    def __init__(self, kind: str, detail: str) -> None:
        self.kind = kind
        self.detail = detail
        super().__init__(f"{kind}: {detail}")


def render_persisted_value(value) -> str:
    """Render a persisted observed_value as text the validator accepts.

    Uses Python's shortest round-trip float representation, so
    ``float(render_persisted_value(v)) == float(v)`` exactly — agreement
    within the 1e-6 tolerance holds by construction, never by luck.
    """
    number = float(value)
    text = repr(number)
    if float(text) != number:  # pragma: no cover — repr() round-trips
        raise PatchApplicationError(
            "patch_value_invalid", f"non-round-trip rendering for {value!r}"
        )
    return text


def derive_numeric_patch_manifest(paper_md: str, result_markers: list) -> tuple[dict, ...]:
    """Derive the authorized patch manifest from persisted RESULT evidence.

    Every numeric token rendered adjacent to a registered marker whose
    float value disagrees with the marker's persisted observed_value
    beyond the validator tolerance yields one patch: the exact token
    span, the defective rendering, and the persisted replacement. Tokens
    that already agree are left untouched (preservation), and multiple
    defective renderings of one marker each get their own patch.
    """
    by_bracket = {f"[{m.marker}]": m for m in (result_markers or [])}
    patches: list[dict] = []

    def _consider(num_match: re.Match, bracket: str) -> None:
        marker = by_bracket.get(bracket)
        if marker is None:
            return
        old_text = num_match.group("num")
        try:
            rendered = float(old_text)
        except ValueError:
            return
        if abs(rendered - float(marker.observed_value)) <= _VALUE_TOLERANCE:
            return
        patches.append({
            "marker": bracket,
            "span_start": num_match.start("num"),
            "span_end": num_match.end("num"),
            "old_text": old_text,
            "new_text": render_persisted_value(marker.observed_value),
            "required_value": float(marker.observed_value),
            "metric_name": marker.metric_name,
            "artifact_sha256": getattr(marker, "artifact_sha256", "") or "",
            "basis": "persisted observed_value",
        })

    for match in _NUM_BEFORE_RE.finditer(paper_md):
        bracket = re.search(r"\[RESULT-\d+\]", match.group(0)).group(0)
        _consider(match, bracket)
    for match in _NUM_AFTER_RE.finditer(paper_md):
        bracket = re.match(r"\[RESULT-\d+\]", match.group(0)).group(0)
        _consider(match, bracket)

    return tuple(sorted(patches, key=lambda p: p["span_start"]))


def apply_numeric_patches(paper_md: str, manifest: tuple[dict, ...]) -> str:
    """Apply the manifest deterministically or raise — never partially.

    Validates every patch first (typed ``PatchApplicationError``), then
    applies right-to-left. Byte identity outside the authorized spans is
    structural: only the listed spans are rewritten.
    """
    patches = sorted(manifest, key=lambda p: p["span_start"])
    previous_end = -1
    for patch in patches:
        start, end = patch["span_start"], patch["span_end"]
        if start < 0 or end > len(paper_md) or start >= end:
            raise PatchApplicationError(
                "patch_span_drift",
                f"out-of-range span {start}:{end} for {patch['marker']}",
            )
        if start < previous_end:
            raise PatchApplicationError(
                "patch_overlap",
                f"span {start}:{end} for {patch['marker']} overlaps a prior patch",
            )
        if paper_md[start:end] != patch["old_text"]:
            raise PatchApplicationError(
                "patch_span_drift",
                f"source bytes at {start}:{end} are {paper_md[start:end]!r},"
                f" manifest expected {patch['old_text']!r}",
            )
        try:
            rendered = float(patch["new_text"])
        except ValueError as exc:
            raise PatchApplicationError(
                "patch_value_invalid",
                f"replacement {patch['new_text']!r} is not numeric",
            ) from exc
        if abs(rendered - float(patch["required_value"])) > _VALUE_TOLERANCE:
            raise PatchApplicationError(
                "patch_value_invalid",
                f"replacement {patch['new_text']!r} does not resolve to the"
                f" persisted value {patch['required_value']!r}",
            )
        previous_end = end

    revised = paper_md
    for patch in reversed(patches):
        revised = (
            revised[: patch["span_start"]]
            + patch["new_text"]
            + revised[patch["span_end"]:]
        )
    return revised


def verify_patch_postconditions(
    original: str, revised: str, manifest: tuple[dict, ...],
) -> list[str]:
    """Prove the structural preservation contract; return typed violations.

    Checks, in order: reconstruction (applying the manifest to the
    original reproduces the candidate — byte identity outside authorized
    spans), section structure (identical heading sequence), and marker
    identity (identical RESULT/SOURCE token multiset). An empty list
    means every postcondition holds.
    """
    violations: list[str] = []
    try:
        reconstructed = apply_numeric_patches(original, manifest)
        if reconstructed != revised:
            violations.append("reconstruction_mismatch")
    except PatchApplicationError as exc:
        violations.append(f"reconstruction_mismatch: {exc}")

    from backend.pipeline.evaluation.paper_sections import parse_paper

    before = parse_paper(original)
    after = parse_paper(revised)
    if [s.name for s in before.sections] != [s.name for s in after.sections] or (
        [s.heading for s in before.sections] != [s.heading for s in after.sections]
    ):
        violations.append("structural_change: section sequence differs")

    if _marker_multiset(original) != _marker_multiset(revised):
        violations.append("marker_identity_change: RESULT/SOURCE tokens differ")
    return violations


def _marker_multiset(paper_md: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for match in _MARKER_TOKEN_RE.finditer(paper_md):
        token = match.group(0)
        counts[token] = counts.get(token, 0) + 1
    return counts


def gate_regressions(gates_before: list[dict], gates_after: list[dict]) -> list[str]:
    """Every gate green before repair must still be green after (P4).

    Handles both gate shapes: boolean ``passed`` and classification
    gates (scope_alignment / conclusion_support) where the green values
    are ``on_scope`` / ``supported_by_paper``. Returns a typed
    ``preservation_violation:<gate>`` entry per regression.
    """
    green_values = {"on_scope", "supported_by_paper"}

    def _is_green(gate: dict) -> bool:
        if "passed" in gate:
            return bool(gate["passed"])
        return gate.get("classification") in green_values

    after_by_name = {g.get("gate"): g for g in (gates_after or [])}
    regressions = []
    for gate in gates_before or []:
        name = gate.get("gate")
        counterpart = after_by_name.get(name)
        if counterpart is None:
            regressions.append(f"preservation_violation:{name}:gate_missing_after")
        elif _is_green(gate) and not _is_green(counterpart):
            regressions.append(f"preservation_violation:{name}")
    return regressions


# ── Productive-1 R6: deterministic R-REMOVE targeting ────────────────
#
# Frozen charter semantics: for an unmapped empirical assertion (per the
# canonical shared conclusion-support rule), one R-REMOVE patch may cover
# EXACTLY the complete sentence containing the matched assertion. The
# sentence must contain no RESULT/SOURCE marker; boundaries follow the
# decimal-aware deterministic rule (digit.digit never terminates a
# sentence; a terminal period followed by whitespace/end-of-text may);
# spans derive against the original revision and must not overlap
# numeric patches. Anything ambiguous fails closed with a typed reason.
# No paraphrasing, no weakening, no citation — removal only.

_MARKER_ANY_RE = re.compile(r"\[(RESULT|SOURCE)-\d+\]")
_WS_RUN_RE = re.compile(r"\s+")


class ConclusionRemovalError(RuntimeError):
    """Typed fail-closed R-REMOVE derivation/application failure."""

    def __init__(self, kind: str, detail: str) -> None:
        self.kind = kind
        self.detail = detail
        super().__init__(f"{kind}: {detail}")


def split_sentences_decimal_aware(text: str) -> list[tuple[int, int, str]]:
    """Split into sentence spans under the frozen deterministic rule.

    A terminator (``.``, ``!``, ``?``) ends a sentence only when it is
    followed by whitespace or end-of-text, and — for ``.`` — when it is
    NOT a decimal point (a digit on both sides). Newlines count as
    whitespace. Non-terminating periods keep the sentence intact.
    """
    spans: list[tuple[int, int, str]] = []
    start = 0
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch in ".!?":
            is_decimal = (
                ch == "."
                and i > 0
                and i + 1 < n
                and text[i - 1].isdigit()
                and text[i + 1].isdigit()
            )
            followed_by_ws = (i + 1 >= n) or text[i + 1].isspace()
            if not is_decimal and followed_by_ws:
                sentence = text[start:i + 1]
                if sentence.strip():
                    spans.append((start, i + 1, sentence))
                start = i + 1
        i += 1
    if start < n and text[start:].strip():
        spans.append((start, n, text[start:]))
    return spans


def _normalized(text: str) -> str:
    return _WS_RUN_RE.sub(" ", text).strip()


def derive_conclusion_removal_patches(
    paper_md: str, assessment,
) -> tuple[tuple[dict, ...], list[str]]:
    """Derive R-REMOVE patches for the assessment's unmapped claims.

    Returns (patches, typed_errors). Any error means NO patches — the
    caller fails closed; there is never a partial removal set.
    """
    import hashlib

    if not assessment.unmapped_claims:
        return ((), [])

    joined = assessment.joined_text
    joined_sentences = [
        (s, e, t) for s, e, t in split_sentences_decimal_aware(joined)
    ]
    original_sentences = split_sentences_decimal_aware(paper_md)

    patches: list[dict] = []
    errors: list[str] = []
    for claim in assessment.unmapped_claims:
        # 1. The claim's containing sentence in the canonical joined text.
        containing = [
            t for s, e, t in joined_sentences if s <= claim.start and claim.end <= e
        ]
        if len(containing) != 1:
            errors.append(
                "conclusion_sentence_ambiguous: "
                f"claim '{claim.label}' does not sit in exactly one joined-text "
                f"sentence (found {len(containing)})"
            )
            continue
        target_normalized = _normalized(containing[0])

        # 2. Unique match of that sentence's content in the original bytes.
        matches = [
            (s, e)
            for s, e, t in original_sentences
            if _normalized(t) == target_normalized
        ]
        if len(matches) != 1:
            errors.append(
                "conclusion_sentence_ambiguous: "
                f"sentence for claim '{claim.label}' matches {len(matches)} "
                "original spans (must be exactly 1)"
            )
            continue
        span_start, span_end = matches[0]
        sentence_text = paper_md[span_start:span_end]

        # 3. Marker-bearing sentences are never removable.
        if _MARKER_ANY_RE.search(sentence_text):
            errors.append(
                "conclusion_sentence_marker_bearing: "
                f"sentence for claim '{claim.label}' contains a RESULT/SOURCE marker"
            )
            continue

        patches.append({
            "type": "conclusion_removal",
            "span_start": span_start,
            "span_end": span_end,
            "old_text": sentence_text,
            "new_text": "",
            "matched_pattern": claim.label,
            "sentence_sha256": hashlib.sha256(sentence_text.encode()).hexdigest(),
            "pre_classification": assessment.classification,
        })

    if errors:
        return ((), errors)
    return (tuple(sorted(patches, key=lambda p: p["span_start"])), [])


def apply_combined_patches(
    paper_md: str,
    numeric_patches: tuple[dict, ...],
    removal_patches: tuple[dict, ...],
) -> str:
    """Apply numeric replacements and conclusion removals atomically.

    All spans — across both sets — are validated against the SAME
    original bytes before anything applies: disjoint, in-bounds, and
    byte-identical ``old_text``. Numeric replacements additionally keep
    their lexical-resolution check. Any violation raises typed and
    leaves the original untouched (this function is pure).
    """
    all_patches = sorted(
        [(p, "numeric") for p in numeric_patches]
        + [(p, "removal") for p in removal_patches],
        key=lambda pair: pair[0]["span_start"],
    )
    previous_end = -1
    for patch, kind in all_patches:
        start, end = patch["span_start"], patch["span_end"]
        if start < 0 or end > len(paper_md) or start >= end:
            raise PatchApplicationError(
                "patch_span_drift",
                f"out-of-range span {start}:{end} ({kind} patch)",
            )
        if start < previous_end:
            raise PatchApplicationError(
                "patch_overlap",
                f"{kind} span {start}:{end} overlaps a prior patch",
            )
        if paper_md[start:end] != patch["old_text"]:
            raise PatchApplicationError(
                "patch_span_drift",
                f"source bytes at {start}:{end} ({kind}) are "
                f"{paper_md[start:end]!r}, manifest expected {patch['old_text']!r}",
            )
        if kind == "numeric":
            try:
                rendered = float(patch["new_text"])
            except ValueError as exc:
                raise PatchApplicationError(
                    "patch_value_invalid",
                    f"replacement {patch['new_text']!r} is not numeric",
                ) from exc
            if abs(rendered - float(patch["required_value"])) > _VALUE_TOLERANCE:
                raise PatchApplicationError(
                    "patch_value_invalid",
                    f"replacement {patch['new_text']!r} does not resolve to the"
                    f" persisted value {patch['required_value']!r}",
                )
        previous_end = end

    revised = paper_md
    for patch, _kind in reversed(all_patches):
        revised = (
            revised[: patch["span_start"]]
            + patch["new_text"]
            + revised[patch["span_end"]:]
        )
    return revised


def verify_combined_postconditions(
    original: str,
    revised: str,
    numeric_patches: tuple[dict, ...],
    removal_patches: tuple[dict, ...],
) -> list[str]:
    """Prove the R6 preservation contract over the combined repair.

    Reconstruction over the union of authorized spans, heading-sequence
    identity, and RESULT/SOURCE marker-multiset identity (R-REMOVE
    sentences are marker-free by derivation, so the multiset must be
    exactly identical). Returns typed violations; empty means clean.
    """
    violations: list[str] = []
    try:
        reconstructed = apply_combined_patches(
            original, numeric_patches, removal_patches,
        )
        if reconstructed != revised:
            violations.append("reconstruction_mismatch")
    except PatchApplicationError as exc:
        violations.append(f"reconstruction_mismatch: {exc}")

    from backend.pipeline.evaluation.paper_sections import parse_paper

    before = parse_paper(original)
    after = parse_paper(revised)
    if [s.name for s in before.sections] != [s.name for s in after.sections] or (
        [s.heading for s in before.sections] != [s.heading for s in after.sections]
    ):
        violations.append("structural_change: section sequence differs")

    if _marker_multiset(original) != _marker_multiset(revised):
        violations.append("marker_identity_change: RESULT/SOURCE tokens differ")
    return violations
