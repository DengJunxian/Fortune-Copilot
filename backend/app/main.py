from __future__ import annotations

import re
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.errors import install_exception_handlers
from app.core.http_security import (
    HostedProxyMiddleware,
    RateLimitMiddleware,
    RequestBodyLimitMiddleware,
    SecurityHeadersMiddleware,
)
from app.core.logging import configure_logging

settings = get_settings()
configure_logging(settings.log_level)

app = FastAPI(
    title="Fortune Copilot API",
    summary="中国个人与家庭财富规划 API",
    description=(
        "提供个人／家庭基本情况、资产负债、年度收支、财务比率、"
        "理财目标、大额支出与八章理财规划书能力，并支持客户经理与风险人员的后续工作流。"
        "关键金额、比率和配置数字由版本化确定性程序计算，"
        "语言模型只负责理解、追问和解释已验证结果。"
    ),
    version=settings.app_version,
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None if settings.is_production else "/redoc",
    openapi_url=None if settings.is_production else "/api/v1/openapi.json",
)

app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)
app.add_middleware(RequestBodyLimitMiddleware, max_bytes=settings.max_request_body_bytes)
app.add_middleware(RateLimitMiddleware, settings=settings)
app.add_middleware(SecurityHeadersMiddleware, settings=settings)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Content-Type",
        "Authorization",
        "X-Request-ID",
        "X-Actor-ID",
        "X-Actor-Role",
        "X-Confirm-Action",
    ],
    expose_headers=["X-Request-ID", "X-RateLimit-Limit", "X-RateLimit-Remaining"],
)
app.add_middleware(HostedProxyMiddleware, settings=settings)


@app.middleware("http")
async def add_request_id(request: Request, call_next):  # type: ignore[no-untyped-def]
    proposed = request.headers.get("X-Request-ID", "")
    request_id = proposed if re.fullmatch(r"[A-Za-z0-9._:-]{1,80}", proposed) else uuid4().hex
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.get("/", tags=["system"])
def root() -> dict[str, str | bool]:
    return {
        "name": "Fortune Copilot API",
        "version": settings.app_version,
        "docs": "disabled" if settings.is_production else "/docs",
        "mock_mode": settings.is_mock_mode,
    }


app.include_router(api_router, prefix="/api/v1")
install_exception_handlers(app)
