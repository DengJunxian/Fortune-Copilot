from __future__ import annotations

from app.services.llm.base import LLMProvider, LLMRequest, LLMResponse


class MockLLMProvider(LLMProvider):
    name = "mock"
    model = "fortune-copilot-template-v1"

    async def generate(self, request: LLMRequest) -> LLMResponse:
        return LLMResponse(
            provider=self.name,
            model=self.model,
            content=(
                "当前处于本地 Mock 模式。系统可以解释已确认数据，但不会猜测缺失信息，"
                "也不会由语言模型生成关键金额、比例或配置。"
            ),
            structured={
                **request.fallback_output,
                **(
                    {}
                    if request.fallback_output
                    else {
                        "task": request.task,
                        "requires_user_confirmation": bool(request.user_text.strip()),
                        "calculation_source": "deterministic_tools_only",
                    }
                ),
            },
            degraded=False,
            validated_schema=request.schema_name,
        )
