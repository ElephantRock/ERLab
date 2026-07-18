"""Ollama (local models) provider implementation."""

import json
from collections.abc import AsyncIterator

import httpx

from backend.providers.base import LLMProvider, LLMResponse


class OllamaProvider(LLMProvider):
    def __init__(
        self,
        base_url: str | None = None,
        model: str = "llama3",
    ):
        super().__init__()
        if base_url is None:
            try:
                from backend.config import get_settings
                base_url = get_settings().ollama_base_url
            except Exception:
                base_url = "http://localhost:11434"
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._client = httpx.AsyncClient(timeout=120.0)

    @property
    def provider_name(self) -> str:
        return "ollama"

    @property
    def default_model(self) -> str:
        return self._model

    async def complete(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        response = await self._client.post(
            f"{self._base_url}/api/chat",
            json={
                "model": self._model,
                "messages": messages,
                "temperature": temperature,
                "options": {"num_predict": max_tokens},
                "stream": False,
            },
        )
        response.raise_for_status()
        return response.json()["message"]["content"]

    async def complete_with_usage(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        response = await self._client.post(
            f"{self._base_url}/api/chat",
            json={
                "model": self._model,
                "messages": messages,
                "temperature": temperature,
                "options": {"num_predict": max_tokens},
                "stream": False,
            },
        )
        response.raise_for_status()
        data = response.json()
        inp = data.get("prompt_eval_count", 0)
        out = data.get("eval_count", 0)
        self._report_cost(inp, out)
        return LLMResponse(
            content=data["message"]["content"],
            input_tokens=inp,
            output_tokens=out,
        )

    async def complete_stream(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        async with self._client.stream(
            "POST",
            f"{self._base_url}/api/chat",
            json={
                "model": self._model,
                "messages": messages,
                "temperature": temperature,
                "options": {"num_predict": max_tokens},
                "stream": True,
            },
        ) as response:
            async for line in response.aiter_lines():
                if line.strip():
                    data = json.loads(line)
                    if "message" in data and "content" in data["message"]:
                        content = data["message"]["content"]
                        if content:
                            yield content

    async def structured_output(
        self,
        messages: list[dict],
        schema: dict,
        temperature: float = 0.3,
    ) -> dict:
        messages[-1]["content"] += "\n\nRespond with a valid JSON object."
        response = await self._client.post(
            f"{self._base_url}/api/chat",
            json={
                "model": self._model,
                "messages": messages,
                "temperature": temperature,
                "format": "json",
                "stream": False,
            },
        )
        response.raise_for_status()
        return json.loads(response.json()["message"]["content"])

    async def structured_output_with_usage(
        self,
        messages: list[dict],
        schema: dict,
        temperature: float = 0.3,
    ) -> LLMResponse:
        messages[-1]["content"] += "\n\nRespond with a valid JSON object."
        response = await self._client.post(
            f"{self._base_url}/api/chat",
            json={
                "model": self._model,
                "messages": messages,
                "temperature": temperature,
                "format": "json",
                "stream": False,
            },
        )
        response.raise_for_status()
        data = response.json()
        inp = data.get("prompt_eval_count", 0)
        out = data.get("eval_count", 0)
        self._report_cost(inp, out)
        return LLMResponse(
            content="",
            structured=json.loads(data["message"]["content"]),
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
        if not tools:
            return await self.complete_with_usage(messages, temperature, max_tokens, stage)

        tool_prompt = "\n\nYou have access to these tools:\n"
        for t in tools:
            func = t.get("function", t)
            tool_prompt += f"- {func['name']}: {func.get('description', '')}\n"
            tool_prompt += f"  Parameters: {json.dumps(func.get('parameters', {}))}\n"
        tool_prompt += (
            '\nIf you want to call a tool, respond with JSON: '
            '{"tool_calls": [{"name": "...", "arguments": "{...}"}]}\n'
            "Otherwise, respond normally."
        )
        augmented = messages + [{"role": "user", "content": tool_prompt}]
        return await self.complete_with_usage(augmented, temperature, max_tokens, stage)
