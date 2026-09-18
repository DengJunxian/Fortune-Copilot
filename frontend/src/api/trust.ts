export interface KnowledgeCatalog {
  dataset_version: string;
  updated_at: string;
  retrieval_version: string;
  vectorizer_version: string;
  source_summary: string;
  document_count: number;
  active_document_count: number;
  chunk_count: number;
  quarantined_chunk_count: number;
  categories: string[];
  runtime_network_required: false;
}

export interface KnowledgeCitation {
  citation_id: string;
  chunk_id: string;
  chunk_code: string;
  document_code: string;
  title: string;
  issuing_authority: string;
  category: string;
  source_uri: string;
  source_type: string;
  publication_date: string;
  effective_date: string;
  expiry_date: string | null;
  last_verified_date: string | null;
  applicable_audiences: string[];
  applicable_regions: string[];
  page_ref: string | null;
  paragraph_ref: string;
  document_version: string;
  content_hash: string;
}

export interface KnowledgeSearch {
  query: string;
  as_of_date: string;
  answer: string;
  claims: Array<{ text: string; citation_ids: string[] }>;
  matches: Array<{
    chunk_id: string;
    chunk_code: string;
    excerpt: string;
    keyword_score: string;
    vector_score: string;
    metadata_score: string;
    combined_score: string;
    citation_id: string;
  }>;
  citations: KnowledgeCitation[];
  insufficient_information: boolean;
  filtered_expired_count: number;
  filtered_not_yet_effective_count: number;
  filtered_quarantined_count: number;
  retrieval_version: string;
  vectorizer_version: string;
  calculation_source: "deterministic_hybrid_retrieval";
  limitations: string[];
}

export type GraphLane = "family" | "facts" | "goals" | "controls" | "knowledge";

export interface HouseholdGraph {
  graph_id: string;
  graph_version: string;
  title: string;
  subtitle: string;
  as_of_date: string;
  synthetic: boolean;
  nodes: Array<{
    id: string;
    node_type: string;
    label: string;
    lane: GraphLane;
    properties: Record<string, string | number | boolean | null>;
    source_entity_type: string;
    source_entity_id: string | null;
    calculation_source: string;
  }>;
  edges: Array<{
    id: string;
    source: string;
    target: string;
    relation: string;
    label: string;
    evidence: string[];
  }>;
  inferences: Array<{
    code: string;
    title: string;
    conclusion: string;
    evidence_node_ids: string[];
    rule: string;
    human_review_required: boolean;
  }>;
  node_type_coverage: string[];
  calculation_source: "deterministic_relational_graph_service";
  limitations: string[];
}

export interface IntakeDraft {
  draft_id: string;
  household_id: string | null;
  status: "pending_confirmation" | "partially_confirmed" | "confirmed";
  parser_version: string;
  source_text_hash: string;
  redacted_preview: string;
  extracted_fields: Array<{
    code: string;
    label: string;
    value: string;
    value_type: "money" | "count" | "stage" | "relationship" | "text";
    unit: string | null;
    evidence: string;
    confidence: string;
    confirmed: boolean;
  }>;
  missing_fields: Array<{
    code: string;
    label: string;
    reason: string;
    required_for: string[];
    priority: number;
    follow_up_question: string;
  }>;
  confirmed_values: Record<string, string>;
  contains_untrusted_instruction: boolean;
  confirmation_required: boolean;
  created_at: string;
  confirmed_at: string | null;
  boundary_note: string;
}

export interface AgentCatalog {
  orchestrator_version: string;
  state_machine: string[];
  agent_count: 9;
  agents: Array<{
    code: string;
    name: string;
    purpose: string;
    sequence: number;
    input_schema_name: string;
    input_json_schema: Record<string, unknown>;
    output_schema_name: string;
    output_json_schema: Record<string, unknown>;
    allowed_tools: string[];
    prohibited_actions: string[];
    timeout_seconds: number;
    failure_fallback: string;
    audit_event: string;
  }>;
  hard_gates: string[];
}

