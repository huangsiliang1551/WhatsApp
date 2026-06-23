import { api } from "./api";

// ── Types ──

export interface H5Language {
  id: string;
  language_code: string;
  display_name: string;
  flag_emoji?: string;
  is_enabled: boolean;
  is_default: boolean;
  created_at: string;
  updated_at?: string;
}

export interface CreateLanguageRequest {
  language_code: string;
  display_name: string;
  flag_emoji?: string;
  is_enabled?: boolean;
}

export interface UpdateLanguageRequest {
  display_name?: string;
  flag_emoji?: string;
  is_enabled?: boolean;
}

export interface TranslationEntry {
  id: string;
  site_id: string;
  language_code: string;
  translation_key: string;
  translated_text: string;
  is_ai_translated: boolean;
  created_at: string;
  updated_at?: string;
}

export interface TranslateKeyRequest {
  key: string;
  source_text?: string;
}

export interface BatchTranslateRequest {
  source_language_code: string;
}

export interface SitePermission {
  id: string;
  site_id: string;
  user_id: string;
  role: string;
  created_at: string;
  updated_at?: string;
}

export interface GrantPermissionRequest {
  site_id: string;
  user_id: string;
  role: string;
}

export interface DeployVerification {
  site_id: string;
  domain: string;
  results: {
    domain_accessible: boolean;
    ssl_valid: boolean;
    api_proxy_working: boolean;
    error?: string;
  };
}

export interface DeployScriptResult {
  site_id: string;
  site_key: string;
  domain: string;
  script: string;
}

export interface H5SiteEnhanced {
  site_key: string;
  name: string;
  brand_name?: string;
  account_id?: string;
  site_type: string;
  status: string;
  domain?: string;
  created_at: string;
  id?: string;
  [key: string]: unknown;
}

export interface H5Site {
  site_key: string;
  name: string;
  brand_name?: string;
  account_id?: string;
  site_type: string;
  status: string;
  domain?: string;
  created_at: string;
  id?: string;
}

// ── Language Management ──

export async function listLanguages(): Promise<H5Language[]> {
  const res = await api.get<{ items: H5Language[]; total: number }>("/api/h5/languages");
  return res.data.items;
}

export async function createLanguage(data: CreateLanguageRequest): Promise<H5Language> {
  const res = await api.post<H5Language>("/api/h5/languages", data);
  return res.data;
}

export async function updateLanguage(id: string, data: UpdateLanguageRequest): Promise<H5Language> {
  const res = await api.put<H5Language>(`/api/h5/languages/${encodeURIComponent(id)}`, data);
  return res.data;
}

export async function deleteLanguage(id: string): Promise<void> {
  await api.delete(`/api/h5/languages/${encodeURIComponent(id)}`);
}

export async function setDefaultLanguage(id: string): Promise<void> {
  await api.post(`/api/h5/languages/${encodeURIComponent(id)}/set-default`);
}

// ── Translation Management ──

export async function getTranslations(siteId: string, langCode: string): Promise<TranslationEntry[]> {
  const res = await api.get<{ translations: TranslationEntry[]; total: number }>(
    `/api/h5/sites/${encodeURIComponent(siteId)}/translations/${encodeURIComponent(langCode)}`
  );
  return res.data.translations;
}

export async function translateKey(
  siteId: string,
  langCode: string,
  data: TranslateKeyRequest
): Promise<string> {
  const res = await api.post<string>("/api/h5/translations/translate", data, {
    params: { site_id: siteId, language_code: langCode },
  });
  return res.data;
}

export async function batchTranslate(
  siteId: string,
  langCode: string,
  data: BatchTranslateRequest
): Promise<Record<string, string>> {
  const res = await api.post<Record<string, string>>(
    `/api/h5/sites/${encodeURIComponent(siteId)}/translations/${encodeURIComponent(langCode)}/batch`,
    data
  );
  return res.data;
}

// ── Site Permissions ──

export async function getUserPermissions(userId: string): Promise<SitePermission[]> {
  const res = await api.get<SitePermission[]>("/api/h5/permissions/user", {
    params: { user_id: userId },
  });
  return res.data;
}

export async function getSitePermissions(siteId: string): Promise<SitePermission[]> {
  const res = await api.get<{ items: SitePermission[]; total: number }>(
    `/api/h5/sites/${encodeURIComponent(siteId)}/permissions`
  );
  return res.data.items;
}

export async function grantPermission(data: GrantPermissionRequest): Promise<SitePermission> {
  const res = await api.post<SitePermission>("/api/h5/permissions", data);
  return res.data;
}

export async function revokePermission(id: string): Promise<void> {
  await api.delete(`/api/h5/permissions/${encodeURIComponent(id)}`);
}

export async function updatePermissionRole(id: string, role: string): Promise<SitePermission> {
  const res = await api.put<SitePermission>(`/api/h5/permissions/${encodeURIComponent(id)}`, { role });
  return res.data;
}

// ── Deployment ──

export async function generateDeployScript(siteId: string): Promise<DeployScriptResult> {
  const res = await api.post<DeployScriptResult>(`/api/h5/sites/${encodeURIComponent(siteId)}/deploy-script`);
  return res.data;
}

export async function verifyDeployment(siteId: string): Promise<DeployVerification> {
  const res = await api.post<DeployVerification>(`/api/h5/sites/${encodeURIComponent(siteId)}/verify-deployment`);
  return res.data;
}

// ── Sites (Enhanced, with id field) ──

export async function listSites(): Promise<H5Site[]> {
  const res = await api.get<{ items: H5Site[] } | H5Site[]>("/api/platform/sites");
  // Handle both paginated {items: [...]} and flat array formats
  if (Array.isArray(res.data)) return res.data;
  return (res.data as { items: H5Site[] }).items ?? [];
}
