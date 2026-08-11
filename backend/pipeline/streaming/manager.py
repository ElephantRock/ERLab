"""StreamManager — manages active SSE streams with deduplication."""

from __future__ import annotations

import asyncio
import logging

from backend.pipeline.streaming.events import StreamEvent, StreamEventType

logger = logging.getLogger(__name__)


class StreamManager:
    """Manages active streams with dedup and event routing."""

    def __init__(self, dedup_window: float = 1.0) -> None:
        self._dedup_window = dedup_window
        self._streams: dict[str, asyncio.Queue] = {}
        self._recent_events: dict[str, float] = {}  # event_type:timestamp for dedup

    def create_stream(self, run_id: str) -> asyncio.Queue:
        """Create and register a queue for a run. Returns the queue."""
        queue: asyncio.Queue = asyncio.Queue()
        self._streams[run_id] = queue
        logger.debug("Stream created for run %s", run_id)
        return queue

    def remove_stream(self, run_id: str) -> None:
        """Remove and cleanup a stream."""
        self._streams.pop(run_id, None)

    def emit(self, event: StreamEvent) -> int:
        """Send event to the queue matching event.run_id. Returns listener count."""
        if self._should_dedup(event):
            return 0

        queue = self._streams.get(event.run_id)
        if queue is not None:
            queue.put_nowait(event)
            return 1

        # Broadcast to all streams if no specific run_id
        if not event.run_id:
            count = 0
            for q in self._streams.values():
                q.put_nowait(event)
                count += 1
            return count

        return 0

    def emit_llm_chunk(self, run_id: str, chunk: str, provider: str = "", model: str = "") -> None:
        """Convenience for emitting LLM streaming chunks."""
        self.emit(StreamEvent(
            type=StreamEventType.LLM_CHUNK,
            run_id=run_id,
            data={"chunk": chunk, "provider": provider, "model": model},
        ))

    def cancel_stream(self, run_id: str) -> None:
        """Send done event and remove stream."""
        self.emit(StreamEvent(
            type=StreamEventType.DONE,
            run_id=run_id,
            data={"cancelled": True},
        ))
        self.remove_stream(run_id)

    def get_active_streams(self) -> list[str]:
        """List active run_ids."""
        return list(self._streams.keys())

    def _should_dedup(self, event: StreamEvent) -> bool:
        """Suppress duplicate events within the dedup window."""
        if event.type in (StreamEventType.LLM_CHUNK, StreamEventType.DONE, StreamEventType.HEARTBEAT):
            return False  # Never dedup these

        key = f"{event.run_id}:{event.type.value}"
        now = event.timestamp

        last = self._recent_events.get(key)
        if last and (now - last) < self._dedup_window:
            return True

        self._recent_events[key] = now

        # Prune old entries
        cutoff = now - self._dedup_window * 2
        self._recent_events = {k: v for k, v in self._recent_events.items() if v > cutoff}

        return False

    @property
    def stream_count(self) -> int:
        return len(self._streams)
