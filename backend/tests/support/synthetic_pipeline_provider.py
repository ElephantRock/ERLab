"""Deterministic synthetic provider for the post-gap downstream proof.

Routes responses by canonical stage context (set via ``set_context``), not
only by prompt/schema keyword matching — because several stages share
schemas (e.g. ideator and refiner both use ``{ideas: [...]}``).

Every response is:
    deterministic   — same stage context → same output, always
    schema-conformant — matches what the real stage parses
    stage-specific — content is relevant to the synthetic low-resource MT seed
    usage-bearing  — records input/output tokens in a call ledger
    run-scoped     — every call records the active run_id
    network-free   — no I/O, no real model

The provider implements the full LLMProvider surface required by the
downstream stages:
    complete(), complete_with_usage(), structured_output(),
    structured_output_with_usage(), set_context(), complete_stream()

A call ledger records (stage, method, run_id, input_tokens, output_tokens)
for accounting assertions.
"""

from __future__ import annotations

from typing import Any

from backend.providers.base import LLMProvider

# Stage names from PipelineOrchestrator._STAGE_ORDER that this provider
# serves (the post-gap downstream set).
SUPPORTED_STAGES = frozenset({
    "idea_generation",
    "idea_reflection",
    "gap_reflection",
    "novelty_checking",
    "feasibility_scoring",
    "proposal_synthesis",
    "adversarial_review",
    "evaluation",
    "paper_synthesis",
    "citation_audit",
    "proposal_deepening",
})


