# Fortune Copilot 数据字典

版本：Stage 13 / 2026-08-05  
迁移：`0013_demo_release`  
默认币种：CNY

## 数据治理约定

除 `runtime_metadata` 外，所有领域表共享以下字段：

| 字段 | 类型 | 规则 |
| --- | --- | --- |
| id | String(36) | 应用生成 UUID，主键 |
| currency | String(3) | ISO 4217 三位大写代码；默认 CNY |
| valuation_date | Date, nullable | 数据对应的估值／观察日期 |
| data_source | String(64) | `user`、合成数据版本或后续受控接口标识 |
| is_user_confirmed | Boolean | 是否经过用户确认；估算值必须为 false |
| version | Integer | 从 1 开始的乐观并发版本；更新与软删除均递增 |
| created_at / updated_at | DateTime | UTC 审计时间 |
| is_deleted / deleted_at | Boolean / DateTime | 软删除状态；普通查询默认排除 |

货币字段统一使用 `Numeric(20, 2)` 和 Python `Decimal`。API 金额必须使用十进制字符串或整数，拒绝 JSON 二进制浮点值。比例和概率使用 `Numeric(9, 6)`；取值范围由 Pydantic Schema 校验。

健康信息只保存 `health_risk_level`，不建立诊断、病历、检查报告或自由文本病史字段。日志和审计事件只记录实体、版本、动作及调用方，不记录完整财务载荷。

## 家庭与授权

| 实体／表 | 作用 | 关键字段与关系 |
| --- | --- | --- |
| Household / households | 家庭聚合根 | code、name、lifecycle_stage、region、demo_profile、is_synthetic |
| HouseholdMember / household_members | 家庭成员 | household_id → Household；relationship、birth_date、occupation、employment_stability、expected_retirement_age、health_risk_level |
| ConsentRecord / consent_records | 分场景最小必要授权记录 | household_id；可选 member_id；scopes、purpose、granted_at、withdrawn_at、consent_version；metadata_json 固定记录 scenario、explicit、sensitive_data_acknowledged，敏感范围必须独立授权 |
| IdentityAccessGrant / identity_access_grants | 身份区到财务对象的去标识授权映射 | actor_subject_hash、actor_role、household_id、allowed_actions、purpose、valid_until、revoked_at；主体原值与登录凭证不进入财务表 |
| PrivacyRequest / privacy_requests | 可审计隐私权利请求 | 可空 household_id、household_ref_hash、request_type、status、scope、reason_hash、requested_by_hash、confirmation_method、result_summary、completed_at；擦除后只留最小墓碑证据 |

## 家庭财务事实

| 实体／表 | 作用 | 关键字段与关系 |
| --- | --- | --- |
| IncomeSource / income_sources | 收入来源 | household_id、member_id、income_type、amount、frequency、stability、volatility、interruption_probability、cycle_correlation、source_concentration、is_sustainable |
| ExpenseItem / expense_items | 支出项目 | household_id、member_id、amount、frequency、necessity、compressible_ratio、seasonality、category |
| Asset / assets | 已有资产 | category、subcategory、acquisition_cost、market_value、liquidity_days、liquidity_level、risk_level、purpose、pledged、ownership、owner_member_id、property_use |
| Liability / liabilities | 已有负债 | category、outstanding_balance、annual_interest_rate、monthly_payment、maturity_date、rate_type、prepayment_cost、linked_asset_id、borrower_member_id、is_high_interest |
| InsurancePolicy / insurance_policies | 商业保险合同事实 | policy_type、insured_member_id、coverage_amount、annual_premium、start_date、end_date、deductible、waiting_period_days、guaranteed_benefit、non_guaranteed_benefit、cash_value |
| SocialSecurityAccount / social_security_accounts | 社保、公积金、年金等 | member_id、account_type、balance、annual_personal_contribution、annual_employer_contribution、benefit_region |
| FinancialGoal / financial_goals | 家庭目标 | goal_type、target_amount、target_date、rigidity、priority、can_defer、minimum_acceptable_amount、prepared_amount、annual_cost_growth_rate |

`InsurancePolicy.guaranteed_benefit` 只记录具体合同条款中明确的保证利益金额；它不代表将银行理财、基金、信托、保险整体描述为保本产品。信用卡可用额度没有对应 Asset 字段；只有已经发生的信用卡未付进入 Liability。

