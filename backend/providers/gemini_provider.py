"""Google Gemini provider implementation."""

import json
from typing import AsyncIterator

import google.generativeai as genai

from backend.providers.base import LLMProvider


class GeminiProvider(LLMProvider):
    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.0-flash",
        embedding_model: str = "models/embedding-001",
    ):
        genai.configure(api_key=api_key)
        self._model_name = model
        self._embedding_model = embedding_model

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
        prompt += "\n\nRespond with a valid JSON object matching this schema:\n" + json.dumps(schema)
        response = await model.generate_content_async(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=temperature,
                response_mime_type="application/json",
            ),
        )
        return json.loads(response.text)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        result = genai.embed_content(
            model=self._embedding_model,
            content=texts,
            task_type="retrieval_document",
        )
        return result["embedding"]

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
