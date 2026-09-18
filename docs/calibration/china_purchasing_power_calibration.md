# V5 E13：中国购买力校准层

E13 把购买力计算中的关键参数从散落规则提升为可查询、可冻结、可降级的注册表。它不声称已经获得工商银行生产数据，也不把公开统计观察或仓库演示规则包装成银行结论。

注册表版本为 `china-purchasing-power-calibration-v1.0.0`，数据文件位于 `data/calibration/china_purchasing_power_v1.json`，数据库迁移为 `0027_v5_calibration_registry`。

## 三种模式

| 模式 | 含义 | 当前状态 | 使用边界 |
| --- | --- | --- | --- |
| `controlled_demo` | 仓库内版本化演示规则或已确认的演示输入 | 可用，但结果固定为 `degraded` | 不得表述为统计实证或银行授权 |
| `empirically_calibrated` | 已核验公开快照派生的观察参数 | 部分可用 | 必须保留样本期、口径、来源与限制；观察值不是预测 |
| `bank_authorized` | 经银行合同、客户授权、生产凭据和治理流程提供的参数 | 不可用 | 不允许回退到其他模式后改名为银行授权 |

`DatabaseCalibrationPort` 默认按 `bank_authorized → empirically_calibrated → controlled_demo` 排序，但返回值始终携带真实模式。调用方要求特定模式时只在该模式内解析；没有匹配记录即返回 `needs_review` 和空值。

## 数据集与质量结论

注册表当前有五个数据集、17 个参数，粒度为“参数代码 + 分群 + 地区 + 生效区间 + 参数版本”。

| 数据集 | 粒度／样本期 | 质量结论 | 风险与用途 |
| --- | --- | --- | --- |
| Fortune Copilot 演示购买力规则 | 全国、非抽样、2026-08-10 起 | 受控版本规则 | HCI 分类率、IAI 分层阈值和 GCI 未确认失败关闭值只能用于 Demo |
| 国家统计局 2026 年 1—4 月 CPI | 全国、四个月同比平均 | 已核验公开快照 | 只作 HCI 锚点，不替代家庭分类支出权重，也不预测未来 |
| 杭州最低工资 | 两个政策时点，2021-08 至 2024-01 | 已核验短序列 | CAGR 只进入 IAI；两点政策序列不代表逐年工资增速 |
| 南京最低工资 | 两个政策时点，2024-01 至 2026-01 | 已核验短序列 | 同上 |
| 广州最低工资 | 两个政策时点，2021-12 至 2025-03 | 已核验短序列 | 同上 |

没有把全国或地区“人均消费支出同比”当成 CPI。杭州 2018 年生活消费支出观察已经过时，南京／广州消费支出观察也不是价格指数，因此均未进入 HCI 参数。

注册表加载时自动检查：

- 数据集代码／来源版本和参数作用域／版本唯一；
- 参数值落在上下界内、置信度在 0—1、起止日期顺序有效；
- 查询时同时检查数据集生效日、参数生效区间、分群和地区；
- 数据库外键、复合唯一约束与幂等物化保持一对多完整性；
- 缺少参数时不生成默认估计，只返回 `missing_verified_parameter`。

## 参数追溯契约

每次解析都返回：

- `parameter_id` 与参数代码；
- 数值、上下界、分群、地区和有效期；
- `source`、`source_reference`、业务版本与数据集代码；
- 估计方法、置信度、限制、模式、状态与解析原因。

统一 `RecordMixin.version` 继续承担数据库行的乐观版本；`source_version` 和 `parameter_version` 分别记录数据集与参数的业务来源版本。这避免业务版本覆盖现有审计字段。

## HCI、GCI、IAI

### HCI

家庭成本通胀继续按家庭实际支出权重计算。分类支出率由 `HCI.expense_category_rate` 解析，当前属于 `controlled_demo`；`HCI.official_cpi_anchor` 来自国家统计局公开快照，只作为并列锚点。HCI 因混合使用经验锚点和演示分类率而显示 `degraded`。

### GCI

每条目标／责任流的 `annual_growth_assumption` 都生成独立参数引用，来源是对应 `stream_version`，不会套用全国 CPI。用户已确认的流仍标成 `controlled_demo`；未确认流为 `needs_review`。注册表中的 `GCI.unconfirmed_rate_fallback=0` 只表达失败关闭，不得用于正式预测。

### IAI

地区最低工资 CAGR 只进入 IAI 的收入追赶观察。`critical_below`、`watch_below` 和 `comfortable_at` 分层阈值已从规则常量提升为参数，但当前仍是 `controlled_demo`，因此 IAI 不会被描述为纯经验模型。

## 消费者与审计边界

- 购买力响应在总层和 HCI／每条 GCI／IAI 层分别返回模式、状态和参数引用。
- `/wealth/goals` 用独立徽标展示“受控演示”“经验校准”“银行授权”，并显示降级／待复核。
- 八章报告第四章增加校准模式表，附录 F 冻结数据集来源；含演示参数时一致性状态为 `needs_review`。
- Decision Evidence V2 冻结注册表版本、模式可用性、数据集版本和来源记录 ID；历史回放不读取最新参数替换旧证据。
- 缺少经过验证的参数时可以保留旧计算值用于兼容展示，但参数引用必须为空值或明确说明旧规则降级，前端与报告必须提示人工复核。

## API 与功能开关

- `GET /api/v1/calibration/catalog`
- `GET /api/v1/calibration/parameters/{code}?segment=...&region=...&effective_date=...&mode=...`
- `GET /api/v1/households/{id}/eligible-capital`

`ENABLE_V5_CALIBRATION` 在开发环境默认关闭，Docker Demo 开启。`CALIBRATION_REGISTRY_PATH` 指向只读注册表；生产环境接入银行参数前必须补齐授权、凭据、数据责任人与独立验证流程。
