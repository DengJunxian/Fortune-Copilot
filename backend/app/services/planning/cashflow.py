from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from app.services.financial.utils import money
from app.services.methodology.models import DailyLiquidityRule


@dataclass(frozen=True, slots=True)
class CashNeedForecast:
    strategy: str
    target_amount: Decimal
    p95_projected_net_outflow: Decimal | None
    horizons_days: tuple[int, ...]
    salary_date_available: bool
    billing_date_available: bool
    explanation: str


class CashFlowForecastPort(Protocol):
    """Port for a governed 14/30-day cash-flow forecast implementation."""

    def forecast(self, monthly_essential_expenses: Decimal) -> CashNeedForecast: ...


class DeterministicDailyLiquidityPolicy:
    """Competition adapter; replaceable by a governed bank cash-flow forecast."""

    def __init__(self, rule: DailyLiquidityRule) -> None:
        self.rule = rule

    def forecast(self, monthly_essential_expenses: Decimal) -> CashNeedForecast:
        target = money(
            min(
                self.rule.maximum_amount,
                max(
                    self.rule.minimum_amount,
                    monthly_essential_expenses * self.rule.operating_months,
                ),
            )
        )
        return CashNeedForecast(
            strategy=self.rule.strategy,
            target_amount=target,
            p95_projected_net_outflow=None,
            horizons_days=tuple(self.rule.future_forecast_horizons_days),
            salary_date_available=False,
            billing_date_available=False,
            explanation=(
                "比赛版使用月必要支出的 0.25 倍并限制在 3,000-20,000 元；"
                "CashFlowForecastPort 已预留 14/30 日、工资日、账单日、"
                "周期账单和 P95 净流出接入边界。"
            ),
        )
