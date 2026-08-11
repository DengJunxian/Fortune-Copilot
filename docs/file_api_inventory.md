# Fortune Copilot 文件与 API 清单

核验版本：0.14.0
核验日：2026-08-11
OpenAPI：165 个路径、196 个 HTTP 操作（包含根路径）

## 核心文件清单

| 路径 | 用途 |
| --- | --- |
| `README.md` | 项目定位、截图、架构、账号、启动、演示、测试与免责声明 |
| `DESIGN.md` | 三端统一设计系统、组件和无障碍契约 |
| `VERSION` / `CHANGELOG.md` | 发布版本与变更记录 |
| `docker-compose.yml` | 默认 frontend + backend + SQLite/Mock；PostgreSQL 为显式 profile |
| `.env.example` | 无密钥默认配置和可选 Provider 环境变量 |
| `Makefile` | 安装、迁移、种子、测试、验收、备份与恢复入口 |
| `backend/app/main.py` | FastAPI 应用、安全中间件与 OpenAPI |
| `backend/app/api/v1/router.py` | 30 个端点模块的统一路由 |
| `backend/app/models/` | 80 张应用表的领域实体与持久化模型；加 `alembic_version` 共 81 张表 |
| `backend/app/schemas/` | API/Pydantic 输入输出契约 |
| `backend/app/services/financial/` | 五表、20 指标、保障、购买力与诊断 |
| `backend/app/services/planning/` | 生命周期、目标、七步瀑布、三尺与反事实 |
| `backend/app/services/portfolio/` | 三候选、产品映射、适当性闸门与再平衡 |
| `backend/app/services/twin/` | 逐月孪生、Monte Carlo、压力与运行管理 |
| `backend/app/services/behavior/` | 双画像、实验、偏差、干预与 A/B |
| `backend/app/services/trust/` | RAG、图谱、录入草稿、九智能体与治理终检 |
| `backend/app/services/review_workflow.py` | 八状态三端审核链 |
| `backend/app/services/reporting/` | 严格八章报告、数字账本、HTML/PDF 与重算 |
| `backend/app/services/security/` | 隐私、模型风险、对抗评测和发布门禁 |
| `backend/app/services/demo_release.py` | 十阶段主 Demo、对照、预热、恢复与实验 |
| `backend/app/services/financial_graph/`—`monitoring/` | V5 图谱、画像、责任/ELTC、持久孪生、家企、CFS、产品、专业方案与持续监控 |
| `backend/app/services/agents/` / `calibration/` | 受限工具型 Agent 与中国购买力校准注册表 |
| `backend/alembic/versions/` | `0001`—`0027` 连续数据库迁移链；V5 为 `0016`—`0027` |
| `backend/tests/` | 194 个后端 Pytest 用例（含参数化展开） |
| `frontend/src/pages/` | Public、Planning、Continuous Wealth、Advisor、Risk 全部路由页面 |
| `frontend/src/components/` | 三端业务、图表、工作流、报告和安全组件 |
| `frontend/src/styles/tokens.css` | DESIGN.md 的设计令牌实现 |
| `frontend/src/test/` | 65 个 Vitest／Testing Library 用例，V5 页面含 axe-core 检查 |
| `frontend/e2e/smoke.spec.ts` | 21 个 Playwright 场景，含 A-H、创始人链与 1440/1024/768/390 四档 V5 路由 |
| `data/synthetic/v5_personas/` | A-H Canonical Persona V2 与 Golden Outcomes V2 |
| `data/synthetic/families.json` | A/B/C 兼容对照事实 |
| `data/rules/` | 财务、规划、组合、孪生、行为规则 |
| `data/products/mock_products_v1.json` | 19 项 Mock 产品目录 |
| `data/knowledge/controlled_knowledge_v1.json` | 9 文档/16 切片受控知识 |
| `data/expected/` | 与运行时分离的五组标准答案 |
| `data/benchmarks/` | 可信 AI 与发布实验基准 |
| `scripts/acceptance_check.py` | 24 项本机黑盒验收 |
| `scripts/demo_warmup.py` | 本地预热 |
| `scripts/final_delivery_check.py` | 最终材料、红线和产物结构验收 |
| `scripts/build_final_materials.py` | 技术白皮书 DOCX 生成 |
| `scripts/build_competition_deck.mjs` | 比赛 PPTX 生成与逐页渲染 |
| `docs/technical_whitepaper.md` | 12 主题技术白皮书源文件 |
| `docs/demo_script_3min.md` | 0—180 秒逐句演示脚本 |
| `docs/defense_qa.md` | 15 个答辩高频问题 |
| `docs/icbc_business_value.md` | 工行业务价值、评价与落地边界 |
| `docs/final_acceptance_report.md` | 30 条理念矩阵与最终结论 |
| `docs/final_function_matrix.md` | 已实现/Mock/计划能力矩阵 |
| `docs/final_test_report.md` | 最终实测证据 |
| `docs/known_limitations.md` | 已知限制与安全边界 |
| `docs/demo_risk_plan.md` | 演示故障与降级预案 |
| `output/doc/wealthtwin_technical_whitepaper.docx` | 排版后的技术白皮书 |
| `output/presentations/wealthtwin_competition_deck.pptx` | 14 页、13 段叙事比赛演示稿 |

