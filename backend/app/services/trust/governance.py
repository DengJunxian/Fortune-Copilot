from __future__ import annotations

import re
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import ActorContext
from app.domain.enums import AuditEventType
from app.models.common import utc_now
from app.models.governance import AuditEvent, PolicyDocument, Product
from app.models.trust import KnowledgeChunk
from app.schemas.trust import (
    GovernanceIssue,
    GovernanceValidationRequest,
    GovernanceValidationResponse,
)
from app.services.trust.knowledge import scan_untrusted_instructions


def validate_governed_output(
    session: Session,
    request: GovernanceValidationRequest,
    *,
    actor: ActorContext | None = None,
    household_id: str | None = None,
) -> GovernanceValidationResponse:
    as_of = request.as_of_date or date.today()
    ledger_by_code = {entry.code: entry for entry in request.numeric_ledger}
    ledger_by_path = {entry.source_path: entry for entry in request.numeric_ledger}
    issues: list[GovernanceIssue] = []
    requires_human_review = False

    for index, claim in enumerate(request.claims):
        instruction_evidence = scan_untrusted_instructions(claim.text)
        if instruction_evidence:
            issues.append(
                GovernanceIssue(
                    code="untrusted_instruction_in_output",
                    severity="block",
                    message="输出包含看似可执行的文档指令，已按不可信数据拦截。",
                    claim_index=index,
                    evidence=instruction_evidence,
                )
            )
        if re.search(r"保本保收益|稳赚不赔|保证.{0,12}(?:收益|回报)", claim.text):
            issues.append(
                GovernanceIssue(
                    code="prohibited_financial_promise",
                    severity="block",
                    message="输出包含保本或收益保证表述。",
                    claim_index=index,
                )
            )
        if "最低工资等于CPI" in claim.text or "最低工资就是CPI" in claim.text:
            issues.append(
                GovernanceIssue(
                    code="minimum_wage_cpi_conflation",
                    severity="block",
                    message="最低工资与 CPI 口径被错误合并。",
                    claim_index=index,
                )
            )
        if (
            request.ordinary_household_path
            and any(product in claim.text for product in ("股指期货", "杠杆", "集中个股"))
            and any(action in claim.text for action in ("推荐", "买入", "加仓", "配置"))
        ):
            issues.append(
                GovernanceIssue(
                    code="high_risk_default_recommendation",
                    severity="block",
                    message="普通家庭默认路径不得推荐个股、杠杆或股指期货。",
                    claim_index=index,
                )
            )
            requires_human_review = True

        if claim.claim_type == "numeric":
            if claim.tool_reference is None:
                issues.append(
                    GovernanceIssue(
                        code="numeric_without_tool_reference",
                        severity="block",
                        message="数字声明缺少确定性工具引用。",
                        claim_index=index,
                    )
                )
                continue
            entry = ledger_by_code.get(claim.tool_reference) or ledger_by_path.get(
                claim.tool_reference
            )
            if entry is None:
                issues.append(
                    GovernanceIssue(
                        code="numeric_tool_reference_not_found",
                        severity="block",
                        message="数字声明引用的工具输出不存在。",
                        claim_index=index,
                        evidence=[claim.tool_reference],
                    )
                )
            elif claim.value is None or claim.value != entry.value:
                issues.append(
                    GovernanceIssue(
                        code="numeric_value_mismatch",
                        severity="block",
                        message="声明数值与确定性工具账本不一致。",
                        claim_index=index,
                        evidence=[f"expected={entry.value}", f"observed={claim.value}"],
                    )
                )

        if claim.claim_type == "policy":
            if not claim.citation_chunk_ids:
                issues.append(
                    GovernanceIssue(
                        code="policy_without_citation",
                        severity="block",
                        message="政策声明缺少受控来源和有效期。",
                        claim_index=index,
                    )
                )
            for chunk_id in claim.citation_chunk_ids:
                row = session.execute(
                    select(KnowledgeChunk, PolicyDocument)
                    .join(PolicyDocument, KnowledgeChunk.document_id == PolicyDocument.id)
                    .where(
                        KnowledgeChunk.id == chunk_id,
                        KnowledgeChunk.is_deleted.is_(False),
                        PolicyDocument.is_deleted.is_(False),
                    )
                ).one_or_none()
                if row is None:
                    issues.append(
                        GovernanceIssue(
                            code="policy_citation_not_found",
                            severity="block",
                            message="政策引用不在受控知识库中。",
                            claim_index=index,
                            evidence=[chunk_id],
                        )
                    )
                    continue
                chunk, document = row
                if chunk.security_status != "clean":
                    issues.append(
                        GovernanceIssue(
                            code="policy_citation_quarantined",
                            severity="block",
                            message="政策引用命中已隔离的不可信指令片段。",
                            claim_index=index,
                            evidence=[chunk.code],
                        )
                    )
                if document.effective_date > as_of or (
                    document.expiry_date is not None and document.expiry_date < as_of
                ):
                    issues.append(
                        GovernanceIssue(
                            code="policy_citation_out_of_date",
                            severity="block",
                            message="政策引用在指定日期尚未生效或已经失效。",
                            claim_index=index,
                            evidence=[
                                document.code or document.id,
                                document.effective_date.isoformat(),
                                document.expiry_date.isoformat()
                                if document.expiry_date
                                else "no_expiry_recorded",
                            ],
                        )
                    )

        if claim.claim_type == "product":
            if claim.product_code is None or claim.product_catalog_version is None:
                issues.append(
                    GovernanceIssue(
                        code="product_reference_incomplete",
                        severity="block",
                        message="产品声明必须引用受控产品代码和目录版本。",
                        claim_index=index,
                    )
                )
                continue
            product = session.scalar(
                select(Product).where(
                    Product.code == claim.product_code,
                    Product.enabled.is_(True),
                    Product.is_deleted.is_(False),
                )
            )
            if product is None:
                issues.append(
                    GovernanceIssue(
                        code="product_not_in_controlled_catalog",
                        severity="block",
                        message="产品不在启用的受控目录中。",
                        claim_index=index,
                        evidence=[claim.product_code],
                    )
                )
            elif product.catalog_version != claim.product_catalog_version:
                issues.append(
                    GovernanceIssue(
                        code="product_catalog_version_mismatch",
                        severity="block",
                        message="产品目录版本与受控记录不一致。",
                        claim_index=index,
                        evidence=[
                            f"expected={product.catalog_version}",
                            f"observed={claim.product_catalog_version}",
                        ],
                    )
                )

    blocked = any(issue.severity == "block" for issue in issues)
    if blocked and actor is not None:
        session.add(
            AuditEvent(
                household_id=household_id,
                event_type=AuditEventType.HALLUCINATION_BLOCKED,
                actor_id=actor.actor_id,
                actor_role=actor.role,
                entity_type="GovernanceValidation",
                entity_id=None,
                event_version=1,
                summary=f"反幻觉校验拦截 {sum(issue.severity == 'block' for issue in issues)} 项",
                evidence={
                    "issue_codes": [issue.code for issue in issues],
                    "claim_count": len(request.claims),
                    "as_of_date": as_of.isoformat(),
                },
                occurred_at=utc_now(),
                valuation_date=as_of,
                data_source="deterministic_governance_validator",
                is_user_confirmed=True,
            )
        )
        session.commit()
    return GovernanceValidationResponse(
        passed=not blocked,
        blocked=blocked,
        requires_human_review=requires_human_review,
        issues=issues,
        validated_claim_count=len(request.claims),
    )
