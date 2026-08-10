from __future__ import annotations

from typing import Protocol

from app.schemas.portfolio import HedgeLabBoundary


class ProfessionalHedgingOverlay(Protocol):
    """Future port for approved professional hedging, never a retail return enhancer."""

    def boundary(self) -> HedgeLabBoundary: ...


class DisabledDemoHedgingOverlay:
    """Competition adapter: shows prerequisites without exposing a trading path."""

    def boundary(self) -> HedgeLabBoundary:
        return HedgeLabBoundary(
            title="专业对冲实验室默认关闭",
            reason="普通家庭不提供股指期货、杠杆或衍生品交易入口；比赛版只展示治理边界。",
            prerequisites=[
                "专业投资者类型与独立身份核验",
                "衍生品知识、经验和损失承受能力评估",
                "明确的现货风险敞口与套期保值目的",
                "产品、渠道和交易时点适当性",
                "人工复核与独立风险确认",
            ],
        )


def professional_hedging_boundary() -> HedgeLabBoundary:
    return DisabledDemoHedgingOverlay().boundary()