## 画像、计算与方案

| 实体／表 | 作用 | 关键字段与关系 |
| --- | --- | --- |
| RiskAssessment / risk_assessments | 四维风险测评 | capacity_score、willingness_score、knowledge_score、behavior_score、final_risk_limit、explanation |
| BehaviorAssessment / behavior_assessments | 行为问卷与实验画像 | questionnaire_score、experiment_score、final_behavior_limit、detected_biases、experiment_answers、explanation |
| BehaviorExperimentSession / behavior_experiment_sessions | 可退出的七维问卷与六项实验会话 | questionnaire、questionnaire/experiment score、objective/questionnaire/experiment/effective limit、status、information_status、assigned_variant、consent_basis、input/formula/experiment/rule version、started/completed/exited_at |
| BehaviorExperimentResponse / behavior_experiment_responses | 单项行为选择与一致性证据 | session_id、experiment_code、choice_code、response_time_ms、modification_count、consistency_score、response_payload、evidence、answered_at；会话 + 实验代码唯一 |
| BehaviorBiasFinding / behavior_bias_findings | 十一项确定性偏差发现 | session_id、bias_code、name、score、severity、explanation、evidence、source_experiment_codes；会话 + 偏差代码唯一 |
| BehaviorIntervention / behavior_interventions | 个性化干预与冷静期状态 | session_id、linked_goal_id、intervention_code、status、trigger_biases、scenario_code、personalized_message、action_instruction、cooling_period_hours、starts/eligible/completed/dismissed_at、assigned_variant、evidence |
| BehaviorExperimentAssignment / behavior_experiment_assignments | A/B 试验分配证据 | session_id、experiment_key、framework_version、variant_code、assignment_method/hash、data_scope、eligible_data、assigned_at；每会话唯一 |
| FinancialSnapshot / financial_snapshots | 某时点确定性分析快照 | snapshot_date、input_version、rule_version_id、calculation_source、structured_data |
| FinancialMetric / financial_metrics | 可追溯指标结果 | snapshot_id、metric_code、value（可空）、numerator、denominator、unit、status、is_applicable、formula_version、threshold_version、evidence |
| AccountBucketPlan / account_bucket_plans | 四账户瀑布阶段结果 | recommendation_id、bucket、sequence、current_amount、target_amount、allocated_amount、gap_amount、recommended_range_min/max、annual_cost_amount、coverage_gap_amount、三种 ratio、plan_version、input_version、calculation_source、constraint_evidence、rule_version_id |
| PortfolioPlan / portfolio_plans | 可复现组合候选 | recommendation_id、plan_name、candidate_type、denominator_name、strategic／tactical allocations、product_mappings、rebalancing、investment_amount、objective_score、goal_success_probability、scenario range、extreme loss、max drawdown、fees、liquidity、suitability_decision、solver method/status/seed/parameters、input/rule/optimizer version |
| SuitabilityCheck / suitability_checks | 候选三道闸门结果 | portfolio_plan_id、recommendation_id、gate、status、decision、check_version、input_version、reasons、evidence、rule_version_id |
| IntakeDraft / intake_drafts | 自然语言待确认草稿 | household_id（可空）、source_text_hash、redacted_preview、parser_version、status、extracted_fields、missing_fields、confirmed_values、contains_untrusted_instruction、confirmed_at；不保存原始文本，不直接改写家庭事实 |
| AgentOrchestrationRun / agent_orchestration_runs | 九智能体一次完整运行 | household_id、request_kind、status、current_state、query_hash、redacted_input、structured_output、numeric_ledger、citation_chunk_ids、blocked_issues、requires_human_review、degraded、orchestrator_version、started/completed_at |
| AgentStepRun / agent_step_runs | 单智能体步骤证据 | run_id、household_id、agent_code、sequence、status、input/output schema、tool_calls、structured_output、citations、prohibitions_checked、timeout_seconds、failure_code、degraded、started/completed_at；运行 + 智能体唯一 |
| DemoRun / demo_runs | 发布版十阶段主 Demo 账本 | household_id、story_version、status、current_stage、progress_percent、stages、artifacts、metrics、recovered_from_run_id、offline_mode、external_network_required、error_code/message、started/completed_at；失败记录只追加并由新运行恢复 |
| ExperimentSuiteRun / experiment_suite_runs | 七项发布实验账本 | suite_version、status、passed、恰好七项 cases、metrics、main_demo_run_id、started/completed_at；真实参与者项目以 protocol_ready／measured=false 保存 |

