# Fortune Copilot 安全最佳实践审计报告

审计日期：2026-08-05  
范围：FastAPI/SQLAlchemy 后端、React/TypeScript 前端、Nginx、Docker Compose、Python/npm 依赖、隐私与模型调用路径。  
方法：代码审阅、路由/对象边界追踪、密钥模式扫描、依赖漏洞审计、单元/集成/权限/对抗测试、前端静态检查与真实浏览器测试。  
结论口径：竞赛原型的可验证安全基线，不是生产认证或渗透测试替代品。

## 执行摘要

审计识别 4 项高风险、5 项中风险问题。高风险问题均已修复并加入回归测试；中风险代码问题均已修复，其中依赖漏洞通过升级 pytest 修复。仍有 5 项已接受的架构性剩余风险，主要来自竞赛版没有外部 IdP/在线会话撤销、分布式限流、恶意文件沙箱和备份介质擦除。

最终发布判断：Mock/测试环境可进入下一阶段；不得把本报告解释为允许处理真实客户数据或直接生产上线。

## 已修复发现

### SEC-001 — 调用方可伪造 Demo 角色且缺少可信短会话

- 严重度：High
- 状态：Resolved
- 原风险：`X-Actor-ID`/`X-Actor-Role` 由调用方直接控制。若沿用到生产，攻击者可以自行声明 advisor/compliance/admin。
- 影响：角色提升、跨家庭访问、审批或导出越权。
- 修复：新增 HMAC-SHA256 签名、随机 nonce、签发/过期/最大时长校验的 Bearer 会话；production 强制关闭 Demo Header 并要求 32+ 字符签名密钥。演示会话只依据去标识访问授权签发，并检查撤销/有效期。
- 证据：`backend/app/core/auth.py:87`、`backend/app/core/auth.py:126`、`backend/app/core/auth.py:168`、`backend/app/core/auth.py:175`、`backend/app/core/config.py:101`、`backend/app/services/security/privacy.py:74`。
- 验证：签名篡改、会话过期、production Demo Header 拒绝和合法 production Bearer 均由 `backend/tests/test_security_privacy.py` 覆盖。
- 误报说明：Demo/Test 仍故意支持请求头角色，以满足离线竞赛演示；该路径由环境校验隔离，不是生产认证声明。

### SEC-002 — 报告、审核流和录入草稿存在对象级授权缺口