## API 分组统计

| 前缀 | 路径数 | 操作数 | 主要用途 |
| --- | ---: | ---: | --- |
| `/` | 1 | 1 | 根信息 |
| `/api/v1/health` | 3 | 3 | 健康、存活与就绪 |
| `/api/v1/meta` | 1 | 1 | 能力清单 |
| `/api/v1/households` | 103 | 134 | V4 家庭域与 V5 Graph → Monitoring 全链 |
| `/api/v1/demo` | 12 | 12 | 发布清单、种子、主运行、实验、A-H 基准与创始人故事 |
| `/api/v1/security` | 7 | 7 | 会话、上传、评测、模型台账和授权目录 |
| `/api/v1/trust` | 9 | 9 | 知识、图谱、录入、治理与 Agent 工具注册表 |
| `/api/v1/plan-workflows` | 5 | 5 | 三端状态动作、证据、投诉与审计 |
| `/api/v1/reports` | 5 | 5 | 报告读取、HTML/PDF、门禁与发布 |
| 其他 13 个目录 | 21 | 29 | 顾问、合规、行为、产品、决策证据、校准等目录 |

## 完整公开 API 路径

### 系统、目录与 Demo

- `GET /`
- `GET /api/v1/health`
- `GET /api/v1/meta/capabilities`
- `GET /api/v1/behavior/catalog`
- `GET /api/v1/behavior/ab-framework`
- `GET /api/v1/portfolio/products`
- `GET /api/v1/twin/scenarios`
- `GET /api/v1/trust/agents/catalog`
- `GET /api/v1/security/privacy/consent-catalog`
- `GET /api/v1/demo/manifest`
- `POST /api/v1/demo/load`
- `POST /api/v1/demo/reset`
- `POST /api/v1/demo/preheat`
- `GET /api/v1/demo/families/comparison`
- `POST /api/v1/demo/runs`
- `GET /api/v1/demo/runs/{run_id}`
- `POST /api/v1/demo/runs/{run_id}/retry`
- `POST /api/v1/demo/experiments/run`
- `GET /api/v1/demo/experiments/latest`
- `POST /api/v1/demo/v5/release-benchmark`
- `POST /api/v1/demo/v5/founder-story`

### 家庭根资源与九类嵌套资源

- `POST /api/v1/households`
- `GET /api/v1/households`
- `GET|PATCH|DELETE /api/v1/households/{household_id}`
- `POST|GET /api/v1/households/{household_id}/members`
- `GET|PATCH|DELETE /api/v1/households/{household_id}/members/{record_id}`
- `POST|GET /api/v1/households/{household_id}/assets`
- `GET|PATCH|DELETE /api/v1/households/{household_id}/assets/{record_id}`
- `POST|GET /api/v1/households/{household_id}/liabilities`
- `GET|PATCH|DELETE /api/v1/households/{household_id}/liabilities/{record_id}`
- `POST|GET /api/v1/households/{household_id}/incomes`
- `GET|PATCH|DELETE /api/v1/households/{household_id}/incomes/{record_id}`
- `POST|GET /api/v1/households/{household_id}/expenses`
- `GET|PATCH|DELETE /api/v1/households/{household_id}/expenses/{record_id}`
- `POST|GET /api/v1/households/{household_id}/insurance-policies`
- `GET|PATCH|DELETE /api/v1/households/{household_id}/insurance-policies/{record_id}`
- `POST|GET /api/v1/households/{household_id}/goals`
- `GET|PATCH|DELETE /api/v1/households/{household_id}/goals/{record_id}`
- `POST|GET /api/v1/households/{household_id}/risk-assessments`
- `GET|PATCH|DELETE /api/v1/households/{household_id}/risk-assessments/{record_id}`
- `POST|GET /api/v1/households/{household_id}/consents`
- `GET|PATCH|DELETE /api/v1/households/{household_id}/consents/{record_id}`