`FinancialMetric.value` 为 NULL 表示当前家庭条件下不适用或分母缺失，禁止伪造为 0。`AccountBucketPlan.denominator_name` 是必填字段，完整的家庭总资产、可投资金融资产和年度新增结余比例分别保存；长期增长 70% 的专用分母与条件保存在建议结构和约束证据中，不会被误解为家庭总资产统一比例。

## Stage 3 分析契约

计算顺序固定为：家庭基础情况 → 资产负债表 → 现金流量表 → 保险保障表 → 目标资金表 → 流动性矩阵 → 数据诊断／保障／购买力 → 20 项指标。每项指标 API 均包含 `metric_id`、中文名、公式、输入与来源记录、实际代入、结果、分子、分母、单位、阈值版本、状态、解释键、数据日、来源类型、适用性、参考条件、解释和行动。

用户原文“介于比率”按上下文解释为“结余比率”：年度税后结余 ÷ 年度税后总收入。该解释锁定在 `savings_ratio` 指标与 ADR-011 中，不另造含义不明的比率。

规则源 `data/rules/financial_health_v1.json` 的每个参考条件必须标注 `official_rule`、`industry_reference` 或 `internal_demo`。当前比赛阈值和离线购买力参数均明确标记为 `internal_demo`，不冒充监管统一标准或实时统计发布。完整公式、主 Demo 基准与边界行为见 `docs/financial_engine.md`。

## Stage 4 规划契约

Planning API 的每次响应包含生命周期识别与证据、目标未来金额／现值／缺口／月年投入、冲突和调整组合、可规划资源、七步瀑布、五硬一软、四账户当前／目标／建议／缺口、三尺、70% 条件、行动草案和版本元数据。

目标成本增速、Demo 折现率、安全月数修正、硬约束增长上限、行为修正系数和参考带全部来自 `data/rules/planning_waterfall_v1.json`，持久化为独立 RuleVersion。详细口径和资源守恒规则见 `docs/planning_engine.md`。

## Stage 5 组合与适当性契约

组合本金固定来自动态四账户确认的长期增长建议额。API 同时返回当前长期增长资产和应补回安全层金额，但两者不会重复加入组合本金。三个候选固定为 conservative／balanced／growth，每个都包含资产类别比例与金额、Mock 产品映射、情景区间、尾部损失、回撤、流动性、费率、适用条件、风险、三闸门、求解诊断和再平衡证据。

规则源 `data/rules/portfolio_policy_v1.json` 定义 5% 网格、多目标权重、候选上下界、R1—R5 高风险上限、单产品／单资产类别集中度、复杂度和 5pp／20%／6 个月再平衡。求解失败必须返回带原因的规则型降级。固定情景成功率不是 Monte Carlo 或收益承诺。

家庭安全闸门复用流动性、债务、保障、近期目标和真实长期金额；客户闸门对能力、意愿、知识、行为及已有结论取审慎下限；产品闸门逐项检查风险、期限、流动性、复杂度、最低金额、启用／专业条件和集中度。阻断可产生 reject、downgrade 或 education_only，不能被市场情景和客户主动要求绕过。

## Stage 6 数字孪生契约

孪生请求包含分析日、seed、路径数、期限、输出间隔、1—6 个场景代码、场景覆盖、计划调整、基础假设覆盖和家庭事件。金额以十进制字符串输入；每个请求生成参数哈希和输入版本。响应保存初始家庭状态、完整假设快照、无冲击基线、原方案压力、优化方案压力、逐场景标准回答、比较、限制和计数口径。

每个分布包含净资产 P10／P25／P50／P75／P90、流动／长期资产和负债中位数、全目标与逐目标成功率、失败时间分布、资金耗尽、被迫出售、最差 5 条路径和数值校验。共同随机数要求基线、原方案和优化方案使用相同 seed 与 path_id 随机流。目标支出只在到期月扣减一次；失业期主收入必须为零；正常退休提款不算紧急被迫出售。

