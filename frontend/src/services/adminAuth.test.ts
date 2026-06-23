import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

// 模拟 localStorage
const localStorageStore: Record<string, string> = {};
vi.stubGlobal("localStorage", {
  getItem: vi.fn((key: string) => localStorageStore[key] ?? null),
  setItem: vi.fn((key: string, value: string) => { localStorageStore[key] = value; }),
  removeItem: vi.fn((key: string) => { delete localStorageStore[key]; }),
  clear: vi.fn(() => { Object.keys(localStorageStore).forEach((k) => delete localStorageStore[k]); }),
  get length() { return Object.keys(localStorageStore).length; },
  key: vi.fn((index: number) => Object.keys(localStorageStore)[index] ?? null),
});

// 在每个测试前清除缓存模块，确保 adminAuth 重新加载
function resetModule(): void {
  vi.resetModules();
}

describe("adminAuth service", () => {
  let adminAuthModule: typeof import("./adminAuth");
  let adminAuth: import("./adminAuth").AdminAuthService;

  beforeEach(async () => {
    resetModule();
    localStorageStore["admin_access_token"] = "existing-token";
    localStorageStore["admin_refresh_token"] = "existing-refresh";
    adminAuthModule = await import("./adminAuth");
    adminAuth = adminAuthModule.adminAuth;
  });

  afterEach(() => {
    vi.restoreAllMocks();
    Object.keys(localStorageStore).forEach((k) => delete localStorageStore[k]);
  });

  describe("isAuthenticated", () => {
    it("returns true when access token exists", () => {
      expect(adminAuth.isAuthenticated()).toBe(true);
    });

    it("returns false when no access token", () => {
      delete localStorageStore["admin_access_token"];
      // 创建新实例以反映空状态
      expect(adminAuth.isAuthenticated()).toBe(false);
    });
  });

  describe("getAccessToken", () => {
    it("returns token from localStorage", () => {
      const token = adminAuth.getAccessToken();
      expect(token).toBe("existing-token");
    });
  });

  describe("login", () => {
    it("makes POST request to /api/admin/auth/login", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ access_token: "new-token", refresh_token: "new-refresh" }),
      });

      const tokens = await adminAuth.login({ username: "admin", password: "pass" });
      expect(tokens.access_token).toBe("new-token");
      expect(tokens.refresh_token).toBe("new-refresh");
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/admin/auth/login"),
        expect.objectContaining({ method: "POST" })
      );
    });

    it("throws error on failed login", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 401,
        json: async () => ({ detail: "用户名或密码错误" }),
      });

      await expect(adminAuth.login({ username: "admin", password: "wrong" })).rejects.toThrow("用户名或密码错误");
    });

    it("stores token in memory after login", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ access_token: "memory-token", refresh_token: "memory-refresh" }),
      });

      await adminAuth.login({ username: "admin", password: "pass", remember: false });
      expect(adminAuth.getAccessToken()).toBe("memory-token");
    });
  });

  describe("refresh", () => {
    it("refreshes token successfully", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ access_token: "refreshed-token", refresh_token: "refreshed-refresh" }),
      });

      const result = await adminAuth.refresh();
      expect(result).toBe(true);
      expect(adminAuth.getAccessToken()).toBe("refreshed-token");
    });

    it("returns false when no refresh token available", async () => {
      delete localStorageStore["admin_refresh_token"];
      const result = await adminAuth.refresh();
      expect(result).toBe(false);
    });
  });

  describe("logout", () => {
    it("clears tokens on logout", async () => {
      mockFetch.mockResolvedValueOnce({ ok: true, json: async () => ({}) });

      await adminAuth.logout();
      expect(adminAuth.getAccessToken()).toBeNull();
    });

    it("clears tokens even if API call fails", async () => {
      mockFetch.mockRejectedValueOnce(new Error("Network error"));

      await adminAuth.logout();
      expect(adminAuth.getAccessToken()).toBeNull();
    });
  });

  describe("getMe", () => {
    it("fetches user info", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ id: "user-1", username: "admin", display_name: "管理员", role: "admin" }),
      });

      const user = await adminAuth.getMe();
      expect(user.id).toBe("user-1");
      expect(user.display_name).toBe("管理员");
    });
  });

  describe("changePassword", () => {
    it("calls change password API", async () => {
      mockFetch.mockResolvedValueOnce({ ok: true, json: async () => ({}) });

      await expect(adminAuth.changePassword({ old_password: "old", new_password: "new" })).resolves.toBeUndefined();
    });
  });

  describe("clearAuth", () => {
    it("clears all auth state", () => {
      adminAuth.clearAuth();
      expect(adminAuth.getAccessToken()).toBeNull();
    });
  });
});
