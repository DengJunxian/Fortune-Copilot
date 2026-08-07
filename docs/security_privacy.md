# Fortune Copilot 安全与隐私控制说明

## 1. 定位与边界

本项目采用“银行级思路、竞赛版可验证最小实现”。它不是通过等保、PCI DSS、ISO 27001 或银行生产安全认证的系统，也不声称替代真实身份平台、密钥管理系统、WAF、SIEM、工单系统、备份擦除流程或监管归档。

主 Demo 默认 `APP_ENV=demo`、SQLite、Mock LLM 和合成数据，无 API Key、真实银行接口或网络也能完整运行。生产配置必须关闭演示请求头认证、设置 32 字符以上随机会话签名密钥、使用明确的 CORS/Host 白名单，并由外部身份提供方完成登录与授权映射。

## 2. 数据分类与最小必要原则

| 等级 | 例子 | 默认处理 |
| --- | --- | --- |
| 直接身份信息 | 姓名、手机号、身份证号、邮箱、地址 | 不进入外部模型；日志不记录值；擦除时去标识 |
| 敏感家庭信息 | 健康、保障、家庭责任 | 独立明示授权；仅在保障核对场景使用 |
| 财务信息 | 收入、支出、资产、负债、目标 | 家庭对象级授权；关键数字仅由确定性工具计算 |
| 治理证据 | 哈希、版本、状态、规则、引用 ID | 最小化保留，用于一致性和审计 |
| 测试数据 | A/B/C 合成家庭、评测夹具 | 必须标注 Mock／测试，不解释为真实客户或生产指标 |

外部模型字段固定白名单为 `intent`、`missing_fields`、`verified_statements`、`verified_fact_refs`、`citation_ids`、`risk_flags`、`language`、`tone`。字段名不在白名单时请求直接失败；手机号、身份证、邮箱、银行卡号和密钥样式会再次脱敏。金额、比率、产品属性和政策事实不由语言模型创建。

## 3. 分场景授权

| 场景 | 范围 | 是否敏感 | 用途 |
| --- | --- | --- | --- |
| core_planning | profile、finance、risk | 否 | 家庭底表、财务体检、目标规划 |
| protection_review | identity_sensitive、health_sensitive、insurance | 是，必须独立确认 | 家庭责任、健康风险与保障缺口核对 |
| simulation_and_report | simulation、report | 否 | 压力模拟与八章报告 |
| behavior_experiment | behavior | 否 | 可退出的行为问卷与实验 |

每条授权必须包含具体场景、用途、版本、时间与 `explicit=true`。涉及敏感范围时还必须包含 `sensitive_data_acknowledged=true`。授权可以逐条撤回；撤回后对应范围不再用于新计算，工作流在缺少基础规划授权时停止推进。

## 4. 身份、会话与对象权限

- 身份区使用 `IdentityAccessGrant` 保存主体不可逆哈希、角色、家庭 ID、用途、允许动作、有效期与撤销时间；家庭财务表不保存登录凭证。
- 应用会话是 HMAC-SHA256 签名、短期、带随机 nonce 的封装，默认 30 分钟超时。签名错误、未来签发、超出最大期限和过期均返回 401。
- 角色固定为 client、advisor、compliance、admin；旧 `risk` 只在 Demo 输入层映射为 compliance。
- 家庭路径由依赖层统一执行对象授权；报告 ID、审核流 ID、录入草稿 ID 等非家庭路径在服务层再次解析归属并授权。
- 越权读取返回 404，避免确认另一个家庭或对象是否存在。受限主体的家庭、顾问和合规列表在查询阶段按授权范围过滤。
- `X-Actor-ID`／`X-Actor-Role` 只在 development、demo、test 且 `DEMO_AUTH_ENABLED=true` 时接受。production 必须使用 Bearer 会话；演示会话签发端点在 production 返回 404。

管理员拥有全家庭访问是当前竞赛版职责模型。真实部署仍需在外部身份平台增加机构、网点、岗位、职责分离、停职和紧急授权流程。

## 5. 隐私权利

### 撤回

逐条撤回采用乐观版本控制，原因只以 SHA-256 摘要进入审计，原文不进入日志。重复或陈旧版本返回 409。

### 导出

`POST /api/v1/households/{id}/privacy/exports` 同时要求：有效 client/admin 会话、对象权限、`X-Confirm-Action: export_household_data` 和导出原因。返回当前家庭的 JSON 包并记录导出范围、格式和原因哈希，不在审计里复制财务载荷。旧 GET 导出仅为 Demo 向后兼容，production 返回 410。

### 删除

`POST /api/v1/households/{id}/privacy/deletion-requests` 同时要求会话、对象权限、`X-Confirm-Action: erase_household_data`、当前记录版本、家庭代码和原因。执行后：

