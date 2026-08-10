from __future__ import annotations

from datetime import UTC, datetime

from app.core.config import Settings
from app.core.errors import AppError
from app.schemas.integrations import (
    AuthoritativeSourceReference,
    CapabilityReadiness,
    IntegrationCapabilityCode,
    IntegrationReadinessResponse,
    IntegrationRequest,
    IntegrationResult,
    OperationalControlReadiness,
)
from app.services.integrations.fail_closed import UnavailableProductionAdapter
from app.services.integrations.ports import ProductionIntegrationPort
from app.services.public_data.rules import (
    load_public_data_snapshot,
    public_data_integrity_hash,
)

ASSESSMENT_VERSION = "fortune-copilot-production-readiness-v1.0.0"

PRIVATE_CAPABILITIES: dict[IntegrationCapabilityCode, tuple[str, tuple[str, ...]]] = {
    "identity_access_management": (
        "IAM 与最小权限",
        ("工行身份提供方信任关系", "MFA/设备风险策略", "角色与家庭对象授权映射"),
    ),
    "customer_consent_authorization": (
        "客户授权与用途控制",
        ("客户有效授权", "用途和范围", "撤回与有效期", "敏感个人信息单独同意"),
    ),
    "kyc_cdd_edd_aml": (
        "KYC、CDD/EDD 与 AML",
        ("客户身份核验", "受益所有人/代理关系", "风险评级", "持续尽调与可疑交易系统"),
    ),
    "bank_account_and_cashflow_data": (
        "账户、流水与贷款事实",
        ("客户授权", "工行数据服务协议", "生产凭据/证书", "账务口径与对账规则"),
    ),
    "social_security_provident_pension_data": (
        "社保、公积金与养老金事实",
        ("客户授权", "依法可用的数据共享渠道", "字段级用途控制", "数据质量与对账"),
    ),
    "product_master_and_channel_inventory": (
        "产品主数据、库存与渠道权限",
        ("产品主数据协议", "可售/费率/库存实时源", "渠道权限", "快照时效 SLA"),
    ),
    "transaction_suitability_order_settlement_positions": (
        "交易时点检查、订单、清算与持仓回写",
        ("交易网关", "交易时点适当性", "双录/确认规则", "订单清算与对账", "幂等控制"),
    ),
    "advisor_crm_and_human_accountability": (
        "客户经理 CRM 与人工责任节点",
        ("CRM 工单接口", "客户经理组织与权限", "职责分离", "人工签署和审计回写"),
    ),
    "market_property_regime_committee": (
        "投研委员会 Market/Property Regime",
        ("投研委员会发布流程", "批准人和有效期", "证据附件", "撤回/替换机制"),
    ),
}


class IntegrationRegistry:
    def __init__(self) -> None:
        self._adapters: dict[IntegrationCapabilityCode, ProductionIntegrationPort] = {
            capability: UnavailableProductionAdapter(capability, prerequisites)
            for capability, (_label, prerequisites) in PRIVATE_CAPABILITIES.items()
        }

    def register(self, adapter: ProductionIntegrationPort) -> None:
        if adapter.capability not in PRIVATE_CAPABILITIES:
            raise ValueError("only bank-private production ports can be registered")
        self._adapters[adapter.capability] = adapter

    def execute(
        self,
        capability: IntegrationCapabilityCode,
        request: IntegrationRequest,
    ) -> IntegrationResult:
        adapter = self._adapters.get(capability)
        if adapter is None:
            raise AppError(
                "integration_not_executable",
                "该能力不是可执行的银行私有适配器",
                status_code=409,
                details={"capability": capability},
            )
        return adapter.execute(request)

    def adapter(self, capability: IntegrationCapabilityCode) -> ProductionIntegrationPort:
        adapter = self._adapters.get(capability)
        if adapter is None:
            raise KeyError(capability)
        return adapter


default_registry = IntegrationRegistry()


