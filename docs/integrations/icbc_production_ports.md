# 工商银行生产集成端口与边界

## 结论

公开互联网资料可以验证工商银行存在开放平台和银企互联接入机制，却不能取得客户数据、业务权限、生产证书或交易资格。Fortune Copilot 因此不内置猜测的 URL、交易码、字段或签名算法；银行专有能力默认绑定 `UnavailableProductionAdapter`，调用时返回 503，且禁止用 Mock 结果替代生产事实。

工商银行公开的[银企互联介绍](https://www.icbc.com.cn/page/773213223851053056.html)将接入流程列为申请、场景分析、协议签署、联调测试和生产运行。公开的[企业开发手册](https://open.icbc.com.cn/icbc/apip/mdres/bank_enterprise_access.pdf)还涉及证书、签名、报文和网络要求。这些资料用于确认接入边界，并不构成 Fortune Copilot 已获得的个人客户、产品或交易接口。

## 已建立的 Port

| Port | 生产职责 | 未满足时行为 |
| --- | --- | --- |
| `IdentityAccessPort` | 联邦身份、MFA、角色与家庭对象授权 | 禁止建立生产会话 |
| `CustomerConsentPort` | 用途、范围、有效期、撤回与单独同意 | 禁止读取客户数据 |
| `CustomerDueDiligencePort` | KYC、受益所有人、CDD/EDD、AML | 禁止进入产品和交易流程 |
| `BankFinancialDataPort` | 账户、流水、贷款和对账事实 | 不生成替代余额或流水 |
| `InstitutionalDataPort` | 社保、公积金、年金和养老金事实 | 只允许客户自报或明确 Mock 数据 |
| `ProductMasterPort` | 可售状态、费率、库存、风险和渠道权限 | 只允许教育性资产类别结果 |
| `TransactionExecutionPort` | 交易时点适当性、订单、清算和持仓回写 | 不生成可执行购买建议 |
| `AdvisorCrmPort` | 工单、职责分离、人工签署和回写 | 本地审核流不能冒充银行 CRM |
| `InvestmentCommitteePort` | Market/Property Regime 发布与撤回 | 继续使用明确标记的 Demo 快照 |
| `ChannelDeliveryPort` | 手机银行、网银、网点和客户经理渠道 | 不宣称全渠道上线 |

## 接入验收条件

真实 Adapter 至少需要通过以下验收后才能替换默认阻断器：

1. 业务协议、数据处理目的、字段范围和保留期限已经批准。
2. 客户授权可验证、可撤回，敏感信息满足单独同意要求。
3. 密钥和证书由银行密钥设施托管，仓库与日志不保存秘密值。
4. 请求具备幂等、超时、重试边界、对账和审计证据。
5. 产品与交易数据带业务时点；陈旧或不可用时失败关闭。
6. 独立安全、合规、模型和灾备审查完成。

`GET /api/v1/integrations/readiness` 将这些条件逐项显示。当前返回 `production_ready=false` 和 `has_live_icbc_connection=false` 是预期结果，不是故障伪装。

仓库原有“快速 KYC”只收集风险能力、意愿、知识和波动承受，用于财富规划适当性上限；它不是监管意义上的客户身份核验、受益所有人识别、CDD/EDD 或 AML。两者在代码和界面中不得互相替代。