- 严重度：High
- 状态：Resolved
- 原风险：部分路径只有角色检查，知道 report/workflow/draft ID 的同角色主体可能读取其他家庭对象；列表也可能返回未授权家庭。
- 影响：家庭财务、报告、审核证据和录入草稿横向泄漏（BOLA）。
- 修复：家庭路径统一授权；ID 路径解析对象所属家庭后再次授权；越权统一返回 404；家庭、顾问和合规列表在 SQL 查询阶段按授权范围过滤。
- 证据：`backend/app/core/auth.py:168`、`backend/app/services/reporting/service.py:175`、`backend/app/services/review_workflow.py:603`、`backend/app/services/review_workflow.py:1066`、`backend/app/services/trust/intake.py:315`、`backend/app/services/crud.py:50`。
- 验证：受限 Bearer 对授权家庭返回 200，对其他家庭与 SQL 注入式 ID 返回 404。
- 参考：[OWASP API1:2023 Broken Object Level Authorization](https://owasp.org/API-Security/editions/2023/en/0xa1-broken-object-level-authorization/)。

### SEC-003 — 数据导出、删除和报告发布缺少一致的二次确认/发布门禁

- 严重度：High
- 状态：Resolved
- 原风险：旧导出是直接 GET，家庭删除仅软删除，报告没有不可绕过的发布前总门禁。
- 影响：误操作、敏感数据过度导出、删除不完整、未经适当性/引用/人工复核的报告被视为发布版。
- 修复：隐私导出、逻辑擦除和发布使用专用 POST，要求角色、对象权限、动作确认头；擦除再要求家庭代码和乐观版本；发布必须十项全 pass、人工复核和报告序号一致。旧 GET 导出在 production 返回 410，旧软删除也要求二次确认。
- 证据：`backend/app/core/auth.py:238`、`backend/app/api/v1/endpoints/security.py:67`、`backend/app/api/v1/endpoints/security.py:110`、`backend/app/services/security/privacy.py:130`、`backend/app/services/security/privacy.py:182`、`backend/app/services/security/quality_gate.py:94`。
- 验证：缺少确认头返回 409；无人工复核时仅 `human_review` 阻断；十项通过后才发布并写 `QualityGateRun`/AuditEvent。

### SEC-004 — 外部模型输入边界、注入前置阻断和响应大小不足

- 严重度：High
- 状态：Resolved
- 原风险：可选外部 Provider 可能收到超出场景必要范围的上下文；恶意用户指令或超大响应会扩大数据泄漏和资源消耗风险。
- 影响：敏感字段外发、Prompt 注入、非结构化/超大响应进入应用。
- 修复：固定字段白名单和递归脱敏；用户注入在网络调用前阻断；production Provider URL 必须 HTTPS 且 hostname 在 allowlist；响应限制 1 MiB，JSON Schema 与 Pydantic 双校验，失败退回本地模板。
- 证据：`backend/app/core/privacy.py:94`、`backend/app/core/privacy.py:120`、`backend/app/core/privacy.py:132`、`backend/app/services/llm/openai_compatible.py:56`、`backend/app/services/llm/openai_compatible.py:105`、`backend/app/core/config.py:119`。
- 验证：注入字符串在不可达测试 URL 前即被阻断；`member_name` 字段被 allowlist 拒绝；无 Key 返回 Mock。

### SEC-005 — API/边缘缺少统一 Host、Origin、安全头、体积和速率限制

- 严重度：Medium
- 状态：Resolved（生产仍需边缘补强）
- 原风险：Host Header、跨站不安全方法、超大请求、暴力/资源耗尽请求及浏览器基础头缺少统一控制。
- 影响：Host 注入、跨站请求、拒绝服务面扩大、点击劫持与内容嗅探风险。
- 修复：TrustedHost、Origin allowlist、请求体上限、普通/昂贵路径限流、安全头；Nginx 同步 CSP、安全头和 1 MiB client body limit。production 关闭 API 文档并启用 HSTS。
- 证据：`backend/app/core/http_security.py:50`、`backend/app/core/http_security.py:101`、`backend/app/core/http_security.py:185`、`backend/app/main.py:37`、`frontend/nginx.conf:6`。
- 验证：非法 Host=400、非法 Origin=403、第 11 次限流请求=429、17 字节对 16 字节测试上限=413。
- 参考：[Starlette Middleware](https://www.starlette.io/middleware/)。

### SEC-006 — 上传入口缺少窄类型、大小与注入隔离策略

- 严重度：Medium
- 状态：Resolved
- 原风险：未来文档入口若直接接收任意文件，会引入恶意内容、解析器和 Prompt 注入风险。
- 影响：资源消耗、恶意文件持久化、RAG/模型提示注入。
- 修复：只允许 UTF-8 TXT/Markdown/JSON，扩展名与 MIME 双检查，默认 512 KiB，拒绝 NUL/错误编码/无效 JSON；注入标记 quarantined；只在内存检查，不保存原文件。
- 证据：`backend/app/services/security/uploads.py:18`、`backend/app/services/security/uploads.py:25`。
- 验证：允许文件 clean，注入文件 quarantined，HTML=415，超限=413。

### SEC-007 — 引用 URI 可能成为危险协议链接

- 严重度：Medium
- 状态：Resolved
- 原风险：受控知识中的 `source_uri` 直接进入 HTML/React href；若数据源被污染，可形成 `javascript:` 链接。
- 影响：用户点击后的脚本执行或恶意跳转。
- 修复：后端 HTML 和前端组件都只允许完整 HTTP/HTTPS URL；其他协议显示“本地受控快照”，不生成链接；外部链接加 `noopener noreferrer`。
- 证据：`backend/app/services/reporting/render.py:49`、`frontend/src/utils/format.ts:66`、`frontend/src/components/client/PlanningReportWorkspace.tsx:233`。
- 误报说明：当前权威知识源是本地版本化 JSON，未发现危险协议；修复用于防止未来数据污染。

### SEC-008 — 未处理异常堆栈可能把提交值带入日志

- 严重度：Medium
- 状态：Resolved
- 原风险：`logger.exception` 会记录异常正文和堆栈；数据库/解析异常可能包含敏感值。
- 影响：日志侧身份或财务数据泄漏。
- 修复：未处理异常只记录异常类型和请求 ID；验证错误只返回字段路径、错误类型和通用消息；模型/隐私审计只保存字段名、哈希和计数。
- 证据：`backend/app/core/errors.py:102`、`backend/app/core/logging.py:9`、`backend/app/services/security/model_risk.py:22`。

### SEC-009 — 开发依赖 pytest 存在已知临时目录符号链接漏洞

- 严重度：Medium
- 状态：Resolved
- 原风险：本地环境 pytest 8.4.2 命中 GHSA-6w46-j5rx-g56g / CVE-2025-71176。
- 影响：不可信测试环境中，临时目录清理可能受到符号链接竞态影响；不属于应用运行时依赖，但会影响 CI/开发机。
- 修复：约束升级为 `pytest>=9.0.3,<10`，当前解析版本 9.1.1；把 pip-audit 纳入 dev 依赖和显式联网门禁。
- 证据：`backend/pyproject.toml:26`、`backend/pyproject.toml:27`、`Makefile:65`。
- 参考：[GitHub Advisory GHSA-6w46-j5rx-g56g](https://github.com/advisories/GHSA-6w46-j5rx-g56g)。

## 剩余风险与缓解

### RISK-001 — 无仓库内生产登录/MFA/在线会话撤销

- 严重度：Medium
- 状态：Accepted for competition scope
- 影响：签发后的短会话在授权撤销后可能继续有效到过期。
- 缓解：默认 30 分钟；生产只能由外部 IdP 签发；上线前接入 MFA、撤销列表、人员状态和高风险再认证。

### RISK-002 — 限流为单进程内存状态

- 严重度：Medium
- 状态：Accepted with deployment requirement
- 影响：多副本间不共享计数，进程重启清零。
- 缓解：应用层保留最小保护；生产必须在 API 网关/WAF 使用共享限流和告警。

### RISK-003 — 逻辑擦除不覆盖备份即时物理销毁

- 严重度：Medium
- 状态：Accepted with policy requirement
- 缓解：响应明确披露；生产定义法定留存、备份到期、恢复后二次擦除和操作审计。

### RISK-004 — 文档安全只覆盖文本，不含恶意 Office/PDF 沙箱

- 严重度：Low
- 状态：Accepted by attack-surface reduction
- 缓解：竞赛版拒绝 Office/PDF；如未来开放，必须使用隔离转换、杀毒/CDR、页数/压缩比限制和人工复核。

### RISK-005 — 前端 CSP 允许内联样式

- 严重度：Low
- 状态：Accepted temporarily
- 缓解：脚本只允许 self，React 不使用危险 HTML；后续将既有内联样式迁移到 class 或采用 nonce/hash 后移除 `style-src 'unsafe-inline'`。

## 供应链与密钥结论

- Python 与 npm 锁定/约束均纳入审计；最终结果记录在 `docs/progress.md`。
- 仓库密钥模式扫描未把用户提供的外部模型凭证写入源码、环境样例、文档、测试、镜像或输出。
- 外部模型配置只通过环境注入；默认 Mock，不因缺 Key 阻断 Demo。

## 参考基线

- [OWASP API Security Top 10 — API1:2023](https://owasp.org/API-Security/editions/2023/en/0xa1-broken-object-level-authorization/)
- [OWASP API Security Top 10 — API3:2023](https://owasp.org/API-Security/editions/2023/en/0xa3-broken-object-property-level-authorization/)
- [OWASP API Security Top 10 — API5:2023](https://owasp.org/API-Security/editions/2023/en/0xa5-broken-function-level-authorization/)
- [Starlette Middleware](https://www.starlette.io/middleware/)
- [FastAPI Behind a Proxy](https://fastapi.tiangolo.com/advanced/behind-a-proxy/)