### 财务、规划、组合与孪生

- `GET /api/v1/households/{household_id}/financial-analysis`
- `GET /api/v1/households/{household_id}/financial-analysis/export`
- `POST /api/v1/households/{household_id}/financial-analysis/runs`
- `GET /api/v1/households/{household_id}/statements`
- `GET /api/v1/households/{household_id}/metrics`
- `GET /api/v1/households/{household_id}/diagnostics`
- `GET /api/v1/households/{household_id}/planning`
- `POST /api/v1/households/{household_id}/planning/counterfactual`
- `GET /api/v1/households/{household_id}/planning/export`
- `POST /api/v1/households/{household_id}/planning/runs`
- `GET /api/v1/households/{household_id}/portfolio`
- `POST /api/v1/households/{household_id}/portfolio/suitability-check`
- `GET /api/v1/households/{household_id}/portfolio/export`
- `POST /api/v1/households/{household_id}/portfolio/runs`
- `POST /api/v1/households/{household_id}/twin/runs`
- `GET /api/v1/households/{household_id}/twin/runs/{run_id}`
- `POST /api/v1/households/{household_id}/twin/runs/{run_id}/advance`
- `POST /api/v1/households/{household_id}/twin/runs/{run_id}/cancel`
- `GET /api/v1/households/{household_id}/twin/runs/{run_id}/export`

### V5 图谱、画像、责任、孪生与家企

- `GET /api/v1/households/{household_id}/financial-graph`
- `POST /api/v1/households/{household_id}/financial-graph/positions`
- `PATCH|DELETE /api/v1/households/{household_id}/financial-graph/positions/{position_id}`
- `GET /api/v1/households/{household_id}/client-profile`
- `POST /api/v1/households/{household_id}/client-profile/recalculate`
- `GET /api/v1/households/{household_id}/wealth-needs`
- `POST /api/v1/households/{household_id}/wealth-needs/recalculate`
- `GET /api/v1/households/{household_id}/liability-calendar`
- `POST /api/v1/households/{household_id}/liability-streams`
- `GET /api/v1/households/{household_id}/eligible-capital`
- `GET /api/v1/households/{household_id}/wealth-twin`
- `GET /api/v1/households/{household_id}/wealth-twin/snapshots/{snapshot_id}`
- `POST /api/v1/households/{household_id}/life-events`
- `GET /api/v1/households/{household_id}/event-timeline`
- `POST /api/v1/households/{household_id}/enterprises`
- `POST /api/v1/households/{household_id}/enterprise-exposures`
- `GET /api/v1/households/{household_id}/family-enterprise-view`

### V5 CFS、产品、证据、专业方案与持续服务

- `POST /api/v1/households/{household_id}/cfs-solutions`
- `GET /api/v1/households/{household_id}/cfs-solutions/{solution_id}`
- `POST /api/v1/households/{household_id}/cfs-solutions/{solution_id}/recalculate`
- `GET /api/v1/households/{household_id}/cfs-solutions/{solution_id}/product-candidates`
- `POST /api/v1/households/{household_id}/professional-referrals`
- `GET /api/v1/products/search`
- `GET /api/v1/products/{product_id}`
- `POST /api/v1/products/eligibility-check`
- `POST /api/v1/products/rank`
- `GET /api/v1/decisions/{decision_id}/evidence`
- `POST /api/v1/decisions/{decision_id}/replay`
- `GET /api/v1/households/{household_id}/retirement-plan`
- `GET /api/v1/households/{household_id}/currency-exposures`
- `GET /api/v1/households/{household_id}/trust-succession-needs`
- `GET /api/v1/households/{household_id}/philanthropy-goals`
- `GET /api/v1/households/{household_id}/monitoring/alerts`
- `POST /api/v1/households/{household_id}/monitoring/evaluate`
- `GET /api/v1/households/{household_id}/behavior-interventions`
- `GET /api/v1/households/{household_id}/next-best-actions`
- `GET /api/v1/advisor/action-center`
- `GET /api/v1/trust/agents/tool-registry`
- `POST /api/v1/households/{household_id}/bounded-agent-runs`
- `GET /api/v1/households/{household_id}/bounded-agent-runs/{run_id}`
- `GET /api/v1/calibration/catalog`
- `GET /api/v1/calibration/parameters/{parameter_code}`

