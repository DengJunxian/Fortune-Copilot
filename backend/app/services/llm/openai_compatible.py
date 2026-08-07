from __future__ import annotations

import json
from typing import Any

import httpx
from pydantic import BaseModel, Field, ValidationError

from app.core.errors import AppError
from app.core.privacy import (
    external_model_context,
    redact_sensitive_text,
    scan_prompt_injection,
)
from app.services.llm.base import LLMProvider, LLMRequest, LLMResponse

MAX_MODEL_RESPONSE_BYTES = 1_048_576


class _Message(BaseModel):
    content: str


class _Choice(BaseModel):
    message: _Message


class _ChatCompletion(BaseModel):
    model: str | None = None
    choices: list[_Choice] = Field(min_length=1)


class OpenAICompatibleLLMProvider(LLMProvider):
    """OpenAI-compatible JSON-schema transport; it never performs financial calculations."""

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str | None,
        timeout_seconds: int,
        provider_name: str = "openai_compatible",
    ) -> None:
        self.name = provider_name
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    @property
    def endpoint(self) -> str:
        return f"{self.base_url}/chat/completions"

    async def generate(self, request: LLMRequest) -> LLMResponse:
        injection_evidence = scan_prompt_injection(request.user_text)
        if injection_evidence:
            raise AppError(
                "prompt_injection_blocked",
                "输入包含试图改变系统规则的指令，已停止外部模型调用",
                status_code=422,
                details={"evidence_codes": injection_evidence},
            )
        safe_context = external_model_context(request.context)
        safe_user_text = redact_sensitive_text(request.user_text)
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload: dict[str, Any] = {
            "model": self.model,
            "temperature": 0,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你只负责理解、追问和解释。不得计算、修改或猜测任何金额、"
                        "比率、政策事实或产品属性。只输出 JSON，不要输出 Markdown。"
                        f"输出必须通过这个 JSON Schema 校验："
                        f"{json.dumps(request.response_json_schema, ensure_ascii=False)}"
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "task": request.task,
                            "user_text_redacted": safe_user_text,
                            "verified_context": safe_context,
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                },
            ],
        }
        if self.name == "deepseek":
            # DeepSeek's current OpenAI-compatible API supports JSON Object mode.
            # Application-owned Pydantic validation below supplies schema strictness.
            payload["response_format"] = {"type": "json_object"}
            payload["max_tokens"] = 2200
            payload["thinking"] = {"type": "disabled"}
        else:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": request.schema_name,
                    "strict": True,
                    "schema": request.response_json_schema,
                },
            }
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(self.endpoint, headers=headers, json=payload)
            response.raise_for_status()
        if len(response.content) > MAX_MODEL_RESPONSE_BYTES:
            raise ValueError("model response exceeds application limit")
        try:
            completion = _ChatCompletion.model_validate(response.json())
            structured = json.loads(completion.choices[0].message.content)
        except (ValidationError, json.JSONDecodeError, IndexError, TypeError) as exc:
            raise ValueError("invalid_openai_compatible_structured_response") from exc
        if not isinstance(structured, dict):
            raise ValueError("structured response must be a JSON object")
        return LLMResponse(
            provider=self.name,
            model=completion.model or self.model,
            content="结构化解释已通过传输层解析，仍需应用层 Pydantic 与治理校验。",
            structured=structured,
            degraded=False,
            validated_schema=request.schema_name,
        )
