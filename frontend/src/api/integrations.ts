export type IntegrationState =
  | "available_public_snapshot"
  | "implemented_local_only"
  | "mock_only"
  | "contract_required"
  | "authorization_required"
  | "governance_required"
  | "operational_evidence_required";

export interface CapabilityReadiness {
  capability: string;
  label: string;
  state: IntegrationState;
  adapter_id: string;
  execution_allowed: boolean;
  production_blocking: boolean;
  current_implementation: string;
  required_prerequisites: string[];
  evidence: string[];
}

export interface OperationalControlReadiness {
  code: string;
  label: string;
  state: string;
  production_blocking: boolean;
  evidence: string;
}

export interface AuthoritativeSourceReference {
  code: string;
  title: string;
  authority: string;
  source_reference: string;
  effective_from: string | null;
}

export interface IntegrationReadiness {
  assessment_version: string;
  assessed_at: string;
  runtime_mode: string;
  production_ready: boolean;
  has_live_icbc_connection: boolean;
  has_live_government_connection: boolean;
  public_data_snapshot_version: string;
  public_data_integrity_hash: string;
  capabilities: CapabilityReadiness[];
  operational_controls: OperationalControlReadiness[];
  authoritative_sources: AuthoritativeSourceReference[];
  boundary_note: string;
}

export interface PublicDataSnapshotSummary {
  snapshot: {
    publication_cutoff: string;
    official_cpi: {
      rate: string;
      statistic_label: string;
      source_reference: string;
      version: string;
    };
    regional_minimum_wages: Record<string, {
      region_name: string;
      version: string;
      data_quality: string;
    }>;
    regional_living_cost_observations: Record<string, {
      region_name: string;
      amount: string;
      period_end: string;
      data_quality: string;
      can_be_used_as_cpi: false;
    }>;
  };
  integrity_hash: string;
  update_mode: "controlled_snapshot_not_runtime_scraping";
  boundary_note: string;
}

const apiBase = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

async function readJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(apiBase + path, {
    signal,
    headers: { Accept: "application/json" },
  });
  if (!response.ok) throw new Error(`API ${response.status}: ${path}`);
  return (await response.json()) as T;
}

export function fetchIntegrationReadiness(signal?: AbortSignal): Promise<IntegrationReadiness> {
  return readJson("/api/v1/integrations/readiness", signal);
}

export function fetchPublicDataSnapshot(signal?: AbortSignal): Promise<PublicDataSnapshotSummary> {
  return readJson("/api/v1/public-data/authoritative-snapshot", signal);
}
