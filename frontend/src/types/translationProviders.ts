export interface TranslationProviderConfig {
  id: string;
  name: string;
  provider_type: string;     // tencent_cloud
  region: string | null;
  has_secret: boolean;       // 仅 true/false，不暴露密钥
  priority: number;
  is_enabled: boolean;
  timeout_seconds: number;
  metadata_json: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface CreateTranslationProviderRequest {
  name: string;
  provider_type: string;
  secret_id: string;
  secret_key: string;
  region?: string;
  priority?: number;
  is_enabled?: boolean;
  timeout_seconds?: number;
  metadata_json?: Record<string, unknown> | null;
}

export interface UpdateTranslationProviderRequest {
  name?: string;
  provider_type?: string;
  secret_id?: string | null;   // 不传则保留原密钥
  secret_key?: string | null;  // 不传则保留原密钥
  region?: string | null;
  priority?: number;
  is_enabled?: boolean;
  timeout_seconds?: number;
  metadata_json?: Record<string, unknown> | null;
}

export interface TestConnectionRequest {
  config_id?: string;
  secret_id?: string | null;
  secret_key?: string | null;
  region?: string | null;
  timeout_seconds?: number;
}

export interface TestConnectionResponse {
  status: "ok" | "error";
  latency_ms: number | null;
  source_text: string | null;
  translated_text: string | null;
  error_type: string | null;
  message: string | null;
  error_friendly_message: string | null;
  error_code: string | null;
}

// ── Region Ping ──

export interface TMTRegionInfo {
  region: string;
  label: string;
  endpoint: string;
}

export interface RegionPingRequest {
  config_id?: string;
  secret_id?: string | null;
  secret_key?: string | null;
  timeout_seconds?: number;
}

export interface RegionPingResult {
  region: string;
  label: string;
  latency_ms: number | null;
  status: "ok" | "error" | "timeout" | "pending";
  error: string | null;
}

export interface RegionPingResponse {
  results: RegionPingResult[];
}