`data/rules/twin_simulation_v1.json` 定义时间步长、收益、波动、相关矩阵、通胀、收入增长、数值边界和 19 个可组合场景，全部标记 `internal_demo`。完整公式、组合规则、标准答案和限制见 `docs/twin_engine.md`。

## Stage 7 行为金融契约

行为会话必须具备合成数据标识，或未撤回的 `behavior`／`risk` 授权；缺少客观 `RiskAssessment.capacity_score` 时不能开始。问卷固定七维，实验固定六项。每项响应保存选择、反应时间、修改次数、一致性和规则证据；完成前不创建偏差发现或干预，退出后也不生成新画像。

双画像响应包含客观能力、问卷自述、实验行为和最终配置上限四层，及强制冲突代码。最终配置上限是三者的审慎最低值；行为不能提高客观能力。十一项偏差逐项保存分数、级别和来源证据；十二类干预由规则选择，单次最多 6 项。冷静期保存开始／可操作时间，未到期完成返回冲突，不会暗中交易。

四组 A/B 分配保存可复现哈希、框架版本和数据范围。指标只聚合 `eligible_data=true` 的合成或明确授权测试会话，不代表收益或因果效果。规则源 `data/rules/behavior_finance_v1.json` 与独立 B 标准答案 `data/expected/demo_b_behavior_v1.json` 的完整口径见 `docs/behavior_engine.md`。

## Stage 8 可信 AI 契约

知识文档与切片由 `data/knowledge/controlled_knowledge_v1.json` 幂等导入。查询先筛类别、人群、地区、生效／失效日期和安全状态，再使用 0.55 关键词 + 0.35 离线向量 + 0.10 元数据评分。结果保存来源、日期、版本、段落和哈希；无命中固定返回信息不足。

自然语言录入只创建 IntakeDraft，提取金额仍为十进制字符串。用户确认值保存在 `confirmed_values`，未提供的房贷余额、利率、期限、支出、资产和保险保持缺失；月供不得推算贷款余额。正式家庭事实写入需要后续显式映射流程，本阶段不自动执行。

九智能体状态机固定按信息采集、财务报表、财务诊断、目标规划、行为金融、资产配置、政策知识、报告生成、合规审计运行。每一步使用独立 Pydantic 输入／输出 Schema、工具白名单、禁止事项、超时和失败回退。`numeric_ledger` 的每项保存 code、值、单位、确定性工具、来源路径和值哈希；政策引用保存 KnowledgeChunk ID。完整规则见 `docs/trusted_ai.md`。

## Stage 9 客户端体验契约

Stage 9 没有增加领域表或数据库迁移。`ClientExperienceResponse` 是按请求生成的只读视图，聚合 Household、ConsentRecord、确定性 `FinancialAnalysisResponse`、`PlanningResponse` 和受控 KnowledgeCitation；所有金融值仍以 Decimal 序列化字符串返回。

| 视图对象 | 核心字段 | 约束 |
| --- | --- | --- |
| ClientJourneyStep | code、label、status、reason、action、view | 固定 13 步；view 只能指向 11 个已实现任务之一 |
| ClientPrivacySummary | active／withdrawn count、consents、export/delete/review path、boundary_note | 授权包含记录版本；撤回后不可用于新计算 |
| ActionCalendarGroup | code、label、description、items | 固定五组；`next_12_months` 恰有 12 个确定性复盘项 |
| ActionCalendarItem | code、title、detail、why、constraint_or_formula、change_trigger、risk_and_assumptions、amount、due_date、priority、source_record_ids、calculation_source | 逐项说明家庭数据、原因、约束／公式、重算触发和风险假设；金额来自规划规则或为明确的 0 元复盘任务，不自动执行 |
| ClientReportPreview | report_version、knowledge_retrieval_version、chapter_count、chapters、citations、data_as_of | `chapter_count` 是 Literal 8，chapters 长度固定 8，目录名称和顺序由测试锁定 |
| ClientDeliveryState | report、workflow、actions、explanation | 只暴露 not generated／under review／client ready 三类可请求状态，不返回内部草稿 ID、意见或内容 |
| ClientDataExport | financial_analysis、planning、client_experience、package_version、exported_at | 完整可核验数据包；信用卡额度不进入资产 |

