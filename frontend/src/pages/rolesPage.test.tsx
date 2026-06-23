import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { RolesPage } from "./RolesPage";

describe("RolesPage legacy compatibility entry", () => {
  beforeEach(() => {
    window.history.replaceState({}, "", "/system/roles");
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("shows the compatibility notice before redirecting into the single workbench roles entry", async () => {
    const popStateSpy = vi.spyOn(window, "dispatchEvent");
    window.history.replaceState({}, "", "/system/roles?agencyId=agency-77&role=agent");

    render(<RolesPage />);

    expect(screen.getByText("角色权限兼容入口")).toBeTruthy();
    expect(screen.getByText("旧版 /system/roles 已并入代理商管理工作台。")).toBeTruthy();
    expect(screen.getByText("正在跳转到代理商管理工作台的角色视图...")).toBeTruthy();

    await waitFor(() => {
      expect(window.location.pathname + window.location.search).toBe(
        "/system/agents?agencyId=agency-77&tab=roles&role=agent"
      );
    });

    expect(popStateSpy).toHaveBeenCalledWith(expect.any(PopStateEvent));
  });

  it("keeps the legacy entry routable when only the agency scope is present", async () => {
    window.history.replaceState({}, "", "/system/roles?agencyId=agency-88");

    render(<RolesPage />);

    await waitFor(() => {
      expect(window.location.pathname + window.location.search).toBe(
        "/system/agents?agencyId=agency-88&tab=roles"
      );
    });
  });
});
