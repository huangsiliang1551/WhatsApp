import { api } from "./api";
import type {
  TranslationProviderConfig,
  CreateTranslationProviderRequest,
  UpdateTranslationProviderRequest,
  TestConnectionRequest,
  TestConnectionResponse,
  RegionPingRequest,
  RegionPingResponse,
  TMTRegionInfo,
} from "../types/translationProviders";

export async function listTranslationProviderConfigs(includeDisabled: boolean = false): Promise<TranslationProviderConfig[]> {
  const response = await api.get<TranslationProviderConfig[]>(`/api/translation-providers?include_disabled=${includeDisabled}`);
  return response.data;
}

export async function createTranslationProviderConfig(data: CreateTranslationProviderRequest): Promise<TranslationProviderConfig> {
  const response = await api.post<TranslationProviderConfig>("/api/translation-providers", data);
  return response.data;
}

export async function updateTranslationProviderConfig(id: string, data: UpdateTranslationProviderRequest): Promise<TranslationProviderConfig> {
  const response = await api.patch<TranslationProviderConfig>(`/api/translation-providers/${id}`, data);
  return response.data;
}

export async function deleteTranslationProviderConfig(id: string): Promise<void> {
  await api.delete(`/api/translation-providers/${id}`);
}

export async function testTranslationProviderConnection(data: TestConnectionRequest): Promise<TestConnectionResponse> {
  const configId = data.config_id;
  if (!configId) {
    throw new Error("缺少 config_id，请先保存提供商后再测试连接");
  }
  const response = await api.post<TestConnectionResponse>(`/api/translation-providers/${configId}/test`, data);
  return response.data;
}

// ── Region Ping ──

export async function listTMTRegions(): Promise<TMTRegionInfo[]> {
  const response = await api.get<TMTRegionInfo[]>("/api/translation-providers/regions");
  return response.data;
}

export async function pingTMTRegions(data: RegionPingRequest): Promise<RegionPingResponse> {
  const response = await api.post<RegionPingResponse>("/api/translation-providers/ping-regions", data);
  return response.data;
}