授权撤回请求必须携带 `expected_version` 与原因，更新 ConsentRecord 的 `withdrawn_at` 和版本，并写 `consent_withdrawn` AuditEvent；重复或陈旧提交返回 409。Stage 9 的通用家庭删除原先只执行乐观版本软删除；Stage 12 已增加正式隐私擦除流程，通用旧路径仅作兼容且也必须二次确认。

严格八章客户端预览是 Stage 9 的可读交付，不等于正式 `PlanReport`。Stage 10 新增独立方案审核版本链；Stage 11 的正式报告会关联生成时的审核版本，并在符合状态时把 AdvisorReview／CustomerConfirmation 的 `report_id` 指向新快照。正式报告与旧预览使用不同目录契约，只有正式报告采用最终指定八章。完整契约见 `docs/formal_reports.md`。

## Stage 10 三端审核契约

| 契约 | 关键字段 | 不变量 |
| --- | --- | --- |
| PlanWorkflowResponse | workflow_id、household_id、current、versions、state_order、next_actions、traceable | `state_order` 固定八状态；`next_actions` 同时按当前状态、提交标志和角色过滤 |
| PlanWorkflowVersionOut | version_number、cycle、prior_version_id、state、action、reason、actor、selected_candidate、recommendation/suitability snapshot、communication_draft、decisions、confirmation、versions、before/after hash、request_id、created_at | 每次动作新版本；`before_hash` 必须等于前版 `after_hash`；客户端只收到合规后裁剪的当前版本 |
| AdvisorDossier | household、members、premeeting_questions、financial_anomalies、goal_conflicts、3 candidates、risk_and_liquidity_notes、suggested_communication_draft、12 reminders、mock_bank | 金额与三候选来自确定性工具；沟通稿为可编辑 Mock 模板，不替代客户经理 |
| ComplianceEvidence | overall_decision、explanation、controls、three_gate_statuses、blocked/warning codes、prohibited_phrases、versions、hash_chain_verified | 固定十类控制；阻断不能审批，预警或高风险要求人工复核 |
| MockBankSnapshot | adapter_version、mock、official_connection、interfaces、reconciled totals、credit_limit_in_total_assets、source | 恰好 8 类；`mock=true`、`official_connection=false`、信用卡额度不进入资产 |
| ComplaintReplayResponse / WorkflowAuditPackage | requested_version、timeline／versions、audit_events、integrity_status、package_hash、request_id | 只读回放不改历史；审计导出本身也写事件 |

方案计算与推进需要未撤回且同时包含 `profile`、`finance`、`risk` 的授权。客户确认必须逐项提交 `risk_read`、`mock_understood`、`not_guaranteed`，并只保存签署姓名哈希和脱敏提示。`Active` 表示规划版本生效，不表示交易或法律电子签名。

## Stage 11 正式报告契约

| 契约 | 关键字段 | 不变量 |
| --- | --- | --- |
| FormalReportDocument | report／household／parent／workflow ID、sequence、status、8 chapters、appendices、citations、sourced claims、numeric ledger、versions、execution metrics、checks、trigger／reason、data date、hash、boundary | 一级目录名称和顺序严格固定；所有关键数字有确定性来源；所有政策事实有受控引用；结尾必须有适用边界 |
| ReportActionOut | action／group code、title、why、completion criteria、review cycle、amount、due date、status、completed/deferred/reason、record version、calculation source | 四种状态合计等于行动总数；延期必须有日期；写入使用乐观版本 |
| ReportGenerationChain | household、current report、items、chain verified、audit event count | sequence 连续，首项无父报告，后续 parent 指向前项；每项保留自身哈希和治理版本 |
| FormalReportSummary | report／parent／workflow ID、sequence、version、status、consistency、trigger、date、hash、watermark、HTML/PDF URL | 只读摘要不能代替完整结构化快照 |

## Stage 12 安全、隐私、模型风险与发布契约

