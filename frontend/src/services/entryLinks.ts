// 入口链接服务（spec 3.2, 10.1）
// 复用 api.ts 的 axios 实例与鉴权拦截器，不重复造 client。

import { api } from "./api";
import type {
  EntryLink,
  EntryLinkCreateInput,
  EntryLinkStats,
} from "../types/entryLinks";

export async function listEntryLinks(params?: {
  site_id?: string;
  link_type?: string;
  target_type?: string;
  target_staff_user_id?: string;
  target_ai_agent_id?: string;
  status?: string;
}): Promise<EntryLink[]> {
  const response = await api.get<EntryLink[]>("/api/entry-links", { params });
  return response.data;
}

export async function createEntryLink(
  input: EntryLinkCreateInput,
): Promise<EntryLink> {
  const response = await api.post<EntryLink>("/api/entry-links", input);
  return response.data;
}

export async function getEntryLink(linkId: string): Promise<EntryLink> {
  const response = await api.get<EntryLink>(`/api/entry-links/${linkId}`);
  return response.data;
}

export async function revokeEntryLink(linkId: string): Promise<EntryLink> {
  const response = await api.post<EntryLink>(`/api/entry-links/${linkId}/revoke`);
  return response.data;
}

export async function rotateEntryLink(linkId: string): Promise<EntryLink> {
  const response = await api.post<EntryLink>(`/api/entry-links/${linkId}/rotate`);
  return response.data;
}

export async function getEntryLinkStats(linkId: string): Promise<EntryLinkStats> {
  const response = await api.get<EntryLinkStats>(`/api/entry-links/${linkId}/stats`);
  return response.data;
}
