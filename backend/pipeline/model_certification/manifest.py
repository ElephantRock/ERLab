"""Candidate model manifest — declarative model specification.

A manifest describes a model before it has been tested.
All new models enter as candidates, never directly into production.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml


_VALID_PROVIDERS = frozenset({
    "lmstudio", "openai", "anthropic", "local", "vllm", "ollama", "api",
})

_VALID_SOURCES = frozenset({
    "local", "api", "remote",
})


@dataclass
class CandidateModelManifest:
    """Declarative specification of a model candidate for certification.

    New models are candidates first, not production models.
    Defaults: candidate_status='untested', allowed_for_pipeline=False.
    """

    model_id: str
    provider: str                     # lmstudio, openai, anthropic, local, vllm, ollama, api
    source: str                       # local, api, remote
    model_family: str                 # qwen, glm, gpt, claude, llama, mistral, etc.
    parameter_count: str | None = None  # "4b", "14b", "70b", etc.
    quantization: str | None = None   # "q4_k_m", "fp16", "unknown"
    engine: str | None = None         # lmstudio, vllm, ollama, api
    advertised_context_window: int = 4096
    advertised_max_output_tokens: int = 2048
    supports_json_mode: bool = False
    supports_tool_calling: bool = False
    supports_streaming: bool = True
    candidate_status: str = "untested"
    allowed_for_pipeline: bool = False

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(self) -> list[str]:
        """Validate manifest fields. Returns list of errors (empty = valid)."""
        errors: list[str] = []

        if not self.model_id or not self.model_id.strip():
            errors.append("model_id is required and must be non-empty")

        if not self.provider or not self.provider.strip():
            errors.append("provider is required")
        elif self.provider.lower() not in _VALID_PROVIDERS:
            errors.append(
                f"provider '{self.provider}' not in {_VALID_PROVIDERS}"
            )

        if not self.source or not self.source.strip():
            errors.append("source is required")
        elif self.source.lower() not in _VALID_SOURCES:
            errors.append(f"source '{self.source}' not in {_VALID_SOURCES}")

        if not self.model_family or not self.model_family.strip():
            errors.append("model_family is required")

        if self.advertised_context_window <= 0:
            errors.append(
                f"advertised_context_window must be > 0, got {self.advertised_context_window}"
            )

        if self.advertised_max_output_tokens <= 0:
            errors.append(
                f"advertised_max_output_tokens must be > 0, got {self.advertised_max_output_tokens}"
            )

        if self.advertised_max_output_tokens > self.advertised_context_window:
            errors.append(
                "advertised_max_output_tokens cannot exceed advertised_context_window"
            )

        return errors

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Convert to plain dict for serialization."""
        return asdict(self)

    def to_yaml(self) -> str:
        """Serialize to YAML string."""
        return yaml.dump(self.to_dict(), default_flow_style=False, sort_keys=False)

    @classmethod
    def from_yaml(cls, text: str) -> CandidateModelManifest:
        """Deserialize from YAML string."""
        data = yaml.safe_load(text)
        if not isinstance(data, dict):
            raise ValueError("YAML must contain a mapping")
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    @classmethod
    def from_yaml_file(cls, path: str | Path) -> CandidateModelManifest:
        """Load manifest from a YAML file."""
        return cls.from_yaml(Path(path).read_text(encoding="utf-8"))

    def to_yaml_file(self, path: str | Path) -> None:
        """Write manifest to a YAML file."""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(self.to_yaml(), encoding="utf-8")

    # ------------------------------------------------------------------
    # Provenance
    # ------------------------------------------------------------------

    @property
    def content_hash(self) -> str:
        """SHA-256 hash of the serialized manifest fields (for report provenance)."""
        serialized = json.dumps(self.to_dict(), sort_keys=True)
        return hashlib.sha256(serialized.encode()).hexdigest()[:16]