| 契约 | 关键字段 | 不变量 |
| --- | --- | --- |
| SessionClaims | sub、role、household_ids、iat、exp、iss、aud、nonce | HMAC-SHA256 签名；过期、未来签发、篡改、超出最大时长均拒绝；production 不接受 Demo Header |
| ConsentScenario | code、required_scopes、sensitive、purpose、required_acknowledgement | 场景明示同意；identity/health/insurance 敏感范围必须独立记录和确认 |
| PrivacyExport / PrivacyDeletion | reason、确认动作、对象授权；删除另含 expected_version、household_code_confirmation | 原因只保存哈希；导出不复制载荷进审计；擦除去标识并逻辑删除业务记录，备份物理到期不作虚假承诺 |
| ModelRun ledger | information_extraction／explanation／rag／report、provider/model、prompt_hash、input field names、redacted summary、degraded/injection/human-review/fallback evidence | 四类任务分账；不保存 API Key、完整提示词或直接身份值；关键数字仍来自确定性工具 |
| Adversarial Evaluation | suite_version、environment、8 cases、metrics、started/completed_at | 固定八类用例不得 skip；所有指标标记 test／not_production_metric |
| QualityGate / Publish | gate_version、10 ordered gates、passed、evaluated_by_hash、report sequence、publication status/time | 任一门禁 block 则保持 draft；全 pass + 合规人工复核 + 专用二次确认 + 序号一致才可 published |

## 产品、情景、报告与治理

| 实体／表 | 作用 | 关键字段与关系 |
| --- | --- | --- |
| Product / products | 版本化 Mock 产品事实 | code、name、product_type、asset_class、risk_level、term_months、minimum_holding_months、liquidity_level、redemption_rules、annual_fee_rate、underlying_assets、historical_volatility_min/max、minimum_investment、suitable_accounts、principal_guaranteed、guarantee_basis、guarantee/non-guaranteed disclosure、complexity_level、catalog_version、professional_only、education_only、enabled、is_simulated、terms |
| PolicyDocument / policy_documents | 可追溯政策知识 | code、title、issuing_authority、category、document_version、publication/effective/expiry/last_verified date、source_uri、source_type、applicable_audiences、applicable_regions、content、content_hash、controlled_snapshot、metadata_json |
| KnowledgeChunk / knowledge_chunks | 受控检索切片 | document_id、code、page_ref、paragraph_ref、content、keywords、64 维 embedding、token_count、content_hash、security_status、security_evidence、metadata_json |
| ScenarioDefinition / scenario_definitions | 版本化可组合压力情景 | code、category、parameters、explanation、scenario_version、is_composable、source_type、enabled |
| SimulationRun / simulation_runs | 可恢复、可取消的可复现仿真运行 | scenario_id、snapshot_id、random_seed、engine_version、inputs、outputs、status、progress_percent、scenario_codes、path_count、horizon_months、time_step_months、input/formula/result/parameter version、rule_version_id、calculation_source、cancel_requested、started_at、completed_at、error_code |
| Recommendation / recommendations | 建议版本 | recommendation_type、status、summary、structured_advice、suitability_evidence、rule_version_id |
| ActionItem / action_items | 可执行行动 | recommendation_id、report_id、action_code、group_code、title、due_date、status、completed_at、deferred_until、status_reason、status_changed_at、owner_role、evidence；household + action_code 唯一 |
| PlanReport / plan_reports | 正式规划书不可变快照 | household_id、sequence、parent_report_id、workflow_id/version_id、report_version、chapter_count、structured_report、generated_at、consistency_status、trigger／reason、report_hash、input/formula/planning/portfolio/twin/model/prompt/knowledge/product version、watermark、is_current、publication_status、published_at、quality_gate_run_id；八章检查、household + sequence 唯一 |
| AdvisorReview / advisor_reviews | 顾问人工复核 | report_id、advisor_id、decision、comments、reviewed_at |
| CustomerConfirmation / customer_confirmations | 客户确认 | report_id、member_id、confirmation_type、confirmed_at、confirmation_version、evidence |
| PlanWorkflowVersion / plan_workflow_versions | 三端共享的不可变方案版本 | household_id、workflow_id、sequence、cycle、prior_version_id、state、action、reason、actor_id/role、selected_candidate、recommendation/suitability snapshot、communication_draft、advisor/compliance decision、customer_confirmation、submitted_for_compliance、requires_human_review、is_current、input/rule/model/prompt/knowledge/product version、before/after hash、request_id；workflow + sequence 唯一 |
| AuditEvent / audit_events | 不可抵赖操作证据 | event_type、actor_id、actor_role、entity_type、entity_id、event_version、summary、evidence、occurred_at |
| ModelRun / model_runs | 四类模型任务审计 | provider、model_name、task、prompt_hash、redacted_input（字段名／注入标记）、structured_output（摘要／人工复核／降级原因）、started_at、completed_at、degraded |
| QualityGateRun / quality_gate_runs | 报告发布前确定性门禁 | household_id、report_id、gate_version、environment、passed、10 项 gate_results、metrics、evaluated_by_hash、evaluated_at |
| EvaluationRun / evaluation_runs | 固定安全对抗评测 | suite_version、environment、passed、8 项 cases、测试 metrics、started_at、completed_at |
| RuleVersion / rule_versions | 确定性规则版本 | code、semantic_version、effective_from、effective_to、rules、source_summary |

