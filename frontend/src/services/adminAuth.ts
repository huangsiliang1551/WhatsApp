/**
 * AdminAuthService — 管理后台 JWT 认证服务
 *
 * 职责：
 * - login / refresh / logout / getMe
 * - Token 存储（内存优先，「记住登录」存 localStorage）
 * - 认证状态判断
 */

const STORAGE_KEY_ACCESS = "admin_access_token";
const STORAGE_KEY_REFRESH = "admin_refresh_token";

let inMemoryAccessToken: string | null = null;
let inMemoryRefreshToken: string | null = null;

export interface AdminTokens {
  access_token: string;
  refresh_token?: string;
  expires_in?: number;
  account_ids?: string[];
  user_type?: string;
}

export interface AdminUser {
  id: string;
  username: string;
  display_name: string;
  role: "admin" | "operator" | "agent" | "super_admin" | "support" | "finance" | "manager";
  avatar_url?: string;
  email?: string;
  user_type?: "super_admin" | "agent" | "agent_member";
  agency_id?: string;
  agency_name?: string;
}

interface RawAdminMeResponse {
  user_id: string;
  id?: string;
  username: string;
  role: string;
}

export interface LoginPayload {
  username: string;
  password: string;
  remember?: boolean;
}

export interface ChangePasswordPayload {
  old_password: string;
  new_password: string;
}

const API_BASE = resolveApiBaseUrl(
  import.meta.env.VITE_API_BASE_URL as string | undefined,
  import.meta.env.DEV,
);

async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const token = getAccessToken();
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 10_000);
  try {
    const response = await fetch(`${API_BASE}${path}`, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    clearTimeout(timer);
    if (!response.ok) {
      const errorBody = await response.json().catch(() => ({}));
      const message =
        (errorBody as { detail?: string }).detail ||
        (errorBody as { message?: string }).message ||
        `HTTP ${response.status}`;
      throw new Error(message);
    }
    return response.json() as Promise<T>;
  } finally {
    clearTimeout(timer);
  }
}

async function apiGet<T>(path: string): Promise<T> {
  const headers: Record<string, string> = {};
  const token = getAccessToken();
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 10_000);
  try {
    const response = await fetch(`${API_BASE}${path}`, { headers, signal: controller.signal });
    clearTimeout(timer);
    if (!response.ok) {
      const errorBody = await response.json().catch(() => ({}));
      const message =
        (errorBody as { detail?: string }).detail ||
        (errorBody as { message?: string }).message ||
        `HTTP ${response.status}`;
      throw new Error(message);
    }
    return response.json() as Promise<T>;
  } finally {
    clearTimeout(timer);
  }
}

function persistTokens(access: string, refresh: string): void {
  inMemoryAccessToken = access;
  inMemoryRefreshToken = refresh;
  try {
    localStorage.setItem(STORAGE_KEY_ACCESS, access);
    localStorage.setItem(STORAGE_KEY_REFRESH, refresh);
  } catch {
    // localStorage 不可用时忽略
  }
}

function clearTokens(): void {
  inMemoryAccessToken = null;
  inMemoryRefreshToken = null;
  try {
    localStorage.removeItem(STORAGE_KEY_ACCESS);
    localStorage.removeItem(STORAGE_KEY_REFRESH);
  } catch {
    // ignore
  }
}

function getAccessToken(): string | null {
  if (inMemoryAccessToken) return inMemoryAccessToken;
  try {
    return localStorage.getItem(STORAGE_KEY_ACCESS);
  } catch {
    return null;
  }
}

function getRefreshToken(): string | null {
  if (inMemoryRefreshToken) return inMemoryRefreshToken;
  try {
    return localStorage.getItem(STORAGE_KEY_REFRESH);
  } catch {
    return null;
  }
}

export class AdminAuthService {
  private _currentUser: AdminUser | null = null;
  private _userType: string | null = null;

  async login(payload: LoginPayload): Promise<AdminTokens> {
    const tokens = await apiPost<AdminTokens>("/api/admin/auth/login", {
      username: payload.username,
      password: payload.password,
    });
    persistTokens(tokens.access_token, tokens.refresh_token || "");
    this._userType = tokens.user_type || null;
    return tokens;
  }

  async refresh(): Promise<boolean> {
    const refreshToken = this.getRefreshToken();
    if (!refreshToken) return false;

    try {
      const resp = await fetch(`${API_BASE}/api/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });
      if (!resp.ok) return false;
      const data = await resp.json();
      persistTokens(data.access_token, data.refresh_token || "");
      if (data.user_type) this._userType = data.user_type;
      return true;
    } catch {
      return false;
    }
  }

  async logout(): Promise<void> {
    try {
      await apiPost<unknown>("/api/auth/logout", {});
    } catch {
      // 即使登出接口失败，也要清理本地 token
    }
    clearTokens();
    this._currentUser = null;
  }

  async getMe(): Promise<AdminUser> {
    if (this._currentUser) return this._currentUser;
    const raw = await apiGet<RawAdminMeResponse & { user_type?: string; agency_id?: string; agency_name?: string; display_name?: string; email?: string }>("/api/admin/auth/me");
    const user: AdminUser = {
      id: raw.user_id ?? raw.id ?? "",
      username: raw.username,
      display_name: raw.display_name ?? raw.username,
      role: raw.role as AdminUser["role"],
      email: raw.email,
      user_type: raw.user_type as AdminUser["user_type"],
      agency_id: raw.agency_id,
      agency_name: raw.agency_name,
    };
    this._currentUser = user;
    return user;
  }

  async changePassword(payload: ChangePasswordPayload): Promise<void> {
    await apiPost<unknown>("/api/auth/change-password", payload);
  }

  isAuthenticated(): boolean {
    return getAccessToken() !== null;
  }

  getAccessToken(): string | null {
    return getAccessToken();
  }

  getCurrentUser(): AdminUser | null {
    return this._currentUser;
  }

  getUserType(): string | null {
    return this._userType;
  }

  getRefreshToken(): string | null {
    return getRefreshToken();
  }

  /** Set an external access token (used when agent/workspace reuses the admin ChatPage). */
  setAccessToken(token: string): void {
    persistTokens(token, '');
  }

  clearAuth(): void {
    clearTokens();
    this._currentUser = null;
    this._userType = null;
  }
}

export const adminAuth = new AdminAuthService();
import { resolveApiBaseUrl } from "./resolveApiBaseUrl";
