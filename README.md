# 智运财富 · 普慧金融

英文名：Fortune Copilot。

**Fortune Copilot 不是基金推荐器，而是面向中国家庭的财务健康规划系统。** 它以 CHFH 中国家庭财富健康理论为总框架，以 GRB（Goal、Risk、Behavior）动态账户模型为配置核心，在家庭生活、刚性责任、保障与近期目标得到安排后，才评估真正长期资金的购买力增长。

客户从家庭情况、客户识别和一张完整财务报表开始，查看资产负债、年度收支和六项家庭财务比率，再录入理财目标与大额支出，最后生成固定八章的理财规划书。

金额、比例、阈值、适当性、产品资格和规划书数字均由确定性程序计算。大语言模型只用于理解、追问和解释已验证结果，无权覆盖硬约束。所有关键结论携带方法论、规则、地区参数、市场状态、养老金政策、产品快照与评估版本，并生成可重演的决策哈希。

> 仓库已加入经官方公开网页核验的 CPI、杭州／南京／广州最低工资和监管政策只读快照；它们不是实时 API。工商银行 IAM、客户数据、AML/CDD、产品、交易、CRM 和内部投研系统仍只有 fail-closed Port/Adapter 契约，未接入、也不伪装接入。

## 产品流程

1. 填写个人／家庭基本情况、资金来源、投资经验与风险承受信息。
2. 录入资产、负债、年收入和年支出。
3. 查看美观的财务报表可视化和六项比率分析。
4. 填写理财目标、大额支出和已准备资金。
5. 生成、阅读、打印或导出八章理财规划书。

## 财务报表口径

### 资产

- 现金、活期存款与货币基金
- 定期存款与银行理财
- 非银行金融资产
- 自住房产
- 投资性房产
- 车辆及其他资产

### 负债

- 房产贷款、车贷和消费贷款余额
- 信用卡未付金额
- 非银行借／贷款与其他负债

信用卡额度不是资产，不进入资产合计。

### 年收入与年支出

- 收入：本人收入、配偶收入、资产生息、出租收入和其他收入。
- 支出：生活费、父母赡养、子女教养、保费、还贷和其他支出。

## 六项家庭财务比率

- 流动比率
- 负债比率
- 结余比率
- 财务负担率
- 投资与净资产比率
- 房产与资产比率

每项都显示计算方式、本次代入、常用参考范围、指标含义、家庭分析和下一步。参考范围是观察标尺，不是对所有家庭适用的统一合格线。

## 中国家庭动态四账户

- 要花的钱：按实际消费习惯准备数千元起的支付和结算资金，信用卡额度不计入资产。
- 保命的钱：保险以消费型保障为主，保障与投资分开。
- 保本的钱：服务应急、个人养老金和五年内目标；参考区间会随家庭目标、资金期限和市场环境调整，账户名称不代表所有产品保证本金。
- 生钱的钱：可规划金融净值达到客户选择的 30万—100万元启动线后进入正式评估；未达线但有正结余、无待处理高息债务、有多余长期资金且通过适当性条件时，可用不超过该多余资金 10% 的小仓位学习宽基指数基金。70% 只针对正式配置中完成前置安排后的长期可规划资源。

普通家庭不默认配置个股、杠杆、股指期货或新增投资性房产。最低工资涨幅只作长期购买力辅助观察，不等同于 CPI。

## CHFH、GRB、CHFI 与 HFDT

- CHFH 将决策主体从单个投资者扩展为家庭，联合观察资产、负债、现金流、保障、制度账户、目标、风险和行为。
- GRB 用目标期限与刚性、风险承担能力与意愿、真实行为反馈共同决定四账户，不只读取一次风险问卷。
- CHFI 以十个维度做家庭财务健康诊断，采用可用维度归一化后的几何平均，强项不能抵消现金流、偿债或保障短板。它不是征信评分。
- HFDT 家庭金融数字孪生使用可复现压力情景检验失业、医疗支出、市场下跌和家庭责任变化下的财务韧性，不预测市场涨跌。

系统形成 `CHFH → GRB → 动态四账户 → CHFI → HFDT → 产品适当性 → 持续复盘` 的单一主线。RRI-G 的责任、韧性和制度覆盖能力保留为内部约束组件，不再作为对外独立方法论品牌。

市场口径来自统一规则，不由客户或大语言模型临时判断。当前演示规则为中性：参考区间 10%—20%，中间参考点 15%。

V4 的完整定义与边界见：

- [`中国家庭财富框架`](docs/methodology/china_household_wealth_framework.md)
- [`Deep Research 报告吸收与原则校准`](docs/methodology/deep_research_alignment.md)
- [`四域责任瀑布`](docs/methodology/four_domain_responsibility_waterfall.md)
- [`中国家庭购买力门槛 PPH`](docs/methodology/purchasing_power_hurdle.md)
- [`Fortune Copilot V4 架构`](docs/architecture/fortune_copilot_v4.md)
- [`决策证据治理`](docs/governance/decision_evidence.md)
- [`Personal Pension Copilot`](docs/product/personal_pension.md)
- [`工行生产集成端口与边界`](docs/integrations/icbc_production_ports.md)
- [`权威公共数据管道`](docs/governance/authoritative_public_data.md)
- [`模型生命周期与监控`](docs/governance/model_lifecycle_monitoring.md)
- [`生产就绪、SRE 与灾备`](docs/operations/production_readiness.md)

