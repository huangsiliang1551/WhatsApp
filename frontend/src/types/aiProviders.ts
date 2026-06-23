export interface AIProviderConfig {
  id: string;
  name: string;
  provider_type: string;     // openai | deepseek | groq | ollama | together | custom
  api_base_url: string | null;
  model: string;
  priority: number;
  is_enabled: boolean;
  timeout_seconds: number;
  use_responses_api: boolean;
  has_api_key: boolean;      // 仅 true/false，不暴露密钥
  metadata_json: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface CreateAIProviderRequest {
  name: string;
  provider_type: string;
  api_base_url?: string | null;
  api_key?: string | null;
  model: string;
  priority?: number;
  is_enabled?: boolean;
  timeout_seconds?: number;
  use_responses_api?: boolean;
  metadata_json?: Record<string, unknown> | null;
}

export interface UpdateAIProviderRequest {
  name?: string;
  api_base_url?: string | null;
  api_key?: string | null;    // 不传则保留原密钥
  model?: string;
  priority?: number;
  is_enabled?: boolean;
  timeout_seconds?: number;
  use_responses_api?: boolean;
  metadata_json?: Record<string, unknown> | null;
}

export interface TestConnectionRequest {
  config_id?: string;         // 测试已有配置
  provider_type?: string;     // 或测试临时配置
  api_base_url?: string | null;
  api_key?: string | null;
  model?: string;
  timeout_seconds?: number;
}

export interface TestConnectionResponse {
  status: "ok" | "error";
  latency_ms: number | null;
  model_echoed: string | null;
  error_type: string | null;
  message: string | null;
}

export interface AccountOverride {
  account_id: string;
  provider_config_id: string;
  provider_name: string;
  model: string;
  is_active: boolean;
}
