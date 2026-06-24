import { describe, expect, it } from "vitest";

import { shouldServeH5AppShell } from "./spaFallback";

describe("shouldServeH5AppShell", () => {
  it("serves the app shell for H5 deep links in dev", () => {
    expect(
      shouldServeH5AppShell({
        method: "GET",
        pathname: "/h5/tasks",
      }),
    ).toBe(true);
    expect(
      shouldServeH5AppShell({
        method: "GET",
        pathname: "/h5/tasks/package/pkg-1",
      }),
    ).toBe(true);
  });

  it("does not intercept api or asset requests", () => {
    expect(
      shouldServeH5AppShell({
        method: "GET",
        pathname: "/api/h5/sites/mall-cn/brand-config",
      }),
    ).toBe(false);
    expect(
      shouldServeH5AppShell({
        method: "GET",
        pathname: "/src/main.tsx",
      }),
    ).toBe(false);
    expect(
      shouldServeH5AppShell({
        method: "GET",
        pathname: "/assets/app.js",
      }),
    ).toBe(false);
  });

  it("ignores non-navigation methods and unrelated routes", () => {
    expect(
      shouldServeH5AppShell({
        method: "POST",
        pathname: "/h5/tasks",
      }),
    ).toBe(false);
    expect(
      shouldServeH5AppShell({
        method: "GET",
        pathname: "/system/dashboard",
      }),
    ).toBe(false);
  });
});
