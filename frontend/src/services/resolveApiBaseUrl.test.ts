import { describe, expect, it } from "vitest";

import { resolveApiBaseUrl } from "./resolveApiBaseUrl";

describe("resolveApiBaseUrl", () => {
  it("prefers explicit VITE_API_BASE_URL when provided", () => {
    expect(resolveApiBaseUrl("https://api.example.com", true)).toBe("https://api.example.com");
  });

  it("uses same-origin requests in development when no explicit base URL is provided", () => {
    expect(resolveApiBaseUrl(undefined, true)).toBe("");
    expect(resolveApiBaseUrl("   ", true)).toBe("");
  });

  it("uses same-origin requests in production when no explicit base URL is provided", () => {
    expect(resolveApiBaseUrl(undefined, false)).toBe("");
    expect(resolveApiBaseUrl("   ", false)).toBe("");
  });
});
