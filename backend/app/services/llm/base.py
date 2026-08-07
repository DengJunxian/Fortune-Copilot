from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class LLMRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task: str
    user_text: str
    context: dict[str, Any] = Field(default_factory=dict)
    schema_name: str = "GenericStructuredOutput"
    response_json_schema: dict[str, Any] = Field(
        default_factory=lambda: {"type": "object", "additionalProperties": True}
    )
    fallback_output: dict[str, Any] = Field(default_factory=dict)


class LLMResponse(BaseModel):
    provider: str
    model: str
    content: str
    structured: dict[str, Any] = Field(default_factory=dict)
    degraded: bool = False
    validated_schema: str = "GenericStructuredOutput"
    failure_code: str | None = None


class LLMProvider(ABC):
    name: str
    model: str

    @abstractmethod
    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate language only; financial calculations are not permitted here."""


async def generate_validated[OutputModel: BaseModel](
    provider: LLMProvider,
    request: LLMRequest,
    output_model: type[OutputModel],
) -> tuple[LLMResponse, OutputModel]:
    """Validate provider JSON and fall back to an application-owned template."""

    try:
        response = await provider.generate(request)
        validated = output_model.model_validate(response.structured)
        return (
            response.model_copy(
                update={
                    "structured": validated.model_dump(mode="json"),
                    "validated_schema": output_model.__name__,
                }
            ),
            validated,
        )
    except Exception as exc:
        fallback = output_model.model_validate(request.fallback_output)
        return (
            LLMResponse(
                provider="template_fallback",
                model="fortune-copilot-template-v1",
                content="模型不可用或结构校验失败，已使用本地模板解释；确定性流程未受影响。",
                structured=fallback.model_dump(mode="json"),
                degraded=True,
                validated_schema=output_model.__name__,
                failure_code=type(exc).__name__,
            ),
            fallback,
        )
