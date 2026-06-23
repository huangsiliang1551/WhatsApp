import { describe, expect, it } from "vitest";

import { groupedConsoleRoutes, primaryConsoleRoutes, resolveConsoleRoute } from "./consoleRoutes";

describe("consoleRoutes", () => {
  it("keeps agents under the people group navigation", () => {
    expect(groupedConsoleRoutes.people.some((route) => route.id === "agents")).toBe(true);
    expect(groupedConsoleRoutes.settings.some((route) => route.id === "agents")).toBe(false);
  });

  it("keeps /system/roles as a hidden compatibility entry instead of a primary navigation destination", () => {
    const route = resolveConsoleRoute("/system/roles");

    expect(route.id).toBe("agents");
    expect(route.hideInMenu).toBe(true);
    expect(route.visibleInNav).toBe(false);
    expect(groupedConsoleRoutes.people.some((candidate) => candidate.id === "agents")).toBe(true);
    expect(primaryConsoleRoutes.some((candidate) => candidate.path === "/system/roles")).toBe(false);
  });

  it("removes the H5 template market from primary console navigation", () => {
    expect(primaryConsoleRoutes.some((route) => route.path === "/system/h5-templates")).toBe(false);
    expect(groupedConsoleRoutes.settings.some((route) => route.path === "/system/h5-templates")).toBe(false);
    expect(resolveConsoleRoute("/system/h5-templates").id).toBe("dashboard");
  });
});
