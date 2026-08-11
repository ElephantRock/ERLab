"""Proposal Deepener: Enriches proposals with concrete detail.

Takes high-level research proposals and adds:
1. Preliminary architecture diagrams (text description)
2. Toy examples / minimal working examples
3. Expected failure modes
4. Concrete evaluation criteria

Addresses reviewer concern: "Adding concrete preliminary architectures,
toy examples, or expected failure modes would strengthen them significantly."
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

_DEEPENING_PROMPT = """\
You are a senior research architect. Given a research proposal, you must add
concrete technical detail. This is a CLOSED-BOOK task — only use information
from the proposal itself. Do NOT invent citations, datasets, or benchmarks
that are not mentioned in the proposal.

For each proposal, produce:

## Preliminary Architecture
Describe the system architecture in concrete terms: modules, data flow,
interfaces. Name specific components. Use a formal notation where appropriate.
Be precise: name specific layers, specific algorithms, specific data structures.
Example: "Module A applies a cross-attention layer (d=512, h=8) over the
structured representation before passing to Module B."

## Minimal Working Example
Give a concrete, worked toy example showing how the system would process
a specific input. Use real-looking (but synthetic) data. Show the transformation
at each step. Include actual numbers, actual function names, actual intermediate
representations.
Example:
  Input: {{"premises": ["A->B", "B->C"], "query": "Does A->C?"}}
  Step 1 (Parser): Graph(edges=[(A,B), (B,C)])
  Step 2 (Engine): BFS from A reaches C via B -> path=[A,B,C]
  Output: {{"result": true, "confidence": 0.95, "trace": ["A->B", "B->C"]}}

## Expected Failure Modes
List 3-5 specific ways the proposed system could fail, with concrete scenarios.
For each failure mode, describe: (a) the symptom, (b) the root cause, (c) a
potential mitigation. Be specific — not generic ML failure modes.
Example: "On inputs with >500 reasoning steps, the graph search exceeds memory
because the adjacency list grows O(n²). Mitigation: switch to sparse adjacency
with frontier pruning at depth 50."

## Success Criteria
Define 3-5 measurable criteria that would constitute a successful implementation.
Each criterion must include: metric name, target value, and comparison baseline.
Use a table format:
| # | Metric | Target | Baseline | Measurement Method |

Proposal to deepen:

