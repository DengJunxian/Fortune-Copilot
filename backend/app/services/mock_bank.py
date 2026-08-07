from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.auth import ActorContext
from app.domain.enums import AssetCategory, AuditEventType, LiabilityCategory
from app.domain.financial import AssetFact
from app.models.common import utc_now
from app.models.governance import AuditEvent
from app.schemas.review_workflow import (
    MockBankEntry,
    MockBankInterface,
    MockBankSnapshot,
)
from app.services.financial.facts import load_household_facts

ADAPTER_VERSION = "mock-bank-adapter-v1.0.0"


def _asset_entry(asset: AssetFact, *, boundary_note: str) -> MockBankEntry:
    return MockBankEntry(
        record_id=asset.id,
        display_name=asset.name,
        amount=asset.market_value,
        amount_role="asset",
        source_record_ids=[asset.id],
        details={
            "category": asset.category.value,
            "liquidity_days": asset.liquidity_days,
            "valuation_date": (
                asset.valuation_date.isoformat() if asset.valuation_date is not None else None
            ),
        },
        boundary_note=boundary_note,
    )


def _interface(code: str, label: str, entries: list[MockBankEntry]) -> MockBankInterface:
    return MockBankInterface.model_validate(
        {
            "code": code,
            "label": label,
            "status": "available" if entries else "empty",
            "entries": entries,
        }
    )


