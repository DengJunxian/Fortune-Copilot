# 部署、迁移与合成数据恢复

Sites 前端加 Render Python 后端的私有完整演示方案见 [V6 完整演示托管](hosting_sites_render.md)。该方案与下述本地 Compose 部署并存；未完成远端联调前，不应把静态页面视为完整上线。

## 发布构成

软件版本以根目录 `VERSION` 为准，当前为 0.15.0；`make repo-check` 检查 Python、npm、前端静态能力清单和部署配置是否一致。API 默认版本复用 Python 包版本，部署环境可通过 `APP_VERSION` 显式设置。`CHANGELOG.md` 记录变更，`LICENSE` 与 `THIRD_PARTY_NOTICES.md` 记录授权边界。

默认 Compose 只启动后端和前端：

- backend：Python 3.12、FastAPI、Alembic、SQLite 持久化卷、Mock LLM；
- frontend：Node 22 构建后的 Nginx 静态站点与同源 `/api` 代理；
- postgres：仅在显式 `postgres` profile 中启动，不是 Demo 前置条件。

## 环境变量

| 变量 | 默认／示例 | 说明 |
| --- | --- | --- |
| APP_ENV | development／Compose 为 demo | production 会启用更严格校验并禁用 Demo Header |
| APP_VERSION | 0.15.0 | API 与运行清单版本 |
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

发布前在空库执行完整升级，不使用 ORM `create_all` 替代迁移。当前 head 为 `0028_v6_product_sale_status`，包含 PostgreSQL 产品状态字段扩容。用 `docker compose exec backend alembic heads` 查看源码迁移终点，`alembic current` 查看运行数据库版本。

## SQLite 合成数据备份

内置命令只允许 `development`／`demo`／`test`，只支持文件型 SQLite，并在写入前执行完整性、发布表结构、V5 A-H 完整集合和“无活动非合成家庭”检查。为恢复 0.13.0，工具仍接受完整的 V4 A-C 历史备份，但拒绝任意残缺集合。默认拒绝覆盖已有备份。

Compose 内执行：

```bash
docker compose exec backend python -m app.cli backup-demo \
  --output /data/backups/wealthtwin-demo-0.15.0.sqlite
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
  --input /data/backups/wealthtwin-demo-0.15.0.sqlite \
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

## 常见问题

### GitHub Actions 出现红叉

打开失败运行，先查看失败的 job 和具体 step。`Type check` 失败表示类型检查未通过，不代表测试已经执行；后续步骤可能被跳过。源码修复后运行 `make check`，远端 CI 还会检查两种数据库迁移。历史失败记录会保留，以 `main` 最新提交对应的运行结果为准。

### 页面打不开或端口被占用

新配置默认前端为 `8080`、API 为 `8000`。已有 `.env` 的端口设置优先；开发模式 `make frontend-dev` / `make backend-dev` 则使用 `5173` / `8000`。

```bash
docker compose ps -a
docker compose port frontend 80
docker compose port backend 8000
docker compose logs --tail=100 backend frontend
```

如果默认端口已被其他项目占用，在 `.env` 设置 `FRONTEND_PORT=18080` 与 `BACKEND_PORT=18000`，然后运行 `docker compose up -d --build`。相应页面为 `http://localhost:18080`，健康检查为 `http://localhost:18000/api/v1/health`。上述 `make warmup` / `make acceptance` 的默认端口也需要用 `API_URL` / `WEB_URL` 覆盖。

### GitHub 已更新，但页面仍是旧版本

`docker start` 只启动已有容器，不会重新构建源码。先检查 `docker compose ls` 中的项目和工作目录，再在目标仓库执行 `docker compose up -d --build`。如果此前使用过 `docker compose -p 名称`，继续使用同一个名称，以复用对应数据卷。

健康接口版本应与 `VERSION` 一致；同时检查本地 `.env` 是否残留旧 `APP_VERSION`。保留数据库卷，不要为解决版本问题执行 `down -v`。构建失败时查看构建日志，后端未健康时优先查看迁移日志。

### 缺少 PPT、截图或 final-acceptance 报错

技术仓库不包含 `output/` 比赛成品。普通开发执行 `make repo-check` 和 `make check`。`make final-acceptance` 属于历史材料交付流程，会要求本地成品及历史接口数量；它的失败不能直接判定当前技术项目不可运行。
