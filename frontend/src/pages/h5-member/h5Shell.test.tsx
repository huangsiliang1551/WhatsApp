import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { t } from "./i18n";
import type { H5PageShellProps } from "./H5PageShell";

const storage = new Map<string, string>();

function installLocalStorageMock(): void {
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

function createShellProps(overrides: Partial<H5PageShellProps> = {}): H5PageShellProps {
  return {
    children: <section>content</section>,
    route: { page: "home", siteKey: "mall-cn" } as any,
    navigate: vi.fn(),
    loading: false,
    toastItems: [],
    session: {
      memberId: "member-1",
      accountId: "acct-10001",
      phone: "13800000000",
      displayName: "Demo",
      siteKey: "mall-cn",
    } as any,
    memberPhoneMasked: "138****0000",
    dashboard: {
      site: {
        site_key: "mall-cn",
        brand_name: "Mall",
        tagline: "tagline",
        accent_color: "#1677ff",
      },
      member: {
        accountId: "38271456",
        accountIdMasked: "38****56",
        phone: "13800000000",
        publicUserId: "h5-38271456",
        displayName: "Demo Member",
        inviteCode: "INV-ABCD1234",
        createdAt: "2026-06-20T00:00:00.000Z",
      },
      wallet: {
        currency: "USD",
        systemBalance: 120,
        taskBalance: 36,
        withdrawThreshold: 100,
        shortfallAmount: 0,
        canWithdraw: true,
      },
      unreadCount: 2,
      pendingClaimCount: 1,
      activeCount: 1,
      expiringCount: 0,
      recentMessages: [],
      leaderboard: [],
      verification: {
        currentStatus: "approved",
        hasActiveRequest: false,
      },
      fragments: {
        totalCount: 3,
        completedCount: 1,
        missingCount: 2,
        canExchange: false,
        shippingOrderCount: 0,
        latestShippingStatus: null,
        rewardName: null,
      },
    } as any,
    actionName: null,
    unreadMessageCount: 3,
    primaryTabId: "home",
    secondaryBackPath: "/h5/me?site_key=mall-cn",
    topbarSubtitle: "subtitle",
    effectiveWalletSummary: {
      currency: "USD",
      systemBalance: 120,
      taskBalance: 36,
      withdrawThreshold: 100,
      shortfallAmount: 0,
      canWithdraw: true,
    } as any,
    rechargeAmount: "100",
    transferAllAmount: 36,
    claimDialogPackage: null,
    showRechargeChannels: false,
    showTransferAllConfirm: false,
    onMarkAllMessagesRead: vi.fn(),
    onRecharge: vi.fn(),
    onClaimTaskPackage: vi.fn(),
    onCloseClaimDialog: vi.fn(),
    onTransferAllTaskBalance: vi.fn(),
    onSetShowRechargeChannels: vi.fn(),
    onSetShowTransferAllConfirm: vi.fn(),
    ...overrides,
  };
}

describe("H5PageShell", () => {
  beforeEach(() => {
    storage.clear();
    installLocalStorageMock();
  });

  afterEach(() => {
    cleanup();
    storage.clear();
  });

  it("renders tabbar as home tasks earnings me", async () => {
    const { H5PageShell: Shell } = await import("./H5PageShell");
    render(<Shell {...createShellProps()} />);

    expect(screen.getByRole("button", { name: new RegExp(t("shell.tabHome")) })).toBeTruthy();
    expect(screen.getByRole("button", { name: new RegExp(t("shell.tabTasks")) })).toBeTruthy();
    expect(screen.getByRole("button", { name: new RegExp(t("shell.tabEarnings")) })).toBeTruthy();
    expect(screen.getByRole("button", { name: new RegExp(t("shell.tabProfile")) })).toBeTruthy();
    expect(screen.queryByRole("button", { name: new RegExp(t("shell.tabMessages")) })).toBeNull();
  });

  it("highlights the active tab and navigates to the target route on click", async () => {
    const navigate = vi.fn();
    const { H5PageShell: Shell } = await import("./H5PageShell");
    render(
      <Shell
        {...createShellProps({
          navigate,
          primaryTabId: "earnings",
        })}
      />,
    );

    const earningsButton = screen.getByRole("button", { name: new RegExp(t("shell.tabEarnings")) });
    expect(earningsButton.className).toContain("h5-member-tabbar-item-active");

    fireEvent.click(screen.getByRole("button", { name: new RegExp(t("shell.tabTasks")) }));
    expect(navigate).toHaveBeenCalledWith("/h5/tasks?site_key=mall-cn");
  });

  it("syncs the selected locale to the document language and direction", async () => {
    storage.set("h5-lang", "ar");
    document.documentElement.lang = "";
    document.documentElement.dir = "";

    const { H5PageShell: Shell } = await import("./H5PageShell");
    render(<Shell {...createShellProps()} />);

    expect(document.documentElement.lang).toBe("ar");
    expect(document.documentElement.dir).toBe("rtl");
  });

  it("keeps a single topbar mark-all-read action on the messages route", async () => {
    const onMarkAllMessagesRead = vi.fn();
    const { H5PageShell: Shell } = await import("./H5PageShell");

    render(
      <Shell
        {...createShellProps({
          route: { page: "messages", siteKey: "mall-cn" } as any,
          secondaryBackPath: "/h5/home?site_key=mall-cn",
          topbarSubtitle: "Updates, reminders, and support replies",
          unreadMessageCount: 2,
          onMarkAllMessagesRead,
        })}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /Mark All Read/i }));
    expect(onMarkAllMessagesRead).toHaveBeenCalledTimes(1);
    expect(screen.getAllByRole("button", { name: /Mark All Read/i })).toHaveLength(1);
  });

  it("renders the home topbar as an account status layer instead of a generic brand banner", async () => {
    const navigate = vi.fn();
    const { H5PageShell: Shell } = await import("./H5PageShell");

    render(
      <Shell
        {...createShellProps({
          navigate,
          route: { page: "home", siteKey: "mall-cn" } as any,
          dashboard: {
            ...createShellProps().dashboard,
            site: {
              site_key: "mall-cn",
              brand_name: "Mall",
              tagline: "tagline",
              accent_color: "#1677ff",
            },
            member: {
              ...createShellProps().dashboard?.member,
              displayName: "Demo Member",
            },
            verification: {
              currentStatus: "approved",
              hasActiveRequest: false,
            },
          } as any,
        })}
      />,
    );

    expect(screen.getByText("Demo Member")).toBeTruthy();
    expect(screen.getByText(/38\*{4}56/)).toBeTruthy();
    expect(screen.getByRole("button", { name: /approved/i })).toBeTruthy();
    expect(screen.queryByText("Mall")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: /approved/i }));
    expect(navigate).toHaveBeenCalledWith("/h5/verification?site_key=mall-cn");
  });

  it("keeps root scrolling locked and uses the h5 shell as the only scroll container", async () => {
    document.documentElement.style.overflow = "hidden";
    document.documentElement.style.overflowY = "hidden";
    document.body.style.overflow = "hidden";
    document.body.style.overflowY = "hidden";

    const { H5PageShell: Shell } = await import("./H5PageShell");
    const view = render(<Shell {...createShellProps()} />);
    const main = screen.getByRole("main");

    expect(document.documentElement.style.overflow).toBe("hidden");
    expect(document.documentElement.style.overflowY).toBe("hidden");
    expect(document.body.style.overflow).toBe("hidden");
    expect(document.body.style.overflowY).toBe("hidden");
    expect(main.style.height).toBe("var(--h5-visual-viewport-height, 100dvh)");
    expect(main.style.overflowY).toBe("auto");
    expect(main.style.touchAction).toBe("pan-y");
    expect(main.style.webkitOverflowScrolling).toBe("touch");

    view.unmount();

    expect(document.documentElement.style.overflow).toBe("hidden");
    expect(document.documentElement.style.overflowY).toBe("hidden");
    expect(document.body.style.overflow).toBe("hidden");
    expect(document.body.style.overflowY).toBe("hidden");
  });

  it("syncs the scroll shell height with visualViewport when mobile browsers report a reduced keyboard viewport", async () => {
    const addEventListener = vi.fn();
    const removeEventListener = vi.fn();

    Object.defineProperty(window, "visualViewport", {
      configurable: true,
      value: {
        height: 612,
        addEventListener,
        removeEventListener,
      },
    });

    const { H5PageShell: Shell } = await import("./H5PageShell");
    const view = render(<Shell {...createShellProps()} />);

    expect(document.documentElement.style.getPropertyValue("--h5-visual-viewport-height")).toBe("612px");
    expect(addEventListener).toHaveBeenCalledWith("resize", expect.any(Function));
    expect(addEventListener).toHaveBeenCalledWith("scroll", expect.any(Function));

    view.unmount();

    expect(removeEventListener).toHaveBeenCalledWith("resize", expect.any(Function));
    expect(removeEventListener).toHaveBeenCalledWith("scroll", expect.any(Function));
  });

  it("keeps full home identity titles accessible for long localized member names", async () => {
    const { H5PageShell: Shell } = await import("./H5PageShell");
    render(
      <Shell
        {...createShellProps({
          session: {
            ...createShellProps().session,
            displayName: "International Growth Rewards Center with Extended Localized Name",
          } as any,
          dashboard: {
            ...createShellProps().dashboard,
            member: {
              ...createShellProps().dashboard?.member,
              displayName: "International Growth Rewards Center with Extended Localized Name",
            },
          } as any,
        })}
      />,
    );

    expect(
      screen.getByTitle("International Growth Rewards Center with Extended Localized Name"),
    ).toBeTruthy();
  });

  it("uses the compact toast layout on primary tab routes", async () => {
    const { H5PageShell: Shell } = await import("./H5PageShell");
    render(
      <Shell
        {...createShellProps({
          toastItems: [{ key: "notice", message: "Saved", tone: "notice", duration: 2600 }],
          route: { page: "home", siteKey: "mall-cn" } as any,
        })}
      />,
    );

    const status = document.querySelector(".h5-member-toast-stack") as HTMLElement | null;
    expect(status?.className).toContain("h5-member-toast-stack-compact");
    expect(document.querySelector(".h5-member-toast-compact")).toBeTruthy();
  });

  it("renders recharge channel guidance without demo wording in english", async () => {
    storage.set("h5-lang", "en-US");
    const { H5PageShell: Shell } = await import("./H5PageShell");

    render(
      <Shell
        {...createShellProps({
          showRechargeChannels: true,
          session: {
            ...createShellProps().session,
            displayName: "Member",
          } as any,
          dashboard: {
            ...createShellProps().dashboard,
            member: {
              ...createShellProps().dashboard?.member,
              displayName: "Member",
            },
          } as any,
        })}
      />,
    );

    expect(document.body.textContent?.toLowerCase()).not.toContain("demo");
  });

  it("marks the whatsapp route content region as chat mode so the inner page can stretch to the remaining viewport", async () => {
    const { H5PageShell: Shell } = await import("./H5PageShell");

    render(
      <Shell
        {...createShellProps({
          route: { page: "whatsapp", siteKey: "mall-cn" } as any,
          primaryTabId: "profile",
          secondaryBackPath: "/h5/me?site_key=mall-cn",
          children: <div className="h5-chat-container">chat</div>,
        })}
      />,
    );

    const content = document.querySelector(".h5-member-content") as HTMLElement;
    expect(content.className).toContain("h5-member-content-chat");
  });
});
