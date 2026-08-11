"""OpenAI provider implementation."""

import json
import logging
from collections.abc import AsyncIterator

import openai

from backend.providers.base import LLMProvider, LLMResponse

logger = logging.getLogger(__name__)


class OpenAIProvider(LLMProvider):
    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o",
        base_url: str | None = None,
    ):
        super().__init__()
        kwargs = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self._client = openai.AsyncOpenAI(**kwargs)
        self._model = model
        self._base_url = base_url or ""

    @property
    def _structured_output_mode(self) -> str:
        """Determine the structured-output dialect for this endpoint.

        Z.AI's GLM endpoint documents ``json_object`` mode, not
        OpenAI-style ``json_schema``. When ``json_schema`` is sent to
        Z.AI, GLM-5.2 returns JSON wrapped in markdown fences and
        sometimes truncates the content because the reasoning model's
        internal chain-of-thought consumes the completion token budget.

        LM Studio and OpenAI's native API support ``json_schema``
        directly and return clean JSON.

        The distinction is endpoint-level, not model-level: the same
        OpenAI-compatible transport does not imply the same
        structured-output dialect.
        """
        url = (self._base_url or "").lower()
        # Z.AI endpoints (api.z.ai) use json_object dialect
        if "z.ai" in url or "zai" in url:
            return "json_object"
        # LM Studio and OpenAI native support json_schema
        return "json_schema"

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
        served = getattr(response, "model", None) or self._model
        self._set_receipt_from_response(served)
        return response.choices[0].message.content  # type: ignore[return-value]

    async def complete_with_usage(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stage: str = "",
        run_id: str | None = None,
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
        self._report_cost(inp, out, stage=stage, run_id=run_id)
        served = getattr(response, "model", None) or self._model
        self._set_receipt_from_response(served)
        return LLMResponse(
            content=response.choices[0].message.content or "",
            input_tokens=inp,
            output_tokens=out,
            served_model=served,
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
        max_tokens: int = 8192,
    ) -> dict:
        mode = self._structured_output_mode

        if mode == "json_object":
            # Z.AI GLM dialect: place the schema in the prompt, use
            # json_object response_format. This produces clean, directly
            # parseable JSON without markdown fences.
            schema_hint = json.dumps(schema, indent=2)
            augmented = list(messages) + [{"role": "user", "content": (
                f"Return ONLY a valid JSON object matching this schema:\n"
                f"```json\n{schema_hint}\n```\n\n"
                f"Return the JSON object directly, no markdown fences."
            )}]
            try:
                response = await self._client.chat.completions.create(
                    model=self._model,
                    messages=augmented,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format={"type": "json_object"},
                )
                content = response.choices[0].message.content or ""
                result = self._parse_structured_content(content)
                if result:
                    return result
                logger.warning(
                    "structured_output: json_object returned"
                    " %d chars but failed all parse attempts",
                    len(content),
                )
            except Exception as e:
                logger.debug(
                    "structured_output: json_object path failed: %s",
                    str(e)[:200],
                )

            return await self._structured_output_fallback(messages, schema, temperature, max_tokens)

        # Default: json_schema dialect (LM Studio, OpenAI native)
        try:
            response = await self._client.chat.completions.create(  # type: ignore[call-overload]
                model=self._model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "response",
                        "schema": schema,
                        "strict": False,
                    },
                },
            )
            content = response.choices[0].message.content  # type: ignore[union-attr]
            if content:
                result = self._parse_structured_content(content)
                if result:
                    return result
                logger.warning(
                    "structured_output: json_schema returned"
                    " %d chars but failed all parse attempts",
                    len(content),
                )
        except Exception as e:
            logger.debug("structured_output: json_schema path failed: %s", str(e)[:200])

        # Fallback: plain completion + extract JSON (for providers that don't support json_schema)
        return await self._structured_output_fallback(messages, schema, temperature, max_tokens)

    @staticmethod
    def _parse_structured_content(content: str) -> dict | None:
        """Parse structured-output content with fence stripping and repair.

        Tries direct parse, markdown-fence strip, trailing-comma repair,
        and regex extraction. Returns None if all attempts fail.
        """
        import re as _re

        text = content.strip()

        # Strip markdown fences if present
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
        text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Repair trailing commas
        repaired = _re.sub(r',\s*([}\]])', r'\1', text)
        try:
            return json.loads(repaired)
        except json.JSONDecodeError:
            pass

        # Extract first {...} block
        m = _re.search(r'\{.*\}', text, _re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                repaired2 = _re.sub(r',\s*([}\]])', r'\1', m.group())
                try:
                    return json.loads(repaired2)
                except json.JSONDecodeError:
                    pass

        return None

    async def structured_output_with_usage(
        self,
        messages: list[dict],
        schema: dict,
        temperature: float = 0.3,
        max_tokens: int = 8192,
        stage: str = "",
        run_id: str | None = None,
    ) -> LLMResponse:
        mode = self._structured_output_mode
        try:
            if mode == "json_object":
                schema_hint = json.dumps(schema, indent=2)
                augmented = list(messages) + [{"role": "user", "content": (
                    f"Return ONLY a valid JSON object matching this schema:\n"
                    f"```json\n{schema_hint}\n```\n\n"
                    f"Return the JSON object directly, no markdown fences."
                )}]
                response = await self._client.chat.completions.create(
                    model=self._model,
                    messages=augmented,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format={"type": "json_object"},
                )
            else:
                response = await self._client.chat.completions.create(  # type: ignore[call-overload]
                    model=self._model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format={
                        "type": "json_schema",
                        "json_schema": {
                            "name": "response",
                            "schema": schema,
                            "strict": False,
                        },
                    },
                )
            usage = response.usage
            inp = usage.prompt_tokens if usage else 0
            out = usage.completion_tokens if usage else 0
            self._report_cost(inp, out, stage=stage, run_id=run_id)
            content = response.choices[0].message.content or ""
            served = getattr(response, "model", None) or self._model
            self._set_receipt_from_response(served)
            parsed = self._parse_structured_content(content)
            if parsed is None:
                parsed = {}
            return LLMResponse(
                content="",
                structured=parsed,
                input_tokens=inp,
                output_tokens=out,
                served_model=served,
            )
        except Exception:
            result = await self._structured_output_fallback(messages, schema, temperature)
            return LLMResponse(content="", structured=result)

    async def _structured_output_fallback(
        self,
        messages: list[dict],
        schema: dict,
        temperature: float = 0.3,
        max_tokens: int = 8192,
    ) -> dict:
        """Fallback for providers that don't support response_format (e.g. LM Studio)."""
        import re

        schema_hint = json.dumps(schema, indent=2)
        augmented = messages + [{"role": "user", "content": (
            f"Return a JSON object matching this schema:\n"
            f"```json\n{schema_hint}\n```\n\n"
            f"Return ONLY the JSON object, no markdown fences."
        )}]
        text = await self.complete(augmented, temperature=temperature, max_tokens=max_tokens)
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

        # Attempt JSON repair: fix trailing commas and truncated content
        import re as _re
        # Remove trailing commas before } or ]
        repaired = _re.sub(r',\s*([}\]])', r'\1', text)
        try:
            return json.loads(repaired)
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

        served = getattr(response, "model", None) or self._model
        self._set_receipt_from_response(served)

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
