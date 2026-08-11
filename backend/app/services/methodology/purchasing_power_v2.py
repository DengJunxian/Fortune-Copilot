from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from decimal import Decimal

from app.domain.enums import CalibrationMode, ExpenseCategory
from app.domain.financial import ExpenseFact, HouseholdFacts
from app.schemas.calibration import CalibrationParameterResolution, CalibrationStatus
from app.schemas.eligible_capital import (
    GoalCostInflation,
    HouseholdCostInflation,
    IncomeAdequacyIndex,
    InflationComponent,
    PurchasingPowerV2,
)
from app.schemas.methodology import MethodologyAssessment
from app.services.calibration.port import CalibrationPort, UnavailableCalibrationPort
from app.services.financial.rules import FinancialRules
from app.services.financial.utils import ZERO, annualize, money, ratio
from app.services.liability_engine.rules import LiabilityRules
from app.services.liability_engine.schedule import SchedulableStream


def _stream_id(stream: SchedulableStream, index: int) -> str:
    for key in ("id", "source_goal_id", "source_responsibility_id"):
        value = getattr(stream, key, None)
        if value is not None:
            return str(value)
    return f"projected-stream-{index}"


def _stream_name(stream: SchedulableStream, index: int) -> str:
    return str(getattr(stream, "name", f"负债流 {index}"))


def _status(references: Sequence[CalibrationParameterResolution]) -> CalibrationStatus:
    statuses = {item.status for item in references}
    if "needs_review" in statuses:
        return "needs_review"
    if "degraded" in statuses:
        return "degraded"
    return "available"


def _modes(references: Sequence[CalibrationParameterResolution]) -> list[CalibrationMode]:
    order = {
        CalibrationMode.BANK_AUTHORIZED: 0,
        CalibrationMode.EMPIRICALLY_CALIBRATED: 1,
        CalibrationMode.CONTROLLED_DEMO: 2,
    }
    return sorted(
        {item.mode for item in references if item.mode is not None},
        key=order.__getitem__,
    )


def _unique(
    references: Sequence[CalibrationParameterResolution],
) -> list[CalibrationParameterResolution]:
    return list({item.parameter_id: item for item in references}.values())


def _gci_reference(
    stream: SchedulableStream,
    index: int,
    region: str,
    analysis_date: date,
) -> CalibrationParameterResolution:
    confirmed = bool(getattr(stream, "is_user_confirmed", False))
    stream_version = str(getattr(stream, "stream_version", "unversioned-stream"))
    return CalibrationParameterResolution(
        parameter_id=f"liability-stream:{_stream_id(stream, index)}:annual-growth",
        code="GCI.annual_growth_assumption",
        value=stream.annual_growth_assumption,
        segment=stream.inflation_index_code,
        region=region,
        mode=CalibrationMode.CONTROLLED_DEMO,
        status="degraded" if confirmed else "needs_review",
        source="confirmed_liability_stream" if confirmed else "unconfirmed_liability_stream",
        source_reference=stream_version,
        version=stream_version,
        method="source_stream_identity",
        confidence=Decimal("0.900000") if confirmed else Decimal("0.000000"),
        limitations=[
            "目标成本增长率来自目标或责任记录，不是官方 CPI。",
            (
                "当前为用户确认的受控输入，仍不可表述为经验校准。"
                if confirmed
                else "来源记录未经用户确认，正式使用前必须复核。"
            ),
        ],
        effective_from=analysis_date,
        dataset_code="household_liability_stream",
        reason=(
            "confirmed_controlled_input_requires_review"
            if confirmed
            else "unconfirmed_goal_cost_parameter"
        ),
    )


