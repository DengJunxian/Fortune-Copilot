# 客户经理、合规与客户三端闭环

版本：Stage 10 审核流 + Stage 11 正式报告关联 + Stage 12 权限加固 / 2026-08-05  
引擎：`plan-review-workflow-v1.0.0`  
迁移：`0009_review_workflow`、`0010_formal_reports`、`0011_report_uniqueness`、`0012_security_privacy_quality`

## 设计结论

顾问端、风险合规端和客户端读取同一个 `workflow_id` 的不可变版本链。语言模型只提供可编辑的 Mock 沟通模板；家庭金额、比率、三候选、风险与流动性指标均由既有确定性财务、规划和组合工具重新计算。方案状态 `Active` 只表示该规划版本进入复盘基线，不代表真实签约、下单、调仓或银行交易。

Stage 10 建立规划建议审核闭环；Stage 11 已在这条版本链之上生成正式八章 `PlanReport` 快照。每份报告关联生成时的 `workflow_id` 和 `workflow_version_id`，不能增加或减少一级章节，也不会因审核流后续推进而改写旧报告。

## 四角色与最小权限

角色只接受 `client`、`advisor`、`compliance`、`admin`；旧演示流量中的 `risk` 只作为输入别名映射为 `compliance`，新审计记录永远写规范角色。production 使用带家庭授权范围和过期时间的签名 Bearer 短会话；`X-Actor-ID`／`X-Actor-Role` 只在 development／demo／test 开启。未知角色返回 403，跨家庭对象读取返回 404。

| 能力 | client | advisor | compliance | admin |
| --- | :---: | :---: | :---: | :---: |
| 查看合规通过后的当前客户版本 | 是 | 是 | 是 | 是 |
| 查看完整版本链、内部理由与请求 ID | 否 | 是 | 是 | 是 |
| 客户队列、面谈底稿、8 类 Mock 接口 | 否 | 是 | 否 | 是 |
| 创建、计算、适当性检查、编辑、提交 | 否 | 是 | 否 | 是 |
| 合规队列、控制证据、通过／退回／人工复核 | 否 | 否 | 是 | 是 |
| 客户逐项确认与脱敏演示签署 | 是 | 否 | 否 | 是 |
| 激活或废止已确认规划 | 否 | 是 | 否 | 是 |
| 投诉回放与内部审计包 | 否 | 否 | 是 | 是 |

客户端在 `ComplianceReviewed` 之前读取当前方案会得到 `workflow_not_ready_for_client`。通过后只返回当前客户可见版本：内部操作者、请求 ID、顾问修改字段和完整历史被裁去；客户姓名只保存 SHA-256 与首字脱敏提示，不保存明文，也不冒充法律电子签名。当前三套家庭都是可切换的合成 Demo；签名会话是可验证应用边界，不替代生产 SSO、MFA、机构职责分离或在线撤销。

正式报告延续同一边界：合规前 `workflow_linked` 快照对客户返回 `report_not_ready_for_client`；合规通过后新生成的 `client_ready` 报告由客户和顾问读取同一结构化快照。无审核流时，客户可生成带“待人工复核”水印的竞赛草稿。顾问复核和客户确认记录在符合状态时关联报告 ID；关联只补足引用关系，不覆盖审核证据。

## 不可跳步状态机

唯一主序列严格为：

```text
Draft → Calculated → SuitabilityChecked → AdvisorReviewed → ComplianceReviewed
      → CustomerConfirmed → Active → Superseded
```

API 值为 `draft`、`calculated`、`suitability_checked`、`advisor_reviewed`、`compliance_reviewed`、`customer_confirmed`、`active`、`superseded`。数据库检查约束和 ORM 都持久化这些小写值。