def build_mock_bank_snapshot(
    session: Session,
    household_id: str,
    analysis_date: date,
) -> MockBankSnapshot:
    facts = load_household_facts(session, household_id)
    valuation_dates = [
        item.valuation_date
        for collection in (
            facts.assets,
            facts.liabilities,
            facts.insurance_policies,
            facts.social_security_accounts,
            facts.incomes,
            facts.expenses,
        )
        for item in collection
        if item.valuation_date is not None
    ]
    data_as_of = max(valuation_dates) if valuation_dates else analysis_date

    account_categories = {
        AssetCategory.CASH,
        AssetCategory.DEMAND_DEPOSIT,
        AssetCategory.MONEY_MARKET,
        AssetCategory.TIME_DEPOSIT,
    }
    wealth_categories = {AssetCategory.BANK_WEALTH_MANAGEMENT, AssetCategory.TRUST}
    fund_categories = {
        AssetCategory.BOND,
        AssetCategory.BOND_FUND,
        AssetCategory.PUBLIC_FUND,
        AssetCategory.EQUITY_FUND,
        AssetCategory.STOCK,
    }

    accounts = [
        _asset_entry(asset, boundary_note="合成账户余额；仅供竞赛 Mock 演示。")
        for asset in facts.assets
        if asset.category in account_categories
    ]
    wealth = [
        _asset_entry(
            asset,
            boundary_note="银行理财或信托不等同于存款，不承诺保本保收益。",
        )
        for asset in facts.assets
        if asset.category in wealth_categories
    ]
    funds = [
        _asset_entry(
            asset,
            boundary_note="存量基金或证券持仓仅作事实展示，不代表默认推荐。",
        )
        for asset in facts.assets
        if asset.category in fund_categories
    ]

    credit_cards: list[MockBankEntry] = []
    mortgages: list[MockBankEntry] = []
    for liability in facts.liabilities:
        if liability.category == LiabilityCategory.CREDIT_CARD_UNPAID:
            synthetic_limit = max(
                Decimal("50000.00"),
                (liability.outstanding_balance * Decimal("5")).quantize(Decimal("0.01")),
            )
            credit_cards.append(
                MockBankEntry(
                    record_id=liability.id,
                    display_name=liability.name,
                    amount=liability.outstanding_balance,
                    amount_role="liability",
                    source_record_ids=[liability.id],
                    details={
                        "mock_credit_limit": str(synthetic_limit),
                        "outstanding_balance": str(liability.outstanding_balance),
                        "annual_interest_rate": str(liability.annual_interest_rate),
                        "credit_limit_is_asset": False,
                    },
                    boundary_note="Mock 授信额度仅作备用授信信息，绝不计入家庭资产。",
                )
            )
        if liability.category == LiabilityCategory.MORTGAGE:
            mortgages.append(
                MockBankEntry(
                    record_id=liability.id,
                    display_name=liability.name,
                    amount=liability.outstanding_balance,
                    amount_role="liability",
                    source_record_ids=[liability.id],
                    details={
                        "monthly_payment": str(liability.monthly_payment),
                        "annual_interest_rate": str(liability.annual_interest_rate),
                        "maturity_date": (
                            liability.maturity_date.isoformat()
                            if liability.maturity_date is not None
                            else None
                        ),
                    },
                    boundary_note="合成房贷余额与还款计划；不代表真实银行查询。",
                )
            )

    insurance = [
        MockBankEntry(
            record_id=policy.id,
            display_name=policy.name,
            amount=policy.coverage_amount,
            amount_role="coverage",
            source_record_ids=[policy.id],
            details={
                "policy_type": policy.policy_type.value,
                "annual_premium": str(policy.annual_premium),
                "cash_value": str(policy.cash_value),
                "guaranteed_benefit": policy.guaranteed_benefit,
                "non_guaranteed_benefit": policy.non_guaranteed_benefit,
            },
            boundary_note="保额、保费、现金价值与非保证利益分列，不将保险统一描述为保本。",
        )
        for policy in facts.insurance_policies
    ]

    pension = [
        _asset_entry(
            asset,
            boundary_note="个人养老金资产按存量事实展示，受账户规则与产品风险约束。",
        )
        for asset in facts.assets
        if asset.category == AssetCategory.PENSION_ACCOUNT
    ]
    pension.extend(
        MockBankEntry(
            record_id=account.id,
            display_name=account.account_type,
            amount=account.balance,
            amount_role="information_only",
            source_record_ids=[account.id],
            details={
                "annual_personal_contribution": str(account.annual_personal_contribution),
                "annual_employer_contribution": str(account.annual_employer_contribution),
                "included_in_reconciled_assets": False,
            },
            boundary_note="社保账户信息单列，避免与已入账养老金资产重复计算。",
        )
        for account in facts.social_security_accounts
    )

    cash_flow = [
        MockBankEntry(
            record_id=item.id,
            display_name=item.name,
            amount=item.amount,
            amount_role="cashflow_in",
            source_record_ids=[item.id],
            details={"frequency": item.frequency.value, "income_type": item.income_type.value},
            boundary_note="合成现金流入；金额口径保留原始频率。",
        )
        for item in facts.incomes
    ]
    cash_flow.extend(
        MockBankEntry(
            record_id=item.id,
            display_name=item.name,
            amount=item.amount,
            amount_role="cashflow_out",
            source_record_ids=[item.id],
            details={"frequency": item.frequency.value, "category": item.category.value},
            boundary_note="合成现金流出；金额口径保留原始频率。",
        )
        for item in facts.expenses
    )

    return MockBankSnapshot(
        adapter_version=ADAPTER_VERSION,
        household_id=facts.id,
        household_code=facts.code,
        data_as_of=data_as_of,
        interfaces=[
            _interface("accounts", "账户", accounts),
            _interface("credit_cards", "信用卡", credit_cards),
            _interface("mortgages", "房贷", mortgages),
            _interface("wealth_management", "理财与信托", wealth),
            _interface("funds", "基金与证券", funds),
            _interface("insurance", "保险", insurance),
            _interface("personal_pension", "个人养老金", pension),
            _interface("cash_flow", "现金流", cash_flow),
        ],
        reconciled_asset_total=sum((asset.market_value for asset in facts.assets), Decimal("0.00")),
        reconciled_liability_total=sum(
            (item.outstanding_balance for item in facts.liabilities), Decimal("0.00")
        ),
        boundary_note=(
            "全部记录为合成数据，经项目自有 Mock 适配层返回；未连接真实银行接口，"
            "未使用任何银行官方标识，也不声称生产接入。"
        ),
    )


def audit_mock_bank_access(
    session: Session,
    snapshot: MockBankSnapshot,
    actor: ActorContext,
    request_id: str,
) -> None:
    session.add(
        AuditEvent(
            household_id=snapshot.household_id,
            event_type=AuditEventType.MOCK_BANK_DATA_ACCESSED,
            actor_id=actor.actor_id,
            actor_role=actor.role,
            entity_type="MockBankSnapshot",
            entity_id=None,
            event_version=1,
            summary="读取合成 Mock 银行接口快照",
            evidence={
                "actor": actor.actor_id,
                "role": actor.role,
                "action": "read_mock_bank_snapshot",
                "object": snapshot.household_id,
                "adapter_version": snapshot.adapter_version,
                "request_id": request_id,
                "credit_limit_in_total_assets": False,
            },
            occurred_at=utc_now(),
            data_source=ADAPTER_VERSION,
            is_user_confirmed=True,
        )
    )
    session.commit()
