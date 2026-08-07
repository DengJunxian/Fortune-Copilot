import asyncio

from pydantic import BaseModel

from app.core.config import Settings
from app.services.llm import (
    LLMProvider,
    LLMRequest,
    LLMResponse,
    OpenAICompatibleLLMProvider,
    generate_validated,
    get_llm_provider,
)


class ExplanationOutput(BaseModel):
    explanation: str
    numeric_source: str


class FailingProvider(LLMProvider):
    name = "failing"
    model = "failure-fixture"

    async def generate(self, request: LLMRequest) -> LLMResponse:
        raise OSError(f"simulated failure for {request.task}")


class TimeoutProvider(LLMProvider):
    name = "timeout"
    model = "timeout-fixture"

    async def generate(self, request: LLMRequest) -> LLMResponse:
        raise TimeoutError(f"simulated timeout for {request.task}")


def test_mock_provider_is_deterministic_and_never_claims_to_calculate() -> None:
    provider = get_llm_provider()
    request = LLMRequest(task="explain", user_text="解释家庭流动性")
    first = asyncio.run(provider.generate(request))
    second = asyncio.run(provider.generate(request))
    assert first == second
    assert first.provider == "mock"
    assert first.structured["calculation_source"] == "deterministic_tools_only"
    assert "不会由语言模型生成关键金额" in first.content


def test_structured_provider_failure_uses_pydantic_validated_local_template() -> None:
    request = LLMRequest(
        task="explain_verified_result",
        user_text="解释已经由工具计算的结论",
        schema_name="ExplanationOutput",
        response_json_schema=ExplanationOutput.model_json_schema(),
        fallback_output={
            "explanation": "外部模型不可用，保留确定性结果并使用本地模板。",
            "numeric_source": "deterministic_tools_only",
        },
    )
    response, output = asyncio.run(
        generate_validated(FailingProvider(), request, ExplanationOutput)
    )
    assert response.degraded is True
    assert response.provider == "template_fallback"
    assert response.failure_code == "OSError"
    assert response.validated_schema == "ExplanationOutput"
    assert output.numeric_source == "deterministic_tools_only"


def test_structured_provider_timeout_safely_degrades_to_local_template() -> None:
    request = LLMRequest(
        task="explain_verified_result",
        user_text="解释已经由工具计算的结论",
        schema_name="ExplanationOutput",
        response_json_schema=ExplanationOutput.model_json_schema(),
        fallback_output={
            "explanation": "外部模型超时，保留确定性结果并使用本地模板。",
            "numeric_source": "deterministic_tools_only",
        },
    )
    response, output = asyncio.run(
        generate_validated(TimeoutProvider(), request, ExplanationOutput)
    )
    assert response.degraded is True
    assert response.provider == "template_fallback"
    assert response.failure_code == "TimeoutError"
    assert output.numeric_source == "deterministic_tools_only"


def test_factory_supports_keyless_local_openai_compatible_transport_without_calling_it() -> None:
    settings = Settings(
        _env_file=None,
        LLM_PROVIDER="local_openai_compatible",
        LLM_BASE_URL="http://127.0.0.1:11434/v1",
        LLM_MODEL="local-structured-model",
    )
    provider = get_llm_provider(settings)
    assert isinstance(provider, OpenAICompatibleLLMProvider)
    assert provider.endpoint == "http://127.0.0.1:11434/v1/chat/completions"
    assert provider.api_key is None
