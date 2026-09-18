# Fortune Copilot 最终测试报告

测试版本：0.14.0
测试日：2026-08-11
运行环境：macOS，本机 Docker Compose，frontend `127.0.0.1:18081`，backend `127.0.0.1:18001`
模式：`runtime_mode=demo`，`mock_mode=true`，SQLite，外部网络调用 0

## 最终结论

代码质量、单元测试、生产构建、真实 Compose 浏览器回归、重置式黑盒验收、安全依赖审计、比赛材料结构、PPT 溢出和 DOCX 逐页渲染均已执行。核心主链未发现阻断项；唯一保留的构建提示是顾问／合规共享工作区包大于 500 kB，它不影响入口、`/demo` 或客户端的路由级懒加载，作为已知非阻断性能债务保留。

## 实测结果

| 检查 | 命令／方法 | 结果 | 关键证据 |
| --- | --- | --- | --- |
| Lint、类型、单元与构建 | `make check` | 通过 | Ruff、ESLint 0 告警；Mypy 256 个源文件；TypeScript 通过；Pytest 194/194；Vitest 65/65；Vite 构建 5,276 模块 |
| 真实浏览器回归 | Playwright CLI，真实 Compose | 通过 | 21/21；A-H 与创始人链、规划精细资产、11 个 V5 路由、1440/1024/768/390 四档宽度；控制台 0 error／0 warning |
| 重置式本机黑盒验收 | `python3 scripts/acceptance_check.py ... --reset-demo` | 通过 | 24/24，4,664 ms，外部网络调用 0；只删除并重建八类合成 Persona |
| V5 Release Benchmark V2 | `/api/v1/demo/v5/release-benchmark` | 通过 | A-H 8/8；九项指标全部达标，八项 1.0、无效告警率 0 |
| 创始人融资事件链 | `/api/v1/demo/v5/founder-story` | 通过 | 14/14 阶段；初始、融资与确认快照互异；人工审核链完整 |
| 十阶段主 Demo | 黑盒验收生成的最新持久化运行 | 通过 | 10/10 阶段；初诊 12 ms；100 路径 Monte Carlo 1,074 ms；八章报告 61 ms；完整链 1,388 ms |
| OpenAPI 与健康 | 最终交付校验器读取运行服务 | 通过 | 健康、数据库正常、Mock 为 true；165 个路径、196 个 HTTP 操作；五个页面均返回 200 |
| Python/npm 依赖安全 | `make security-audit` | 通过 | `pip-audit --local` 未发现已知漏洞；npm 生产依赖 0 漏洞；本地项目包不在 PyPI，按工具规则跳过 |
| 比赛 PPT 结构与溢出 | `slides_test.py` + PPTX 包检查 + 逐页目检 | 通过 | 14 页、14 份 `[Sources]` 讲者备注、13 段指定叙事顺序、结语原文一致；无画布溢出 |
| 技术白皮书 | DOCX → 临时 PDF → PNG 逐页复核 | 通过 | DOCX 包结构有效；18 页中文完整，无缺字、空白页、裁切和错误续号；12 个主题与结语原文一致 |
| 最终材料与理念红线 | `make final-acceptance` | 通过 | 23/23；21 个必需文件、提示词哈希、README、12 主题白皮书、六段脚本、15 问答、30 项矩阵、DOCX/PPTX、密钥扫描、健康、OpenAPI 与五页面全部通过 |

## 黑盒验收覆盖

24 项验收包括服务健康、Mock 默认、synthetic-only 重置、A-H 种子、本地预热、发布清单、V5 九指标基准、创始人 14 阶段事件链、A／B／C 唯一配置、主家庭、确定性主计算、恶意适当性请求拒绝、十阶段 Demo、性能目标、数字孪生、严格八章报告、十项发布门禁、八项固定安全对抗、七项发布实验，以及首页、Demo、客户、顾问和风险合规五个页面。

本次主 Demo 的配置来源仍为 `deterministic_tools`。家庭 B 的长期可配置金额为 0.00 元；应急、保障与近期目标未完成时，系统没有为了展示收益而强行生成长期增长配置。适当性对抗中的 100% 高风险、杠杆、集中和股指期货请求被三道闸门拒绝并返回审计事件。

## 浏览器与界面验证

Playwright 在真实 Compose 上串行执行 21 个场景，覆盖离线入口、键盘跳转、A-H 九指标发布基准、创始人 14 阶段故事、规划 → 精细资产 → 规划结果、11 个 V5 路由的 1440/1024/768/390 四档宽度、完整 Demo、三端不可变方案链、正式报告导出与重算、客户端 12 任务、移动端与 reduced-motion、财务 JSON、动态四账户、三候选与适当性拒绝、孪生运行／取消、行为双画像，以及受控知识、录入确认、图谱与九智能体。

比赛 PPT 的 14 张渲染图已逐页复核，修改后再次检查关键连接、状态标签、行为截图和消费者保护区域；自动溢出测试通过。技术白皮书使用本机可嵌入的中文字体生成 DOCX，经 LibreOffice 以显式字体目录渲染为 18 页临时 PDF，再逐页查看；临时 PDF 仅用于 QA，不作为对外交付物。

## 安全与边界检查

- 仓库凭证扫描不输出命中内容，只报告路径；真实密钥、私钥和非空 API Key 赋值命中为 0。
- `.env.example` 的 `LLM_API_KEY` 为空；默认 Mock Provider 无需密钥。
- 固定测试夹具使用明确的 `sk-test-...` 假值验证脱敏逻辑，不是可用凭证。
- 安全对抗结果为测试环境指标，不代表生产 SLA、真实客户效果或工商银行经营指标。
- 真实工行接口、生产 SSO、交易、法律签署、实时政策和真实实验仍按 `docs/final_function_matrix.md` 标注为 Mock 或计划。

## 可复现命令

```bash
make check
PLAYWRIGHT_BASE_URL=http://127.0.0.1:18081 npm --workspace frontend run test:e2e
python3 scripts/acceptance_check.py \
  --api-url http://127.0.0.1:18001 \
  --web-url http://127.0.0.1:18081 \
  --reset-demo
make security-audit
API_URL=http://127.0.0.1:18001 \
WEB_URL=http://127.0.0.1:18081 \
make final-acceptance
```

默认端口空闲时可省略 `API_URL`／`WEB_URL`；本报告使用隔离的 18001／18081 映射，没有终止或修改其他本机服务。若工作区 `.env` 选择外部 Provider，离线复核应在启动 Compose 时显式使用 `LLM_PROVIDER=mock`。

## 结果解释边界

所有时间均为本机竞赛环境单次实测，不是生产 SLA。理解度、顾问工时、AUM 留存、行为干预和消费者保护成效尚无真实参与者／员工／客户数据；相关能力只有经边界约束的实验协议、合成／授权测试记录和工程链路，不能外推为因果结论或工商银行实际效果。
