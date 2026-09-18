from __future__ import annotations

import hashlib
import re
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import ActorContext, require_household_access
from app.core.errors import AppError
from app.domain.enums import AuditEventType, IntakeDraftStatus
from app.models.common import utc_now
from app.models.family import Household
from app.models.governance import AuditEvent
from app.models.trust import IntakeDraft
from app.schemas.trust import (
    ConfirmIntakeDraftRequest,
    ExtractedDraftField,
    IntakeDraftRequest,
    IntakeDraftResponse,
    MissingDraftField,
)
from app.services.security.model_risk import record_model_run
from app.services.trust.knowledge import scan_untrusted_instructions

PARSER_VERSION = "deterministic-zh-intake-v1.1.0"
CHINESE_DIGITS = {
    "零": 0,
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}
SMALL_UNITS = {"十": 10, "百": 100, "千": 1000}
BIG_UNITS = {"万": 10000, "亿": 100000000}
MONEY_TOKEN = r"[零一二两三四五六七八九十百千万亿\d.,]+"

MISSING_FIELD_DEFINITIONS = (
    (
        "living_expenses",
        "必要生活支出",
        "原文未提供完整支出",
        ["结余", "应急金"],
        1,
        "家庭每月必要生活支出大约是多少?",
    ),
    (
        "assets",
        "家庭资产",
        "原文未提供资产余额",
        ["净资产", "四账户"],
        1,
        "目前现金、存款、理财和其他主要资产分别有多少?",
    ),
    (
        "insurance",
        "现有保险",
        "原文未提供保障事实",
        ["保障缺口"],
        1,
        "家庭成员目前有哪些医疗、重疾、寿险或意外保障?",
    ),
    (
        "education_target_stage",
        "留学阶段",
        "原文未说明教育阶段",
        ["教育目标"],
        1,
        "预计在哪个教育阶段留学?",
    ),
    (
        "education_destination_detail",
        "目标地区",
        "只识别到海外方向，未说明地区",
        ["教育成本"],
        1,
        "留学的目标国家或地区是哪里?",
    ),
    (
        "education_prepared_amount",
        "已准备教育资金",
        "原文未提供已准备金额",
        ["教育缺口"],
        1,
        "当前已经为教育目标准备了多少资金?",
    ),
    (
        "mortgage_balance",
        "房贷余额",
        "月供不能推导贷款余额",
        ["资产负债表", "偿债压力"],
        2,
        "当前房贷剩余本金是多少?",
    ),
    (
        "member_ages",
        "家庭成员年龄",
        "原文没有完整年龄",
        ["生命周期", "退休期限"],
        2,
        "请补充两位成人的年龄。",
    ),
    (
        "mortgage_rate",
        "房贷利率",
        "原文未提供合同利率",
        ["利息成本", "提前还款比较"],
        2,
        "房贷当前执行利率是多少?",
    ),
    (
        "mortgage_term",
        "房贷剩余期限",
        "原文未提供到期日",
        ["现金流压力", "生命周期"],
        2,
        "房贷还剩多少年?",
    ),
    (
        "education_horizon_years",
        "教育目标期限",
        "原文未提供明确年限",
        ["目标规划"],
        2,
        "预计从哪一年开始使用教育资金?",
    ),
    (
        "education_goal_amount",
        "教育目标金额",
        "原文未提供明确金额",
        ["目标规划"],
        2,
        "教育目标总预算大约是多少?",
    ),
    (
        "salary_split",
        "夫妻收入拆分",
        "只提供合计收入，未说明各自金额",
        ["收入稳定性", "失业压力"],
        3,
        "两位成人的税后月收入分别是多少?",
    ),
)


def _chinese_integer(value: str) -> int:
    section = 0
    total = 0
    number = 0
    for char in value:
        if char in CHINESE_DIGITS:
            number = CHINESE_DIGITS[char]
        elif char in SMALL_UNITS:
            unit = SMALL_UNITS[char]
            section += (number or 1) * unit
            number = 0
        elif char in BIG_UNITS:
            unit = BIG_UNITS[char]
            total += (section + number or 1) * unit
            section = 0
            number = 0
    return total + section + number


