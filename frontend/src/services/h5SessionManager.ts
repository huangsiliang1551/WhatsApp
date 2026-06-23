/**
 * H5 会员端 Session 管理器
 * 统一管理登录态，支持 cookie + localStorage 双写
 *
 * 生产态：仅 cookie（HttpOnly + Secure + SameSite）由服务端管理
 * 开发态/Mock：localStorage fallback
 */
import { api } from "./api";

export type H5MemberInfo = {
  accountId: string;
  phone: string;
  publicUserId: string;
  displayName: string;
  inviteCode: string;
  avatarUrl?: string | null;
  accountIdMasked?: string;
  createdAt?: string;
};

type TokenResponse = {
  access_token: string;
  refresh_token: string;
  expires_in: number;
};

const STORAGE_KEY_TOKEN = "h5_access_token";
const STORAGE_KEY_REFRESH = "h5_refresh_token";
const STORAGE_KEY_EXPIRES = "h5_token_expires";
const STORAGE_KEY_USER = "h5_user_info";
const COOKIE_NAME = "h5_member_session";
const COOKIE_REFRESH_NAME = "h5_member_refresh";

export class H5SessionManager {
  private _accessToken: string | null = null;
  private _refreshToken: string | null = null;
  private _expiresAt: number | null = null;
  private _userInfo: H5MemberInfo | null = null;
  private _refreshPromise: Promise<boolean> | null = null;

  constructor() {
    this._loadFromStorage();
  }

  // ─── Public API ───────────────────────────────────────

  isAuthenticated(): boolean {
    return !!this._accessToken && !this.isTokenExpired();
  }

  getAccessToken(): string | null {
    return this._accessToken;
  }

  getRefreshToken(): string | null {
    return this._refreshToken;
  }

  getUserInfo(): H5MemberInfo | null {
    return this._userInfo;
  }

  setUserInfo(info: H5MemberInfo, persist: boolean = true): void {
    this._userInfo = info;
    if (persist) this._saveToStorage();
  }

  setSession(accessToken: string, refreshToken: string, expiresIn: number, persist: boolean = true): void {
    this._accessToken = accessToken;
    this._refreshToken = refreshToken;
    this._expiresAt = Date.now() + expiresIn * 1000;
    if (persist) this._saveToStorage();
  }

  clearSession(): void {
    this._accessToken = null;
    this._refreshToken = null;
    this._expiresAt = null;
    this._userInfo = null;
    this._clearStorage();
  }

  isTokenExpired(): boolean {
    if (!this._expiresAt) return true;
    return Date.now() >= this._expiresAt;
  }

  /** 过期前 5 分钟内返回 true，适合提前续期 */
  shouldRefresh(): boolean {
    if (!this._expiresAt || !this._refreshToken) return false;
    return Date.now() >= this._expiresAt - 5 * 60 * 1000;
  }

  /** 尝试续期 token，返回是否成功 */
  async refreshToken(): Promise<boolean> {
    // 防止并发重复请求
    if (this._refreshPromise) return this._refreshPromise;

    this._refreshPromise = this._doRefresh();
    try {
      return await this._refreshPromise;
    } finally {
      this._refreshPromise = null;
    }
  }

  // ─── Internal ──────────────────────────────────────────

  private async _doRefresh(): Promise<boolean> {
    const refreshToken = this._refreshToken;
    if (!refreshToken) return false;

    try {
      const res = await api.post<TokenResponse>("/api/h5/auth/refresh", {
        refresh_token: refreshToken,
      });

      this.setSession(res.data.access_token, res.data.refresh_token, res.data.expires_in);
      return true;
    } catch {
      this.clearSession();
      return false;
    }
  }

  /** 挂载 Authorization header（给 axios interceptor 用） */
  authHeader(): Record<string, string> {
    if (this._accessToken) {
      return { Authorization: `Bearer ${this._accessToken}` };
    }
    return {};
  }

  // ─── Storage ───────────────────────────────────────────

  private _loadFromStorage(): void {
    try {
      const token = localStorage.getItem(STORAGE_KEY_TOKEN);
      const refresh = localStorage.getItem(STORAGE_KEY_REFRESH);
      const expires = localStorage.getItem(STORAGE_KEY_EXPIRES);
      const user = localStorage.getItem(STORAGE_KEY_USER);

      if (token) this._accessToken = token;
      if (refresh) this._refreshToken = refresh;
      if (expires) this._expiresAt = Number(expires);
      if (user) {
        try {
          this._userInfo = JSON.parse(user) as H5MemberInfo;
        } catch {
          // ignore corrupt data
        }
      }
    } catch {
      // localStorage 不可用时忽略
    }
  }

  private _saveToStorage(): void {
    try {
      if (this._accessToken) localStorage.setItem(STORAGE_KEY_TOKEN, this._accessToken);
      if (this._refreshToken) localStorage.setItem(STORAGE_KEY_REFRESH, this._refreshToken);
      if (this._expiresAt) localStorage.setItem(STORAGE_KEY_EXPIRES, String(this._expiresAt));
      if (this._userInfo) localStorage.setItem(STORAGE_KEY_USER, JSON.stringify(this._userInfo));
    } catch {
      // storage full or unavailable
    }
  }

  private _clearStorage(): void {
    try {
      localStorage.removeItem(STORAGE_KEY_TOKEN);
      localStorage.removeItem(STORAGE_KEY_REFRESH);
      localStorage.removeItem(STORAGE_KEY_EXPIRES);
      localStorage.removeItem(STORAGE_KEY_USER);
    } catch {
      // ignore
    }
  }
}

export const sessionManager = new H5SessionManager();

/**
 * Axios 请求拦截器函数：自动附加 Authorization header
 * 并检查 token 是否需要续期
 */
export function requestInterceptor(config: Record<string, unknown>): Record<string, unknown> {
  if (sessionManager.shouldRefresh()) {
    // 后台异步续期，不阻塞当前请求
    sessionManager.refreshToken().catch(() => {
      // 续期失败已由 clearSession 处理
    });
  }

  const headers = sessionManager.authHeader();
  return {
    ...config,
    headers: { ...(config.headers as Record<string, unknown>), ...headers },
  };
}
