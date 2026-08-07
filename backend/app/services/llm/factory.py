from __future__ import annotations

from app.core.config import Settings, get_settings
from app.services.llm.base import LLMProvider
from app.services.llm.mock import MockLLMProvider
from app.services.llm.openai_compatible import OpenAICompatibleLLMProvider


def get_llm_provider(settings: Settings | None = None) -> LLMProvider:
    active = settings or get_settings()
    if active.is_mock_mode:
        return MockLLMProvider()
    provider = active.llm_provider.casefold()
    if (
        provider
        in {
            "openai",
            "openai_compatible",
            "deepseek",
            "local",
            "local_openai_compatible",
        }
        and active.llm_base_url
        and active.llm_model
    ):
        return OpenAICompatibleLLMProvider(
            base_url=active.llm_base_url,
            model=active.llm_model,
            api_key=(
                active.llm_api_key.get_secret_value() if active.llm_api_key is not None else None
            ),
            timeout_seconds=active.llm_timeout_seconds,
            provider_name=provider,
        )
    # Unknown or incomplete configuration fails closed without making a network request.
    return MockLLMProvider()