| 当前状态 | 允许动作 | 执行角色 | 结果 |
| --- | --- | --- | --- |
| 无 | `create` | advisor / admin | Draft |
| Draft | `calculate` | advisor / admin | Calculated |
| Calculated | `suitability_check` | advisor / admin | SuitabilityChecked |
| SuitabilityChecked | `advisor_review` | advisor / admin | AdvisorReviewed |
| AdvisorReviewed | `revise_advice`、`edit_communication` | advisor / admin | 保持 AdvisorReviewed，新版本 |
| AdvisorReviewed | `submit_compliance` | advisor / admin | 保持 AdvisorReviewed，标记已提交，新版本 |
| 已提交的 AdvisorReviewed | `compliance_approve` | compliance / admin | ComplianceReviewed |
| 已提交的 AdvisorReviewed | `compliance_return` | compliance / admin | 新修订周期的 Draft |
| 已提交的 AdvisorReviewed | `require_human_review` | compliance / admin | 保持 AdvisorReviewed，新版本 |
| ComplianceReviewed | `customer_confirm` | client / admin | CustomerConfirmed |
| CustomerConfirmed | `activate` | advisor / admin | Active |
| Active | `supersede` | advisor / admin | Superseded |

每个动作必须提交当前 `expected_version` 和非空理由。越权返回 403；跳步、旧版本、缺少授权、未提交先审批、未完成必要人工复核或命中阻断规则返回 409。合规退回会增加 `cycle`、清空所选建议和审批结果，并要求从确定性计算重新开始，不能沿用旧金额悄悄越过闸门。

同一家庭同时只允许一个未废止的审核流；重复建案返回 `workflow_already_open`。Active 方案必须先进入 Superseded，才能为新一轮家庭事实创建新的 workflow，避免客户端“当前版本”在并行草稿间漂移。

所有编辑都插入新的 `PlanWorkflowVersion`，旧行不覆盖。相邻版本满足 `current.before_hash == previous.after_hash`；`after_hash` 对工作流、家庭、序号、周期、前版、状态、动作、理由、角色、快照、治理版本、前哈希与请求 ID 的规范 JSON 做 SHA-256。

## 顾问端

`/advisor` 的主工作区按以下任务顺序组织：

1. 客户队列展示生命周期、地区、净资产、年度结余、异常、目标冲突、方案版本和确认状态；金额由当前家庭事实实时计算。
2. 面谈前底稿列出授权／数据日核对、财务异常和目标冲突问题。
3. 稳健／基准／进取用同一矩阵比较；不拆成营销卡片，不把假设收益表达为承诺。
4. 产品类型适配理由、主要风险、流动性、压力损失、回撤与费用均来自确定性组合结果和当前 Mock 产品目录。
5. 沟通稿是可编辑 Mock 模板；保存、顾问人工复核和提交合规是不同动作。存在 R4／R5 类型时必须明确完成人工核对。
6. 修改理由、时间、操作者、角色、版本和哈希进入版本账本；AI 不代替客户经理作出建议决定。
7. 客户确认后由顾问激活；页面提供未来 12 个月复盘与再平衡提醒，但绝不自动交易。

## 风险合规端

`/risk` 的主工作区提供待审队列和十类控制：

| 控制类别 | 核验内容 |
| --- | --- |
| family_suitability | 应急、债务、保障和近期目标等家庭安全条件 |
| customer_suitability | 能力、意愿、知识、行为审慎上限与人工核对 |
| product_suitability | 风险、期限、流动性、复杂度与产品类型适配 |
| prohibited_wording | 保本、保证收益、稳赚、零风险等禁止性表述 |
| numeric_consistency | 沟通稿数字只能引用当前确定性数字账本 |
| source_integrity | 政策和事实必须有受控来源，不得补造来源 |
| model_governance | 模型输出、Prompt 注入和反幻觉状态 |
| authorization | `profile`、`finance`、`risk` 有效授权 |
| version_integrity | 前后哈希、当前版本和请求链完整性 |
| anomalous_recommendation | 异常配置、较高风险类型和人工复核要求 |

证据同时展示方案、规则、模型、Prompt、知识、产品目录和输入版本。合规可通过、退回或要求人工复核；存在硬阻断时不能通过，存在预警或人工要求时必须勾选完成人工复核。家庭安全闸门不通过时，候选只能是 `education_only`；合规可在确认该边界后让“规划版本”进入客户阅读，但这不改变产品不可执行结论，也不授权交易。

投诉回放按指定 `version_id` 重建当时的版本时间线、控制证据和哈希完整性，不修改历史。审计导出返回完整 JSON 包并写入新的“已导出”审计事件。

## 八类 Mock 银行接口

