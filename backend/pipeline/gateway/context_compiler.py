"""Context compiler — builds bounded prompts that fit the model's context.

Every LLM call should go through the ContextCompiler, not just oversized ones.
This makes prompt construction deterministic and testable.

The compiler takes:
- Instructions (system prompt, task description)
- Evidence (papers, gaps, ideas — the RAG context)
- Current artifact (existing draft, proposal)
- Schema (if structured output)

And produces a message list that fits within the token budget.

Strategies (in order of preference):
1. Truncate evidence (keep most relevant, drop rest)
2. Summarize evidence (replace full abstracts with summaries)
3. Reduce output budget (shorter expected response)
4. Section-wise execution (split into independent calls)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from backend.pipeline.gateway.token_budget import TokenBudget, TokenBudgeter

logger = logging.getLogger(__name__)


@dataclass
class CompiledPrompt:
    """Result of context compilation."""

    messages: list[dict]
    budget: TokenBudget
    strategy_used: str = "full"  # "full" | "truncated" | "summarized" | "section_wise"
    evidence_dropped: int = 0
    tokens_saved: int = 0


class ContextCompiler:
    """Compiles task state into a bounded prompt that fits the model's context.

    Usage:
        compiler = ContextCompiler(budgeter)
        compiled = compiler.compile(
            instructions="Generate a proposal...",
            evidence=[paper_abstract_1, paper_abstract_2, ...],
            max_output_tokens=4096,
            context_window=8192,
        )
        # compiled.messages fits within budget
    """

    def __init__(self, budgeter: TokenBudgeter):
        self._budgeter = budgeter

    def compile(
        self,
        instructions: str,
        evidence: list[str] | None = None,
        current_artifact: str = "",
        schema: str | None = None,
        max_output_tokens: int = 4096,
        context_window: int = 4096,
        system_role: str = "system",
        user_role: str = "user",
    ) -> CompiledPrompt:
        """Build messages that fit within the token budget.

        Args:
            instructions: The task instructions (system prompt).
            evidence: List of evidence strings (paper abstracts, gap descriptions).
            current_artifact: Existing content to include (draft, proposal).
            schema: JSON schema description (if structured output).
            max_output_tokens: Desired output token budget.
            context_window: Model's total context capacity.
            system_role: Role name for system messages.
            user_role: Role name for user messages.

        Returns:
            CompiledPrompt with messages that fit within budget.
        """
        evidence = evidence or []

        # Step 1: Build the full prompt
        messages = self._build_messages(
            instructions, evidence, current_artifact, schema,
            system_role, user_role,
        )

        # Step 2: Check budget
        budget = self._budgeter.check(messages, max_output_tokens, context_window)

        if budget.fits:
            return CompiledPrompt(
                messages=messages,
                budget=budget,
                strategy_used="full",
            )

        # Step 3: Try truncating evidence
        messages, dropped, saved = self._truncate_evidence(
            instructions, evidence, current_artifact, schema,
            max_output_tokens, context_window,
            system_role, user_role,
        )
        budget = self._budgeter.check(messages, max_output_tokens, context_window)

        if budget.fits:
            return CompiledPrompt(
                messages=messages,
                budget=budget,
                strategy_used="truncated",
                evidence_dropped=dropped,
                tokens_saved=saved,
            )

        # Step 4: Try reducing output budget
        reduced_output = max(256, budget.available_for_output)
        budget = TokenBudget(
            input_tokens=budget.input_tokens,
            output_reserve=reduced_output,
            context_window=context_window,
        )

        if budget.fits:
            logger.info(
                "Reduced output budget: %d → %d tokens",
                max_output_tokens, reduced_output,
            )
            return CompiledPrompt(
                messages=messages,
                budget=budget,
                strategy_used="truncated+reduced_output",
                evidence_dropped=dropped,
                tokens_saved=saved,
            )

        # Step 5: Aggressive truncation — keep only instructions + minimal evidence
        messages = self._build_messages(
            instructions,
            evidence[:2] if evidence else [],  # Keep only 2 evidence items
            "",  # Drop current artifact
            None,  # Drop schema from prompt
            system_role, user_role,
        )
        budget = self._budgeter.check(messages, 512, context_window)

        if budget.fits:
            return CompiledPrompt(
                messages=messages,
                budget=budget,
                strategy_used="aggressive_truncate",
                evidence_dropped=len(evidence) - min(2, len(evidence)),
                tokens_saved=budget.overflow_tokens,
            )

        # Step 6: Emergency — instructions only
        messages = [
            {system_role: instructions[:int(context_window * 0.5)]},
        ]
        budget = self._budgeter.check(messages, 256, context_window)

        return CompiledPrompt(
            messages=messages,
            budget=budget,
            strategy_used="emergency",
            evidence_dropped=len(evidence),
            tokens_saved=budget.overflow_tokens,
        )

    def _build_messages(
        self,
        instructions: str,
        evidence: list[str],
        current_artifact: str,
        schema: str | None,
        system_role: str,
        user_role: str,
    ) -> list[dict]:
        """Build the message list from components."""
        messages = []

        # System message with instructions
        system_content = instructions
        if schema:
            system_content += f"\n\nRespond in this JSON schema:\n{schema}"
        messages.append({"role": system_role, "content": system_content})

        # Evidence block
        if evidence:
            evidence_text = "\n\n---\n\n".join(
                f"[E{i+1}] {e}" for i, e in enumerate(evidence)
            )
            messages.append({
                "role": user_role,
                "content": f"Research evidence:\n\n{evidence_text}",
            })

        # Current artifact
        if current_artifact:
            messages.append({
                "role": user_role,
                "content": f"Current draft:\n\n{current_artifact}",
            })

        # Task prompt
        messages.append({
            "role": user_role,
            "content": "Proceed with the task as instructed above.",
        })

        return messages

    def _truncate_evidence(
        self,
        instructions: str,
        evidence: list[str],
        current_artifact: str,
        schema: str | None,
        max_output_tokens: int,
        context_window: int,
        system_role: str,
        user_role: str,
    ) -> tuple[list[dict], int, int]:
        """Truncate evidence items to fit within budget.

        Drops the longest evidence items first (they're least likely to be
        the most relevant — the reranker already sorted by relevance).

        Returns:
            (messages, evidence_dropped, tokens_saved)
        """
        if not evidence:
            messages = self._build_messages(
                instructions, [], current_artifact, schema,
                system_role, user_role,
            )
            return messages, 0, 0

        # Sort evidence by length (longest first) — drop those first
        indexed = [(len(e), i, e) for i, e in enumerate(evidence)]
        indexed.sort(reverse=True)  # longest first

        # Try progressively fewer evidence items
        for n_keep in range(len(evidence) - 1, 0, -1):
            # Keep the n_keep shortest items (most likely relevant after reranking)
            kept_indices = {idx for _, idx, _ in indexed[-n_keep:]}
            kept_evidence = [evidence[i] for i in sorted(kept_indices)]

            messages = self._build_messages(
                instructions, kept_evidence, current_artifact, schema,
                system_role, user_role,
            )
            budget = self._budgeter.check(messages, max_output_tokens, context_window)

            if budget.fits:
                dropped = len(evidence) - n_keep
                saved = budget.overflow_tokens
                return messages, dropped, saved

        # Even 1 evidence item doesn't fit — return empty evidence
        messages = self._build_messages(
            instructions, [], current_artifact, schema,
            system_role, user_role,
        )
        return messages, len(evidence), 0

    def estimate_evidence_budget(
        self,
        instructions: str,
        current_artifact: str,
        max_output_tokens: int,
        context_window: int,
        avg_evidence_tokens: int = 200,
    ) -> int:
        """How many evidence items can fit given other constraints?

        Useful for pre-filtering evidence before compilation.
        """
        # Build messages without evidence to get baseline
        baseline = self._build_messages(
            instructions, [], current_artifact, None, "system", "user",
        )
        baseline_budget = self._budgeter.check(baseline, max_output_tokens, context_window)

        available = baseline_budget.available_for_input - baseline_budget.input_tokens
        if available <= 0:
            return 0

        # Each evidence item needs avg_evidence_tokens + overhead
        per_item = avg_evidence_tokens + 20  # separator + label
        return max(0, available // per_item)
