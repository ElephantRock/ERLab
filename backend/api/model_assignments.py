"""Real model assignment override store.

A separate, explicitly-scoped JSON file that stores per-stage model ID
overrides using real catalog model IDs (e.g. ``qwen/qwen3-4b-2507``),
not the abstract IDs (``cloud``, ``local``, ``auto``) used by the
legacy ``model_config.json``.

Runtime precedence order:
1. Per-stage real model override from this store
2. Configured preferred model (``EROCK_LMSTUDIO_MODEL``)
3. Model Manager / selector fitness scoring
4. Safe fallback / degradation

File format::

    {
      "schema_version": 1,
      "assignments": {
        "idea_generation": "qwen/qwen3-4b-2507"
      },
      "updated_at": "2026-06-17T06:56:00Z"
    }
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1
ASSIGNMENTS_PATH = Path("./data/model_assignments.json")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_assignments() -> dict[str, str]:
    """Load real-model per-stage overrides.

    Returns:
        ``{stage: model_id}`` dict (empty if file is missing or corrupt).
    """
    if not ASSIGNMENTS_PATH.exists():
        return {}
    try:
        data = json.loads(ASSIGNMENTS_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            raw = data.get("assignments", {})
            if isinstance(raw, dict):
                return {k: v for k, v in raw.items() if isinstance(k, str) and isinstance(v, str)}
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to load model_assignments.json: %s", e)
    return {}


def save_assignments(assignments: dict[str, str]) -> None:
    """Persist real-model per-stage overrides atomically.

    Writes to a temp file first, then replaces.
    """
    ASSIGNMENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "assignments": dict(sorted(assignments.items())),
        "updated_at": _now_iso(),
    }
    tmp_path = ASSIGNMENTS_PATH.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp_path.replace(ASSIGNMENTS_PATH)
    logger.info("Saved %d stage assignment overrides", len(assignments))


def clear_assignments() -> None:
    """Remove all per-stage overrides."""
    save_assignments({})


def remove_stage(stage: str) -> None:
    """Remove a single stage override."""
    current = load_assignments()
    if stage in current:
        del current[stage]
        save_assignments(current)


def get_stage_override(stage: str) -> str | None:
    """Get the real model override for a specific stage.

    This is the entry point for runtime selection — returns ``None``
    when no override exists, letting the caller fall through to
    preferred_model → fitness scoring → fallback.
    """
    return load_assignments().get(stage)
