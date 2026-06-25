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

  it("exposes invite management as a standalone marketing destination", () => {
    const route = resolveConsoleRoute("/marketing/invites");

    expect(route.id).toBe("invite_management");
    expect(route.visibleInNav).toBe(true);
    expect(groupedConsoleRoutes.content.some((candidate) => candidate.id === "invite_management")).toBe(true);
    expect(primaryConsoleRoutes.some((candidate) => candidate.path === "/marketing/invites")).toBe(true);
  });

  it("exposes invite relations and rewards as standalone marketing destinations", () => {
    expect(resolveConsoleRoute("/marketing/invite-relations").id).toBe("invite_relations");
    expect(resolveConsoleRoute("/marketing/invite-rewards").id).toBe("invite_rewards");
    expect(groupedConsoleRoutes.content.some((candidate) => candidate.id === "invite_relations")).toBe(true);
    expect(groupedConsoleRoutes.content.some((candidate) => candidate.id === "invite_rewards")).toBe(true);
  });
});
