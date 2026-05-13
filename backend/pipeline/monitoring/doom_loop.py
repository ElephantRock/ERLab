"""Doom-loop detection for pipeline stages.

Ported from huggingface/ml-intern agent/core/doom_loop.py (Apache 2.0).
Adapted for Elephant Rock's pipeline stage context.

Detects when the pipeline is stuck producing identical or repeating outputs
and returns a corrective message to break the cycle.
"""

import hashlib
import json
import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StageOutputSignature:
    """Hashable signature for a single stage's output."""

    stage_name: str
    output_hash: str


def hash_stage_output(output: Any) -> str:
    """Canonicalize + hash stage output for comparison.

    Uses json.dumps with sort_keys for deterministic serialization,
    then MD5 hash truncated to 12 hex chars (same as ml-intern).
    Handles None, empty strings, and unicode correctly.
    """
    if output is None:
        return hash_stage_output("")
    if isinstance(output, str):
        canonical = output
    else:
        try:
            canonical = json.dumps(output, sort_keys=True, separators=(",", ":"))
        except (TypeError, ValueError):
            canonical = str(output)
    return hashlib.md5(canonical.encode("utf-8")).hexdigest()[:12]


def detect_identical_consecutive(
    signatures: list[StageOutputSignature], threshold: int = 3
) -> str | None:
    """Return stage name if threshold+ identical consecutive outputs found.

    Only triggers when the SAME stage produces the SAME output hash
    threshold or more times in a row.
    """
    if len(signatures) < threshold:
        return None

    count = 1
    for i in range(1, len(signatures)):
        if signatures[i] == signatures[i - 1]:
            count += 1
            if count >= threshold:
                return signatures[i].stage_name
        else:
            count = 1

    return None


def detect_repeating_sequence(
    signatures: list[StageOutputSignature],
) -> list[StageOutputSignature] | None:
    """Detect repeating patterns of length 2-5 with 2+ repetitions.

    Checks the tail of the signature list for cycles like [A,B,A,B]
    or [A,B,C,A,B,C].
    """
    n = len(signatures)
    for seq_len in range(2, 6):
        min_required = seq_len * 2
        if n < min_required:
            continue

        tail = signatures[-min_required:]
        pattern = tail[:seq_len]

        # Count repetitions from the end
        reps = 0
        for start in range(n - seq_len, -1, -seq_len):
            chunk = signatures[start : start + seq_len]
            if chunk == pattern:
                reps += 1
            else:
                break

        if reps >= 2:
            return pattern

    return None


def check_pipeline_doom(stage_history: list[dict]) -> str | None:
    """High-level check for pipeline doom loops.

    Args:
        stage_history: List of dicts with keys 'stage_name' and 'output_hash'.
                       Built by the orchestrator as stages complete.

    Returns:
        Corrective message string if doom detected, None otherwise.
    """
    if not stage_history:
        return None

    signatures = [
        StageOutputSignature(
            stage_name=entry.get("stage_name", "unknown"),
            output_hash=entry.get("output_hash", ""),
        )
        for entry in stage_history
    ]

    if len(signatures) < 3:
        return None

    # Check for identical consecutive outputs
    stage_name = detect_identical_consecutive(signatures, threshold=3)
    if stage_name:
        logger.warning(
            "Doom loop detected: 3+ identical consecutive outputs from '%s'",
            stage_name,
        )
        return (
            f"[DOOM LOOP] Stage '{stage_name}' has produced identical output "
            f"3+ times consecutively. The pipeline is stuck. "
            f"Skipping remaining optional stages."
        )

    # Check for repeating sequences
    pattern = detect_repeating_sequence(signatures)
    if pattern:
        pattern_desc = " -> ".join(s.stage_name for s in pattern)
        logger.warning(
            "Doom loop detected: repeating sequence [%s]", pattern_desc
        )
        return (
            f"[DOOM LOOP] Pipeline is stuck in a repeating cycle: "
            f"[{pattern_desc}]. Skipping remaining optional stages."
        )

    return None


def extract_stage_fingerprint(
    stage_name: str,
    gaps: list | None = None,
    ideas: list | None = None,
    proposals: list | None = None,
) -> str:
    """Extract a minimal fingerprint from stage output for hashing.

    Only gap_analysis, idea_generation, and proposal_synthesis produce
    fingerprints — these are the stages most likely to loop.
    Other stages return empty string (no doom check needed).
    """
    if stage_name == "gap_analysis" and gaps:
        titles = []
        for g in gaps:
            if isinstance(g, dict):
                titles.append(g.get("title", g.get("name", "")))
            elif hasattr(g, "title"):
                titles.append(getattr(g, "title", ""))
            elif hasattr(g, "name"):
                titles.append(getattr(g, "name", ""))
        return " | ".join(titles)

    if stage_name == "idea_generation" and ideas:
        parts = []
        for idea in ideas:
            if isinstance(idea, dict):
                title = idea.get("title", "")
                score = idea.get("novelty_score", idea.get("score", ""))
                parts.append(f"{title}:{score}")
            elif hasattr(idea, "title"):
                title = getattr(idea, "title", "")
                score = getattr(idea, "novelty_score", getattr(idea, "score", ""))
                parts.append(f"{title}:{score}")
        return " | ".join(parts)

    if stage_name == "proposal_synthesis" and proposals:
        excerpts = []
        for p in proposals:
            if isinstance(p, dict):
                content = p.get("content", p.get("methodology", ""))
            elif hasattr(p, "content"):
                content = getattr(p, "content", "")
            else:
                content = str(p)[:500]
            excerpts.append(content[:500])
        return " | ".join(excerpts)

    return ""
