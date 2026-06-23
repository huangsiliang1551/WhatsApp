import { api } from "./api";
import type {
  AIProviderConfig,
  CreateAIProviderRequest,
  UpdateAIProviderRequest,
  TestConnectionRequest,
  TestConnectionResponse,
  AccountOverride,
} from "../types/aiProviders";

export async function listAIProviderConfigs(includeDisabled: boolean = false): Promise<AIProviderConfig[]> {
  const response = await api.get<AIProviderConfig[]>(`/api/ai-providers?include_disabled=${includeDisabled}`);
  return response.data;
}

export async function createAIProviderConfig(data: CreateAIProviderRequest): Promise<AIProviderConfig> {
  const response = await api.post<AIProviderConfig>("/api/ai-providers", data);
  return response.data;
}

export async function updateAIProviderConfig(id: string, data: UpdateAIProviderRequest): Promise<AIProviderConfig> {
  const response = await api.patch<AIProviderConfig>(`/api/ai-providers/${id}`, data);
  return response.data;
}

export async function deleteAIProviderConfig(id: string): Promise<void> {
  await api.delete(`/api/ai-providers/${id}`);
}

export async function testAIProviderConnection(data: TestConnectionRequest): Promise<TestConnectionResponse> {
  const configId = data.config_id;
  if (!configId) {
    throw new Error("缺少 config_id，请先保存提供商后再测试连接");
  }
  const response = await api.post<TestConnectionResponse>(`/api/ai-providers/${configId}/test`, data);
  return response.data;
}

export async function reorderAIProviders(orderedIds: string[]): Promise<void> {
  await api.put("/api/ai-providers/reorder", { ordered_ids: orderedIds });
}

export async function listAccountOverrides(): Promise<AccountOverride[]> {
  const response = await api.get<AccountOverride[]>("/api/ai-providers/account-overrides");
  return response.data;
}

export async function setAccountOverride(accountId: string, configId: string): Promise<void> {
  await api.put(`/api/ai-providers/account-overrides/${accountId}`, { provider_config_id: configId });
}

export async function clearAccountOverride(accountId: string): Promise<void> {
  await api.delete(`/api/ai-providers/account-overrides/${accountId}`);
}
