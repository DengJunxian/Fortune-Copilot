/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_ENABLE_V5_FINANCIAL_GRAPH?: string;
  readonly VITE_ENABLE_V5_CLIENT_PROFILE?: string;
  readonly VITE_ENABLE_V5_LIABILITY_ENGINE?: string;
  readonly VITE_ENABLE_V5_PERSISTENT_TWIN?: string;
  readonly VITE_ENABLE_V5_FAMILY_ENTERPRISE?: string;
  readonly VITE_ENABLE_V5_CFS?: string;
  readonly VITE_ENABLE_V5_PRODUCT_ONTOLOGY?: string;
  readonly VITE_ENABLE_V5_MONITORING?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
