# V5 买方产品本体、资格与候选排序

状态：E07 已实现。迁移：`0022_v5_product_ontology`。前置依赖：E06 CFS 与家庭风险预算。

## 目标与边界

E07 把产品放在“家庭需要 → CFS 行动 → 风险预算”之后。产品本体回答产品是什么，快照回答在某个日期从什么来源观察到什么，资格引擎回答它是否可进入当前客户的比较，买方排序回答合格候选之间的相对顺序。

`Portfolio`、`CFS` 和 `Product` 不是同一个对象。一个 CFS 组件映射为 0—N 个候选；现金保留、偿债、保障询价、专业服务和正式 `NO PRODUCT` 都是有效结果。

## 数据模型

迁移没有创建 `products_v2`，而是在既有 `products` 上增加发行人、法域、产品族／子类、全口径成本、渠道激励披露、利益冲突、专业复核、CFS 角色、分类版本和证据字段。`currency` 已由统一 `RecordMixin` 提供，因此没有重复列。

新表 `product_snapshots` 保存：

- 产品、快照日、销售状态、风险等级；
- 费用、流动性和条款快照；
- 渠道、来源引用和结构化证据；
- 确定性 `snapshot_hash` 与版本。

同一产品和快照哈希唯一。`0021 → 0022 → 0021` 往返不会删除 CFS 表；升级前的旧产品保留，并获得 `legacy-v1` 分类默认值。

## 分类与真实基金适配

`ProductFamily` 统一支持存款、银行理财、货币市场基金、债券基金、权益／指数基金、债券／国债、黄金、保险、个人养老金产品、信托／传承工具和现金管理十一类。

现有 `verified_real_funds_v1.json` 继续作为受控公开资料源，Fund Advisory 接口与服务没有删除或改写。Adapter 将目录中的 8 只基金幂等映射到既有 `products`，并按目录版本生成证据快照。工行官网公开列示统一标记为 `channel_verification_required`，不等同于当日可售。

## 资格引擎

输入覆盖 need、风险预算、账户包装器、目标期限、最大锁定期、客户资格、渠道和快照新鲜度。输出严格为：

- `eligible`
- `restricted`
- `blocked`
- `education_only`
- `professional_review`

硬阻断优先于排序；产品用途、账户、风险等级、风险预算开放状态、期限或流动性不匹配时不进入候选。快照过期后，即使产品事实仍可用于比较，也只能返回 `education_only`，`executable_recommendation_allowed` 必须为 `false`。

## 买方排序

排名按需要匹配、硬资格、流动性、风险、目标期限、全口径成本、分散度、发行人集中、操作简洁度和利益冲突依次计分。缺失费用会扣分并限制执行；已知利益冲突只会扣分。`distribution_incentive_disclosure` 从不产生正向分数，测试明确证明修改渠道激励不会改善分数或排名。

所有当前真实基金快照都只证明公开资料和渠道线索，未证明实时可售，也未补齐客户全口径费用，因此候选可以用于买方比较，但不会形成交易指令。

## API

- `GET /api/v1/products/search`
- `GET /api/v1/products/{product_id}`
- `POST /api/v1/products/eligibility-check`
- `POST /api/v1/products/rank`
- `GET /api/v1/households/{household_id}/cfs-solutions/{solution_id}/product-candidates`

全部受 `ENABLE_V5_PRODUCT_ONTOLOGY` 控制并要求已认证 Actor。开发默认关闭；隔离 Docker Demo 在迁移和验收通过后开启。

## 客户界面

`/wealth/cfs` 在风险预算之后增加产品决策区。每个组件显示为什么需要这类工具、候选产品、客户总成本、流动性、风险、没有选择其他候选的原因和利益冲突披露。界面没有购买按钮；费用缺失显示“待渠道补齐”；非产品行动明确显示 `NO PRODUCT`。

## 验收

- 8 只公开基金幂等接入，重复适配不复制产品或快照。
- `NO PRODUCT` 是结构化响应和可见界面状态，不以空白、零金额组合或占位产品替代。
- 目录过期时所有剩余候选为 `education_only`，不可执行。
- 渠道激励披露变化不会改善客户排名。
- CFS 组件覆盖 0 个和多个候选两种路径，方案与产品保持独立。
- Playwright 在 1440×1000 与 390×844 验收 `NO PRODUCT` 和 3 候选路径，控制台 0 error／0 warning。

截图：

- `output/playwright/e07-product-ontology-no-product-desktop.png`
- `output/playwright/e07-product-ontology-no-product-mobile.png`
- `output/playwright/e07-product-ontology-candidates-desktop.png`
- `output/playwright/e07-product-ontology-candidates-mobile.png`

E07 不包含 E08 Decision Evidence V2、顾问审批、客户交易确认、实时产品主数据或交易系统接入。
