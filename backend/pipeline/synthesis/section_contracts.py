"""Per-section prompt templates with structured claim output requirements.

Each section has a contract defining:
1. What claim types are allowed
2. What structure the output must follow
3. How speculative claims must be marked
4. The JSON schema for structured output

The generator emits typed claims as JSON. The ClaimRenderer converts to prose.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# ── JSON Schema for Structured Claims ────────────────────────────────────

CLAIM_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["claims", "section"],
    "properties": {
        "section": {"type": "string"},
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "claim_id", "text", "type", "evidence_ids",
                    "speculative", "rationale", "section",
                ],
                "properties": {
                    "claim_id": {"type": "string", "description": "Local ID like C001"},
                    "text": {"type": "string", "description": "The claim text"},
                    "type": {
                        "type": "string",
                        "description": "One of: background, prior_limitation, "
                                        "method_design_motivation, method_proposed_mechanism, "
                                        "method_claimed_benefit, hypothesis, "
                                        "evaluation_benchmark, evaluation_metric, "
                                        "evaluation_protocol, expected_contribution, result",
                    },
                    "evidence_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Source IDs like SOURCE-14. Empty if unsupported.",
                    },
                    "speculative": {
                        "type": "boolean",
                        "description": "True if this is a hypothesis or untested claim",
                    },
                    "rationale": {
                        "type": "string",
                        "description": "Why this claim is here",
                    },
                    "section": {"type": "string"},
                    "newly_proposed": {
                        "type": "boolean",
                        "description": "True if this is a new contribution, not from prior work",
                    },
                    "benchmark_precedent": {
                        "type": "string",
                        "description": "Citation for benchmark precedent, if applicable",
                    },
                    "assumption_refs": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "IDs of assumptions this claim depends on",
                    },
                },
            },
        },
        "assumptions": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["text", "basis", "risk"],
                "properties": {
                    "text": {"type": "string"},
                    "basis": {
                        "type": "string",
                        "description": "analogical | theoretical | empirical | conjecture",
                    },
                    "risk": {
                        "type": "string",
                        "description": "low | medium | high",
                    },
                    "supporting_sources": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "validation_plan": {"type": "string"},
                },
            },
        },
    },
}

CLAIM_SCHEMA_STR = json.dumps(CLAIM_SCHEMA, indent=2)


# ── Per-Section Prompt Templates ─────────────────────────────────────────

RELATED_WORK_PROMPT = """\
You are writing the Related Work section of a research paper.

## STRICT RULES:
1. ONLY "background" and "prior_limitation" claim types are allowed.
2. EVERY claim MUST cite a source using [SOURCE-X].
3. NO speculative claims. No "we hypothesize", "we expect", "we propose".
4. Every paragraph must be citation-dense.

## CLAIM FORMAT:
Each claim must have:
- text: The factual statement about prior work
- type: "background" (factual finding) or "prior_limitation" (gap/weakness)
- evidence_ids: The [SOURCE-X] citations supporting this claim
- speculative: false (ALWAYS false for Related Work)
- rationale: Why this prior work is relevant

## OUTPUT FORMAT:
Output a JSON object with your claims:
{schema}

Example:
{{
  "section": "related_work",
  "claims": [
    {{
      "claim_id": "C001",
      "text": "Tool-augmented LLMs have shown promise in structured reasoning tasks [SOURCE-3].",
      "type": "background",
      "evidence_ids": ["SOURCE-3"],
      "speculative": false,
      "rationale": "Establishes baseline for tool-augmented approaches"
    }}
  ]
}}
"""


INTRODUCTION_PROMPT = """\
You are writing the Introduction section of a research paper.

## STRICT RULES:
1. Allowed claim types: background, prior_limitation, method_design_motivation.
2. background and prior_limitation claims MUST cite [SOURCE-X].
3. method_design_motivation claims should cite analogous prior work where possible.
4. Do NOT include method_claimed_benefit or hypothesis claims here.

## STRUCTURE:
- Open with background on the problem (cite sources)
- Identify prior limitations (cite sources)
- Motivate the design approach (cite analogous work)

## OUTPUT FORMAT:
{schema}
"""


METHOD_PROMPT = """\
You are writing the Proposed Method section of a research paper.

## CRITICAL — MECHANISM VS BENEFIT SPLITTING:
If a sentence describes a mechanism AND claims a benefit, you MUST split it into two claims.

