"""Skill proposer and generator — EvoSkill-style proposer-generator split.

The proposer analyzes what went wrong and diagnoses failures.
The generator produces skill artifacts that address the diagnosis.

Reference: EvoSkill four-agent pipeline (skill_proposer, prompt_proposer,
skill_generator, prompt_generator) with feedback_history.md.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from backend.pipeline.skills.models import Skill

if TYPE_CHECKING:
    from backend.providers.base import LLMProvider

logger = logging.getLogger(__name__)

PROPOSER_PROMPT = """You are a skill proposer analyzing why a skill failed.

## Skill: {skill_name}
## Current Version Content:
{current_content}

## Feedback History:
{feedback}

## Recent Execution Trace:
{trace}

Diagnose what went wrong and suggest a specific improvement. Format:
DIAGNOSIS: <what went wrong>
SUGGESTION: <specific improvement to the skill content>"""

GENERATOR_PROMPT = """You are a skill generator. Based on the diagnosis and suggestion below,
generate an improved version of this skill.

## Skill: {skill_name}
## Domain: {domain}
## Current Version:
{current_content}

## Diagnosis:
{diagnosis}

## Suggestion:
{suggestion}

Generate the improved skill content as a clear, actionable prompt/instruction:"""


class SkillProposer:
    """Analyzes skill failures and produces diagnoses."""

    def __init__(self, provider: LLMProvider):
        self._provider = provider

    async def diagnose(
        self,
        skill: Skill,
        trace: str = "",
    ) -> tuple[str, str]:
        """Analyze skill and return (diagnosis, suggestion).

        Looks at the feedback history and recent execution trace to
        identify what went wrong and how to fix it.
        """
        current = skill.get_current()
        if not current:
            return "No version history", "Create initial skill content"

        # Build feedback summary from last N entries
        recent_feedback = skill.feedback_history[-5:]
        feedback_text = (
            "\n".join(
                f"- Iter {fb.iteration} [{'OK' if fb.success else 'FAIL'}] "
                f"score={fb.score:.2f}: {fb.observation}"
                for fb in recent_feedback
            )
            if recent_feedback
            else "No feedback history"
        )

        prompt = PROPOSER_PROMPT.format(
            skill_name=skill.name,
            current_content=current.content[:1000],
            feedback=feedback_text,
            trace=trace[:2000],
        )

        try:
            response = await self._provider.complete(
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at diagnosing skill failures in AI research pipelines.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=500,
            )
            return self._parse_diagnosis(response)
        except Exception as e:
            logger.error("SkillProposer failed: %s", e)
            return f"Proposer error: {e}", "Manual review needed"

    @staticmethod
    def _parse_diagnosis(response: str) -> tuple[str, str]:
        """Parse DIAGNOSIS and SUGGESTION from response."""
        diagnosis = ""
        suggestion = ""
        for line in response.split("\n"):
            line = line.strip()
            if line.upper().startswith("DIAGNOSIS:"):
                diagnosis = line[len("DIAGNOSIS:") :].strip()
            elif line.upper().startswith("SUGGESTION:"):
                suggestion = line[len("SUGGESTION:") :].strip()
        if not diagnosis:
            diagnosis = response[:200]
        if not suggestion:
            suggestion = "Review and improve based on feedback"
        return diagnosis, suggestion


class SkillGenerator:
    """Generates improved skill content based on proposer diagnoses."""

    def __init__(self, provider: LLMProvider):
        self._provider = provider

    async def generate(
        self,
        skill: Skill,
        diagnosis: str,
        suggestion: str,
    ) -> str:
        """Generate improved skill content."""
        current = skill.get_current()
        current_content = current.content if current else ""

        prompt = GENERATOR_PROMPT.format(
            skill_name=skill.name,
            domain=skill.domain,
            current_content=current_content[:1500],
            diagnosis=diagnosis,
            suggestion=suggestion,
        )

        try:
            response = await self._provider.complete(
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at writing effective AI skill prompts.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.5,
                max_tokens=1000,
            )
            return response.strip()
        except Exception as e:
            logger.error("SkillGenerator failed: %s", e)
            return current_content  # Return unchanged on failure


CREATE_FROM_TRACE_PROMPT = """You are analyzing an execution trace to extract a reusable skill.

## Execution Trace:
{trace}

## Domain: {domain}

Identify a repeated, successful pattern in this trace and extract it as a skill.

Provide your response in this exact format:
TRIGGER: <when should this skill activate>
STEPS: <numbered list of steps>
EXPECTED_OUTCOME: <what result should this skill produce>
DESCRIPTION: <one-line description of what this skill does>"""


class SkillCreator:
    """Creates new skills from observed execution patterns."""

    def __init__(self, provider: LLMProvider):
        self._provider = provider

    async def create_from_trace(
        self,
        trace: str,
        domain: str = "",
    ) -> Skill | None:
        """Generate a new skill from an observed execution pattern.

        Uses LLM to analyze the trace and extract trigger, steps, and expected outcome.
        Returns a new Skill object or None if no pattern is found.
        """
        prompt = CREATE_FROM_TRACE_PROMPT.format(
            trace=trace[:3000],
            domain=domain or "general",
        )

        try:
            response = await self._provider.complete(
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at identifying reusable patterns in AI research pipelines.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.4,
                max_tokens=800,
            )
            return self._parse_skill(response, domain)
        except Exception as e:
            logger.error("SkillCreator failed: %s", e)
            return None

    @staticmethod
    def _parse_skill(response: str, domain: str) -> Skill | None:
        """Parse LLM response into a Skill object."""
        sections: dict[str, str] = {}
        current = ""
        lines: list[str] = []

        for line in response.split("\n"):
            stripped = line.strip()
            if stripped.startswith("TRIGGER:"):
                if current:
                    sections[current] = "\n".join(lines).strip()
                current = "trigger"
                lines = [stripped[len("TRIGGER:"):].strip()]
            elif stripped.startswith("STEPS:"):
                if current:
                    sections[current] = "\n".join(lines).strip()
                current = "steps"
                lines = [stripped[len("STEPS:"):].strip()]
            elif stripped.startswith("EXPECTED_OUTCOME:"):
                if current:
                    sections[current] = "\n".join(lines).strip()
                current = "expected_outcome"
                lines = [stripped[len("EXPECTED_OUTCOME:"):].strip()]
            elif stripped.startswith("DESCRIPTION:"):
                if current:
                    sections[current] = "\n".join(lines).strip()
                current = "description"
                lines = [stripped[len("DESCRIPTION:"):].strip()]
            elif current:
                lines.append(line)

        if current:
            sections[current] = "\n".join(lines).strip()

        if not sections.get("trigger") or not sections.get("steps"):
            return None

        description = sections.get("description", "Auto-created skill from execution trace")
        skill_id = f"skill_{uuid.uuid4().hex[:8]}"
        name = description[:60].strip()

        # Build SKILL.md content
        content_parts = [f"# {name}", ""]
        content_parts.append("## Description")
        content_parts.append(description)
        content_parts.append("")
        content_parts.append("## Trigger")
        content_parts.append(sections["trigger"])
        content_parts.append("")
        content_parts.append("## Steps")
        content_parts.append(sections["steps"])
        content_parts.append("")
        if "expected_outcome" in sections:
            content_parts.append("## Expected Outcome")
            content_parts.append(sections["expected_outcome"])
            content_parts.append("")

        skill = Skill(
            id=skill_id,
            name=name,
            description=description,
            domain=domain,
            tags=["auto-created"],
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        skill.add_version("\n".join(content_parts))
        return skill