## Stage 13 完整 Demo 与实验契约

| 契约 | 关键字段 | 不变量 |
| --- | --- | --- |
| DemoManifestResponse | release/story/dataset version、runtime/mock、ready、三家庭、最新运行、预热时间、TTL、release assets、boundaries | 外部网络依赖固定 false；ready 仅在 A／B／C 全部存在时为真 |
| DemoRunResponse | run/household/story、status、current stage、progress、stages、artifacts、metrics、recovered_from、offline、error、timestamps | 完整运行恰有 10 个完成阶段；关键结果保留输入／规则／模型／Prompt／知识／产品／审核版本；失败不覆盖历史 |
| FamilyComparisonResponse | 3 rows、analysis date、cache status、unique signatures、fixed_ratio_model、conclusion | 恰有 A／B／C；配置来自确定性财务／规划／组合工具；三个签名必须不同；fixed_ratio_model 固定 false |
| ExperimentSuiteResponse | 7 cases、passed、main Demo、metrics、environment、real_bank_results_claimed、boundary | 恰有七项；environment 固定 test；real_bank_results_claimed 固定 false；无参与者的理解度和顾问时间只能 protocol_ready |
| DemoPreheatResponse | warmed components、timings、cache expiry、external network calls | 只读取本地数据库、规则和知识；外部调用固定 0 |

`DemoRun.artifacts` 是按阶段保存的版本化证据索引，不是新的金融事实源。财务、规划、组合、孪生、行为、报告和九智能体结果仍来自各自确定性服务或受治理服务；Demo 编排器不复制一套计算公式。完整运行与发布口径见 `docs/demo_runbook.md` 和 `docs/performance_experiments.md`。

## 核心枚举

