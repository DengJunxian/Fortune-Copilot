# 部署、迁移与合成数据恢复

## 发布构成

版本号的唯一人工发布标记是根目录 `VERSION`，当前为 0.14.0；Python、npm、前端静态能力清单、Compose 和 API 版本保持一致。`CHANGELOG.md` 记录变更，`LICENSE` 与 `THIRD_PARTY_NOTICES.md` 记录授权边界。

默认 Compose 只启动后端和前端：

- backend：Python 3.12、FastAPI、Alembic、SQLite 持久化卷、Mock LLM；
- frontend：Node 22 构建后的 Nginx 静态站点与同源 `/api` 代理；
- postgres：仅在显式 `postgres` profile 中启动，不是 Demo 前置条件。

## 环境变量

| 变量 | 默认／示例 | 说明 |
| --- | --- | --- |
| APP_ENV | development／Compose 为 demo | production 会启用更严格校验并禁用 Demo Header |
| APP_VERSION | 0.14.0 | API 与运行清单版本 |
| SYNTHETIC_DATA_PATH | `../data/synthetic/v5_personas/personas_v2.json` | A-H Canonical Persona V2 种子 |
| V5_PERSONA_GOLDEN_PATH | `../data/synthetic/v5_personas/golden_outcomes_v2.json` | 结构性 Golden Outcomes |
| V5_RELEASE_BENCHMARK_PATH | `../data/benchmarks/v5_release_v2.json` | 九项发布阈值与边界 |
| DATABASE_URL | SQLite 文件 | PostgreSQL 可选；不要把密码提交到仓库 |
| *_RULES_PATH | `data/rules/*.json` | 确定性规则源 |
| PRODUCT_CATALOG_PATH | Mock 产品目录 | 不是真实在售产品 |
| KNOWLEDGE_BASE_PATH | 本地受控知识 | 不自动联网更新 |
| DEMO_BENCHMARK_PATH | 发布实验协议 | 测试目标和问卷／计时协议 |
| DEMO_STORY_VERSION | wealthtwin-main-demo-v1.0.0 | 主剧情契约版本 |
| DEMO_CACHE_TTL_SECONDS | 300 | 三家庭对照缓存 TTL |
| DEMO_MAIN_PATH_COUNT | 100 | 主剧情 Monte Carlo 路径数 |
| LLM_PROVIDER | mock | 安全默认；外部模型不是主 Demo 前置条件 |
| LLM_API_KEY | 空 | 只允许从本地未提交环境注入；日志与仓库不得保存 |
| DEMO_AUTH_ENABLED | true（demo） | production 必须 false，并接入正式身份系统 |
| SESSION_SIGNING_KEY | 空（demo） | production 至少 32 个随机字符 |
| BACKEND_PORT / FRONTEND_PORT | 8000 / 8080 | 只改变宿主机端口映射 |

完整空值模板见 `.env.example`。

## 迁移与健康

容器启动命令先执行 `alembic upgrade head`，再用 `seed --if-empty` 幂等导入合成家庭，最后启动 Uvicorn。健康检查访问 `/api/v1/health`，同时核验数据库连接。手动检查：

```bash
docker compose ps
curl http://127.0.0.1:8000/api/v1/health
docker compose exec backend alembic current
docker compose exec backend alembic check
```

发布前在空库执行完整升级，不使用 ORM `create_all` 替代迁移。当前 head 为 `0027_v5_calibration_registry`。E14 不增加迁移。

## SQLite 合成数据备份

内置命令只允许 `development`／`demo`／`test`，只支持文件型 SQLite，并在写入前执行完整性、发布表结构、V5 A-H 完整集合和“无活动非合成家庭”检查。为恢复 0.13.0，工具仍接受完整的 V4 A-C 历史备份，但拒绝任意残缺集合。默认拒绝覆盖已有备份。

Compose 内执行：

```bash
docker compose exec backend python -m app.cli backup-demo \
  --output /data/backups/wealthtwin-demo-0.14.0.sqlite
```

同时生成 `.manifest.json`，包含 SHA-256、字节数、家庭代码、创建时间和 `synthetic_only=true`。开发环境可用：

```bash
make backup-demo OUTPUT=/absolute/path/wealthtwin-demo.sqlite
```

备份文件可能包含完整合成财务记录和审计链，仍应按内部测试数据控制访问；不要提交 Git。

## SQLite 恢复

恢复会替换当前 SQLite 文件，因此先停止后端写入。命令要求固定确认短语，并在替换前自动保存一个带 UTC 时间戳的 `pre-restore` 恢复副本。输入备份同样必须通过完整性、表结构、A-H（或完整历史 A-C）和 synthetic-only 校验。

```bash
docker compose stop backend
docker compose run --rm backend python -m app.cli restore-demo \
  --input /data/backups/wealthtwin-demo-0.14.0.sqlite \
  --confirm restore_synthetic_demo
docker compose up -d backend frontend
make acceptance
```

开发环境可用 `make restore-demo INPUT=/absolute/path/wealthtwin-demo.sqlite`。如果恢复后验收失败，停止后端并把命令返回的 `recovery_artifact` 作为输入恢复。不要在 production 或含真实家庭的数据库上使用演示恢复通道。

## PostgreSQL 计划

PostgreSQL 不走 SQLite 内置工具。授权部署应使用 TLS、独立最小权限账号、加密备份和机构密钥管理：

```bash
pg_dump --format=custom --no-owner --file=wealthtwin.dump "$DATABASE_URL"
pg_restore --clean --if-exists --no-owner --dbname="$DATABASE_URL" wealthtwin.dump
```

恢复前后均需核对 Alembic revision、合成 Persona 范围和 `scripts/acceptance_check.py`。生产备份的保留、删除、跨系统授权撤回和灾备演练尚未由本竞赛仓库实现，不得宣称完成。

## 发布门

```bash
make check
make security-audit
docker compose up -d --build
make warmup
make acceptance
PLAYWRIGHT_BASE_URL=http://127.0.0.1:8080 make test-e2e
```

验收脚本、浏览器和核心服务只访问本机。报告发布仍需人工复核、十项门禁全部通过和 `publish_report` 二次确认；主 Demo 只提交合规查看，不自动冒充审批、签署或交易。
