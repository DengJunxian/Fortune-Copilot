from app.core.config import Settings


def test_all_v5_feature_flags_default_to_false() -> None:
    settings = Settings(APP_ENV="test", DATABASE_URL="sqlite://")

    assert settings.enable_v5_financial_graph is False
    assert settings.enable_v5_client_profile is False
    assert settings.enable_v5_liability_engine is False
    assert settings.enable_v5_persistent_twin is False
    assert settings.enable_v5_family_enterprise is False
    assert settings.enable_v5_cfs is False
    assert settings.enable_v5_product_ontology is False
    assert settings.enable_v5_monitoring is False
    assert settings.enable_v5_agents is False