## 规划书结构

一级目录严格保持八章：

1. 家庭基础情况
2. 理财目标
3. 大额支出计划
4. 理财假设
5. 家庭财务报表
6. 家庭财务比率分析
7. 投资规划建议
8. 免责声明

第 7 章先安排应急储备、偿债、保障、近期目标和长期资金，再按已经确定的金额说明具体基金。客户先看到资金用途、金额和风险，需要时再展开产品资料来源。购买前仍应以工行手机银行当日产品页面和风险测评结果为准。详细规则见 [`docs/fund_advisory.md`](docs/fund_advisory.md)。

## 三类客户案例

首页可直接进入三类已准备客户的完整规划流程：

- 单身职场新人：关注现金储备、结余能力和购房目标。
- 双收入三口之家：关注偿债压力、教育准备和资产集中。
- 临近退休夫妻：关注流动性、退休现金流和医疗安排。

## 技术架构

```mermaid
flowchart LR
    WEB["React + TypeScript"] --> API["FastAPI"]
    API --> LEDGER["家庭事实与责任账本"]
    LEDGER --> METHOD["CHFH + GRB 方法论与版本快照"]
    METHOD --> FIN["确定性规划、组合与压力测试"]
    API --> LLM["可降级的金融解释层"]
    FIN --> EVIDENCE["Decision Evidence Package"]
    FIN --> DB["SQLite／PostgreSQL"]
    FIN --> REPORT["八章 HTML／PDF 规划书"]
```

- 前端：React 19、TypeScript、Vite、ECharts、Phosphor Icons。
- 后端：FastAPI、Pydantic、SQLAlchemy 2、Alembic。
- 计算：Decimal 金额、PFNW、三分母、地区化启动线、PPH 与版本化规则快照。
- 模型：DeepSeek 的 OpenAI 兼容接口，JSON 输出通过应用自有 Pydantic 模型再次校验。
- 测试：Pytest、Vitest、Testing Library 与 Playwright。

详细产品架构见 [`docs/product/frontend_architecture_v2.md`](docs/product/frontend_architecture_v2.md)，视觉与组件契约见 [`DESIGN.md`](DESIGN.md)，本轮前端审计见 [`docs/design/wealth_planning_product_audit.md`](docs/design/wealth_planning_product_audit.md)。

## 快速启动

需要 Docker Desktop 与 Docker Compose。

```bash
cp .env.example .env
docker compose up --build
```

默认访问：

- 产品首页：http://localhost:18080
- 开始规划：http://localhost:18080/planning
- API 文档：http://localhost:18000/docs
- 健康检查：http://localhost:18000/api/v1/health

### 连接 DeepSeek

在本地 `.env` 配置：

```dotenv
LLM_PROVIDER=deepseek
LLM_API_KEY=填写本地密钥
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-v4-flash
```

密钥不应写入代码、`.env.example` 或版本库。Docker Compose 会把上述本地变量传入后端。未配置密钥时，金额和比率仍由确定性程序完整计算，解释使用本地模板。

## 本地开发

需要 Python 3.12 与 Node.js 22。

```bash
make setup
make migrate
make seed
```

分别启动两个终端：

```bash
make backend-dev
make frontend-dev
```

## 质量检查

```bash
make check
```

该命令依次执行后端与前端静态检查、类型检查、全量测试和前端生产构建。

## 主要 API

- `POST /api/v1/wealth-planning/cases`：创建客户基本情况与家庭财务报表，返回确定性分析。
- `POST /api/v1/households/{household_id}/ratio-explanations`：对已验证六项比率生成结构化解释。
- `POST /api/v1/households/{household_id}/plan-narrative`：返回确定性四账户结果与八章规划书讲解。
- `POST /api/v1/households/{household_id}/goals`：保存理财目标。
- `POST /api/v1/households/{household_id}/reports`：生成严格八章正式规划书。
- `GET /api/v1/fund-advisory/products`：读取已核验的公开基金资料。
- `GET /api/v1/households/{household_id}/fund-advisory`：生成第七章的具体产品说明。
- `GET /api/v1/public-data/authoritative-snapshot`：读取带官方来源、版本和完整性哈希的公共数据快照。
- `GET /api/v1/integrations/readiness`：查看银行专有能力、审批和运维证据缺口。
- `GET /api/v1/health/live`、`GET /api/v1/health/ready`：存活与环境感知的就绪探针。
- `POST /api/v1/security/model-governance/evaluate`：对汇总漂移、公平性、可用性与独立验证状态执行确定性门禁。

## 产品边界

- 不把银行理财、信托、基金或保险统一描述为保本产品。
- 不把最低工资变化等同于 CPI。
- 不把某一账户内的比例解释为家庭总资产固定配置。
- 不向普通家庭默认推荐个股、杠杆或股指期货。
- 真实基金建议仍须在执行当日完成工行风险测评、适当性判断、最新产品资料、费率、限购／暂停和账户可售状态复核；官网公开列示不是实时可买保证。
