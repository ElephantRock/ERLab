"""LiteLLM provider — unified interface to 100+ LLM providers.

Wraps litellm.completion() and litellm.embedding() to route requests
through any provider supported by LiteLLM (Google, Cohere, Mistral, etc.).
Lazy-imports litellm at method level so the app won't crash if uninstalled.
"""

import json
import logging
from collections.abc import AsyncIterator

from backend.providers.base import LLMProvider, LLMResponse

logger = logging.getLogger(__name__)


class LiteLLMProvider(LLMProvider):
    """LLM provider backed by litellm — routes to any model."""

    def __init__(self, model: str = "gpt-4o", api_key: str | None = None):
        super().__init__()
        self._model = model
        self._api_key = api_key

    @property
    def provider_name(self) -> str:
        return "litellm"

    @property
    def default_model(self) -> str:
        return self._model

    async def complete(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        import litellm

        response = await litellm.acompletion(
            model=self._model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=self._api_key,
        )
        return response.choices[0].message.content

    async def complete_with_usage(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        import litellm

        response = await litellm.acompletion(
            model=self._model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=self._api_key,
        )
        usage = getattr(response, "usage", None)
        inp = usage.prompt_tokens if usage else 0
        out = usage.completion_tokens if usage else 0
        self._report_cost(inp, out)
        return LLMResponse(
            content=response.choices[0].message.content or "",
            input_tokens=inp,
            output_tokens=out,
        )

    async def complete_stream(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        import litellm

        response = litellm.acompletion(
            model=self._model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
            api_key=self._api_key,
        )
        async for chunk in response:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    async def structured_output(
        self,
        messages: list[dict],
        schema: dict,
        temperature: float = 0.3,
    ) -> dict:
        import litellm

        response = await litellm.acompletion(
            model=self._model,
            messages=messages,
            temperature=temperature,
            response_format={"type": "json_object"},
            api_key=self._api_key,
        )
        content = response.choices[0].message.content
        return json.loads(content)

    async def structured_output_with_usage(
        self,
        messages: list[dict],
        schema: dict,
        temperature: float = 0.3,
    ) -> LLMResponse:
        import litellm

        response = await litellm.acompletion(
            model=self._model,
            messages=messages,
            temperature=temperature,
            response_format={"type": "json_object"},
            api_key=self._api_key,
        )
        usage = getattr(response, "usage", None)
        inp = usage.prompt_tokens if usage else 0
        out = usage.completion_tokens if usage else 0
        self._report_cost(inp, out)
        content = response.choices[0].message.content or "{}"
        return LLMResponse(
            content="",
            structured=json.loads(content),
            input_tokens=inp,
            output_tokens=out,
        )

    async def complete_with_tools(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        stage: str = "",
    ) -> LLMResponse:
        import litellm

        kwargs: dict = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "api_key": self._api_key,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        response = await litellm.acompletion(**kwargs)
        usage = getattr(response, "usage", None)
        inp = usage.prompt_tokens if usage else 0
        out = usage.completion_tokens if usage else 0
        self._report_cost(inp, out)

        choice = response.choices[0]
        content = choice.message.content or ""

        tool_calls_data = None
        if hasattr(choice.message, "tool_calls") and choice.message.tool_calls:
            tool_calls_data = {
                "tool_calls": [
                    {
                        "id": tc.id,
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    }
                    for tc in choice.message.tool_calls
                ]
            }

        return LLMResponse(
            content=content,
            structured=tool_calls_data,
            input_tokens=inp,
            output_tokens=out,
        )

    async def embed(self, texts: list[str]) -> list[list[float]]:
        import litellm

        response = await litellm.aembedding(
            model=self._model,
            input=texts,
            api_key=self._api_key,
        )
        return [item["embedding"] for item in response.data]
