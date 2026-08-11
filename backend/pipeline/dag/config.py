"""ConfigLoader — reads pipeline.yaml and returns an immutable validated dict.

BATCH-180 / HB-01: YAML is the single source of truth.
No env vars, no .env overrides, no strategy presets, no gate booleans.
"""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml

# ── Required top-level sections ───────────────────────────────
_REQUIRED_SECTIONS = ("models", "infrastructure", "budgets", "search", "strategies")

# ── Required sub-keys inside each section ─────────────────────
_REQUIRED_MODELS = ("thinking", "generation", "embedding", "reranker")
_REQUIRED_INFRA = ("chroma_dir", "bm25_dir", "database", "server")
_REQUIRED_BUDGETS = (
    "max_papers", "max_gaps", "max_ideas", "max_abstract_chars",
    "trim_top_k", "stage_timeout", "total_timeout",
)
_REQUIRED_SEARCH = ("sources", "queries_per_source", "citation_explore")


def _resolve_path(value: str, base_dir: str | Path) -> str:
    """Resolve a relative path to absolute, rooted at *base_dir*."""
    p = Path(value)
    if p.is_absolute():
        return str(p)
    return str(Path(base_dir) / p)


class ConfigLoader:
    """Load and validate ``pipeline.yaml``.

    Returns a deep-copied dict on every call so callers get an
    independent snapshot (AUTH-01: immutable during a pipeline run).
    """

    def __init__(self, yaml_path: str | Path | None = None) -> None:
        if yaml_path is None:
            yaml_path = Path(__file__).parent / "pipeline.yaml"
        self._yaml_path = Path(yaml_path)

    # ── public API ────────────────────────────────────────────

    def load(self) -> dict[str, Any]:
        """Read YAML, validate required sections, resolve paths.

        Returns an immutable-style snapshot (deep copy).
        Raises ``FileNotFoundError`` if YAML missing.
        Raises ``ValueError`` if required sections / fields missing.
        """
        if not self._yaml_path.exists():
            raise FileNotFoundError(f"Pipeline config not found: {self._yaml_path}")

        with open(self._yaml_path, encoding="utf-8") as fh:
            raw: dict[str, Any] = yaml.safe_load(fh)

        if not isinstance(raw, dict):
            raise ValueError("Pipeline config YAML must be a mapping at top level")

        self._validate_sections(raw)
        self._validate_models(raw["models"])
        self._validate_infrastructure(raw["infrastructure"])
        self._validate_budgets(raw["budgets"])
        self._validate_search(raw["search"])
        self._validate_strategies(raw["strategies"])

        # Resolve relative paths → absolute
        base_dir = str(self._yaml_path.parent)
        infra = raw["infrastructure"]
        for key in ("chroma_dir", "bm25_dir", "database"):
            infra[key] = _resolve_path(infra[key], base_dir)

        return copy.deepcopy(raw)

    @property
    def yaml_path(self) -> Path:
        return self._yaml_path

    # ── validation helpers ────────────────────────────────────

    @staticmethod
    def _validate_sections(raw: dict) -> None:
        missing = [s for s in _REQUIRED_SECTIONS if s not in raw]
        if missing:
            raise ValueError(f"Missing required sections: {', '.join(missing)}")

    @staticmethod
    def _validate_models(models: dict) -> None:
        missing = [k for k in _REQUIRED_MODELS if k not in models]
        if missing:
            raise ValueError(f"Missing model entries: {', '.join(missing)}")
        for name, cfg in models.items():
            if "provider" not in cfg and "strategy" not in cfg:
                raise ValueError(f"Model '{name}' missing 'provider' or 'strategy'")

    @staticmethod
    def _validate_infrastructure(infra: dict) -> None:
        missing = [k for k in _REQUIRED_INFRA if k not in infra]
        if missing:
            raise ValueError(f"Missing infrastructure fields: {', '.join(missing)}")

    @staticmethod
    def _validate_budgets(budgets: dict) -> None:
        missing = [k for k in _REQUIRED_BUDGETS if k not in budgets]
        if missing:
            raise ValueError(f"Missing budget fields: {', '.join(missing)}")

    @staticmethod
    def _validate_search(search: dict) -> None:
        missing = [k for k in _REQUIRED_SEARCH if k not in search]
        if missing:
            raise ValueError(f"Missing search fields: {', '.join(missing)}")

    @staticmethod
    def _validate_strategies(strategies: dict) -> None:
        if not strategies:
            raise ValueError("At least one strategy must be defined")
        for name, cfg in strategies.items():
            if "stages" not in cfg:
                raise ValueError(f"Strategy '{name}' missing 'stages' list")
            if "description" not in cfg:
                raise ValueError(f"Strategy '{name}' missing 'description'")
            if not isinstance(cfg["stages"], list) or len(cfg["stages"]) == 0:
                raise ValueError(f"Strategy '{name}' must have a non-empty stages list")
