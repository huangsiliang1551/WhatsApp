import { describe, expect, it } from "vitest";

import { resolveH5ApiBaseUrl } from "./h5Member";

describe("resolveH5ApiBaseUrl", () => {
  it("prefers explicit VITE_API_BASE_URL when provided", () => {
    expect(resolveH5ApiBaseUrl("https://api.example.com", false)).toBe("https://api.example.com");
  });

  it("uses same-origin requests in development when no explicit base URL is provided", () => {
    expect(resolveH5ApiBaseUrl(undefined, true)).toBe("");
    expect(resolveH5ApiBaseUrl("   ", true)).toBe("");
  });

  it("uses same-origin requests in production when no explicit base URL is provided", () => {
    expect(resolveH5ApiBaseUrl(undefined, false)).toBe("");
    expect(resolveH5ApiBaseUrl("   ", false)).toBe("");
  });
});
