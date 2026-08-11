"""Bridge from stage_callback to StreamManager."""

from __future__ import annotations

from collections.abc import Callable

from backend.pipeline.streaming.events import StreamEvent, StreamEventType
from backend.pipeline.streaming.manager import StreamManager


def create_stage_callback(
    stream_manager: StreamManager,
    run_id: str,
) -> Callable[[str, int, int, float], None]:
    """Return a stage_callback compatible with PipelineOrchestrator.

    The callback signature is: (stage_name, index, total, elapsed)
    """
    def _callback(stage_name: str, index: int, total: int, elapsed: float) -> None:
        stream_manager.emit(StreamEvent(
            type=StreamEventType.STAGE_COMPLETE,
            run_id=run_id,
            data={
                "stage": stage_name,
                "index": index,
                "total": total,
                "elapsed": round(elapsed, 2),
            },
        ))
    return _callback


def create_llm_stream_callback(
    stream_manager: StreamManager,
    run_id: str,
) -> Callable[[str, str, str], None]:
    """Return a callback for LLM chunk relay."""
    def _callback(chunk: str, provider: str = "", model: str = "") -> None:
        stream_manager.emit_llm_chunk(run_id, chunk, provider, model)
    return _callback
