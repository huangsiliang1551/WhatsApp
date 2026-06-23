import { act, cleanup, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { canSeePageWithMenus, usePermissions } from "./usePermissions";

const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

const getAccessTokenMock = vi.fn();
const getCurrentUserMock = vi.fn();
const getMeMock = vi.fn();

vi.mock("../services/adminAuth", () => ({
  adminAuth: {
    getAccessToken: () => getAccessTokenMock(),
    getCurrentUser: () => getCurrentUserMock(),
    getMe: () => getMeMock(),
  },
}));

describe("usePermissions", () => {
  beforeEach(() => {
    mockFetch.mockReset();
    getAccessTokenMock.mockReset().mockReturnValue("token-1");
    getCurrentUserMock.mockReset().mockReturnValue({
      role: "agent",
      agency_id: "agency-1",
    });
    getMeMock.mockReset().mockResolvedValue({ agency_id: "agency-1" });
  });

  afterEach(() => {
    vi.clearAllMocks();
    cleanup();
  });

  it("requires exact canonical menu ids", () => {
    expect(canSeePageWithMenus(["members"], "members")).toBe(true);
    expect(canSeePageWithMenus(["member_access"], "members")).toBe(false);
    expect(canSeePageWithMenus(["security_settings"], "access_control")).toBe(false);
  });

  it("loads canonical permissions and menus from the backend", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        user_type: "agent",
        role: "agent",
        agency_id: "agency-1",
        agency_name: "Agency One",
        menus: ["agents", "tickets"],
        permissions: ["roles.view", "roles.edit_perms"],
      }),
    });

    const { result } = renderHook(() => usePermissions());

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.perms).toMatchObject({
      user_type: "agent",
      agency_id: "agency-1",
      menus: ["agents", "tickets"],
      permissions: ["roles.view", "roles.edit_perms"],
    });
    expect(result.current.can("roles.view")).toBe(true);
    expect(result.current.can("roles.delete")).toBe(false);
    expect(result.current.canSeePage("agents")).toBe(true);
    expect(result.current.canSeePage("security")).toBe(false);
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/auth/permissions"),
      expect.objectContaining({
        headers: { Authorization: "Bearer token-1" },
      }),
    );
  });

  it("falls back to empty canonical permissions when the backend request fails", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 403,
    });

    const { result } = renderHook(() => usePermissions());

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.perms).toMatchObject({
      user_type: "agent",
      role: "agent",
      agency_id: "agency-1",
      permissions: [],
      menus: [],
    });
    expect(result.current.can("roles.view")).toBe(false);
    expect(result.current.canSeePage("agents")).toBe(false);
  });

  it("does not call the backend when there is no token", async () => {
    getAccessTokenMock.mockReturnValueOnce(null);

    const { result } = renderHook(() => usePermissions());

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(mockFetch).not.toHaveBeenCalled();
    expect(result.current.perms).toMatchObject({
      user_type: "agent",
      permissions: [],
      menus: [],
    });
  });

  it("reloads permissions on popstate", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        user_type: "agent",
        role: "agent",
        agency_id: "agency-1",
        agency_name: "Agency One",
        menus: ["tickets"],
        permissions: ["tickets.view"],
      }),
    });

    const { result } = renderHook(() => usePermissions());

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.canSeePage("tickets")).toBe(true);

    mockFetch.mockReset();
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        user_type: "agent",
        role: "agent",
        agency_id: "agency-1",
        agency_name: "Agency One",
        menus: ["agents"],
        permissions: ["roles.view"],
      }),
    });

    await act(async () => {
      window.dispatchEvent(new PopStateEvent("popstate"));
    });

    await waitFor(() => expect(result.current.can("roles.view")).toBe(true));
    expect(result.current.canSeePage("agents")).toBe(true);
    expect(result.current.canSeePage("tickets")).toBe(false);
    expect(mockFetch).toHaveBeenCalledTimes(1);
  });
});