项目自有 `mock-bank-adapter-v1.0.0` 从现有合成家庭事实投影出恰好八类接口：

1. `accounts`：现金、活期、货币类和定期；
2. `credit_cards`：未偿余额与合成备用授信信息；
3. `mortgages`：合成房贷余额、月供、利率和到期日；
4. `wealth_management`：银行理财与信托事实；
5. `funds`：基金、债券与已有证券持仓事实；
6. `insurance`：保额、保费、现金价值、保证与非保证利益分列；
7. `personal_pension`：个人养老金资产和不重复入账的社保账户信息；
8. `cash_flow`：原始频率的合成收入与支出。

快照固定返回 `mock=true`、`official_connection=false` 和 `credit_limit_in_total_assets=false`。信用卡额度是 `information_only`，未偿余额是负债；理财、信托、基金和保险按各自条款显示，不被统一标为保本。界面不使用真实银行 Logo、官方配色仿制或生产接入声明。

## 审计字段

每次版本动作的 `AuditEvent.evidence` 至少包含：

- actor、role、time、action；
- object（workflow、version、state）；
- before_hash、after_hash；
- reason；
- rule_version、model_version、prompt_version、knowledge_version、product_catalog_version；
- request_id。

Mock 接口读取、合规决定、客户确认、投诉回放和审计包导出也各自写事件。授权撤回后，除合规退回和废止外的后续推进都会被阻断。

## API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/v1/advisor/households` | 顾问客户队列 |
| GET | `/api/v1/households/{id}/advisor-dossier` | 面谈底稿、三方案与 12 月复盘 |
| GET | `/api/v1/households/{id}/mock-bank-snapshot` | 八类合成 Mock 接口快照 |
| POST | `/api/v1/households/{id}/plan-workflows` | 创建 Draft V1 |
| GET | `/api/v1/households/{id}/plan-workflows/current` | 读取家庭最新方案；客户仅见合规后裁剪版本 |
| GET | `/api/v1/plan-workflows/{workflow_id}` | 读取指定工作流 |
| POST | `/api/v1/plan-workflows/{workflow_id}/actions` | 按状态、角色和版本执行动作 |
| GET | `/api/v1/compliance/review-queue` | 合规待审与历史当前状态队列 |
| GET | `/api/v1/plan-workflows/{workflow_id}/compliance-evidence` | 十类控制与治理版本 |
| POST | `/api/v1/plan-workflows/{workflow_id}/complaint-replays` | 按版本投诉回放 |
| GET | `/api/v1/plan-workflows/{workflow_id}/audit-export` | 导出版本与审计包 |
| POST／GET | `/api/v1/households/{id}/reports`、`/reports/current` | 生成／读取关联正式报告 |
| GET | `/api/v1/households/{id}/reports/generation-chain` | 顾问／合规读取报告父子哈希链 |

## 验收覆盖

- Pytest 覆盖客户越权建案、合规越权计算、客户端内部草稿不可见、状态跳步、完整三端闭环、每次编辑新版本、授权撤回、禁止性话术阻断、投诉回放、审计导出、八类 Mock 接口、信用卡额度边界和旧角色别名规范化。
- Vitest 覆盖顾问队列、三方案、八状态、模拟账号切换、请求角色、合规解释、投诉回放，以及客户只能看到合规后版本并逐项确认。
- Playwright 在真实 Compose 中完成九个不可变方案版本、正式报告 R1 → R2、12 月提醒、十类控制、客户脱敏演示签署、投诉回放、报告 PDF 和审计下载，并继续回归离线模式与既有客户端主流程。
- 空 SQLite 已验证升级到 `0011`、降级到 `0009`、再次升级到 `0011`；迁移库上的方案 Draft 与正式报告 R1 均由真实 Compose 链路覆盖。

## 明确限制

- 头部模拟账号不是生产认证；真实 SSO、会话、客户归属、机构层级、职责分离审批和细粒度行级授权留待安全发布阶段。
- Mock 适配层没有调用外部网络，也没有真实银行余额、产品在售、交易、签约、短信或电子签章能力。
- 演示签署不是法律电子签名；`Active` 不是下单状态。任何真实产品办理仍需适当性、双录、合同、销售与银行生产流程。
