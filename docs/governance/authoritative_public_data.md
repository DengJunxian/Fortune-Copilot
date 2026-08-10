# 权威公共数据管道

## 为什么不用运行时网页抓取

网页内容会变更，统计口径也可能被误读。若在每次规划时临时抓取，历史建议无法稳定重演。当前管道采用：

> 官方来源 → 人工口径复核 → 结构校验 → 不可变快照 → SHA-256 → 规则计算 → 决策证据

运行时只读取 `data/public/authoritative_public_snapshot_v1.json`，不会连接所谓“政府实时 API”。每个记录保存来源、观察日、生效日、入库日、版本、质量、是否实时、是否演示和 lineage；所有 URL 必须属于代码白名单中的政府或工商银行官方域名。

## 当前已核验数据

- 国家统计局：2026 年 1—4 月 CPI 同比平均涨幅 0.9%，作为 `official_cpi_trend` 观察信号。[来源](https://www.stats.gov.cn/english/PressRelease/202605/t20260512_1963677.html)
- 国家统计局：2025 年全国居民人均消费支出 29,476 元、名义同比增长 4.4%。该指标被明确标记为消费支出观察，不能当作 CPI。[来源](https://www.stats.gov.cn/sj/zxfb/202601/t20260119_1962321.html)
- 杭州：2021 年 8 月起 2,280 元，2024 年 1 月起 2,490 元。[2021 文件](https://zfgb.hangzhou.gov.cn/10/105220253/t116220253054/518325.shtml)、[2024 文件](https://zfgb.hangzhou.gov.cn/10/105220253/t117220253054/518480.shtml)
- 南京市区：2024 年一类地区 2,490 元，2026 年一类地区 2,660 元。[2024 文件](https://jshrss.jiangsu.gov.cn/art/2024/1/15/art_77279_11124963.html)、[2026 文件](https://www.jiangsu.gov.cn/art/2025/12/30/art_90848_11702519.html)
- 广州：2021 年 12 月起 2,300 元，2025 年 3 月起 2,500 元。[2021 文件](https://cms.gz.gov.cn/gzzcwjk/storage/material/2023/10/18/1c09052e32b1fee9342ddcbfe3526afb.pdf)、[2025 文件](https://www.gz.gov.cn/xw/tzgg/content/mpost_10134789.html)

地区生活成本管道另保存居民人均消费支出观察：南京 2024 年 44,578 元、名义增长 3.2%；广州 2025 年 49,177 元、名义增长 3.1%；杭州目前只有已核验但过时的 2018 年观察，因此标记 `historical_stale`，不会冒充当前生活成本。[南京来源](https://tjj.nanjing.gov.cn/njstjj/202504/t20250401_5108470.html)、[广州来源](https://tjj.gz.gov.cn/zzfwzq/tjkx/content/post_10804061.html)、[杭州历史来源](https://tjj.hangzhou.gov.cn/art/2019/3/4/art_1229279682_2571106.html)

杭州和广州序列覆盖约三年；南京当前公开快照只有两年，质量标记为 `verified_public_snapshot_short_series`。系统不会为了凑足 3—5 年而虚构数据。

## PPH 接入

PPH 仍为：

```text
max(official_cpi_trend,
    family_weighted_expense_inflation,
    regional_minimum_wage_cagr)
```

其中官方 CPI 和最低工资来自本快照，家庭支出加权变化来自已确认的家庭输入和版本化财务规则。最低工资组件固定 `is_cpi=false`；名义人均消费支出固定 `can_be_used_as_cpi=false`。规划元数据和 `DecisionEvidencePackage` 同时保存公共数据快照版本。

## 更新纪律

新数据不覆盖旧文件。维护者应创建新版本、保留旧快照、复核官方域名和统计口径、运行全量 invariant tests，再经规则治理批准切换配置。失效链接、地区映射不确定或序列不足时应降级并提示，不得自行补值。
