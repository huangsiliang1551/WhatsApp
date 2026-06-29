import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { readFileSync } from "node:fs";
import { t } from "./i18n";

// Custom localStorage mock (same pattern as existing tests)
const storage = new Map<string, string>();
const originalXmlHttpRequest = globalThis.XMLHttpRequest;

class MockXMLHttpRequest {
  readyState = 4;
  status = 200;
  response = null;
  responseText = "";
  responseType = "";
  onreadystatechange: (() => void) | null = null;
  onload: (() => void) | null = null;
  onerror: (() => void) | null = null;

  open(): void {}
  setRequestHeader(): void {}
  abort(): void {}
  addEventListener(): void {}
  removeEventListener(): void {}
  getAllResponseHeaders(): string { return ""; }
  getResponseHeader(): string | null { return null; }
  send(): void {
    this.onreadystatechange?.();
    this.onload?.();
  }
}

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

beforeEach(() => {
  storage.clear();
  installLocalStorageMock();
  storage.set("h5-lang", "zh-CN");
  Object.defineProperty(globalThis, "XMLHttpRequest", {
    configurable: true,
    writable: true,
    value: MockXMLHttpRequest,
  });
});

afterEach(() => {
  storage.clear();
  Object.defineProperty(globalThis, "XMLHttpRequest", {
    configurable: true,
    writable: true,
    value: originalXmlHttpRequest,
  });
});

