"""hello-plugin — A minimal Elephant Rock plugin.

Registers a hook handler that logs when a pipeline completes,
and provides a hello_world tool that can be called by agents.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── Plugin Metadata ──────────────────────────────────────────

PLUGIN_DIR = Path(__file__).parent
MANIFEST_PATH = PLUGIN_DIR / "plugin.json"


def load_manifest() -> dict[str, Any]:
    """Load and return the plugin manifest from plugin.json."""
    if MANIFEST_PATH.exists():
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {}


# ── Hook Handler ─────────────────────────────────────────────

async def on_pipeline_completed(payload: dict) -> None:
    """Hook handler for the pipeline.completed event.

    Receives a payload dict with:
        - run_id: str          The unique run identifier
        - ideas_count: int     Number of ideas generated
        - gaps_count: int      Number of gaps found
        - proposals_count: int Number of proposals synthesized
    """
    run_id = payload.get("run_id", "unknown")
    ideas = payload.get("ideas_count", 0)
    gaps = payload.get("gaps_count", 0)
    proposals = payload.get("proposals_count", 0)

    logger.info(
        "🎉 hello-plugin: Pipeline %s completed — "
        "%d gaps, %d ideas, %d proposals",
        run_id,
        gaps,
        ideas,
        proposals,
    )


# ── Tool Registration ────────────────────────────────────────

def register_tools(registry) -> None:
    """Register plugin tools with the ToolRegistry.

    This function is called by the PluginLoader during discovery.
    """

    async def hello_world(run_id: str = "unknown") -> str:
        """Return a friendly greeting for a pipeline run.

        Args:
            run_id: The pipeline run identifier.

        Returns:
            A greeting string.
        """
        manifest = load_manifest()
        plugin_name = manifest.get("name", "hello-plugin")
        version = manifest.get("version", "?.?.?")
        return f"Hello from {plugin_name} v{version}! Run: {run_id}"

    registry.register(
        name="hello_world",
        handler=hello_world,
        description="Greet the pipeline runner. "
        "Useful for verifying the plugin system is working.",
        trust_level="untrusted",
    )
    logger.info("hello-plugin: registered hello_world tool")


# ── Plugin Entry Point ───────────────────────────────────────

def register_hooks(hooks) -> None:
    """Register hook handlers with the HookDispatcher.

    This is an optional entry point for plugins that only handle events
    and don't register tools. The PluginLoader can call this if present.
    """
    hooks.register("pipeline.complete", on_pipeline_completed)
    logger.info("hello-plugin: registered pipeline.complete hook")
