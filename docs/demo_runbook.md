# Fortune Copilot 完整 Demo 运行手册

## 演示边界

本手册覆盖提示词 13 的比赛 Demo 与 E14 V5 发布回归。默认使用 A-H 八类 Canonical 合成 Persona、SQLite、版本化本地规则、受控知识和 Mock LLM；不需要 API Key、真实银行接口、行情服务或互联网。`/demo` 的旧主剧情仍以 B 为主家庭，并保留 A／B／C 三家庭对照。页面顶部和正式报告持续显示“竞赛原型”与 Mock／人工复核状态。

关键金额、比率、配置、概率、分位数和报告数字只由确定性工具生成。自然语言模块只创建待确认草稿；信用卡额度不计入资产；四账户不采用固定比例；长期增长的 70% 约束只可能作用于通过安全闸门的长期资金；普通家庭路径不默认提供个股、杠杆或股指期货操作。

## 一键启动

要求 Docker Desktop 与 Docker Compose。仓库根目录执行：

```bash
cp .env.example .env
docker compose up --build
```

等待 `backend` 健康后打开 <http://localhost:8080/demo>。首次启动自动执行 Alembic 迁移并在空库导入 A-H 八类合成 Persona。默认端口冲突时可以显式改映射：

```bash
BACKEND_PORT=18000 FRONTEND_PORT=18080 docker compose up --build
```

对应页面是 <http://localhost:18080/demo>。API 文档只在非 production 环境开放。

## 演示账号

顶栏账号选择器只模拟 RBAC，不是真实登录或法律电子签名。

| 账号 | 请求角色 | 主要用途 |
| --- | --- | --- |
| 客户 · 李先生 | client | 查看合规后版本、八章规划书、行动与隐私入口 |
| 客户经理 · 王顾问 | advisor | 查看面谈底稿、三候选、理由与版本链 |
| 合规审核员 · 陈审核 | compliance | 查看十类控制、模型／规则版本、门禁与审计 |
| 演示管理员 | admin | 加载、重置、预热、主 Demo 与实验套件 |

## 主剧情

在 `/demo` 点击“一键运行完整 Demo”，系统依次持久化以下十个阶段：

1. 加载 35 岁双收入育儿合成家庭 B；
2. 将自然语言解析为待确认草稿并逐项确认，不猜缺失事实；
3. 生成五张底表，识别房产集中、保障缺口和应急金不足；
4. 读取十年教育目标，按安全约束动态重配四账户；
5. 生成稳健／基准／进取候选并执行家庭、客户、产品三道闸门；
6. 用固定 seed 和共同随机数模拟一方失业 6 个月 + 权益下跌 30%；
7. 从六项选择证据识别损失厌恶并生成冷静期；
8. 建立顾问底稿、不可变工作流与合规证据，但不冒充人工审批；
9. 生成一级目录严格八章的正式规划书与行动清单；
10. 运行九智能体受治理终检并封存版本、引用与审计索引。

完成后可直接跳转客户端、顾问端和风险端读取同一份结果。每个阶段都有状态、耗时和审计事件；运行记录在进程重启后仍可读取。

## 三家庭对照

`/demo` 的 A／B／C 表读取三户各自的生命周期、资产负债、结余、应急覆盖、保障缺口和目标期限，再调用同一组确定性规划与组合规则。表格同时显示四账户金额和配置签名；验收要求三个签名均不相同且 `fixed_ratio_model=false`。它证明同一方法对不同家庭给出不同配置，不是固定四象限换名。

## V5 发布基准与创始人故事

管理员可通过两个带确认短语的接口运行 E14 回归。两者只重置 `is_synthetic=true` 的数据，production 环境禁用：

```bash
curl -X POST http://127.0.0.1:8000/api/v1/demo/v5/release-benchmark \
  -H 'X-Demo-Actor: admin' \
  -H 'X-Confirm-Action: run_v5_release_benchmark'

curl -X POST http://127.0.0.1:8000/api/v1/demo/v5/founder-story \
  -H 'X-Demo-Actor: admin' \
  -H 'X-Confirm-Action: run_founder_story'
```

发布基准要求 A-H 全部经过同一 Profile → Need → Liability／ELTC → Twin → CFS → Product／Specialized → Monitoring 管线，并逐项报告九个指标。创始人故事固定为 14 个有序阶段；融资事件改变企业估值和创始人持股后，系统必须生成新画像、需求、经济暴露、风险预算、孪生与 CFS 版本，保留“不新增权益风险”的安全结论，再进入人工审核、合规批准、客户确认和最终快照。

## 重置、加载、预热与恢复

- “加载合成数据”是幂等写入，A-H 已有家庭和稳定家企引用不会重复创建。
- “重置合成数据”携带专用确认头，只删除 `is_synthetic=true` 的家庭与演示派生记录；production 禁止执行。
- “本地预热”读取发布清单、三家庭计算、场景、行为规则和受控知识，并将对照结果放入 TTL 缓存；外部请求数固定为 0。
- 某阶段失败时，运行记录保存安全错误码和已完成阶段；“从失败记录安全重试”创建新运行并引用原运行，不覆盖失败证据。
- 浏览器无法连接后端时只显示诚实的离线说明，不伪造家庭数字。

命令行预热：

```bash
make warmup
# 非默认端口
API_URL=http://127.0.0.1:18000 make warmup
```

## 自动验收

服务启动后执行：

```bash
make acceptance
# 全新重建八类合成 Persona 后验收
python3 scripts/acceptance_check.py --reset-demo
```

非默认端口：

```bash
API_URL=http://127.0.0.1:18000 WEB_URL=http://127.0.0.1:18080 make acceptance
```

脚本只允许 localhost／回环地址，并检查健康、Mock 默认、A-H 种子、预热、主计算、信用卡边界、A／B／C 唯一配置、适当性拒绝、十阶段主 Demo、性能目标、数字孪生、严格八章报告、十项发布门禁、八项安全对抗、七项实验、V5 九指标基准、创始人 14 阶段故事和五个页面。输出是 JSON 证据账本，任何关键失败返回非零状态。

## 常见故障

| 现象 | 检查 | 恢复 |
| --- | --- | --- |
| 页面显示本地后端未就绪 | `docker compose ps`、`/api/v1/health` | 查看 backend 日志；修复后点击预热或重新运行 |
| 数据集不完整 | `/api/v1/demo/manifest` | 管理员加载 A-H；必要时显式重置合成数据 |
| 某阶段失败 | Demo 运行的 `error_code` 与最后阶段 | 保留失败记录，点击安全重试 |
| 报告门禁阻断 | 风险端十项门禁逐项原因 | 修复数据／引用／适当性后生成新报告，不修改旧快照 |
| 默认端口占用 | `docker compose ps` | 使用 `BACKEND_PORT`／`FRONTEND_PORT` 显式改映射 |

不要把 production 认证、真实客户、真实产品、实时政策、真实工行接口或真实实验结果作为故障恢复捷径；这些能力不在比赛 Mock 主链中。