| 枚举 | API 值 | 中文口径 |
| --- | --- | --- |
| LifecycleStage | early_career / family_formation / parenting / mature_family / retirement_preparation / retirement_and_legacy | 初入职场／婚姻组建／育儿成长／家庭成熟／退休准备／养老传承 |
| AccountBucket | daily_liquidity / risk_protection / stable_goals / long_term_growth | 要花／保命／保本的钱／生钱 |
| AssetCategory | cash、demand_deposit、money_market、time_deposit、bank_wealth_management、bond、bond_fund、public_fund、equity_fund、stock、pension_account、insurance_cash_value、trust、primary_residence、investment_property、vehicle、other | 资产事实分类；股票只可表示已有持仓，不代表默认推荐 |
| LiabilityCategory | mortgage / auto_loan / consumer_loan / credit_card_unpaid / bank_loan / non_bank_loan / other | 房贷／车贷／消费贷／信用卡未付／银行借款／非银行借款／其他 |
| GoalType | emergency_fund / education / home / retirement / medical / travel / debt_repayment / family_support / wealth_transfer / other | 应急、教育、住房、养老、医疗等目标 |
| RiskLevel | low / medium_low / medium / medium_high / high | 风险等级 |
| ProductRiskLevel | r1 / r2 / r3 / r4 / r5 | 产品风险等级 |
| LiquidityLevel | immediate / within_7_days / within_30_days / within_1_year / illiquid | 即时、7 日内、30 日内、一年内、非流动 |
| PortfolioCandidateType | conservative / balanced / growth | 稳健／基准／进取三候选 |
| SuitabilityGateType | family_safety / customer / product | 家庭安全／客户／产品三道闸门 |
| SuitabilityStatus | pass / restrict / block | 通过／限制／阻断 |
| SuitabilityDecision | allow / downgrade / reject / education_only | 允许／降级／拒绝／仅教育展示 |
| MarketScenario | neutral / risk_off / risk_on | 中性／避险／风险偏好，仅控制最多 5pp 战术偏移 |
| SimulationStatus | queued / running / completed / cancelled / failed | 孪生运行等待／执行／完成／取消／失败状态 |
| BehaviorSessionStatus | active / completed / exited | 行为实验进行／完成／主动退出 |
| BehaviorInterventionStatus | active / completed / dismissed | 干预进行／完成／用户暂不采用 |
| IntakeDraftStatus | pending_confirmation / partially_confirmed / confirmed | 待逐项确认／部分确认／提取项全部确认；不等于已写入正式事实 |
| OrchestrationStatus | running / completed / degraded / blocked | 九智能体运行中／终检通过／降级完成／终检阻断 |
| AgentStepStatus | pending / running / completed / degraded / blocked | 单步等待／执行／完成／降级／阻断 |
| ComplexityLevel | basic / standard / complex / professional | 基础／标准／复杂／专业产品理解要求 |
| RecommendationStatus | draft / pending_review / approved / rejected / customer_confirmed / executed / expired | 建议生命周期 |
| ActorRole | client / advisor / compliance / admin | 客户／客户经理／合规审核员／管理员；`risk` 仅是旧请求输入别名 |
| PlanWorkflowState | draft / calculated / suitability_checked / advisor_reviewed / compliance_reviewed / customer_confirmed / active / superseded | 严格八状态主序列，不可跳步 |
| PlanWorkflowAction | create / calculate / suitability_check / advisor_review / revise_advice / edit_communication / submit_compliance / compliance_approve / compliance_return / require_human_review / customer_confirm / activate / supersede | 动作由状态与角色双重守卫；编辑也创建新版本 |
| AuditEventType | 既有授权／数据／计算／建议／适当性／孪生／行为／复核／可信 AI 事件，加 privacy_data_exported、privacy_data_erased、model_executed、quality_gate_evaluated、report_published、adversarial_evaluation_completed、file_inspection_recorded | 隐私、模型、评测、上传检查与发布动作也以去标识证据追踪 |

## 合成数据

权威文件为 `data/synthetic/families.json`，版本 `synthetic-families-v1.0.0`：

- A：24 岁初入职场者，期限长、无房贷、行为画像存在追涨和从众倾向。
- B：35／33 岁夫妻与 5 岁子女，双收入、育儿、赡养、房贷和房产集中，是主 Demo。
- C：55／53 岁退休准备家庭，金融资产较多、意愿高但风险能力受退休与医疗约束。

家庭 B 明细输入求和为：资产 2,850,000.00 元、负债 1,208,000.00 元、年收入 360,000.00 元、年支出 288,000.00 元。种子仍不保存净资产、比率或应急月数；Stage 3 引擎由相同明细计算出净资产 1,642,000.00 元及全部指标。独立标准答案仅位于 `data/expected` 的测试夹具，不被运行时读取。

## CRUD 契约

- 根资源：`/api/v1/households`。
- 嵌套资源：members、assets、liabilities、incomes、expenses、insurance-policies、goals、risk-assessments、consents。
- 列表参数：`page >= 1`，`1 <= page_size <= 100`；响应包含 total 和 pages。
- 更新体必须携带 `expected_version`；过期版本返回 `409 version_conflict`。
- 通用删除使用 `?expected_version=`，执行软删除并从普通查询隐藏；家庭旧删除路径还要求 `X-Confirm-Action: legacy_soft_delete_household`。正式隐私擦除使用专用 POST、家庭代码和版本三重确认。
- development／demo／test 可使用 `X-Actor-ID` 与 `X-Actor-Role` 演示 RBAC；production 强制关闭并使用签名 Bearer 短会话。角色错误返回 403，跨家庭对象读取统一返回 404。
- 所有跨成员／资产引用必须属于当前 household，防止跨家庭数据串联。
- 通用 API 新建 Household 默认 `is_synthetic=false`；只有种子导入显式标记为 true，因此 `reset-demo` 不会清理普通用户录入家庭。

完整关系图见 `docs/er_diagram.md`。
