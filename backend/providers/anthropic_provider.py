"""Anthropic (Claude) provider implementation."""

import json
from typing import AsyncIterator

import anthropic

from backend.providers.base import LLMProvider


class AnthropicProvider(LLMProvider):
    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-20250514",
        embedding_model: str = "text-embedding-3-small",  # Falls back to OpenAI for embeddings
    ):
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = model
        self._embedding_model = embedding_model

    @property
    def provider_name(self) -> str:
        return "anthropic"

    @property
    def default_model(self) -> str:
        return self._model

    async def complete(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        system, filtered = self._extract_system(messages)
        response = await self._client.messages.create(
            model=self._model,
            system=system or "You are a helpful research assistant.",
            messages=filtered,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.content[0].text

    async def complete_stream(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        system, filtered = self._extract_system(messages)
        async with self._client.messages.stream(
            model=self._model,
            system=system or "You are a helpful research assistant.",
            messages=filtered,
            temperature=temperature,
            max_tokens=max_tokens,
        ) as stream:
            async for text in stream.text_stream:
                yield text

    async def structured_output(
        self,
        messages: list[dict],
        schema: dict,
        temperature: float = 0.3,
    ) -> dict:
        system, filtered = self._extract_system(messages)
        # Use tool-use with a single tool matching the schema
        response = await self._client.messages.create(
            model=self._model,
            system=system or "You are a helpful research assistant.",
            messages=filtered,
            temperature=temperature,
            tools=[
                {
                    "name": "structured_output",
                    "description": "Return structured output",
                    "input_schema": schema,
                }
            ],
            tool_choice={"type": "tool", "name": "structured_output"},
        )
        return response.content[0].input

    async def embed(self, texts: list[str]) -> list[list[float]]:
        # Anthropic doesn't offer embeddings — use OpenAI as fallback
        import openai as _openai

        client = _openai.AsyncOpenAI()
        response = await client.embeddings.create(model=self._embedding_model, input=texts)
        return [item.embedding for item in response.data]

    @staticmethod
    def _extract_system(messages: list[dict]) -> tuple[str | None, list[dict]]:
        system = None
        filtered = []
        for msg in messages:
            if msg["role"] == "system":
                system = msg["content"]
            else:
                filtered.append(msg)
        return system, filtered
