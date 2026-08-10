from fastapi import APIRouter

from app.api.v1.endpoints import (
    behavior,
    client,
    demo,
    domain,
    financial,
    fund_advisory,
    health,
    integrations,
    meta,
    planning,
    portfolio,
    public_data,
    reports,
    review,
    security,
    trust,
    twin,
    wealth_planning,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(integrations.router)
api_router.include_router(meta.router)
api_router.include_router(public_data.router)
api_router.include_router(domain.router)
api_router.include_router(financial.router)
api_router.include_router(fund_advisory.router)
api_router.include_router(planning.router)
api_router.include_router(portfolio.router)
api_router.include_router(twin.router)
api_router.include_router(behavior.router)
api_router.include_router(trust.router)
api_router.include_router(client.router)
api_router.include_router(demo.router)
api_router.include_router(review.router)
api_router.include_router(reports.router)
api_router.include_router(security.router)
api_router.include_router(wealth_planning.router)
