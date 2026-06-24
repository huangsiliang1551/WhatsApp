// AI Agent 服务（spec 3.2, 10.2）

import { api } from "./api";
import type {
  AIAgent,
  AIAgentCreateInput,
  AIAgentPatchInput,
} from "../types/aiAgents";
import type { EntryLink } from "../types/entryLinks";

export async function listAIAgents(params?: {
  site_id?: string;
  status?: string;
}): Promise<AIAgent[]> {
  const response = await api.get<AIAgent[]>("/api/ai-agents", { params });
  return response.data;
}

export async function createAIAgent(input: AIAgentCreateInput): Promise<AIAgent> {
  const response = await api.post<AIAgent>("/api/ai-agents", input);
  return response.data;
}

export async function getAIAgent(agentId: string): Promise<AIAgent> {
  const response = await api.get<AIAgent>(`/api/ai-agents/${agentId}`);
  return response.data;
}

export async function updateAIAgent(
  agentId: string,
  input: AIAgentPatchInput,
): Promise<AIAgent> {
  const response = await api.patch<AIAgent>(`/api/ai-agents/${agentId}`, input);
  return response.data;
}

export async function disableAIAgent(agentId: string): Promise<AIAgent> {
  const response = await api.post<AIAgent>(`/api/ai-agents/${agentId}/disable`);
  return response.data;
}

export async function archiveAIAgent(agentId: string): Promise<AIAgent> {
  const response = await api.post<AIAgent>(`/api/ai-agents/${agentId}/archive`);
  return response.data;
}

export async function healthCheckAIAgent(agentId: string): Promise<AIAgent> {
  const response = await api.post<AIAgent>(`/api/ai-agents/${agentId}/health-check`);
  return response.data;
}

export async function listAIAgentEntryLinks(agentId: string): Promise<EntryLink[]> {
  const response = await api.get<EntryLink[]>(`/api/ai-agents/${agentId}/entry-links`);
  return response.data;
}
