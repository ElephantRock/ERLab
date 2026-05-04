"""Cross-run recombination API — proposes novel ideas by combining top
ideas from different pipeline runs (BATCH-65/TASK-02).

POST /recombination/propose
  Body: {"run_ids": [1, 2], "max_ideas": 5}
  Response: {"recombined_ideas": [...], "method_dna": [...]}
"""

from __future__ import annotations

import json
import logging
from itertools import combinations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.api.errors import BadRequestError
from backend.pipeline.generation.models import IdeaCandidate

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Request / Response schemas ──────────────────────────────────


class RecombinationRequest(BaseModel):
    """Request body for cross-run recombination."""

    run_ids: list[int] = Field(
        ..., min_length=2, description="Two or more pipeline run IDs to recombine"
    )
    max_ideas: int = Field(
        default=5, ge=1, le=10, description="Max recombined ideas to return (capped at 10)"
    )


# ── Endpoint ────────────────────────────────────────────────────


@router.post(
    "/propose",
    summary="Propose recombined ideas from multiple runs",
    description=(
        "Combine the top ideas from two or more pipeline runs into novel "
        "recombined ideas with full source traceability. Each run must have "
        "at least 2 ideas (HB-01). Maximum 10 recombined ideas per request (HB-02)."
    ),
)
async def propose_recombination(request: RecombinationRequest):
    """Cross-run recombination endpoint.

    Steps:
      1. Validate that every run_id has ≥2 ideas (HB-01).
      2. Load top ideas per run, sorted by overall_score descending.
      3. Pair ideas from *different* runs and recombine via IdeaRecombinator.
      4. Cap output at request.max_ideas (max 10, HB-02).
      5. Store recombined ideas in DB with source_idea_ids traceability.
      6. Return results with method DNA for each parent idea.
    """
    from backend.db.crud import create_idea, get_ideas_for_run
    from backend.db.database import get_session
    from backend.pipeline.generation.recombination import IdeaRecombinator
    from backend.providers.provider_factory import create_provider

    max_ideas = min(request.max_ideas, 10)  # HB-02 hard cap

    # ── Step 1–2: Load ideas per run ────────────────────────────
    run_ideas: dict[int, list] = {}
    with get_session() as session:
        for run_id in request.run_ids:
            ideas = get_ideas_for_run(session, run_id)
            if len(ideas) < 2:  # HB-01
                raise BadRequestError(
                    detail=f"Run {run_id} has {len(ideas)} idea(s); "
                           f"at least 2 are required for recombination",
                    hint="Ensure each run has completed and produced ≥2 ideas",
                )
            # Sort by overall_score descending; treat None as -1
            run_ideas[run_id] = sorted(
                ideas,
                key=lambda i: i.overall_score if i.overall_score is not None else -1,
                reverse=True,
            )

    # ── Step 3: Build cross-run pairs ───────────────────────────
    # Pick the top idea from each run and form pairs between runs.
    top_per_run = {run_id: ideas[0] for run_id, ideas in run_ideas.items()}
    pairs: list[tuple[int, int]] = list(combinations(request.run_ids, 2))

    # ── Step 4–5: Recombine via IdeaRecombinator ────────────────
    provider = create_provider()
    recombinator = IdeaRecombinator(provider)

    recombined_ideas: list[dict] = []
    method_dna_records: list[dict] = []
    seen_parents: set[tuple[int, int]] = set()

    for run_a, run_b in pairs:
        if len(recombined_ideas) >= max_ideas:
            break

        parent_a = top_per_run[run_a]
        parent_b = top_per_run[run_b]

        pair_key = (min(parent_a.id, parent_b.id), max(parent_a.id, parent_b.id))
        if pair_key in seen_parents:
            continue
        seen_parents.add(pair_key)

        candidate_a = IdeaCandidate(
            title=parent_a.title,
            problem_statement=parent_a.problem_statement,
            proposed_method=parent_a.proposed_method,
            expected_contributions=parent_a.expected_contributions or "",
        )
        candidate_b = IdeaCandidate(
            title=parent_b.title,
            problem_statement=parent_b.problem_statement,
            proposed_method=parent_b.proposed_method,
            expected_contributions=parent_b.expected_contributions or "",
        )

        child = await recombinator.recombine(candidate_a, candidate_b)

        # Store in DB with source_idea_ids traceability
        with get_session() as session:
            stored = create_idea(
                session,
                title=child.title,
                problem_statement=child.problem_statement,
                proposed_method=child.proposed_method,
                expected_contributions=child.expected_contributions,
                source_idea_ids=json.dumps([parent_a.id, parent_b.id]),
            )

        recombined_ideas.append({
            "id": stored.id,
            "title": child.title,
            "problem_statement": child.problem_statement,
            "proposed_method": child.proposed_method,
            "expected_contributions": child.expected_contributions,
            "source_idea_ids": [parent_a.id, parent_b.id],
        })

        # Method DNA for each parent
        method_dna_records.append(_extract_dna(parent_a))
        method_dna_records.append(_extract_dna(parent_b))

    logger.info(
        "Recombination produced %d ideas from %d runs",
        len(recombined_ideas),
        len(request.run_ids),
    )

    return {
        "recombined_ideas": recombined_ideas,
        "method_dna": method_dna_records,
    }


# ── Helpers ─────────────────────────────────────────────────────


def _extract_dna(idea) -> dict:
    """Extract lightweight method DNA from a DB Idea row.

    Falls back gracefully when fields are missing or empty.
    """
    method_text = idea.proposed_method or ""
    keywords = _extract_keywords(method_text)

    return {
        "idea_id": idea.id,
        "title": idea.title,
        "core_technique": _first_sentence(method_text),
        "domain": idea.domain or "unknown",
        "evaluation_approach": "",
        "method_keywords": keywords,
    }


def _first_sentence(text: str) -> str:
    """Return the first sentence of *text* (up to the first period)."""
    idx = text.find(".")
    if idx != -1:
        return text[: idx + 1].strip()
    return text[:200].strip() if text else "unknown"


def _extract_keywords(text: str, max_keywords: int = 5) -> list[str]:
    """Extract candidate keywords from method text.

    Uses a simple heuristic: split on whitespace, keep tokens
    that are longer than 4 characters and not common stop-words.
    """
    stop_words = {
        "which", "their", "about", "would", "could", "should",
        "these", "those", "using", "based", "through", "between",
    }
    tokens = text.lower().split()
    seen: set[str] = set()
    keywords: list[str] = []
    for token in tokens:
        clean = token.strip(".,;:()[]{}")
        if len(clean) > 4 and clean not in stop_words and clean not in seen:
            seen.add(clean)
            keywords.append(clean)
            if len(keywords) >= max_keywords:
                break
    return keywords
