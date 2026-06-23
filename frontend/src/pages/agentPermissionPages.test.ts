import { describe, expect, it } from "vitest";

import agentDetailPageSource from "./AgentDetailPage.tsx?raw";
import agentsPageSource from "./AgentsPage.tsx?raw";

describe("agent permission workbench pages", () => {
  it("does not reintroduce static permission templates or modules into the shared AgentsPage workbench", () => {
    expect(agentsPageSource).not.toContain("PERMISSION_TEMPLATES");
    expect(agentsPageSource).not.toContain("PERMISSION_MODULES");
  });

  it("does not reintroduce static permission templates or modules into the shared AgentDetailPage workbench", () => {
    expect(agentDetailPageSource).not.toContain("PERMISSION_TEMPLATES");
    expect(agentDetailPageSource).not.toContain("PERMISSION_MODULES");
  });

  it("keeps free-text custom role assignment out of the shared AgentsPage workbench", () => {
    expect(agentsPageSource).not.toContain("customRoleName");
    expect(agentsPageSource).not.toContain("__custom__");
  });

  it("keeps free-text custom role assignment out of the shared AgentDetailPage workbench", () => {
    expect(agentDetailPageSource).not.toContain("customRoleName");
    expect(agentDetailPageSource).not.toContain("__custom__");
  });
});