def parse_money(value: str) -> Decimal:
    normalized = value.replace(",", "").replace("，", "").strip()
    if re.fullmatch(r"\d+(?:\.\d+)?(?:万|千|百|亿)?", normalized):
        unit = Decimal("1")
        if normalized[-1:] in {"万", "千", "百", "亿"}:
            unit = Decimal(
                str({"百": 100, "千": 1000, "万": 10000, "亿": 100000000}[normalized[-1]])
            )
            normalized = normalized[:-1]
        return (Decimal(normalized) * unit).quantize(Decimal("0.01"))
    return Decimal(_chinese_integer(normalized)).quantize(Decimal("0.01"))


def _money_field(
    text: str,
    *,
    code: str,
    label: str,
    pattern: str,
    unit: str = "CNY/month",
) -> ExtractedDraftField | None:
    match = re.search(pattern, text)
    if match is None:
        return None
    token = match.group("amount")
    try:
        amount = parse_money(token)
    except (ArithmeticError, ValueError):
        return None
    return ExtractedDraftField(
        code=code,
        label=label,
        value=f"{amount:.2f}",
        value_type="money",
        unit=unit,
        evidence=match.group(0),
        confidence=Decimal("0.980000"),
        confirmed=False,
    )


def extract_intake_fields(text: str) -> tuple[list[ExtractedDraftField], list[MissingDraftField]]:
    extracted: list[ExtractedDraftField] = []
    salary = _money_field(
        text,
        code="joint_monthly_salary",
        label="夫妻月工资合计",
        pattern=(
            rf"(?:每月|每个月|月)?(?:税后)?(?:工资|收入)(?:合计|共|一共)?"
            rf"(?:大约|约|近)?\s*"
            rf"(?P<amount>{MONEY_TOKEN})(?:元)?"
        ),
    )
    if salary is not None:
        extracted.append(salary)
    mortgage = _money_field(
        text,
        code="monthly_mortgage_payment",
        label="每月房贷",
        pattern=rf"房贷(?:月供|每月|月)?\s*(?P<amount>{MONEY_TOKEN})(?:元)?",
    )
    if mortgage is not None:
        extracted.append(mortgage)
    mortgage_balance = _money_field(
        text,
        code="mortgage_balance",
        label="房贷余额",
        pattern=rf"(?P<amount>{MONEY_TOKEN})(?:元)?(?:的)?房贷(?:余额)?",
        unit="CNY",
    )
    if mortgage_balance is not None:
        extracted.append(mortgage_balance)
    if re.search(r"(?:我和爱人|我和配偶|夫妻|爱人)", text):
        extracted.append(
            ExtractedDraftField(
                code="spouse_present",
                label="配偶关系",
                value="true",
                value_type="relationship",
                evidence=re.search(r"(?:我和爱人|我和配偶|夫妻|爱人)", text).group(0),  # type: ignore[union-attr]
                confidence=Decimal("0.990000"),
                confirmed=False,
            )
        )
    child_stage = re.search(r"(?:孩子|子女).{0,4}(幼儿园|托班|小学|初中|高中|大学)", text)
    if child_stage is not None:
        extracted.append(
            ExtractedDraftField(
                code="child_education_stage",
                label="子女教育阶段",
                value=child_stage.group(1),
                value_type="stage",
                evidence=child_stage.group(0),
                confidence=Decimal("0.970000"),
                confirmed=False,
            )
        )
    child_age = re.search(r"(?:孩子|小孩|子女)(?:今年)?\s*(?P<age>\d{1,2})\s*岁", text)
    if child_age is not None:
        age = int(child_age.group("age"))
        extracted.append(
            ExtractedDraftField(
                code="child_age",
                label="子女年龄",
                value=str(age),
                value_type="count",
                unit="岁",
                evidence=child_age.group(0),
                confidence=Decimal("0.990000"),
                confirmed=False,
            )
        )
        inferred_stage = (
            "学龄前"
            if age <= 6
            else "小学阶段"
            if age <= 12
            else "中学阶段"
            if age <= 18
            else "成年阶段"
        )
        extracted.append(
            ExtractedDraftField(
                code="child_lifecycle_stage",
                label="子女生命周期阶段",
                value=inferred_stage,
                value_type="stage",
                evidence=child_age.group(0),
                confidence=Decimal("0.900000"),
                confirmed=False,
            )
        )
    location = re.search(r"在(?P<location>[\u4e00-\u9fff]{2,8})(?:工作|生活|居住)", text)
    if location is not None:
        extracted.append(
            ExtractedDraftField(
                code="household_location",
                label="家庭所在地",
                value=location.group("location"),
                value_type="text",
                evidence=location.group(0),
                confidence=Decimal("0.980000"),
                confirmed=False,
            )
        )
    overseas_goal = re.search(r"(?:国外|海外|留学)", text)
    if overseas_goal is not None and re.search(r"(?:孩子|小孩|子女|教育|大学)", text):
        extracted.extend(
            [
                ExtractedDraftField(
                    code="education_goal_present",
                    label="子女教育目标",
                    value="true",
                    value_type="relationship",
                    evidence=overseas_goal.group(0),
                    confidence=Decimal("0.960000"),
                    confirmed=False,
                ),
                ExtractedDraftField(
                    code="education_goal_region",
                    label="教育目标方向",
                    value="海外（待确认国家或地区）",
                    value_type="text",
                    evidence=overseas_goal.group(0),
                    confidence=Decimal("0.940000"),
                    confirmed=False,
                ),
            ]
        )
    primary_age = re.search(r"(?:我|本人)(?:今年)?\s*(?P<age>\d{1,2})\s*岁", text)
    if primary_age is not None:
        extracted.append(
            ExtractedDraftField(
                code="member_ages",
                label="本人年龄",
                value=primary_age.group("age"),
                value_type="count",
                unit="岁",
                evidence=primary_age.group(0),
                confidence=Decimal("0.990000"),
                confirmed=False,
            )
        )
    education_horizon = re.search(
        rf"(?P<years>{MONEY_TOKEN})年(?:后|内).{{0,16}}(?:子女)?教育", text
    )
    if education_horizon is not None:
        token = education_horizon.group("years")
        years = int(parse_money(token))
        if 1 <= years <= 60:
            extracted.append(
                ExtractedDraftField(
                    code="education_horizon_years",
                    label="教育目标期限",
                    value=str(years),
                    value_type="count",
                    unit="年",
                    evidence=education_horizon.group(0),
                    confidence=Decimal("0.980000"),
                    confirmed=False,
                )
            )
    education_amount = _money_field(
        text,
        code="education_goal_amount",
        label="教育目标金额",
        pattern=rf"(?:子女)?教育(?:资金|金|目标|费用)?\s*(?P<amount>{MONEY_TOKEN})(?:元)?",
        unit="CNY",
    )
    if education_amount is not None:
        extracted.append(education_amount)
    extracted_codes = {item.code for item in extracted}
    missing = [
        MissingDraftField(
            code=code,
            label=label,
            reason=reason,
            required_for=required_for,
            priority=priority,
            follow_up_question=question,
        )
        for code, label, reason, required_for, priority, question in MISSING_FIELD_DEFINITIONS
        if code not in extracted_codes
    ]
    if salary is None:
        missing.insert(
            0,
            MissingDraftField(
                code="joint_monthly_salary",
                label="家庭月收入",
                reason="未识别到明确金额",
                required_for=["现金流", "结余"],
                priority=1,
                follow_up_question="家庭税后月收入合计大约是多少?",
            ),
        )
    if mortgage is None:
        missing.insert(
            0,
            MissingDraftField(
                code="monthly_mortgage_payment",
                label="每月房贷",
                reason="未识别到明确金额",
                required_for=["现金流", "偿债压力"],
                priority=2,
                follow_up_question="目前每月房贷月供是多少?",
            ),
        )
    missing.sort(key=lambda item: (item.priority, item.code))
    return extracted, missing


