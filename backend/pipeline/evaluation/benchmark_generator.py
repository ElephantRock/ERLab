"""Benchmark Generator — creates synthetic evaluation datasets from paper corpora.

BATCH-RAG-01/TASK-02: Uses LM Studio (local LLM) to generate research questions
from paper abstracts. Each question is paired with its source paper ID as
ground truth for retrieval evaluation.

Design: Generates N questions per paper abstract via structured LLM prompt.
Uses local qwen3-4b for zero-cost question generation.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from backend.pipeline.evaluation.benchmark_models import (
    BenchmarkDataset,
    BenchmarkQuestion,
)
from backend.pipeline.literature.models import Paper

if TYPE_CHECKING:
    from backend.providers.base import LLMProvider

logger = logging.getLogger(__name__)

QUESTION_GENERATION_PROMPT = """\
You are a research evaluation expert. Given the following research paper abstract, \
generate exactly {n_questions} specific research questions that are directly and \
explicitly answerable by reading this paper.

Requirements:
- Each question must be specific enough to identify this paper from others
- Questions should cover different aspects: methodology, findings, contributions
- Questions should be answerable by someone who has read the paper
- Format: Return a JSON array of objects with "question" and "answer" fields

Paper Title: {title}
Abstract: {abstract}

Return ONLY a JSON array, no other text:
[{{"question": "...", "answer": "..."}}]
"""

FALLBACK_QUESTIONS_PROMPT = """\
Generate {n_questions} research questions about this paper title: {title}

Return a JSON array:
[{{"question": "...", "answer": "..."}}]
"""


class BenchmarkGenerator:
    """Generates synthetic benchmark questions from a list of papers.

    Parameters
    ----------
    provider:
        LLMProvider for question generation. Should be a local model (LM Studio)
        for zero cost. Falls back to template-based generation if provider is None.
    questions_per_paper:
        Number of questions to generate per paper abstract.
    """

    def __init__(
        self,
        provider: LLMProvider | None = None,
        questions_per_paper: int = 3,
    ) -> None:
        self._provider = provider
        self._questions_per_paper = max(1, min(questions_per_paper, 5))

    async def generate(
        self,
        papers: list[Paper],
        domain: str = "",
        source_run_id: str | None = None,
    ) -> BenchmarkDataset:
        """Generate a benchmark dataset from a list of papers.

        For each paper, generates N questions using the LLM.
        Falls back to template questions if LLM is unavailable.
        """
        dataset_id = f"bench_{uuid.uuid4().hex[:8]}"
        questions: list[BenchmarkQuestion] = []

        for paper in papers:
            if not paper.abstract or len(paper.abstract) < 50:
                logger.debug("Skipping paper %s: abstract too short", paper.id)
                continue

            try:
                paper_questions = await self._generate_for_paper(paper)
                questions.extend(paper_questions)
            except Exception as e:
                logger.warning(
                    "Failed to generate questions for paper %s: %s",
                    paper.id,
                    str(e)[:100],
                )
                # Fallback: template question
                questions.append(
                    BenchmarkQuestion(
                        question=f"What are the key findings of '{paper.title}'?",
                        source_paper_id=paper.id,
                        source_paper_title=paper.title,
                        expected_answer="See paper abstract",
                        domain=domain,
                        difficulty="easy",
                    )
                )

        dataset = BenchmarkDataset(
            id=dataset_id,
            name=f"Benchmark for {domain or 'unknown domain'}",
            domain=domain,
            questions=questions,
            source_run_id=source_run_id,
            papers_count=len(papers),
            questions_per_paper=self._questions_per_paper,
        )

        logger.info(
            "Generated benchmark dataset %s: %d questions from %d papers",
            dataset_id,
            len(questions),
            len(papers),
        )
        return dataset

    async def _generate_for_paper(self, paper: Paper) -> list[BenchmarkQuestion]:
        """Generate questions for a single paper using LLM."""
        if self._provider is None:
            return self._template_questions(paper)

        prompt = QUESTION_GENERATION_PROMPT.format(
            n_questions=self._questions_per_paper,
            title=paper.title,
            abstract=paper.abstract or "",
        )

        try:
            messages = [{"role": "user", "content": prompt}]
            response = await self._provider.complete(messages)
            return self._parse_llm_response(response, paper)
        except Exception as e:
            logger.warning("LLM question generation failed: %s", str(e)[:100])
            return self._template_questions(paper)

    def _parse_llm_response(
        self, response: str, paper: Paper
    ) -> list[BenchmarkQuestion]:
        """Parse LLM response into BenchmarkQuestion objects."""
        # Try to extract JSON from response
        text = response.strip()
        # Remove markdown code fences if present
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1]) if len(lines) > 2 else text

        try:
            items = json.loads(text)
        except json.JSONDecodeError:
            # Try to find JSON array in response
            start = text.find("[")
            end = text.rfind("]")
            if start >= 0 and end > start:
                try:
                    items = json.loads(text[start : end + 1])
                except json.JSONDecodeError:
                    logger.warning("Could not parse LLM response as JSON")
                    return self._template_questions(paper)
            else:
                return self._template_questions(paper)

        questions = []
        for item in items[: self._questions_per_paper]:
            q_text = item.get("question", "").strip()
            answer = item.get("answer", "").strip()
            if q_text:
                questions.append(
                    BenchmarkQuestion(
                        question=q_text,
                        source_paper_id=paper.id,
                        source_paper_title=paper.title,
                        expected_answer=answer or "See paper abstract",
                        domain="",
                        difficulty="medium",
                    )
                )

        return questions if questions else self._template_questions(paper)

    def _template_questions(self, paper: Paper) -> list[BenchmarkQuestion]:
        """Fallback: generate template questions without LLM."""
        templates = [
            ("What is the main contribution of '{title}'?", "easy"),
            ("What methodology does '{title}' propose?", "medium"),
            ("What are the key findings of '{title}'?", "medium"),
            ("What problem does '{title}' address?", "easy"),
            ("What are the limitations of '{title}'?", "hard"),
        ]
        questions = []
        for i in range(min(self._questions_per_paper, len(templates))):
            template, difficulty = templates[i]
            questions.append(
                BenchmarkQuestion(
                    question=template.format(title=paper.title),
                    source_paper_id=paper.id,
                    source_paper_title=paper.title,
                    expected_answer=paper.abstract[:200] if paper.abstract else "See paper",
                    difficulty=difficulty,
                )
            )
        return questions