def assess_purchasing_power_v2(
    facts: HouseholdFacts,
    streams: Sequence[SchedulableStream],
    financial_rules: FinancialRules,
    methodology: MethodologyAssessment,
    liability_rules: LiabilityRules,
    analysis_date: date,
    calibration_port: CalibrationPort | None = None,
) -> PurchasingPowerV2:
    port = calibration_port or UnavailableCalibrationPort()
    region = methodology.minimum_wage_snapshot.region_code
    eligible_expenses = [
        item for item in facts.expenses if item.category != ExpenseCategory.DEBT_SERVICE
    ]
    annual_costs = [annualize(item.amount, item.frequency) for item in eligible_expenses]
    total_cost = sum(annual_costs, ZERO)
    hci_components: list[tuple[ExpenseFact, Decimal, CalibrationParameterResolution]] = []
    for item, annual_cost in zip(eligible_expenses, annual_costs, strict=True):
        reference = port.get_parameter(
            "HCI.expense_category_rate",
            item.category.value,
            region,
            analysis_date,
        )
        configured_rate = Decimal(
            financial_rules.purchasing_power.expense_category_rates.get(
                item.category.value,
                "0",
            )
        )
        hci_components.append((item, annual_cost, reference))
        if reference.value is None:
            reference.limitations.append(
                f"计算暂沿用旧规则值 {configured_rate}，该值未绑定校准注册表。"
            )
    weighted_rate = (
        sum(
            (
                annual_cost
                * (
                    reference.value
                    if reference.value is not None
                    else Decimal(
                        financial_rules.purchasing_power.expense_category_rates.get(
                            item.category.value,
                            "0",
                        )
                    )
                )
                for item, annual_cost, reference in hci_components
            ),
            ZERO,
        )
        / total_cost
        if total_cost > ZERO
        else ZERO
    )
    components = [
        InflationComponent(
            code=item.category.value,
            label=item.name,
            annual_rate=(
                reference.value
                if reference.value is not None
                else Decimal(
                    financial_rules.purchasing_power.expense_category_rates.get(
                        item.category.value,
                        "0",
                    )
                )
            ),
            annual_cost=annual_cost,
            weight=ratio(annual_cost / total_cost) if total_cost > ZERO else ZERO,
        )
        for item, annual_cost, reference in hci_components
    ]
    sustainable_income = money(
        sum(
            (
                annualize(item.amount, item.frequency)
                for item in facts.incomes
                if item.is_sustainable
            ),
            ZERO,
        )
    )
    essential_cost = money(
        sum(
            (
                annualize(item.amount, item.frequency)
                for item in facts.expenses
                if item.necessity.value == "essential"
            ),
            ZERO,
        )
    )
    adequacy_ratio = (
        (sustainable_income / essential_cost).quantize(Decimal("0.000001"))
        if essential_cost > ZERO
        else Decimal("0.000000")
    )
    threshold_references = {
        name: port.get_parameter(f"IAI.threshold.{name}", "all", region, analysis_date)
        for name in ("critical_below", "watch_below", "comfortable_at")
    }
    thresholds = liability_rules.iai_thresholds
    threshold_values = {
        name: (reference.value if reference.value is not None else getattr(thresholds, name))
        for name, reference in threshold_references.items()
    }
    status = (
        "critical"
        if adequacy_ratio < threshold_values["critical_below"]
        else "watch"
        if adequacy_ratio < threshold_values["watch_below"]
        else "comfortable"
        if adequacy_ratio >= threshold_values["comfortable_at"]
        else "adequate"
    )
    cpi_reference = port.get_parameter("HCI.official_cpi_anchor", "all", "CN", analysis_date)
    hci_references = _unique([cpi_reference, *(item[2] for item in hci_components)])
    wage_reference = port.get_parameter("IAI.minimum_wage_cagr", "all", region, analysis_date)
    iai_references = [*threshold_references.values(), wage_reference]
    gci_references = [
        _gci_reference(stream, index, region, analysis_date)
        for index, stream in enumerate(streams, 1)
    ]
    all_references = _unique([*hci_references, *gci_references, *iai_references])
    overall_status = _status(all_references)
    return PurchasingPowerV2(
        formula_version=liability_rules.formula_version,
        calibration_registry_version=port.registry_version,
        calibration_status=overall_status,
        calibration_modes=_modes(all_references),
        parameter_references=all_references,
        requires_human_review=overall_status != "available",
        household_cost_inflation=HouseholdCostInflation(
            annual_rate=ratio(weighted_rate),
            components=components,
            calibration_status=_status(hci_references),
            calibration_modes=_modes(hci_references),
            parameter_references=hci_references,
            interpretation="按家庭实际支出权重计算生活成本通胀，不混入债务本金；校准模式单独披露。",
        ),
        goal_cost_inflation=[
            GoalCostInflation(
                stream_id=_stream_id(stream, index),
                stream_name=_stream_name(stream, index),
                stream_type=stream.stream_type,
                inflation_index_code=stream.inflation_index_code,
                annual_rate=stream.annual_growth_assumption,
                calibration_status=gci_references[index - 1].status,
                calibration_modes=_modes([gci_references[index - 1]]),
                parameter_references=[gci_references[index - 1]],
                interpretation="目标成本增长只作用于该目标现金流；来源记录与校准模式不得混称。",
            )
            for index, stream in enumerate(streams, 1)
        ],
        income_adequacy=IncomeAdequacyIndex(
            sustainable_annual_income=sustainable_income,
            essential_annual_cost=essential_cost,
            ratio=adequacy_ratio,
            status=status,
            minimum_wage_trend=ratio(
                wage_reference.value
                if wage_reference.value is not None
                else methodology.minimum_wage_snapshot.cagr
            ),
            calibration_status=_status(iai_references),
            calibration_modes=_modes(iai_references),
            parameter_references=iai_references,
            interpretation="最低工资趋势只辅助观察收入追赶能力，不进入投资收益门槛。",
        ),
    )
