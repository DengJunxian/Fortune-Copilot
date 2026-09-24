# Fortune Copilot V6 完整演示托管

本方案保留现有 V6 前后端与合成数据边界：Sites 承载 React 静态资源和同源 `/api` Worker 代理；Render 承载原 FastAPI Docker 镜像、SQLite 持久卷与只读规则／样本快照。两端连通并通过下列验收前，不发布 Sites 版本。

## 运行边界

- 这是**仅限合成家庭**的私有比赛演示，不是银行生产部署；`APP_ENV=demo`、`LLM_PROVIDER=mock`、Mock 银行适配器均保持原义。
- Sites 保持 owner-only。浏览器只请求 Sites 的同源 `/api`；Worker 在服务端加入 `X-Fortune-Proxy-Secret`，从不把密钥注入 Vite 包。
- Render 的 `HOSTED_PROXY_REQUIRED=true` 在密钥未设置或不足 32 字符时拒绝启动；除 `/api/v1/health/live` 外，直连 Render URL 一律需要代理密钥。
- `render.yaml` 关闭自动部署，并使用付费 `0.5c-512mb` Web Service＋1 GB 持久卷；没有持久卷时不应上线需要写入／事件重算的完整 Demo。费用以 Render 创建页面显示为准，不能将它表述为免费服务。
- `data/` 随 Docker 镜像发布为 `/seed-data`，SQLite 在 `/data` 持久化。启动脚本在挂载卷可见后运行 Alembic 与幂等 `seed --if-empty`。

## 部署顺序

1. 本地执行 `npm run test:sites`、`npm run build:sites`、后端测试以及 Docker 构建，确认 `dist/client/index.html`、`dist/server/index.js` 和 `dist/.openai/hosting.json` 来自同一源码状态。
2. 在已登录且获得付费资源授权的 Render 工作区，从仓库根目录 `render.yaml` 创建 Blueprint。创建时填写随机生成的 `HOSTED_PROXY_SECRET`（至少 32 字符），不要提交到仓库或放入前端构建变量。检查服务的真实 URL、计费与持久卷。
3. Render 启动后，确认 `/api/v1/health/live` 可达，直接访问 `/api/v1/households` 返回 `403 proxy_required`，持密钥请求可读到合成家庭。检查日志确认迁移和种子成功。
4. 在 Sites 创建或复用项目，把同一个密钥以 secret 环境变量 `FORTUNE_PROXY_SECRET` 写入运行时，并将 `FORTUNE_API_ORIGIN` 设为 Render 的 HTTPS origin。不要设置 `VITE_API_BASE_URL` 为 Render URL；前端继续使用同源 `/api`。
5. 将**精确源码 commit**推到 Sites source repository，构建并保存该 commit 对应版本；只在后端已就绪且验收完成后部署 owner-only 版本。Sites 的任何部署 URL 都按生产 URL 对待。
6. 从 Sites 域名验证健康、家庭列表、CHFH、ELTC、GRB、组合、候选漏斗、家庭事件重算、客户经理和合规视图。确认前端没有退回 `offline-demo`，也没有向浏览器暴露代理密钥。

## 故障与恢复

- 如果 Sites 返回 `503 API hosting is not configured`，核对两项 Sites 运行时环境变量并重新部署保存的版本。
- 如果 API 返回 `403 proxy_required`，核对 Render 与 Sites 密钥是否一致；不要关闭门禁作为排障手段。
- 如果 Render 健康通过但业务请求失败，检查 Alembic、`/data` 持久卷和 `/seed-data` 路径。Render 的 pre-deploy 容器不访问持久卷，因此迁移与种子必须继续在启动脚本中。
- 如果需要公开分享给评委，先重新设计身份授权、数据隔离、配额与审计；不能简单把 owner-only 改成 public。当前演示角色 Header 不是生产身份系统。