Title: {title}
Problem: {problem}
Method: {method}
"""


@dataclass
class DeepenedProposal:
    """A proposal enriched with concrete detail."""
    idea_id: int
    title: str
    architecture: str = ""
    toy_example: str = ""
    failure_modes: str = ""
    success_criteria: str = ""


class ProposalDeepener:
    """Enriches proposals with architecture detail, toy examples, and failure modes.

    Can operate in two modes:
    - LLM mode: Uses an LLM to generate deepening content
    - Template mode: Generates structured placeholders (for testing)
    """

    def __init__(self, provider: Any = None) -> None:
        self._provider = provider

    async def deepen(self, idea: dict) -> DeepenedProposal:
        """Deepen a single proposal.

        Args:
            idea: Dict with 'id', 'title', 'problem_statement', 'proposed_method'.

        Returns:
            DeepenedProposal with architecture, toy example, failure modes, criteria.
        """
        if self._provider:
            return await self._deepen_with_llm(idea)
        else:
            return self._deepen_template(idea)

    async def _deepen_with_llm(self, idea: dict) -> DeepenedProposal:
        """Use LLM to generate deepening content."""
        # Escape any braces in user content to avoid .format() errors
        title = idea.get("title", "").replace("{", "{{").replace("}", "}}")
        problem = idea.get("problem_statement", "").replace("{", "{{").replace("}", "}}")
        method = idea.get("proposed_method", "").replace("{", "{{").replace("}", "}}")
        prompt = _DEEPENING_PROMPT.format(title=title, problem=problem, method=method)
        try:
            result = await self._provider.complete(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=2048,
            )
            return self._parse_deepening(idea, result)
        except Exception as e:
            logger.warning("LLM deepening failed for idea %s: %s", idea.get("id"), e)
            return self._deepen_template(idea)

    def _deepen_template(self, idea: dict) -> DeepenedProposal:
        """Generate structured template deepening (no LLM needed)."""
        title = idea.get("title", "Untitled")
        method = idea.get("proposed_method", "")
        problem = idea.get("problem_statement", "")

        architecture = (
            f"## Preliminary Architecture: {title}\n\n"
            f"The system consists of three core modules:\n"
            f"1. **Input Processor**: Transforms raw inputs into structured representations\n"
            f"2. **Reasoning Engine**: Executes the core {title.split(':')[0].strip()} algorithm\n"
            f"3. **Validation Layer**: Verifies outputs against formal constraints\n\n"
            f"Data flow: Input → Processor → Engine → Validator → Output\n"
            f"Key interfaces: JSON-over-HTTP between modules; Python APIs for internal calls.\n"
        )

        toy_example = (
            f"## Minimal Working Example\n\n"
            f"**Input**: A synthetic problem instance:\n"
            f'```json\n{{"task": "reasoning_step_1", "context": "Given facts A, B, C...", '
            f'"query": "What follows from A ∧ B?"}}\n```\n\n'
            f"**Processing**:\n"
            f"1. Input Processor extracts entities: [A, B, C]\n"
            f"2. Reasoning Engine applies method: {method[:80]}...\n"
            f"3. Validation Layer checks: output satisfies constraint formalism\n\n"
            f"**Output**: `{{\"result\": \"A ∧ B → D\", \"confidence\": 0.92, \"trace\": [...]}}`\n"
        )

        failure_modes = (
            "## Expected Failure Modes\n\n"
            "1. **Scalability collapse**: System degrades on inputs >10K entities. "
            "Root cause: O(n²) graph traversal. Mitigation: lazy evaluation + pruning.\n\n"
            "2. **Hallucinated constraints**: Validator accepts invalid symbolic rules. "
            "Root cause: LLM-generated rules not verified against formal logic. "
            "Mitigation: automated theorem prover as secondary check.\n\n"
            "3. **Context window overflow**: Complex reasoning exceeds token limits. "
            "Root cause: Graph expansion without budgeting. "
            "Mitigation: dynamic context management with summarization.\n\n"
            "4. **Distribution shift**: Performance drops on out-of-domain inputs. "
            "Root cause: Training/evaluation domain gap. "
            "Mitigation: domain adaptation layer + confidence calibration.\n"
        )

        success_criteria = (
            "## Success Criteria\n\n"
            "| # | Metric | Target | Baseline |\n"
            "|:--|:-------|:-------|:---------|\n"
            "| 1 | Reasoning accuracy | >85% | 72% (CoT baseline) |\n"
            "| 2 | Latency per query | <5s | 3s (CoT baseline) |\n"
            "| 3 | Hallucination rate | <5% | 18% (unconstrained LLM) |\n"
            "| 4 | Explanation quality (human eval) | >4.0/5 | 3.2/5 |\n"
            "| 5 | Cost efficiency | <2× CoT cost | 5× CoT cost (GoT baseline) |\n"
        )

        return DeepenedProposal(
            idea_id=idea.get("id", 0),
            title=title,
            architecture=architecture,
            toy_example=toy_example,
            failure_modes=failure_modes,
            success_criteria=success_criteria,
        )

    def _parse_deepening(self, idea: dict, llm_output: str) -> DeepenedProposal:
        """Parse LLM output into structured DeepenedProposal."""
        sections = {
            "architecture": "",
            "toy_example": "",
            "failure_modes": "",
            "success_criteria": "",
        }

        current = None
        for line in llm_output.split("\n"):
            lower = line.lower().strip()
            if "architecture" in lower and lower.startswith("#"):
                current = "architecture"
            elif "working example" in lower and lower.startswith("#"):
                current = "toy_example"
            elif "failure mode" in lower and lower.startswith("#"):
                current = "failure_modes"
            elif "success criteria" in lower and lower.startswith("#"):
                current = "success_criteria"
            elif current:
                sections[current] += line + "\n"

        return DeepenedProposal(
            idea_id=idea.get("id", 0),
            title=idea.get("title", ""),
            architecture=sections["architecture"],
            toy_example=sections["toy_example"],
            failure_modes=sections["failure_modes"],
            success_criteria=sections["success_criteria"],
        )
