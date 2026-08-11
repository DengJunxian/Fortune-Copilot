from __future__ import annotations

from functools import lru_cache
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        populate_by_name=True,
    )

    app_env: str = Field(default="development", alias="APP_ENV")
    app_version: str = Field(default="0.14.0", alias="APP_VERSION")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    cors_origins_raw: str = Field(
        default="http://localhost:5173,http://localhost:8080",
        alias="CORS_ORIGINS",
    )
    database_url: str = Field(default="sqlite:///./data/wealthtwin.db", alias="DATABASE_URL")
    synthetic_data_path: str = Field(
        default="../data/synthetic/v5_personas/personas_v2.json",
        alias="SYNTHETIC_DATA_PATH",
    )
    v5_persona_data_path: str = Field(
        default="../data/synthetic/v5_personas/personas_v2.json",
        alias="V5_PERSONA_DATA_PATH",
    )
    v5_persona_golden_path: str = Field(
        default="../data/synthetic/v5_personas/golden_outcomes_v2.json",
        alias="V5_PERSONA_GOLDEN_PATH",
    )
    financial_rules_path: str = Field(
        default="../data/rules/financial_health_v1.json",
        alias="FINANCIAL_RULES_PATH",
    )
    planning_rules_path: str = Field(
        default="../data/rules/planning_waterfall_v1.json",
        alias="PLANNING_RULES_PATH",
    )
    methodology_rules_path: str = Field(
        default="../data/rules/wealth_methodology_v3.json",
        alias="METHODOLOGY_RULES_PATH",
    )
    public_data_snapshot_path: str = Field(
        default="../data/public/authoritative_public_snapshot_v1.json",
        alias="PUBLIC_DATA_SNAPSHOT_PATH",
    )
    calibration_registry_path: str = Field(
        default="../data/calibration/china_purchasing_power_v1.json",
        alias="CALIBRATION_REGISTRY_PATH",
    )
    portfolio_rules_path: str = Field(
        default="../data/rules/portfolio_policy_v1.json",
        alias="PORTFOLIO_RULES_PATH",
    )
    product_catalog_path: str = Field(
        default="../data/products/mock_products_v1.json",
        alias="PRODUCT_CATALOG_PATH",
    )
    fund_advisory_catalog_path: str = Field(
        default="../data/products/verified_real_funds_v1.json",
        alias="FUND_ADVISORY_CATALOG_PATH",
    )
    twin_rules_path: str = Field(
        default="../data/rules/twin_simulation_v1.json",
        alias="TWIN_RULES_PATH",
    )
    behavior_rules_path: str = Field(
        default="../data/rules/behavior_finance_v1.json",
        alias="BEHAVIOR_RULES_PATH",
    )
    client_profile_rules_path: str = Field(
        default="../data/rules/client_profile_v1.json",
        alias="CLIENT_PROFILE_RULES_PATH",
    )
    liability_rules_path: str = Field(
        default="../data/rules/liability_engine_v1.json",
        alias="LIABILITY_RULES_PATH",
    )
    family_enterprise_rules_path: str = Field(
        default="../data/rules/family_enterprise_v1.json",
        alias="FAMILY_ENTERPRISE_RULES_PATH",
    )
    cfs_rules_path: str = Field(
        default="../data/rules/cfs_composer_v1.json",
        alias="CFS_RULES_PATH",
    )
    specialized_cfs_rules_path: str = Field(
        default="../data/rules/specialized_cfs_v1.json",
        alias="SPECIALIZED_CFS_RULES_PATH",
    )
    monitoring_rules_path: str = Field(
        default="../data/rules/monitoring_v1.json",
        alias="MONITORING_RULES_PATH",
    )
    knowledge_base_path: str = Field(
        default="../data/knowledge/controlled_knowledge_v1.json",
        alias="KNOWLEDGE_BASE_PATH",
    )
    demo_benchmark_path: str = Field(
        default="../data/benchmarks/demo_release_v1.json",
        alias="DEMO_BENCHMARK_PATH",
    )
    v5_release_benchmark_path: str = Field(
        default="../data/benchmarks/v5_release_v2.json",
        alias="V5_RELEASE_BENCHMARK_PATH",
    )
    demo_story_version: str = Field(
        default="wealthtwin-main-demo-v1.0.0", alias="DEMO_STORY_VERSION"
    )
    demo_cache_ttl_seconds: int = Field(default=300, ge=30, le=3600, alias="DEMO_CACHE_TTL_SECONDS")
    demo_main_path_count: int = Field(default=100, ge=100, le=5000, alias="DEMO_MAIN_PATH_COUNT")
    llm_provider: str = Field(default="mock", alias="LLM_PROVIDER")
    llm_api_key: SecretStr | None = Field(default=None, alias="LLM_API_KEY")
    llm_base_url: str | None = Field(default="https://api.deepseek.com", alias="LLM_BASE_URL")
    llm_model: str | None = Field(default="deepseek-v4-flash", alias="LLM_MODEL")
    llm_allowed_hosts_raw: str = Field(default="api.deepseek.com", alias="LLM_ALLOWED_HOSTS")
    llm_timeout_seconds: int = Field(default=20, ge=1, le=120, alias="LLM_TIMEOUT_SECONDS")
    allowed_hosts_raw: str = Field(
        default="localhost,127.0.0.1,test,testserver,backend",
        alias="ALLOWED_HOSTS",
    )
    max_request_body_bytes: int = Field(
        default=1_048_576,
        ge=16_384,
        le=10_485_760,
        alias="MAX_REQUEST_BODY_BYTES",
    )
    max_upload_bytes: int = Field(
        default=524_288,
        ge=1_024,
        le=5_242_880,
        alias="MAX_UPLOAD_BYTES",
    )
    rate_limit_per_minute: int = Field(
        default=120,
        ge=10,
        le=10_000,
        alias="RATE_LIMIT_PER_MINUTE",
    )
    expensive_rate_limit_per_minute: int = Field(
        default=30,
        ge=2,
        le=1_000,
        alias="EXPENSIVE_RATE_LIMIT_PER_MINUTE",
    )
    session_timeout_minutes: int = Field(
        default=30,
        ge=5,
        le=480,
        alias="SESSION_TIMEOUT_MINUTES",
    )
    session_signing_key: SecretStr | None = Field(default=None, alias="SESSION_SIGNING_KEY")
    demo_auth_enabled: bool = Field(default=True, alias="DEMO_AUTH_ENABLED")
    enable_v5_financial_graph: bool = Field(default=False, alias="ENABLE_V5_FINANCIAL_GRAPH")
    enable_v5_client_profile: bool = Field(default=False, alias="ENABLE_V5_CLIENT_PROFILE")
    enable_v5_liability_engine: bool = Field(default=False, alias="ENABLE_V5_LIABILITY_ENGINE")
    enable_v5_persistent_twin: bool = Field(default=False, alias="ENABLE_V5_PERSISTENT_TWIN")
    enable_v5_family_enterprise: bool = Field(default=False, alias="ENABLE_V5_FAMILY_ENTERPRISE")
    enable_v5_cfs: bool = Field(default=False, alias="ENABLE_V5_CFS")
    enable_v5_product_ontology: bool = Field(default=False, alias="ENABLE_V5_PRODUCT_ONTOLOGY")
    enable_v5_monitoring: bool = Field(default=False, alias="ENABLE_V5_MONITORING")
    enable_v5_agents: bool = Field(default=False, alias="ENABLE_V5_AGENTS")
    enable_v5_calibration: bool = Field(default=False, alias="ENABLE_V5_CALIBRATION")

    @model_validator(mode="after")
    def validate_security_boundaries(self) -> Settings:
        environment = self.app_env.casefold()
        if "*" in self.cors_origins:
            raise ValueError("CORS_ORIGINS must be an explicit allowlist")
        if environment == "production":
            if self.demo_auth_enabled:
                raise ValueError("DEMO_AUTH_ENABLED must be false in production")
            if (
                self.session_signing_key is None
                or len(self.session_signing_key.get_secret_value()) < 32
            ):
                raise ValueError("SESSION_SIGNING_KEY must contain at least 32 characters")
            if any(
                origin.startswith(("http://localhost", "http://127.0.0.1"))
                for origin in self.cors_origins
            ):
                raise ValueError("production CORS_ORIGINS cannot contain localhost HTTP origins")
            if not self.is_mock_mode:
                parsed_model_url = urlsplit(self.llm_base_url or "")
                if (
                    parsed_model_url.scheme != "https"
                    or parsed_model_url.hostname not in self.llm_allowed_hosts
                ):
                    raise ValueError(
                        "production LLM_BASE_URL must use HTTPS and an LLM_ALLOWED_HOSTS entry"
                    )
        return self

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins_raw.split(",") if origin.strip()]

    @property
    def allowed_hosts(self) -> list[str]:
        return [host.strip() for host in self.allowed_hosts_raw.split(",") if host.strip()]

    @property
    def llm_allowed_hosts(self) -> list[str]:
        return [
            host.strip().casefold()
            for host in self.llm_allowed_hosts_raw.split(",")
            if host.strip()
        ]

    @property
    def is_production(self) -> bool:
        return self.app_env.casefold() == "production"

    @property
    def allow_demo_actor_headers(self) -> bool:
        return self.demo_auth_enabled and self.app_env.casefold() in {
            "development",
            "demo",
            "test",
        }

    @property
    def is_mock_mode(self) -> bool:
        provider = self.llm_provider.casefold()
        if provider == "mock":
            return True
        if provider in {"local", "local_openai_compatible"}:
            return not (self.llm_base_url and self.llm_model)
        return self.llm_api_key is None or not (self.llm_base_url and self.llm_model)


@lru_cache
def get_settings() -> Settings:
    return Settings()
