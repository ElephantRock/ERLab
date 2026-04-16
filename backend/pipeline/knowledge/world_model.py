"""Persistent research landscape model.

Tracks topic clusters, active gaps, historical ideas, and causal
links across pipeline runs. Provides trend detection and gap evolution.
"""

import json
import logging
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class TopicCluster(BaseModel):
    id: str
    name: str
    description: str = ""
    paper_count: int = 0
    trend_direction: str = "stable"  # "growing", "declining", "stable"
    last_updated: datetime = datetime.now()


class ResearchLandscape(BaseModel):
    topics: list[TopicCluster] = Field(default_factory=list)
    active_gaps: list[dict] = Field(default_factory=list)
    historical_ideas: list[dict] = Field(default_factory=list)
    causal_links: list[dict] = Field(default_factory=list)
    version: int = 0
    last_updated: datetime = datetime.now()


class WorldModel:
    """Persistent model of research landscape tracking topics, gaps, ideas over time."""

    def __init__(self, persist_path: str = "./data/world_model.json"):
        self._path = Path(persist_path)
        self._landscape = ResearchLandscape()
        self._load()

    async def update_from_run(self, result, provider=None) -> None:
        """Update the world model from a pipeline result."""
        # Update gaps
        new_gap_titles = {g.title for g in result.gaps}
        existing_gap_titles = {g.get("title", "") for g in self._landscape.active_gaps}

        # Add new gaps
        for gap in result.gaps:
            if gap.title not in existing_gap_titles:
                self._landscape.active_gaps.append({
                    "title": gap.title,
                    "description": gap.description,
                    "gap_type": gap.gap_type,
                    "confidence": gap.confidence,
                    "first_seen": datetime.now().isoformat(),
                })
            else:
                # Update existing gap
                for g in self._landscape.active_gaps:
                    if g.get("title") == gap.title:
                        g["confidence"] = gap.confidence
                        g["last_seen"] = datetime.now().isoformat()

        # Store top ideas
        for idea in sorted(result.ideas, key=lambda x: x.score, reverse=True)[:5]:
            self._landscape.historical_ideas.append({
                "title": idea.title,
                "score": idea.score,
                "method": idea.proposed_method[:200],
                "run_id": getattr(result, "run_id", ""),
                "timestamp": datetime.now().isoformat(),
            })

        # Keep only last 50 historical ideas
        if len(self._landscape.historical_ideas) > 50:
            self._landscape.historical_ideas = self._landscape.historical_ideas[-50:]

        self._landscape.version += 1
        self._landscape.last_updated = datetime.now()
        self._save()

    def get_landscape(self) -> ResearchLandscape:
        return self._landscape

    def get_gap_evolution(self, gap_title: str) -> list[dict]:
        """Get the history of a specific gap across runs."""
        return [
            h for h in self._landscape.active_gaps
            if h.get("title") == gap_title
        ]

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text())
            self._landscape = ResearchLandscape(**data)
            logger.info("Loaded world model v%d", self._landscape.version)
        except Exception as e:
            logger.warning("Failed to load world model: %s", e)

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(self._landscape.model_dump_json(indent=2))
