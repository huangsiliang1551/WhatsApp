import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  buildRoleCenterPath,
  openRoleCenter,
  readRoleCenterQuery,
  syncRoleCenterLocation,
} from "./roleCenterUrlState";

describe("roleCenterUrlState", () => {
  beforeEach(() => {
    window.history.replaceState({}, "", "/system/agents");
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("builds a role center path from agencyId and role", () => {
    expect(buildRoleCenterPath("agency-1", "agent")).toBe("/system/agents?agencyId=agency-1&tab=roles&role=agent");
    expect(buildRoleCenterPath("agency-1")).toBe("/system/agents?agencyId=agency-1&tab=roles");
  });

  it("reads agencyId and role from a query string", () => {
    expect(readRoleCenterQuery("?agencyId=agency-1&role=agent")).toEqual({
      agencyId: "agency-1",
      role: "agent",
    });
  });

  it("syncs role center query params onto the current pathname", () => {
    window.history.replaceState({}, "", "/system/agents?agencyId=old&tab=members&role=old_role");

    syncRoleCenterLocation("agency-2", "support");

    expect(window.location.pathname + window.location.search).toBe("/system/agents?agencyId=agency-2&tab=roles&role=support");
  });

  it("pushes the role center path and dispatches popstate when opening", () => {
    const popStateSpy = vi.spyOn(window, "dispatchEvent");

    openRoleCenter("agency-9", "manager");

    expect(window.location.pathname + window.location.search).toBe("/system/agents?agencyId=agency-9&tab=roles&role=manager");
    expect(popStateSpy).toHaveBeenCalledWith(expect.any(PopStateEvent));
  });
});