export interface Orchestration {
  run_id: string;
  household_id: string;
  request_kind: string;
  status: "running" | "completed" | "degraded" | "blocked";
  current_state: string;
  orchestrator_version: string;
  provider_mode: string;
  steps: Array<{
    step_id: string;
    agent_code: string;
    agent_name: string;
    sequence: number;
    status: "pending" | "running" | "completed" | "degraded" | "blocked";
    input_schema_name: string;
    output_schema_name: string;
    tool_calls: Array<{
      tool: string;
      status: "completed" | "degraded" | "blocked";
      input_reference: string;
      output_reference: string;
      calculation_source: string;
    }>;
    structured_output: Record<string, unknown>;
    citations: string[];
    prohibitions_checked: string[];
    timeout_seconds: number;
    failure_code: string | null;
    degraded: boolean;
    started_at: string;
    completed_at: string | null;
  }>;
  numeric_ledger: Array<{
    code: string;
    value: string;
    unit: string;
    source_tool: string;
    source_path: string;
    value_hash: string;
  }>;
  citation_chunk_ids: string[];
  structured_output: Record<string, unknown>;
  blocked_issues: Array<{
    code: string;
    severity: "info" | "warning" | "block";
    message: string;
    claim_index: number | null;
    evidence: string[];
  }>;
  requires_human_review: boolean;
  degraded: boolean;
  started_at: string;
  completed_at: string | null;
  boundary_note: string;
}

const apiBase = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

async function readJson<T>(path: string, signal?: AbortSignal, init?: RequestInit): Promise<T> {
  const response = await fetch(apiBase + path, {
    ...init,
    signal,
    headers: { Accept: "application/json", ...init?.headers },
  });
  if (!response.ok) throw new Error(`API ${response.status}: ${path}`);
  return (await response.json()) as T;
}

export function fetchKnowledgeCatalog(signal?: AbortSignal): Promise<KnowledgeCatalog> {
  return readJson("/api/v1/trust/knowledge/catalog?as_of_date=2026-08-04", signal);
}

export function searchKnowledge(query: string, signal?: AbortSignal): Promise<KnowledgeSearch> {
  return readJson("/api/v1/trust/knowledge/search", signal, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, as_of_date: "2026-08-04", limit: 5 }),
  });
}

export function fetchShanghaiGraph(signal?: AbortSignal): Promise<HouseholdGraph> {
  return readJson("/api/v1/trust/graphs/shanghai-demo?as_of_date=2026-08-04", signal);
}

export function fetchHouseholdGraph(
  householdId: string,
  signal?: AbortSignal,
): Promise<HouseholdGraph> {
  return readJson(
    `/api/v1/households/${encodeURIComponent(householdId)}/trust-graph?analysis_date=2026-08-04`,
    signal,
  );
}

export function createIntakeDraft(householdId: string, text: string): Promise<IntakeDraft> {
  return readJson("/api/v1/trust/intake/drafts", undefined, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ household_id: householdId, text }),
  });
}

export function confirmIntakeDraft(
  draftId: string,
  confirmedValues: Record<string, string>,
): Promise<IntakeDraft> {
  return readJson(`/api/v1/trust/intake/drafts/${encodeURIComponent(draftId)}/confirm`, undefined, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ confirmed_values: confirmedValues }),
  });
}

export function fetchAgentCatalog(signal?: AbortSignal): Promise<AgentCatalog> {
  return readJson("/api/v1/trust/agents/catalog", signal);
}

export function fetchLatestOrchestration(
  householdId: string,
  signal?: AbortSignal,
): Promise<Orchestration | null> {
  return readJson(
    `/api/v1/households/${encodeURIComponent(householdId)}/trust-orchestrations/latest`,
    signal,
  );
}

export function runTrustOrchestration(householdId: string): Promise<Orchestration> {
  return readJson(
    `/api/v1/households/${encodeURIComponent(householdId)}/trust-orchestrations`,
    undefined,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        request_kind: "trusted_plan_explanation",
        policy_query: "个人养老金每年缴费限额和家庭适配需要核对什么?",
        analysis_date: "2026-08-04",
      }),
    },
  );
}
