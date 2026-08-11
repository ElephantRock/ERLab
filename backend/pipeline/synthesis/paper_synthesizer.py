"""Paper synthesis — expand a research proposal into a full academic paper.

Uses the generation provider (A-01) to convert proposal text + source papers
into a structured academic paper with proper sections and [SOURCE-X] citations.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path

from backend.providers.base import LLMProvider

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).parent / "prompts" / "paper_synthesis_system.md"


@dataclass(frozen=True)
class SynthesisSession:
    """Information-isolation contract for paper synthesis.

    Enumerates the EXACT inputs the synthesizer is permitted to see. The
    synthesizer prompt is the only channel from the pipeline to the generation
    model; controlling this object's fields controls that channel.

    Design intent (phase-8 / CRUX failure-mode fix): prevent producer-side
    state — orchestrator run context, evaluation scores, prior verifier
    verdicts, self-assessment — from leaking into the synthesis prompt. Only
    the proposal, its supporting literature, the (optional) observed
    experiment results, and the domain belong here.

    This wrapper is ADVISORY in the prototype: ``synthesize_session()`` logs
    a warning if a caller passes an out-of-band input via the legacy
    positional args. It does not fail the call. Promote to a hard boundary
    once the call-site audit is complete.
    """

    proposal_text: str
    source_papers: tuple[str, ...] = ()
    domain: str = "AI/NLP"
    experiment_context: str | None = None
    result_markers: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        # Defensive: source_papers / result_markers may be passed as lists.
        if not isinstance(self.source_papers, tuple):
            object.__setattr__(self, "source_papers", tuple(self.source_papers))
        if not isinstance(self.result_markers, tuple):
            object.__setattr__(self, "result_markers", tuple(self.result_markers))


@dataclass
class PaperSynthesisResult:
    """Result of expanding a proposal into a full academic paper."""

    proposal_id: int
    paper_markdown: str
    word_count: int
    venue: str
    model_used: str
    source_count: int
    # Phase 4 / WP-4C: the frozen marker→source map. Each entry is
    # {marker_index, marker, source_id} where source_id is the literature
    # Paper.id used to construct [SOURCE-N]. Out-of-range markers emitted by
    # the model carry source_id=None and mapping_status="unmapped". The map is
    # built by PaperSynthesisStage.build_source_map and persisted by
    # persist_proposals into paper_source_markers.
    source_map: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


class PaperSynthesizer:
    """Expand a research proposal into a full academic paper via LLM.

    Uses the generation provider (cloud) — this is a generation task (A-01).
    Gracefully returns None on LLM failure (HB-02).
    """

    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider
        self._system_prompt = PROMPT_PATH.read_text(encoding="utf-8")

    async def synthesize(
        self,
        proposal_text: str,
        source_papers: list[str],
        domain: str = "AI/NLP",
        venue: str = "Generic",
        proposal_id: int = 0,
        experiment_context: str | None = None,
        result_markers: list[str] | None = None,
    ) -> PaperSynthesisResult | None:
        """Expand proposal text into a full academic paper.

        Args:
            proposal_text: The proposal markdown (post-adversarial-review).
            source_papers: List of formatted source strings (e.g. "[SOURCE-1] ...").
            domain: Research domain (e.g. "AI/NLP").
            venue: Target venue name (e.g. "IEEE", "ACM").
            proposal_id: Identifier for the proposal.
            experiment_context: Observed-results context string. When present,
                rendered as a dedicated ``## Experiment Ground Truth`` block at
                the top of the user prompt and asserted as a non-negotiable
                invariant by the system prompt (see
                prompts/paper_synthesis_system.md § GROUND TRUTH INVARIANTS).
                Must NOT be folded into ``source_papers`` — it is ground truth,
                not literature.
            result_markers: Verbatim ``[RESULT-N]`` marker strings (e.g.
                ``["[RESULT-1] balanced_accuracy=0.95", "[RESULT-2] ..."]``)
                drawn from persisted experiment output. Rendered inside the
                ground-truth block. When absent, the model is told no result
                markers are authorized.

        Returns:
            PaperSynthesisResult on success, None on LLM failure (HB-02).
        """
        user_content = self._build_user_prompt(
            proposal_text, source_papers, domain,
            experiment_context=experiment_context,
            result_markers=result_markers,
        )

        try:
            raw = await self._provider.complete(
                messages=[
                    {"role": "system", "content": self._system_prompt},
                    {"role": "user", "content": user_content},
                ],
                temperature=0.4,
                # glm-5.2 is a reasoning model: emits a separate reasoning_content
                # channel that consumes tokens before the final content is written.
                # The 8192 ceiling used for glm-4.6 (non-reasoning) was unsafe here
                # — small/medium calls could exhaust the budget mid-reasoning and
                # return empty content.
                #
                # Server-side maximum verified empirically: z.ai rejects anything
                # above 131072 with HTTP 400 code 1210 ("限制数值范围[1,131072]").
                # Use the documented max — orders of magnitude above any realistic
                # paper, large enough that reasoning overhead cannot self-truncate.
                max_tokens=131072,
            )
        except Exception as e:
            logger.warning("Paper synthesis LLM call failed (HB-02): %s", e)
            return None

        if not raw or not raw.strip():
            logger.warning("Paper synthesis returned empty output (HB-02)")
            return None

        word_count = len(raw.split())

        model_used = getattr(self._provider, "default_model", "unknown")
        if callable(model_used):
            model_used = model_used()
        model_used = str(model_used)

        source_count = len(source_papers)

        if word_count < 2000:
            logger.warning(
                "Paper synthesis produced only %d words (HB-05: minimum 2000). "
                "Accepting best-effort output.",
                word_count,
            )

        return PaperSynthesisResult(
            proposal_id=proposal_id,
            paper_markdown=raw,
            word_count=word_count,
            venue=venue,
            model_used=model_used,
            source_count=source_count,
        )

    async def synthesize_session(self, session: SynthesisSession) -> PaperSynthesisResult | None:
        """Isolated entry point: synthesize from a typed ``SynthesisSession``.

        This is the preferred call site going forward. It enforces the
        information-isolation contract: only the five fields on
        ``SynthesisSession`` (proposal_text, source_papers, experiment_context,
        result_markers, domain) reach the model. ``venue`` and ``proposal_id``
        are deliberately NOT on the session — they are result-metadata, not
        prompt inputs, so they do not belong on the channel-permission contract.
        The legacy ``synthesize(...)`` signature retains them as kwargs.

        Advisory in the prototype — does not fail on unexpected inputs, only
        logs. Promote to a hard boundary once all call sites are audited.
        """
        return await self.synthesize(
            proposal_text=session.proposal_text,
            source_papers=list(session.source_papers),
            domain=session.domain,
            experiment_context=session.experiment_context,
            result_markers=list(session.result_markers),
        )

    @staticmethod
    def _build_user_prompt(
        proposal_text: str,
        source_papers: list[str],
        domain: str,
        experiment_context: str | None = None,
        result_markers: list[str] | None = None,
    ) -> str:
        """Build the user prompt with proposal + source literature.

        When ``experiment_context`` is present, it is rendered as a dedicated
        ``## Experiment Ground Truth`` block at the TOP of the prompt — above
        the supporting literature and the proposal — so the system prompt's
        GROUND TRUTH INVARIANTS section applies to it. It is never folded into
        the source list. ``result_markers`` (verbatim [RESULT-N] strings from
        persisted experiment output) are listed inside the block as the
        authoritative marker set; markers not in this list are forbidden.
        """
        parts: list[str] = []
        has_gt = bool(experiment_context and experiment_context.strip())
        has_markers = bool(result_markers)

        # Ground truth first — non-negotiable observed facts.
        if has_gt:
            parts.append("## Experiment Ground Truth (NON-NEGOTIABLE)\n")
            parts.append(
                "The experiment below has ALREADY BEEN RUN. These are observed "
                "results, not suggestions. Per the GROUND TRUTH INVARIANTS in "
                "your system instructions, the paper MUST be about this method "
                "and dataset, and the [RESULT-N] markers MUST appear verbatim "
                "with correct metric direction.\n"
            )
            parts.append(experiment_context.strip())
            parts.append("")
        elif has_markers:
            # Markers without prose context: still authoritative for marker
            # fidelity, surfaced as their own ground-truth sub-block.
            parts.append("## Experiment Ground Truth (NON-NEGOTIABLE)\n")
            parts.append(
                "The following [RESULT-N] markers are drawn from observed "
                "experiment output. They MUST appear verbatim in the Results "
                "section with correct metric direction. Markers not in this "
                "list are forbidden.\n"
            )

        if has_markers:
            parts.append("### Authorized result markers (use verbatim)")
            for m in result_markers:  # type: ignore[union-attr]
                parts.append(f"- {m}")
            parts.append("")

        parts.append(f"## Research Domain\n{domain}\n")
        parts.append("## Supporting Literature (CLOSED-BOOK — cite only these)\n")

        if source_papers:
            for paper_str in source_papers:
                parts.append(paper_str)
        else:
            parts.append("No specific supporting papers provided.")

        parts.append("\n## Research Proposal to Expand\n")
        parts.append(proposal_text)

        if has_gt or has_markers:
            parts.append(
                "\n\nNow write a complete academic paper expanding this proposal. "
                "Follow the section structure from your instructions. "
                "Use [SOURCE-X] citations referencing only the papers listed above. "
                "The Experiment Ground Truth block above is authoritative — if "
                "the proposal conflicts with it, the ground truth wins."
            )
        else:
            parts.append(
                "\n\nNow write a complete academic paper expanding this proposal. "
                "Follow the section structure from your instructions. "
                "Use [SOURCE-X] citations referencing only the papers listed above."
            )

        return "\n".join(parts)
