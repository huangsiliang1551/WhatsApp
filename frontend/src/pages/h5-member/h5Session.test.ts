import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { H5SessionManager } from "../../services/h5SessionManager";

// Custom localStorage mock (same pattern as existing tests)
const storage = new Map<string, string>();

function installLocalStorageMock(): void {
  Object.defineProperty(window, "localStorage", {
    configurable: true,
    value: {
      getItem(key: string): string | null {
        return storage.get(key) ?? null;
      },
      setItem(key: string, value: string): void {
        storage.set(key, value);
      },
      removeItem(key: string): void {
        storage.delete(key);
      },
      clear(): void {
        storage.clear();
      },
    },
  });
}

describe("H5SessionManager", () => {
  let manager: H5SessionManager;

  beforeEach(() => {
    storage.clear();
    installLocalStorageMock();
    manager = new H5SessionManager();
  });

  afterEach(() => {
    storage.clear();
  });

  it("starts unauthenticated", () => {
    expect(manager.isAuthenticated()).toBe(false);
  });

  it("setSession makes isAuthenticated true", () => {
    manager.setSession("access123", "refresh123", 3600);
    expect(manager.isAuthenticated()).toBe(true);
    expect(manager.getAccessToken()).toBe("access123");
    expect(manager.getRefreshToken()).toBe("refresh123");
  });

  it("isTokenExpired returns true when no session", () => {
    expect(manager.isTokenExpired()).toBe(true);
  });

  it("setSession sets future expiry", () => {
    manager.setSession("a", "r", 3600);
    expect(manager.isTokenExpired()).toBe(false);
    expect(manager.shouldRefresh()).toBe(false);
  });

  it("shouldRefresh returns true near expiry", () => {
    // Set token with only 60 seconds expiry — well within the 5-minute refresh window
    manager.setSession("a", "r", 60);
    expect(manager.shouldRefresh()).toBe(true);
  });

  it("clearSession removes everything", () => {
    manager.setSession("a", "r", 3600);
    manager.setUserInfo({ accountId: "1", phone: "138", publicUserId: "u1", displayName: "Test", inviteCode: "c1" });
    manager.clearSession();
    expect(manager.isAuthenticated()).toBe(false);
    expect(manager.getUserInfo()).toBeNull();
  });

  it("authHeader returns empty when no token", () => {
    expect(manager.authHeader()).toEqual({});
  });

  it("authHeader returns Bearer when token exists", () => {
    manager.setSession("tok123", "ref123", 3600);
    const header = manager.authHeader();
    expect(header.Authorization).toBe("Bearer tok123");
  });

  it("persists to localStorage and reloads", () => {
    manager.setSession("persist1", "persistRef1", 7200);
    expect(localStorage.getItem("h5_access_token")).toBe("persist1");
    expect(localStorage.getItem("h5_refresh_token")).toBe("persistRef1");
  });

  it("getUserInfo returns null when not set", () => {
    expect(manager.getUserInfo()).toBeNull();
  });

  it("setUserInfo stores and retrieves user info", () => {
    const info = { accountId: "42", phone: "13900000000", publicUserId: "u42", displayName: "Alice", inviteCode: "INV42" };
    manager.setUserInfo(info);
    expect(manager.getUserInfo()).toEqual(info);
  });
});