def build_integration_readiness(settings: Settings) -> IntegrationReadinessResponse:
    public_data = load_public_data_snapshot(settings.public_data_snapshot_path)
    capabilities: list[CapabilityReadiness] = []
    for capability, (label, prerequisites) in PRIVATE_CAPABILITIES.items():
        adapter = default_registry.adapter(capability)
        capabilities.append(
            CapabilityReadiness(
                capability=capability,
                label=label,
                state=(
                    "authorization_required"
                    if capability
                    in {
                        "customer_consent_authorization",
                        "bank_account_and_cashflow_data",
                        "social_security_provident_pension_data",
                    }
                    else "governance_required"
                    if capability in {"market_property_regime_committee"}
                    else "contract_required"
                ),
                adapter_id=adapter.adapter_id,
                execution_allowed=adapter.is_live,
                production_blocking=not adapter.is_live,
                current_implementation=(
                    "本地领域模型/工作流已实现；银行生产端口默认绑定 fail-closed adapter。"
                ),
                required_prerequisites=list(prerequisites),
                evidence=[
                    "未配置任何工行客户数据、产品数据或交易凭据",
                    "Mock 数据只能用于教育演示，不得作为生产事实回填",
                ],
            )
        )

    capabilities.extend(
        [
            CapabilityReadiness(
                capability="regional_public_data_pipeline",
                label="权威地区与政策公共数据",
                state="available_public_snapshot",
                adapter_id="governed-public-snapshot-loader",
                execution_allowed=True,
                production_blocking=False,
                current_implementation=(
                    "官方域名白名单、Pydantic 结构校验、统计口径标签、版本和 SHA-256 完整性哈希。"
                ),
                required_prerequisites=["定期双人复核", "新版本批准", "来源失效告警"],
                evidence=[
                    public_data.snapshot_version,
                    "运行时不抓取网页；只读取已批准的不可变快照",
                ],
            ),
            CapabilityReadiness(
                capability="model_independent_validation_monitoring",
                label="模型独立验证、漂移与公平性监控",
                state="implemented_local_only",
                adapter_id="deterministic-model-governance-evaluator",
                execution_allowed=True,
                production_blocking=True,
                current_implementation=(
                    "已实现确定性阈值评估和降级判定；尚无工行独立验证批准、生产基线或监控遥测。"
                ),
                required_prerequisites=["独立验证报告", "批准编号", "生产基线", "持续监控数据"],
                evidence=["LLM 不可用时确定性规划引擎仍可运行"],
            ),
            CapabilityReadiness(
                capability="sre_dr_multichannel",
                label="SRE、灾备与全渠道",
                state="operational_evidence_required",
                adapter_id="local-health-and-readiness-probes",
                execution_allowed=False,
                production_blocking=True,
                current_implementation=(
                    "本地健康检查与容器启动探针已实现；生产高可用、恢复演练和全渠道部署未完成。"
                ),
                required_prerequisites=[
                    "RTO/RPO 批准",
                    "恢复演练",
                    "多活/容灾",
                    "监控告警",
                    "渠道验收",
                ],
                evidence=["不得以 Docker Compose 本地运行替代银行级容灾证明"],
            ),
        ]
    )

    controls = [
        OperationalControlReadiness(
            code="liveness_readiness",
            label="存活与就绪探针",
            state="implemented_local_only",
            production_blocking=False,
            evidence="API 与数据库健康探针可用；外部银行依赖在 readiness 中单独阻断。",
        ),
        OperationalControlReadiness(
            code="backup_restore",
            label="备份恢复",
            state="requires_verified_drill",
            production_blocking=True,
            evidence="仓库没有经工行批准的备份介质、恢复演练记录或 RPO 证明。",
        ),
        OperationalControlReadiness(
            code="high_availability_disaster_recovery",
            label="高可用与灾备",
            state="requires_bank_platform",
            production_blocking=True,
            evidence="需要工行基础设施、网络隔离、容量管理、灾备切换与演练。",
        ),
        OperationalControlReadiness(
            code="multichannel_delivery",
            label="全渠道交付",
            state="requires_bank_platform",
            production_blocking=True,
            evidence="需要手机银行、网银、网点和客户经理渠道的身份、权限及发布体系。",
        ),
    ]
    source_refs = [
        AuthoritativeSourceReference(
            code=item.code,
            title=item.title,
            authority=item.authority,
            source_reference=str(item.source_reference),
            effective_from=item.effective_from,
        )
        for item in public_data.policy_sources
    ]
    source_refs.extend(
        AuthoritativeSourceReference(
            code=item.code,
            title=item.public_description,
            authority=item.authority,
            source_reference=str(item.source_reference),
        )
        for item in public_data.integration_access_boundaries
    )
    production_ready = not any(item.production_blocking for item in capabilities) and not any(
        item.production_blocking for item in controls
    )
    return IntegrationReadinessResponse(
        assessment_version=ASSESSMENT_VERSION,
        assessed_at=datetime.now(UTC),
        runtime_mode=settings.app_env,
        production_ready=production_ready,
        public_data_snapshot_version=public_data.snapshot_version,
        public_data_integrity_hash=public_data_integrity_hash(public_data),
        capabilities=capabilities,
        operational_controls=controls,
        authoritative_sources=source_refs,
        boundary_note=(
            "互联网公开资料只能确认法规、公开参数和接入流程，不能授予客户数据、工行系统、"
            "产品库存、交易、CRM 或投研权限；这些能力在真实适配器和审批证据到位前保持硬阻断。"
        ),
    )