1. 家庭业务记录逻辑删除；
2. 成员姓名、职业和出生日期去标识；
3. 既有审计脱离家庭 ID，并将载荷缩减为事件类型与擦除标记；
4. 只保留 `PrivacyRequest` 的家庭引用哈希、范围、计数和状态；
5. 明确说明备份物理过期由部署方保留策略执行，竞赛版不声称即时擦除备份。

旧通用家庭软删除也必须携带专用二次确认头，但正式隐私操作应使用上述擦除接口。

## 6. Web 与 API 基础防护

- Trusted Host、明确 CORS allowlist；不启用跨域凭证。
- Bearer 会话不依赖浏览器 Cookie；对不安全方法额外校验 Origin，降低跨站请求风险。
- API 与 Nginx 设置 `nosniff`、`DENY` frame、no-referrer、Permissions-Policy 和 CSP；production API 增加 HSTS 并关闭 Swagger、ReDoc 和 OpenAPI 暴露。
- React 不使用 `dangerouslySetInnerHTML`；报告 HTML 对文本和属性转义；引用链接只允许 HTTP/HTTPS，`javascript:` 与本地快照不会进入可点击 href。
- Pydantic 请求模型拒绝额外字段；SQLAlchemy 参数化查询；请求 ID 只接受有限字符集。
- 全局请求体默认 1 MiB；上传默认 512 KiB，只接收 UTF-8 TXT、Markdown、JSON，校验后不持久化。提示注入文件标记为 quarantined。
- 默认每来源/方法/路径每分钟 120 次，计算、模拟、报告和评测写操作每分钟 30 次。当前实现是单进程内存限流，生产必须在网关或 WAF 再执行分布式限流。
- 未处理异常日志只记录异常类型和请求 ID，不记录异常正文、堆栈局部变量或请求载荷。

## 7. 敏感操作二次确认

| 操作 | 角色 | 二次确认 |
| --- | --- | --- |
| 隐私数据导出 | client / admin | session + `export_household_data` |
| 家庭数据逻辑擦除 | client / admin | session + `erase_household_data` + 家庭代码 + 版本 |
| 正式报告发布 | compliance / admin | session + `publish_report` + 报告序号 + 人工复核 |
| 旧家庭软删除 | 当前有权角色 | session + `legacy_soft_delete_household` + 版本 |

报告只有在数据完整性、计算、目标、家庭安全、客户适当性、产品适当性、事实引用、数值一致性、禁止性表述和人工复核十项全部通过时才能发布。

## 8. 环境隔离和配置

| 配置 | Demo/Test | Production |
| --- | --- | --- |
| DEMO_AUTH_ENABLED | true | 必须 false |
| SESSION_SIGNING_KEY | 可用内置 Demo 键 | 必须提供随机 32+ 字符秘密 |
| CORS_ORIGINS | localhost 明确列表 | 不得含 `*` 或 localhost HTTP |
| ALLOWED_HOSTS | localhost/test/backend | 部署域名明确列表 |
| LLM_PROVIDER | mock | 默认仍建议 mock；启用外部模型需完整配置 |
| LLM_BASE_URL | 可为空／本地开发 | HTTPS 且 hostname 必须在 LLM_ALLOWED_HOSTS |
| 文档接口 | 开启 | 关闭 |
| 数据 | 仅合成数据 | 需另行完成真实数据治理审批 |

密钥只通过环境或部署方密钥服务注入。仓库、种子、文档、测试、前端 bundle、Dockerfile 和审计表都不得保存密钥。

## 9. 验证与运维

本地离线质量检查：

```bash
make check
make test-e2e
```

联网依赖情报检查：

```bash
make security-audit
```

安全与对抗测试位于 `backend/tests/test_security_privacy.py`；浏览器质量门禁和测试指标断言位于 `frontend/src/test/App.test.tsx` 与 `frontend/e2e/smoke.spec.ts`。评测结果及公式见 `docs/evaluation.md`，模型边界见 `docs/model_card.md`，代码级审计见 `docs/security_best_practices_report.md`。

## 10. 剩余风险

- 生产身份验证、MFA、SSO、账户恢复与机构级授权由外部 IdP 承担，仓库只验证已签名短会话。
- 已签发会话没有在线撤销列表；授权撤销最多在会话到期后完全生效。生产需接入会话撤销或缩短高风险会话期限。
- 内存限流不跨进程；必须由 API 网关/WAF 补充分布式限流和异常流量检测。
- 上传器不接收 Office/PDF，也不含杀毒沙箱；这属于刻意缩小的竞赛版攻击面。
- 逻辑擦除不等于备份介质即时物理删除；生产需定义法定留存、备份到期和恢复后二次擦除流程。
- 前端 CSP 为兼容既有内联样式允许 `style-src 'unsafe-inline'`；脚本仍只允许 self，后续可用 nonce/hash 收紧样式策略。