def _preview(text: str) -> str:
    redacted = re.sub(MONEY_TOKEN + r"(?:元)?", "[金额]", text)
    return redacted[:240]


def _draft_out(draft: IntakeDraft) -> IntakeDraftResponse:
    confirmed = {str(key): str(value) for key, value in draft.confirmed_values.items()}
    fields = [ExtractedDraftField.model_validate(item) for item in draft.extracted_fields]
    for field in fields:
        field.confirmed = field.code in confirmed
        if field.confirmed:
            field.value = confirmed[field.code]
    return IntakeDraftResponse(
        draft_id=draft.id,
        household_id=draft.household_id,
        status=draft.status.value,
        parser_version=draft.parser_version,
        source_text_hash=draft.source_text_hash,
        redacted_preview=draft.redacted_preview,
        extracted_fields=fields,
        missing_fields=[MissingDraftField.model_validate(item) for item in draft.missing_fields],
        confirmed_values=confirmed,
        contains_untrusted_instruction=draft.contains_untrusted_instruction,
        confirmation_required=draft.status != IntakeDraftStatus.CONFIRMED,
        created_at=draft.created_at,
        confirmed_at=draft.confirmed_at,
        boundary_note=(
            "这是结构化草稿，不会直接写入家庭事实；每个提取值都需确认，未提供的金额保持缺失。"
        ),
    )


