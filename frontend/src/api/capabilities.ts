export type CapabilityStatus = "available" | "planned" | "blocked";

export interface DependencyStatus {
  status: "ok" | "degraded";
  detail: string;
}

export interface Capability {
  id: string;
  status: CapabilityStatus;
  implementation: "real" | "mock" | "mock_only" | "none";
  notes: string;
}

export interface CapabilitiesResponse {
  version: string;
  runtime_mode: string;
  mock_mode: boolean;
  database: DependencyStatus;
  portals: string[];
  capabilities: Capability[];
  guardrails: string[];
}

export type CapabilitySource = "api" | "offline-fallback";

export const offlineCapabilities: CapabilitiesResponse = {
  version: "0.13.0",
  runtime_mode: "offline-demo",
  mock_mode: true,
  database: {
    status: "degraded",
    detail: "后端不可达，前端使用本地能力清单",
  },
  portals: ["client", "advisor", "risk"],
  capabilities: [
    {
      id: "frontend_foundation",
      status: "available",
      implementation: "real",
      notes: "React 三端路由、设计令牌、错误边界与离线降级",
    },
    {
      id: "llm_provider",
      status: "available",
      implementation: "mock",
      notes: "当前不依赖外部模型",
    },
    {
      id: "domain_data",
      status: "blocked",
      implementation: "real",
      notes: "领域模型与 CRUD 已实现；当前纯前端降级模式无法访问后端数据库",
    },
    {
      id: "synthetic_households",
      status: "blocked",
      implementation: "real",
      notes: "家庭 A/B/C 已随项目提供；连接后端后可访问",
    },
    {
      id: "financial_engine",
      status: "blocked",
      implementation: "real",
      notes: "确定性财务体检已实现；纯前端降级模式无法读取家庭数据库",
    },
    {
      id: "client_experience",
      status: "blocked",
      implementation: "real",
      notes: "十一项客户任务和八章规划书已实现；需连接本地 Mock 后端读取合成家庭数据",
    },
    {
      id: "advisor_compliance_workflow",
      status: "blocked",
      implementation: "real",
      notes: "四角色审核流已实现；纯前端降级无法读取不可变方案与审计链",
    },
    {
      id: "bank_adapter",
      status: "blocked",
      implementation: "mock_only",
      notes: "八类合成 Mock 银行适配接口需要本地后端，不连接真实银行",
    },
    {
      id: "complete_demo_release",
      status: "blocked",
      implementation: "real",
      notes: "十阶段完整 Demo、三家庭对照和七项实验已实现；纯前端降级无法执行后端计算",
    },
  ],
  guardrails: [
    "credit_limit_is_not_asset",
    "no_fixed_four_account_ratio",
    "no_principal_or_return_guarantee",
    "llm_must_not_calculate_key_numbers",
    "growth_70_percent_requires_long_term_funds_and_safety_gates",
    "minimum_wage_is_not_cpi",
    "no_default_stock_leverage_or_futures_recommendation",
  ],
};

const apiBase = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

export async function fetchCapabilities(signal?: AbortSignal): Promise<CapabilitiesResponse> {
  const response = await fetch(apiBase + "/api/v1/meta/capabilities", {
    signal,
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error("Capability endpoint returned " + response.status);
  }
  return (await response.json()) as CapabilitiesResponse;
}