### 行为金融与可信 AI

- `GET /api/v1/households/{household_id}/behavior`
- `GET /api/v1/households/{household_id}/behavior/export`
- `POST /api/v1/households/{household_id}/behavior/sessions`
- `GET /api/v1/households/{household_id}/behavior/sessions/{session_id}`
- `POST /api/v1/households/{household_id}/behavior/sessions/{session_id}/responses/{experiment_code}`
- `POST /api/v1/households/{household_id}/behavior/sessions/{session_id}/complete`
- `POST /api/v1/households/{household_id}/behavior/sessions/{session_id}/exit`
- `POST /api/v1/households/{household_id}/behavior/interventions/{intervention_id}/actions`
- `GET /api/v1/trust/knowledge/catalog`
- `POST /api/v1/trust/knowledge/search`
- `GET /api/v1/trust/graphs/shanghai-demo`
- `GET /api/v1/households/{household_id}/trust-graph`
- `POST /api/v1/trust/intake/drafts`
- `GET /api/v1/trust/intake/drafts/{draft_id}`
- `POST /api/v1/trust/intake/drafts/{draft_id}/confirm`
- `POST /api/v1/households/{household_id}/trust-orchestrations`
- `GET /api/v1/households/{household_id}/trust-orchestrations/latest`
- `GET /api/v1/households/{household_id}/trust-orchestrations/{run_id}`
- `POST /api/v1/trust/governance/validate`

### 客户、顾问、合规、报告与 Mock 银行

- `GET /api/v1/households/{household_id}/client-experience`
- `GET /api/v1/households/{household_id}/client-experience/export`
- `GET /api/v1/advisor/households`
- `GET /api/v1/compliance/review-queue`
- `GET /api/v1/households/{household_id}/advisor-dossier`
- `GET /api/v1/households/{household_id}/mock-bank-snapshot`
- `POST /api/v1/households/{household_id}/plan-workflows`
- `GET /api/v1/households/{household_id}/plan-workflows/current`
- `GET /api/v1/plan-workflows/{workflow_id}`
- `POST /api/v1/plan-workflows/{workflow_id}/actions`
- `GET /api/v1/plan-workflows/{workflow_id}/compliance-evidence`
- `POST /api/v1/plan-workflows/{workflow_id}/complaint-replays`
- `GET /api/v1/plan-workflows/{workflow_id}/audit-export`
- `POST /api/v1/households/{household_id}/reports`
- `GET /api/v1/households/{household_id}/reports/current`
- `POST /api/v1/households/{household_id}/reports/recalculate`
- `GET /api/v1/households/{household_id}/reports/generation-chain`
- `GET /api/v1/households/{household_id}/report-actions`
- `POST /api/v1/households/{household_id}/report-actions/{action_code}`
- `GET /api/v1/reports/{report_id}`
- `GET /api/v1/reports/{report_id}/html`
- `GET /api/v1/reports/{report_id}/pdf`
- `POST /api/v1/reports/{report_id}/quality-gate`
- `POST /api/v1/reports/{report_id}/publish`

### 安全与隐私

- `POST /api/v1/security/demo-sessions`
- `POST /api/v1/security/document-inspections`
- `GET /api/v1/security/model-runs`
- `POST /api/v1/security/evaluations/run`
- `GET /api/v1/security/dashboard`
- `POST /api/v1/households/{household_id}/privacy/exports`
- `POST /api/v1/households/{household_id}/privacy/consents/{consent_id}/withdraw`
- `POST /api/v1/households/{household_id}/privacy/deletion-requests`
- `POST /api/v1/households/{household_id}/privacy/human-review-requests`

## 复核命令

```bash
curl -fsS http://127.0.0.1:18001/api/v1/openapi.json > /tmp/wealthtwin-openapi.json
python3 -c 'import json; d=json.load(open("/tmp/wealthtwin-openapi.json")); print(len(d["paths"]))'
```

默认 Compose 可使用 `8000`；本轮隔离验收使用 `18001`。OpenAPI 是接口和 Schema 的权威机器可读清单；本文件用于比赛交付与人工导航。
