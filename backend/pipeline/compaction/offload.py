"""Filesystem offload for evicted context — persists and recovers message history."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ContextOffloadStore:
    """Manages offloaded context chunks on the filesystem."""

    def __init__(self, offload_dir: str = "./data/context_offload") -> None:
        self._dir = Path(offload_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    def save(
        self,
        run_id: str,
        index: int,
        messages: list[dict],
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Write a chunk of messages to a JSONL file. Returns file path."""
        run_dir = self._dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        path = run_dir / f"chunk_{index:04d}.jsonl"
        data = {
            "run_id": run_id,
            "index": index,
            "messages": messages,
            "metadata": metadata or {},
        }
        path.write_text(json.dumps(data, default=str) + "\n", encoding="utf-8")
        logger.debug("Offloaded %d messages for run %s chunk %d", len(messages), run_id, index)
        return str(path)

    def load(self, run_id: str) -> list[dict]:
        """Load all offloaded messages for a run, sorted by chunk index."""
        run_dir = self._dir / run_id
        if not run_dir.exists():
            return []

        all_messages: list[dict] = []
        chunks = sorted(run_dir.glob("chunk_*.jsonl"))

        for chunk_path in chunks:
            try:
                data = json.loads(chunk_path.read_text(encoding="utf-8"))
                all_messages.extend(data.get("messages", []))
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning("Skipping corrupted offload chunk %s: %s", chunk_path, e)

        return all_messages

    def delete(self, run_id: str) -> int:
        """Delete all offloaded data for a run. Returns number of chunks removed."""
        run_dir = self._dir / run_id
        if not run_dir.exists():
            return 0

        count = 0
        for chunk_path in run_dir.glob("chunk_*.jsonl"):
            chunk_path.unlink()
            count += 1

        # Remove empty directory
        try:
            run_dir.rmdir()
        except OSError:
            pass

        return count

    def list_offloads(self) -> list[dict[str, Any]]:
        """List all offloaded runs with metadata."""
        results = []
        if not self._dir.exists():
            return results

        for run_dir in sorted(self._dir.iterdir()):
            if not run_dir.is_dir():
                continue
            chunks = list(run_dir.glob("chunk_*.jsonl"))
            if chunks:
                results.append({
                    "run_id": run_dir.name,
                    "chunk_count": len(chunks),
                })
        return results
