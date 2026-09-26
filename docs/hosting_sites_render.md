# Fortune Copilot V6 完整演示托管

本方案保留现有 V6 前后端与合成数据边界：Sites 承载 React 静态资源和同源 `/api` Worker 代理；Render Free 承载原 FastAPI Docker 镜像；Neon Free PostgreSQL 持久化合成家庭。两端连通并通过下列验收前，不发布 Sites 版本。用户当前明确不创建付费资源。

## 运行边界

- 这是**仅限合成家庭**的私有比赛演示，不是银行生产部署；`APP_ENV=demo`、`LLM_PROVIDER=mock`、Mock 银行适配器均保持原义。
- Sites 保持 owner-only。浏览器只请求 Sites 的同源 `/api`；Worker 在服务端加入 `X-Fortune-Proxy-Secret`，从不把密钥注入 Vite 包。
- Render 的 `HOSTED_PROXY_REQUIRED=true` 在密钥未设置或不足 32 字符时拒绝启动；除 `/api/v1/health/live` 外，直连 Render URL 一律需要代理密钥。
- `render.yaml` 关闭自动部署并选择 Render `free` Web Service。免费实例不能挂持久卷，闲置后会休眠，下一次访问可能需要约一分钟唤醒；不能把它当作始终在线的比赛现场保障。超出免费额度也可能被暂停。
- Neon Free 存放 PostgreSQL；不要使用 Render 30 天到期的免费 PostgreSQL，也不要把 SQLite 写在 Render 免费实例的临时文件系统中。Neon 的免费额度与数据保留条件须在创建页面再次核对。
- 公开基金目录快照可能过期。过期时仍可展示来源与候选筛选，但系统保持 `executable_recommendations_allowed=false`；不能把演示候选说成当日可执行的工行货架产品。
- `data/` 随 Docker 镜像发布为 `/seed-data`。启动脚本连接外部 PostgreSQL，运行 Alembic 与幂等 `seed --if-empty`；容器重启不会重置家庭事件和方案记录。

## 部署顺序

1. 本地执行 `npm run test:sites`、`npm run build:sites`、后端测试以及 Docker 构建，确认 `dist/client/index.html`、`dist/server/index.js` 和 `dist/.openai/hosting.json` 来自同一源码状态。
   后端 CI 同时在 SQLite 和 PostgreSQL 上运行空库迁移，并用 PostgreSQL 验证公开产品目录首次加载；两种数据库都须 `alembic check` 无差异。
2. 在用户本人登录的 Neon 工作区创建**免费** PostgreSQL 项目，仅用于合成家庭。将 Neon 连接字符串的 scheme 改为 `postgresql+psycopg://`，保留 `sslmode=require`；密钥不要提交到仓库。
3. 在已登录的 Render 工作区，从仓库根目录 `render.yaml` 创建 Free Blueprint。创建时填写上一步的 `DATABASE_URL`，并填写随机生成的 `HOSTED_PROXY_SECRET`（至少 32 字符）；不要添加付款方式、选择付费规格或创建持久卷。检查服务的真实 URL 与免费额度。
4. Render 启动后，确认 `/api/v1/health/live` 可达，直接访问 `/api/v1/households` 返回 `403 proxy_required`，持密钥请求可读到合成家庭。检查日志确认 PostgreSQL 迁移和种子成功。
5. 在 Sites 创建或复用项目，把同一个密钥以 secret 环境变量 `FORTUNE_PROXY_SECRET` 写入运行时，并将 `FORTUNE_API_ORIGIN` 设为 Render 的 HTTPS origin。不要设置 `VITE_API_BASE_URL` 为 Render URL；前端继续使用同源 `/api`。
6. 将**精确源码 commit**推到 Sites source repository，构建并保存该 commit 对应版本；只在后端已就绪且验收完成后部署 owner-only 版本。Sites 的任何部署 URL 都按生产 URL 对待。
7. 从 Sites 域名验证健康、家庭列表、CHFH、ELTC、GRB、组合、候选漏斗、家庭事件重算、客户经理和合规视图。确认前端没有退回 `offline-demo`，也没有向浏览器暴露代理密钥。现场演示前主动打开站点完成冷启动预热，并复查上述主链路。

## 故障与恢复

- 如果 Sites 返回 `503 API hosting is not configured`，核对两项 Sites 运行时环境变量并重新部署保存的版本。
- 如果 API 返回 `403 proxy_required`，核对 Render 与 Sites 密钥是否一致；不要关闭门禁作为排障手段。
- 如果 Render 健康通过但业务请求失败，检查 Neon 连接串、TLS、Alembic、免费额度和 `/seed-data` 路径。不能改回临时 SQLite 来掩盖数据库连接故障。
- 如果需要公开分享给评委，先重新设计身份授权、数据隔离、配额与审计；不能简单把 owner-only 改成 public。当前演示角色 Header 不是生产身份系统。
