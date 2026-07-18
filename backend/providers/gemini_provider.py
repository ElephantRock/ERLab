"""Google Gemini provider implementation."""

import json
from collections.abc import AsyncIterator

import google.generativeai as genai

from backend.providers.base import LLMProvider, LLMResponse


class GeminiProvider(LLMProvider):
    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.0-flash",
    ):
        super().__init__()
        genai.configure(api_key=api_key)
        self._model_name = model

    @property
    def provider_name(self) -> str:
        return "gemini"

    @property
    def default_model(self) -> str:
        return self._model_name

    async def complete(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        model = genai.GenerativeModel(self._model_name)
        prompt = self._messages_to_prompt(messages)
        response = await model.generate_content_async(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            ),
        )
        return response.text

    async def complete_with_usage(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        model = genai.GenerativeModel(self._model_name)
        prompt = self._messages_to_prompt(messages)
        response = await model.generate_content_async(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            ),
        )
        usage = response.usage_metadata
        inp = usage.prompt_token_count if usage else 0
        out = usage.candidates_token_count if usage else 0
        self._report_cost(inp, out)
        return LLMResponse(
            content=response.text,
            input_tokens=inp,
            output_tokens=out,
        )

    async def complete_stream(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        model = genai.GenerativeModel(self._model_name)
        prompt = self._messages_to_prompt(messages)
        response = await model.generate_content_async(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            ),
            stream=True,
        )
        async for chunk in response:
            if chunk.text:
                yield chunk.text

    async def structured_output(
        self,
        messages: list[dict],
        schema: dict,
        temperature: float = 0.3,
    ) -> dict:
        model = genai.GenerativeModel(self._model_name)
        prompt = self._messages_to_prompt(messages)
        prompt += "\n\nRespond with a valid JSON object matching this schema:\n" + json.dumps(
            schema
        )
        response = await model.generate_content_async(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=temperature,
                response_mime_type="application/json",
            ),
        )
        return json.loads(response.text)

    async def structured_output_with_usage(
        self,
        messages: list[dict],
        schema: dict,
        temperature: float = 0.3,
    ) -> LLMResponse:
        model = genai.GenerativeModel(self._model_name)
        prompt = self._messages_to_prompt(messages)
        prompt += "\n\nRespond with a valid JSON object matching this schema:\n" + json.dumps(
            schema
        )
        response = await model.generate_content_async(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=temperature,
                response_mime_type="application/json",
            ),
        )
        usage = response.usage_metadata
        inp = usage.prompt_token_count if usage else 0
        out = usage.candidates_token_count if usage else 0
        self._report_cost(inp, out)
        return LLMResponse(
            content="",
            structured=json.loads(response.text),
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

    @staticmethod
    def _messages_to_prompt(messages: list[dict]) -> str:
        parts = []
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            if role == "system":
                parts.append(f"System: {content}")
            elif role == "user":
                parts.append(f"User: {content}")
            elif role == "assistant":
                parts.append(f"Assistant: {content}")
        return "\n\n".join(parts)