WRONG (single claim):
  "We propose a two-stage uncertainty-aware tool router that improves robustness"

RIGHT (two claims):
  Claim 1: type="method_proposed_mechanism", text="We propose a two-stage uncertainty-aware tool router.", speculative=false
  Claim 2: type="method_claimed_benefit", text="We hypothesize that this router may improve robustness in high-stakes settings.", speculative=true

Any sentence containing "improves", "enables", "solves", "reduces", "advances", "increases",
"outperforms", "mitigates", "enhances" in context of the proposed method is a benefit claim.

## CLAIM TYPES:
1. method_design_motivation — Why this design, citing prior work. speculative=false. Must cite.
2. method_proposed_mechanism — What you propose. speculative=false. Purely descriptive.
3. method_claimed_benefit — What you expect it to achieve. MUST have speculative=true.
4. background — Factual statements about prior work. Must cite.

## DESIGN ASSUMPTIONS:
If you make assumptions, list them separately with basis, risk, and validation plan.

## OUTPUT FORMAT:
{schema}

Include an "assumptions" array if applicable.
"""


EVALUATION_PROMPT = """\
You are writing the Evaluation Plan section of a research paper.

## REQUIRED — FOUR BLOCKS (all must be present):

### Block 1: Benchmarks / Datasets
- Cite precedent: "We use dataset X [SOURCE-Y]" → type="evaluation_benchmark"
- Or mark as new: "We propose a new benchmark..." → type="evaluation_benchmark", newly_proposed=true
- Performance numbers FORBIDDEN unless actual experiments exist.

### Block 2: Metrics
- Cite precedent: "Following [SOURCE-X], we measure..." → type="evaluation_metric"
- Or justify as new: "We introduce a new metric..." → type="evaluation_metric", newly_proposed=true

### Block 3: Experimental Protocol
- Design rationale required → type="evaluation_protocol"
- May include design_assumptions

### Block 4: Expected Outcomes
- ALL expected outcomes MUST be hypotheses: "We hypothesize that..." → type="hypothesis", speculative=true
- Words "improves by X%" → type="result" → REJECTED without experiments
- NEVER state expected results as proven facts.

## OUTPUT FORMAT:
{schema}

Include an "assumptions" array for experimental assumptions.
"""


ABSTRACT_PROMPT = """\
You are writing the Abstract section of a research paper.

## RULES:
1. Allowed types: background, method_proposed_mechanism, expected_contribution.
2. expected_contribution MUST be marked speculative=true.
3. Use "We aim to..." or "We expect..." for contributions, NOT "This work advances..."

## OUTPUT FORMAT:
{schema}
"""


DISCUSSION_PROMPT = """\
You are writing the Discussion and Future Work section of a research paper.

## RULES:
1. Allowed types: background, hypothesis, expected_contribution.
2. hypothesis and expected_contribution MUST be marked speculative=true.
3. Frame future work as hypotheses, not predictions.

## OUTPUT FORMAT:
{schema}
"""


CONCLUSION_PROMPT = """\
You are writing the Conclusion section of a research paper.

## RULES:
1. Allowed types: background, expected_contribution.
2. expected_contribution MUST be marked speculative=true.
3. Use "This work aims to..." NOT "This work advances..."
4. Summarize grounded findings, mark speculative contributions honestly.

## OUTPUT FORMAT:
{schema}
"""


# ── Prompt Registry ──────────────────────────────────────────────────────

SECTION_PROMPTS: dict[str, str] = {
    "abstract": ABSTRACT_PROMPT,
    "introduction": INTRODUCTION_PROMPT,
    "related_work": RELATED_WORK_PROMPT,
    "proposed_method": METHOD_PROMPT,
    "evaluation_plan": EVALUATION_PROMPT,
    "discussion": DISCUSSION_PROMPT,
    "conclusion": CONCLUSION_PROMPT,
}


def get_section_prompt(section_id: str) -> str:
    """Get the prompt template for a section, with schema filled in."""
    template = SECTION_PROMPTS.get(section_id, "")
    if not template:
        # Fallback generic prompt
        template = (
            "Write the {section} section. "
            "Output claims as JSON with the schema below.\n"
            "{schema}"
        )
    return template.replace("{schema}", CLAIM_SCHEMA_STR)


def get_schema_for_validation() -> dict[str, Any]:
    """Get the JSON schema for validating structured output."""
    return CLAIM_SCHEMA
