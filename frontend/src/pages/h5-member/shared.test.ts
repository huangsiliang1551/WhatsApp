import { beforeEach, describe, expect, it } from "vitest";

import { getRouteSubtitle, getRouteTitle } from "./shared";
import { getCurrentLocale } from "./sharedUtils";

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

describe("getRouteSubtitle", () => {
  beforeEach(() => {
    installLocalStorageMock();
    window.localStorage.clear();
    document.documentElement.lang = "";
  });

  it("keeps the site tagline on the home route when one is available", () => {
    window.localStorage.setItem("h5-lang", "en-US");

    expect(
      getRouteSubtitle(
        { page: "home" },
        { tagline: "Daily rewards from your active task queue.", brandName: "Member Rewards Center" },
      ),
    ).toBe("Daily rewards from your active task queue.");
  });

  it("uses a task-and-earn default subtitle on home when no site tagline is provided", () => {
    window.localStorage.setItem("h5-lang", "en-US");

    expect(getRouteSubtitle({ page: "home" }, { brandName: "Member Rewards Center" })).toBe(
      "Start a task, track today's earnings, and withdraw with confidence.",
    );
  });

  it("falls back to the default home subtitle when the site tagline is still the deprecated portal copy", () => {
    window.localStorage.setItem("h5-lang", "en-US");

    expect(
      getRouteSubtitle(
        { page: "home" },
        { tagline: "Task packages, wallet, support, and fragments in one place.", brandName: "Member Rewards Center" },
      ),
    ).toBe("Start a task, track today's earnings, and withdraw with confidence.");
  });

  it("returns route-specific subtitles for key secondary pages instead of falling back to the brand name", () => {
    window.localStorage.setItem("h5-lang", "en-US");

    expect(getRouteSubtitle({ page: "orders" }, { brandName: "Member Rewards Center" })).toBe("Recent orders and payments");
    expect(getRouteSubtitle({ page: "tickets" }, { brandName: "Member Rewards Center" })).toBe("Support requests and replies");
    expect(getRouteSubtitle({ page: "fragments" }, { brandName: "Member Rewards Center" })).toBe("Fragment progress and reward shipping");
    expect(getRouteSubtitle({ page: "leaderboard" }, { brandName: "Member Rewards Center" })).toBe("Top withdrawal rankings");
    expect(getRouteSubtitle({ page: "whatsapp" }, { brandName: "Member Rewards Center" })).toBe("Binding status and chat updates");
    expect(getRouteSubtitle({ page: "invite" }, { brandName: "Member Rewards Center" })).toBe("Invite rewards and share link");
  });

  it("returns the dedicated invite title instead of falling back to login", () => {
    window.localStorage.setItem("h5-lang", "en-US");

    expect(getRouteTitle({ page: "invite" })).toBe("Invite Friends");
  });

  it("defaults to chinese locale when no explicit h5 language preference is stored", () => {
    Object.defineProperty(window.navigator, "language", {
      configurable: true,
      value: "en-US",
    });
    document.documentElement.lang = "en-US";

    expect(getCurrentLocale()).toBe("zh-CN");
  });
});
