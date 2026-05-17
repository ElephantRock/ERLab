"""Stage evaluation cases — machine-readable test definitions.

Each case defines a prompt, expected context, gold answer,
and metadata for stage-specific model evaluation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml

_VALID_DIFFICULTIES = frozenset({"easy", "medium", "hard"})


@dataclass
class GoldAnswer:
    """Expected output for a stage eval case."""

    expected_fields: dict[str, Any] = field(default_factory=dict)
    expected_keys: list[str] = field(default_factory=list)
    inclusion_set: list[str] = field(default_factory=list)   # for filtering
    exclusion_set: list[str] = field(default_factory=list)   # for filtering
    planted_errors: list[dict[str, Any]] = field(default_factory=list)  # for adversarial
    notes: str = ""


@dataclass
class StageEvalCase:
    """A single test case for stage-specific model evaluation.

    The evaluation unit is: model × stage × schema × budget × hardware.
    """

    case_id: str                      # e.g. "query_generation-001"
    stage: str                        # e.g. "query_generation"
    prompt_template: str              # The actual prompt to send
    input_context: dict = field(default_factory=dict)  # Papers, gaps, etc.
    schema_path: str | None = None    # Expected output JSON schema
    gold_path: str | None = None      # Gold answer file (relative to case dir)
    gold: GoldAnswer | None = None    # Inline gold answer (alternative to file)
    input_token_budget: int = 4096
    output_token_budget: int = 2048
    difficulty: str = "medium"        # easy | medium | hard
    requires_grounding: bool = False
    required_capabilities: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    def __post_init__(self):
        if self.difficulty not in _VALID_DIFFICULTIES:
            raise ValueError(
                f"difficulty must be one of {_VALID_DIFFICULTIES}, "
                f"got '{self.difficulty}'"
            )

    def validate(self) -> list[str]:
        """Validate case fields. Returns list of errors (empty = valid)."""
        errors: list[str] = []

        if not self.case_id:
            errors.append("case_id is required")
        if not self.stage:
            errors.append("stage is required")
        if not self.prompt_template:
            errors.append("prompt_template is required")
        if self.input_token_budget <= 0:
            errors.append("input_token_budget must be > 0")
        if self.output_token_budget <= 0:
            errors.append("output_token_budget must be > 0")

        # Grounding cases must have gold answers
        if self.requires_grounding and self.gold is None and self.gold_path is None:
            errors.append(
                "Gold answer required when requires_grounding=True "
                "(set gold or gold_path)"
            )

        return errors

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d

    def to_yaml(self) -> str:
        return yaml.dump(self.to_dict(), default_flow_style=False, sort_keys=False)

    @classmethod
    def from_yaml(cls, text: str) -> StageEvalCase:
        data = yaml.safe_load(text)
        if not isinstance(data, dict):
            raise ValueError("YAML must contain a mapping")
        # Convert gold dict to GoldAnswer if present
        if "gold" in data and isinstance(data["gold"], dict):
            data["gold"] = GoldAnswer(**{
                k: v for k, v in data["gold"].items()
                if k in GoldAnswer.__dataclass_fields__
            })
        return cls(**{
            k: v for k, v in data.items()
            if k in cls.__dataclass_fields__
        })

    @classmethod
    def from_yaml_file(cls, path: str | Path) -> StageEvalCase:
        return cls.from_yaml(Path(path).read_text(encoding="utf-8"))

    def to_yaml_file(self, path: str | Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(self.to_yaml(), encoding="utf-8")


def load_suite(stage: str, eval_dir: str | Path) -> list[StageEvalCase]:
    """Load all eval cases for a given stage.

    Args:
        stage: Stage name (e.g. "query_generation").
        eval_dir: Root directory containing stage subdirectories.

    Returns:
        List of StageEvalCase for the given stage.
    """
    stage_dir = Path(eval_dir) / stage
    if not stage_dir.is_dir():
        return []

    cases = []
    for yaml_file in sorted(stage_dir.glob("*.yaml")):
        try:
            case = StageEvalCase.from_yaml_file(yaml_file)
            # Only include cases for the requested stage
            if case.stage == stage:
                cases.append(case)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(
                "Failed to load eval case %s: %s", yaml_file, e
            )

    return cases


def load_all_suites(eval_dir: str | Path) -> dict[str, list[StageEvalCase]]:
    """Load eval cases for all stages.

    Returns:
        Dict mapping stage name to list of cases.
    """
    eval_path = Path(eval_dir)
    if not eval_path.is_dir():
        return {}

    result: dict[str, list[StageEvalCase]] = {}
    for stage_dir in sorted(eval_path.iterdir()):
        if stage_dir.is_dir():
            stage = stage_dir.name
            cases = load_suite(stage, eval_dir)
            if cases:
                result[stage] = cases

    return result