def create_intake_draft(
    session: Session,
    request: IntakeDraftRequest,
    actor: ActorContext,
) -> IntakeDraftResponse:
    if request.household_id is not None:
        household = session.scalar(
            select(Household).where(
                Household.id == request.household_id,
                Household.is_deleted.is_(False),
            )
        )
        if household is None:
            raise AppError("household_not_found", "家庭不存在", status_code=404)
    extracted, missing = extract_intake_fields(request.text)
    instruction_evidence = scan_untrusted_instructions(request.text)
    draft = IntakeDraft(
        household_id=request.household_id,
        source_text_hash=hashlib.sha256(request.text.encode("utf-8")).hexdigest(),
        redacted_preview=_preview(request.text),
        parser_version=PARSER_VERSION,
        status=IntakeDraftStatus.PENDING_CONFIRMATION,
        extracted_fields=[field.model_dump(mode="json") for field in extracted],
        missing_fields=[field.model_dump(mode="json") for field in missing],
        confirmed_values={},
        contains_untrusted_instruction=bool(instruction_evidence),
        valuation_date=utc_now().date(),
        data_source="deterministic_intake_parser",
        is_user_confirmed=False,
    )
    session.add(draft)
    session.flush()
    session.add(
        AuditEvent(
            household_id=request.household_id,
            event_type=AuditEventType.INTAKE_DRAFT_CREATED,
            actor_id=actor.actor_id,
            actor_role=actor.role,
            entity_type="IntakeDraft",
            entity_id=draft.id,
            event_version=draft.version,
            summary=f"生成自然语言录入草稿，提取 {len(extracted)} 项，缺失 {len(missing)} 项",
            evidence={
                "source_text_hash": draft.source_text_hash,
                "field_codes": [field.code for field in extracted],
                "missing_codes": [field.code for field in missing],
                "untrusted_instruction_evidence": instruction_evidence,
            },
            occurred_at=draft.created_at,
            valuation_date=draft.valuation_date,
            data_source="deterministic_intake_parser",
            is_user_confirmed=True,
        )
    )
    record_model_run(
        session,
        household_id=request.household_id,
        actor=actor,
        provider="deterministic_parser",
        model_name=PARSER_VERSION,
        task="information_extraction",
        prompt_version=PARSER_VERSION,
        inputs={
            "intent": "household_intake",
            "verified_fact_refs": [],
            "missing_fields": [field.code for field in missing],
            "risk_flags": instruction_evidence,
        },
        output={
            "extracted_field_codes": [field.code for field in extracted],
            "missing_field_codes": [field.code for field in missing],
        },
        started_at=draft.created_at,
        degraded=bool(instruction_evidence),
        prompt_injection_detected=bool(instruction_evidence),
        human_review_required=bool(instruction_evidence),
        fallback_reason="untrusted_instruction_quarantined" if instruction_evidence else None,
    )
    session.commit()
    session.refresh(draft)
    return _draft_out(draft)