describe("Shared utilities", () => {
  beforeEach(() => {
    storage.set("h5-lang", "zh-CN");
  });

  afterEach(() => {
    storage.clear();
  });

  it("t() returns zh-CN string for valid key", () => {
    const result = t("common.confirm");
    expect(result).toBe("确认");
  });

  it("t() returns key for invalid key", () => {
    const result = t("nonexistent.key");
    expect(result).toBe("nonexistent.key");
  });

  it("t() handles template params", () => {
    // common.loading format: "加载中..."
    const result = t("common.loading");
    expect(result).toBe("加载中...");
  });

  it("formatMoney formats correctly", async () => {
    const { formatMoney } = await import("./shared");
    const result = formatMoney(1234.56);
    // The format is "楼1,234.56" for zh-CN with USD currency
    expect(result).toContain("1,234.56");
  });

  it("formatPercentage formats correctly", async () => {
    const { formatPercentage } = await import("./shared");
    expect(formatPercentage(0.15)).toBe("15%");
  });

  it("formatTimestamp handles null", async () => {
    const { formatTimestamp } = await import("./shared");
    expect(formatTimestamp(null)).toBe("暂无");
  });

  it("formatCountdown formats seconds correctly", async () => {
    const { formatCountdown } = await import("./shared");
    expect(formatCountdown(3661)).toBe("01:01:01");
    expect(formatCountdown(0)).toBe("00:00:00");
  });

  it("treats rtl locales with region suffixes as rtl", async () => {
    storage.set("h5-lang", "ar-SA");
    const { getCurrentLocale, getLocaleDirection, syncDocumentLocale } = await import("./shared");

    expect(getCurrentLocale()).toBe("ar-SA");
    expect(getLocaleDirection()).toBe("rtl");

    syncDocumentLocale();
    expect(document.documentElement.lang).toBe("ar-SA");
    expect(document.documentElement.dir).toBe("rtl");
  });

  it("falls back to English copy for unsupported non-Chinese locales", async () => {
    storage.set("h5-lang", "fr-FR");
    document.documentElement.lang = "fr-FR";
    Object.defineProperty(window.navigator, "language", {
      configurable: true,
      value: "fr-FR",
    });
    const { getCurrentLocale, getLocaleDirection, syncDocumentLocale } = await import("./shared");

    expect(getCurrentLocale()).toBe("fr-FR");
    expect(getLocaleDirection()).toBe("ltr");
    expect(t("common.confirm")).toBe("Confirm");

    syncDocumentLocale();
    expect(document.documentElement.lang).toBe("fr-FR");
    expect(document.documentElement.dir).toBe("ltr");
  });

  it("sanitizes english copy with clean punctuation for member-facing strings", () => {
    storage.set("h5-lang", "en-US");

    expect(t("serviceMessages.checkinBody")).toContain("check-in is complete");
    expect(t("home.activeTask", { time: "02:00:00" })).toBe("Active task · 02:00:00 remaining");
    expect(t("messages.prevPage")).toBe("← Prev");
    expect(t("messages.nextPage")).toBe("Next →");
  });

  it("returns clean english task and purchase copy without stray symbols", () => {
    storage.set("h5-lang", "en-US");

    expect(t("tasks.signInGoal", { amount: "$5.00", n: 7 })).toBe("$5.00 for 7 consecutive days");
    expect(t("tasks.needAmount", { amount: "$20.00" })).toBe("Need: $20.00");
    expect(t("tasks.currentBalance", { amount: "$12.00" })).toBe("Current: $12.00");
    expect(t("tasks.rewardSent", { amount: "$36.00" })).toBe("Reward $36.00 has been sent to task balance");
    expect(t("tasks.progressPaying", { amount: "$20.00" })).toBe("Processing Payment ($20.00)");
    expect(t("tasks.packageCompleted")).toBe("Package Completed!");
    expect(t("tasks.productCompleted")).toBe("Done");
    expect(t("tasks.productFailed")).toBe("Failed");
  });

  it("keeps recharge and whatsapp copy localized in chinese", () => {
    storage.set("h5-lang", "zh-CN");

    expect(t("recharge.title")).toBe("充值");
    expect(t("whatsapp.title")).toBe("WhatsApp 绑定");
    expect(t("whatsapp.bindTitle")).toBe("绑定 WhatsApp");
  });

  it("keeps earnings, service, and account copy localized in chinese", () => {
    storage.set("h5-lang", "zh-CN");

    expect(t("withdraw.title")).toBe("提现");
    expect(t("orders.title")).toBe("订单");
    expect(t("promotion.title")).toBe("推广");
    expect(t("settings.title")).toBe("设置");
    expect(t("chat.title")).toBe("在线客服");
    expect(t("network.offline")).toBe("当前网络已断开，部分功能暂时不可用");
    expect(t("notification.loginFailed")).toBe("登录失败。");
  });

  it("avoids nested full-screen chat viewports that block touch scrolling inside the member shell", () => {
    const css = readFileSync("src/styles/h5-member.css", "utf8");
    const chatContainerBlock = css.match(/\.h5-chat-container\s*\{([^}]*)\}/)?.[1] ?? "";
    const chatMessagesBlock = css.match(/\.h5-chat-messages\s*\{([^}]*)\}/)?.[1] ?? "";

    expect(chatContainerBlock).not.toMatch(/height:\s*100vh/);
    expect(chatContainerBlock).toMatch(/min-height:\s*0/);
    expect(chatMessagesBlock).toMatch(/overflow-y:\s*auto/);
    expect(chatMessagesBlock).toMatch(/min-height:\s*0/);
    expect(chatMessagesBlock).toMatch(/touch-action:\s*pan-y/);
  });

  it("anchors toast notifications above the fixed bottom rail instead of covering the topbar", () => {
    const css = readFileSync("src/styles/h5-member.css", "utf8");
    const toastStackBlock = css.match(/\.h5-member-toast-stack\s*\{([^}]*)\}/)?.[1] ?? "";

    expect(toastStackBlock).not.toMatch(/top:\s*calc/);
    expect(toastStackBlock).toMatch(/bottom:\s*calc\(88px \+ env\(safe-area-inset-bottom, 0px\)\)/);
    expect(toastStackBlock).toMatch(/align-items:\s*center/);
    expect(toastStackBlock).toMatch(/width:\s*min\(calc\(100% - 24px\), 420px\)/);
  });

  it("uses a compact primary-route toast variant so success notices do not dominate the viewport", () => {
    const css = readFileSync("src/styles/h5-member.css", "utf8");
    const compactStackBlock = css.match(/\.h5-member-toast-stack-compact\s*\{([^}]*)\}/)?.[1] ?? "";
    const compactToastBlock = css.match(/\.h5-member-toast-compact\s*\{([^}]*)\}/)?.[1] ?? "";

    expect(compactStackBlock).toMatch(/width:\s*min\(calc\(100% - 32px\), 320px\)/);
    expect(compactStackBlock).toMatch(/inset-inline-end:\s*16px/);
    expect(compactStackBlock).toMatch(/transform:\s*none/);
    expect(compactToastBlock).toMatch(/padding:\s*10px 12px 12px/);
    expect(compactToastBlock).toMatch(/border-radius:\s*12px/);
  });

  it("keeps shared.tsx free of shipping-form constant exports so Vite Fast Refresh can avoid invalidation", () => {
    const sharedSource = readFileSync("src/pages/h5-member/shared.tsx", "utf8");
    const defaultsSource = readFileSync("src/pages/h5-member/formDefaults.ts", "utf8");
    const ticketDefaultsSource = readFileSync("src/pages/h5-member/ticketDefaults.ts", "utf8");

    expect(sharedSource).not.toMatch(/export const DEFAULT_SHIPPING_FORM/);
    expect(sharedSource).not.toMatch(/export const DEFAULT_TICKET_DRAFT/);
    expect(defaultsSource).toMatch(/export const DEFAULT_SHIPPING_FORM/);
    expect(ticketDefaultsSource).toMatch(/export const DEFAULT_TICKET_DRAFT/);
  });

  it("keeps shared UI exports in a dedicated component module so Vite Fast Refresh can preserve interactive state", () => {
    const componentSource = readFileSync("src/pages/h5-member/sharedComponents.tsx", "utf8");

    expect(componentSource).toMatch(/export function ToastStack/);
    expect(componentSource).toMatch(/export function SectionHeader/);
    expect(componentSource).toMatch(/export function PullToRefresh/);
  });

  it("routes runtime h5 utility imports through a non-tsx module so Vite does not invalidate the whole shell on every helper edit", () => {
    const runtimeFiles = [
      "src/pages/H5App.tsx",
      "src/pages/h5-member/H5PageShell.tsx",
      "src/pages/h5-member/HomePage.tsx",
      "src/pages/h5-member/FragmentsPage.tsx",
      "src/pages/h5-member/InvitePage.tsx",
      "src/pages/h5-member/LeaderboardPage.tsx",
      "src/pages/h5-member/MessagesPage.tsx",
      "src/pages/h5-member/OrdersPage.tsx",
      "src/pages/h5-member/PackageDetailPage.tsx",
      "src/pages/h5-member/ProfilePage.tsx",
      "src/pages/h5-member/PromotionPage.tsx",
      "src/pages/h5-member/RechargePage.tsx",
      "src/pages/h5-member/TasksPage.tsx",
      "src/pages/h5-member/TicketsPage.tsx",
      "src/pages/h5-member/VerificationPage.tsx",
      "src/pages/h5-member/WhatsAppPage.tsx",
      "src/pages/h5-member/WithdrawPage.tsx",
      "src/pages/h5-member/useH5MemberApp.ts",
      "src/pages/h5-member/sharedComponents.tsx",
    ];

    const utilsSource = readFileSync("src/pages/h5-member/sharedUtils.ts", "utf8");
    expect(utilsSource).toMatch(/export function buildH5Path/);
    expect(utilsSource).toMatch(/export function formatMoney/);

    runtimeFiles.forEach((file) => {
      const source = readFileSync(file, "utf8");
      expect(source).not.toMatch(/from\s+["']\.\/shared["']/);
    });
  });

  it("keeps important unread message toast promotion in the app hook while task package manual-add notices stay page-local", () => {
    const hookSource = readFileSync("src/pages/h5-member/useH5MemberApp.ts", "utf8");

    expect(hookSource).toMatch(/isImportantMessage/);
    expect(hookSource).toMatch(/importantToast/);
    expect(hookSource).toMatch(/shownImportantToastKeysRef/);
    expect(hookSource).not.toMatch(/adjustmentNotice/);
  });

  it("returns production-ready english whatsapp support copy", () => {
    storage.set("h5-lang", "en-US");

    expect(t("whatsapp.legacyTitle")).not.toMatch(/legacy/i);
    expect(t("whatsapp.legacyDesc").toLowerCase()).not.toContain("temporary mode");
    expect(t("notification.whatsappOpened").toLowerCase()).not.toContain("pending backend integration");
    expect(t("serviceMessages.whatsappOpenedBody").toLowerCase()).not.toContain("prototype");
  });

  it("removes half-finished english copy from verification and orders surfaces", () => {
    storage.set("h5-lang", "en-US");

    expect(t("verification.uploadNote").toLowerCase()).not.toContain("official api");
    expect(t("verification.uploadNote").toLowerCase()).not.toContain("later");
    expect(t("orders.desc").toLowerCase()).not.toContain("v1");
    expect(t("orders.desc").toLowerCase()).not.toContain("not available");
  });

  it("returns localized purchase and fragment stage copy for english locale", async () => {
    storage.set("h5-lang", "en-US");
    const {
      getPurchasePhaseLabel,
      getFragmentStageContent,
      getPurchaseFailureActions,
      getVerificationStatusLabel,
    } = await import("./shared");

    expect(getPurchasePhaseLabel("create_order")).toBe("Creating Order");
    expect(getPurchasePhaseLabel("paying")).toBe("Processing Payment");
    expect(getPurchasePhaseLabel("settling")).toBe("Updating Task Progress");
    expect(getPurchasePhaseLabel("success")).toBe("Payment Complete / Task Completed");
    expect(getPurchasePhaseLabel("failed")).toBe("Payment Failed / Task Failed");
    expect(getVerificationStatusLabel("approved")).toBe("Approved");
    expect(getPurchaseFailureActions("Insufficient balance for this package.")).toEqual(["recharge"]);
    expect(getPurchaseFailureActions("Package purchase timed out.")).toEqual(["tasks"]);

    expect(getFragmentStageContent({ canExchangeFragments: false, latestShippingStatus: null })).toEqual({
      title: "Step 2: Keep collecting",
      description: "Keep checking in or doing tasks to collect fragments.",
    });
    expect(getFragmentStageContent({ canExchangeFragments: true, latestShippingStatus: "pending_address" })).toEqual({
      title: "Step 3: Fill in shipping info",
      description: "Progress: Address Pending",
    });
    expect(getFragmentStageContent({ canExchangeFragments: true, latestShippingStatus: "shipped" })).toEqual({
      title: "Step 4: Wait for shipping",
      description: "Progress: Shipped",
    });
  });

  it("localizes password toggle labels and preserves full compact row titles", async () => {
    storage.set("h5-lang", "zh-CN");
    const { CompactListRow, PasswordField } = await import("./sharedComponents");

    const { rerender } = render(
      <>
        <PasswordField
          value="secret"
          placeholder="password"
          visible={false}
          onChange={() => undefined}
          onToggle={() => undefined}
        />
        <CompactListRow
          title="这是一个非常长的任务标题，用于验证完整标题是否仍然可以访问"
          subtitle="副标题"
          value="123"
        />
      </>,
    );

    expect(screen.getByRole("button", { name: "显示密码" })).toBeTruthy();
    expect(
      screen.getByTitle("这是一个非常长的任务标题，用于验证完整标题是否仍然可以访问"),
    ).toBeTruthy();

    storage.set("h5-lang", "en-US");
    rerender(
      <PasswordField
        value="secret"
        placeholder="password"
        visible
        onChange={() => undefined}
        onToggle={() => undefined}
      />,
    );

    expect(screen.getByRole("button", { name: "Hide password" })).toBeTruthy();
  });

  it("keeps compact row side note and action copy inside one auxiliary rail", async () => {
    const { CompactListRow } = await import("./sharedComponents");

    render(
      <CompactListRow
        title="Verification"
        meta="Not Submitted"
        sideNote="View"
        actionLabel="Enter"
      />,
    );

    const sideNote = screen.getByText("View");
    const actionLabel = screen.getByText("Enter");
    const sideRail = sideNote.parentElement;

    expect(sideRail).toBeTruthy();
    expect(sideRail).toBe(actionLabel.parentElement);
    expect(sideRail?.className).toContain("h5-member-list-row-meta");
  });

  it("stacks profile balance actions on narrow phones to avoid horizontal crowding", () => {
    const css = readFileSync("src/styles/h5-member.css", "utf8");

    expect(css).toMatch(/@media \(max-width:\s*420px\)[\s\S]*\.h5-member-profile-balance-card\s*\{[\s\S]*flex-direction:\s*column/);
    expect(css).toMatch(/@media \(max-width:\s*420px\)[\s\S]*\.h5-member-balance-card-actions\s*\{[\s\S]*width:\s*100%/);
  });

  it("extends profile balance action wrapping to medium-width phones so long localized buttons do not collide", () => {
    const css = readFileSync("src/styles/h5-member.css", "utf8");

    expect(css).toMatch(/@media \(max-width:\s*480px\)[\s\S]*\.h5-member-profile-balance-card\s*\{[\s\S]*flex-direction:\s*column/);
    expect(css).toMatch(/@media \(max-width:\s*480px\)[\s\S]*\.h5-member-balance-card-actions\s*\{[\s\S]*width:\s*100%/);
    expect(css).toMatch(/@media \(max-width:\s*480px\)[\s\S]*\.h5-member-balance-card-actions\s*\{[\s\S]*flex-wrap:\s*wrap/);
  });

  it("stacks topbar regions and promotes full-width action buttons on very narrow phones", () => {
    const css = readFileSync("src/styles/h5-member.css", "utf8");

    expect(css).toMatch(/@media \(max-width:\s*420px\)[\s\S]*\.h5-member-topbar-main,\s*[\s\S]*\.h5-member-topbar-side\s*\{[\s\S]*width:\s*100%/);
    expect(css).toMatch(/@media \(max-width:\s*420px\)[\s\S]*\.h5-member-card-actions\s*>\s*\*\s*\{[\s\S]*width:\s*100%/);
  });

  it("reduces topbar and tabbar density for 320-360px phones", () => {
    const css = readFileSync("src/styles/h5-member.css", "utf8");

    expect(css).toMatch(/@media \(max-width:\s*360px\)[\s\S]*\.h5-member-topbar-title-group strong\s*\{[\s\S]*font-size:\s*16px/);
    expect(css).toMatch(/@media \(max-width:\s*360px\)[\s\S]*\.h5-member-topbar-title-group span\s*\{[\s\S]*font-size:\s*11px/);
    expect(css).toMatch(/@media \(max-width:\s*360px\)[\s\S]*\.h5-member-tabbar-item span:last-child\s*\{[\s\S]*font-size:\s*10px/);
  });

  it("caps topbar subtitles to two lines on narrow phones so long locales do not overrun the header", () => {
    const css = readFileSync("src/styles/h5-member.css", "utf8");

    expect(css).toMatch(/@media \(max-width:\s*420px\)[\s\S]*\.h5-member-topbar-title-group span\s*\{[\s\S]*display:\s*-webkit-box/);
    expect(css).toMatch(/@media \(max-width:\s*420px\)[\s\S]*\.h5-member-topbar-title-group span\s*\{[\s\S]*-webkit-line-clamp:\s*2/);
    expect(css).toMatch(/@media \(max-width:\s*420px\)[\s\S]*\.h5-member-topbar-title-group span\s*\{[\s\S]*overflow:\s*hidden/);
  });

  it("stacks auth support cards into a single column on narrow phones so long localized helper copy stays readable", () => {
    const css = readFileSync("src/styles/h5-member.css", "utf8");

    expect(css).toMatch(/@media \(max-width:\s*420px\)[\s\S]*\.h5-member-auth-support-grid\s*\{[\s\S]*grid-template-columns:\s*1fr/);
  });

  it("stacks message and order overview metric grids on mobile so translated KPI cards do not squeeze into two columns", () => {
    const css = readFileSync("src/styles/h5-member.css", "utf8");

    expect(css).toMatch(/@media \(max-width:\s*640px\)[\s\S]*\.h5-member-message-overview-grid[\s\S]*grid-template-columns:\s*1fr/);
    expect(css).toMatch(/@media \(max-width:\s*640px\)[\s\S]*\.h5-member-orders-overview-grid[\s\S]*grid-template-columns:\s*1fr/);
  });

  it("reserves bottom cta clearance above the fixed tabbar for short mobile forms", () => {
    const css = readFileSync("src/styles/h5-member.css", "utf8");

    expect(css).toMatch(/\.h5-member-app-shell\s*\{[\s\S]*--h5-member-bottom-rail-clearance:\s*calc\(152px \+ env\(safe-area-inset-bottom, 0px\)\)/);
    expect(css).toMatch(/\.h5-member-app-shell\s*\{[\s\S]*scroll-padding-bottom:\s*var\(--h5-member-bottom-rail-clearance\)/);
    expect(css).toMatch(/\.h5-member-safe-bottom\s*\{[\s\S]*height:\s*var\(--h5-member-bottom-rail-clearance\)/);
    expect(css).toMatch(/\.h5-member-safe-bottom\s*\{[\s\S]*flex:\s*0 0 var\(--h5-member-bottom-rail-clearance\)/);
  });

  it("compacts toast and bottom navigation on short landscape phones", () => {
    const css = readFileSync("src/styles/h5-member.css", "utf8");

    expect(css).toMatch(/@media \(max-height:\s*420px\) and \(orientation:\s*landscape\)[\s\S]*\.h5-member-app-shell\s*\{[\s\S]*--h5-member-bottom-rail-clearance:\s*calc\(108px \+ env\(safe-area-inset-bottom, 0px\)\)/);
    expect(css).toMatch(/@media \(max-height:\s*420px\) and \(orientation:\s*landscape\)[\s\S]*\.h5-member-toast-stack\s*\{[\s\S]*inset-inline-end:\s*12px/);
    expect(css).toMatch(/@media \(max-height:\s*420px\) and \(orientation:\s*landscape\)[\s\S]*\.h5-member-toast-stack\s*\{[\s\S]*transform:\s*none/);
    expect(css).toMatch(/@media \(max-height:\s*420px\) and \(orientation:\s*landscape\)[\s\S]*\.h5-member-tabbar-item\s*\{[\s\S]*min-height:\s*40px/);
    expect(css).toMatch(/@media \(max-height:\s*420px\) and \(orientation:\s*landscape\)[\s\S]*\.h5-member-tabbar-item span:last-child\s*\{[\s\S]*font-size:\s*9px/);
  });

  it("keeps the sticky network banner below the topbar so offline state does not cover navigation controls", () => {
    const css = readFileSync("src/styles/h5-member.css", "utf8");

    expect(css).toMatch(/\.h5-member-topbar\s*\{[\s\S]*z-index:\s*20/);
    expect(css).toMatch(/\.h5-network-banner\s*\{[\s\S]*top:\s*calc\([^)]+env\(safe-area-inset-top, 0px\)\)/);
    expect(css).toMatch(/\.h5-network-banner\s*\{[\s\S]*z-index:\s*19/);
  });

  it("caps mobile detail and confirm overlays to the viewport with their own scroll area", () => {
    const css = readFileSync("src/styles/h5-member.css", "utf8");

    expect(css).toMatch(/\.h5-member-msg-detail-panel\s*\{[\s\S]*max-height:\s*min\(calc\(100dvh - 48px - env\(safe-area-inset-bottom, 0px\)\), 720px\)/);
    expect(css).toMatch(/\.h5-member-msg-detail-panel\s*\{[\s\S]*overflow-y:\s*auto/);
    expect(css).toMatch(/\.h5-member-claim-confirm\s*\{[\s\S]*max-height:\s*min\(calc\(100dvh - 48px - env\(safe-area-inset-bottom, 0px\)\), 720px\)/);
    expect(css).toMatch(/\.h5-member-claim-confirm\s*\{[\s\S]*overflow-y:\s*auto/);
  });

  it("lets the whatsapp composer shrink cleanly on narrow phones without pushing controls off-screen", () => {
    const css = readFileSync("src/styles/h5-member.css", "utf8");

    expect(css).toMatch(/\.h5-chat-input-area\s*\{[\s\S]*min-width:\s*0/);
    expect(css).toMatch(/\.h5-chat-input\s*\{[\s\S]*min-width:\s*0/);
  });

  it("keeps the chat composer above the fixed bottom rail by reserving a dedicated tabbar offset", () => {
    const css = readFileSync("src/styles/h5-member.css", "utf8");

    expect(css).toMatch(/\.h5-member-app-shell\s*\{[\s\S]*--h5-member-tabbar-overlay:\s*calc\(72px \+ env\(safe-area-inset-bottom, 0px\)\)/);
    expect(css).toMatch(/\.h5-chat-container\s*\{[\s\S]*padding-bottom:\s*var\(--h5-member-tabbar-overlay\)/);
    expect(css).toMatch(/\.h5-chat-container\s*\{[\s\S]*box-sizing:\s*border-box/);
    expect(css).toMatch(/@media \(max-height:\s*420px\) and \(orientation:\s*landscape\)[\s\S]*\.h5-member-app-shell\s*\{[\s\S]*--h5-member-tabbar-overlay:\s*calc\(56px \+ env\(safe-area-inset-bottom, 0px\)\)/);
  });

  it("switches the whatsapp route into a flex chat content shell instead of stacking it like a regular card page", () => {
    const css = readFileSync("src/styles/h5-member.css", "utf8");

    expect(css).toMatch(/\.h5-member-content-chat\s*\{[\s\S]*display:\s*flex/);
    expect(css).toMatch(/\.h5-member-content-chat\s*\{[\s\S]*flex:\s*1 1 auto/);
    expect(css).toMatch(/\.h5-member-content-chat\s*\{[\s\S]*min-height:\s*0/);
    expect(css).toMatch(/\.h5-member-content-chat\s*\{[\s\S]*overflow:\s*hidden/);
  });

  it("hides the fixed tabbar while the chat composer is focused so the keyboard does not stack over navigation", () => {
    const css = readFileSync("src/styles/h5-member.css", "utf8");

    expect(css).toMatch(/\.h5-member-content-chat:focus-within\s*>\s*\.h5-chat-container\s*\{[\s\S]*padding-bottom:\s*env\(safe-area-inset-bottom, 0px\)/);
    expect(css).toMatch(/\.h5-member-content-chat:focus-within\s*~\s*\.h5-member-tabbar\s*\{[\s\S]*transform:\s*translateY\(calc\(100% \+ env\(safe-area-inset-bottom, 0px\)\)\)/);
    expect(css).toMatch(/\.h5-member-content-chat:focus-within\s*~\s*\.h5-member-tabbar\s*\{[\s\S]*opacity:\s*0/);
    expect(css).toMatch(/\.h5-member-content-chat:focus-within\s*~\s*\.h5-member-tabbar\s*\{[\s\S]*pointer-events:\s*none/);
  });

  it("wraps the messages topbar action under the title on narrow phones instead of crushing the header", () => {
    const css = readFileSync("src/styles/h5-member.css", "utf8");

    expect(css).toMatch(/@media \(max-width:\s*420px\)[\s\S]*\.h5-member-topbar-main\s*\{[\s\S]*flex-wrap:\s*wrap/);
    expect(css).toMatch(/@media \(max-width:\s*420px\)[\s\S]*\.h5-member-msg-topbar-btn\s*\{[\s\S]*width:\s*100%/);
    expect(css).toMatch(/@media \(max-width:\s*420px\)[\s\S]*\.h5-member-msg-topbar-btn\s*\{[\s\S]*justify-content:\s*center/);
    expect(css).toMatch(/\.h5-member-msg-topbar-count\s*\{[\s\S]*margin-inline-start:\s*2px/);
  });

  it("wraps purchase balance dialog amounts instead of forcing a single cramped row", () => {
    const css = readFileSync("src/styles/h5-member.css", "utf8");

    expect(css).toMatch(/\.h5-balance-dialog \.h5-balance-dialog-amounts\s*\{[\s\S]*flex-wrap:\s*wrap/);
    expect(css).toMatch(/\.h5-balance-dialog \.h5-balance-dialog-amounts span\s*\{[\s\S]*min-width:\s*112px/);
  });

  it("shrinks progress overlays and lets translated status copy wrap on 320-360px phones", () => {
    const css = readFileSync("src/styles/h5-member.css", "utf8");

    expect(css).toMatch(/@media \(max-width:\s*360px\)[\s\S]*\.h5-progress-modal\s*\{[\s\S]*width:\s*min\(100%, 280px\)/);
    expect(css).toMatch(/@media \(max-width:\s*360px\)[\s\S]*\.h5-progress-modal\s*\{[\s\S]*padding:\s*24px 16px/);
    expect(css).toMatch(/@media \(max-width:\s*360px\)[\s\S]*\.h5-package-progress-status\s*\{[\s\S]*flex-wrap:\s*wrap/);
  });

  it("lets promotion record rows wrap translated labels inside a mobile-safe stacked card layout", () => {
    const css = readFileSync("src/styles/h5-member.css", "utf8");

    expect(css).toMatch(/\.h5-member-promotion-record-row\s+\.h5-member-list-row-title strong,\s*[\s\S]*overflow-wrap:\s*anywhere/);
    expect(css).toMatch(/@media \(max-width:\s*640px\)[\s\S]*\.h5-member-promotion-record-row \.h5-member-list-row\s*\{[\s\S]*padding:\s*14px/);
    expect(css).toMatch(/@media \(max-width:\s*640px\)[\s\S]*\.h5-member-promotion-record-row \.h5-member-list-row-subtitle,[\s\S]*white-space:\s*normal/);
  });

  it("stacks invite actions and record rows on narrow phones so multilingual copy stays readable", () => {
    const css = readFileSync("src/styles/h5-member.css", "utf8");

    expect(css).toMatch(/@media \(max-width:\s*420px\)[\s\S]*\.h5-invite-actions\s*\{[\s\S]*flex-direction:\s*column/);
    expect(css).toMatch(/@media \(max-width:\s*420px\)[\s\S]*\.h5-invite-actions button\s*\{[\s\S]*width:\s*100%/);
    expect(css).toMatch(/@media \(max-width:\s*420px\)[\s\S]*\.h5-invite-record-row\s*\{[\s\S]*grid-template-columns:\s*1fr/);
  });

  it("lays out withdraw inline actions as a real flex row and stacks them on narrow phones for long translations", () => {
    const css = readFileSync("src/styles/h5-member.css", "utf8");

    expect(css).toMatch(/\.h5-member-inline-actions,\s*[\s\S]*\.h5-member-card-actions\s*\{[\s\S]*display:\s*flex/);
    expect(css).toMatch(/\.h5-member-inline-actions,\s*[\s\S]*\.h5-member-card-actions\s*\{[\s\S]*flex-wrap:\s*wrap/);
    expect(css).toMatch(/@media \(max-width:\s*420px\)[\s\S]*\.h5-member-inline-actions\s*>\s*\*\s*\{[\s\S]*width:\s*100%/);
  });

  it("uses the real h5 scroll shell for pull-to-refresh instead of a non-scrolling wrapper", async () => {
    const onRefresh = vi.fn().mockResolvedValue(undefined);
    const { PullToRefresh } = await import("./sharedComponents");

    const shell = document.createElement("div");
    shell.className = "h5-member-app-shell";
    Object.defineProperty(shell, "scrollTop", {
      configurable: true,
      get: () => 48,
    });
    document.body.appendChild(shell);

    const view = render(
      <PullToRefresh onRefresh={onRefresh}>
        <div>Scrollable content</div>
      </PullToRefresh>,
      { container: shell },
    );

    const pullWrapper = screen.getByText("Scrollable content").parentElement as HTMLElement;

    fireEvent.touchStart(pullWrapper, { touches: [{ clientY: 100 }] });
    fireEvent.touchMove(pullWrapper, { touches: [{ clientY: 240 }] });
    fireEvent.touchEnd(pullWrapper);

    await waitFor(() => {
      expect(onRefresh).not.toHaveBeenCalled();
    });

    view.unmount();
    shell.remove();
  });

  it("triggers refresh once when the h5 scroll shell is at the top and the pull threshold is exceeded", async () => {
    const onRefresh = vi.fn().mockResolvedValue(undefined);
    const { PullToRefresh } = await import("./sharedComponents");

    const shell = document.createElement("div");
    shell.className = "h5-member-app-shell";
    let shellScrollTop = 0;
    Object.defineProperty(shell, "scrollTop", {
      configurable: true,
      get: () => shellScrollTop,
    });
    document.body.appendChild(shell);

    const view = render(
      <PullToRefresh onRefresh={onRefresh}>
        <div>Scrollable content</div>
      </PullToRefresh>,
      { container: shell },
    );

    const pullWrapper = screen.getByText("Scrollable content").parentElement as HTMLElement;

    fireEvent.touchStart(pullWrapper, { touches: [{ clientY: 100 }] });
    fireEvent.touchMove(pullWrapper, { touches: [{ clientY: 240 }] });
    fireEvent.touchEnd(pullWrapper);

    await waitFor(() => {
      expect(onRefresh).toHaveBeenCalledTimes(1);
    });

    view.unmount();
    shell.remove();
  });

  it("uses dedicated pull-to-refresh shell classes so the indicator styling is not hard-coded inline", async () => {
    const onRefresh = vi.fn().mockResolvedValue(undefined);
    const { PullToRefresh } = await import("./sharedComponents");
    const css = readFileSync("src/styles/h5-member.css", "utf8");

    render(
      <PullToRefresh onRefresh={onRefresh}>
        <div>Scrollable content</div>
      </PullToRefresh>,
    );

    const pullWrapper = screen.getByText("Scrollable content").parentElement as HTMLElement;

    expect(pullWrapper.className).toContain("h5-pull-shell");
    expect(css).toMatch(/\.h5-pull-shell\s*\{/);
    expect(css).toMatch(/\.h5-pull-indicator\s*\{[\s\S]*justify-content:\s*center/);
    expect(css).toMatch(/\.h5-pull-indicator\s*\{[\s\S]*min-height:\s*40px/);
    expect(css).toMatch(/\.h5-pull-indicator-icon\s*\{[\s\S]*margin-inline-end:\s*6px/);

    fireEvent.touchStart(pullWrapper, { touches: [{ clientY: 0 }] });
    fireEvent.touchMove(pullWrapper, { touches: [{ clientY: 120 }] });
    fireEvent.touchEnd(pullWrapper);

    await waitFor(() => {
      const loadingText = screen.getByText(t("common.loading"));
      const loadingIcon = loadingText.parentElement?.querySelector(".h5-pull-indicator-icon");
      expect(loadingIcon).toBeTruthy();
      expect(loadingIcon?.getAttribute("style")).toBeNull();
    });
  });

  it("compacts profile hero and task card chrome for ultra-narrow phones", () => {
    const css = readFileSync("src/styles/h5-member.css", "utf8");

    expect(css).toMatch(/@media \(max-width:\s*360px\)[\s\S]*\.h5-member-profile-avatar\s*\{[\s\S]*width:\s*60px[\s\S]*height:\s*60px/);
    expect(css).toMatch(/@media \(max-width:\s*360px\)[\s\S]*\.h5-task-instance-card\s*\{[\s\S]*padding:\s*12px/);
    expect(css).toMatch(/@media \(max-width:\s*360px\)[\s\S]*\.h5-task-instance-card \.h5-task-instance-status-badge\s*\{[\s\S]*align-self:\s*flex-start/);
  });

  it("compacts earnings balance cards and stacks transfer-all controls on ultra-narrow phones", () => {
    const css = readFileSync("src/styles/h5-member.css", "utf8");

    expect(css).toMatch(/@media \(max-width:\s*360px\)[\s\S]*\.h5-member-wallet-balance-card\s*\{[\s\S]*align-items:\s*flex-start/);
    expect(css).toMatch(/@media \(max-width:\s*360px\)[\s\S]*\.h5-member-wallet-balance-card\s*\{[\s\S]*flex-direction:\s*column/);
    expect(css).toMatch(/@media \(max-width:\s*360px\)[\s\S]*\.h5-member-wallet-balance-card \.h5-member-balance-card-value\s*\{[\s\S]*font-size:\s*15px/);
    expect(css).toMatch(/@media \(max-width:\s*360px\)[\s\S]*\.h5-member-wallet-balance-card \.h5-member-balance-card-actions\s*\{[\s\S]*width:\s*100%/);
  });

  it("stacks package product rows on ultra-narrow phones so long titles and action buttons do not collide", () => {
    const css = readFileSync("src/styles/h5-member.css", "utf8");

    expect(css).toMatch(/@media \(max-width:\s*360px\)[\s\S]*\.h5-package-product-item\s*\{[\s\S]*align-items:\s*flex-start/);
    expect(css).toMatch(/@media \(max-width:\s*360px\)[\s\S]*\.h5-package-product-item\s*\{[\s\S]*flex-wrap:\s*wrap/);
    expect(css).toMatch(/@media \(max-width:\s*360px\)[\s\S]*\.h5-package-product-btn\s*\{[\s\S]*width:\s*100%/);
  });

  it("keeps wallet balance labels on their local typography instead of inheriting summary-card hero sizing", () => {
    const css = readFileSync("src/styles/h5-member.css", "utf8");

    expect(css).toMatch(/\.h5-member-wallet-balance-card \.h5-member-balance-card-label\s*\{[\s\S]*font-size:\s*12px/);
    expect(css).toMatch(/\.h5-member-wallet-balance-card \.h5-member-balance-card-label\s*\{[\s\S]*color:\s*#64748b/);
    expect(css).toMatch(/\.h5-member-wallet-balance-card \.h5-member-balance-card-value\s*\{[\s\S]*font-size:\s*18px/);
    expect(css).toMatch(/\.h5-member-wallet-balance-card \.h5-member-balance-card-value\s*\{[\s\S]*color:\s*#0f172a/);
  });

  it("uses dedicated infinite-scroll feedback classes instead of inline loader and end-state styles", async () => {
    const { InfiniteScroll } = await import("./sharedComponents");
    const css = readFileSync("src/styles/h5-member.css", "utf8");
    const onLoadMore = vi.fn();

    const { rerender } = render(
      <InfiniteScroll hasMore loading onLoadMore={onLoadMore}>
        <div>Feed content</div>
      </InfiniteScroll>,
    );

    const sentinel = document.querySelector(".h5-infinite-scroll-sentinel") as HTMLDivElement | null;
    const loadingState = screen.getByText(t("common.loading")).closest(".h5-infinite-scroll-loading");
    const loadingIcon = loadingState?.querySelector(".h5-infinite-scroll-loading-icon");

    expect(sentinel).toBeTruthy();
    expect(sentinel?.getAttribute("style")).toBeNull();
    expect(loadingState).toBeTruthy();
    expect(loadingState?.getAttribute("style")).toBeNull();
    expect(loadingIcon).toBeTruthy();
    expect(css).toMatch(/\.h5-infinite-scroll-sentinel\s*\{[\s\S]*height:\s*1px/);
    expect(css).toMatch(/\.h5-infinite-scroll-loading\s*\{[\s\S]*text-align:\s*center/);
    expect(css).toMatch(/\.h5-infinite-scroll-loading-icon\s*\{[\s\S]*margin-inline-end:\s*6px/);

    rerender(
      <InfiniteScroll hasMore={false} loading={false} onLoadMore={onLoadMore}>
        <div>Feed content</div>
      </InfiniteScroll>,
    );

    const endState = screen.getByText(t("common.noMore")).closest(".h5-infinite-scroll-end");

    expect(endState).toBeTruthy();
    expect(endState?.getAttribute("style")).toBeNull();
    expect(css).toMatch(/\.h5-infinite-scroll-end\s*\{[\s\S]*font-size:\s*13px/);
  });

  it("uses dedicated error-boundary fallback classes instead of inline positioning and button sizing", async () => {
    const { ErrorBoundary } = await import("./ErrorBoundary");
    const css = readFileSync("src/styles/h5-member.css", "utf8");
    const errorSpy = vi.spyOn(console, "error").mockImplementation(() => undefined);

    function ThrowingChild(): JSX.Element {
      throw new Error("render failed");
    }

    render(
      <ErrorBoundary>
        <ThrowingChild />
      </ErrorBoundary>,
    );

    const shell = screen.getByText(t("errorBoundary.title")).closest("section");
    const refreshButton = screen.getByRole("button", { name: t("errorBoundary.refresh") });

    expect(shell).toBeTruthy();
    expect(shell?.className).toContain("h5-error-boundary-shell");
    expect(shell?.getAttribute("style")).toBeNull();
    expect(refreshButton.className).toContain("h5-error-boundary-refresh");
    expect(refreshButton.getAttribute("style")).toBeNull();
    expect(css).toMatch(/\.h5-error-boundary-shell\s*\{[\s\S]*justify-content:\s*center/);
    expect(css).toMatch(/\.h5-error-boundary-refresh\s*\{[\s\S]*min-width:\s*120px/);

    errorSpy.mockRestore();
  });

  it("uses dedicated skeleton variant classes instead of inline placeholder sizing across shared loading states", async () => {
    const { HomeSkeleton } = await import("./skeletons/HomeSkeleton");
    const { ListSkeleton } = await import("./skeletons/ListSkeleton");
    const { DetailSkeleton } = await import("./skeletons/DetailSkeleton");
    const { ProfileSkeleton } = await import("./skeletons/ProfileSkeleton");
    const css = readFileSync("src/styles/h5-member.css", "utf8");

    const { container } = render(
      <>
        <HomeSkeleton />
        <ListSkeleton count={2} />
        <DetailSkeleton />
        <ProfileSkeleton />
      </>,
    );

    expect(container.querySelector(".h5-skeleton-card-home-hero")).toBeTruthy();
    expect(container.querySelector(".h5-skeleton-card-list-item")).toBeTruthy();
    expect(container.querySelector(".h5-skeleton-card-detail-hero")).toBeTruthy();
    expect(container.querySelector(".h5-skeleton-card-profile-hero")).toBeTruthy();
    expect(container.querySelector(".h5-skeleton-profile-hero-copy")).toBeTruthy();
    expect(container.querySelector(".h5-skeleton-grid-profile-actions")).toBeTruthy();

    container.querySelectorAll<HTMLElement>(".h5-skeleton-card, .h5-skeleton-row, .h5-skeleton-grid, .h5-skeleton-profile-hero-copy")
      .forEach((node) => {
        expect(node.getAttribute("style")).toBeNull();
      });

    expect(css).toMatch(/\.h5-skeleton-card-home-hero\s*\{[\s\S]*height:\s*100px/);
    expect(css).toMatch(/\.h5-skeleton-card-list-item\s*\{[\s\S]*height:\s*80px/);
    expect(css).toMatch(/\.h5-skeleton-card-detail-hero\s*\{[\s\S]*height:\s*180px/);
    expect(css).toMatch(/\.h5-skeleton-card-profile-hero\s*\{[\s\S]*display:\s*flex/);
    expect(css).toMatch(/\.h5-skeleton-grid-profile-actions\s*\{[\s\S]*margin-top:\s*8px/);
  });

  it("uses dedicated image-viewer zoom cursor classes instead of inline cursor styling", async () => {
    const { ImageViewer } = await import("./ImageViewer");
    const css = readFileSync("src/styles/h5-member.css", "utf8");
    const timeMarks = [1000, 1200, 1200, 1200];
    const dateNowSpy = vi.spyOn(Date, "now").mockImplementation(() => timeMarks.shift() ?? 1200);
    const inlineImages = [
      "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16'%3E%3Crect width='16' height='16' fill='%2399c'/%3E%3C/svg%3E",
      "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16'%3E%3Crect width='16' height='16' fill='%239c9'/%3E%3C/svg%3E",
    ];

    const { container } = render(
      <ImageViewer
        images={inlineImages}
        onClose={() => undefined}
      />,
    );

    const content = container.querySelector(".h5-image-viewer-content") as HTMLDivElement | null;
    const image = container.querySelector(".h5-image-viewer-img") as HTMLImageElement | null;

    expect(content).toBeTruthy();
    expect(image).toBeTruthy();
    expect(image?.className).not.toContain("h5-image-viewer-img-zoomed");
    expect(image?.getAttribute("style") ?? "").toContain("transform:");
    expect(image?.getAttribute("style") ?? "").not.toContain("cursor:");

    fireEvent.click(content!);
    fireEvent.click(content!);

    await waitFor(() => {
      expect((container.querySelector(".h5-image-viewer-img") as HTMLImageElement | null)?.className).toContain("h5-image-viewer-img-zoomed");
    });
    expect(image?.getAttribute("style") ?? "").not.toContain("cursor:");
    expect(css).toMatch(/\.h5-image-viewer-img\s*\{[\s\S]*cursor:\s*default/);
    expect(css).toMatch(/\.h5-image-viewer-img-zoomed\s*\{[\s\S]*cursor:\s*grab/);

    dateNowSpy.mockRestore();
  });

  it("uses a dedicated close icon in the image viewer instead of raw fallback glyph text", async () => {
    const { ImageViewer } = await import("./ImageViewer");

    const { container } = render(
      <ImageViewer
        images={["https://example.com/proof-a.jpg"]}
        onClose={() => undefined}
      />,
    );

    const closeButton = container.querySelector(".h5-image-viewer-close") as HTMLButtonElement | null;
    const closeIcon = container.querySelector(".h5-image-viewer-close .anticon-close");

    expect(closeIcon).toBeTruthy();
    expect(closeButton).toBeTruthy();
    expect(closeButton?.textContent?.trim()).toBe("");
  });

  it("uses a dedicated hidden input class in media uploader instead of inline display rules", async () => {
    const { MediaUploader } = await import("./MediaUploader");
    const css = readFileSync("src/styles/h5-member.css", "utf8");
    const { container } = render(
      <MediaUploader accept="image/*" compress={false} multiple onUpload={() => undefined} />,
    );

    const input = container.querySelector('input[type="file"]') as HTMLInputElement | null;

    expect(input).toBeTruthy();
    expect(input?.className).toContain("h5-media-input");
    expect(input?.getAttribute("style")).toBeNull();
    expect(css).toMatch(/\.h5-media-input\s*\{[\s\S]*display:\s*none/);
  });

  it("renders compression size copy with a dedicated arrow node instead of loose fallback text", async () => {
    const createObjectUrl = vi.fn(() => "blob:test");
    const revokeObjectUrl = vi.fn();
    Object.defineProperty(URL, "createObjectURL", {
      configurable: true,
      writable: true,
      value: createObjectUrl,
    });
    Object.defineProperty(URL, "revokeObjectURL", {
      configurable: true,
      writable: true,
      value: revokeObjectUrl,
    });

    const originalImage = globalThis.Image;
    const originalGetContext = HTMLCanvasElement.prototype.getContext;
    const originalToBlob = HTMLCanvasElement.prototype.toBlob;

    class MockImage {
      onload: (() => void) | null = null;
      onerror: (() => void) | null = null;
      width = 1600;
      height = 900;
      set src(_value: string) {
        queueMicrotask(() => this.onload?.());
      }
    }

    Object.defineProperty(globalThis, "Image", {
      configurable: true,
      writable: true,
      value: MockImage,
    });

    HTMLCanvasElement.prototype.getContext = vi.fn(() => ({
      drawImage: vi.fn(),
    })) as unknown as typeof HTMLCanvasElement.prototype.getContext;

    HTMLCanvasElement.prototype.toBlob = vi.fn((callback: BlobCallback) => {
      callback?.(new Blob(["compressed"], { type: "image/jpeg" }));
    }) as typeof HTMLCanvasElement.prototype.toBlob;

    const { MediaUploader } = await import("./MediaUploader");
    const largeFile = new File([new Uint8Array(1024 * 1024 + 32)], "proof-large.png", { type: "image/png" });
    const { container } = render(
      <MediaUploader accept="image/*" multiple={false} onUpload={() => undefined} />,
    );

    const input = container.querySelector('input[type="file"]') as HTMLInputElement | null;
    expect(input).toBeTruthy();
    fireEvent.change(input!, { target: { files: [largeFile] } });

    await waitFor(() => {
      const arrow = container.querySelector(".h5-media-compression-arrow");
      const sizeCopy = container.querySelector(".h5-media-preview-size");

      expect(arrow).toBeTruthy();
      expect(arrow?.textContent).toBe("->");
      expect(sizeCopy?.textContent).toContain("1.0 MB");
      expect(sizeCopy?.textContent).toContain("10 B");
    });

    Object.defineProperty(globalThis, "Image", {
      configurable: true,
      writable: true,
      value: originalImage,
    });
    HTMLCanvasElement.prototype.getContext = originalGetContext;
    HTMLCanvasElement.prototype.toBlob = originalToBlob;
  });
});

describe("MessagesPage", () => {
  beforeEach(() => {
    class MockIntersectionObserver {
      observe(): void {}
      unobserve(): void {}
      disconnect(): void {}
    }

    Object.defineProperty(globalThis, "IntersectionObserver", {
      configurable: true,
      writable: true,
      value: MockIntersectionObserver,
    });
  });

  afterEach(() => {
    cleanup();
  });

  it("renders important and other message sections", async () => {
    const { MessagesPage } = await import("./MessagesPage");
    const onMarkAllRead = vi.fn().mockResolvedValue(undefined);
    const onOpenMessage = vi.fn().mockResolvedValue(undefined);

    render(
      <MessagesPage
        messages={[
          {
            id: "msg-task",
            category: "task",
            title: "Task update",
            body: "Complete your current package",
            createdAt: "2026-06-23T08:00:00.000Z",
            isRead: false,
          },
          {
            id: "msg-fragment",
            category: "fragment",
            title: "Fragment drop",
            body: "You received a new fragment",
            createdAt: "2026-06-22T08:00:00.000Z",
            isRead: true,
          },
        ]}
        unreadMessageCount={1}
        actionName={null}
        siteKey="mall-cn"
        loading={false}
        error={null}
        currentPage={1}
        totalMessages={2}
        onMarkAllRead={onMarkAllRead}
        onOpenMessage={onOpenMessage}
        onNavigate={() => undefined}
        onPageChange={() => undefined}
        onRetry={() => undefined}
      />,
    );

    expect(screen.getByText(t("messages.importantNotice"))).toBeTruthy();
    expect(screen.getByText(t("messages.otherMessages"))).toBeTruthy();
    expect(screen.getByText("Task update")).toBeTruthy();
    expect(screen.getByText("Fragment drop")).toBeTruthy();
  });

  it("surfaces an inbox overview and service shortcuts before grouped message sections", async () => {
    const { MessagesPage } = await import("./MessagesPage");
    const onNavigate = vi.fn();

    render(
      <MessagesPage
        messages={[
          {
            id: "msg-task",
            category: "task",
            title: "Task update",
            body: "Complete your current package",
            createdAt: "2026-06-23T08:00:00.000Z",
            isRead: false,
          },
          {
            id: "msg-wallet",
            category: "wallet",
            title: "Wallet review",
            body: "Balance settlement completed",
            createdAt: "2026-06-22T08:00:00.000Z",
            isRead: true,
          },
        ]}
        unreadMessageCount={1}
        actionName={null}
        siteKey="mall-cn"
        loading={false}
        error={null}
        currentPage={1}
        totalMessages={2}
        onMarkAllRead={vi.fn().mockResolvedValue(undefined)}
        onOpenMessage={vi.fn().mockResolvedValue(undefined)}
        onNavigate={onNavigate}
        onPageChange={() => undefined}
        onRetry={() => undefined}
      />,
    );

    const overviewHeading = screen.getByText(t("messages.overviewTitle"));
    const importantHeading = screen.getByText(t("messages.importantNotice"));

    expect(overviewHeading.compareDocumentPosition(importantHeading)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
    expect(screen.getByText(t("messages.overviewUnreadLabel"))).toBeTruthy();
    expect(screen.getByText(t("messages.overviewPriorityLabel"))).toBeTruthy();
    expect(screen.getByText(t("messages.overviewReadLabel"))).toBeTruthy();
    expect(screen.getByText(t("messages.overviewNextStepLabel"))).toBeTruthy();

    fireEvent.click(screen.getByText(t("messages.taskShortcutTitle")));
    fireEvent.click(screen.getByText(t("messages.supportShortcutTitle")));

    expect(onNavigate).toHaveBeenNthCalledWith(1, "/h5/tasks");
    expect(onNavigate).toHaveBeenNthCalledWith(2, "/h5/tickets/new");
  });

  it("uses dedicated message category tone classes inside the detail overlay instead of inline colors", async () => {
    const { MessagesPage } = await import("./MessagesPage");

    const { container } = render(
      <MessagesPage
        messages={[
          {
            id: "msg-support",
            category: "support",
            title: "Support update",
            body: "A new reply is waiting",
            createdAt: "2026-06-23T08:00:00.000Z",
            isRead: false,
          },
        ]}
        unreadMessageCount={1}
        actionName={null}
        siteKey="mall-cn"
        loading={false}
        error={null}
        currentPage={1}
        totalMessages={1}
        onMarkAllRead={vi.fn().mockResolvedValue(undefined)}
        onOpenMessage={vi.fn().mockResolvedValue(undefined)}
        onNavigate={() => undefined}
        onPageChange={() => undefined}
        onRetry={() => undefined}
      />,
    );

    fireEvent.click(screen.getByText("Support update"));

    const categoryBadge = container.querySelector(".h5-member-msg-detail-category");

    expect(categoryBadge?.className).toContain("h5-member-msg-detail-category-support");
    expect(categoryBadge?.getAttribute("style")).toBeNull();
  });

  it("does not render a duplicate in-page mark all read button when the shell owns the primary action", async () => {
    const { MessagesPage } = await import("./MessagesPage");

    render(
      <MessagesPage
        messages={[
          {
            id: "msg-wallet",
            category: "wallet",
            title: "Wallet reminder",
            body: "Balance changed",
            createdAt: "2026-06-23T09:00:00.000Z",
            isRead: false,
          },
        ]}
        unreadMessageCount={1}
        actionName={null}
        siteKey="mall-cn"
        loading={false}
        error={null}
        currentPage={1}
        totalMessages={1}
        onMarkAllRead={vi.fn().mockResolvedValue(undefined)}
        onOpenMessage={vi.fn().mockResolvedValue(undefined)}
        onNavigate={() => undefined}
        onPageChange={() => undefined}
        onRetry={() => undefined}
      />,
    );

    expect(screen.queryByRole("button", { name: t("messages.markAllRead") })).toBeNull();
  });

  it("formats archived message dates with the current locale instead of a hardcoded locale", async () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-06-23T12:00:00.000Z"));
    storage.set("h5-lang", "en-US");

    const { MessagesPage } = await import("./MessagesPage");
    const onOpenMessage = vi.fn().mockResolvedValue(undefined);
    const archivedAt = "2026-04-01T08:00:00.000Z";

    render(
      <MessagesPage
        messages={[
          {
            id: "msg-archived",
            category: "system",
            title: "Archive notice",
            body: "Older messages should still respect the selected locale.",
            createdAt: archivedAt,
            isRead: true,
          },
        ]}
        unreadMessageCount={0}
        actionName={null}
        siteKey="mall-us"
        loading={false}
        error={null}
        currentPage={1}
        totalMessages={1}
        onMarkAllRead={vi.fn().mockResolvedValue(undefined)}
        onOpenMessage={onOpenMessage}
        onNavigate={() => undefined}
        onPageChange={() => undefined}
        onRetry={() => undefined}
      />,
    );

    fireEvent.click(screen.getByText("Archive notice"));

    const expectedDate = new Intl.DateTimeFormat("en-US", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    }).format(new Date(archivedAt));

    expect(screen.getByText(expectedDate)).toBeTruthy();
    vi.useRealTimers();
  });

  it("styles unread message badges as spaced pills instead of concatenated title text", () => {
    const css = readFileSync("src/styles/h5-member.css", "utf8");

    expect(css).toMatch(/\.h5-member-message-feed-title\s*\{[\s\S]*display:\s*flex/);
    expect(css).toMatch(/\.h5-member-message-feed-title\s*\{[\s\S]*gap:\s*6px/);
    expect(css).toMatch(/\.h5-member-message-unread-dot\s*\{[\s\S]*display:\s*inline-flex/);
    expect(css).toMatch(/\.h5-member-message-unread-dot\s*\{[\s\S]*border-radius:\s*999px/);
  });

  it("does not trigger pull-to-refresh when the message detail overlay is open", async () => {
    const { MessagesPage } = await import("./MessagesPage");
    const onPageChange = vi.fn();
    const shell = document.createElement("div");
    shell.className = "h5-member-app-shell";
    Object.defineProperty(shell, "scrollTop", {
      configurable: true,
      get: () => 0,
    });
    document.body.appendChild(shell);

    const view = render(
      <MessagesPage
        messages={[
          {
            id: "msg-task",
            category: "task",
            title: "Task update",
            body: "Complete your current package",
            createdAt: "2026-06-23T08:00:00.000Z",
            isRead: false,
          },
        ]}
        unreadMessageCount={1}
        actionName={null}
        siteKey="mall-cn"
        loading={false}
        error={null}
        currentPage={1}
        totalMessages={1}
        onMarkAllRead={vi.fn().mockResolvedValue(undefined)}
        onOpenMessage={vi.fn().mockResolvedValue(undefined)}
        onNavigate={() => undefined}
        onPageChange={onPageChange}
        onRetry={() => undefined}
      />,
      { container: shell },
    );

    fireEvent.click(screen.getByText("Task update"));
    const detailPanel = document.querySelector(".h5-member-msg-detail-panel") as HTMLElement;

    fireEvent.touchStart(detailPanel, { touches: [{ clientY: 100 }] });
    fireEvent.touchMove(detailPanel, { touches: [{ clientY: 240 }] });
    fireEvent.touchEnd(detailPanel);

    await waitFor(() => {
      expect(onPageChange).not.toHaveBeenCalled();
    });

    view.unmount();
    shell.remove();
  });
});

describe("Verification helpers", () => {
  it("maps non-submitted verification requests to the not-submitted label instead of other", async () => {
    storage.set("h5-lang", "en-US");
    const { getVerificationRequestStatusLabel } = await import("./shared");

    expect(getVerificationRequestStatusLabel("not_submitted")).toBe("Not Submitted");
  });
});

describe("VerificationPage", () => {
  afterEach(() => {
    cleanup();
  });

  it("hides the resubmission form while an active verification request is under review", async () => {
    storage.set("h5-lang", "en-US");
    const { VerificationPage } = await import("./VerificationPage");

    const activeRequest = {
      id: "vr-under-review",
      requestType: "identity",
      status: "under_review",
      notes: "Please review my submitted identity documents.",
      reviewNote: null,
      reviewerActorId: null,
      reviewedAt: null,
      createdAt: "2026-06-23T09:00:00.000Z",
      updatedAt: "2026-06-23T09:05:00.000Z",
      documents: [],
    } as any;

    render(
      <VerificationPage
        effectiveVerificationSummary={{
          currentStatus: "under_review",
          hasActiveRequest: true,
          activeRequest,
          history: [activeRequest],
        }}
        verificationRequests={[activeRequest]}
        verificationRequestDetail={activeRequest}
        verificationHistory={[activeRequest]}
        verificationNotes=""
        focusedVerificationRequest={activeRequest}
        canSubmitVerificationRequest={false}
        verificationActionId={null}
        siteKey="mall-cn"
        onNavigate={vi.fn()}
        onSubmitVerification={vi.fn().mockResolvedValue(undefined)}
        onOpenVerificationRequest={vi.fn().mockResolvedValue(undefined)}
        onVerificationNotesChange={vi.fn()}
        verificationName=""
        verificationIdNumber=""
        actionName={null}
        onSubmitVerificationApi={vi.fn().mockResolvedValue(undefined)}
        onVerificationNameChange={vi.fn()}
        onVerificationIdNumberChange={vi.fn()}
        onVerificationPhotoFilesChange={vi.fn()}
      />,
    );

    expect(screen.queryByRole("button", { name: t("verification.submitRequestBtn") })).toBeNull();

    const currentRequestHeading = screen.getByText(t("verification.currentRequest"));
    const historyHeading = screen.getByText(t("verification.applicationHistory"));
    expect(currentRequestHeading.compareDocumentPosition(historyHeading)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
    expect(screen.getByText("Please review my submitted identity documents.")).toBeTruthy();
  });
});

describe("OrdersPage", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders the processing filter and forwards the processing status selection", async () => {
    const { OrdersPage } = await import("./OrdersPage");
    const onSetOrderFilter = vi.fn();

    render(
      <OrdersPage
        filteredOrders={[
          {
            id: "order-processing",
            orderNo: "ORD-PROCESSING",
            packageId: "pkg-1",
            packageTitle: "Growth Package",
            productName: "Processing Product",
            amount: 20,
            currency: "USD",
            status: "processing",
            createdAt: "2026-06-23T09:00:00.000Z",
            sourceLabel: "Growth Package",
          },
        ]}
        orderFilter="all"
        siteKey="mall-cn"
        onNavigate={() => undefined}
        onSetOrderFilter={onSetOrderFilter}
        ordersLoading={false}
        ordersError={null}
        ordersPage={1}
        ordersTotal={1}
        onOrderPageChange={() => undefined}
        onRetryOrders={() => undefined}
      />,
    );

    const processingFilter = screen.getByRole("button", { name: t("orders.filterProcessing") });
    expect(processingFilter).toBeTruthy();
    expect(screen.getAllByText(t("orders.badgeProcessing")).length).toBeGreaterThanOrEqual(1);

    fireEvent.click(processingFilter);
    expect(onSetOrderFilter).toHaveBeenCalledWith("processing");
  });

  it("renders english order status badges without leaking chinese labels", async () => {
    storage.set("h5-lang", "en-US");
    const { OrdersPage } = await import("./OrdersPage");

    render(
      <OrdersPage
        filteredOrders={[
          {
            id: "order-processing-en",
            orderNo: "ORD-PROCESSING-EN",
            packageId: "pkg-1",
            packageTitle: "Growth Package",
            productName: "Processing Product",
            amount: 20,
            currency: "USD",
            status: "processing",
            createdAt: "2026-06-23T09:00:00.000Z",
            sourceLabel: "Growth Package",
          },
          {
            id: "order-pending-en",
            orderNo: "ORD-PENDING-EN",
            packageId: "pkg-2",
            packageTitle: "Growth Package",
            productName: "Pending Product",
            amount: 22,
            currency: "USD",
            status: "pending",
            createdAt: "2026-06-23T10:00:00.000Z",
            sourceLabel: "Growth Package",
          },
        ]}
        orderFilter="all"
        siteKey="mall-us"
        onNavigate={() => undefined}
        onSetOrderFilter={vi.fn()}
        ordersLoading={false}
        ordersError={null}
        ordersPage={1}
        ordersTotal={2}
        onOrderPageChange={() => undefined}
        onRetryOrders={() => undefined}
      />,
    );

    expect(screen.getAllByText("Processing").length).toBeGreaterThanOrEqual(2);
    expect(screen.queryByText(/处理中/)).toBeNull();
  });

  it("surfaces an order overview and resolution shortcuts before filters and order rows", async () => {
    storage.set("h5-lang", "en-US");
    const { OrdersPage } = await import("./OrdersPage");
    const onNavigate = vi.fn();

    render(
      <OrdersPage
        filteredOrders={[
          {
            id: "order-paid",
            orderNo: "ORD-PAID",
            packageId: "pkg-1",
            packageTitle: "Growth Package",
            productName: "Paid Product",
            amount: 32,
            currency: "USD",
            status: "paid",
            createdAt: "2026-06-23T09:00:00.000Z",
            sourceLabel: "Growth Package",
          },
          {
            id: "order-processing",
            orderNo: "ORD-PROCESSING",
            packageId: "pkg-2",
            packageTitle: "Promotion Package",
            productName: "Processing Product",
            amount: 20,
            currency: "USD",
            status: "processing",
            createdAt: "2026-06-23T10:00:00.000Z",
            sourceLabel: "Promotion Package",
          },
          {
            id: "order-failed",
            orderNo: "ORD-FAILED",
            packageId: "pkg-3",
            packageTitle: "Rookie Package",
            productName: "Failed Product",
            amount: 12,
            currency: "USD",
            status: "failed",
            createdAt: "2026-06-23T11:00:00.000Z",
            sourceLabel: "Rookie Package",
          },
        ]}
        orderFilter="all"
        siteKey="mall-us"
        onNavigate={onNavigate}
        onSetOrderFilter={vi.fn()}
        ordersLoading={false}
        ordersError={null}
        ordersPage={1}
        ordersTotal={3}
        onOrderPageChange={() => undefined}
        onRetryOrders={() => undefined}
      />,
    );

    const overviewHeading = screen.getByText(t("orders.overviewTitle"));
    const overviewCard = overviewHeading.closest("article");
    const filtersHeading = screen.getByRole("button", { name: t("orders.filterAll") });
    const firstOrder = screen.getByText("Paid Product");

    expect(overviewHeading.compareDocumentPosition(filtersHeading)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
    expect(filtersHeading.compareDocumentPosition(firstOrder)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
    expect(overviewCard?.textContent).toContain(t("orders.overviewPaidLabel"));
    expect(overviewCard?.textContent).toContain(t("orders.overviewProcessingLabel"));
    expect(overviewCard?.textContent).toContain(t("orders.overviewFailedLabel"));
    expect(overviewCard?.textContent).toContain(t("orders.overviewNextStepLabel"));

    fireEvent.click(screen.getByText(t("orders.overviewTaskShortcutTitle")));
    fireEvent.click(screen.getByText(t("orders.overviewSupportShortcutTitle")));

    expect(onNavigate).toHaveBeenNthCalledWith(1, "/h5/tasks");
    expect(onNavigate).toHaveBeenNthCalledWith(2, "/h5/tickets/new");
  });

  it("stacks order filters into a compact multi-row layout on ultra-narrow phones", () => {
    const css = readFileSync("src/styles/h5-member.css", "utf8");

    expect(css).toMatch(/@media \(max-width:\s*360px\)[\s\S]*\.h5-member-orders-filters\s*\{[\s\S]*flex-wrap:\s*wrap/);
    expect(css).toMatch(/@media \(max-width:\s*360px\)[\s\S]*\.h5-member-orders-filters\s*\{[\s\S]*overflow-x:\s*visible/);
    expect(css).toMatch(/@media \(max-width:\s*360px\)[\s\S]*\.h5-member-orders-filters \.h5-member-segmented-chip\s*\{[\s\S]*flex:\s*1 1 calc\(50% - 8px\)/);
    expect(css).toMatch(/@media \(max-width:\s*360px\)[\s\S]*\.h5-member-orders-filters \.h5-member-segmented-chip\s*\{[\s\S]*min-width:\s*0/);
  });

  it("wraps order filters by 420px so english status chips stay inside the viewport", () => {
    const css = readFileSync("src/styles/h5-member.css", "utf8");
    const media420Block =
      css.match(/@media \(max-width:\s*420px\)\s*\{([\s\S]*?)\n\}/)?.[1] ?? "";

    expect(media420Block).toMatch(/\.h5-member-orders-filters\s*\{[\s\S]*flex-wrap:\s*wrap/);
    expect(media420Block).toMatch(/\.h5-member-orders-filters \.h5-member-segmented-chip\s*\{[\s\S]*flex:\s*1 1 calc\(50% - 8px\)/);
    expect(media420Block).toMatch(/\.h5-member-orders-filters \.h5-member-segmented-chip\s*\{[\s\S]*min-width:\s*0/);
  });

  it("pull-to-refresh on orders returns to page one instead of replaying the local filter on later pages", async () => {
    const { OrdersPage } = await import("./OrdersPage");
    const onSetOrderFilter = vi.fn();
    const onOrderPageChange = vi.fn();
    const shell = document.createElement("div");
    shell.className = "h5-member-app-shell";
    Object.defineProperty(shell, "scrollTop", {
      configurable: true,
      get: () => 0,
    });
    document.body.appendChild(shell);

    const view = render(
      <OrdersPage
        filteredOrders={[
          {
            id: "order-processing",
            orderNo: "ORD-PROCESSING",
            packageId: "pkg-1",
            packageTitle: "Growth Package",
            productName: "Processing Product",
            amount: 20,
            currency: "USD",
            status: "processing",
            createdAt: "2026-06-23T09:00:00.000Z",
            sourceLabel: "Growth Package",
          },
        ]}
        orderFilter="processing"
        siteKey="mall-cn"
        onNavigate={() => undefined}
        onSetOrderFilter={onSetOrderFilter}
        ordersLoading={false}
        ordersError={null}
        ordersPage={3}
        ordersTotal={60}
        onOrderPageChange={onOrderPageChange}
        onRetryOrders={() => undefined}
      />,
      { container: shell },
    );

    const pullWrapper = document.querySelector(".h5-pull-shell") as HTMLElement;

    fireEvent.touchStart(pullWrapper, { touches: [{ clientY: 100 }] });
    fireEvent.touchMove(pullWrapper, { touches: [{ clientY: 240 }] });
    fireEvent.touchEnd(pullWrapper);

    await waitFor(() => {
      expect(onOrderPageChange).toHaveBeenCalledWith(1);
    });
    expect(onSetOrderFilter).not.toHaveBeenCalled();

    view.unmount();
    shell.remove();
  });

  it("lets ultra-narrow list rows wrap translated titles and stack side rails", () => {
    const css = readFileSync("src/styles/h5-member.css", "utf8");

    expect(css).toMatch(/@media \(max-width:\s*360px\)[\s\S]*\.h5-member-list-row\s*\{[\s\S]*align-items:\s*flex-start/);
    expect(css).toMatch(/@media \(max-width:\s*360px\)[\s\S]*\.h5-member-list-row-title strong\s*\{[\s\S]*white-space:\s*normal/);
    expect(css).toMatch(/@media \(max-width:\s*360px\)[\s\S]*\.h5-member-list-row-side\s*\{[\s\S]*width:\s*100%/);
    expect(css).toMatch(/@media \(max-width:\s*360px\)[\s\S]*\.h5-member-list-row-side\s*\{[\s\S]*align-items:\s*flex-start/);
  });
});

describe("TasksPage", () => {
  afterEach(() => {
    cleanup();
  });

  it("prioritizes in-progress work above the sign-in card when active tasks exist", async () => {
    storage.set("h5-lang", "en-US");
    const { TasksPage } = await import("./TasksPage");

    render(
      <TasksPage
        signInStatus={{
          consecutiveDays: 3,
          todaySignedIn: false,
          goalDays: 7,
          goalReward: 5,
          isCompleted: false,
        }}
        taskInstances={[
          {
            id: "pkg-active",
            title: "Active Growth Package",
            description: "desc",
            type: "growth",
            status: "active",
            rewardRatio: 0.18,
            rewardAmount: 36,
            products: [],
            completedCount: 1,
            totalCount: 3,
            systemBalance: 120,
            currentCommission: 12,
            totalCommission: 36,
            countdownSeconds: 7200,
            completionWindowHours: 24,
          } as any,
        ]}
        actionName={null}
        loading={false}
        error={null}
        onSignIn={vi.fn().mockResolvedValue(undefined)}
        onNavigate={vi.fn()}
        onRefresh={vi.fn().mockResolvedValue(undefined)}
        onOpenClaimDialog={vi.fn()}
      />,
    );

    const inProgressHeading = screen.getByRole("heading", { name: /In Progress/i, level: 4 });
    const signInButton = screen.getByRole("button", { name: t("tasks.signIn") });

    expect(inProgressHeading.compareDocumentPosition(signInButton)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
  });

  it("renders task cards with only batch progress, title, status, estimated reward, and the primary action", async () => {
    storage.set("h5-lang", "en-US");
    const { TasksPage } = await import("./TasksPage");
    const onOpenClaimDialog = vi.fn();

    render(
      <TasksPage
        signInStatus={{
          consecutiveDays: 3,
          todaySignedIn: false,
          goalDays: 7,
          goalReward: 5,
          isCompleted: false,
        }}
        taskInstances={[
          {
            id: "pkg-pending",
            title: "Growth Package",
            description: "desc",
            type: "growth",
            status: "pending_claim",
            rewardRatio: 0.18,
            rewardAmount: 36,
            products: [],
            batchIndex: 1,
            batchTotal: 5,
            completedCount: 0,
            totalCount: 3,
            systemBalance: 120,
            currentCommission: 0,
            totalCommission: 36,
            countdownSeconds: 7200,
            completionWindowHours: 24,
          } as any,
        ]}
        actionName={null}
        loading={false}
        error={null}
        onSignIn={vi.fn().mockResolvedValue(undefined)}
        onNavigate={() => undefined}
        onRefresh={vi.fn().mockResolvedValue(undefined)}
        onOpenClaimDialog={onOpenClaimDialog as any}
      />,
    );

    const taskCard = document.querySelector(".h5-task-instance-card");
    expect(taskCard).toBeTruthy();
    expect(taskCard?.textContent).toContain("Today's Task 1/5");
    expect(taskCard?.textContent).toContain("Growth Package");
    expect(taskCard?.textContent).toContain(t("tasks.groupAvailable"));
    expect(taskCard?.textContent).toContain("Est. Reward: $36.00");
    expect(taskCard?.textContent).not.toContain(t("tasks.remainingTime"));
    expect(taskCard?.textContent).not.toContain(t("tasks.totalCommission"));
    expect(taskCard?.textContent).not.toContain("Reward Ratio");
    expect(taskCard?.textContent).not.toContain("item(s)");
    expect(screen.getByRole("button", { name: t("tasks.signIn") }).getAttribute("title")).toBe(t("tasks.signIn"));

    fireEvent.click(screen.getAllByRole("button", { name: t("tasks.claim") })[0]);
    expect(onOpenClaimDialog).toHaveBeenCalledWith({ id: "pkg-pending", title: "Growth Package" });
  });

  it("surfaces a single execution focus card before the sign-in and overview blocks", async () => {
    storage.set("h5-lang", "en-US");
    const { TasksPage } = await import("./TasksPage");
    const onNavigate = vi.fn();

    render(
      <TasksPage
        signInStatus={{
          consecutiveDays: 3,
          todaySignedIn: false,
          goalDays: 7,
          goalReward: 5,
          isCompleted: false,
        }}
        taskInstances={[
          {
            id: "pkg-active",
            title: "Active Growth Package",
            description: "desc",
            type: "growth",
            status: "active",
            rewardRatio: 0.18,
            rewardAmount: 36,
            products: [],
            completedCount: 1,
            totalCount: 3,
            systemBalance: 120,
            currentCommission: 12,
            totalCommission: 36,
            countdownSeconds: 7200,
            completionWindowHours: 24,
          } as any,
          {
            id: "pkg-pending",
            title: "Pending Growth Package",
            description: "desc",
            type: "growth",
            status: "pending_claim",
            rewardRatio: 0.12,
            rewardAmount: 28,
            products: [],
            completedCount: 0,
            totalCount: 2,
            systemBalance: 120,
            currentCommission: 0,
            totalCommission: 28,
            countdownSeconds: 5400,
            completionWindowHours: 24,
          } as any,
        ]}
        actionName={null}
        loading={false}
        error={null}
        onSignIn={vi.fn().mockResolvedValue(undefined)}
        onNavigate={onNavigate}
        onRefresh={vi.fn().mockResolvedValue(undefined)}
        onOpenClaimDialog={vi.fn()}
      />,
    );

    const focusHeading = screen.getByText(t("tasks.focusTitle"));
    const signInButton = screen.getByRole("button", { name: t("tasks.signIn") });
    const overviewHeading = screen.getByText(t("tasks.overviewTitle"));

    expect(focusHeading.compareDocumentPosition(signInButton)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
    expect(signInButton.compareDocumentPosition(overviewHeading)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
    expect(screen.getByText(t("tasks.focusMeta"))).toBeTruthy();
    expect(screen.getByRole("button", { name: t("home.actionContinue") })).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: t("home.actionContinue") }));
    expect(onNavigate).toHaveBeenCalledWith("/h5/tasks/package/pkg-active");
  });

  it("uses dedicated task error and action spacing classes without restoring deprecated task-card progress chrome", async () => {
    storage.set("h5-lang", "en-US");
    const { TasksPage } = await import("./TasksPage");

    const { container } = render(
      <TasksPage
        signInStatus={{
          consecutiveDays: 7,
          todaySignedIn: true,
          goalDays: 7,
          goalReward: 5,
          isCompleted: true,
        }}
        taskInstances={[
          {
            id: "pkg-active",
            title: "Active Growth Package",
            description: "desc",
            type: "growth",
            status: "active",
            rewardRatio: 0.18,
            rewardAmount: 36,
            products: [],
            completedCount: 1,
            totalCount: 3,
            systemBalance: 120,
            currentCommission: 12,
            totalCommission: 36,
            countdownSeconds: 7200,
            completionWindowHours: 24,
          } as any,
        ]}
        actionName={null}
        loading={false}
        error="Task center temporarily unavailable"
        onSignIn={vi.fn().mockResolvedValue(undefined)}
        onNavigate={vi.fn()}
        onRefresh={vi.fn().mockResolvedValue(undefined)}
        onOpenClaimDialog={vi.fn()}
      />,
    );

    expect(container.querySelector(".h5-signin-progress-fill-complete")).toBeTruthy();
    expect(container.querySelector(".h5-task-card-progress")).toBeNull();
    expect(container.querySelector(".h5-task-card-actions")).toBeTruthy();
    expect(container.querySelector(".h5-task-error-copy")).toBeTruthy();
  });
});

describe("PackageDetailPage", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    cleanup();
  });

  it("keeps a failed purchase visible and shows retry/contact actions", async () => {
    const { PackageDetailPage } = await import("./PackageDetailPage");
    const onStartProduct = vi.fn().mockRejectedValue(new Error("璐拱澶辫触锛岃绋嶅悗閲嶈瘯"));
    const onRetryProduct = vi.fn().mockResolvedValue({ success: true });
    const onNavigate = vi.fn();

    render(
      <PackageDetailPage
        instance={{
          id: "pkg-1",
          title: "Task package",
          description: "desc",
          type: "growth",
          status: "active",
          rewardRatio: 0.1,
          rewardAmount: 10,
          completedCount: 0,
          totalCount: 1,
          systemBalance: 100,
          currentProduct: {
            id: "prod-1",
            productName: "Product 1",
            imageUrl: "",
            price: 20,
            currency: "USD",
            status: "available",
          },
          products: [
            {
              id: "prod-1",
              productName: "Product 1",
              imageUrl: "",
              price: 20,
              currency: "USD",
              status: "available",
            },
          ],
        }}
        actionName={null}
        onStartProduct={onStartProduct}
        onRetryProduct={onRetryProduct}
        onNavigate={onNavigate}
        onRefresh={vi.fn().mockResolvedValue(undefined)}
      />,
    );

    expect(screen.getByRole("button", { name: t("tasks.productAvailable") }).getAttribute("title")).toBe(t("tasks.productAvailable"));

    fireEvent.click(screen.getByRole("button", { name: t("tasks.productAvailable") }));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2400);
    });

    expect(screen.getByText("璐拱澶辫触锛岃绋嶅悗閲嶈瘯")).toBeTruthy();
    expect(screen.getByRole("button", { name: t("purchase.actionRetry") })).toBeTruthy();
    expect(screen.getByRole("button", { name: t("purchase.actionContact") })).toBeTruthy();
    expect(onStartProduct).toHaveBeenCalledWith("prod-1");
  });

  it("routes timeout-style failure back to task center", async () => {
    const { PackageDetailPage } = await import("./PackageDetailPage");
    const onStartProduct = vi.fn().mockRejectedValue(new Error("浠诲姟鍖呭凡瓒呮椂浣滃簾"));
    const onNavigate = vi.fn();

    render(
      <PackageDetailPage
        instance={{
          id: "pkg-2",
          title: "Task package",
          description: "desc",
          type: "growth",
          status: "active",
          rewardRatio: 0.1,
          rewardAmount: 10,
          completedCount: 0,
          totalCount: 1,
          systemBalance: 100,
          currentProduct: {
            id: "prod-2",
            productName: "Product 2",
            imageUrl: "",
            price: 20,
            currency: "USD",
            status: "available",
          },
          products: [
            {
              id: "prod-2",
              productName: "Product 2",
              imageUrl: "",
              price: 20,
              currency: "USD",
              status: "available",
            },
          ],
        }}
        actionName={null}
        onStartProduct={onStartProduct}
        onRetryProduct={vi.fn().mockResolvedValue({ success: true })}
        onNavigate={onNavigate}
        onRefresh={vi.fn().mockResolvedValue(undefined)}
      />,
    );

    expect(screen.getByRole("button", { name: t("tasks.productAvailable") }).getAttribute("title")).toBe(t("tasks.productAvailable"));

    fireEvent.click(screen.getByRole("button", { name: t("tasks.productAvailable") }));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2400);
    });

    fireEvent.click(screen.getAllByRole("button", { name: t("purchase.actionBackToTasks") }).at(-1)!);
    expect(onNavigate).toHaveBeenCalledWith("/h5/tasks");
  });

  it("renders summary metrics for remaining items, commission, and countdown", async () => {
    const { PackageDetailPage } = await import("./PackageDetailPage");

    render(
      <PackageDetailPage
        instance={{
          id: "pkg-summary",
          title: "Growth Package",
          description: "desc",
          type: "growth",
          status: "active",
          rewardRatio: 0.12,
          rewardAmount: 48,
          completedCount: 1,
          totalCount: 4,
          systemBalance: 100,
          currentCommission: 12,
          totalCommission: 48,
          countdownSeconds: 3661,
          products: [
            {
              id: "prod-1",
              productName: "Product 1",
              imageUrl: "",
              price: 20,
              currency: "USD",
              status: "completed",
            },
            {
              id: "prod-2",
              productName: "Product 2",
              imageUrl: "",
              price: 28,
              currency: "USD",
              status: "available",
            },
          ],
        } as any}
        actionName={null}
        onStartProduct={vi.fn().mockResolvedValue({ success: true })}
        onRetryProduct={vi.fn().mockResolvedValue({ success: true })}
        onNavigate={vi.fn()}
        onRefresh={vi.fn().mockResolvedValue(undefined)}
      />,
    );

    expect(screen.getByText(t("tasks.remainingItems"))).toBeTruthy();
    expect(screen.getAllByText(t("tasks.expectedCommission")).length).toBeGreaterThan(0);
    expect(screen.getAllByText(t("tasks.countdown")).length).toBeGreaterThan(0);
    expect(screen.getByText("01:01:01")).toBeTruthy();
    expect(screen.getByText(/Current Commission/)).toBeTruthy();
  });

  it("shows task amount breakdown without surfacing the manual adjustment notice copy", async () => {
    storage.set("h5-lang", "en-US");
    const { PackageDetailPage } = await import("./PackageDetailPage");

    render(
      <PackageDetailPage
        instance={{
          id: "pkg-adjusted",
          title: "Growth Package",
          description: "desc",
          type: "growth",
          status: "active",
          rewardRatio: 0.12,
          rewardAmount: 48,
          plannedAmount: 50,
          systemGeneratedAmount: 50,
          manualAddedAmount: 26,
          effectiveAmount: 76,
          hasAdjustmentNotice: true,
          adjustmentNotice: "Task updated. Newly added items are now included in this package.",
          completedCount: 1,
          totalCount: 3,
          systemBalance: 100,
          currentCommission: 12,
          totalCommission: 48,
          countdownSeconds: 3661,
          currentProduct: {
            id: "prod-2",
            productName: "Product 2",
            imageUrl: "",
            price: 28,
            currency: "USD",
            status: "available",
          },
          products: [
            {
              id: "prod-1",
              productName: "Product 1",
              imageUrl: "",
              price: 20,
              currency: "USD",
              status: "completed",
            },
            {
              id: "prod-2",
              productName: "Product 2",
              imageUrl: "",
              price: 28,
              currency: "USD",
              status: "available",
            },
          ],
        } as any}
        actionName={null}
        onStartProduct={vi.fn().mockResolvedValue({ success: true })}
        onRetryProduct={vi.fn().mockResolvedValue({ success: true })}
        onNavigate={vi.fn()}
        onRefresh={vi.fn().mockResolvedValue(undefined)}
      />,
    );

    expect(screen.getByText(/Planned Amount/i)).toBeTruthy();
    expect(screen.getByText(/System Amount/i)).toBeTruthy();
    expect(screen.getByText(/Manual Add Amount/i)).toBeTruthy();
    expect(screen.getByText(/Effective Amount/i)).toBeTruthy();
    expect(screen.getAllByText("$50.00").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("$26.00")).toBeTruthy();
    expect(screen.getByText("$76.00")).toBeTruthy();
    expect(screen.queryByText("Task updated. Newly added items are now included in this package.")).toBeNull();
  });

  it("renders reward summary, completion steps, and notes support sections in order", async () => {
    const { PackageDetailPage } = await import("./PackageDetailPage");
    const onNavigate = vi.fn();

    render(
      <PackageDetailPage
        instance={{
          id: "pkg-structure",
          title: "Growth Package",
          description: "desc",
          type: "growth",
          status: "active",
          rewardRatio: 0.12,
          rewardAmount: 48,
          completedCount: 1,
          totalCount: 4,
          systemBalance: 100,
          currentCommission: 12,
          totalCommission: 48,
          countdownSeconds: 3661,
          products: [
            {
              id: "prod-1",
              productName: "Product 1",
              imageUrl: "",
              price: 20,
              currency: "USD",
              status: "completed",
            },
            {
              id: "prod-2",
              productName: "Product 2",
              imageUrl: "",
              price: 28,
              currency: "USD",
              status: "available",
            },
          ],
        } as any}
        actionName={null}
        onStartProduct={vi.fn().mockResolvedValue({ success: true })}
        onRetryProduct={vi.fn().mockResolvedValue({ success: true })}
        onNavigate={onNavigate}
        onRefresh={vi.fn().mockResolvedValue(undefined)}
      />,
    );

    const rewardHeading = screen.getByText(t("tasks.detailRewardSummary"));
    const stepsHeading = screen.getByText(t("tasks.detailCompletionSteps"));
    const supportHeading = screen.getByText(t("tasks.detailSupport"));

    expect(rewardHeading.compareDocumentPosition(stepsHeading)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
    expect(stepsHeading.compareDocumentPosition(supportHeading)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
    expect(screen.getByText(t("tasks.detailRewardArrival"))).toBeTruthy();
    expect(screen.getByText(t("tasks.detailSupportHint"))).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: t("tasks.contactSupport") }));
    expect(onNavigate).toHaveBeenCalledWith("/h5/tickets/new");
  });

  it("renders only the current product card when currentProduct is provided", async () => {
    const { PackageDetailPage } = await import("./PackageDetailPage");

    render(
      <PackageDetailPage
        instance={{
          id: "pkg-current-only",
          title: "Growth Package",
          description: "desc",
          type: "growth",
          status: "active",
          rewardRatio: 0.12,
          rewardAmount: 48,
          completedCount: 1,
          totalCount: 4,
          systemBalance: 100,
          currentCommission: 12,
          totalCommission: 48,
          countdownSeconds: 3661,
          batchIndex: 2,
          batchTotal: 5,
          currentProduct: {
            id: "prod-2",
            productName: "Product 2",
            imageUrl: "",
            price: 28,
            currency: "USD",
            status: "available",
          },
          products: [
            {
              id: "prod-1",
              productName: "Product 1",
              imageUrl: "",
              price: 20,
              currency: "USD",
              status: "completed",
            },
            {
              id: "prod-2",
              productName: "Product 2",
              imageUrl: "",
              price: 28,
              currency: "USD",
              status: "available",
            },
            {
              id: "prod-3",
              productName: "Product 3",
              imageUrl: "",
              price: 30,
              currency: "USD",
              status: "pending",
            },
          ],
        } as any}
        actionName={null}
        onStartProduct={vi.fn().mockResolvedValue({ success: true })}
        onRetryProduct={vi.fn().mockResolvedValue({ success: true })}
        onNavigate={vi.fn()}
        onRefresh={vi.fn().mockResolvedValue(undefined)}
      />,
    );

    expect(screen.getByText("Product 2")).toBeTruthy();
    expect(screen.queryByText("Product 1")).toBeNull();
    expect(screen.queryByText("Product 3")).toBeNull();
    expect(screen.getByText("2/5")).toBeTruthy();
  });

  it("shows a waiting hint instead of a blank product area when no current product is available yet", async () => {
    storage.set("h5-lang", "en-US");
    const { PackageDetailPage } = await import("./PackageDetailPage");

    render(
      <PackageDetailPage
        instance={{
          id: "pkg-waiting-product",
          title: "Growth Package",
          description: "desc",
          type: "growth",
          status: "active",
          rewardRatio: 0.12,
          rewardAmount: 48,
          completedCount: 1,
          totalCount: 4,
          systemBalance: 100,
          currentCommission: 12,
          totalCommission: 48,
          countdownSeconds: 3661,
          currentProduct: null,
          products: [
            {
              id: "prod-1",
              productName: "Product 1",
              imageUrl: "",
              price: 20,
              currency: "USD",
              status: "completed",
            },
            {
              id: "prod-2",
              productName: "Product 2",
              imageUrl: "",
              price: 28,
              currency: "USD",
              status: "pending",
            },
          ],
        } as any}
        actionName={null}
        onStartProduct={vi.fn().mockResolvedValue({ success: true })}
        onRetryProduct={vi.fn().mockResolvedValue({ success: true })}
        onNavigate={vi.fn()}
        onRefresh={vi.fn().mockResolvedValue(undefined)}
      />,
    );

    expect(screen.getAllByText(t("tasks.detailWaitingNextTask")).length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: t("tasks.productAvailable") })).toBeNull();
    expect(screen.queryByRole("button", { name: t("tasks.productRunning") })).toBeNull();
  });

  it("does not expose a future available product when currentProduct is still null", async () => {
    storage.set("h5-lang", "en-US");
    const { PackageDetailPage } = await import("./PackageDetailPage");

    render(
      <PackageDetailPage
        instance={{
          id: "pkg-hide-future-product",
          title: "Growth Package",
          description: "desc",
          type: "growth",
          status: "active",
          rewardRatio: 0.12,
          rewardAmount: 48,
          completedCount: 1,
          totalCount: 4,
          systemBalance: 100,
          currentCommission: 12,
          totalCommission: 48,
          countdownSeconds: 3661,
          currentProduct: null,
          products: [
            {
              id: "prod-1",
              productName: "Product 1",
              imageUrl: "",
              price: 20,
              currency: "USD",
              status: "completed",
            },
            {
              id: "prod-2",
              productName: "Product 2",
              imageUrl: "",
              price: 28,
              currency: "USD",
              status: "available",
            },
          ],
        } as any}
        actionName={null}
        onStartProduct={vi.fn().mockResolvedValue({ success: true })}
        onRetryProduct={vi.fn().mockResolvedValue({ success: true })}
        onNavigate={vi.fn()}
        onRefresh={vi.fn().mockResolvedValue(undefined)}
      />,
    );

    expect(screen.getAllByText(t("tasks.detailWaitingNextTask")).length).toBeGreaterThan(0);
    expect(screen.queryByText("Product 2")).toBeNull();
    expect(screen.queryByRole("button", { name: t("tasks.productAvailable") })).toBeNull();
  });

  it("surfaces a dedicated task focus card before the reward summary", async () => {
    storage.set("h5-lang", "en-US");
    const { PackageDetailPage } = await import("./PackageDetailPage");

    render(
      <PackageDetailPage
        instance={{
          id: "pkg-focus",
          title: "Growth Package",
          description: "desc",
          type: "growth",
          status: "active",
          rewardRatio: 0.12,
          rewardAmount: 48,
          completedCount: 1,
          totalCount: 4,
          systemBalance: 100,
          currentCommission: 12,
          totalCommission: 48,
          countdownSeconds: 3661,
          currentProduct: {
            id: "prod-1",
            productName: "Product 1",
            imageUrl: "",
            price: 20,
            currency: "USD",
            status: "available",
          },
          products: [
            {
              id: "prod-1",
              productName: "Product 1",
              imageUrl: "",
              price: 20,
              currency: "USD",
              status: "completed",
            },
            {
              id: "prod-2",
              productName: "Product 2",
              imageUrl: "",
              price: 28,
              currency: "USD",
              status: "available",
            },
          ],
        } as any}
        actionName={null}
        onStartProduct={vi.fn().mockResolvedValue({ success: true })}
        onRetryProduct={vi.fn().mockResolvedValue({ success: true })}
        onNavigate={vi.fn()}
        onRefresh={vi.fn().mockResolvedValue(undefined)}
      />,
    );

    const focusHeading = screen.getByText(t("tasks.detailFocusTitle"));
    const rewardHeading = screen.getByText(t("tasks.detailRewardSummary"));

    expect(focusHeading.compareDocumentPosition(rewardHeading)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
    expect(screen.getByText(t("tasks.detailFocusMeta"))).toBeTruthy();
    expect(screen.getByText(t("tasks.detailNextStep"))).toBeTruthy();
    expect(screen.getByText(t("tasks.detailRemainingLabel", { done: 1, total: 4 }))).toBeTruthy();
  });

  it("does not leak mojibake placeholders in reward copy, progress states, or completion states", async () => {
    storage.set("h5-lang", "en-US");
    const { PackageDetailPage } = await import("./PackageDetailPage");

    const activeView = render(
      <PackageDetailPage
        instance={{
          id: "pkg-no-mojibake",
          title: "Growth Package",
          description: "desc",
          type: "growth",
          status: "active",
          rewardRatio: 0.12,
          rewardAmount: 48,
          completedCount: 1,
          totalCount: 4,
          systemBalance: 100,
          currentCommission: 12,
          totalCommission: 48,
          countdownSeconds: 3661,
          currentProduct: {
            id: "prod-1",
            productName: "Product 1",
            imageUrl: "",
            price: 20,
            currency: "USD",
            status: "available",
          },
          products: [
            {
              id: "prod-1",
              productName: "Product 1",
              imageUrl: "",
              price: 20,
              currency: "USD",
              status: "available",
            },
          ],
        } as any}
        actionName={null}
        onStartProduct={vi.fn().mockResolvedValue({ success: true })}
        onRetryProduct={vi.fn().mockResolvedValue({ success: true })}
        onNavigate={vi.fn()}
        onRefresh={vi.fn().mockResolvedValue(undefined)}
      />,
    );

    expect(activeView.container.textContent).not.toMatch(/馃|猬/);

    fireEvent.click(screen.getByRole("button", { name: t("tasks.productAvailable") }));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });

    expect(activeView.container.textContent).not.toMatch(/馃|猬/);
    activeView.unmount();

    const completedView = render(
      <PackageDetailPage
        instance={{
          id: "pkg-complete-clean",
          title: "Growth Package",
          description: "desc",
          type: "growth",
          status: "completed",
          rewardRatio: 0.12,
          rewardAmount: 48,
          completedCount: 1,
          totalCount: 1,
          systemBalance: 100,
          currentCommission: 48,
          totalCommission: 48,
          countdownSeconds: 0,
          products: [
            {
              id: "prod-complete",
              productName: "Product 1",
              imageUrl: "",
              price: 20,
              currency: "USD",
              status: "completed",
            },
          ],
        } as any}
        actionName={null}
        onStartProduct={vi.fn().mockResolvedValue({ success: true })}
        onRetryProduct={vi.fn().mockResolvedValue({ success: true })}
        onNavigate={vi.fn()}
        onRefresh={vi.fn().mockResolvedValue(undefined)}
      />,
    );

    expect(completedView.container.textContent).not.toMatch(/馃|猬/);
  });

  it("routes completed-package balance actions to the earnings wallet path", async () => {
    const { PackageDetailPage } = await import("./PackageDetailPage");
    const onNavigate = vi.fn();

    render(
      <PackageDetailPage
        instance={{
          id: "pkg-complete",
          title: "Growth Package",
          description: "desc",
          type: "growth",
          status: "completed",
          rewardRatio: 0.12,
          rewardAmount: 48,
          completedCount: 4,
          totalCount: 4,
          systemBalance: 100,
          currentCommission: 48,
          totalCommission: 48,
          countdownSeconds: 0,
          products: [
            {
              id: "prod-finish",
              productName: "Finished Product",
              imageUrl: "",
              price: 20,
              currency: "USD",
              status: "completed",
            },
          ],
        } as any}
        actionName={null}
        onStartProduct={vi.fn().mockResolvedValue({ success: true })}
        onRetryProduct={vi.fn().mockResolvedValue({ success: true })}
        onNavigate={onNavigate}
        onRefresh={vi.fn().mockResolvedValue(undefined)}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: t("tasks.viewBalance") }));
    expect(onNavigate).toHaveBeenCalledWith("/h5/wallet");
  });

  it("uses package-specific completion copy instead of a generic success banner", async () => {
    storage.set("h5-lang", "en-US");
    const { PackageDetailPage } = await import("./PackageDetailPage");

    render(
      <PackageDetailPage
        instance={{
          id: "pkg-complete-copy",
          title: "Growth Package",
          description: "desc",
          type: "growth",
          status: "completed",
          rewardRatio: 0.12,
          rewardAmount: 48,
          completedCount: 4,
          totalCount: 4,
          systemBalance: 100,
          currentCommission: 48,
          totalCommission: 48,
          countdownSeconds: 0,
          products: [
            {
              id: "prod-finish",
              productName: "Finished Product",
              imageUrl: "",
              price: 20,
              currency: "USD",
              status: "completed",
            },
          ],
        } as any}
        actionName={null}
        onStartProduct={vi.fn().mockResolvedValue({ success: true })}
        onRetryProduct={vi.fn().mockResolvedValue({ success: true })}
        onNavigate={vi.fn()}
        onRefresh={vi.fn().mockResolvedValue(undefined)}
      />,
    );

    expect(screen.getByText(t("serviceMessages.packageCompletedTitle", { title: "Growth Package" }))).toBeTruthy();
    expect(screen.getByText(t("serviceMessages.packageCompletedBody"))).toBeTruthy();
    expect(screen.queryByText(t("tasks.packageCompleted"))).toBeNull();
  });

  it("preserves full media preview filenames for long uploads", async () => {
    vi.useRealTimers();
    const createObjectUrl = vi.fn(() => "blob:test");
    const revokeObjectUrl = vi.fn();
    Object.defineProperty(URL, "createObjectURL", {
      configurable: true,
      writable: true,
      value: createObjectUrl,
    });
    Object.defineProperty(URL, "revokeObjectURL", {
      configurable: true,
      writable: true,
      value: revokeObjectUrl,
    });

    const { MediaUploader } = await import("./MediaUploader");
    const longFileName = "very-long-proof-of-identity-document-name-2026-06-23-final-review.png";
    const file = new File(["demo"], longFileName, { type: "image/png" });
    const { container } = render(
      <MediaUploader accept="image/*" compress={false} multiple onUpload={() => undefined} />,
    );

    const input = container.querySelector('input[type="file"]') as HTMLInputElement | null;
    expect(input).toBeTruthy();
    fireEvent.change(input!, { target: { files: [file] } });

    await waitFor(() => {
      expect(screen.getByTitle(longFileName)).toBeTruthy();
    });
  });

  it("uses localized purchase fallback copy when a non-error failure occurs", async () => {
    storage.set("h5-lang", "en-US");
    const { PackageDetailPage } = await import("./PackageDetailPage");

    render(
      <PackageDetailPage
        instance={{
          id: "pkg-fallback",
          title: "Task package",
          description: "desc",
          type: "growth",
          status: "active",
          rewardRatio: 0.1,
          rewardAmount: 10,
          completedCount: 0,
          totalCount: 1,
          systemBalance: 100,
          currentProduct: {
            id: "prod-fallback",
            productName: "Product fallback",
            imageUrl: "",
            price: 20,
            currency: "USD",
            status: "available",
          },
          products: [
            {
              id: "prod-fallback",
              productName: "Product fallback",
              imageUrl: "",
              price: 20,
              currency: "USD",
              status: "available",
            },
          ],
        }}
        actionName={null}
        onStartProduct={vi.fn().mockRejectedValue("raw failure")}
        onRetryProduct={vi.fn().mockResolvedValue({ success: true })}
        onNavigate={vi.fn()}
        onRefresh={vi.fn().mockResolvedValue(undefined)}
      />,
    );

    expect(screen.getByRole("button", { name: t("tasks.productAvailable") }).getAttribute("title")).toBe(t("tasks.productAvailable"));

    fireEvent.click(screen.getByRole("button", { name: t("tasks.productAvailable") }));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2400);
    });

    expect(screen.getByText(t("notification.purchaseFailed"))).toBeTruthy();
  });
});

describe("PromotionPage", () => {
  afterEach(() => {
    cleanup();
  });

  it("surfaces a promotion program summary and mobile-safe invitee records instead of table headers", async () => {
    storage.set("h5-lang", "en-US");
    const { PromotionPage } = await import("./PromotionPage");

    render(
      <PromotionPage
        dashboard={{
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
          unreadCount: 1,
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
        }}
        siteKey="mall-cn"
        onNavigate={() => undefined}
        onCopyText={vi.fn().mockResolvedValue(undefined)}
        loading={false}
        error={null}
      />,
    );

    const summaryHeading = screen.getAllByText(t("promotion.programTitle"))[0];
    const actionsHeading = screen.getAllByText(t("promotion.actionsTitle"))[0];
    const recordsHeading = screen.getAllByText(t("promotion.inviteeList"))[0];

    expect(summaryHeading.compareDocumentPosition(actionsHeading)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
    expect(actionsHeading.compareDocumentPosition(recordsHeading)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
    expect(screen.getAllByText(t("promotion.linkGenerated")).length).toBeGreaterThan(0);
    expect(screen.getAllByText(t("promotion.qualifiedRate")).length).toBeGreaterThan(0);
    expect(screen.queryByRole("columnheader", { name: t("promotion.colSequence") })).toBeNull();
    expect(screen.queryByRole("columnheader", { name: t("promotion.colUserId") })).toBeNull();
  });

  it("renders settlement and delay guidance for promotion tasks", async () => {
    storage.set("h5-lang", "en-US");
    const { PromotionPage } = await import("./PromotionPage");

    render(
      <PromotionPage
        dashboard={{
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
          unreadCount: 1,
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
        }}
        siteKey="mall-cn"
        onNavigate={() => undefined}
        onCopyText={vi.fn().mockResolvedValue(undefined)}
        loading={false}
        error={null}
      />,
    );

    expect(screen.getByText(t("promotion.rewardBalance"))).toBeTruthy();
    expect(screen.getByText(t("promotion.rewardBalanceValue"))).toBeTruthy();
    expect(screen.getByText(t("promotion.validityWindow"))).toBeTruthy();
    expect(screen.getByText(t("promotion.delayNotice"))).toBeTruthy();
    expect(screen.getAllByText(t("promotion.followupTitle")).length).toBeGreaterThan(0);
    expect(screen.getAllByText(t("promotion.hasRecharged")).length).toBeGreaterThan(0);
    expect(screen.getAllByText(t("promotion.notRecharged")).length).toBeGreaterThan(0);
  });
});

describe("InvitePage", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders localized stat labels and clean invite record separators in chinese", async () => {
    storage.set("h5-lang", "zh-CN");
    const { InvitePage } = await import("./InvitePage");

    render(
      <InvitePage
        inviteInfo={{
          inviteLink: "https://example.com/invite?code=INV-ABCD1234",
          invitedCount: 12,
          earnedAmount: 36,
          maxInvites: 50,
          remainingInvites: 38,
        }}
        inviteRecords={[
          {
            id: "record-1",
            userIdMasked: "U38***56",
            type: "registration",
            rewardAmount: 2,
            createdAt: "2026-06-23T09:00:00.000Z",
          } as any,
        ]}
        loading={false}
        error={null}
        onCopyText={vi.fn().mockResolvedValue(undefined)}
        onRetry={vi.fn().mockResolvedValue(undefined)}
      />,
    );

    expect(screen.getByText("已邀请")).toBeTruthy();
    expect(screen.getByText("已获得")).toBeTruthy();
    expect(screen.getAllByText(/剩余名额|邀请进度|总名额/).length).toBeGreaterThan(0);
    expect(document.body.textContent).not.toContain("Invited:");
    expect(document.body.textContent).not.toContain("路");
  });
});

describe("InvitePage", () => {
  it("uses localized share copy for WhatsApp share in english", async () => {
    storage.set("h5-lang", "en-US");
    const openSpy = vi.spyOn(window, "open").mockImplementation(() => null);
    const { InvitePage } = await import("./InvitePage");

    render(
      <InvitePage
        inviteInfo={{
          inviteCode: "INV-ABCD1234",
          inviteLink: "https://example.com/invite/INV-ABCD1234",
          invitedCount: 3,
          earnedAmount: 8,
          maxInvites: 20,
          remainingInvites: 17,
        }}
        inviteRecords={[]}
        loading={false}
        error={null}
        onCopyText={vi.fn()}
        onRetry={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: new RegExp(t("tasks.inviteWhatsAppShare")) }));

    expect(openSpy).toHaveBeenCalledWith(
      `https://wa.me/?text=${encodeURIComponent("Join now and earn rewards together!\nhttps://example.com/invite/INV-ABCD1234")}`,
      "_blank",
      "noopener,noreferrer",
    );
  });

  it("does not leak stray currency markers into english invite reward copy", async () => {
    storage.set("h5-lang", "en-US");
    const { InvitePage } = await import("./InvitePage");

    render(
      <InvitePage
        inviteInfo={{
          inviteCode: "INV-ABCD1234",
          inviteLink: "https://example.com/invite/INV-ABCD1234",
          invitedCount: 3,
          earnedAmount: 8,
          maxInvites: 20,
          remainingInvites: 17,
        }}
        inviteRecords={[]}
        loading={false}
        error={null}
        onCopyText={vi.fn()}
        onRetry={vi.fn()}
      />,
    );

    expect(document.body.textContent).not.toContain("楼");
    expect(document.body.textContent).not.toContain("¥US$");
    expect(screen.getAllByText(/Earn \$2\.00 for each registered friend/).length).toBeGreaterThan(0);
  });

  it("surfaces an invite program summary before the action card and records list", async () => {
    storage.set("h5-lang", "en-US");
    const { InvitePage } = await import("./InvitePage");

    render(
      <InvitePage
        inviteInfo={{
          inviteCode: "INV-ABCD1234",
          inviteLink: "https://example.com/invite/INV-ABCD1234",
          invitedCount: 3,
          earnedAmount: 8,
          maxInvites: 20,
          remainingInvites: 17,
        }}
        inviteRecords={[]}
        loading={false}
        error={null}
        onCopyText={vi.fn()}
        onRetry={vi.fn()}
      />,
    );

    const programHeading = screen.getAllByText(t("tasks.inviteProgramTitle"))[0];
    const actionHeading = screen.getAllByText(t("tasks.inviteMyLink"))[0];
    const recordsHeading = screen.getAllByText(t("tasks.inviteRecords"))[0];

    expect(programHeading.compareDocumentPosition(actionHeading) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(actionHeading.compareDocumentPosition(recordsHeading) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.getAllByText(t("tasks.inviteCapacity")).length).toBeGreaterThan(0);
    expect(screen.getAllByText(t("tasks.inviteProgress")).length).toBeGreaterThan(0);
  });

  it("renders invite records with structured status and timestamp copy instead of legacy separators", async () => {
    storage.set("h5-lang", "en-US");
    const { InvitePage } = await import("./InvitePage");

    render(
      <InvitePage
        inviteInfo={{
          inviteCode: "INV-ABCD1234",
          inviteLink: "https://example.com/invite/INV-ABCD1234",
          invitedCount: 3,
          earnedAmount: 8,
          maxInvites: 20,
          remainingInvites: 17,
        }}
        inviteRecords={[
          {
            id: "inv-1",
            userIdMasked: "US***42",
            type: "registration",
            rewardAmount: 2,
            createdAt: "2026-06-23T09:00:00.000Z",
          },
        ]}
        loading={false}
        error={null}
        onCopyText={vi.fn()}
        onRetry={vi.fn()}
      />,
    );

    expect(document.body.textContent).not.toContain(" 路 ");
    expect(screen.getByText("US***42")).toBeTruthy();
    expect(screen.getByText(t("tasks.inviteRecordRegistered"))).toBeTruthy();
    expect(screen.getAllByText(/\+\$?2(?:\.00)?/).length).toBeGreaterThan(0);
  });
});

describe("LeaderboardPage", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders a top-performer summary ahead of the ranked list", async () => {
    storage.set("h5-lang", "en-US");
    const { LeaderboardPage } = await import("./LeaderboardPage");

    render(
      <LeaderboardPage
        leaderboard={[
          { rank: 1, accountIdMasked: "US***88", amount: 1280, currency: "USD" },
          { rank: 2, accountIdMasked: "US***42", amount: 920, currency: "USD" },
        ]}
        loading={false}
        error={null}
      />,
    );

    const summaryHeading = screen.getByText("Top Performer");
    const listHeading = screen.getByText("Leaderboard");
    expect(summaryHeading.compareDocumentPosition(listHeading) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.getAllByText("US***88").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Masked accounts only").length).toBeGreaterThan(0);
  });

  it("surfaces a ranking overview before the top performer and full leaderboard list", async () => {
    storage.set("h5-lang", "en-US");
    const { LeaderboardPage } = await import("./LeaderboardPage");

    render(
      <LeaderboardPage
        leaderboard={[
          { rank: 1, accountIdMasked: "US***88", amount: 1280, currency: "USD" },
          { rank: 2, accountIdMasked: "US***42", amount: 920, currency: "USD" },
          { rank: 3, accountIdMasked: "US***12", amount: 760, currency: "USD" },
        ]}
        loading={false}
        error={null}
      />,
    );

    const overviewHeading = screen.getByText(t("leaderboard.overviewTitle"));
    const summaryHeading = screen.getByText(t("leaderboard.topPerformer"));
    const listHeading = screen.getByText(t("leaderboard.title"));

    expect(overviewHeading.compareDocumentPosition(summaryHeading)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
    expect(summaryHeading.compareDocumentPosition(listHeading)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
    expect(screen.getByText(t("leaderboard.overviewLeaderLabel"))).toBeTruthy();
    expect(screen.getByText(t("leaderboard.overviewRunnerUpLabel"))).toBeTruthy();
    expect(screen.getByText(t("leaderboard.overviewSpreadLabel"))).toBeTruthy();
    expect(screen.getByText(t("leaderboard.overviewPrivacyLabel"))).toBeTruthy();
  });
});

describe("HomePage", () => {
  beforeEach(() => {
    storage.set("h5-lang", "zh-CN");
  });

  afterEach(() => {
    cleanup();
  });

  it("routes continue-task CTA to the package detail path", async () => {
    const { HomePage } = await import("./HomePage");
    const onNavigate = vi.fn();

    render(
      <HomePage
        dashboard={{
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
          unreadCount: 1,
          pendingClaimCount: 0,
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
        }}
        session={null}
        memberPhoneMasked="138****0000"
        focusTaskPackage={{
          id: "pkg-active",
          title: "Growth Package",
          description: "desc",
          type: "growth",
          status: "active",
          rewardRatio: 0.18,
          claimedAt: null,
          expiresAt: null,
          dispatchedAt: "2026-06-23T00:00:00.000Z",
          completionWindowHours: 24,
          items: [],
          promotion: null,
          taskBalanceAwardedAt: null,
          totalCommission: 36,
          currentCommission: 12,
          completedItems: 1,
          totalItems: 3,
          countdownSeconds: 7200,
        } as any}
        primaryHomeAction={{
          title: t("home.actionContinueTask"),
          description: t("home.actionContinueTaskDesc"),
          buttonLabel: t("home.actionContinue"),
          kind: "continue",
          packageId: "pkg-active",
        }}
        unreadMessageCount={1}
        siteKey="mall-cn"
        actionName={null}
        homeWalletBalance={null}
        notificationCount={0}
        onNavigate={onNavigate}
        onOpenClaimDialog={vi.fn()}
        onShowTransferAllConfirm={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: t("home.actionContinue") }));
    expect(onNavigate).toHaveBeenCalledWith("/h5/tasks/package/pkg-active");
  });

  it("renders a calm account status layer before the earnings hero", async () => {
    storage.set("h5-lang", "en-US");
    const { HomePage } = await import("./HomePage");

    render(
      <HomePage
        dashboard={{
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
          unreadCount: 3,
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
        }}
        session={{
          siteKey: "mall-cn",
          accountId: "38271456",
          publicUserId: "h5-38271456",
          phone: "13800000000",
          phoneMasked: "138****0000",
          displayName: "Demo Member",
          token: "demo-token",
        }}
        memberPhoneMasked="138****0000"
        focusTaskPackage={null}
        primaryHomeAction={{
          title: t("home.actionCanWithdraw"),
          description: t("home.actionCanWithdrawDesc"),
          buttonLabel: t("home.actionGoWithdraw"),
          kind: "withdraw",
        }}
        unreadMessageCount={3}
        siteKey="mall-cn"
        actionName={null}
        homeWalletBalance={null}
        notificationCount={3}
        onNavigate={vi.fn()}
        onOpenClaimDialog={vi.fn()}
        onShowTransferAllConfirm={vi.fn()}
      />,
    );

    const statusHeading = screen.getByText(t("home.statusGreeting", { name: "Demo Member" }));
    const earningsHeading = screen.getByText(t("home.todayEarningsTitle"));

    expect(statusHeading.compareDocumentPosition(earningsHeading)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
    expect(screen.getByText(/Account 382\*\*\*56/)).toBeTruthy();
  });

  it("surfaces verification and notification signals in the home status rail without replacing the main CTA", async () => {
    storage.set("h5-lang", "en-US");
    const { HomePage } = await import("./HomePage");

    render(
      <HomePage
        dashboard={{
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
          unreadCount: 3,
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
        }}
        session={null}
        memberPhoneMasked="138****0000"
        focusTaskPackage={null}
        primaryHomeAction={{
          title: t("home.actionCanWithdraw"),
          description: t("home.actionCanWithdrawDesc"),
          buttonLabel: t("home.actionGoWithdraw"),
          kind: "withdraw",
        }}
        unreadMessageCount={3}
        siteKey="mall-cn"
        actionName={null}
        homeWalletBalance={null}
        notificationCount={3}
        onNavigate={vi.fn()}
        onOpenClaimDialog={vi.fn()}
        onShowTransferAllConfirm={vi.fn()}
      />,
    );

    expect(screen.getByText(t("home.statusVerification", { status: t("verification.statusApproved") }))).toBeTruthy();
    expect(screen.getByText(t("home.statusAlerts", { count: 3 }))).toBeTruthy();
    expect(screen.getByRole("button", { name: t("home.actionGoWithdraw") })).toBeTruthy();
  });

  it("routes the home status avatar to the profile center path", async () => {
    storage.set("h5-lang", "en-US");
    const { HomePage } = await import("./HomePage");
    const onNavigate = vi.fn();

    render(
      <HomePage
        dashboard={{
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
          unreadCount: 3,
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
        }}
        session={null}
        memberPhoneMasked="138****0000"
        focusTaskPackage={null}
        primaryHomeAction={{
          title: t("home.actionCanWithdraw"),
          description: t("home.actionCanWithdrawDesc"),
          buttonLabel: t("home.actionGoWithdraw"),
          kind: "withdraw",
        }}
        unreadMessageCount={3}
        siteKey="mall-cn"
        actionName={null}
        homeWalletBalance={null}
        notificationCount={3}
        onNavigate={onNavigate}
        onOpenClaimDialog={vi.fn()}
        onShowTransferAllConfirm={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: t("profile.title") }));

    expect(onNavigate).toHaveBeenCalledWith("/h5/me");
  });

  it("routes generic home CTA actions to their explicit entry-state path", async () => {
    const { HomePage } = await import("./HomePage");
    const onNavigate = vi.fn();

    render(
      <HomePage
        dashboard={{
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
            systemBalance: 0,
            taskBalance: 0,
            withdrawThreshold: 100,
            shortfallAmount: 100,
            canWithdraw: false,
          },
          unreadCount: 0,
          pendingClaimCount: 0,
          activeCount: 0,
          expiringCount: 0,
          recentMessages: [],
          leaderboard: [],
          verification: {
            currentStatus: "not_submitted",
            hasActiveRequest: false,
          },
          fragments: {
            totalCount: 3,
            completedCount: 0,
            missingCount: 3,
            canExchange: false,
            shippingOrderCount: 0,
            latestShippingStatus: null,
            rewardName: null,
          },
        }}
        session={null}
        memberPhoneMasked="138****0000"
        focusTaskPackage={null}
        primaryHomeAction={{
          title: t("home.actionBindWhatsApp"),
          description: t("home.actionBindWhatsAppDesc"),
          buttonLabel: t("home.actionGoBindWhatsApp"),
          kind: "navigate",
          path: "/h5/whatsapp",
        }}
        unreadMessageCount={0}
        siteKey="mall-cn"
        actionName={null}
        homeWalletBalance={null}
        notificationCount={0}
        onNavigate={onNavigate}
        onOpenClaimDialog={vi.fn()}
        onShowTransferAllConfirm={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: t("home.actionGoBindWhatsApp") }));
    expect(onNavigate).toHaveBeenCalledWith("/h5/whatsapp");
  });

  it("renders growth-home sections in the expected order", async () => {
    const { HomePage } = await import("./HomePage");

    render(
      <HomePage
        dashboard={{
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
          unreadCount: 1,
          pendingClaimCount: 0,
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
        }}
        session={null}
        memberPhoneMasked="138****0000"
        focusTaskPackage={null}
        primaryHomeAction={{
          title: t("home.actionCanWithdraw"),
          description: t("home.actionCanWithdrawDesc"),
          buttonLabel: t("home.actionGoWithdraw"),
          kind: "withdraw",
        }}
        unreadMessageCount={1}
        siteKey="mall-cn"
        actionName={null}
        homeWalletBalance={null}
        notificationCount={0}
        onNavigate={vi.fn()}
        onOpenClaimDialog={vi.fn()}
        onShowTransferAllConfirm={vi.fn()}
      />,
    );

    const earningsHeading = screen.getByText(t("home.todayEarningsTitle"));
    const recommendedHeading = screen.getByText(t("home.recommendedTasksSection"));
    const serviceHeading = screen.getByText(t("home.supportSection"));

    expect(earningsHeading.compareDocumentPosition(recommendedHeading)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
    expect(recommendedHeading.compareDocumentPosition(serviceHeading)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
    expect(screen.getByRole("button", { name: t("home.actionGoWithdraw") })).toBeTruthy();
  });

  it("keeps promotion and support actions out of the recommended tasks section", async () => {
    const { HomePage } = await import("./HomePage");

    render(
      <HomePage
        dashboard={{
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
          unreadCount: 1,
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
        }}
        session={null}
        memberPhoneMasked="138****0000"
        focusTaskPackage={null}
        primaryHomeAction={{
          title: t("home.actionCanWithdraw"),
          description: t("home.actionCanWithdrawDesc"),
          buttonLabel: t("home.actionGoWithdraw"),
          kind: "withdraw",
        }}
        unreadMessageCount={1}
        siteKey="mall-cn"
        actionName={null}
        homeWalletBalance={null}
        notificationCount={0}
        onNavigate={vi.fn()}
        onOpenClaimDialog={vi.fn()}
        onShowTransferAllConfirm={vi.fn()}
      />,
    );

    const recommendedSection = screen.getByText(t("home.recommendedTasksSection")).closest(".h5-card");
    const growthSection = screen.getByText(t("home.growthSection")).closest(".h5-card");
    const supportSection = screen.getByText(t("home.supportSection")).closest(".h5-card");

    expect(recommendedSection?.textContent).not.toContain(t("home.promotion"));
    expect(recommendedSection?.textContent).not.toContain(t("home.ticketComplaint"));
    expect(growthSection?.textContent).toContain(t("home.promotion"));
    expect(supportSection?.textContent).toContain(t("home.ticketComplaint"));
  });
});

describe("RechargePage", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders the wallet snapshot summary before history", async () => {
    const { RechargePage } = await import("./RechargePage");

    render(
      <RechargePage
        effectiveWalletSummary={{
          currency: "USD",
          systemBalance: 320,
          taskBalance: 86,
          withdrawThreshold: 100,
          shortfallAmount: 0,
          canWithdraw: true,
        }}
        rechargeAmount="100"
        rechargeHistory={[
          {
            id: "tx-1",
            transactionType: "recharge",
            amount: 100,
            currency: "USD",
            status: "success",
            note: "Recharge",
            createdAt: "2026-06-23T09:00:00.000Z",
          } as any,
        ]}
        actionName={null}
        loading={false}
        error={null}
        rechargeStatus={null}
        onRechargeAmountChange={vi.fn()}
        onNavigate={vi.fn()}
        onOpenRechargeChannels={vi.fn()}
      />,
    );

    const summaryHeading = screen.getAllByText(t("recharge.snapshotTitle")).at(0)!;
    const historyHeading = screen.getAllByText(t("recharge.history")).at(-1)!;
    expect(summaryHeading.compareDocumentPosition(historyHeading)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
    expect(screen.getAllByText(t("withdraw.systemBalance")).length).toBeGreaterThan(0);
    expect(screen.getAllByText(t("withdraw.taskBalance")).length).toBeGreaterThan(0);
  });

  it("keeps trust signals and earnings actions above the recharge form", async () => {
    storage.set("h5-lang", "en-US");
    const { RechargePage } = await import("./RechargePage");
    const onNavigate = vi.fn();

    render(
      <RechargePage
        effectiveWalletSummary={{
          currency: "USD",
          systemBalance: 320,
          taskBalance: 86,
          withdrawThreshold: 100,
          shortfallAmount: 0,
          canWithdraw: true,
        }}
        rechargeAmount="100"
        rechargeHistory={[
          {
            id: "tx-1",
            transactionType: "recharge",
            amount: 100,
            currency: "USD",
            status: "success",
            note: "Recharge",
            createdAt: "2026-06-23T09:00:00.000Z",
          } as any,
          {
            id: "tx-2",
            transactionType: "recharge",
            amount: 80,
            currency: "USD",
            status: "success",
            note: "Recharge",
            createdAt: "2026-06-20T09:00:00.000Z",
          } as any,
        ]}
        actionName={null}
        loading={false}
        error={null}
        rechargeStatus={null}
        onRechargeAmountChange={vi.fn()}
        onNavigate={onNavigate}
        onOpenRechargeChannels={vi.fn()}
      />,
    );

    const flowLabel = screen.getByText(t("recharge.recentFlow"));
    const withdrawButton = screen.getByRole("button", { name: t("recharge.quickWithdraw") });
    const formHeading = screen.getAllByText(t("recharge.amount")).at(0)!;

    expect(flowLabel.compareDocumentPosition(formHeading)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
    expect(screen.getByText(t("recharge.recentFlowHint"))).toBeTruthy();

    fireEvent.click(withdrawButton);
    expect(onNavigate).toHaveBeenCalledWith("/h5/withdraw");
  });

  it("uses wallet snapshot as the landing headline while keeping recharge as a secondary action", async () => {
    storage.set("h5-lang", "en-US");
    const { RechargePage } = await import("./RechargePage");

    render(
      <RechargePage
        effectiveWalletSummary={{
          currency: "USD",
          systemBalance: 320,
          taskBalance: 86,
          withdrawThreshold: 100,
          shortfallAmount: 0,
          canWithdraw: true,
        }}
        rechargeAmount="100"
        rechargeHistory={[]}
        actionName={null}
        loading={false}
        error={null}
        rechargeStatus={null}
        onRechargeAmountChange={vi.fn()}
        onNavigate={vi.fn()}
        onOpenRechargeChannels={vi.fn()}
      />,
    );

    expect(screen.getByText(t("recharge.snapshotTitle"))).toBeTruthy();
    expect(screen.getByRole("button", { name: t("recharge.quickRecharge") })).toBeTruthy();
    expect(screen.queryByText(/^Recharge$/)).toBeNull();
  });

  it("surfaces withdrawal readiness and a four-card earnings snapshot before the recharge form", async () => {
    storage.set("h5-lang", "en-US");
    const { RechargePage } = await import("./RechargePage");
    const { formatMoney } = await import("./shared");

    render(
      <RechargePage
        effectiveWalletSummary={{
          currency: "USD",
          systemBalance: 80,
          taskBalance: 46,
          withdrawThreshold: 100,
          shortfallAmount: 20,
          canWithdraw: false,
        }}
        rechargeAmount="100"
        rechargeHistory={[
          {
            id: "tx-1",
            transactionType: "recharge",
            amount: 100,
            currency: "USD",
            status: "success",
            note: "Recharge",
            createdAt: "2026-06-23T09:00:00.000Z",
          } as any,
          {
            id: "tx-2",
            transactionType: "recharge",
            amount: 40,
            currency: "USD",
            status: "success",
            note: "Recharge",
            createdAt: "2026-06-23T03:00:00.000Z",
          } as any,
          {
            id: "tx-3",
            transactionType: "recharge",
            amount: 75,
            currency: "USD",
            status: "success",
            note: "Recharge",
            createdAt: "2026-06-20T09:00:00.000Z",
          } as any,
        ]}
        actionName={null}
        loading={false}
        error={null}
        rechargeStatus={null}
        onRechargeAmountChange={vi.fn()}
        onNavigate={vi.fn()}
        onOpenRechargeChannels={vi.fn()}
      />,
    );

    const summaryCards = document.querySelectorAll(".h5-member-wallet-balance-card");
    const thresholdLabel = screen.getByText(t("withdraw.threshold", { amount: formatMoney(100, "USD") }));
    const thresholdHint = screen.getByText(t("withdraw.needTransferHint", { amount: formatMoney(20, "USD") }));
    const formHeading = screen.getAllByText(t("recharge.amount")).at(0)!;

    expect(summaryCards.length).toBeGreaterThanOrEqual(4);
    expect(thresholdLabel.compareDocumentPosition(formHeading)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
    expect(thresholdHint).toBeTruthy();
  });

  it("renders wallet history rows with descriptive titles and localized status labels", async () => {
    storage.set("h5-lang", "zh-CN");
    const { RechargePage } = await import("./RechargePage");

    render(
      <RechargePage
        effectiveWalletSummary={{
          currency: "USD",
          systemBalance: 320,
          taskBalance: 86,
          withdrawThreshold: 100,
          shortfallAmount: 0,
          canWithdraw: true,
        }}
        rechargeAmount="100"
        rechargeHistory={[
          {
            id: "tx-1",
            transactionType: "recharge",
            amount: 100,
            currency: "USD",
            status: "paid",
            note: "银行卡转账入账",
            createdAt: "2026-06-23T09:00:00.000Z",
          } as any,
        ]}
        actionName={null}
        loading={false}
        error={null}
        rechargeStatus={null}
        onRechargeAmountChange={vi.fn()}
        onNavigate={vi.fn()}
        onOpenRechargeChannels={vi.fn()}
      />,
    );

    expect(screen.getByText("银行卡转账入账")).toBeTruthy();
    expect(screen.getByText("已入账")).toBeTruthy();
    expect(screen.queryByText(/^paid$/)).toBeNull();
  });

  it("prefers backend display titles for wallet history rows", async () => {
    const { RechargePage } = await import("./RechargePage");

    render(
      <RechargePage
        effectiveWalletSummary={{
          currency: "USD",
          systemBalance: 320,
          taskBalance: 86,
          withdrawThreshold: 100,
          shortfallAmount: 0,
          canWithdraw: true,
        }}
        rechargeAmount="100"
        rechargeHistory={[
          {
            id: "tx-typed-title",
            transactionType: "recharge",
            amount: 100,
            currency: "USD",
            status: "paid",
            note: "",
            displayTitle: "充值补单到账",
            displayCategory: "wallet_credit",
            createdAt: "2026-06-23T09:00:00.000Z",
          } as any,
        ]}
        actionName={null}
        loading={false}
        error={null}
        rechargeStatus={null}
        onRechargeAmountChange={vi.fn()}
        onNavigate={vi.fn()}
        onOpenRechargeChannels={vi.fn()}
      />,
    );

    expect(screen.getByText("充值补单到账")).toBeTruthy();
  });

  it("renders bonus and refund wallet labels without falling back to generic recharge copy", async () => {
    const { RechargePage } = await import("./RechargePage");

    render(
      <RechargePage
        effectiveWalletSummary={{
          currency: "USD",
          systemBalance: 320,
          taskBalance: 86,
          withdrawThreshold: 100,
          shortfallAmount: 0,
          canWithdraw: true,
        }}
        rechargeAmount="100"
        rechargeHistory={[
          {
            id: "tx-bonus",
            transactionType: "bonus_grant",
            amount: 60,
            currency: "USD",
            status: "paid",
            note: "",
            displayTitle: "赠金到账",
            createdAt: "2026-06-23T09:00:00.000Z",
          } as any,
          {
            id: "tx-refund",
            transactionType: "withdraw_reject_refund",
            amount: 40,
            currency: "USD",
            status: "paid",
            note: "",
            displayTitle: "提现退回",
            createdAt: "2026-06-23T10:00:00.000Z",
          } as any,
        ]}
        actionName={null}
        loading={false}
        error={null}
        rechargeStatus={null}
        onRechargeAmountChange={vi.fn()}
        onNavigate={vi.fn()}
        onOpenRechargeChannels={vi.fn()}
      />,
    );

    expect(screen.getByText("赠金到账")).toBeTruthy();
    expect(screen.getByText("提现退回")).toBeTruthy();
    expect(screen.queryByText(t("recharge.historyDefaultNote"))).toBeNull();
  });

  it("uses a dedicated wallet snapshot heading instead of repeating the earnings page title inside the hero card", async () => {
    storage.set("h5-lang", "en-US");
    const { RechargePage } = await import("./RechargePage");

    render(
      <RechargePage
        effectiveWalletSummary={{
          currency: "USD",
          systemBalance: 320,
          taskBalance: 86,
          withdrawThreshold: 100,
          shortfallAmount: 0,
          canWithdraw: true,
        }}
        rechargeAmount="100"
        rechargeHistory={[]}
        actionName={null}
        loading={false}
        error={null}
        rechargeStatus={null}
        onRechargeAmountChange={vi.fn()}
        onNavigate={vi.fn()}
        onOpenRechargeChannels={vi.fn()}
      />,
    );

    expect(screen.getByText(t("recharge.snapshotTitle"))).toBeTruthy();
    expect(screen.queryByText(/^Earnings$/)).toBeNull();
  });
});

describe("WithdrawPage", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders estimated receive copy with the active locale", async () => {
    storage.set("h5-lang", "en-US");
    const { WithdrawPage } = await import("./WithdrawPage");

    render(
      <WithdrawPage
        effectiveWalletSummary={{
          currency: "USD",
          systemBalance: 320,
          taskBalance: 86,
          withdrawThreshold: 100,
          shortfallAmount: 0,
          canWithdraw: true,
        }}
        withdrawAmount="100"
        withdrawRequests={[]}
        maxWithdrawAmount={320}
        actionName={null}
        onWithdrawAmountChange={vi.fn()}
        onWithdraw={vi.fn().mockResolvedValue(undefined)}
        onShowTransferAllConfirm={vi.fn()}
        onSetMaxWithdraw={vi.fn()}
      />,
    );

    expect(screen.getByText(/Estimated receive:/i)).toBeTruthy();
  });

  it("shows localized withdrawal statuses without leaking raw enum values", async () => {
    storage.set("h5-lang", "en-US");
    const { WithdrawPage } = await import("./WithdrawPage");

    render(
      <WithdrawPage
        effectiveWalletSummary={{
          currency: "USD",
          systemBalance: 320,
          taskBalance: 86,
          withdrawThreshold: 100,
          shortfallAmount: 0,
          canWithdraw: true,
        }}
        withdrawAmount="100"
        withdrawRequests={[
          {
            id: "wd-1",
            amount: 80,
            currency: "USD",
            status: "reviewing",
            createdAt: "2026-06-23T09:00:00.000Z",
          } as any,
        ]}
        maxWithdrawAmount={320}
        actionName={null}
        onWithdrawAmountChange={vi.fn()}
        onWithdraw={vi.fn().mockResolvedValue(undefined)}
        onShowTransferAllConfirm={vi.fn()}
        onSetMaxWithdraw={vi.fn()}
      />,
    );

    expect(screen.getAllByText(t("withdraw.statusReviewing")).length).toBeGreaterThan(0);
    expect(screen.queryByText(/^reviewing$/i)).toBeNull();
  });

  it("surfaces withdrawal readiness guidance before the withdraw form", async () => {
    storage.set("h5-lang", "en-US");
    const { WithdrawPage } = await import("./WithdrawPage");
    const { formatMoney } = await import("./shared");

    render(
      <WithdrawPage
        effectiveWalletSummary={{
          currency: "USD",
          systemBalance: 80,
          taskBalance: 46,
          withdrawThreshold: 100,
          shortfallAmount: 20,
          canWithdraw: false,
        }}
        withdrawAmount="40"
        withdrawRequests={[]}
        maxWithdrawAmount={80}
        actionName={null}
        onWithdrawAmountChange={vi.fn()}
        onWithdraw={vi.fn().mockResolvedValue(undefined)}
        onShowTransferAllConfirm={vi.fn()}
        onSetMaxWithdraw={vi.fn()}
      />,
    );

    const summaryCards = document.querySelectorAll(".h5-member-wallet-balance-card");
    const thresholdHint = screen.getByText(t("withdraw.needTransferHint", { amount: formatMoney(20, "USD") }));
    const formHeading = screen.getAllByText(t("withdraw.amount")).at(0)!;

    expect(summaryCards.length).toBeGreaterThanOrEqual(3);
    expect(thresholdHint.compareDocumentPosition(formHeading)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
    expect(screen.getByText(t("withdraw.nextStep"))).toBeTruthy();
  });

  it("uses a dedicated withdrawal overview heading instead of repeating the generic page title in the hero", async () => {
    storage.set("h5-lang", "en-US");
    const { WithdrawPage } = await import("./WithdrawPage");

    render(
      <WithdrawPage
        effectiveWalletSummary={{
          currency: "USD",
          systemBalance: 320,
          taskBalance: 86,
          withdrawThreshold: 100,
          shortfallAmount: 0,
          canWithdraw: true,
        }}
        withdrawAmount="100"
        withdrawRequests={[]}
        maxWithdrawAmount={320}
        actionName={null}
        onWithdrawAmountChange={vi.fn()}
        onWithdraw={vi.fn().mockResolvedValue(undefined)}
        onShowTransferAllConfirm={vi.fn()}
        onSetMaxWithdraw={vi.fn()}
      />,
    );

    expect(screen.getByText(t("withdraw.snapshotTitle"))).toBeTruthy();
    expect(document.querySelector(".h5-member-wallet-balance-hero .h5-member-section-heading strong")?.textContent).toBe(
      t("withdraw.snapshotTitle"),
    );
  });

  it("uses dedicated withdrawal status icon classes instead of inline icon sizing and color styles", async () => {
    storage.set("h5-lang", "en-US");
    const { WithdrawPage } = await import("./WithdrawPage");

    const { container, rerender } = render(
      <WithdrawPage
        effectiveWalletSummary={{
          currency: "USD",
          systemBalance: 320,
          taskBalance: 86,
          withdrawThreshold: 100,
          shortfallAmount: 0,
          canWithdraw: true,
        }}
        withdrawAmount="100"
        withdrawRequests={[
          {
            id: "wd-1",
            amount: 80,
            currency: "USD",
            status: "reviewing",
            createdAt: "2026-06-23T09:00:00.000Z",
          } as any,
        ]}
        maxWithdrawAmount={320}
        actionName={null}
        onWithdrawAmountChange={vi.fn()}
        onWithdraw={vi.fn().mockResolvedValue(undefined)}
        onShowTransferAllConfirm={vi.fn()}
        onSetMaxWithdraw={vi.fn()}
      />,
    );

    expect(container.querySelector(".h5-withdraw-status-flow-icon")).toBeTruthy();
    expect(container.querySelector(".h5-withdraw-status-flow-icon")?.getAttribute("style")).toBeNull();

    rerender(
      <WithdrawPage
        effectiveWalletSummary={{
          currency: "USD",
          systemBalance: 320,
          taskBalance: 86,
          withdrawThreshold: 100,
          shortfallAmount: 0,
          canWithdraw: true,
        }}
        withdrawAmount="100"
        withdrawRequests={[
          {
            id: "wd-2",
            amount: 80,
            currency: "USD",
            status: "rejected",
            createdAt: "2026-06-23T09:00:00.000Z",
          } as any,
        ]}
        maxWithdrawAmount={320}
        actionName={null}
        onWithdrawAmountChange={vi.fn()}
        onWithdraw={vi.fn().mockResolvedValue(undefined)}
        onShowTransferAllConfirm={vi.fn()}
        onSetMaxWithdraw={vi.fn()}
      />,
    );

    expect(container.querySelector(".h5-withdraw-status-flow-icon-rejected")).toBeTruthy();
    expect(container.querySelector(".h5-withdraw-status-flow-icon-rejected")?.getAttribute("style")).toBeNull();
  });

  it("shows withdrawal split details and rejected refund copy in history rows", async () => {
    storage.set("h5-lang", "zh-CN");
    const { WithdrawPage } = await import("./WithdrawPage");
    const { formatMoney } = await import("./shared");

    render(
      <WithdrawPage
        effectiveWalletSummary={{
          currency: "USD",
          systemBalance: 320,
          taskBalance: 86,
          withdrawThreshold: 100,
          shortfallAmount: 0,
          canWithdraw: true,
        }}
        withdrawAmount="100"
        withdrawRequests={[
          {
            id: "wd-rejected",
            amount: 80,
            cashAmount: 30,
            bonusAmount: 50,
            actualPayoutAmount: null,
            rejectionReason: "银行卡信息不完整",
            currency: "USD",
            status: "rejected",
            createdAt: "2026-06-23T09:00:00.000Z",
          } as any,
          {
            id: "wd-paid",
            amount: 120,
            cashAmount: 100,
            bonusAmount: 20,
            actualPayoutAmount: 118.8,
            rejectionReason: null,
            currency: "USD",
            status: "paid",
            createdAt: "2026-06-23T10:00:00.000Z",
          } as any,
        ]}
        maxWithdrawAmount={320}
        actionName={null}
        onWithdrawAmountChange={vi.fn()}
        onWithdraw={vi.fn().mockResolvedValue(undefined)}
        onShowTransferAllConfirm={vi.fn()}
        onSetMaxWithdraw={vi.fn()}
      />,
    );

    expect(screen.getByText("提现退回")).toBeTruthy();
    expect(screen.getByText("提现完成")).toBeTruthy();
    expect(document.body.textContent).toContain(`真实资金 ${formatMoney(30, "USD")}`);
    expect(document.body.textContent).toContain(`赠金 ${formatMoney(50, "USD")}`);
    expect(document.body.textContent).toContain(`实际打款 ${formatMoney(118.8, "USD")}`);
    expect(screen.getByText("银行卡信息不完整")).toBeTruthy();
  });
});

describe("ProfilePage", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders account-service center before quick action grid", async () => {
    const { ProfilePage } = await import("./ProfilePage");

    render(
      <ProfilePage
        dashboard={{
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
          unreadCount: 1,
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
        }}
        whatsAppBinding={{ isBound: true, phoneNumber: "60123456789", updatedAt: "2026-06-23T09:00:00.000Z" } as any}
        profileVerificationStatusLabel={t("profile.verified")}
        profileQuickActions={[
          { key: "promotion", label: t("profileLinks.promotion"), description: t("profileLinks.promotionDesc"), path: "/h5/promotion" },
          { key: "orders", label: t("profileLinks.orders"), description: t("profileLinks.ordersDesc"), path: "/h5/orders" },
        ]}
        actionName={null}
        onNavigate={vi.fn()}
        onLogout={vi.fn()}
        onShowTransferAllConfirm={vi.fn()}
      />,
    );

    const serviceCenterHeading = screen.getByText(t("profile.serviceCenter"));
    const quickActionsHeading = screen.getByText(t("profile.commonEntries"));
    expect(serviceCenterHeading.compareDocumentPosition(quickActionsHeading)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
    expect(screen.getByText(t("profile.logout"))).toBeTruthy();
  });

  it("does not duplicate the settings row action copy in the service center list", async () => {
    const { ProfilePage } = await import("./ProfilePage");

    render(
      <ProfilePage
        dashboard={{
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
          unreadCount: 1,
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
        }}
        whatsAppBinding={null}
        profileVerificationStatusLabel={t("profile.verified")}
        profileQuickActions={[
          { key: "promotion", label: t("profileLinks.promotion"), description: t("profileLinks.promotionDesc"), path: "/h5/promotion" },
          { key: "orders", label: t("profileLinks.orders"), description: t("profileLinks.ordersDesc"), path: "/h5/orders" },
        ]}
        actionName={null}
        onNavigate={vi.fn()}
        onLogout={vi.fn()}
        onShowTransferAllConfirm={vi.fn()}
      />,
    );

    const settingsRowTitle = screen
      .getAllByText(t("settings.title"))
      .find((node) => node.closest(".h5-member-list-row"));
    const settingsRow = settingsRowTitle?.closest(".h5-member-list-row");
    expect(settingsRow).toBeTruthy();
    expect(settingsRow?.textContent?.match(new RegExp(t("common.enter"), "g"))?.length ?? 0).toBe(1);
  });

  it("routes the profile recharge action to the unified earnings wallet path", async () => {
    const { ProfilePage } = await import("./ProfilePage");
    const onNavigate = vi.fn();

    render(
      <ProfilePage
        dashboard={{
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
          unreadCount: 1,
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
        }}
        whatsAppBinding={null}
        profileVerificationStatusLabel={t("profile.verified")}
        profileQuickActions={[
          { key: "promotion", label: t("profileLinks.promotion"), description: t("profileLinks.promotionDesc"), path: "/h5/promotion" },
          { key: "orders", label: t("profileLinks.orders"), description: t("profileLinks.ordersDesc"), path: "/h5/orders" },
        ]}
        actionName={null}
        onNavigate={onNavigate}
        onLogout={vi.fn()}
        onShowTransferAllConfirm={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: t("profile.recharge") }));
    expect(onNavigate).toHaveBeenCalledWith("/h5/wallet");
  });

  it("keeps the verification service row to a single action label", async () => {
    const { ProfilePage } = await import("./ProfilePage");

    render(
      <ProfilePage
        dashboard={{
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
          unreadCount: 1,
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
        }}
        whatsAppBinding={null}
        profileVerificationStatusLabel={t("profile.verified")}
        profileQuickActions={[
          { key: "promotion", label: t("profileLinks.promotion"), description: t("profileLinks.promotionDesc"), path: "/h5/promotion" },
          { key: "orders", label: t("profileLinks.orders"), description: t("profileLinks.ordersDesc"), path: "/h5/orders" },
        ]}
        actionName={null}
        onNavigate={vi.fn()}
        onLogout={vi.fn()}
        onShowTransferAllConfirm={vi.fn()}
      />,
    );

    const verificationRowTitle = screen
      .getAllByText(t("verification.title"))
      .find((node) => node.closest(".h5-member-list-row"));
    const verificationRow = verificationRowTitle?.closest(".h5-member-list-row");
    expect(verificationRow).toBeTruthy();
    expect(verificationRow?.textContent).not.toContain(t("common.view"));
    expect(verificationRow?.textContent?.match(new RegExp(t("common.enter"), "g"))?.length ?? 0).toBe(1);
  });

  it("keeps duplicated service entries out of the quick action grid", async () => {
    const { ProfilePage } = await import("./ProfilePage");

    render(
      <ProfilePage
        dashboard={{
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
          unreadCount: 1,
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
        }}
        whatsAppBinding={{ isBound: true, phoneNumber: "60123456789", updatedAt: "2026-06-23T09:00:00.000Z" } as any}
        profileVerificationStatusLabel={t("profile.verified")}
        profileQuickActions={[
          { key: "promotion", label: t("profileLinks.promotion"), description: t("profileLinks.promotionDesc"), path: "/h5/promotion" },
          { key: "orders", label: t("profileLinks.orders"), description: t("profileLinks.ordersDesc"), path: "/h5/orders" },
          { key: "tickets", label: t("profileLinks.tickets"), description: t("profileLinks.ticketsDesc"), path: "/h5/tickets" },
          { key: "contact", label: t("profileLinks.contact"), description: t("profileLinks.contactDesc"), path: "/h5/tickets/new" },
        ]}
        actionName={null}
        onNavigate={vi.fn()}
        onLogout={vi.fn()}
        onShowTransferAllConfirm={vi.fn()}
      />,
    );

    const quickGrid = screen.getByText(t("profile.commonEntries")).closest(".h5-card");
    expect(quickGrid?.textContent).toContain(t("profileLinks.promotion"));
    expect(quickGrid?.textContent).toContain(t("profileLinks.orders"));
    expect(quickGrid?.textContent).not.toContain(t("messages.title"));
    expect(quickGrid?.textContent).not.toContain(t("whatsapp.title"));
    expect(quickGrid?.textContent).not.toContain(t("settings.title"));
  });

  it("keeps support in the primary service center and limits the secondary grid to promotion and orders", async () => {
    const { ProfilePage } = await import("./ProfilePage");

    render(
      <ProfilePage
        dashboard={{
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
          unreadCount: 1,
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
        }}
        whatsAppBinding={{ isBound: true, phoneNumber: "60123456789", updatedAt: "2026-06-23T09:00:00.000Z" } as any}
        profileVerificationStatusLabel={t("profile.verified")}
        profileQuickActions={[
          { key: "promotion", label: t("profileLinks.promotion"), description: t("profileLinks.promotionDesc"), path: "/h5/promotion" },
          { key: "orders", label: t("profileLinks.orders"), description: t("profileLinks.ordersDesc"), path: "/h5/orders" },
          { key: "tickets", label: t("profileLinks.tickets"), description: t("profileLinks.ticketsDesc"), path: "/h5/tickets" },
          { key: "contact", label: t("profileLinks.contact"), description: t("profileLinks.contactDesc"), path: "/h5/tickets/new" },
        ]}
        actionName={null}
        onNavigate={vi.fn()}
        onLogout={vi.fn()}
        onShowTransferAllConfirm={vi.fn()}
      />,
    );

    const serviceCard = screen.getByText(t("profile.serviceCenter")).closest(".h5-card");
    const quickGrid = screen.getByText(t("profile.commonEntries")).closest(".h5-card");

    expect(serviceCard?.textContent).toContain(t("tickets.title"));
    expect(quickGrid?.textContent).toContain(t("profileLinks.promotion"));
    expect(quickGrid?.textContent).toContain(t("profileLinks.orders"));
    expect(quickGrid?.textContent).not.toContain(t("profileLinks.tickets"));
    expect(quickGrid?.textContent).not.toContain(t("profileLinks.contact"));
  });

  it("surfaces account snapshot pills with stable member context above the balance controls", async () => {
    const { ProfilePage } = await import("./ProfilePage");

    render(
      <ProfilePage
        dashboard={{
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
          unreadCount: 3,
          pendingClaimCount: 2,
          activeCount: 4,
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
        }}
        whatsAppBinding={{ isBound: true, phoneNumber: "60123456789", updatedAt: "2026-06-23T09:00:00.000Z" } as any}
        profileVerificationStatusLabel={t("profile.verified")}
        profileQuickActions={[
          { key: "promotion", label: t("profileLinks.promotion"), description: t("profileLinks.promotionDesc"), path: "/h5/promotion" },
          { key: "orders", label: t("profileLinks.orders"), description: t("profileLinks.ordersDesc"), path: "/h5/orders" },
        ]}
        actionName={null}
        onNavigate={vi.fn()}
        onLogout={vi.fn()}
        onShowTransferAllConfirm={vi.fn()}
      />,
    );

    const overviewCard = screen.getByText(t("profile.accountCenter")).closest(".h5-card");
    const statStrip = overviewCard?.querySelector(".h5-member-profile-stat-strip");
    const balanceStrip = overviewCard?.querySelector(".h5-member-profile-balance-strip");

    expect(statStrip).toBeTruthy();
    expect(balanceStrip).toBeTruthy();
    expect(statStrip?.textContent).toContain(t("profile.snapshotMemberSince"));
    expect(statStrip?.textContent).toContain(t("profile.snapshotActiveTasks"));
    expect(statStrip?.textContent).toContain(t("profile.snapshotPendingClaim"));
    expect(statStrip?.compareDocumentPosition(balanceStrip!)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
  });

  it("adds a service snapshot strip ahead of the detailed service rows", async () => {
    const { ProfilePage } = await import("./ProfilePage");

    render(
      <ProfilePage
        dashboard={{
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
          unreadCount: 3,
          pendingClaimCount: 2,
          activeCount: 4,
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
        }}
        whatsAppBinding={{ isBound: true, phoneNumber: "60123456789", updatedAt: "2026-06-23T09:00:00.000Z" } as any}
        profileVerificationStatusLabel={t("profile.verified")}
        profileQuickActions={[
          { key: "promotion", label: t("profileLinks.promotion"), description: t("profileLinks.promotionDesc"), path: "/h5/promotion" },
          { key: "orders", label: t("profileLinks.orders"), description: t("profileLinks.ordersDesc"), path: "/h5/orders" },
        ]}
        actionName={null}
        onNavigate={vi.fn()}
        onLogout={vi.fn()}
        onShowTransferAllConfirm={vi.fn()}
      />,
    );

    const serviceCard = screen.getByText(t("profile.serviceCenter")).closest(".h5-card");
    const serviceStrip = serviceCard?.querySelector(".h5-member-profile-service-strip");
    const serviceList = serviceCard?.querySelector(".h5-member-profile-service-list");

    expect(serviceStrip).toBeTruthy();
    expect(serviceList).toBeTruthy();
    expect(serviceStrip?.textContent).toContain(t("profile.serviceVerification"));
    expect(serviceStrip?.textContent).toContain(t("profile.serviceMessages"));
    expect(serviceStrip?.textContent).toContain(t("profile.serviceBinding"));
    expect(serviceStrip?.compareDocumentPosition(serviceList!)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
  });

  it("keeps service center rows in a dedicated mobile-safe layout override", () => {
    const css = readFileSync("src/styles/h5-member.css", "utf8");

    expect(css).toMatch(/\.h5-member-profile-service-list\s+\.h5-member-list-row\s*\{[\s\S]*align-items:\s*flex-start/);
    expect(css).toMatch(/@media \(max-width:\s*420px\)[\s\S]*\.h5-member-profile-service-list\s+\.h5-member-list-row\s*\{[\s\S]*flex-direction:\s*row/);
    expect(css).toMatch(/@media \(max-width:\s*420px\)[\s\S]*\.h5-member-profile-service-list\s+\.h5-member-list-row-side\s*\{[\s\S]*align-items:\s*flex-end/);
  });

  it("allows profile service-center copy to wrap for long translated labels", () => {
    const css = readFileSync("src/styles/h5-member.css", "utf8");

    expect(css).toMatch(
      /\.h5-member-profile-service-list\s+\.h5-member-list-row-title\s+strong\s*\{[\s\S]*white-space:\s*normal[\s\S]*text-overflow:\s*clip[\s\S]*overflow-wrap:\s*anywhere/,
    );
    expect(css).toMatch(
      /\.h5-member-profile-service-list\s+\.h5-member-list-row-action[\s\S]*white-space:\s*normal[\s\S]*overflow-wrap:\s*anywhere/,
    );
  });
});

describe("FragmentsPage", () => {
  afterEach(() => {
    cleanup();
  });

  it("surfaces a fragment overview and shipping checklist before the exchange form", async () => {
    storage.set("h5-lang", "en-US");
    const { FragmentsPage } = await import("./FragmentsPage");

    render(
      <FragmentsPage
        fragmentOverview={{
          inventory: [
            { id: "frag-1", name: "Gold Shard", owned: 2, required: 5, rarity: "rare" },
          ],
          dropLogs: [],
          shippingOrders: [],
        } as any}
        fragmentCompletion={{ completed: 1, total: 3, missing: 2, progress: 34 }}
        canExchangeFragments={false}
        latestShippingOrder={null}
        fragmentStageTitle={t("fragments.stageCollect")}
        fragmentStageDescription={t("fragments.stageKeepCollecting")}
        shippingForm={{
          receiver: "",
          phone: "",
          province: "",
          city: "",
          addressLine: "",
        }}
        actionName={null}
        fragmentsLoading={false}
        fragmentsError={null}
        onCheckIn={vi.fn().mockResolvedValue(undefined)}
        onExchange={vi.fn().mockResolvedValue(undefined)}
        onShippingFormChange={vi.fn()}
        onRetry={vi.fn().mockResolvedValue(undefined)}
      />,
    );

    const overviewHeading = screen.getByText(t("fragments.overviewTitle"));
    const prepHeading = screen.getByText(t("fragments.prepTitle"));
    const stageHeading = screen.getByText(t("fragments.stageCollect"));

    expect(overviewHeading.compareDocumentPosition(prepHeading)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
    expect(prepHeading.compareDocumentPosition(stageHeading)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
    expect(screen.getByText(t("fragments.overviewCollectedLabel"))).toBeTruthy();
    expect(screen.getByText(t("fragments.overviewMissingLabel"))).toBeTruthy();
    expect(screen.getByText(t("fragments.overviewShippingLabel"))).toBeTruthy();
    expect(screen.getByText(t("fragments.overviewNextStepLabel"))).toBeTruthy();
    expect(screen.getByText(t("fragments.prepReceiverTitle"))).toBeTruthy();
    expect(screen.getByText(t("fragments.prepAddressTitle"))).toBeTruthy();
    expect(screen.getByText(t("fragments.prepShippingTitle"))).toBeTruthy();
  });

  it("renders a localized retry action in the error state", async () => {
    storage.set("h5-lang", "en-US");
    const { FragmentsPage } = await import("./FragmentsPage");

    render(
      <FragmentsPage
        fragmentOverview={{
          inventory: [],
          dropLogs: [],
          shippingOrders: [],
        } as any}
        fragmentCompletion={{ completed: 0, total: 0, missing: 0, progress: 0 }}
        canExchangeFragments={false}
        latestShippingOrder={null}
        fragmentStageTitle=""
        fragmentStageDescription=""
        shippingForm={{
          receiver: "",
          phone: "",
          province: "",
          city: "",
          addressLine: "",
        }}
        actionName={null}
        fragmentsLoading={false}
        fragmentsError="Temporary fragment service issue"
        onCheckIn={vi.fn().mockResolvedValue(undefined)}
        onExchange={vi.fn().mockResolvedValue(undefined)}
        onShippingFormChange={vi.fn()}
        onRetry={vi.fn().mockResolvedValue(undefined)}
      />,
    );

    expect(screen.getByRole("button", { name: t("common.retry") })).toBeTruthy();
  });
});

describe("SettingsPage", () => {
  afterEach(() => {
    cleanup();
  });

  it("surfaces an account overview and security checklist before the editable forms", async () => {
    storage.set("h5-lang", "en-US");
    const { SettingsPage } = await import("./SettingsPage");

    const dashboard = {
      site: {
        site_key: "mall-us",
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
      unreadCount: 1,
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
    } as any;

    render(
      <SettingsPage
        dashboard={dashboard}
        settingsPhone="13800000000"
        settingsAvatarUrl={null}
        settingsCurrentPassword=""
        settingsNextPassword=""
        settingsConfirmPassword=""
        settingsCurrentPasswordVisible={false}
        settingsNextPasswordVisible={false}
        settingsConfirmPasswordVisible={false}
        actionName={null}
        onPhoneChange={vi.fn()}
        onAvatarChange={vi.fn().mockResolvedValue(undefined)}
        onSaveProfile={vi.fn().mockResolvedValue(undefined)}
        onCurrentPasswordChange={vi.fn()}
        onCurrentPasswordToggle={vi.fn()}
        onNextPasswordChange={vi.fn()}
        onNextPasswordToggle={vi.fn()}
        onConfirmPasswordChange={vi.fn()}
        onConfirmPasswordToggle={vi.fn()}
        onChangePassword={vi.fn().mockResolvedValue(undefined)}
      />,
    );

    const overviewHeading = screen.getByText(t("settings.overviewTitle"));
    const profileHeading = screen.getByText(t("settings.title"));
    const checklistHeading = screen.getByText(t("settings.securityChecklistTitle"));
    const passwordHeading = screen.getAllByText(t("settings.changePassword"))[0];

    expect(overviewHeading.compareDocumentPosition(profileHeading)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
    expect(checklistHeading.compareDocumentPosition(passwordHeading)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
    expect(screen.getByText(t("settings.overviewVerificationLabel"))).toBeTruthy();
    expect(screen.getByText(t("settings.overviewMemberSinceLabel"))).toBeTruthy();
    expect(screen.getByText(t("settings.securityPhoneTitle"))).toBeTruthy();
    expect(screen.getByText(t("settings.securityPasswordTitle"))).toBeTruthy();
    expect(screen.getByText(t("settings.securityReviewTitle"))).toBeTruthy();
  });

  it("renders localized success messages after saving profile and changing password", async () => {
    storage.set("h5-lang", "en-US");
    const { SettingsPage } = await import("./SettingsPage");

    const dashboard = {
      site: {
        site_key: "mall-us",
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
      unreadCount: 1,
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
    } as any;

    render(
      <SettingsPage
        dashboard={dashboard}
        settingsPhone="13800000000"
        settingsAvatarUrl={null}
        settingsCurrentPassword="current-pass"
        settingsNextPassword="NextPass123!"
        settingsConfirmPassword="NextPass123!"
        settingsCurrentPasswordVisible={false}
        settingsNextPasswordVisible={false}
        settingsConfirmPasswordVisible={false}
        actionName={null}
        onPhoneChange={vi.fn()}
        onAvatarChange={vi.fn().mockResolvedValue(undefined)}
        onSaveProfile={vi.fn().mockResolvedValue(undefined)}
        onCurrentPasswordChange={vi.fn()}
        onCurrentPasswordToggle={vi.fn()}
        onNextPasswordChange={vi.fn()}
        onNextPasswordToggle={vi.fn()}
        onConfirmPasswordChange={vi.fn()}
        onConfirmPasswordToggle={vi.fn()}
        onChangePassword={vi.fn().mockResolvedValue(undefined)}
      />,
    );

    fireEvent.submit(screen.getByRole("button", { name: t("settings.saveProfile") }).closest("form")!);
    await vi.waitFor(() => {
      expect(screen.getByText(t("notification.profileUpdated"))).toBeTruthy();
    });

    fireEvent.submit(screen.getByRole("button", { name: t("settings.modifyPassword") }).closest("form")!);
    await vi.waitFor(() => {
      expect(screen.getByText(t("notification.passwordChanged"))).toBeTruthy();
    });
  });
});

describe("TasksPage growth grouping", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders groups in progress available completed expired order", async () => {
    const { TasksPage } = await import("./TasksPage");

    render(
      <TasksPage
        signInStatus={{
          consecutiveDays: 3,
          todaySignedIn: false,
          goalDays: 7,
          goalReward: 5,
          isCompleted: false,
        }}
        taskInstances={[
          {
            id: "pkg-active",
            title: "Active Growth Package",
            description: "desc",
            type: "growth",
            status: "active",
            rewardRatio: 0.18,
            rewardAmount: 36,
            products: [],
            completedCount: 1,
            totalCount: 3,
            systemBalance: 120,
            currentCommission: 12,
            totalCommission: 36,
            countdownSeconds: 7200,
            completionWindowHours: 24,
          } as any,
          {
            id: "pkg-pending",
            title: "Pending Growth Package",
            description: "desc",
            type: "growth",
            status: "pending_claim",
            rewardRatio: 0.18,
            rewardAmount: 36,
            products: [],
            completedCount: 0,
            totalCount: 3,
            systemBalance: 120,
            currentCommission: 0,
            totalCommission: 36,
            countdownSeconds: 7200,
            completionWindowHours: 24,
          } as any,
          {
            id: "pkg-completed",
            title: "Completed Growth Package",
            description: "desc",
            type: "growth",
            status: "completed",
            rewardRatio: 0.18,
            rewardAmount: 36,
            products: [],
            completedCount: 3,
            totalCount: 3,
            systemBalance: 120,
            currentCommission: 36,
            totalCommission: 36,
            countdownSeconds: 0,
            completionWindowHours: 24,
          } as any,
          {
            id: "pkg-expired",
            title: "Expired Growth Package",
            description: "desc",
            type: "growth",
            status: "expired",
            rewardRatio: 0.18,
            rewardAmount: 36,
            products: [],
            completedCount: 1,
            totalCount: 3,
            systemBalance: 120,
            currentCommission: 12,
            totalCommission: 36,
            countdownSeconds: 0,
            completionWindowHours: 24,
          } as any,
        ]}
        actionName={null}
        loading={false}
        error={null}
        onSignIn={vi.fn().mockResolvedValue(undefined)}
        onNavigate={vi.fn()}
        onRefresh={vi.fn().mockResolvedValue(undefined)}
        onOpenClaimDialog={vi.fn()}
      />,
    );

    const headings = screen.getAllByRole("heading", { level: 4 }).map((node) => node.textContent ?? "");
    expect(headings).toEqual([
      expect.stringContaining(t("tasks.groupInProgress")),
      expect.stringContaining(t("tasks.groupAvailable")),
      expect.stringContaining(t("tasks.groupCompleted")),
      expect.stringContaining(t("tasks.groupExpired")),
    ]);
  });
});
