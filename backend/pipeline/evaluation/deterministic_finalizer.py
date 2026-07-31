"""Phase 11 / 11B+11C — deterministic evidence-bound finalization.

Converts structured evaluator findings into exact, auditable patches.
Zero provider calls. Zero experiment reruns.

11B: canonical title builder from spec
11C: typed RESULT-claim renderer from marker semantics
11D: deterministic patch planner
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field


# ── 11B: Canonical title builder ────────────────────────────────────

def build_canonical_title(
    dataset_name: str,
    task_type: str,
    executed_method: str,
    baseline_method: str,
    primary_metric: str,
) -> str:
    """Generate a title solely from the registered experiment specification.

    The title uses dataset, task, method, baseline, and primary metric.
    It must not introduce unexecuted methods, unsupported contributions,
    novelty language, or statistical-significance language.
    """
    # Clean up method name (take the first meaningful part)
    method_short = executed_method.split("(")[0].strip().split(" vs ")[0].strip()
    if " vs " in executed_method:
        method_short = executed_method.split(" vs ")[0].strip()

    # Clean up dataset name for display
    dataset_display = dataset_name.replace("_", " ").title()
    if dataset_display.lower() == "Iris":
        dataset_display = "Iris"

    # Clean up baseline
    baseline_short = baseline_method.split("(")[0].strip()
    if "majority" in baseline_short.lower():
        baseline_short = "Majority-Class Baseline"
    elif "mean" in baseline_short.lower():
        baseline_short = "Mean Baseline"

    # Clean up metric
    metric_display = primary_metric.replace("_", " ").replace("model ", "").title()

    if task_type == "classification":
        return f"{method_short} on the {dataset_display} Dataset: {metric_display} Against a {baseline_short}"
    elif task_type == "regression":
        return f"{method_short} on the {dataset_display} Dataset: {metric_display} Compared to a {baseline_short}"
    else:
        return f"{method_short} on the {dataset_display} Dataset: {metric_display} Against a {baseline_short}"


# ── 11C: Typed RESULT-claim renderer ────────────────────────────────

def render_result_claim(
    marker: str,
    metric_id: str,
    observed_value: float,
    role: str,
    direction: str = "",
    executed_method: str = "",
    baseline_method: str = "",
    metric_unit: str = "",
) -> str:
    """Build a canonical sentence from persisted marker semantics.

    The renderer consumes metric_id, role, observed_value, direction.
    It handles baseline, comparison, derived roles and all direction types.

    No value is recalculated unless explicitly declared.
    """
    # Format the value
    if abs(observed_value) < 100:
        value_str = f"{observed_value:.6f}".rstrip("0").rstrip(".")
    else:
        value_str = f"{observed_value:.2f}"

    # Clean metric name for display
    metric_display = metric_id.replace("_", " ")

    # Method short names
    method_short = executed_method.split("(")[0].strip().split(" vs ")[0].strip() if executed_method else "the model"
    baseline_short = baseline_method.split("(")[0].strip() if baseline_method else "the baseline"

    if role == "baseline":
        return f"The predeclared {baseline_short.lower()} achieved {value_str} {metric_display} [{marker}]."

    elif role == "comparison":
        return f"The {method_short.lower()} achieved {value_str} {metric_display} [{marker}]."

    elif role == "derived":
        # Derived metrics describe improvement or difference
        if "improvement" in metric_id.lower() or "reduction" in metric_id.lower():
            if direction == "higher_better":
                return f"The observed {metric_display} was {value_str} [{marker}]."
            elif direction == "lower_better":
                return f"The observed {metric_display} was {value_str} [{marker}]."
        return f"The observed {metric_display} was {value_str} [{marker}]."

    else:
        return f"Observed {metric_display}: {value_str} [{marker}]."


def render_result_section(
    result_markers: list,  # list of ResultMarker objects
    executed_method: str = "",
    baseline_method: str = "",
) -> str:
    """Render a complete results summary from all RESULT markers.

    Produces canonical sentences for baseline, comparison, and derived markers.
    """
    lines = []

    # Separate by role
    baselines = [m for m in result_markers if getattr(m, "role", "") == "baseline"]
    comparisons = [m for m in result_markers if getattr(m, "role", "") == "comparison"]
    deriveds = [m for m in result_markers if getattr(m, "role", "") == "derived"]

    for m in baselines:
        lines.append(render_result_claim(
            marker=m.marker, metric_id=m.metric_name, observed_value=m.observed_value,
            role="baseline", executed_method=executed_method, baseline_method=baseline_method,
        ))

    for m in comparisons:
        lines.append(render_result_claim(
            marker=m.marker, metric_id=m.metric_name, observed_value=m.observed_value,
            role="comparison", direction=getattr(m, "direction", ""),
            executed_method=executed_method, baseline_method=baseline_method,
        ))

    for m in deriveds:
        lines.append(render_result_claim(
            marker=m.marker, metric_id=m.metric_name, observed_value=m.observed_value,
            role="derived", direction=getattr(m, "direction", ""),
            executed_method=executed_method, baseline_method=baseline_method,
        ))

    return "\n\n".join(lines)


# ── 11D: Deterministic patch planner ────────────────────────────────

@dataclass
class DeterministicPatch:
    """A single deterministic patch applied to a paper."""

    section: str
    span_type: str  # "title" | "claim_span"
    original_text: str
    original_hash: str
    replacement_text: str
    replacement_hash: str
    finding_resolved: str
    evidence_markers_consumed: list[str] = field(default_factory=list)


@dataclass
class PatchPlan:
    """A complete plan of deterministic patches for a paper."""

    patches: list[DeterministicPatch] = field(default_factory=list)
    rejected: list[str] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return len(self.patches) == 0


def plan_deterministic_patches(
    paper_md: str,
    findings: list,  # ClaimRepairFinding objects
    spec_method: str,
    spec_dataset: str,
    spec_baseline: str,
    spec_comparison: str,
    spec_primary_metric: str,
    spec_task_type: str,
    result_markers: list,  # ResultMarker objects
) -> PatchPlan:
    """Transform hardened gate findings into a patch plan.

    Every patch records section, original span/hash, replacement text/hash,
    finding resolved, and evidence markers consumed.
    """
    plan = PatchPlan()

    # Build the canonical title
    canonical_title = build_canonical_title(
        dataset_name=spec_dataset,
        task_type=spec_task_type,
        executed_method=spec_method,
        baseline_method=spec_baseline,
        primary_metric=spec_primary_metric,
    )

    # Check title finding
    title_match = re.match(r'^(#\s+.+)', paper_md.strip())
    if title_match:
        current_title = title_match.group(1)
        title_lower = current_title.lower()

        # Detect if title contains unexecuted methods
        unexecuted_in_title = any(
            re.search(p, title_lower)
            for p in [r'\bquantum\b', r'\bgnn\b', r'\bpinn\b', r'\bwavelet\b']
        )

        if unexecuted_in_title:
            new_title = f"# {canonical_title}"
            plan.patches.append(DeterministicPatch(
                section="title",
                span_type="title",
                original_text=current_title,
                original_hash=hashlib.sha256(current_title.encode()).hexdigest(),
                replacement_text=new_title,
                replacement_hash=hashlib.sha256(new_title.encode()).hexdigest(),
                finding_resolved="incorrect_central_method in title",
            ))

    # Check claim-result mismatches
    from backend.pipeline.evaluation.claim_result_validator import validate_claim_result_alignment
    mismatches = validate_claim_result_alignment(paper_md, result_markers)

    for mismatch in mismatches:
        # Find the exact claim span containing this marker
        marker = mismatch.marker
        marker_info = next(
            (m for m in result_markers if f"[{m.marker}]" == marker),
            None
        )
        if not marker_info:
            plan.rejected.append(f"Cannot resolve {marker} for patch")
            continue

        # Find the correct comparison marker for this metric type
        # If the claim is about the model but cites a baseline marker,
        # replace with the correct comparison marker
        correct_marker = next(
            (m for m in result_markers
             if getattr(m, "role", "") == "comparison"
             and getattr(m, "metric_name", "") == marker_info.metric_name.replace("baseline_", "model_")),
            None
        )

        if not correct_marker:
            # Try to find any comparison marker
            correct_marker = next(
                (m for m in result_markers if getattr(m, "role", "") == "comparison"),
                None
            )

        if correct_marker:
            # Build the canonical replacement sentence
            replacement = render_result_claim(
                marker=correct_marker.marker,
                metric_id=correct_marker.metric_name,
                observed_value=correct_marker.observed_value,
                role="comparison",
                direction=getattr(correct_marker, "direction", ""),
                executed_method=spec_method,
                baseline_method=spec_baseline,
            )

            # Find the original span containing the wrong marker
            # We need to find the sentence containing the mismatch marker
            # and replace it
            marker_bracket = f"[{marker_info.marker}]"
            # Find the sentence containing this marker
            sentences = re.split(r'(?<=[.!?])\s+', paper_md)
            target_sentence = None
            for s in sentences:
                if marker_bracket in s and mismatch.claimed_subject == "model":
                    target_sentence = s.strip()
                    break

            if target_sentence:
                # Only replace the sentence, not the heading it may contain
                # The target_sentence might include "## Conclusion\n" prefix
                clean_sentence = target_sentence
                heading_prefix = ""
                heading_match = re.match(r'^(#{1,3}\s+\w+\s*\n)', target_sentence)
                if heading_match:
                    heading_prefix = heading_match.group(1)
                    clean_sentence = target_sentence[len(heading_prefix):].strip()

                plan.patches.append(DeterministicPatch(
                    section="conclusion",
                    span_type="claim_span",
                    original_text=clean_sentence,
                    original_hash=hashlib.sha256(target_sentence.encode()).hexdigest(),
                    replacement_text=replacement,
                    replacement_hash=hashlib.sha256(replacement.encode()).hexdigest(),
                    finding_resolved=f"baseline marker {marker} credited to model — replaced with {correct_marker.marker}",
                    evidence_markers_consumed=[correct_marker.marker],
                ))
            else:
                # Ambiguous: multiple sentences or not found
                plan.rejected.append(f"Could not find exact span for {marker} mismatch")

    return plan


def apply_patches(paper_md: str, plan: PatchPlan) -> str:
    """Apply deterministic patches to a paper.

    Unchanged sections must remain byte-identical.
    Rejects when the original span no longer matches.
    """
    result = paper_md

    for patch in plan.patches:
        if patch.span_type == "title":
            # Replace the title line
            result = re.sub(
                r'^#\s+.+',
                patch.replacement_text,
                result,
                count=1,
            )
        elif patch.span_type == "claim_span":
            # Replace the exact claim span
            if patch.original_text in result:
                result = result.replace(patch.original_text, patch.replacement_text, 1)
            else:
                # Original span no longer matches — fail closed
                raise ValueError(
                    f"Original span no longer matches for patch: {patch.finding_resolved}"
                )

    return result
