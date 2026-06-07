"""OpenAI provider implementation."""

import json
from collections.abc import AsyncIterator

import openai

from backend.providers.base import LLMProvider, LLMResponse


class OpenAIProvider(LLMProvider):
    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o",
        embedding_model: str = "text-embedding-3-small",
        base_url: str | None = None,
    ):
        super().__init__()
        kwargs = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self._client = openai.AsyncOpenAI(**kwargs)
        self._model = model
        self._embedding_model = embedding_model

    @property
    def provider_name(self) -> str:
        return "openai"

    @property
    def default_model(self) -> str:
        return self._model

    async def complete(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        response = await self._client.chat.completions.create(  # type: ignore[arg-type]
            model=self._model,
            messages=messages,  # type: ignore[arg-type]
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content  # type: ignore[return-value]

    async def complete_with_usage(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        response = await self._client.chat.completions.create(  # type: ignore[arg-type]
            model=self._model,
            messages=messages,  # type: ignore[arg-type]
            temperature=temperature,
            max_tokens=max_tokens,
        )
        usage = response.usage
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
        stream = await self._client.chat.completions.create(  # type: ignore[arg-type]
            model=self._model,
            messages=messages,  # type: ignore[arg-type]
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        async for chunk in stream:  # type: ignore[union-attr]
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def structured_output(
        self,
        messages: list[dict],
        schema: dict,
        temperature: float = 0.3,
    ) -> dict:
        try:
            response = await self._client.chat.completions.create(  # type: ignore[call-overload]
                model=self._model,
                messages=messages,
                temperature=temperature,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content  # type: ignore[union-attr]
            return json.loads(content)
        except Exception:
            # Fallback: plain completion + extract JSON (for LM Studio)
            return await self._structured_output_fallback(messages, schema, temperature)

    async def structured_output_with_usage(
        self,
        messages: list[dict],
        schema: dict,
        temperature: float = 0.3,
    ) -> LLMResponse:
        try:
            response = await self._client.chat.completions.create(  # type: ignore[call-overload]
                model=self._model,
                messages=messages,
                temperature=temperature,
                response_format={"type": "json_object"},
            )
            usage = response.usage
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
        except Exception:
            result = await self._structured_output_fallback(messages, schema, temperature)
            return LLMResponse(content="", structured=result)

    async def _structured_output_fallback(
        self,
        messages: list[dict],
        schema: dict,
        temperature: float = 0.3,
    ) -> dict:
        """Fallback for providers that don't support response_format (e.g. LM Studio)."""
        import re

        schema_hint = json.dumps(schema, indent=2)
        augmented = messages + [{"role": "user", "content": (
            f"Return a JSON object matching this schema:\n"
            f"```json\n{schema_hint}\n```\n\n"
            f"Return ONLY the JSON object, no markdown fences."
        )}]
        text = await self.complete(augmented, temperature=temperature)
        text = text.strip()

        # Strip markdown fences
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
        text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Extract first {...} block
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                pass

        return {}

    async def complete_with_tools(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        stage: str = "",
    ) -> LLMResponse:
        kwargs: dict = {
            "model": self._model,
            "messages": messages,  # type: ignore[arg-type]
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        response = await self._client.chat.completions.create(**kwargs)  # type: ignore[arg-type]
        usage = response.usage
        inp = usage.prompt_tokens if usage else 0
        out = usage.completion_tokens if usage else 0
        self._report_cost(inp, out, stage)

        choice = response.choices[0]
        content = choice.message.content or ""

        tool_calls_data = None
        if choice.message.tool_calls:
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
        response = await self._client.embeddings.create(
            model=self._embedding_model,
            input=texts,
        )
        return [item.embedding for item in response.data]  # type: ignore[return-value]
