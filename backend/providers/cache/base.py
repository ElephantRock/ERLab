"""Cache protocol, entry model, and key generation for LLM response caching."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from backend.providers.base import LLMResponse


@dataclass
class CacheEntry:
    response: LLMResponse
    created_at: float = 0.0


@runtime_checkable
class BaseCache(Protocol):
    def lookup(self, key: str) -> CacheEntry | None: ...
    def update(self, key: str, entry: CacheEntry) -> None: ...
    def clear(self) -> None: ...
    def stats(self) -> dict[str, int | float]: ...


def make_cache_key(messages: list[dict], **kwargs: object) -> str:
    payload = json.dumps(
        {"messages": messages, **{k: v for k, v in sorted(kwargs.items())}},
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def serialize_response(response: LLMResponse) -> str:
    return json.dumps({
        "content": response.content,
        "structured": response.structured,
        "input_tokens": response.input_tokens,
        "output_tokens": response.output_tokens,
    })


def deserialize_response(data: str) -> LLMResponse:
    d = json.loads(data)
    return LLMResponse(
        content=d["content"],
        structured=d.get("structured"),
        input_tokens=d.get("input_tokens", 0),
        output_tokens=d.get("output_tokens", 0),
    )
