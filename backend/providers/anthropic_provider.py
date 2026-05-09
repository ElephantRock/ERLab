"""Anthropic (Claude) provider implementation."""

import json
from collections.abc import AsyncIterator

import anthropic

from backend.providers.base import LLMProvider, LLMResponse


class AnthropicProvider(LLMProvider):
    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-20250514",
        embedding_model: str = "text-embedding-3-small",
        base_url: str | None = None,
    ):
        super().__init__()
        kwargs = {"api_key": api_key, "timeout": 600.0}  # 10 min timeout
        if base_url:
            kwargs["base_url"] = base_url
        self._client = anthropic.AsyncAnthropic(**kwargs)
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
            messages=filtered,  # type: ignore[arg-type]
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.content[0].text  # type: ignore[return-value, union-attr]

    async def complete_with_usage(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        system, filtered = self._extract_system(messages)
        response = await self._client.messages.create(
            model=self._model,
            system=system or "You are a helpful research assistant.",
            messages=filtered,  # type: ignore[arg-type]
            temperature=temperature,
            max_tokens=max_tokens,
        )
        inp = response.usage.input_tokens
        out = response.usage.output_tokens
        self._report_cost(inp, out)
        return LLMResponse(
            content=response.content[0].text,
            input_tokens=inp,
            output_tokens=out,
        )

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
            messages=filtered,  # type: ignore[arg-type]
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
        try:
            response = await self._client.messages.create(  # type: ignore[call-overload]
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
            return response.content[0].input  # type: ignore[return-value, union-attr]
        except Exception:
            # Fallback: ask the model to return JSON directly (for non-Anthropic endpoints)
            return await self._structured_output_fallback(messages, schema, temperature)

    async def structured_output_with_usage(
        self,
        messages: list[dict],
        schema: dict,
        temperature: float = 0.3,
    ) -> LLMResponse:
        system, filtered = self._extract_system(messages)
        try:
            response = await self._client.messages.create(  # type: ignore[call-overload]
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
            inp = response.usage.input_tokens
            out = response.usage.output_tokens
            self._report_cost(inp, out)
            return LLMResponse(
                content="",
                structured=response.content[0].input,
                input_tokens=inp,
                output_tokens=out,
            )
        except Exception:
            result = await self._structured_output_fallback(messages, schema, temperature)
            return LLMResponse(content="", structured=result)

    async def complete_with_tools(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        stage: str = "",
    ) -> LLMResponse:
        system, filtered = self._extract_system(messages)
        kwargs: dict = {
            "model": self._model,
            "system": system or "You are a helpful research assistant.",
            "messages": filtered,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            anthropic_tools = []
            for t in tools:
                func = t.get("function", t)
                anthropic_tools.append({
                    "name": func["name"],
                    "description": func.get("description", ""),
                    "input_schema": func.get("parameters", {"type": "object", "properties": {}}),
                })
            kwargs["tools"] = anthropic_tools
            kwargs["tool_choice"] = {"type": "auto"}

        response = await self._client.messages.create(**kwargs)  # type: ignore[arg-type]
        inp = response.usage.input_tokens
        out = response.usage.output_tokens
        self._report_cost(inp, out, stage)

        content_text = ""
        tool_calls = []
        for block in response.content:
            if block.type == "text":
                content_text += block.text
            elif block.type == "tool_use":
                tool_calls.append({
                    "id": block.id,
                    "name": block.name,
                    "arguments": json.dumps(block.input),
                })

        return LLMResponse(
            content=content_text,
            structured={"tool_calls": tool_calls} if tool_calls else None,
            input_tokens=inp,
            output_tokens=out,
        )

    async def embed(self, texts: list[str]) -> list[list[float]]:
        # Anthropic doesn't offer embeddings — use OpenAI as fallback
        import openai as _openai

        client = _openai.AsyncOpenAI()
        response = await client.embeddings.create(model=self._embedding_model, input=texts)
        return [item.embedding for item in response.data]  # type: ignore[return-value, union-attr]

    async def _structured_output_fallback(
        self,
        messages: list[dict],
        schema: dict,
        temperature: float = 0.3,
    ) -> dict:
        """Fallback: extract JSON from a regular completion when tool_use isn't supported."""
        import json

        schema_hint = json.dumps(schema, indent=2)
        prompt = (
            f"Return a JSON object matching this schema:\n```json\n{schema_hint}\n```\n\n"
            "Return ONLY the JSON object, no markdown fences, no explanation."
        )
        augmented = messages + [{"role": "user", "content": prompt}]
        text = await self.complete(augmented, temperature=temperature)

        # Strip markdown fences if present
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
        text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Attempt basic JSON repair
            return self._repair_json(text)

    @staticmethod
    def _repair_json(text: str) -> dict:
        """Attempt to repair common JSON errors from LLM output."""
        import json
        import re

        # Fix unterminated strings — find last complete key-value pair
        # Strategy: truncate at last valid closing brace/bracket
        for i in range(len(text) - 1, -1, -1):
            if text[i] in ('}', ']'):
                candidate = text[:i + 1]
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    continue

        # Fix trailing commas before closing braces
        text_fixed = re.sub(r',\s*([}\]])', r'\1', text)
        try:
            return json.loads(text_fixed)
        except json.JSONDecodeError:
            pass

        # Fix single quotes → double quotes
        text_fixed = text.replace("'", '"')
        try:
            return json.loads(text_fixed)
        except json.JSONDecodeError:
            pass

        # Last resort: extract first {...} block with regex
        m = re.search(r'\{.*\}', text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                pass

        raise json.JSONDecodeError(
            f"Could not repair JSON from LLM output (first 200 chars): {text[:200]}",
            text, 0,
        )

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
