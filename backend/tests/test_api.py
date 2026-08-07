import asyncio

from httpx import ASGITransport, AsyncClient, Response

from app.main import app


async def request(path: str, *, request_id: str | None = None) -> Response:
    headers = {"X-Request-ID": request_id} if request_id else None
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(path, headers=headers)


def test_health_reports_local_database_and_mock_mode() -> None:
    response = asyncio.run(request("/api/v1/health"))
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["database"]["status"] == "ok"
    assert payload["mock_mode"] is True
    assert response.headers["X-Request-ID"]


def test_capabilities_are_explicit_about_real_mock_and_planned_boundaries() -> None:
    response = asyncio.run(request("/api/v1/meta/capabilities"))
    assert response.status_code == 200
    payload = response.json()
    assert payload["portals"] == ["client", "advisor", "risk"]
    by_id = {item["id"]: item for item in payload["capabilities"]}
    assert by_id["api_foundation"]["implementation"] == "real"
    assert by_id["llm_provider"]["implementation"] == "mock"
    assert by_id["domain_data"]["implementation"] == "real"
    assert by_id["synthetic_households"]["status"] == "available"
    assert by_id["financial_engine"]["status"] == "available"
    assert by_id["financial_engine"]["implementation"] == "real"
    assert by_id["trusted_ai"]["status"] == "available"
    assert by_id["trusted_ai"]["implementation"] == "real"
    assert by_id["client_experience"]["status"] == "available"
    assert by_id["client_experience"]["implementation"] == "real"
    assert by_id["advisor_compliance_workflow"]["status"] == "available"
    assert by_id["advisor_compliance_workflow"]["implementation"] == "real"
    assert by_id["formal_eight_chapter_reports"]["status"] == "available"
    assert by_id["formal_eight_chapter_reports"]["implementation"] == "real"
    assert by_id["bank_adapter"]["implementation"] == "mock_only"
    assert "credit_limit_is_not_asset" in payload["guardrails"]


def test_http_errors_use_the_shared_error_envelope() -> None:
    response = asyncio.run(request("/api/v1/not-found", request_id="test-request"))
    assert response.status_code == 404
    payload = response.json()
    assert payload["error"]["code"] == "http_error"
    assert payload["error"]["request_id"] == "test-request"