def get_intake_draft(
    session: Session,
    draft_id: str,
    actor: ActorContext,
) -> IntakeDraftResponse:
    draft = session.scalar(
        select(IntakeDraft).where(IntakeDraft.id == draft_id, IntakeDraft.is_deleted.is_(False))
    )
    if draft is None:
        raise AppError("intake_draft_not_found", "录入草稿不存在", status_code=404)
    if draft.household_id is not None:
        require_household_access(actor, draft.household_id)
    return _draft_out(draft)


def confirm_intake_draft(
    session: Session,
    draft_id: str,
    request: ConfirmIntakeDraftRequest,
    actor: ActorContext,
) -> IntakeDraftResponse:
    draft = session.scalar(
        select(IntakeDraft).where(IntakeDraft.id == draft_id, IntakeDraft.is_deleted.is_(False))
    )
    if draft is None:
        raise AppError("intake_draft_not_found", "录入草稿不存在", status_code=404)
    if draft.household_id is not None:
        require_household_access(actor, draft.household_id)
    extracted_codes = {str(item["code"]) for item in draft.extracted_fields}
    missing_codes = {str(item["code"]) for item in draft.missing_fields}
    unknown_codes = sorted(set(request.confirmed_values) - extracted_codes - missing_codes)
    if unknown_codes:
        raise AppError(
            "unknown_intake_field",
            "确认请求包含未定义字段",
            status_code=422,
            details={"field_codes": unknown_codes},
        )
    normalized = {key: str(value).strip() for key, value in request.confirmed_values.items()}
    if any(not value for value in normalized.values()):
        raise AppError("empty_confirmed_value", "确认值不能为空", status_code=422)
    draft.confirmed_values = {**draft.confirmed_values, **normalized}
    all_extracted_confirmed = extracted_codes.issubset(draft.confirmed_values)
    draft.status = (
        IntakeDraftStatus.CONFIRMED
        if all_extracted_confirmed
        else IntakeDraftStatus.PARTIALLY_CONFIRMED
    )
    draft.confirmed_at = utc_now() if all_extracted_confirmed else None
    draft.is_user_confirmed = all_extracted_confirmed
    draft.version += 1
    session.add(
        AuditEvent(
            household_id=draft.household_id,
            event_type=AuditEventType.INTAKE_DRAFT_CONFIRMED,
            actor_id=actor.actor_id,
            actor_role=actor.role,
            entity_type="IntakeDraft",
            entity_id=draft.id,
            event_version=draft.version,
            summary=(
                "自然语言录入草稿已逐项确认"
                if all_extracted_confirmed
                else "自然语言录入草稿部分确认"
            ),
            evidence={
                "confirmed_field_codes": sorted(draft.confirmed_values),
                "remaining_extracted_codes": sorted(extracted_codes - set(draft.confirmed_values)),
                "writes_to_household_facts": False,
            },
            occurred_at=utc_now(),
            valuation_date=draft.valuation_date,
            data_source="user_confirmation",
            is_user_confirmed=True,
        )
    )
    session.commit()
    session.refresh(draft)
    return _draft_out(draft)
