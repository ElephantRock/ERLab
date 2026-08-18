"""Phase 7 / 7B — unified paper synthesis service.

One internal service used by:
  - normal PaperSynthesisStage (pipeline flow)
  - automatic empirical recovery (on B-08 timeout)
  - the Phase 6 operator recovery command (paper_recovery.py)

The service owns:
  - source/result context construction
  - budget accounting (SynthesisBudget + BudgetTimer)
  - monolithic attempt (bounded)
  - section fallback (bounded, with checkpoint callbacks)
  - structural validation (all required sections present)
  - result/source marker collection
  - evaluation handoff

Does NOT own:
  - proposal selection (that's the stage's responsibility)
  - persistence (the caller persists the result)
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from collections.abc import Callable
from dataclasses import dataclass, field

from backend.pipeline.gateway.transport import GatewayTransportError
from backend.pipeline.synthesis.paper_synthesizer import PaperSynthesizer
from backend.pipeline.synthesis.section_wise_synthesizer import (
    DEFAULT_SECTIONS,
    SectionWiseSynthesizer,
)
from backend.pipeline.synthesis.synthesis_budget import BudgetTimer, SynthesisBudget
from backend.providers.base import LLMProvider

logger = logging.getLogger(__name__)

# Required sections for a valid empirical paper (Phase 7 spec)
REQUIRED_SECTIONS = [
    "abstract", "introduction", "related_work", "proposed_method",
    "evaluation_plan", "discussion", "conclusion",
]


@dataclass
class SynthesisServiceResult:
    """Result of a unified synthesis attempt."""

    success: bool
    paper_markdown: str = ""
    word_count: int = 0
    synthesis_strategy: str = ""  # monolithic | section_wise | recovered
    sections_generated: int = 0
    sections_total: int = len(DEFAULT_SECTIONS)
    workflow_state: str = "failed"  # not_requested → ... → ready | blocked | failed
    source_map: list[dict] = field(default_factory=list)
    error: str | None = None
    section_checkpoints: dict[str, dict] = field(default_factory=dict)


def compute_input_fingerprint(
    proposal_hash: str,
    experiment_manifest_hash: str,
    source_map_hash: str,
    synthesis_prompt_version: str = "v1",
    synthesis_config_hash: str = "",
) -> str:
    """Compute a deterministic input fingerprint for section checkpoint reuse.

    Excludes content hash — the fingerprint determines whether inputs are the
    same, not whether the output is the same.
    """
    parts = [
        proposal_hash,
        experiment_manifest_hash,
        source_map_hash,
        synthesis_prompt_version,
        synthesis_config_hash,
    ]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


async def synthesize_paper(
    provider: LLMProvider,
    proposal_text: str,
    source_papers: list[str],
    source_ids: list[str],
    domain: str,
    proposal_id: int,
    budget: SynthesisBudget | None = None,
    experiment_context: str | None = None,
    result_markers: list[str] | None = None,
    existing_checkpoints: dict[str, dict] | None = None,
    checkpoint_callback: Callable[[str, dict], None] | None = None,
    context_window: int = 128000,
    synthesizer_override=None,
) -> SynthesisServiceResult:
    """Unified paper synthesis with budget accounting and checkpointing.

    This is the single entry point for all paper synthesis: pipeline stage,
    automatic recovery, and manual CLI recovery.

    Args:
        provider: LLM provider for generation.
        proposal_text: The proposal markdown.
        source_papers: Formatted source strings with [SOURCE-N] citations.
        source_ids: Ordered literature Paper.id list for source map.
        domain: Research domain.
        proposal_id: Proposal identifier (metadata; does not enter the prompt).
        budget: Synthesis time budget. Defaults to SynthesisBudget().
        experiment_context: Observed-results prose. Rendered as a non-negotiable
            ## Experiment Ground Truth block at the top of the user prompt.
        result_markers: Verbatim [RESULT-N] marker strings from persisted
            experiment output. Listed inside the ground-truth block as the
            authoritative marker set.
        existing_checkpoints: Previously persisted section checkpoints.
        checkpoint_callback: Called with (section_id, checkpoint_dict) after
            each section completes. Used for atomic persistence.
        context_window: Provider context window size.
        synthesizer_override: Optional pre-built PaperSynthesizer for the
            monolithic attempt (used by PaperSynthesisStage to honor an
            injected synthesizer, e.g. in tests). When None the service
            constructs its own from ``provider``.
    """
    if budget is None:
        budget = SynthesisBudget()

    timer = BudgetTimer(budget)
    # Ground-truth re-injection (phase-8 fix): experiment_context is NO LONGER
    # folded into source_papers. It is passed as a dedicated argument and
    # rendered as a non-negotiable ## Experiment Ground Truth block at the top
    # of the user prompt (see PaperSynthesizer._build_user_prompt and the
    # GROUND TRUTH INVARIANTS section of the system prompt). Folding it into
    # sources caused phase-8 scope fabrication: the experiment was treated as
    # supplementary literature while the proposal narrative took primacy.
    synthesis_sources = list(source_papers)

    # ── Step 1: Try monolithic synthesis ───────────────────────────
    logger.info(
        "Synthesis service: monolithic attempt (budget=%ss, remaining=%.0fs)",
        budget.monolithic_attempt_timeout, timer.monolithic_remaining,
    )

    try:
        synthesizer = synthesizer_override if synthesizer_override is not None else PaperSynthesizer(provider)
        # Route through SynthesisSession to enforce the information-isolation
        # contract (phase-8 fix): only typed inputs reach the model.
        from backend.pipeline.synthesis.paper_synthesizer import SynthesisSession
        session = SynthesisSession(
            proposal_text=proposal_text,
            source_papers=tuple(synthesis_sources),
            domain=domain,
            experiment_context=experiment_context,
            result_markers=tuple(result_markers) if result_markers else (),
        )
        result = await asyncio.wait_for(
            synthesizer.synthesize_session(session),
            timeout=timer.monolithic_remaining,
        )
    except (TimeoutError, asyncio.CancelledError):
        logger.warning("Monolithic synthesis timed out after %.0fs", timer.elapsed)
        result = None
    except GatewayTransportError:
        # Case-4 R2 (adjudicated GENERIC_PRODUCT_DEFECT, 2026-08-18): a
        # typed provider/transport failure must keep its identity. The Q2
        # stage-loop terminalization converts it to FAILED_EXECUTION; it
        # must never become fallback output on a dead provider.
        raise
    except Exception as e:
        logger.warning("Monolithic synthesis failed: %s", e)
        result = None

    if result is not None and result.paper_markdown and len(result.paper_markdown.split()) >= 200:
        # Monolithic succeeded
        from backend.pipeline.stages import PaperSynthesisStage
        source_map = PaperSynthesisStage.build_source_map(source_ids, result.paper_markdown)
        return SynthesisServiceResult(
            success=True,
            paper_markdown=result.paper_markdown,
            word_count=result.word_count,
            synthesis_strategy="monolithic",
            sections_generated=len(DEFAULT_SECTIONS),
            sections_total=len(DEFAULT_SECTIONS),
            workflow_state="ready",
            source_map=source_map,
        )

    # ── Step 2: Fall back to section-wise with checkpoints ─────────
    if not timer.should_try_fallback:
        logger.warning(
            "No time remaining for section-wise fallback (elapsed=%.0fs, total=%.0fs)",
            timer.elapsed, budget.total_workflow_timeout,
        )
        return SynthesisServiceResult(
            success=False,
            workflow_state="failed",
            error=f"Monolithic failed and no fallback time remaining (elapsed={timer.elapsed:.0f}s)",
        )

    logger.info(
        "Synthesis service: section-wise fallback (remaining=%.0fs)",
        timer.fallback_remaining,
    )

    section_synth = SectionWiseSynthesizer(
        provider=provider,
        context_window=context_window,
    )

    # Build checkpoint-aware section list
    checkpoints = dict(existing_checkpoints or {})
    completed_sections: dict[str, dict] = {}

    # Generate outline
    try:
        outline = await asyncio.wait_for(
            section_synth._generate_outline(proposal_text, domain),
            timeout=min(60.0, timer.section_remaining),
        )
    except (TimeoutError, asyncio.CancelledError):
        logger.warning("Outline generation timed out")
        outline = "Standard academic paper structure"
    except GatewayTransportError:
        # Case-4 R2 (adjudicated GENERIC_PRODUCT_DEFECT, 2026-08-18): a
        # typed provider/transport failure must keep its identity. The Q2
        # stage-loop terminalization converts it to FAILED_EXECUTION; it
        # must never become fallback output on a dead provider.
        raise
    except Exception as e:
        logger.warning("Outline generation failed: %s", e)
        outline = "Standard academic paper structure"

    source_text = "\n".join(synthesis_sources[:20])
    proposal_summary = section_synth._summarize_proposal(proposal_text)

    for section_id, section_title, target_words in DEFAULT_SECTIONS:
        # Check for existing checkpoint with matching fingerprint
        existing = checkpoints.get(section_id)
        if existing and existing.get("input_fingerprint"):
            # Reuse if fingerprint matches (caller validates this)
            completed_sections[section_id] = existing
            logger.info("Section '%s': reused from checkpoint", section_title)
            continue

        section_budget = timer.section_remaining
        if section_budget < 10.0:
            logger.warning(
                "Insufficient time for section '%s' (remaining=%.0fs) — stopping",
                section_title, timer.fallback_remaining,
            )
            break

        try:
            relevant_sources = section_synth._select_relevant_sources(
                source_text, section_id, section_title, outline,
            )
            draft = await asyncio.wait_for(
                section_synth._generate_section(
                    section_id=section_id,
                    section_title=section_title,
                    target_words=target_words,
                    outline=outline,
                    proposal_summary=proposal_summary,
                    relevant_sources=relevant_sources,
                    domain=domain,
                    experiment_context=experiment_context,
                    result_markers=result_markers,
                ),
                timeout=section_budget,
            )

            section_data = {
                "section_id": section_id,
                "title": section_title,
                "content": draft.content,
                "word_count": draft.word_count,
                "citations_used": draft.citations_used,
                "model_used": draft.model_used,
                "content_hash": hashlib.sha256(draft.content.encode()).hexdigest()[:16],
                "completed_at": str(asyncio.get_event_loop().time()),
            }
            completed_sections[section_id] = section_data

            # Invoke checkpoint callback for atomic persistence
            if checkpoint_callback:
                checkpoint_callback(section_id, section_data)

            logger.info(
                "Section '%s': %d words, %d citations",
                section_title, draft.word_count, len(draft.citations_used),
            )

        except (TimeoutError, asyncio.CancelledError):
            logger.warning(
                "Section '%s' timed out — checkpointing %d/%d sections",
                section_title, len(completed_sections), len(DEFAULT_SECTIONS),
            )
            break
        except Exception as e:
            logger.warning("Section '%s' failed (non-fatal): %s", section_title, e)

    # ── Step 3: Structural validation ──────────────────────────────
    completed_section_ids = set(completed_sections.keys())
    missing = [s for s in REQUIRED_SECTIONS if s not in completed_section_ids]
    if missing:
        logger.warning(
            "Structural validation failed: missing required sections %s "
            "(completed: %d/%d)",
            missing, len(completed_sections), len(DEFAULT_SECTIONS),
        )
        return SynthesisServiceResult(
            success=False,
            workflow_state="partial_checkpoint",
            section_checkpoints=completed_sections,
            error=f"Missing required sections: {missing}",
        )

    # ── Step 4: Assemble ───────────────────────────────────────────
    # Build SectionDraft objects from checkpoint data for assembly
    from backend.pipeline.synthesis.section_wise_synthesizer import SectionDraft
    section_drafts = []
    for section_id, _, _ in DEFAULT_SECTIONS:
        data = completed_sections.get(section_id)
        if data:
            section_drafts.append(SectionDraft(
                section_id=section_id,
                title=data["title"],
                content=data["content"],
                word_count=data["word_count"],
                citations_used=data.get("citations_used", []),
                model_used=data.get("model_used", "unknown"),
            ))

    paper_md = section_synth._assemble_paper(
        section_drafts, outline, domain, "Generic", len(synthesis_sources),
    )
    total_words = len(paper_md.split())

    from backend.pipeline.stages import PaperSynthesisStage
    source_map = PaperSynthesisStage.build_source_map(source_ids, paper_md)

    strategy = "section_wise" if not existing_checkpoints else "recovered"

    return SynthesisServiceResult(
        success=True,
        paper_markdown=paper_md,
        word_count=total_words,
        synthesis_strategy=strategy,
        sections_generated=len(section_drafts),
        sections_total=len(DEFAULT_SECTIONS),
        workflow_state="ready",
        source_map=source_map,
        section_checkpoints=completed_sections,
    )
