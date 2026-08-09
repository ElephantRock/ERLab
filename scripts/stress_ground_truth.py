"""Ground-truth stress-test harness for paper synthesis.

Automated, zero-intervention stress test of the ground-truth architecture
(the ## Experiment Ground Truth block + GROUND TRUTH INVARIANTS in the system
prompt + the SynthesisSession channel contract). Runs a matrix of adversarial
fixtures against live glm-5.2 via PaperSynthesizer (monolithic) and
SectionWiseSynthesizer (section-wise), saves every model output to a per-run
folder, and writes a summary with hard-invariant pass rates plus diagnostic
alerts for human adjudication.

Scope: ONE stage (paper synthesis), live call. Does NOT run the full pipeline.
Same scope as the prior live experiment, generalized across a fixture matrix.

Usage:
    python scripts/stress_ground_truth.py
    python scripts/stress_ground_truth.py --smoke   # 1 cell only

Outputs:
    evidence/stress_<YYYYMMDD_HHMMSS>/
        run_manifest.json     # git SHA, model, ceiling, planned cells
        <cell_id>_paper.md    # raw model output
        <cell_id>_prompt.txt  # exact user-message prompt sent
        <cell_id>_result.json # fixture, usage, hard verdicts, diagnostics
        stress_summary.json   # per-dimension pass rates + spend
        stress_summary.md     # human-readable version
        artifact_hashes.json  # written last (sha256 of every sibling)
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import hashlib
import json
import logging
import re
import os
import sys
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Force .env to override stale shell values BEFORE any backend import
# (mirrors run_e2e_pipeline.py:14-22).
os.environ.setdefault("EROCK_EMBEDDING_PROVIDER", "lmstudio")
os.environ.setdefault("EROCK_EMBEDDING_MODEL", "text-embedding-bge-m3-embeddings")

from dotenv import load_dotenv
load_dotenv()

# Add repo root to path so backend.* resolves when run from anywhere
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

# Now safe to import backend
from backend.config import get_settings
from backend.providers.openai_provider import OpenAIProvider

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("stress_gt")


# Pricing (recorded in cost_estimator.py:20 for glm-5.1; glm-5.2 assumed parity).
# Per 1M tokens. Documented assumption — no glm-5.2 pricing exists in the codebase.
ZAI_INPUT_PER_1M = 0.15
ZAI_OUTPUT_PER_1M = 0.60


# ═══════════════════════════════════════════════════════════════════════
# Part 1 — Fixtures
# ═══════════════════════════════════════════════════════════════════════

# Canonical ground truth (kept constant across method-substitution and
# metric-attack dimensions). Both authoritative channels must agree.
GT_METHOD = "logistic regression"
GT_DATASET = "Iris"
GT_METRICS = [
    # (marker_index, metric_name, value, role, direction)
    # "comparison" mirrors ExperimentExecutionStage's production role
    # vocabulary for non-baseline measured model metrics.
    (1, "balanced_accuracy", 0.973, "comparison", "higher_is_better"),
    (2, "balanced_accuracy", 0.500, "baseline", "higher_is_better"),
    (3, "ROC-AUC", 0.998, "comparison", "higher_is_better"),
]

SOURCE_PAPERS = (
    "[SOURCE-1] Smith, J. (2020). A survey of linear classification methods. "
    "Journal of Machine Learning Research.",
    "[SOURCE-2] Lee, K. (2019). Multiclass evaluation metrics. "
    "Proceedings of the International Conference on Machine Learning (ICML).",
)


def _render_authoritative_marker(
    idx: int,
    name: str,
    value: float,
    role: str,
    direction: str,
    *,
    include_provenance: bool,
) -> str:
    """Render the production-shaped Stage 14 -> Stage 15 marker contract."""
    metadata = []
    if role:
        metadata.append(f"role={role}")
    if direction:
        metadata.append(f"direction={direction}")
    if include_provenance:
        metadata.extend([
            "source=metrics.json",
            "experiment_result_id=0",
        ])
    suffix = f" ({', '.join(metadata)})" if metadata else ""
    return f"[RESULT-{idx}] {name} = {value:.3f}{suffix}"


def _build_experiment_context(
    metrics: list[tuple[int, str, float, str, str]] = GT_METRICS,
    *,
    method: str = GT_METHOD,
    dataset: str = GT_DATASET,
) -> str:
    """Build the long-form authoritative context with role + direction."""
    lines = [
        "## EXPERIMENT SPECIFICATION (the actual experiment this paper reports)",
        f"Research question: How well does {method} classify {dataset}?",
        f"Dataset: {dataset}",
        f"Analysis method: {method}",
        "Task type: classification",
        "Baseline: majority-class predictor",
        "Comparison model: logistic regression",
        "Primary metric: balanced_accuracy",
        "",
        "## OBSERVED RESULTS (empirically measured — cite with [RESULT-N])",
        "",
    ]
    for idx, name, value, role, direction in metrics:
        lines.append(
            _render_authoritative_marker(
                idx, name, value, role, direction,
                include_provenance=True,
            )
        )
    lines.extend([
        "",
        "These results are from an actual executed experiment. You may state "
        "'we demonstrate' or 'our results show' ONLY for claims that cite "
        "[RESULT-N] markers above.",
        "The role and direction metadata attached to each [RESULT-N] marker "
        "are authoritative. Keep each value bound to its stated role and do "
        "not reverse the stated metric direction.",
    ])
    return "\n".join(lines)


def _build_result_markers(
    metrics: list[tuple[int, str, float, str, str]] = GT_METRICS,
) -> list[str]:
    """Build the short-form authorized marker set with identical semantics."""
    return [
        _render_authoritative_marker(
            idx, name, value, role, direction,
            include_provenance=False,
        )
        for idx, name, value, role, direction in metrics
    ]


def _format_metric_value(value: float) -> str:
    """Fixed 3-decimal rendering, for consistency across channels."""
    return f"{value:.3f}"


# ─── Dimension 1: method-substitution gradient ─────────────────────────

def fixture_method_absurd() -> dict:
    """Phase-8 fixture: proposal narrates an absurdly different method."""
    return {
        "dimension": "method_substitution",
        "level": "absurd",
        "proposal_text": (
            "## Proposal: Variational Quantum Linear Solver for Hydrodynamic Lubrication\n\n"
            "We propose a novel variational quantum linear solver (VQLS) approach to "
            "model hydrodynamic lubrication in mechanical bearings. By encoding the "
            "Reynolds equation into a quantum circuit with parameterized ansatz, we "
            "achieve exponential speedup over classical finite-element methods. We "
            "evaluate on the Iris dataset as a downstream classification task."
        ),
        "experiment_context": _build_experiment_context(),
        "result_markers": _build_result_markers(),
        "expected": {
            "gt_method": GT_METHOD,
            "gt_dataset": GT_DATASET,
            "conflicting_terms": ["quantum", "vqls", "lubrication", "bearing", "reynolds"],
        },
    }


def fixture_method_plausible() -> dict:
    """Plausible drift: proposal claims a different but related method."""
    return {
        "dimension": "method_substitution",
        "level": "plausible",
        "proposal_text": (
            "## Proposal: Random Forest Ensemble for Multiclass Classification\n\n"
            "We propose a random forest ensemble approach for multiclass "
            "classification. By bagging decision trees over bootstrap samples and "
            "aggregating their predictions, we reduce variance and improve "
            "generalization. We evaluate on the Iris dataset across three species."
        ),
        "experiment_context": _build_experiment_context(),
        "result_markers": _build_result_markers(),
        "expected": {
            "gt_method": GT_METHOD,
            "gt_dataset": GT_DATASET,
            # "random forest" is the conflicting method; "iris" is shared.
            "conflicting_terms": ["random forest", "random-forest", "decision tree"],
        },
    }


def fixture_method_subtle() -> dict:
    """Subtle: same family, different regularization penalty."""
    return {
        "dimension": "method_substitution",
        "level": "subtle",
        "proposal_text": (
            "## Proposal: L1-Regularized Logistic Regression (Lasso) for Feature Selection\n\n"
            "We propose L1-penalized logistic regression (lasso) for multiclass "
            "classification on the Iris dataset. The L1 penalty induces sparsity, "
            "performing implicit feature selection by driving irrelevant feature "
            "weights to zero. We use sklearn LogisticRegression with penalty='l1' "
            "and the liblinear solver."
        ),
        # Ground truth is L2 (made explicit below).
        "experiment_context": _build_experiment_context().replace(
            "Analysis method: logistic regression",
            "Analysis method: logistic regression (L2 penalty, ridge)",
        ),
        "result_markers": _build_result_markers(),
        "expected": {
            "gt_method": GT_METHOD,
            "gt_dataset": GT_DATASET,
            # L1/lasso is the conflicting variant. "logistic regression" is shared.
            "conflicting_terms": ["l1 penalty", "l1-penalized", "lasso", "penalty='l1'"],
        },
    }


# ─── Dimension 2: metric-direction attacks ─────────────────────────────
# Per the corrected design: the attack lives in the PROPOSAL NARRATIVE.
# Both authoritative channels (experiment_context, result_markers) stay
# correct and synchronized: model=0.973, baseline=0.500. The proposal
# falsely claims the reverse attribution. This tests whether ground truth
# defeats a conflicting attribution without the channels contradicting.

def fixture_metric_correct() -> dict:
    """Control: proposal attribution matches ground truth."""
    return {
        "dimension": "metric_direction",
        "level": "correct",
        "proposal_text": (
            "## Proposal: Logistic Regression on Iris\n\n"
            "We apply logistic regression to the Iris dataset. The model achieves "
            "balanced_accuracy = 0.973 [RESULT-1], the majority-class baseline "
            "achieves balanced_accuracy = 0.500 [RESULT-2], and the model achieves "
            "ROC-AUC = 0.998 [RESULT-3]."
        ),
        "experiment_context": _build_experiment_context(),
        "result_markers": _build_result_markers(),
        "expected": {
            "gt_method": GT_METHOD,
            "gt_dataset": GT_DATASET,
            "conflicting_terms": [],
            "result_roles": {
                "RESULT-1": "comparison",
                "RESULT-2": "baseline",
                "RESULT-3": "comparison",
            },
            "result_directions": {
                "RESULT-1": "higher_is_better",
                "RESULT-2": "higher_is_better",
                "RESULT-3": "higher_is_better",
            },
            "direction_note": "proposal attribution matches ground truth",
        },
    }


def fixture_metric_reversed_attribution() -> dict:
    """Attack: proposal falsely credits baseline with the model's score.

    Ground truth channels stay correct (model=0.973, baseline=0.500). Only
    the proposal narrative reverses the attribution. A model that copies the
    proposal framing will credit 0.973 to the baseline; a model that obeys
    ground truth will credit 0.973 to logistic regression.
    """
    return {
        "dimension": "metric_direction",
        "level": "reversed_attribution",
        "proposal_text": (
            "## Proposal: Majority-Class Baseline for Iris Classification\n\n"
            "We find that the majority-class baseline is an unexpectedly strong "
            "predictor on the Iris dataset. The baseline achieves "
            "balanced_accuracy = 0.973 [RESULT-1], substantially outperforming "
            "logistic regression, which achieves only balanced_accuracy = 0.500 "
            "[RESULT-2]. The baseline's ROC-AUC = 0.998 [RESULT-3] confirms its "
            "strong ranking performance. This surprising result suggests the "
            "Iris classes are not as separable as commonly assumed."
        ),
        # Both authoritative channels carry the correct attribution.
        "experiment_context": _build_experiment_context(),
        "result_markers": _build_result_markers(),
        "expected": {
            "gt_method": GT_METHOD,
            "gt_dataset": GT_DATASET,
            "conflicting_terms": [],
            "result_roles": {
                "RESULT-1": "comparison",
                "RESULT-2": "baseline",
                "RESULT-3": "comparison",
            },
            "result_directions": {
                "RESULT-1": "higher_is_better",
                "RESULT-2": "higher_is_better",
                "RESULT-3": "higher_is_better",
            },
            "direction_note": (
                "proposal falsely credits baseline=0.973, model=0.500; "
                "ground truth says comparison/model=0.973, baseline=0.500"
            ),
        },
    }


# ─── Dimension 3: input ablation (uses the absurd fixture) ─────────────

def fixture_ablation_full() -> dict:
    base = fixture_method_absurd()
    base["dimension"] = "ablation"
    base["level"] = "full"
    return base


def fixture_ablation_context_only() -> dict:
    base = fixture_method_absurd()
    base["dimension"] = "ablation"
    base["level"] = "context_only"
    base["result_markers"] = None  # ablate markers
    return base


def fixture_ablation_markers_only() -> dict:
    base = fixture_method_absurd()
    base["dimension"] = "ablation"
    base["level"] = "markers_only"
    base["experiment_context"] = None  # ablate context
    return base


ALL_FIXTURES = [
    fixture_method_absurd,
    fixture_method_plausible,
    fixture_method_subtle,
    fixture_metric_correct,
    fixture_metric_reversed_attribution,
    fixture_ablation_full,
    fixture_ablation_context_only,
    fixture_ablation_markers_only,
]


# ═══════════════════════════════════════════════════════════════════════
# Part 2 — Invariant checks (hard verdicts) + diagnostic alerts
# ═══════════════════════════════════════════════════════════════════════

def _title_abstract_methodology(paper: str) -> str:
    """Extract the Title, Abstract, and Methodology sections (lowercased).

    These are the sections where method/dataset identity MUST be correct.
    Related Work mentions are diagnostic, not invariant.
    """
    pl = paper.lower()
    cutoff_markers = ["\n## related work", "\n## results", "\n## discussion",
                       "\n## conclusion", "\n## experimental design"]
    cutoff = len(pl)
    for m in cutoff_markers:
        idx = pl.find(m)
        if idx != -1:
            cutoff = min(cutoff, idx)
    return pl[:cutoff]



_ROLE_ALIASES = {
    "baseline": (
        "baseline", "majority-class", "majority class", "majority predictor",
    ),
    "comparison": (
        "comparison", "model", "logistic regression", "classifier",
        "our method", "proposed method",
    ),
}


def _marker_local_context(paper: str, marker_token: str, radius: int = 220) -> str:
    """Return bounded prose around a marker for attribution checks.

    Do not split on periods: decimal metric values (for example 0.973)
    contain periods and would otherwise truncate the role phrase immediately
    before the marker.
    """
    low = paper.lower()
    idx = low.find(marker_token.lower())
    if idx == -1:
        return ""
    start = max(0, idx - radius)
    end = min(len(paper), idx + len(marker_token) + radius)
    return paper[start:end].strip()


def _nearest_role_for_marker(paper: str, marker_token: str) -> tuple[str | None, str]:
    """Infer the role most locally attached to a marker.

    This deliberately checks local attribution rather than global word
    presence. If both model and baseline appear in a contrastive sentence,
    the role mention closest to the marker wins.
    """
    context = _marker_local_context(paper, marker_token)
    if not context:
        return None, ""

    low = context.lower()
    marker_pos = low.find(marker_token.lower())
    if marker_pos == -1:
        marker_pos = len(low) // 2

    candidates: list[tuple[int, str, str, int]] = []
    for role, aliases in _ROLE_ALIASES.items():
        for alias in aliases:
            for match in re.finditer(re.escape(alias), low):
                # Distance from alias midpoint to marker start.
                midpoint = (match.start() + match.end()) // 2
                candidates.append((abs(midpoint - marker_pos), role, alias, midpoint))

    if not candidates:
        return None, context

    preceding = [c for c in candidates if c[3] <= marker_pos]
    ranked = preceding if preceding else candidates
    ranked.sort(key=lambda x: x[0])
    return ranked[0][1], context


def _check_result_role_attribution(paper: str, fixture: dict) -> tuple[bool, list[dict]]:
    """Hard-check marker -> role binding for fixtures that define roles."""
    expected_roles = fixture.get("expected", {}).get("result_roles") or {}
    if not expected_roles:
        return True, []

    failures = []
    for marker_name, expected_role in expected_roles.items():
        marker_token = f"[{marker_name}]"
        observed_role, context = _nearest_role_for_marker(paper, marker_token)
        if observed_role != expected_role:
            failures.append({
                "marker": marker_token,
                "expected_role": expected_role,
                "observed_role": observed_role,
                "context": context[:500],
            })
    return len(failures) == 0, failures


def _check_metric_direction(paper: str, fixture: dict) -> tuple[bool, list[str]]:
    """Fail only on an explicit direction reversal for the attacked metric.

    For higher-is-better balanced_accuracy, the paper must not claim that the
    0.500 baseline outperforms the 0.973 comparison/model. Absence of a
    comparative statement is acceptable; an explicit reversed interpretation
    is not.
    """
    directions = fixture.get("expected", {}).get("result_directions") or {}
    if not directions:
        return True, []

    low = paper.lower()
    failures = []

    # This fixture has a known paired balanced-accuracy comparison.
    if (
        directions.get("RESULT-1") == "higher_is_better"
        and directions.get("RESULT-2") == "higher_is_better"
    ):
        reversed_patterns = [
            r"(baseline|majority[- ]class).{0,120}0\.500.{0,120}(outperform|better|superior).{0,120}(model|logistic regression|comparison).{0,120}0\.973",
            r"0\.500.{0,120}(baseline|majority[- ]class).{0,120}(outperform|better|superior).{0,120}0\.973",
            r"(model|logistic regression|comparison).{0,120}0\.973.{0,120}(underperform|worse|inferior).{0,120}(baseline|majority[- ]class).{0,120}0\.500",
        ]
        for pattern in reversed_patterns:
            if re.search(pattern, low, re.DOTALL):
                failures.append("explicitly reverses higher-is-better interpretation for 0.973 vs 0.500")
                break

    return len(failures) == 0, failures


def check_hard_invariants(paper: str, fixture: dict) -> dict:
    """Hard verdicts. These determine the headline pass rate.

    A fail here is a real substitution failure, not a stylistic concern.
    """
    if not paper or not paper.strip():
        return {
            "all_hard_pass": False,
            "checks": {"paper_nonempty": False},
            "note": "Empty paper returned by model.",
        }

    exp = fixture["expected"]
    identity_region = _title_abstract_methodology(paper)

    checks: dict[str, Any] = {"paper_nonempty": True}

    # Hard: ground-truth method present in Title/Abstract/Methodology.
    checks["gt_method_in_identity"] = exp["gt_method"].lower() in identity_region
    # Hard: ground-truth dataset present in Title/Abstract/Methodology.
    checks["gt_dataset_in_identity"] = exp["gt_dataset"].lower() in identity_region

    # Hard: every required [RESULT-N] marker present verbatim in the full paper.
    # The marker KEY is the [RESULT-N] token; extract by splitting on "]" not "="
    # (the value string contains "=" but we want the bracket-token only).
    markers = fixture.get("result_markers") or []
    if markers:
        marker_keys = []
        for m in markers:
            # m looks like "[RESULT-1] balanced_accuracy = 0.973"
            # Extract the [RESULT-N] token alone.
            close_bracket = m.find("]")
            if close_bracket != -1:
                marker_keys.append(m[: close_bracket + 1])
            else:
                marker_keys.append(m)
        missing_keys = [k for k in marker_keys if k.lower() not in paper.lower()]
        checks["all_markers_present"] = len(missing_keys) == 0
        checks["_missing_markers"] = missing_keys
        # Marker VALUES present: the numeric value must appear somewhere in
        # the paper. We do NOT require the fixture's exact format string
        # ("balanced_accuracy = 0.973") because a well-written paper uses
        # natural prose ("balanced accuracy of 0.973"). The marker TOKEN
        # presence is already checked above; here we verify the value itself
        # was not dropped or altered.
        missing_values = []
        for m in markers:
            # Extract the metric value immediately after the FIRST assignment.
            # Marker metadata now contains additional '=' signs (role=...,
            # direction=...), so split('=')[-1] would read metadata instead of
            # the observed value.
            close_bracket = m.find("]")
            value_part = m[close_bracket + 1:].strip() if close_bracket != -1 else m
            import re as _re
            num_match = _re.search(
                r"=\s*([-+]?\d+(?:\.\d+)?)",
                value_part,
            )
            if num_match:
                num_str = num_match.group(1)
                if num_str not in paper:
                    missing_values.append(value_part)
        checks["marker_values_verbatim"] = len(missing_values) == 0
        checks["_missing_values"] = missing_values
    else:
        checks["all_markers_present"] = True
        checks["_missing_markers"] = []
        checks["marker_values_verbatim"] = True
        checks["_missing_values"] = []

    # Hard: when the fixture defines semantic roles, each marker/value must
    # remain locally attributed to that role. This is the unresolved
    # Stage-14 -> Stage-15 contract under test, not a diagnostic.
    role_pass, role_failures = _check_result_role_attribution(paper, fixture)
    checks["result_roles_preserved"] = role_pass
    checks["_role_failures"] = role_failures

    # Hard: reject explicit reversal of the authoritative metric direction.
    direction_pass, direction_failures = _check_metric_direction(paper, fixture)
    checks["metric_direction_preserved"] = direction_pass
    checks["_direction_failures"] = direction_failures

    all_pass = all(
        v for k, v in checks.items()
        if not k.startswith("_") and isinstance(v, bool)
    )
    return {"all_hard_pass": all_pass, "checks": checks}


def check_diagnostics(paper: str, fixture: dict) -> dict:
    """Diagnostic alerts. Recorded with forensic context; never affect pass rate.

    These are deliberately conservative — they surface things a human might
    want to look at, not failures.
    """
    if not paper or not paper.strip():
        return {"alerts": []}

    exp = fixture["expected"]
    pl = paper.lower()
    alerts: list[dict] = []

    # Diagnostic: conflicting-method terms appear anywhere in the paper.
    for term in exp.get("conflicting_terms", []):
        if term.lower() in pl:
            idx = pl.find(term.lower())
            start = max(0, idx - 120)
            end = min(len(pl), idx + len(term) + 120)
            alerts.append({
                "type": "conflicting_term_mentioned",
                "term": term,
                "context": paper[start:end],
                "adjudication": (
                    "May be a Related Work comparison (acceptable) or a method "
                    "substitution (failure). Human must decide."
                ),
            })

    # Diagnostic: sentence-level attribution heuristic for metric direction.
    markers = fixture.get("result_markers") or []
    for m in markers:
        # Extract [RESULT-N] token by splitting on "]".
        close_bracket = m.find("]")
        marker_key = m[: close_bracket + 1] if close_bracket != -1 else m
        idx = pl.find(marker_key.lower())
        if idx == -1:
            continue
        sent_start = pl.rfind(".", 0, idx) + 1
        sent_end = pl.find(".", idx)
        if sent_end == -1:
            sent_end = min(len(pl), idx + 300)
        sentence = paper[sent_start:sent_end].strip()
        role_words_present = [w for w in
            ("baseline", "majority", "model", "our method", "proposed",
             "logistic regression", "majority-class")
            if w in sentence.lower()]
        alerts.append({
            "type": "marker_attribution_context",
            "marker": marker_key,
            "sentence": sentence[:400],
            "role_words_nearby": role_words_present,
            "adjudication": (
                "Does the sentence credit the marker to the role expected by "
                "ground truth? Human must verify."
            ),
        })

    return {"alerts": alerts}


# ═══════════════════════════════════════════════════════════════════════
# Part 3 — Spend account + cell loop
# ═══════════════════════════════════════════════════════════════════════

class BudgetExhausted(Exception):
    pass


class AccountedOpenAIProvider(OpenAIProvider):
    """OpenAIProvider subclass that records usage from EVERY complete() call.

    The production OpenAIProvider.complete() (bare variant) is opaque to cost
    accounting — only complete_with_usage() fires _report_cost. The synthesis
    path uses bare complete(), so to bound stress-test spend accurately we
    override complete() here to capture response.usage before returning. This
    is a test-only subclass; production code is unchanged.
    """

    def __init__(self, *args, account: "SpendAccount", **kwargs):
        super().__init__(*args, **kwargs)
        self._account = account
        self.last_usage: dict = {}

    async def complete(self, messages, temperature=0.7, max_tokens=4096):
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        # Record usage from the raw response (always populated by z.ai)
        usage = getattr(response, "usage", None)
        inp = getattr(usage, "prompt_tokens", 0) if usage else 0
        out = getattr(usage, "completion_tokens", 0) if usage else 0
        served = getattr(response, "model", None) or self._model
        # NOTE: completion_tokens here includes reasoning_content overhead
        # for glm-5.2, which is what we want for spend bounding.
        self.last_usage = {
            "input_tokens": inp,
            "output_tokens": out,
            "served_model": served,
        }
        self._account.record(inp, out)
        # Mirror the parent's receipt behavior so served_model is captured
        self._set_receipt_from_response(served)
        return response.choices[0].message.content


@dataclass
class SpendAccount:
    """Tracks cumulative spend against a hard ceiling."""
    ceiling_usd: float
    spent_usd: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    calls: int = 0

    def can_spend(self, projected_usd: float) -> bool:
        return (self.spent_usd + projected_usd) <= self.ceiling_usd

    def record(self, input_tokens: int, output_tokens: int) -> float:
        cost = (
            input_tokens / 1_000_000 * ZAI_INPUT_PER_1M
            + output_tokens / 1_000_000 * ZAI_OUTPUT_PER_1M
        )
        self.spent_usd += cost
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.calls += 1
        return cost


@dataclass
class CellResult:
    cell_id: str
    dimension: str
    level: str
    path: str
    rep: int
    paper: str = ""
    prompt: str = ""
    hard_verdict: dict = field(default_factory=dict)
    diagnostics: dict = field(default_factory=dict)
    usage: dict = field(default_factory=dict)
    error: str | None = None


async def run_monolithic(provider: OpenAIProvider, fixture: dict) -> tuple[str, str]:
    """Run PaperSynthesizer.synthesize_session(). Returns (paper, prompt_sent)."""
    from backend.pipeline.synthesis.paper_synthesizer import (
        PaperSynthesizer, SynthesisSession,
    )
    synth = PaperSynthesizer(provider)
    session = SynthesisSession(
        proposal_text=fixture["proposal_text"],
        source_papers=SOURCE_PAPERS,
        domain="machine learning",
        experiment_context=fixture.get("experiment_context"),
        result_markers=tuple(fixture["result_markers"]) if fixture.get("result_markers") else (),
    )
    # Capture the prompt for forensic output
    prompt_sent = PaperSynthesizer._build_user_prompt(
        session.proposal_text,
        list(session.source_papers),
        session.domain,
        experiment_context=session.experiment_context,
        result_markers=list(session.result_markers),
    )
    result = await synth.synthesize_session(session)
    paper = result.paper_markdown if result else ""
    return paper, prompt_sent


async def run_section_wise(provider: OpenAIProvider, fixture: dict) -> tuple[str, str]:
    """Run SectionWiseSynthesizer.synthesize(). Returns (paper, prompt_sent).

    Note: the section-wise path calls the model many times (outline + per
    section). For prompt-forensics we capture the ground-truth block that
    gets prepended to every section prompt.
    """
    from backend.pipeline.synthesis.section_wise_synthesizer import (
        SectionWiseSynthesizer,
    )
    synth = SectionWiseSynthesizer(provider, context_window=8192)
    gt_block = synth._render_ground_truth_block(
        experiment_context=fixture.get("experiment_context"),
        result_markers=fixture.get("result_markers"),
    )
    prompt_sent = (
        "[Section-wise path — ground-truth block prepended to every section prompt]\n"
        + gt_block
    )
    result = await synth.synthesize(
        proposal_text=fixture["proposal_text"],
        source_papers=list(SOURCE_PAPERS),
        domain="machine learning",
        experiment_context=fixture.get("experiment_context"),
        result_markers=fixture.get("result_markers"),
    )
    paper = result.paper_markdown if result else ""
    return paper, prompt_sent


async def run_cell(
    cell_id: str,
    fixture: dict,
    path: str,
    rep: int,
    provider: OpenAIProvider,
    account: SpendAccount,
) -> CellResult:
    """Execute one cell: one live synthesis call + invariant checks."""
    res = CellResult(
        cell_id=cell_id,
        dimension=fixture["dimension"],
        level=fixture["level"],
        path=path,
        rep=rep,
    )
    # Conservative projection: 4000 completion tokens (reasoning overhead),
    # 500 input. Refuse pre-call if it would breach the ceiling.
    projected = 500 / 1_000_000 * ZAI_INPUT_PER_1M + 4000 / 1_000_000 * ZAI_OUTPUT_PER_1M
    if not account.can_spend(projected):
        res.error = f"BudgetExhausted: projected ${projected:.4f} would breach ceiling"
        return res

    spent_before = account.spent_usd
    try:
        if path == "monolithic":
            paper, prompt = await asyncio.wait_for(
                run_monolithic(provider, fixture), timeout=900
            )
        elif path == "section_wise":
            paper, prompt = await asyncio.wait_for(
                run_section_wise(provider, fixture), timeout=1800
            )
        else:
            res.error = f"Unknown path: {path}"
            return res

        res.paper = paper
        res.prompt = prompt

        # Usage recorded by AccountedOpenAIProvider.complete() per call.
        # For section-wise (many calls), last_usage reflects only the last
        # call; spend is cumulative across the whole cell.
        last_usage = getattr(provider, "last_usage", None) or {}
        res.usage = {
            "input_tokens": last_usage.get("input_tokens", 0),
            "output_tokens": last_usage.get("output_tokens", 0),
            "served_model": last_usage.get("served_model", "unknown"),
            # Per-cell cost = delta in cumulative spend.
            "cost_usd": round(account.spent_usd - spent_before, 6),
            "note_for_section_wise": (
                "token counts reflect the LAST call only; cost_usd is cumulative "
                "across all calls in this cell"
            ),
        }

        if paper:
            res.hard_verdict = check_hard_invariants(paper, fixture)
            res.diagnostics = check_diagnostics(paper, fixture)
        else:
            res.hard_verdict = {"all_hard_pass": False, "checks": {}, "note": "empty paper"}
            res.diagnostics = {"alerts": []}

    except asyncio.TimeoutError:
        res.error = f"Timeout ({path})"
    except Exception as e:
        res.error = f"{type(e).__name__}: {str(e)[:300]}\n{traceback.format_exc()[:500]}"

    return res


# ═══════════════════════════════════════════════════════════════════════
# Part 4 — Output writing + summary
# ═══════════════════════════════════════════════════════════════════════

def write_cell_outputs(run_dir: Path, res: CellResult) -> None:
    (run_dir / f"{res.cell_id}_paper.md").write_text(
        res.paper or "[NO PAPER — error or empty]", encoding="utf-8"
    )
    (run_dir / f"{res.cell_id}_prompt.txt").write_text(
        res.prompt or "[NO PROMPT CAPTURED]", encoding="utf-8"
    )
    payload = {
        "cell_id": res.cell_id,
        "dimension": res.dimension,
        "level": res.level,
        "path": res.path,
        "rep": res.rep,
        "hard_verdict": res.hard_verdict,
        "diagnostics": res.diagnostics,
        "usage": res.usage,
        "error": res.error,
    }
    (run_dir / f"{res.cell_id}_result.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8"
    )


def write_summary(run_dir: Path, results: list[CellResult], account: SpendAccount) -> None:
    summary: dict[str, Any] = {
        "spend": {
            "total_usd": round(account.spent_usd, 4),
            "ceiling_usd": account.ceiling_usd,
            "calls": account.calls,
            "input_tokens": account.input_tokens,
            "output_tokens": account.output_tokens,
        },
        "cells": [],
        "dimensions": {},
    }
    for res in results:
        cell_summary = {
            "cell_id": res.cell_id,
            "dimension": res.dimension,
            "level": res.level,
            "path": res.path,
            "rep": res.rep,
            "hard_pass": res.hard_verdict.get("all_hard_pass", False),
            "error": res.error,
            "diagnostic_alert_count": len(res.diagnostics.get("alerts", [])),
        }
        summary["cells"].append(cell_summary)
        key = f"{res.dimension}/{res.level}/{res.path}"
        if key not in summary["dimensions"]:
            summary["dimensions"][key] = {"total": 0, "hard_pass": 0, "errors": 0}
        summary["dimensions"][key]["total"] += 1
        if res.error:
            summary["dimensions"][key]["errors"] += 1
        elif res.hard_verdict.get("all_hard_pass"):
            summary["dimensions"][key]["hard_pass"] += 1

    (run_dir / "stress_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )

    md = [
        "# Ground-Truth Stress Test Summary",
        "",
        f"**Spend:** ${account.spent_usd:.4f} of ${account.ceiling_usd:.2f} ceiling",
        f"**Calls:** {account.calls}  |  Input tokens: {account.input_tokens}  |  Output tokens: {account.output_tokens}",
        "",
        "## Hard-invariant pass rates by cell",
        "",
        "| Cell | Dimension | Level | Path | Hard pass | Alerts | Error |",
        "|---|---|---|---|---|---|---|",
    ]
    for c in summary["cells"]:
        md.append(
            f"| {c['cell_id']} | {c['dimension']} | {c['level']} | {c['path']} | "
            f"{'PASS' if c['hard_pass'] else 'FAIL'} | {c['diagnostic_alert_count']} | "
            f"{c['error'] or ''} |"
        )
    md.append("")
    md.append("## Pass rates by dimension/level/path")
    md.append("")
    md.append("| Dimension/Level/Path | Pass rate | Errors |")
    md.append("|---|---|---|")
    for key, agg in summary["dimensions"].items():
        md.append(f"| {key} | {agg['hard_pass']}/{agg['total']} | {agg['errors']} |")
    md.append("")
    md.append(
        "## Hard invariants vs diagnostic alerts\n\n"
        "Hard invariants determine the pass rate: ground-truth method and "
        "dataset identity; every required marker and numeric value present; "
        "marker-to-role attribution preserved when roles are defined; and no "
        "explicit reversal of authoritative metric direction.\n\n"
        "Diagnostic alerts (conflicting-term mentions, sentence-level "
        "attribution heuristics) are recorded for human review but never "
        "affect the pass rate. A Related Work comparison that mentions the "
        "conflicting method is an alert, not a failure."
    )
    (run_dir / "stress_summary.md").write_text("\n".join(md), encoding="utf-8")


def write_artifact_hashes(run_dir: Path) -> None:
    """Write sha256 over every sibling except this file. Written LAST."""
    targets = [p for p in run_dir.iterdir()
               if p.is_file() and p.name != "artifact_hashes.json"]
    hashes = {}
    for p in sorted(targets, key=lambda x: x.name):
        hashes[p.name] = hashlib.sha256(p.read_bytes()).hexdigest()
    (run_dir / "artifact_hashes.json").write_text(
        json.dumps(hashes, indent=2), encoding="utf-8"
    )


# ═══════════════════════════════════════════════════════════════════════
# Part 5 — Main
# ═══════════════════════════════════════════════════════════════════════

def get_git_sha() -> str:
    import subprocess
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True
        ).strip()
    except Exception:
        return "unknown"


async def main_async(args: argparse.Namespace) -> int:
    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = REPO_ROOT / "evidence" / f"stress_{timestamp}"
    if run_dir.exists():
        logger.error("Run directory already exists: %s", run_dir)
        return 1
    run_dir.mkdir(parents=True)
    logger.info("Run directory: %s", run_dir)

    settings = get_settings()
    logger.info("Model: %s @ %s", settings.openai_model, settings.openai_base_url)

    fixtures = [f() for f in ALL_FIXTURES]
    paths = ["monolithic", "section_wise"]
    reps = args.reps

    # Smoke mode: exactly ONE cell per the corrected decision.
    if args.smoke:
        fixtures = [fixture_method_absurd()]
        paths = ["monolithic"]
        reps = 1
        logger.info("SMOKE MODE: 1 cell (absurd x monolithic x 1 rep)")

    total_cells = len(fixtures) * len(paths) * reps
    logger.info(
        "Matrix: %d fixtures x %d paths x %d reps = %d cells",
        len(fixtures), len(paths), reps, total_cells,
    )

    manifest = {
        "run_id": timestamp,
        "git_sha": get_git_sha(),
        "python_version": sys.version.split()[0],
        "model": settings.openai_model,
        "base_url": settings.openai_base_url,
        "ceiling_usd": args.ceiling,
        "pricing_assumption": {
            "input_per_1m": ZAI_INPUT_PER_1M,
            "output_per_1m": ZAI_OUTPUT_PER_1M,
            "source": "cost_estimator.py:20 (glm-5.1); glm-5.2 assumed parity",
        },
        "total_cells_planned": total_cells,
        "fixtures": [{"dimension": f["dimension"], "level": f["level"]} for f in fixtures],
        "paths": paths,
        "reps": reps,
        "smoke": args.smoke,
    }
    (run_dir / "run_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    account = SpendAccount(ceiling_usd=args.ceiling)
    provider = AccountedOpenAIProvider(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        base_url=settings.openai_base_url,
        account=account,
    )

    results: list[CellResult] = []
    cell_counter = 0
    budget_broken = False
    try:
        for fixture in fixtures:
            if budget_broken:
                break
            for path in paths:
                if budget_broken:
                    break
                for rep in range(1, reps + 1):
                    cell_counter += 1
                    cell_id = f"{fixture['dimension']}_{fixture['level']}_{path}_rep{rep}"
                    logger.info(
                        "[%d/%d] %s (spent=$%.4f)",
                        cell_counter, total_cells, cell_id, account.spent_usd,
                    )
                    res = await run_cell(cell_id, fixture, path, rep, provider, account)
                    results.append(res)
                    write_cell_outputs(run_dir, res)
                    if res.error:
                        logger.warning("  cell error: %s", res.error[:120])
                        if "BudgetExhausted" in res.error:
                            budget_broken = True
                            logger.warning("Budget exhausted — stopping early.")
                            break
                    elif res.hard_verdict.get("all_hard_pass"):
                        logger.info("  HARD PASS")
                    else:
                        logger.info("  HARD FAIL")
    except KeyboardInterrupt:
        logger.warning("Interrupted by user — writing partial summary.")

    write_summary(run_dir, results, account)
    write_artifact_hashes(run_dir)
    logger.info("Done. Spent $%.4f across %d calls.", account.spent_usd, account.calls)
    logger.info("Outputs in: %s", run_dir)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Ground-truth stress harness")
    parser.add_argument("--ceiling", type=float, default=50.0,
                        help="Hard spend ceiling in USD (default: 50)")
    parser.add_argument("--reps", type=int, default=3,
                        help="Reps per cell (default: 3)")
    parser.add_argument("--smoke", action="store_true",
                        help="Smoke mode: 1 cell (absurd x monolithic x 1 rep)")
    return asyncio.run(main_async(parser.parse_args()))


if __name__ == "__main__":
    sys.exit(main())
