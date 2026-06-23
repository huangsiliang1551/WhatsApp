import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { useAsync } from "./useAsync";

function installLocalStorageMock(): void {
  const storage = new Map<string, string>();
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

describe("useAsync", () => {
  beforeEach(() => {
    installLocalStorageMock();
    window.localStorage.clear();
    window.localStorage.setItem("h5-lang", "en-US");
  });

  it("uses localized fallback copy for unknown async failures", async () => {
    const { result } = renderHook(() => useAsync(async () => Promise.reject("raw failure")));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.error).toBe("Error");
  });
});