class SyntheticPipelineProvider(LLMProvider):
    """Deterministic, network-free provider for downstream pipeline proof.

    Construct with ``SyntheticPipelineProvider()``; call
    ``set_context(stage, run_id)`` before the stage executes (the real
    orchestrator does this automatically). Inspect ``call_ledger`` for
    accounting assertions.
    """

    def __init__(self, run_id: str = "synthetic-run") -> None:
        # NOTE: deliberately do NOT call super().__init__() — the base
        # __init__ is benign but some test paths construct providers
        # without it. We set the receipt attr the analyzer reads.
        self._last_receipt: Any = None
        self._stage: str = ""
        self._run_id: str = run_id
        self.call_ledger: list[dict] = []

    # ── Context routing ──────────────────────────────────────────────

    def set_context(self, stage: str, run_id: str) -> None:
        """Set the canonical stage/run_id for the next call(s)."""
        self._stage = stage
        self._run_id = run_id or self._run_id

    def _record(self, method: str, input_tokens: int, output_tokens: int) -> None:
        self.call_ledger.append({
            "stage": self._stage,
            "method": method,
            "run_id": self._run_id,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        })

    def _route_structured(self, messages: list[dict], schema: dict) -> dict:
        """Return a schema-conformant dict for the current stage."""
        stage = self._stage
        # Idea generation runs three sub-agents (ideator/critic/refiner),
        # all under the idea_generation stage. Distinguish by schema shape.
        if stage == "idea_generation":
            return self._idea_generation_response(schema)
        if stage == "novelty_checking":
            return self._novelty_response()
        if stage == "feasibility_scoring":
            return self._feasibility_response()
        if stage == "adversarial_review":
            return self._adversarial_response()
        if stage in ("evaluation", "paper_synthesis", "proposal_synthesis",
                     "citation_audit", "proposal_deepening"):
            # These stages use complete()/complete_with_usage(), not
            # structured_output. If we land here, fall back to a generic
            # schema-filling response.
            return self._fill_schema(schema)
        # Fallback for reflection or unknown stages.
        return self._fill_schema(schema)

    def _route_text(self, messages: list[dict]) -> str:
        """Return deterministic free text for the current stage."""
        stage = self._stage
        if stage == "evaluation":
            return self._evaluation_text()
        if stage == "paper_synthesis":
            return self._paper_markdown()
        if stage == "proposal_synthesis":
            return self._proposal_markdown()
        if stage == "citation_audit":
            return self._citation_audit_json()
        if stage == "idea_reflection" or stage == "gap_reflection":
            return self._reflection_text()
        if stage == "proposal_deepening":
            return self._deepening_markdown()
        # Generic fallback text.
        return "Synthetic completion response for stage " + (stage or "unknown") + "."

    # ── LLMProvider interface ────────────────────────────────────────

    async def complete(self, messages, temperature=0.7, max_tokens=4096) -> str:
        text = self._route_text(messages)
        self._record("complete", self._estimate_in(messages), len(text.split()))
        return text

    async def complete_with_usage(self, messages, temperature=0.7, max_tokens=4096,
                                  stage="", run_id=None) -> Any:
        from backend.providers.base import LLMResponse
        text = self._route_text(messages)
        in_tok, out_tok = self._estimate_in(messages), len(text.split())
        self._record("complete_with_usage", in_tok, out_tok)
        return LLMResponse(content=text, input_tokens=in_tok, output_tokens=out_tok,
                           served_model=self.default_model)

    async def structured_output(self, messages, schema, temperature=0.3, max_tokens=4096,
                                **kwargs) -> dict:
        result = self._route_structured(messages, schema)
        self._record("structured_output", self._estimate_in(messages), 64)
        return result

    async def structured_output_with_usage(self, messages, schema, temperature=0.3,
                                           stage="", run_id=None, **kwargs) -> Any:
        from backend.providers.base import LLMResponse
        result = self._route_structured(messages, schema)
        in_tok = self._estimate_in(messages)
        self._record("structured_output_with_usage", in_tok, 64)
        return LLMResponse(content="", structured=result, input_tokens=in_tok,
                           output_tokens=64, served_model=self.default_model)

    async def complete_stream(self, messages, temperature=0.7, max_tokens=4096):
        yield self._route_text(messages)

    @property
    def provider_name(self) -> str:
        return "synthetic_pipeline"

    @property
    def default_model(self) -> str:
        return "synthetic-model"

    @staticmethod
    def _estimate_in(messages: list[dict]) -> int:
        total = 0
        for m in messages or []:
            total += len(str(m.get("content", "")).split())
        return total

    # ── Stage-specific structured responses ──────────────────────────

    def _idea_generation_response(self, schema: dict) -> dict:
        props = set(schema.get("properties", {}).keys())
        # Refiner schema items carry a 'score' field; ideator does not.
        # Critic schema top-level is {critiques: [...]}.
        if "critiques" in props:
            return self._critic_response()
        return self._ideator_response(schema)

    @staticmethod
    def _ideator_response(schema: dict) -> dict:
        return {
            "ideas": [
                {
                    "title": "Morpheme-Aware BLEU for Polysynthetic Languages",
                    "problem_statement": (
                        "Standard MT evaluation metrics assume whitespace "
                        "tokenization and fail for polysynthetic languages "
                        "where a single word encodes a full clause."
                    ),
                    "proposed_method": (
                        "We propose a morpheme-aware BLEU variant that aligns "
                        "on morpheme sequences rather than surface tokens, "
                        "using a learned segmenter for low-resource languages."
                    ),
                    "expected_contributions": (
                        "A morpheme-level metric validated against human "
                        "fluency judgments for three polysynthetic languages."
                    ),
                    "novelty_rationale": (
                        "Existing morpheme-aware metrics are proposed but "
                        "unvalidated; we provide the first human-judgment "
                        "validation in the lowest-resource setting."
                    ),
                    "evaluation_approach": (
                        "Correlate metric scores with human fluency judgments "
                        "on Inuktitut, Yupik, and Mohawk translation pairs."
                    ),
                },
                {
                    "title": "Truly Low-Resource Benchmark for African MT",
                    "problem_statement": (
                        "Existing low-resource MT benchmarks rarely include "
                        "truly low-resource African language pairs with under "
                        "10k parallel sentences."
                    ),
                    "proposed_method": (
                        "We assemble a benchmark of 12 African language pairs "
                        "with 1k-10k parallel sentences and evaluate "
                        "cross-lingual transfer methods systematically."
                    ),
                    "expected_contributions": (
                        "An open benchmark exposing where cross-lingual "
                        "transfer breaks for the lowest-resource pairs."
                    ),
                    "novelty_rationale": (
                        "No existing benchmark covers this scarcity range "
                        "across African languages with controlled evaluation."
                    ),
                    "evaluation_approach": (
                        "Evaluate mBERT, XLM-R, and NLLB transfer; report "
                        "BLEU, chrF, and morpheme-aware metrics."
                    ),
                },
            ]
        }

    @staticmethod
    def _critic_response() -> dict:
        return {
            "critiques": [
                {
                    "idea_title": "Morpheme-Aware BLEU for Polysynthetic Languages",
                    "strengths": ["Addresses a clear metric gap for polysynthetic languages."],
                    "weaknesses": ["Human judgments for these languages are hard to collect."],
                    "prior_art_concerns": [],
                    "feasibility_concerns": ["Segmenter quality limits metric reliability."],
                    "suggestions": ["Use expert-validated segmenters; add a fallback baseline."],
                    "overall_assessment": "Promising but requires careful validation design.",
                },
                {
                    "idea_title": "Truly Low-Resource Benchmark for African MT",
                    "strengths": ["Fills a real benchmarking gap."],
                    "weaknesses": ["Data licensing and speaker community consent needed."],
                    "prior_art_concerns": [],
                    "feasibility_concerns": ["Parallel data at 1k scale is noisy."],
                    "suggestions": ["Add data provenance and consent documentation."],
                    "overall_assessment": "Strong contribution if data is ethically sourced.",
                },
            ]
        }

    @staticmethod
    def _novelty_response() -> dict:
        return {
            "method_novelty": 0.78,
            "problem_novelty": 0.72,
            "domain_transfer": 0.65,
            "combination_novelty": 0.74,
            "overall_score": 0.72,
            "novelty_arguments": (
                "The combination of morpheme-aware evaluation with truly "
                "low-resource validation has not been previously explored."
            ),
            "closest_match_title": "Morpheme-Aware Metrics for Agglutinative Languages",
            "closest_match_similarity": 0.41,
            "strategic_direction": "methodological_innovation",
        }

    @staticmethod
    def _feasibility_response() -> dict:
        return {
            "data_availability": 6.5,
            "computational_requirements": 7.5,
            "methodological_complexity": 6.0,
            "evaluation_plan": 7.0,
            "novelty_grounding": 7.5,
            "impact_potential": 8.0,
            "overall_score": 7.0,  # recomputed by the scorer; included for completeness
            "reasoning": (
                "Feasible with public data and moderate compute. Main risk "
                "is segmenter quality for the lowest-resource languages."
            ),
            "estimated_timeline": "6-9 months",
            "key_risks": ["Segmenter quality", "Sparse human judgments"],
        }

    @staticmethod
    def _adversarial_response() -> dict:
        return {
            "soundness": 8,
            "novelty": 7,
            "feasibility": 7,
            "clarity": 8,
            "soundness_justification": "The metric is well-defined and the validation plan is sound.",
            "novelty_justification": "Combines morpheme-aware scoring with low-resource validation.",
            "feasibility_justification": "Compute and data requirements are moderate.",
            "clarity_justification": "The proposal is clearly written and well-structured.",
            "revision_notes": "",
        }

    @staticmethod
    def _fill_schema(schema: dict) -> dict:
        """Generic schema-filling fallback for structured_output callers."""
        result: dict[str, Any] = {}
        props = schema.get("properties", {})
        for key, prop_schema in props.items():
            prop_type = prop_schema.get("type")
            if prop_type == "string":
                result[key] = f"Synthetic {key}"
            elif prop_type == "number":
                result[key] = 0.7
            elif prop_type == "integer":
                result[key] = 1
            elif prop_type == "boolean":
                result[key] = True
            elif prop_type == "array":
                items = prop_schema.get("items", {})
                if items.get("type") == "object":
                    result[key] = [SyntheticPipelineProvider._fill_schema(items)]
                elif items.get("type") == "string":
                    result[key] = [f"{key}_item"]
                else:
                    result[key] = []
            elif prop_type == "object":
                result[key] = SyntheticPipelineProvider._fill_schema(prop_schema)
        return result

    # ── Stage-specific free-text responses ───────────────────────────

    @staticmethod
    def _evaluation_text() -> str:
        # ProposalEvaluator expects tagged DIM_SCORE / DIM_JUSTIFICATION lines,
        # 7 dimensions, 0.0-1.0 floats, plus OVERALL_SCORE.
        dims = [
            ("NOVELTY", 0.74, "Novel combination of morpheme-aware scoring with low-resource validation."),
            ("FEASIBILITY", 0.71, "Moderate compute and data requirements; main risk is segmenter quality."),
            ("COMPLETENESS", 0.78, "All required sections present with concrete evaluation plan."),
            ("RIGOR", 0.70, "Validation design is sound; statistical significance plan included."),
            ("CLARITY", 0.82, "Clearly written with well-defined methodology."),
            ("BASELINE_ADEQUACY", 0.69, "Baselines cover standard metrics but could add recent neural segmenters."),
            ("COMPUTE_REALISM", 0.76, "Compute budget is realistic for academic hardware."),
        ]
        lines = []
        for name, score, just in dims:
            lines.append(f"{name}_SCORE: {score}")
            lines.append(f"{name}_JUSTIFICATION: {just}")
        lines.append("OVERALL_SCORE: 0.74")
        return "\n".join(lines)

    @staticmethod
    def _paper_markdown() -> str:
        # Monolithic paper synthesis: raw markdown with [SOURCE-N] markers.
        # Must include at least two [SOURCE-N] markers, all in range, and
        # exceed the minimum paper word threshold.
        body = (
            "## Title\n\n"
            "Morpheme-Aware Evaluation for Truly Low-Resource Machine Translation\n\n"
            "## Abstract\n\n"
            "Standard machine translation evaluation metrics assume whitespace "
            "tokenization and systematically under-report quality for morphologically "
            "rich, polysynthetic languages. We propose a morpheme-aware evaluation "
            "framework that aligns on morpheme sequences rather than surface tokens, "
            "and we validate it against human fluency judgments for three truly "
            "low-resource polysynthetic languages. Our results show that morpheme-level "
            "alignment correlates with human judgments far more reliably than surface "
            "BLEU or chrF in this regime [SOURCE-1]. We further assemble a controlled "
            "benchmark of twelve African language pairs with one to ten thousand "
            "parallel sentences, exposing where cross-lingual transfer from multilingual "
            "encoders breaks down [SOURCE-2]. Together, these contributions make MT "
            "evaluation trustworthy for the languages where it currently fails most.\n\n"
            "## Introduction\n\n"
            "Recent advances in multilingual modeling have improved machine translation "
            "for many languages, yet the lowest-resource languages remain poorly served. "
            "Two intertwined problems persist. First, evaluation metrics designed for "
            "whitespace-tokenized text fail on polysynthetic languages where a single "
            "word may encode an entire clause. Second, the benchmarks used to validate "
            "cross-lingual transfer methods rarely include truly low-resource languages "
            "with under ten thousand parallel sentences, leaving the effectiveness of "
            "these methods in the scarcest settings unmeasured [SOURCE-1]. In this work "
            "we address both gaps. We introduce a morpheme-aware evaluation metric and "
            "validate it against human judgments, and we assemble a controlled benchmark "
            "spanning twelve low-resource African language pairs. Our experiments reveal "
            "that surface metrics substantially underestimate translation quality in the "
            "polysynthetic regime, and that cross-lingual transfer degrades sharply "
            "below a data threshold. These findings have direct implications for how "
            "the community evaluates and deploys low-resource translation systems.\n\n"
            "## Related Work\n\n"
            "Prior work on morpheme-aware metrics has proposed variants of BLEU and chrF "
            "that operate on morpheme sequences, but these metrics have never been "
            "validated against human judgments for polysynthetic languages [SOURCE-3]. "
            "Separately, cross-lingual transfer from multilingual encoders has been "
            "studied extensively for medium-resource languages, yet the lowest-resource "
            "setting remains underexplored. Our work bridges these threads by providing "
            "both a validated metric and a controlled benchmark in the regime where "
            "existing approaches are least reliable.\n\n"
            "## Method\n\n"
            "We define a morpheme-aware metric that computes n-gram precision and recall "
            "over morpheme sequences produced by a learned segmenter. Formally, given a "
            "reference $r$ and hypothesis $h$, we segment both into morpheme sequences "
            "$M(r)$ and $M(h)$ and compute modified n-gram precision. The overall "
            "objective combines morpheme precision with a length penalty: "
            "$$\\mathcal{L} = -\\sum_{t=1}^{T} \\log P(m_t | m_{<t}, c)$$ where $m_t$ "
            "is the t-th morpheme and $c$ is the retrieved context. We compare against "
            "surface BLEU, surface chrF, and a token-level baseline.\n\n"
            "## Evaluation Plan\n\n"
            "We evaluate on three polysynthetic languages (Inuktitut, Yupik, Mohawk) "
            "with expert-collected human fluency judgments, and on twelve African "
            "language pairs with one to ten thousand parallel sentences. Metrics include "
            "Pearson and Spearman correlation with human judgments, and BLEU/chrF for "
            "the African benchmark. Baselines are surface BLEU, surface chrF, and the "
            "token-level baseline. We report statistical significance via bootstrap "
            "resampling.\n\n"
            "## Limitations\n\n"
            "Our morpheme segmenter depends on limited training data for the lowest-"
            "resource languages, which may introduce segmentation error. Human judgment "
            "collection is expensive and limited to three polysynthetic languages. The "
            "African benchmark, while controlled, remains small.\n\n"
            "## Conclusion\n\n"
            "We introduced a morpheme-aware evaluation metric validated against human "
            "judgments for polysynthetic languages, and a controlled benchmark for truly "
            "low-resource African MT. Both contributions target the regime where existing "
            "evaluation and transfer methods fail most. We hope this work encourages the "
            "community to evaluate low-resource MT on its own terms rather than with "
            "metrics designed for higher-resource, whitespace-tokenized languages.\n\n"
            "## References\n\n"
            "[SOURCE-1] Synthetic Author (2023). A Survey of Low-Resource Machine "
            "Translation Benchmarks. Synthetic Workshop.\n"
            "[SOURCE-2] Synthetic Author (2024). Cross-Lingual Transfer for Endangered "
            "Languages: A Review. Synthetic Workshop.\n"
            "[SOURCE-3] Synthetic Author (2023). Evaluation Metrics for Morphologically "
            "Rich Languages. Synthetic Workshop.\n"
        )
        return body

    @staticmethod
    def _proposal_markdown() -> str:
        # ProposalSynthesizer expects markdown with ## Section headers and
        # [SOURCE-N] citations across 10 required sections.
        return (
            "## Title\n\n"
            "Morpheme-Aware Evaluation for Truly Low-Resource Machine Translation\n\n"
            "## Abstract\n\n"
            "We propose a morpheme-aware evaluation metric validated against human "
            "fluency judgments for polysynthetic languages, and a controlled benchmark "
            "for truly low-resource African MT [SOURCE-1].\n\n"
            "## Introduction\n\n"
            "Standard metrics fail for morphologically rich languages and the lowest-"
            "resource settings are underexplored [SOURCE-2]. We address both gaps.\n\n"
            "## Related Work\n\n"
            "Prior morpheme-aware metrics are unvalidated for polysynthetic languages "
            "[SOURCE-3]. Cross-lingual transfer is unstudied below 10k sentences.\n\n"
            "## Proposed Method\n\n"
            "We compute n-gram precision over morpheme sequences from a learned "
            "segmenter. The objective is "
            "$$\\mathcal{L} = -\\sum_{t=1}^{T} \\log P(m_t | m_{<t}, c)$$. "
            "We fuse this with a length penalty and compare to surface baselines.\n\n"
            "## Expected Contributions\n\n"
            "1. A validated morpheme-aware metric. 2. A controlled low-resource "
            "benchmark. 3. Evidence on where transfer breaks.\n\n"
            "## Evaluation Plan\n\n"
            "Three polysynthetic languages with human judgments; twelve African pairs. "
            "Metrics: Pearson/Spearman correlation, BLEU, chrF. Baselines: surface BLEU, "
            "chrF, token baseline. Significance via bootstrap.\n\n"
            "## Timeline\n\n"
            "Months 1-3 data and segmenters; 4-6 experiments; 7-9 writing.\n\n"
            "## References\n\n"
            "[1] Synthetic Author (2023). A Survey of Low-Resource MT Benchmarks.\n"
            "[2] Synthetic Author (2024). Cross-Lingual Transfer Review.\n"
            "[3] Synthetic Author (2023). Evaluation Metrics for Morphologically Rich Languages.\n\n"
            "## Risk Mitigation\n\n"
            "Segmenter error is mitigated with expert-validated fallbacks. Sparse human "
            "judgments are mitigated with bootstrap significance testing.\n"
        )

    @staticmethod
    def _citation_audit_json() -> str:
        # CitationClaimAuditor parses JSON via extract_json(strict=True).
        # Returns one verification per call context.
        import json
        return json.dumps({
            "context_verified": True,
            "context_justification": "The cited survey supports the claimed benchmark gap.",
            "quantitative_claims": [],
            "quantitative_verified": True,
            "trust_contribution": 0.8,
        })

    @staticmethod
    def _reflection_text() -> str:
        # ReflectionStage expects SCORE/PASSED/JUSTIFICATION/FEEDBACK tags.
        return (
            "SCORE: 0.85\n"
            "PASSED: yes\n"
            "JUSTIFICATION: The content is coherent and well-grounded.\n"
            "FEEDBACK: Minor clarity improvements possible but not required.\n"
        )

    @staticmethod
    def _deepening_markdown() -> str:
        # ProposalDeepener parses ## headers (only reached if a provider is injected).
        return (
            "## Preliminary Architecture\n\n"
            "Morpheme segmenter feeding an n-gram metric with length penalty.\n\n"
            "## Minimal Working Example\n\n"
            "Align one Inuktitut hypothesis to a reference at the morpheme level.\n\n"
            "## Failure Modes\n\n"
            "Segmenter error on unseen morphology.\n\n"
            "## Success Criteria\n\n"
            "Spearman correlation above 0.6 with human judgments.\n"
        )
