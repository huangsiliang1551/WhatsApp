import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { fireEvent } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import * as h5Module from "./h5";
import * as h5MemberModule from "./h5Member";
import {
  H5AuthRequiredError,
  type H5TaskPackage,
  getCurrentMemberSession,
  getMemberHomeDashboard,
  loginMember,
  logoutMember,
  registerMember,
} from "./h5Member";

type TaskPackageState = H5TaskPackage & {
  totalCommission: number;
  currentCommission: number;
  completedItems: number;
  totalItems: number;
  countdownSeconds: number;
};

const storage = new Map<string, string>();
const mountedRoots: Root[] = [];
const mountedContainers: HTMLDivElement[] = [];

const MEMBER_SESSION_KEY = "frontend.h5.member-session.v1";
const LEGACY_SESSION = {
  accountId: "38271456",
  phone: "13800000000",
  publicUserId: "h5-38271456",
  displayName: "Legacy Member",
  inviteCode: "INV-LEGACY",
};

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

function createJsonResponse(payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

function createErrorResponse(status: number, detail: string): Response {
  return new Response(
    JSON.stringify({
      detail,
      request_id: "req-test-1",
    }),
    {
      status,
      headers: { "Content-Type": "application/json" },
    },
  );
}

function createHtmlResponse(html = "<!doctype html><html><body>fallback</body></html>"): Response {
  return new Response(html, {
    status: 200,
    headers: { "Content-Type": "text/html" },
  });
}

function createAuthPayload(): Record<string, unknown> {
  return {
    member: {
      userId: "user-1",
      publicUserId: "h5-38271456",
      accountId: "acct-h5",
      siteId: "site-1",
      siteKey: "mall-cn",
      memberNo: "38271456",
      accountIdMasked: "382***56",
      inviteCode: "INV-ABCD1234",
      phone: "13800000000",
      displayName: "Demo Member",
      languageCode: "zh-CN",
      createdAt: "2026-06-11T00:00:00Z",
      lastLoginAt: "2026-06-11T01:00:00Z",
    },
    site: {
      id: "site-1",
      accountId: "acct-h5",
      siteKey: "mall-cn",
      brandName: "Brand mall-cn",
      domain: "mall-cn.example.com",
      defaultLanguage: "zh-CN",
    },
    session: {
      expiresAt: "2026-06-12T00:00:00Z",
      refreshExpiresAt: "2026-06-18T00:00:00Z",
    },
  };
}

function createHomePayload(): Record<string, unknown> {
  return {
    member: {
      userId: "user-1",
      publicUserId: "h5-38271456",
      accountId: "acct-h5",
      siteId: "site-1",
      siteKey: "mall-cn",
      memberNo: "38271456",
      accountIdMasked: "382***56",
      inviteCode: "INV-ABCD1234",
      phone: "13800000000",
      displayName: "Demo Member",
      languageCode: "zh-CN",
      createdAt: "2026-06-11T00:00:00Z",
      lastLoginAt: "2026-06-11T01:00:00Z",
    },
    site: {
      id: "site-1",
      accountId: "acct-h5",
      siteKey: "mall-cn",
      brandName: "Brand mall-cn",
      domain: "mall-cn.example.com",
      defaultLanguage: "zh-CN",
    },
    taskSummary: {
      total: 3,
      available: 1,
      claimed: 1,
      pendingReview: 1,
      completed: 0,
      rejected: 0,
    },
    openTicketCount: 2,
    unreadMessageCount: 3,
    pendingClaimCount: 1,
    activeCount: 1,
    expiringCount: 0,
    recentMessages: [
      {
        id: "msg-1",
        category: "wallet",
        title: "Wallet notice",
        bodyText: "Recent wallet message",
        isRead: false,
        readAt: null,
        createdAt: "2026-06-11T02:00:00Z",
      },
    ],
    leaderboard: [
      {
        rank: 1,
        accountIdMasked: "382***56",
        amount: 120,
        currency: "USD",
      },
    ],
    wallet: {
      systemBalance: 220,
      taskBalance: 40,
      currency: "USD",
    },
    verification: {
      currentStatus: "pending",
      hasActiveRequest: true,
    },
    fragments: {
      rewardName: "Star Gift Box",
      completedCount: 1,
      totalCount: 3,
      missingCount: 2,
      canExchange: false,
      shippingOrderCount: 1,
      latestShippingStatus: "submitted",
    },
  };
}

function createDashboardState() {
  return {
    site: {
      site_key: "mall-cn",
      brand_name: "Brand mall-cn",
      tagline: "Demo tagline",
      accent_color: "#1677ff",
      default_language: "zh-CN",
    },
    member: {
      accountId: "38271456",
      phone: "13800000000",
      publicUserId: "h5-38271456",
      displayName: "Demo Member",
      inviteCode: "INV-ABCD1234",
      languageCode: "zh-CN",
      accountIdMasked: "382***56",
      createdAt: "2026-06-11T00:00:00Z",
    },
    wallet: {
      systemBalance: 220,
      taskBalance: 40,
      currency: "USD",
      withdrawThreshold: 100,
      canWithdraw: true,
      shortfallAmount: 0,
    },
    unreadCount: 3,
    pendingClaimCount: 1,
    activeCount: 1,
    expiringCount: 0,
    recentMessages: [],
    leaderboard: [],
    verification: {
      currentStatus: "not_submitted" as const,
      hasActiveRequest: false,
    },
    fragments: {
      rewardName: "Star Gift Box",
      completedCount: 1,
      totalCount: 3,
      missingCount: 2,
      canExchange: false,
      shippingOrderCount: 1,
      latestShippingStatus: "submitted" as const,
    },
  };
}

function createTaskPackageState(overrides: Partial<TaskPackageState> = {}): TaskPackageState {
  return {
    ...createTaskPackageStateBase(),
    ...overrides,
  };
}

function createTaskPackageStateBase(): TaskPackageState {
  return {
    id: "pkg-1",
    title: "新手任务包 A",
    description: "完成首批下单任务后可领取任务余额与碎片奖励。",
    type: "rookie" as const,
    status: "active" as const,
    rewardRatio: 0.12,
    claimedAt: "2026-06-11T00:00:00Z",
    expiresAt: "2026-06-11T12:00:00Z",
    dispatchedAt: "2026-06-11T00:00:00Z",
    completionWindowHours: 24,
    taskBalanceAwardedAt: null,
    promotion: null,
    items: [
      {
        id: "item-1",
        product_name: "Product A",
        image_url: "https://example.com/a.png",
        price: 20,
        currency: "USD",
        completed_at: null,
        order_id: null,
      },
    ],
    totalCommission: 12,
    currentCommission: 0,
    completedItems: 0,
    totalItems: 1,
    countdownSeconds: 3600,
  };
}

function createMessageState(overrides: Partial<h5MemberModule.H5MessageItem> = {}): h5MemberModule.H5MessageItem {
  return {
    id: "msg-1",
    category: "support",
    title: "工单有新回复",
    body: "请补充订单号",
    createdAt: "2026-06-11T02:00:00Z",
    isRead: false,
    ...overrides,
  };
}

function findButtonByText(text: string): HTMLButtonElement | null {
  return Array.from(document.querySelectorAll("button")).find((button) => button.textContent?.includes(text)) as HTMLButtonElement | undefined ?? null;
}

function setTextareaValue(textarea: HTMLTextAreaElement, value: string): void {
  const descriptor = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, "value");
  descriptor?.set?.call(textarea, value);
  textarea.dispatchEvent(new Event("input", { bubbles: true }));
}

function setInputValue(input: HTMLInputElement, value: string): void {
  const descriptor = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value");
  descriptor?.set?.call(input, value);
  input.dispatchEvent(new Event("input", { bubbles: true }));
}

function createTicketDetailState() {
  return {
    id: "ticket-2001",
    account_id: "acct-h5",
    public_user_id: "h5-38271456",
    category: "help" as const,
    status: "open" as const,
    priority: "normal" as const,
    subject: "Need support",
    content_preview: "Need support",
    linked_task_instance_id: null,
    source: "h5" as const,
    created_at: "2026-06-11T00:00:00Z",
    updated_at: "2026-06-11T00:05:00Z",
    last_reply_at: "2026-06-11T00:05:00Z",
    description: "Need support",
    messages: [
      {
        id: "ticket-msg-1",
        sender_type: "user" as const,
        sender_name: "Demo Member",
        content: "Need support",
        created_at: "2026-06-11T00:00:00Z",
        internal_only: false,
      },
    ],
  };
}

function createTaskPackageDetailState() {
  return {
    id: "pkg-1",
    title: "Starter Package",
    description: "Starter package detail",
    type: "rookie" as const,
    status: "active" as const,
    rewardRatio: 0.2,
    claimedAt: "2026-06-11T00:00:00Z",
    expiresAt: "2026-06-12T00:00:00Z",
    dispatchedAt: "2026-06-11T00:00:00Z",
    completionWindowHours: 24,
    items: [
      {
        id: "item-1",
        product_name: "Demo Product",
        image_url: "https://example.com/demo.png",
        price: 20,
        currency: "USD",
        completed_at: null,
        order_id: null,
      },
    ],
    promotion: null,
    taskBalanceAwardedAt: null,
    totalCommission: 4,
    currentCommission: 0,
    completedItems: 0,
    totalItems: 1,
    countdownSeconds: 3600,
  };
}

function createTaskInstanceState(
  overrides: Partial<h5MemberModule.H5TaskInstance> = {},
): h5MemberModule.H5TaskInstance {
  return {
    id: "pkg-1",
    title: "Starter Package",
    description: "Starter package detail",
    type: "rookie",
    status: "active",
    rewardRatio: 0.2,
    rewardAmount: 4,
    completedCount: 0,
    totalCount: 1,
    systemBalance: 220,
    products: [
      {
        id: "item-1",
        productName: "Demo Product",
        imageUrl: "https://example.com/demo.png",
        price: 20,
        currency: "USD",
        status: "available",
      },
    ],
    ...overrides,
  };
}

function createTaskPackagePayload(): Record<string, unknown> {
  return {
    id: "pkg-1",
    title: "Starter Package",
    description: "Starter package detail",
    type: "rookie",
    status: "active",
    rewardRatio: 0.2,
    claimedAt: "2026-06-11T00:00:00Z",
    expiresAt: "2026-06-12T00:00:00Z",
    dispatchedAt: "2026-06-11T00:00:00Z",
    completionWindowHours: 24,
    items: [
      {
        id: "item-1",
        productName: "Demo Product",
        imageUrl: "https://example.com/demo.png",
        price: 20,
        currency: "USD",
        completedAt: null,
        orderId: null,
      },
    ],
    promotion: {
      metric: "invited_registrations",
      current: 2,
      target: 10,
      inviteCode: "PROMO-38271456",
    },
    taskBalanceAwardedAt: null,
    totalCommission: 4,
    currentCommission: 0,
    completedItems: 0,
    totalItems: 1,
    countdownSeconds: 3600,
  };
}

function createPurchasePayload(): Record<string, unknown> {
  return {
    success: true,
    order: {
      id: "order-1",
      orderNo: "ORD-10001",
      packageId: "pkg-1",
      packageTitle: "Starter Package",
      productName: "Demo Product",
      amount: 20,
      currency: "USD",
      status: "paid",
      createdAt: "2026-06-11T00:10:00Z",
      sourceLabel: "Starter Package",
    },
    taskPackage: {
      ...createTaskPackagePayload(),
      currentCommission: 4,
      completedItems: 1,
      items: [
        {
          id: "item-1",
          productName: "Demo Product",
          imageUrl: "https://example.com/demo.png",
          price: 20,
          currency: "USD",
          completedAt: "2026-06-11T00:10:00Z",
          orderId: "order-1",
        },
      ],
    },
    wallet: {
      systemBalance: 200,
      taskBalance: 40,
      currency: "USD",
      withdrawThreshold: 100,
      canWithdraw: true,
      shortfallAmount: 0,
    },
    fragmentDrop: {
      id: "drop-1",
      fragmentId: "fragment-star",
      fragmentKey: "fragment-star",
      fragmentName: "Star Ray Fragment",
      source: "task",
      createdAt: "2026-06-11T00:10:00Z",
    },
    reason: null,
  };
}

function createWalletSummaryPayload(): Record<string, unknown> {
  return {
    systemBalance: 220,
    taskBalance: 40,
    currency: "USD",
    withdrawThreshold: 100,
    canWithdraw: true,
    shortfallAmount: 0,
  };
}

function createOrderPayload(): Record<string, unknown> {
  return {
    id: "order-1",
    orderNo: "ORD-10001",
    packageId: "pkg-1",
    packageTitle: "Starter Package",
    productName: "Demo Product",
    amount: 20,
    currency: "USD",
    status: "paid",
    createdAt: "2026-06-11T00:10:00Z",
    sourceLabel: "Starter Package",
  };
}

function createWalletTransactionPayload(): Record<string, unknown> {
  return {
    id: "txn-1",
    ledgerType: "system",
    transactionType: "purchase",
    direction: "debit",
    amount: 20,
    currency: "USD",
    status: "paid",
    note: "Starter Package / Demo Product",
    displayCategory: "wallet_debit",
    displayTitle: "Starter Package / Demo Product",
    createdAt: "2026-06-11T00:10:00Z",
  };
}

function createWithdrawalPayload(): Record<string, unknown> {
  return {
    id: "withdraw-1",
    requestNo: "WD-10001",
    amount: 120,
    cashAmount: 100,
    bonusAmount: 20,
    actualPayoutAmount: 118.8,
    currency: "USD",
    status: "submitted",
    rejectionReason: null,
    createdAt: "2026-06-11T00:10:00Z",
    reviewedAt: null,
    paidAt: null,
    history: [],
  };
}

function createLeaderboardPayload(): Record<string, unknown> {
  return {
    rank: 1,
    accountIdMasked: "382***56",
    amount: 120,
    currency: "USD",
  };
}

function createMessagePayload(): Record<string, unknown> {
  return {
    id: "msg-1",
    category: "wallet",
    title: "Wallet notice",
    bodyText: "Message body",
    isRead: false,
    readAt: null,
    createdAt: "2026-06-11T02:00:00Z",
  };
}

function createFragmentOverviewPayload(): Record<string, unknown> {
  return {
    inventory: [
      {
        id: "inventory-1",
        fragmentKey: "fragment-star",
        name: "Star Ray Fragment",
        rarity: "epic",
        color: "#ef4444",
        owned: 1,
        required: 1,
      },
    ],
    dropLogs: [
      {
        id: "drop-1",
        fragmentId: "fragment-star",
        fragmentKey: "fragment-star",
        fragmentName: "Star Ray Fragment",
        source: "task",
        createdAt: "2026-06-11T02:00:00Z",
      },
    ],
    rewardName: "Star Gift Box",
    shippingOrders: [
      {
        id: "shipping-1",
        rewardName: "Star Gift Box",
        status: "submitted",
        createdAt: "2026-06-11T03:00:00Z",
        address: {
          receiver: "Demo User",
          phone: "13800000000",
          country: "China",
          province: "Guangdong",
          city: "Shenzhen",
          addressLine: "Nanshan Science Park",
        },
      },
    ],
  };
}

function createWhatsAppBindingPayload(overrides?: Record<string, unknown>): Record<string, unknown> {
  return {
    isBound: false,
    bindingStatus: "not_started",
    requestId: null,
    phoneNumber: null,
    requestedAt: null,
    startCount: 0,
    lastUpdatedAt: null,
    ...overrides,
  };
}

function createVerificationDocumentResponsePayload(
  overrides: Record<string, unknown> = {},
): Record<string, unknown> {
  return {
    id: "doc-1",
    file_name: "passport-front.jpg",
    mime_type: "image/jpeg",
    storage_key: "member-verification/passport-front.jpg",
    metadata_json: {
      side: "front",
    },
    created_at: "2026-06-11T10:00:10Z",
    ...overrides,
  };
}

function createVerificationRequestResponsePayload(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    id: "vr-1",
    request_type: "identity",
    status: "under_review",
    notes: "Please verify my identity.",
    review_note: "Platform is reviewing the submitted documents.",
    reviewer_actor_id: "risk-reviewer-1",
    reviewed_at: null,
    created_at: "2026-06-11T10:00:00Z",
    updated_at: "2026-06-11T10:05:00Z",
    documents: [createVerificationDocumentResponsePayload()],
    ...overrides,
  };
}

function createVerificationRequestCreatePayload(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    requestType: "identity",
    notes: "Please verify my identity.",
    documents: [
      {
        fileName: "passport-front.jpg",
        mimeType: "image/jpeg",
        storageKey: "member-verification/passport-front.jpg",
        metadataJson: {
          side: "front",
        },
      },
    ],
    ...overrides,
  };
}

function createVerificationSummaryPayload(): Record<string, unknown> {
  return {
    current_status: "under_review",
    has_active_request: true,
    active_request: createVerificationRequestResponsePayload({
      id: "vr-1",
      status: "under_review",
      notes: "Please verify my identity.",
      reviewed_at: null,
      documents: [
        createVerificationDocumentResponsePayload({
          id: "doc-1",
          file_name: "passport-front.jpg",
          mime_type: "image/jpeg",
          storage_key: "member-verification/passport-front.jpg",
          metadata_json: {
            side: "front",
          },
          created_at: "2026-06-11T10:00:10Z",
        }),
      ],
    }),
    history: [
      createVerificationRequestResponsePayload({
        id: "vr-1",
        status: "under_review",
        notes: "Please verify my identity.",
        reviewed_at: null,
        documents: [
          createVerificationDocumentResponsePayload({
            id: "doc-1",
            file_name: "passport-front.jpg",
            mime_type: "image/jpeg",
            storage_key: "member-verification/passport-front.jpg",
            metadata_json: {
              side: "front",
            },
            created_at: "2026-06-11T10:00:10Z",
          }),
        ],
      }),
      createVerificationRequestResponsePayload({
        id: "vr-2",
        request_type: "identity",
        status: "rejected",
        notes: "Missing back side document.",
        reviewed_at: "2026-06-10T09:20:00Z",
        created_at: "2026-06-10T09:00:00Z",
        updated_at: "2026-06-10T09:20:00Z",
        documents: [
          createVerificationDocumentResponsePayload({
            id: "doc-2",
            file_name: "passport-back.jpg",
            mime_type: "image/jpeg",
            storage_key: "member-verification/passport-back.jpg",
            metadata_json: {
              side: "back",
            },
            created_at: "2026-06-10T09:00:10Z",
          }),
        ],
      }),
    ],
  };
}

function getRequestBody(callIndex: number, fetchMock: ReturnType<typeof vi.fn>): Record<string, unknown> {
  const request = fetchMock.mock.calls[callIndex]?.[1] as RequestInit | undefined;
  return JSON.parse(String(request?.body ?? "{}")) as Record<string, unknown>;
}

function getVerificationService(): typeof h5MemberModule & Record<string, (...args: any[]) => Promise<any>> {
  return h5MemberModule as typeof h5MemberModule & Record<string, (...args: any[]) => Promise<any>>;
}

async function flushEffects(): Promise<void> {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
}

async function renderApp(locationKey: string, navigate = vi.fn()): Promise<{
  navigate: ReturnType<typeof vi.fn>;
}> {
  const { H5App } = await import("../pages/H5App");
  const { sessionManager } = await import("./h5SessionManager");
  const isAuthRoute = locationKey.startsWith("/h5/login") || locationKey.startsWith("/h5/register");
  const hasMockedFetch = vi.isMockFunction(globalThis.fetch);
  const shouldSeedRuntimeAuth = !isAuthRoute || hasMockedFetch;

  if (shouldSeedRuntimeAuth) {
    window.localStorage.setItem(MEMBER_SESSION_KEY, JSON.stringify(LEGACY_SESSION));
    sessionManager.setSession("test-access-token", "test-refresh-token", 3600);
    sessionManager.setUserInfo({
      accountId: LEGACY_SESSION.accountId,
      phone: LEGACY_SESSION.phone,
      publicUserId: LEGACY_SESSION.publicUserId,
      displayName: LEGACY_SESSION.displayName,
      inviteCode: LEGACY_SESSION.inviteCode,
      avatarUrl: null,
    });
  }

  const container = document.createElement("div");
  document.body.appendChild(container);
  mountedContainers.push(container);

  const root = createRoot(container);
  mountedRoots.push(root);

  await act(async () => {
    root.render(createElement(H5App, { locationKey, navigate }));
  });
  await flushEffects();

  return { navigate };
}

describe("H5 member auth service contract", () => {
  beforeEach(() => {
    installLocalStorageMock();
    window.localStorage.clear();
    window.localStorage.setItem("h5-lang", "zh-CN");
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
    vi.unstubAllEnvs();
  });

  afterEach(async () => {
    const { sessionManager } = await import("./h5SessionManager");
    while (mountedRoots.length > 0) {
      const root = mountedRoots.pop();
      await act(async () => {
        root?.unmount();
      });
    }
    while (mountedContainers.length > 0) {
      mountedContainers.pop()?.remove();
    }
    vi.restoreAllMocks();
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
    sessionManager.clearSession();
    delete (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT;
    window.localStorage.clear();
  });

  it("logs in through backend auth, uses credentials include, and persists the member session cache", async () => {
    const fetchMock = vi.fn().mockResolvedValue(createJsonResponse(createAuthPayload()));
    vi.stubGlobal("fetch", fetchMock);

    const profile = await loginMember({
      siteKey: "mall-cn",
      phone: "13800000000",
      password: "pass123456",
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/h5/auth/login");
    const request = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(request.credentials).toBe("include");
    expect(request.headers).not.toMatchObject({ Authorization: expect.anything() });
    expect(getRequestBody(0, fetchMock)).toMatchObject({
      siteKey: "mall-cn",
      phone: "13800000000",
      password: "pass123456",
    });
    expect(getRequestBody(0, fetchMock)).not.toHaveProperty("publicUserId");
    expect(profile.accountId).toBe("38271456");
    expect(profile.accountIdMasked).toBe("382***56");
    expect(profile.createdAt).toBe("2026-06-11T00:00:00Z");
    expect(window.localStorage.getItem(MEMBER_SESSION_KEY)).toContain("\"accountId\":\"38271456\"");
  });

  it("registers through backend auth with confirmPassword and persists the member session cache", async () => {
    const fetchMock = vi.fn().mockResolvedValue(createJsonResponse(createAuthPayload()));
    vi.stubGlobal("fetch", fetchMock);

    const profile = await registerMember({
      siteKey: "mall-cn",
      phone: "13800000000",
      password: "pass123456",
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/h5/auth/register");
    const request = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(request.credentials).toBe("include");
    expect(getRequestBody(0, fetchMock)).toMatchObject({
      siteKey: "mall-cn",
      phone: "13800000000",
      password: "pass123456",
      confirmPassword: "pass123456",
    });
    expect(getRequestBody(0, fetchMock)).not.toHaveProperty("accountId");
    expect(profile.publicUserId).toBe("h5-38271456");
    expect(profile.accountId).toBe("38271456");
    expect(window.localStorage.getItem(MEMBER_SESSION_KEY)).toContain("\"publicUserId\":\"h5-38271456\"");
  });

  it("refreshes the auth session after auth/me returns 401", async () => {
    window.localStorage.setItem(MEMBER_SESSION_KEY, JSON.stringify(LEGACY_SESSION));
    Object.defineProperty(document, "cookie", {
      configurable: true,
      get: () => "h5_member_session=active-cookie; h5_member_refresh=refresh-cookie",
    });
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(createErrorResponse(401, "Session expired"))
      .mockResolvedValueOnce(createJsonResponse(createAuthPayload()))
      .mockResolvedValueOnce(createJsonResponse(createAuthPayload()));
    vi.stubGlobal("fetch", fetchMock);

    const session = await getCurrentMemberSession();

    expect(session?.accountId).toBe("38271456");
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/h5/auth/me");
    expect(fetchMock.mock.calls[1]?.[0]).toBe("/api/h5/auth/refresh");
    expect(fetchMock.mock.calls[2]?.[0]).toBe("/api/h5/auth/me");
    expect((fetchMock.mock.calls[1]?.[1] as RequestInit).credentials).toBe("include");
    expect((fetchMock.mock.calls[1]?.[1] as RequestInit).method).toBe("POST");
    expect(window.localStorage.getItem(MEMBER_SESSION_KEY)).toContain("\"accountId\":\"38271456\"");
  });

  it("clears local cache and returns null when auth/me and refresh both return 401", async () => {
    window.localStorage.setItem(MEMBER_SESSION_KEY, JSON.stringify(LEGACY_SESSION));
    vi.stubEnv("VITE_H5_MEMBER_LEGACY_FALLBACK", "false");
    Object.defineProperty(document, "cookie", {
      configurable: true,
      get: () => "h5_member_session=active-cookie; h5_member_refresh=refresh-cookie",
    });
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(createErrorResponse(401, "Session expired"))
      .mockResolvedValueOnce(createErrorResponse(401, "Refresh expired"));
    vi.stubGlobal("fetch", fetchMock);

    const session = await getCurrentMemberSession();

    expect(session).toBeNull();
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(window.localStorage.getItem(MEMBER_SESSION_KEY)).toBeNull();
  });

  it("loads member home through refresh retry and maps backend dashboard fields", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(createErrorResponse(401, "Session expired"))
      .mockResolvedValueOnce(createJsonResponse(createAuthPayload()))
      .mockResolvedValueOnce(createJsonResponse(createHomePayload()));
    vi.stubGlobal("fetch", fetchMock);

    const dashboard = await getMemberHomeDashboard("mall-cn");

    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/h5/member/home");
    expect(fetchMock.mock.calls[1]?.[0]).toBe("/api/h5/auth/refresh");
    expect(fetchMock.mock.calls[2]?.[0]).toBe("/api/h5/member/home");
    expect((fetchMock.mock.calls[0]?.[1] as RequestInit | undefined)?.body).toBeUndefined();
    expect(dashboard.member.accountId).toBe("38271456");
    expect(dashboard.wallet.systemBalance).toBe(220);
    expect(dashboard.wallet.taskBalance).toBe(40);
    expect(dashboard.wallet.currency).toBe("USD");
    expect(dashboard.recentMessages[0]?.body).toBe("Recent wallet message");
    expect(dashboard.unreadCount).toBe(3);
    expect(dashboard.leaderboard[0]?.accountIdMasked).toBe("382***56");
    expect(dashboard.verification.currentStatus).toBe("pending");
    expect(dashboard.verification.hasActiveRequest).toBe(true);
    expect(dashboard.fragments.rewardName).toBe("Star Gift Box");
    expect(dashboard.fragments.completedCount).toBe(1);
    expect(dashboard.fragments.totalCount).toBe(3);
    expect(dashboard.fragments.missingCount).toBe(2);
    expect(dashboard.fragments.canExchange).toBe(false);
    expect(dashboard.fragments.shippingOrderCount).toBe(1);
    expect(dashboard.fragments.latestShippingStatus).toBe("submitted");
  });

  it("falls back to legacy local session only when explicitly enabled", async () => {
    window.localStorage.setItem(MEMBER_SESSION_KEY, JSON.stringify(LEGACY_SESSION));
    vi.stubEnv("VITE_H5_MEMBER_LEGACY_FALLBACK", "true");
    Object.defineProperty(document, "cookie", {
      configurable: true,
      get: () => "h5_member_session=active-cookie; h5_member_refresh=refresh-cookie",
    });
    const fetchMock = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));
    vi.stubGlobal("fetch", fetchMock);

    const session = await getCurrentMemberSession();

    expect(session).toMatchObject(LEGACY_SESSION);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("falls back to legacy local session in dev when auth endpoint returns html instead of json", async () => {
    window.localStorage.setItem(MEMBER_SESSION_KEY, JSON.stringify(LEGACY_SESSION));
    Object.defineProperty(document, "cookie", {
      configurable: true,
      get: () => "h5_member_session=active-cookie; h5_member_refresh=refresh-cookie",
    });
    const fetchMock = vi.fn().mockResolvedValue(createHtmlResponse());
    vi.stubGlobal("fetch", fetchMock);

    const session = await getCurrentMemberSession();

    expect(session).toMatchObject(LEGACY_SESSION);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/h5/auth/me");
  });

  it("surfaces backend detail text instead of raw json payload on login failure", async () => {
    const fetchMock = vi.fn().mockResolvedValue(createErrorResponse(409, "鎵嬫満鍙峰凡娉ㄥ唽"));
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      registerMember({
        siteKey: "mall-cn",
        phone: "13800000000",
        password: "pass123456",
      }),
    ).rejects.toThrow("鎵嬫満鍙峰凡娉ㄥ唽");
  });

  it("surfaces site-not-found detail instead of collapsing login 401 into invalid credentials", async () => {
    const fetchMock = vi.fn().mockResolvedValue(createErrorResponse(401, "Site 'mall-cn' was not found."));
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      loginMember({
        siteKey: "mall-cn",
        phone: "13800000000",
        password: "pass123456",
      }),
    ).rejects.toThrow("Site 'mall-cn' was not found.");
  });

  it("loads the current member session from auth/me before using cached state", async () => {
    window.localStorage.setItem(MEMBER_SESSION_KEY, JSON.stringify(LEGACY_SESSION));
    Object.defineProperty(document, "cookie", {
      configurable: true,
      get: () => "h5_member_session=active-cookie; h5_member_refresh=refresh-cookie",
    });
    const fetchMock = vi.fn().mockResolvedValue(createJsonResponse(createAuthPayload()));
    vi.stubGlobal("fetch", fetchMock);

    const session = await getCurrentMemberSession();

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/h5/auth/me");
    expect((fetchMock.mock.calls[0]?.[1] as RequestInit).credentials).toBe("include");
    expect(session).not.toBeNull();
    expect(session?.accountId).toBe("38271456");
    expect(window.localStorage.getItem(MEMBER_SESSION_KEY)).toContain("\"accountId\":\"38271456\"");
  });

  it("skips backend auth probes in dev when no h5 auth cookies exist and falls back to the local member session", async () => {
    window.localStorage.setItem(MEMBER_SESSION_KEY, JSON.stringify(LEGACY_SESSION));
    Object.defineProperty(document, "cookie", {
      configurable: true,
      get: () => "",
    });
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const session = await getCurrentMemberSession();

    expect(session).toMatchObject(LEGACY_SESSION);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("logs out through backend auth, uses credentials include, and clears the member session cache", async () => {
    window.localStorage.setItem(MEMBER_SESSION_KEY, JSON.stringify(LEGACY_SESSION));
    const fetchMock = vi.fn().mockResolvedValue(createJsonResponse({ ok: true }));
    vi.stubGlobal("fetch", fetchMock);

    await logoutMember();

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/h5/auth/logout");
    expect((fetchMock.mock.calls[0]?.[1] as RequestInit).credentials).toBe("include");
    expect(window.localStorage.getItem(MEMBER_SESSION_KEY)).toBeNull();
  });

  it("loads task packages through backend contract and refresh retry", async () => {
    window.localStorage.setItem(MEMBER_SESSION_KEY, JSON.stringify(LEGACY_SESSION));
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(createErrorResponse(401, "Session expired"))
      .mockResolvedValueOnce(createJsonResponse(createAuthPayload()))
      .mockResolvedValueOnce(createJsonResponse([createTaskPackagePayload()]));
    vi.stubGlobal("fetch", fetchMock);

    const packages = await h5MemberModule.listTaskPackages();

    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/h5/task-packages");
    expect(fetchMock.mock.calls[1]?.[0]).toBe("/api/h5/auth/refresh");
    expect(fetchMock.mock.calls[2]?.[0]).toBe("/api/h5/task-packages");
    expect(packages[0]).toMatchObject({
      id: "pkg-1",
      rewardRatio: 0.2,
      dispatchedAt: "2026-06-11T00:00:00Z",
      countdownSeconds: 3600,
    });
    expect(packages[0]?.items[0]).toMatchObject({
      product_name: "Demo Product",
      image_url: "https://example.com/demo.png",
    });
    expect(packages[0]?.promotion?.inviteCode).toBe("PROMO-38271456");
  });

  it("purchases task package items through backend contract", async () => {
    window.localStorage.setItem(MEMBER_SESSION_KEY, JSON.stringify(LEGACY_SESSION));
    const fetchMock = vi.fn().mockResolvedValue(createJsonResponse(createPurchasePayload()));
    vi.stubGlobal("fetch", fetchMock);

    const purchase = await h5MemberModule.completeTaskPackagePurchase("pkg-1", "item-1");

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/h5/task-packages/pkg-1/items/item-1/purchase");
    expect((fetchMock.mock.calls[0]?.[1] as RequestInit | undefined)?.method).toBe("POST");
    expect(purchase.success).toBe(true);
    expect(purchase.wallet).toMatchObject({
      systemBalance: 200,
      taskBalance: 40,
      canWithdraw: true,
    });
    expect(purchase.order).toMatchObject({
      orderNo: "ORD-10001",
      packageId: "pkg-1",
      productName: "Demo Product",
    });
    expect(purchase.taskPackage.items[0]).toMatchObject({
      completed_at: "2026-06-11T00:10:00Z",
      order_id: "order-1",
    });
    expect(purchase.fragmentDrop?.fragmentName).toBe("Star Ray Fragment");
  });

  it("loads backend commerce aggregates instead of local prototype state", async () => {
    window.localStorage.setItem(MEMBER_SESSION_KEY, JSON.stringify(LEGACY_SESSION));
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(createJsonResponse([createOrderPayload()]))
      .mockResolvedValueOnce(createJsonResponse(createWalletSummaryPayload()))
      .mockResolvedValueOnce(createJsonResponse([createWalletTransactionPayload()]))
      .mockResolvedValueOnce(createJsonResponse([createWithdrawalPayload()]))
      .mockResolvedValueOnce(createJsonResponse([createLeaderboardPayload()]))
      .mockResolvedValueOnce(createJsonResponse(createWithdrawalPayload()))
      .mockResolvedValueOnce(createJsonResponse(createWalletSummaryPayload()));
    vi.stubGlobal("fetch", fetchMock);

    const orders = await h5MemberModule.listMemberOrders();
    const wallet = await h5MemberModule.getWalletSummary();
    const transactions = await h5MemberModule.listWalletTransactions();
    const withdrawals = await h5MemberModule.listWithdrawRequests();
    const leaderboard = await h5MemberModule.getWithdrawLeaderboard();
    const walletAfterWithdraw = await h5MemberModule.createWithdrawRequest(120);

    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/h5/orders");
    expect(fetchMock.mock.calls[1]?.[0]).toBe("/api/h5/wallet");
    expect(fetchMock.mock.calls[2]?.[0]).toBe("/api/h5/wallet/transactions");
    expect(fetchMock.mock.calls[3]?.[0]).toBe("/api/h5/withdrawals");
    expect(fetchMock.mock.calls[4]?.[0]).toBe("/api/h5/withdraw-leaderboard");
    expect(fetchMock.mock.calls[5]?.[0]).toBe("/api/h5/withdrawals");
    expect(fetchMock.mock.calls[6]?.[0]).toBe("/api/h5/wallet");
    expect(getRequestBody(5, fetchMock)).toMatchObject({ amount: 120 });
    expect(orders[0]?.orderNo).toBe("ORD-10001");
    expect(wallet.systemBalance).toBe(220);
    expect(transactions[0]?.transactionType).toBe("purchase");
    expect(transactions[0]?.displayCategory).toBe("wallet_debit");
    expect(transactions[0]?.displayTitle).toBe("Starter Package / Demo Product");
    expect(withdrawals[0]).toMatchObject({
      id: "withdraw-1",
      amount: 120,
      cashAmount: 100,
      bonusAmount: 20,
      actualPayoutAmount: 118.8,
      status: "submitted",
    });
    expect(leaderboard[0]?.accountIdMasked).toBe("382***56");
    expect(walletAfterWithdraw.systemBalance).toBe(220);
  });

  it("loads and updates member messages through backend contract", async () => {
    window.localStorage.setItem(MEMBER_SESSION_KEY, JSON.stringify(LEGACY_SESSION));
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(createJsonResponse([createMessagePayload()]))
      .mockResolvedValueOnce(createJsonResponse({ ...createMessagePayload(), isRead: true }))
      .mockResolvedValueOnce(createJsonResponse({ updated: 3 }));
    vi.stubGlobal("fetch", fetchMock);

    const messages = await h5MemberModule.listMemberMessages();
    await h5MemberModule.markMessageRead("msg-1");
    await h5MemberModule.markAllMessagesRead();

    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/h5/messages");
    expect(fetchMock.mock.calls[1]?.[0]).toBe("/api/h5/messages/msg-1/read");
    expect(fetchMock.mock.calls[2]?.[0]).toBe("/api/h5/messages/read-all");
    expect((fetchMock.mock.calls[1]?.[1] as RequestInit | undefined)?.method).toBe("POST");
    expect(messages[0]).toMatchObject({
      body: "Message body",
      isRead: false,
      createdAt: "2026-06-11T02:00:00Z",
    });
  });

  it("loads fragment overview and submits exchanges through backend contract", async () => {
    window.localStorage.setItem(MEMBER_SESSION_KEY, JSON.stringify(LEGACY_SESSION));
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(createJsonResponse(createFragmentOverviewPayload()))
      .mockResolvedValueOnce(createJsonResponse(createFragmentOverviewPayload()))
      .mockResolvedValueOnce(createJsonResponse(createFragmentOverviewPayload()));
    vi.stubGlobal("fetch", fetchMock);

    const overview = await h5MemberModule.getFragmentsOverview();
    const checkedIn = await h5MemberModule.performDailyCheckIn();
    const exchanged = await h5MemberModule.createFragmentExchange({
      receiver: "Demo User",
      phone: "13800000000",
      country: "China",
      province: "Guangdong",
      city: "Shenzhen",
      addressLine: "Nanshan Science Park",
    });

    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/h5/fragments");
    expect(fetchMock.mock.calls[1]?.[0]).toBe("/api/h5/fragments/check-in");
    expect(fetchMock.mock.calls[2]?.[0]).toBe("/api/h5/fragments/exchanges");
    expect(getRequestBody(2, fetchMock)).toMatchObject({
      receiver: "Demo User",
      addressLine: "Nanshan Science Park",
    });
    expect(getRequestBody(2, fetchMock)).not.toHaveProperty("address_line");
    expect(overview.rewardName).toBe("Star Gift Box");
    expect(overview.inventory[0]).toMatchObject({
      name: "Star Ray Fragment",
      owned: 1,
    });
    expect(checkedIn.dropLogs[0]?.fragmentName).toBe("Star Ray Fragment");
    expect(exchanged.shippingOrders[0]?.address?.addressLine).toBe("Nanshan Science Park");
  });

  it("loads WhatsApp binding state through backend contract and refresh retry", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(createErrorResponse(401, "Session expired"))
      .mockResolvedValueOnce(createJsonResponse(createAuthPayload()))
      .mockResolvedValueOnce(createJsonResponse(createWhatsAppBindingPayload()));
    vi.stubGlobal("fetch", fetchMock);

    const binding = await h5MemberModule.getWhatsAppBinding();

    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/h5/whatsapp-binding");
    expect(fetchMock.mock.calls[1]?.[0]).toBe("/api/h5/auth/refresh");
    expect(fetchMock.mock.calls[2]?.[0]).toBe("/api/h5/whatsapp-binding");
    expect(binding).toMatchObject({
      isBound: false,
      bindingStatus: "not_started",
      requestId: null,
      phoneNumber: null,
      requestedAt: null,
      startCount: 0,
      lastUpdatedAt: null,
    });
  });

  it("starts WhatsApp binding through backend contract", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        createJsonResponse(
          createWhatsAppBindingPayload({
            bindingStatus: "pending",
            requestId: "wa-bind-1",
            requestedAt: "2026-06-11T05:00:00Z",
            startCount: 1,
            lastUpdatedAt: "2026-06-11T05:00:00Z",
          }),
        ),
      );
    vi.stubGlobal("fetch", fetchMock);

    const binding = await h5MemberModule.startWhatsAppBinding();

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/h5/whatsapp-binding/start");
    expect((fetchMock.mock.calls[0]?.[1] as RequestInit | undefined)?.method).toBe("POST");
    expect(binding.bindingStatus).toBe("pending");
    expect(binding.requestId).toBe("wa-bind-1");
    expect(binding.requestedAt).toBe("2026-06-11T05:00:00Z");
    expect(binding.startCount).toBe(1);
    expect(binding.lastUpdatedAt).toBe("2026-06-11T05:00:00Z");
  });

  it("loads member verification summary through backend contract and maps camelCase fields", async () => {
    const fetchMock = vi.fn().mockResolvedValue(createJsonResponse(createVerificationSummaryPayload()));
    vi.stubGlobal("fetch", fetchMock);

    const verificationApi = getVerificationService();
    const summary = await verificationApi.getMemberVerificationSummary();

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/h5/member/verification");
    expect(summary).toMatchObject({
      currentStatus: "under_review",
      hasActiveRequest: true,
    });
    expect(summary).not.toHaveProperty("current_status");
    expect(summary.activeRequest).toMatchObject({
      id: "vr-1",
      requestType: "identity",
      status: "under_review",
      reviewNote: "Platform is reviewing the submitted documents.",
      reviewerActorId: "risk-reviewer-1",
      reviewedAt: null,
    });
    expect(summary.activeRequest).not.toHaveProperty("request_type");
    expect(summary.activeRequest?.documents[0]).toMatchObject({
      id: "doc-1",
      fileName: "passport-front.jpg",
      mimeType: "image/jpeg",
      storageKey: "member-verification/passport-front.jpg",
      metadataJson: {
        side: "front",
      },
    });
    expect(summary.activeRequest?.documents[0]).not.toHaveProperty("file_name");
    expect(summary.history).toHaveLength(2);
    expect(summary.history[1]).toMatchObject({
      id: "vr-2",
      status: "rejected",
      reviewNote: "Platform is reviewing the submitted documents.",
      reviewerActorId: "risk-reviewer-1",
      reviewedAt: "2026-06-10T09:20:00Z",
    });
    expect(summary.history[1]?.documents[0]).toMatchObject({
      id: "doc-2",
      fileName: "passport-back.jpg",
      metadataJson: {
        side: "back",
      },
    });
  });

  it("lists member verification requests through backend contract and maps nested document fields", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      createJsonResponse([
        createVerificationRequestResponsePayload({
          id: "vr-1",
          status: "under_review",
          documents: [
            createVerificationDocumentResponsePayload({
              id: "doc-1",
              file_name: "passport-front.jpg",
              mime_type: "image/jpeg",
              storage_key: "member-verification/passport-front.jpg",
              metadata_json: {
                side: "front",
              },
              created_at: "2026-06-11T10:00:10Z",
            }),
          ],
        }),
        createVerificationRequestResponsePayload({
          id: "vr-2",
          status: "rejected",
          reviewed_at: "2026-06-10T09:20:00Z",
          created_at: "2026-06-10T09:00:00Z",
          updated_at: "2026-06-10T09:20:00Z",
          documents: [
            createVerificationDocumentResponsePayload({
              id: "doc-2",
              file_name: "passport-back.jpg",
              mime_type: "image/jpeg",
              storage_key: "member-verification/passport-back.jpg",
              metadata_json: {
                side: "back",
              },
              created_at: "2026-06-10T09:00:10Z",
            }),
          ],
        }),
      ]),
    );
    vi.stubGlobal("fetch", fetchMock);

    const verificationApi = getVerificationService();
    const requests = await verificationApi.listMemberVerificationRequests();

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/h5/member/verification/requests");
    expect(requests).toHaveLength(2);
    expect(requests[0]).toMatchObject({
      id: "vr-1",
      requestType: "identity",
      status: "under_review",
      reviewNote: "Platform is reviewing the submitted documents.",
      reviewerActorId: "risk-reviewer-1",
      documents: [
        {
          fileName: "passport-front.jpg",
          mimeType: "image/jpeg",
          storageKey: "member-verification/passport-front.jpg",
          metadataJson: {
            side: "front",
          },
        },
      ],
    });
    expect(requests[0]).not.toHaveProperty("request_type");
    expect(requests[0].documents[0]).not.toHaveProperty("file_name");
    expect(requests[1]).toMatchObject({
      id: "vr-2",
      requestType: "identity",
      status: "rejected",
      reviewNote: "Platform is reviewing the submitted documents.",
      reviewerActorId: "risk-reviewer-1",
      reviewedAt: "2026-06-10T09:20:00Z",
      documents: [
        {
          fileName: "passport-back.jpg",
          metadataJson: {
            side: "back",
          },
        },
      ],
    });
  });

  it("creates member verification requests through backend contract and sends the expected payload", async () => {
    const payload = createVerificationRequestCreatePayload({
      notes: "Need identity review before proceeding.",
      documents: [
        {
          fileName: "identity-front.jpg",
          mimeType: "image/jpeg",
          storageKey: "member-verification/identity-front.jpg",
          metadataJson: {
            side: "front",
          },
        },
        {
          fileName: "identity-back.jpg",
          mimeType: "image/jpeg",
          storageKey: "member-verification/identity-back.jpg",
          metadataJson: {
            side: "back",
          },
        },
      ],
    });
    const fetchMock = vi.fn().mockResolvedValue(
      createJsonResponse(
        createVerificationRequestResponsePayload({
          id: "vr-9",
          request_type: "identity",
          status: "pending",
          notes: "Need identity review before proceeding.",
          reviewed_at: null,
          created_at: "2026-06-12T02:00:00Z",
          updated_at: "2026-06-12T02:00:00Z",
          documents: [
            createVerificationDocumentResponsePayload({
              id: "doc-9",
              file_name: "identity-front.jpg",
              mime_type: "image/jpeg",
              storage_key: "member-verification/identity-front.jpg",
              metadata_json: {
                side: "front",
              },
              created_at: "2026-06-12T02:00:10Z",
            }),
            createVerificationDocumentResponsePayload({
              id: "doc-10",
              file_name: "identity-back.jpg",
              mime_type: "image/jpeg",
              storage_key: "member-verification/identity-back.jpg",
              metadata_json: {
                side: "back",
              },
              created_at: "2026-06-12T02:00:20Z",
            }),
          ],
        }),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const verificationApi = getVerificationService();
    const request = await verificationApi.createMemberVerificationRequest(payload);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/h5/member/verification/requests");
    expect((fetchMock.mock.calls[0]?.[1] as RequestInit | undefined)?.method).toBe("POST");
    expect(getRequestBody(0, fetchMock)).toEqual(payload);
    expect(getRequestBody(0, fetchMock)).not.toHaveProperty("request_type");
    expect(request).toMatchObject({
      id: "vr-9",
      requestType: "identity",
      status: "pending",
      notes: "Need identity review before proceeding.",
      reviewNote: "Platform is reviewing the submitted documents.",
      reviewerActorId: "risk-reviewer-1",
      documents: [
        {
          fileName: "identity-front.jpg",
          metadataJson: {
            side: "front",
          },
        },
        {
          fileName: "identity-back.jpg",
          metadataJson: {
            side: "back",
          },
        },
      ],
    });
    expect(request.documents[0]).not.toHaveProperty("file_name");
  });

  it("loads a member verification request detail through backend contract", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      createJsonResponse(
        createVerificationRequestResponsePayload({
          id: "vr-10",
          status: "under_review",
          reviewed_at: "2026-06-12T03:30:00Z",
          created_at: "2026-06-12T03:00:00Z",
          updated_at: "2026-06-12T03:30:00Z",
          documents: [
            createVerificationDocumentResponsePayload({
              id: "doc-11",
              file_name: "passport-front.jpg",
              mime_type: "image/jpeg",
              storage_key: "member-verification/passport-front.jpg",
              metadata_json: {
                side: "front",
              },
              created_at: "2026-06-12T03:00:10Z",
            }),
            createVerificationDocumentResponsePayload({
              id: "doc-12",
              file_name: "passport-back.jpg",
              mime_type: "image/jpeg",
              storage_key: "member-verification/passport-back.jpg",
              metadata_json: {
                side: "back",
              },
              created_at: "2026-06-12T03:00:20Z",
            }),
          ],
        }),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const verificationApi = getVerificationService();
    const request = await verificationApi.getMemberVerificationRequestDetail("vr-10");

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/h5/member/verification/requests/vr-10");
    expect(request).toMatchObject({
      id: "vr-10",
      requestType: "identity",
      status: "under_review",
      reviewNote: "Platform is reviewing the submitted documents.",
      reviewerActorId: "risk-reviewer-1",
      reviewedAt: "2026-06-12T03:30:00Z",
      documents: [
        {
          id: "doc-11",
          fileName: "passport-front.jpg",
          metadataJson: {
            side: "front",
          },
        },
        {
          id: "doc-12",
          fileName: "passport-back.jpg",
          metadataJson: {
            side: "back",
          },
        },
      ],
    });
    expect(request).not.toHaveProperty("request_type");
    expect(request.documents[0]).not.toHaveProperty("file_name");
  });

  it("prioritizes wallet above tool shortcuts on home and only floats important notifications", async () => {
    vi.spyOn(h5MemberModule, "getCurrentMemberSession").mockResolvedValue({
      accountId: "38271456",
      phone: "13800000000",
      publicUserId: "h5-38271456",
      displayName: "Demo Member",
      inviteCode: "INV-ABCD1234",
    });
    vi.spyOn(h5MemberModule, "getMaskedPhone").mockResolvedValue("138****0000");
    vi.spyOn(h5MemberModule, "getMemberHomeDashboard").mockResolvedValue({
      ...createDashboardState(),
      recentMessages: [
        createMessageState({
          id: "msg-wallet",
          category: "wallet",
          title: "Withdrawal status update",
          body: "Your withdrawal request is under review.",
          isRead: false,
        }),
        createMessageState({
          id: "msg-fragment",
          category: "fragment",
          title: "纰庣墖鎺夎惤鎻愰啋",
          body: "鎮ㄤ粖鏃ュ彲缁х画绛惧埌鑾峰彇纰庣墖",
          isRead: false,
        }),
      ],
    });
    vi.spyOn(h5MemberModule, "listTaskPackages").mockResolvedValue([createTaskPackageState()]);

    await renderApp("/h5/home?site_key=mall-cn", vi.fn());

    const walletSection =
      document.querySelector(".h5-member-home-metric-grid") ??
      document.querySelector(".h5-member-home-command-panel");
    const toolsSection =
      document.querySelector(".h5-member-home-section-grid") ??
      document.querySelector(".h5-member-home-command");
    expect(walletSection).not.toBeNull();
    expect(toolsSection).not.toBeNull();
    const walletSectionNode = walletSection as HTMLElement;
    const toolsSectionNode = toolsSection as HTMLElement;
    expect(
      walletSectionNode.compareDocumentPosition(toolsSectionNode) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();

    expect(document.querySelector(".h5-member-toast-stack")).toBeNull();
  }, 10000);

  it("does not auto-surface historical unread notifications as floating toasts on home", async () => {
    vi.useFakeTimers();
    vi.spyOn(h5MemberModule, "getCurrentMemberSession").mockResolvedValue({
      accountId: "38271456",
      phone: "13800000000",
      publicUserId: "h5-38271456",
      displayName: "Demo Member",
      inviteCode: "INV-ABCD1234",
    });
    vi.spyOn(h5MemberModule, "getMaskedPhone").mockResolvedValue("138****0000");
    vi.spyOn(h5MemberModule, "getMemberHomeDashboard").mockResolvedValue({
      ...createDashboardState(),
      recentMessages: [
        createMessageState({
          id: "msg-important",
          category: "wallet",
          title: "Important toast title",
          body: "Important toast body",
          isRead: false,
        }),
      ],
    });
    vi.spyOn(h5MemberModule, "listTaskPackages").mockResolvedValue([createTaskPackageState()]);

    await renderApp("/h5/home?site_key=mall-cn", vi.fn());

    expect(document.querySelector(".h5-member-toast-stack")).toBeNull();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000);
    });
    await flushEffects();

    expect(document.querySelector(".h5-member-toast-stack")).toBeNull();
  });

  it("suppresses floating important notifications on form-heavy secondary pages", async () => {
    vi.spyOn(h5MemberModule, "getCurrentMemberSession").mockResolvedValue({
      accountId: "38271456",
      phone: "13800000000",
      publicUserId: "h5-38271456",
      displayName: "Demo Member",
      inviteCode: "INV-ABCD1234",
    });
    vi.spyOn(h5MemberModule, "getMaskedPhone").mockResolvedValue("138****0000");
    vi.spyOn(h5MemberModule, "getMemberHomeDashboard").mockResolvedValue({
      ...createDashboardState(),
      recentMessages: [
        createMessageState({
          id: "msg-important",
          category: "wallet",
          title: "Rookie task package delivered",
          body: "Check your package status in the task center.",
          isRead: false,
        }),
      ],
    });
    vi.spyOn(h5MemberModule, "getWhatsAppBinding").mockResolvedValue({
      isBound: false,
      phoneNumber: null,
      lastUpdatedAt: null,
    });

    await renderApp("/h5/whatsapp?site_key=mall-cn", vi.fn());

    expect(document.querySelector(".h5-member-toast-stack")).toBeNull();
    expect(document.body.textContent).toContain("WhatsApp");
  });

  it("dismisses action notice toasts after the floating progress finishes", async () => {
    vi.useFakeTimers();
    Object.defineProperty(window.navigator, "clipboard", {
      configurable: true,
      value: { writeText: vi.fn().mockResolvedValue(undefined) },
    });
    vi.spyOn(h5MemberModule, "getCurrentMemberSession").mockResolvedValue({
      accountId: "38271456",
      phone: "13800000000",
      publicUserId: "h5-38271456",
      displayName: "Demo Member",
      inviteCode: "INV-ABCD1234",
    });
    vi.spyOn(h5MemberModule, "getMaskedPhone").mockResolvedValue("138****0000");
    vi.spyOn(h5MemberModule, "getMemberHomeDashboard").mockResolvedValue(createDashboardState());
    vi.spyOn(h5MemberModule, "getPromotionsApi").mockResolvedValue({ items: [] });

    await renderApp("/h5/promotion?site_key=mall-cn", vi.fn());

    const copyButton = document.querySelector(".h5-member-promotion-link-box + .h5-member-card-actions .seed-button") as HTMLButtonElement | null;
    expect(copyButton).not.toBeNull();

    await act(async () => {
      copyButton?.click();
    });
    await flushEffects();

    expect(document.querySelector(".h5-member-toast-stack")).not.toBeNull();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000);
    });
    await flushEffects();

    expect(document.querySelector(".h5-member-toast-stack")).toBeNull();
  });

  it("keeps the home first screen focused on task, wallet, and four core shortcuts", async () => {
    vi.spyOn(h5MemberModule, "getCurrentMemberSession").mockResolvedValue({
      accountId: "38271456",
      phone: "13800000000",
      publicUserId: "h5-38271456",
      displayName: "Demo Member",
      inviteCode: "INV-ABCD1234",
    });
    vi.spyOn(h5MemberModule, "getMaskedPhone").mockResolvedValue("138****0000");
    vi.spyOn(h5MemberModule, "getMemberHomeDashboard").mockResolvedValue(createDashboardState());
    vi.spyOn(h5MemberModule, "listTaskPackages").mockResolvedValue([createTaskPackageState()]);

    await renderApp("/h5/home?site_key=mall-cn", vi.fn());

    expect(document.querySelector(".h5-member-home-command")).not.toBeNull();
    const quickGrid = document.querySelector(".h5-member-home-section-grid") as HTMLElement | null;
    expect(document.querySelector(".h5-member-home-metric-grid")).not.toBeNull();
    expect(quickGrid).not.toBeNull();
    expect(quickGrid?.querySelectorAll(".h5-member-quick-action").length).toBeGreaterThan(0);
    expect(document.querySelector(".h5-card-stack")).not.toBeNull();
    expect(document.body.textContent).toContain("任务中心");
    expect(document.body.textContent).toContain("今日收益");
    expect(document.body.textContent).toContain("联系客服");
    expect(document.body.textContent).toContain("推广");
    expect(document.body.textContent).toContain("充值 / 提现");
    expect(document.body.textContent).toContain("成长动能");
    expect(document.body.textContent).toContain("通知");
    expect(document.body.textContent).toContain("查看");
    expect(document.body.textContent).toContain("进入");
    expect(document.body.textContent).toContain("暂无排行榜数据");
    expect(document.body.textContent).toContain("进行中");
    expect(document.body.textContent).toContain("推荐下一步");
    expect(document.body.textContent).toContain("待领取 1");
    expect(document.body.textContent).toContain("即将到期 0");
    expect(document.body.textContent).toContain("新手任务");
    expect(document.body.textContent).toContain("进度 0/1");
    expect(document.body.textContent).toContain("前 0 名");
    expect(document.body.textContent).not.toContain("Recharge / Withdraw");
    expect(document.body.textContent).not.toContain("Growth Momentum");
    expect(document.body.textContent).not.toContain("No leaderboard data");
    expect(document.body.textContent).not.toContain("View All");
    expect(document.body.textContent).not.toContain("Enter");
    expect(document.body.textContent).not.toContain("In Progress");
    expect(document.body.textContent).not.toContain("Quick next steps");
    expect(document.body.textContent).not.toContain("Top 0");
    expect(document.body.textContent).not.toContain("Rookie Task");
    expect(document.body.textContent).not.toContain("Progress 0/1");
  });

  it("surfaces member verification summary on home and profile", async () => {
    vi.spyOn(h5MemberModule, "getCurrentMemberSession").mockResolvedValue({
      accountId: "38271456",
      phone: "13800000000",
      publicUserId: "h5-38271456",
      displayName: "Demo Member",
      inviteCode: "INV-ABCD1234",
    });
    vi.spyOn(h5MemberModule, "getMaskedPhone").mockResolvedValue("138****0000");
    vi.spyOn(h5MemberModule, "getWhatsAppBinding").mockResolvedValue({
      isBound: false,
      phoneNumber: null,
      lastUpdatedAt: null,
    });
    vi.spyOn(h5MemberModule, "getMemberHomeDashboard").mockResolvedValue({
      ...createDashboardState(),
      verification: {
        currentStatus: "pending",
        hasActiveRequest: true,
      },
    });
    vi.spyOn(h5MemberModule, "listTaskPackages").mockResolvedValue([createTaskPackageState()]);

    await renderApp("/h5/home?site_key=mall-cn", vi.fn());
    expect(document.body.textContent).toContain("会员认证");

    await renderApp("/h5/me?site_key=mall-cn", vi.fn());
    expect(document.querySelector(".h5-member-profile-quick-actions")).not.toBeNull();
  });

  it("treats the legacy /h5/profile route as the member profile center", async () => {
    vi.spyOn(h5MemberModule, "getCurrentMemberSession").mockResolvedValue({
      accountId: "38271456",
      phone: "13800000000",
      publicUserId: "h5-38271456",
      displayName: "Demo Member",
      inviteCode: "INV-ABCD1234",
    });
    vi.spyOn(h5MemberModule, "getMaskedPhone").mockResolvedValue("138****0000");
    vi.spyOn(h5MemberModule, "getWhatsAppBinding").mockResolvedValue({
      isBound: false,
      phoneNumber: null,
      lastUpdatedAt: null,
    });
    vi.spyOn(h5MemberModule, "getMemberHomeDashboard").mockResolvedValue(createDashboardState());

    await renderApp("/h5/profile?site_key=mall-cn", vi.fn());

    expect(document.body.textContent).toContain("账户中心");
    expect(document.querySelector(".h5-member-profile-quick-actions")).not.toBeNull();
  });

  it("renders app-style empty states with next actions for orders and tickets", async () => {
    vi.spyOn(h5MemberModule, "getCurrentMemberSession").mockResolvedValue({
      accountId: "38271456",
      phone: "13800000000",
      publicUserId: "h5-38271456",
      displayName: "Demo Member",
      inviteCode: "INV-ABCD1234",
    });
    vi.spyOn(h5MemberModule, "getMaskedPhone").mockResolvedValue("138****0000");
    vi.spyOn(h5MemberModule, "getMemberHomeDashboard").mockResolvedValue(createDashboardState());
    vi.spyOn(h5MemberModule, "getOrdersApi").mockResolvedValue({ items: [], total: 0 });
    vi.spyOn(h5MemberModule, "getTicketsApi").mockResolvedValue({ items: [], total: 0 });

    await renderApp("/h5/orders?site_key=mall-cn", vi.fn());
    expect(document.querySelector(".h5-empty-state")).not.toBeNull();
    expect(document.body.textContent).toContain("暂无订单");
    expect(document.body.textContent).toContain("返回任务");

    await renderApp("/h5/tickets?site_key=mall-cn", vi.fn());
    expect(document.querySelector(".h5-empty-state")).not.toBeNull();
    expect(document.body.textContent).toContain("暂无工单");
    expect(document.body.textContent).toContain("联系客服");
  });

  it("renders fragment collection progress from the home summary instead of reusing unread counts", async () => {
    vi.spyOn(h5MemberModule, "getCurrentMemberSession").mockResolvedValue({
      accountId: "38271456",
      phone: "13800000000",
      publicUserId: "h5-38271456",
      displayName: "Demo Member",
      inviteCode: "INV-ABCD1234",
    });
    vi.spyOn(h5MemberModule, "getMaskedPhone").mockResolvedValue("138****0000");
    vi.spyOn(h5MemberModule, "getMemberHomeDashboard").mockResolvedValue({
      ...createDashboardState(),
      unreadCount: 9,
      fragments: {
        rewardName: "Star Gift Box",
        completedCount: 2,
        totalCount: 3,
        missingCount: 1,
        canExchange: false,
        shippingOrderCount: 1,
        latestShippingStatus: "submitted",
      },
    });
    vi.spyOn(h5MemberModule, "listTaskPackages").mockResolvedValue([createTaskPackageState()]);

    await renderApp("/h5/home?site_key=mall-cn", vi.fn());

    expect(document.body.textContent).toContain("2/3");
    expect(document.body.textContent).not.toContain("9 閺夆€冲З閹?");
  });

  it("surfaces member verification summary on home and profile", async () => {
    vi.spyOn(h5MemberModule, "getCurrentMemberSession").mockResolvedValue({
      accountId: "38271456",
      phone: "13800000000",
      publicUserId: "h5-38271456",
      displayName: "Demo Member",
      inviteCode: "INV-ABCD1234",
    });
    vi.spyOn(h5MemberModule, "getMaskedPhone").mockResolvedValue("138****0000");
    vi.spyOn(h5MemberModule, "getWhatsAppBinding").mockResolvedValue({
      isBound: false,
      phoneNumber: null,
      lastUpdatedAt: null,
    });
    vi.spyOn(h5MemberModule, "getMemberHomeDashboard").mockResolvedValue({
      ...createDashboardState(),
      verification: {
        currentStatus: "pending",
        hasActiveRequest: true,
      },
    });
    vi.spyOn(h5MemberModule, "listTaskPackages").mockResolvedValue([createTaskPackageState()]);

    await renderApp("/h5/home?site_key=mall-cn", vi.fn());
    expect(document.body.textContent).toContain("会员认证");
    await renderApp("/h5/me?site_key=mall-cn", vi.fn());
    expect(document.querySelector(".h5-member-profile-quick-actions")).not.toBeNull();
  });

  it("renders app-style empty states with next actions for orders and tickets", async () => {
    vi.spyOn(h5MemberModule, "getCurrentMemberSession").mockResolvedValue({
      accountId: "38271456",
      phone: "13800000000",
      publicUserId: "h5-38271456",
      displayName: "Demo Member",
      inviteCode: "INV-ABCD1234",
    });
    vi.spyOn(h5MemberModule, "getMaskedPhone").mockResolvedValue("138****0000");
    vi.spyOn(h5MemberModule, "getMemberHomeDashboard").mockResolvedValue(createDashboardState());
    vi.spyOn(h5MemberModule, "getOrdersApi").mockResolvedValue({ items: [], total: 0 });
    vi.spyOn(h5MemberModule, "getTicketsApi").mockResolvedValue({ items: [], total: 0 });

    await renderApp("/h5/orders?site_key=mall-cn", vi.fn());

    expect(document.querySelector(".h5-empty-state")).not.toBeNull();
    expect(document.body.textContent).toContain("暂无订单");
    expect(document.body.textContent).toContain("返回任务");

    await renderApp("/h5/tickets?site_key=mall-cn", vi.fn());
    const emptyStates = document.querySelectorAll(".h5-empty-state");
    expect(emptyStates.length).toBeGreaterThan(0);
    expect(document.body.textContent).toContain("暂无工单");
    expect(document.body.textContent).toContain("联系客服");
  });

  it("filters the order list by status without exposing search or detail navigation via stable selectors", async () => {
    vi.spyOn(h5MemberModule, "getCurrentMemberSession").mockResolvedValue({
      accountId: "38271456",
      phone: "13800000000",
      publicUserId: "h5-38271456",
      displayName: "Demo Member",
      inviteCode: "INV-ABCD1234",
    });
    vi.spyOn(h5MemberModule, "getMaskedPhone").mockResolvedValue("138****0000");
    vi.spyOn(h5MemberModule, "getMemberHomeDashboard").mockResolvedValue(createDashboardState());
    vi.spyOn(h5MemberModule, "getOrdersApi").mockResolvedValue({
      items: [
        {
          id: "order-paid",
          orderNo: "ORD-PAID",
          packageId: "pkg-1",
          packageTitle: "Starter Package",
          productName: "Paid Product",
          amount: 20,
          currency: "USD",
          status: "paid",
          createdAt: "2026-06-11T00:10:00Z",
          sourceLabel: "Starter Package",
        },
        {
          id: "order-failed",
          orderNo: "ORD-FAILED",
          packageId: "pkg-2",
          packageTitle: "Growth Package",
          productName: "Failed Product",
          amount: 30,
          currency: "USD",
          status: "failed",
          createdAt: "2026-06-11T00:20:00Z",
          sourceLabel: "Growth Package",
        },
        {
          id: "order-processing",
          orderNo: "ORD-PROCESSING",
          packageId: "pkg-3",
          packageTitle: "Scale Package",
          productName: "Processing Product",
          amount: 40,
          currency: "USD",
          status: "processing",
          createdAt: "2026-06-11T00:30:00Z",
          sourceLabel: "Scale Package",
        },
      ],
      total: 3,
    });

    await renderApp("/h5/orders?site_key=mall-cn", vi.fn());

    expect(document.body.textContent).toContain("Paid Product");
    expect(document.body.textContent).toContain("Failed Product");
    expect(document.body.textContent).toContain("Processing Product");
    expect(document.querySelectorAll(".h5-member-list-row").length).toBeGreaterThan(0);

    const processingFilterButton = document.querySelector(
      ".h5-member-orders-filters .h5-member-segmented-chip:nth-of-type(4)",
    ) as HTMLButtonElement | null;
    expect(processingFilterButton).not.toBeNull();

    await act(async () => {
      processingFilterButton?.click();
    });
    await flushEffects();

    expect(document.body.textContent).not.toContain("Paid Product");
    expect(document.body.textContent).not.toContain("Failed Product");
    expect(document.body.textContent).toContain("Processing Product");
    expect(document.querySelector(".h5-member-orders-search")).toBeNull();
    expect(findButtonByText("Order detail")).toBeNull();
  });
});

describe("H5App auth routing", () => {
  beforeEach(() => {
    installLocalStorageMock();
    window.localStorage.clear();
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
    vi.unstubAllEnvs();
  });

  afterEach(async () => {
    while (mountedRoots.length > 0) {
      const root = mountedRoots.pop();
      await act(async () => {
        root?.unmount();
      });
    }
    while (mountedContainers.length > 0) {
      mountedContainers.pop()?.remove();
    }
    vi.restoreAllMocks();
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
    delete (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT;
    window.localStorage.clear();
  });

  it("redirects unauthenticated access on formal pages to login", async () => {
    vi.stubEnv("VITE_H5_MEMBER_LEGACY_FALLBACK", "false");
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(createErrorResponse(401, "Session expired"))
      .mockResolvedValueOnce(createErrorResponse(401, "Refresh expired"));
    const navigate = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    await renderApp("/h5/home?site_key=mall-cn", navigate);

    expect(navigate).toHaveBeenCalledWith("/h5/login?site_key=mall-cn");
  });

  it("redirects logged-in users away from login page to home", async () => {
    const fetchMock = vi.fn().mockResolvedValue(createJsonResponse(createAuthPayload()));
    const navigate = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    await renderApp("/h5/login?site_key=mall-cn", navigate);

    expect(navigate).toHaveBeenCalledWith("/h5/home?site_key=mall-cn");
  });

  it("redirects to login when the route bootstrap loses auth during dashboard loading", async () => {
    vi.stubEnv("VITE_H5_MEMBER_LEGACY_FALLBACK", "false");
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(createJsonResponse(createAuthPayload()))
      .mockResolvedValueOnce(createErrorResponse(401, "Session expired"))
      .mockResolvedValueOnce(createErrorResponse(401, "Refresh expired"));
    const navigate = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    await renderApp("/h5/home?site_key=mall-cn", navigate);

    expect(navigate).toHaveBeenCalledWith("/h5/login?site_key=mall-cn");
  });

  it("renders mobile auth support shortcuts and keeps password visibility toggles usable", async () => {
    await renderApp("/h5/login?site_key=mall-cn", vi.fn());

    expect(document.querySelector(".h5-member-auth-form-card")).not.toBeNull();
    expect(document.querySelector('input[type="checkbox"]')).not.toBeNull();
    expect(document.body.textContent).toContain("忘记密码");

    const passwordInput = document.querySelector(".h5-member-password-field input") as HTMLInputElement | null;
    const toggleButton = document.querySelector(".h5-member-password-toggle") as HTMLButtonElement | null;
    expect(passwordInput?.type).toBe("password");
    expect(toggleButton).not.toBeNull();

    await act(async () => {
      toggleButton?.click();
    });

    expect(passwordInput?.type).toBe("text");
  });

  it("redirects to login when ticket creation hits an auth-required action error", async () => {
    vi.spyOn(h5MemberModule, "getCurrentMemberSession").mockResolvedValue({
      accountId: "38271456",
      phone: "13800000000",
      publicUserId: "h5-38271456",
      displayName: "Demo Member",
      inviteCode: "INV-ABCD1234",
    });
    vi.spyOn(h5MemberModule, "getMemberHomeDashboard").mockResolvedValue(createDashboardState());
    vi.spyOn(h5MemberModule, "getMaskedPhone").mockResolvedValue("138****0000");
    vi.spyOn(h5MemberModule, "createTicketApi").mockRejectedValue(new H5AuthRequiredError());

    const navigate = vi.fn();
    await renderApp("/h5/tickets/new?site_key=mall-cn", navigate);

    const form = document.querySelector("form.h5-card.h5-form") as HTMLFormElement | null;
    expect(form).not.toBeNull();

    await act(async () => {
      form?.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    });
    await flushEffects();

    expect(navigate).toHaveBeenCalledWith("/h5/login?site_key=mall-cn");
  });

  it("redirects to login when ticket reply hits an auth-required action error", async () => {
    vi.spyOn(h5MemberModule, "getCurrentMemberSession").mockResolvedValue({
      accountId: "38271456",
      phone: "13800000000",
      publicUserId: "h5-38271456",
      displayName: "Demo Member",
      inviteCode: "INV-ABCD1234",
    });
    vi.spyOn(h5MemberModule, "getMemberHomeDashboard").mockResolvedValue(createDashboardState());
    vi.spyOn(h5MemberModule, "getMaskedPhone").mockResolvedValue("138****0000");
    vi.spyOn(h5MemberModule, "getTicketDetailApi").mockResolvedValue(createTicketDetailState());
    vi.spyOn(h5MemberModule, "replyToTicketApi").mockRejectedValue(new H5AuthRequiredError());

    const navigate = vi.fn();
    await renderApp("/h5/tickets/ticket-2001?site_key=mall-cn", navigate);

    const form = document.querySelector("form.h5-card.h5-form.h5-member-ticket-reply-card") as HTMLFormElement | null;
    const textarea = form?.querySelector("textarea") as HTMLTextAreaElement | null;
    expect(form).not.toBeNull();
    expect(textarea).not.toBeNull();

    await act(async () => {
      if (textarea) {
        setTextareaValue(textarea, "More details");
      }
    });

    await act(async () => {
      form?.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    });
    await flushEffects();

    expect(navigate).toHaveBeenCalledWith("/h5/login?site_key=mall-cn");
  });

  it("redirects to login when task package purchase hits an auth-required action error", async () => {
    vi.useFakeTimers();
    vi.spyOn(h5MemberModule, "getCurrentMemberSession").mockResolvedValue({
      accountId: "38271456",
      phone: "13800000000",
      publicUserId: "h5-38271456",
      displayName: "Demo Member",
      inviteCode: "INV-ABCD1234",
    });
    vi.spyOn(h5MemberModule, "getMemberHomeDashboard").mockResolvedValue(createDashboardState());
    vi.spyOn(h5MemberModule, "getMaskedPhone").mockResolvedValue("138****0000");
    vi.spyOn(h5MemberModule, "getTaskInstanceDetailApi").mockResolvedValue(createTaskInstanceState());
    vi.spyOn(h5MemberModule, "startProductApi").mockRejectedValue(new H5AuthRequiredError());

    const navigate = vi.fn();
    await renderApp("/h5/tasks/package/pkg-1?site_key=mall-cn", navigate);

    const button = (document.querySelector(".h5-package-product-btn") as HTMLButtonElement | null) ?? Array.from(document.querySelectorAll("button")).find(
      (element) => element.textContent?.includes("璐拱"),
    ) as HTMLButtonElement | null;
    expect(button).not.toBeNull();

    await act(async () => {
      button?.click();
      await vi.advanceTimersByTimeAsync(3000);
    });
    await flushEffects();

    expect(navigate).toHaveBeenCalledWith("/h5/login?site_key=mall-cn");
  });

  it("renders active tasks first and only shows non-empty status partitions", async () => {
    vi.spyOn(h5MemberModule, "getCurrentMemberSession").mockResolvedValue({
      accountId: "38271456",
      phone: "13800000000",
      publicUserId: "h5-38271456",
      displayName: "Demo Member",
      inviteCode: "INV-ABCD1234",
    });
    vi.spyOn(h5MemberModule, "getMemberHomeDashboard").mockResolvedValue(createDashboardState());
    vi.spyOn(h5MemberModule, "getMaskedPhone").mockResolvedValue("138****0000");
    vi.spyOn(h5MemberModule, "getSignInStatusApi").mockResolvedValue({
      consecutiveDays: 3,
      todaySignedIn: false,
      goalDays: 7,
      goalReward: 5,
      isCompleted: false,
    });
    vi.spyOn(h5MemberModule, "getTaskInstancesApi").mockResolvedValue([
      createTaskInstanceState({
        id: "pkg-1",
        title: "Active Package A",
        status: "active",
      }),
      createTaskInstanceState({
        id: "pkg-2",
        title: "Completed Package B",
        status: "completed",
        completedCount: 1,
      }),
    ]);

    await renderApp("/h5/tasks?site_key=mall-cn", vi.fn());

    const partitionTitles = Array.from(document.querySelectorAll(".h5-task-partition-title")).map((node) => node.textContent ?? "");
    expect(document.body.textContent).toContain("Active Package A");
    expect(document.body.textContent).toContain("Completed Package B");
    expect(document.querySelector(".h5-task-instance-status-badge.active")).not.toBeNull();
    expect(document.querySelector(".h5-task-instance-status-badge.completed")).not.toBeNull();
    expect(partitionTitles).toHaveLength(2);
  });

  it("renders compact task cards with progress, status, and detail action", async () => {
    vi.spyOn(h5MemberModule, "getCurrentMemberSession").mockResolvedValue({
      accountId: "38271456",
      phone: "13800000000",
      publicUserId: "h5-38271456",
      displayName: "Demo Member",
      inviteCode: "INV-ABCD1234",
    });
    vi.spyOn(h5MemberModule, "getMemberHomeDashboard").mockResolvedValue(createDashboardState());
    vi.spyOn(h5MemberModule, "getMaskedPhone").mockResolvedValue("138****0000");
    vi.spyOn(h5MemberModule, "getSignInStatusApi").mockResolvedValue({
      consecutiveDays: 3,
      todaySignedIn: false,
      goalDays: 7,
      goalReward: 5,
      isCompleted: false,
    });
    vi.spyOn(h5MemberModule, "getTaskInstancesApi").mockResolvedValue([
      createTaskInstanceState({
        id: "pkg-2",
        title: "Growth Package B",
        status: "active",
        totalCount: 5,
        completedCount: 0,
      }),
    ]);

    await renderApp("/h5/tasks?site_key=mall-cn", vi.fn());

    expect(document.querySelector(".h5-task-instance-card")).not.toBeNull();
    expect(document.querySelector(".h5-task-instance-meta")).not.toBeNull();
    expect(document.querySelector(".h5-task-instance-status-badge.active")).not.toBeNull();
    expect(document.querySelector(".h5-member-progress")).not.toBeNull();
    expect(document.body.textContent).toContain("Growth Package B");
    expect(document.querySelectorAll(".h5-task-instance-card")).toHaveLength(1);
  });

  it("groups messages by priority and surfaces withdraw status in profile", async () => {
    vi.spyOn(h5MemberModule, "getCurrentMemberSession").mockResolvedValue({
      accountId: "38271456",
      phone: "13800000000",
      publicUserId: "h5-38271456",
      displayName: "Demo Member",
      inviteCode: "INV-ABCD1234",
    });
    vi.spyOn(h5MemberModule, "getMaskedPhone").mockResolvedValue("138****0000");
    vi.spyOn(h5MemberModule, "getMemberHomeDashboard").mockResolvedValue({
      ...createDashboardState(),
      wallet: {
        systemBalance: 40,
        taskBalance: 80,
        currency: "USD",
        withdrawThreshold: 100,
        canWithdraw: false,
        shortfallAmount: 60,
      },
    });
    vi.spyOn(h5MemberModule, "getNotificationsApi").mockResolvedValue({
      items: [
        createMessageState({ id: "msg-support", category: "support", title: "工单回复" }),
        createMessageState({ id: "msg-fragment", category: "fragment", title: "碎片掉落提醒" }),
      ],
      total: 2,
    });

    await renderApp("/h5/messages?site_key=mall-cn", vi.fn());
    expect(document.querySelector(".h5-member-msg-list")).not.toBeNull();
    expect(document.querySelectorAll(".h5-member-message-feed-item").length).toBeGreaterThan(0);
    expect(document.body.textContent).toContain("重要通知");
    expect(document.body.textContent).toContain("其他消息");
    expect(document.body.textContent).toContain("请补充订单号");
    expect(document.body.textContent).not.toContain("璇疯ˉ鍏呰鍗曞彿");

    await renderApp("/h5/me?site_key=mall-cn", vi.fn());
    expect(document.body.textContent).toContain("系统余额");
    expect(document.body.textContent).toContain("任务余额");
  });

  it("surfaces whatsapp status and quick actions above the profile service menu", async () => {
    vi.spyOn(h5MemberModule, "getCurrentMemberSession").mockResolvedValue({
      accountId: "38271456",
      phone: "13800000000",
      publicUserId: "h5-38271456",
      displayName: "Demo Member",
      inviteCode: "INV-ABCD1234",
    });
    vi.spyOn(h5MemberModule, "getMaskedPhone").mockResolvedValue("138****0000");
    vi.spyOn(h5MemberModule, "getMemberHomeDashboard").mockResolvedValue(createDashboardState());
    vi.spyOn(h5MemberModule, "getWhatsAppBinding").mockResolvedValue({
      isBound: false,
      phoneNumber: null,
      lastUpdatedAt: null,
    });

    await renderApp("/h5/me?site_key=mall-cn", vi.fn());

    const quickActions = document.querySelector(".h5-member-profile-quick-actions") as HTMLElement | null;
    const balanceStrip = document.querySelector(".h5-member-profile-balance-strip") as HTMLElement | null;
    expect(quickActions).not.toBeNull();
    expect(balanceStrip).not.toBeNull();
    expect(document.querySelector(".h5-member-whatsapp-status-icon-unbound")).not.toBeNull();
    expect(document.body.textContent).toContain("订单");
    expect(document.body.textContent).toContain("联系客服");
    expect((balanceStrip as HTMLElement).textContent).not.toContain("订单");
    expect((balanceStrip as HTMLElement).textContent).not.toContain("联系客服");
    expect((quickActions as HTMLElement).compareDocumentPosition(balanceStrip as HTMLElement) & Node.DOCUMENT_POSITION_PRECEDING).toBeTruthy();
  });

  it("renders wallet as dual-balance cards with a threshold status bar and prioritized transfer action", async () => {
    vi.spyOn(h5MemberModule, "getCurrentMemberSession").mockResolvedValue({
      accountId: "38271456",
      phone: "13800000000",
      publicUserId: "h5-38271456",
      displayName: "Demo Member",
      inviteCode: "INV-ABCD1234",
    });
    vi.spyOn(h5MemberModule, "getMaskedPhone").mockResolvedValue("138****0000");
    vi.spyOn(h5MemberModule, "getMemberHomeDashboard").mockResolvedValue({
      ...createDashboardState(),
      wallet: {
        systemBalance: 40,
        taskBalance: 80,
        currency: "USD",
        withdrawThreshold: 100,
        canWithdraw: false,
        shortfallAmount: 60,
      },
    });
    vi.spyOn(h5MemberModule, "listWalletTransactions").mockResolvedValue([]);
    vi.spyOn(h5MemberModule, "listWithdrawRequests").mockResolvedValue([]);

    await renderApp("/h5/withdraw?site_key=mall-cn", vi.fn());

    expect(document.querySelector(".h5-member-wallet-balance-hero")).not.toBeNull();
    expect(document.querySelector(".h5-member-wallet-threshold-bar")).not.toBeNull();
    expect(document.querySelector(".h5-member-wallet-action-card-priority")).not.toBeNull();
    expect(document.querySelector(".h5-member-balance-pill-button")).not.toBeNull();
  });

  it("renders task package detail with reward, balance, and product action rows", async () => {
    vi.spyOn(h5MemberModule, "getCurrentMemberSession").mockResolvedValue({
      accountId: "38271456",
      phone: "13800000000",
      publicUserId: "h5-38271456",
      displayName: "Demo Member",
      inviteCode: "INV-ABCD1234",
    });
    vi.spyOn(h5MemberModule, "getMemberHomeDashboard").mockResolvedValue(createDashboardState());
    vi.spyOn(h5MemberModule, "getMaskedPhone").mockResolvedValue("138****0000");
    vi.spyOn(h5MemberModule, "getTaskInstanceDetailApi").mockResolvedValue(createTaskInstanceState());

    await renderApp("/h5/tasks/package/pkg-1?site_key=mall-cn", vi.fn());

    expect(document.querySelector(".h5-package-reward-row")).not.toBeNull();
    expect(document.querySelector(".h5-package-balance-row")).not.toBeNull();
    expect(document.querySelector(".h5-package-product-item")).not.toBeNull();
    expect(document.querySelector(".h5-package-product-info")).not.toBeNull();
    expect(document.querySelector(".h5-package-product-price")).not.toBeNull();
    expect(document.querySelector(".h5-package-product-btn")).not.toBeNull();
    expect(document.body.textContent).toContain("Starter Package");
    expect(document.body.textContent).toContain("Demo Product");
  });

  it("lets the task package detail route recover from a first-load failure via a localized retry action", async () => {
    window.localStorage.setItem("h5-lang", "zh-CN");

    vi.spyOn(h5MemberModule, "getCurrentMemberSession").mockResolvedValue({
      accountId: "38271456",
      phone: "13800000000",
      publicUserId: "h5-38271456",
      displayName: "Demo Member",
      inviteCode: "INV-ABCD1234",
    });
    vi.spyOn(h5MemberModule, "getMemberHomeDashboard").mockResolvedValue(createDashboardState());
    vi.spyOn(h5MemberModule, "getMaskedPhone").mockResolvedValue("138****0000");
    const detailSpy = vi
      .spyOn(h5MemberModule, "getTaskInstanceDetailApi")
      .mockRejectedValueOnce(new Error("任务包加载失败"))
      .mockResolvedValueOnce(createTaskInstanceState());

    await renderApp("/h5/tasks/package/pkg-1?site_key=mall-cn", vi.fn());

    expect(document.body.textContent).toContain("任务包加载失败");
    const retryButton = findButtonByText("重试");
    expect(retryButton).not.toBeNull();

    await act(async () => {
      retryButton?.click();
    });
    await flushEffects();

    expect(detailSpy).toHaveBeenCalledTimes(2);
    expect(document.body.textContent).toContain("Starter Package");
    expect(document.body.textContent).toContain("Demo Product");
  });

  it("renders ticket detail as a chat-like thread with a dedicated reply composer", async () => {
    vi.spyOn(h5MemberModule, "getCurrentMemberSession").mockResolvedValue({
      accountId: "38271456",
      phone: "13800000000",
      publicUserId: "h5-38271456",
      displayName: "Demo Member",
      inviteCode: "INV-ABCD1234",
    });
    vi.spyOn(h5MemberModule, "getMemberHomeDashboard").mockResolvedValue(createDashboardState());
    vi.spyOn(h5MemberModule, "getMaskedPhone").mockResolvedValue("138****0000");
    vi.spyOn(h5MemberModule, "getTicketDetailApi").mockResolvedValue({
      ...createTicketDetailState(),
      messages: [
        ...createTicketDetailState().messages,
        {
          id: "ticket-msg-2",
          sender_type: "agent",
          sender_name: "?? A",
          content: "We are checking it",
          created_at: "2026-06-11T00:03:00Z",
          internal_only: false,
        },
      ],
    });

    await renderApp("/h5/tickets/ticket-2001?site_key=mall-cn", vi.fn());
    expect(document.querySelector(".h5-member-ticket-summary-card")).not.toBeNull();
    expect(document.querySelector(".h5-member-ticket-thread")).not.toBeNull();
    expect(document.querySelector(".h5-member-ticket-message-user")).not.toBeNull();
    expect(document.querySelector(".h5-member-ticket-message-agent")).not.toBeNull();
    expect(document.querySelector(".h5-member-ticket-reply-card")).not.toBeNull();
  });

  it("renders fragments as a progress-first collection page with inventory and shipping sections", async () => {
    vi.spyOn(h5MemberModule, "getCurrentMemberSession").mockResolvedValue({
      accountId: "38271456",
      phone: "13800000000",
      publicUserId: "h5-38271456",
      displayName: "Demo Member",
      inviteCode: "INV-ABCD1234",
    });
    vi.spyOn(h5MemberModule, "getMemberHomeDashboard").mockResolvedValue(createDashboardState());
    vi.spyOn(h5MemberModule, "getMaskedPhone").mockResolvedValue("138****0000");
    vi.spyOn(h5MemberModule, "getFragmentsOverview").mockResolvedValue({
      inventory: [
        {
          id: "inventory-1",
          name: "Star Ray Fragment",
          rarity: "epic",
          color: "#ef4444",
          owned: 1,
          required: 1,
        },
      ],
      dropLogs: [
        {
          id: "drop-1",
          fragmentId: "fragment-star",
          fragmentName: "Star Ray Fragment",
          source: "task",
          createdAt: "2026-06-11T02:00:00Z",
        },
      ],
      rewardName: "Star Gift Box",
      shippingOrders: [
        {
          id: "shipping-1",
          rewardName: "Star Gift Box",
          status: "submitted",
          createdAt: "2026-06-11T03:00:00Z",
          address: {
            receiver: "Demo User",
            phone: "13800000000",
            country: "China",
            province: "Guangdong",
            city: "Shenzhen",
            addressLine: "Nanshan Science Park",
          },
        },
      ],
    });

    await renderApp("/h5/fragments?site_key=mall-cn", vi.fn());

    expect(document.querySelector(".h5-member-fragment-hero")).not.toBeNull();
    expect(document.querySelector(".h5-member-fragment-inventory-card")).not.toBeNull();
    expect(document.querySelector(".h5-member-fragment-shipping-list")).not.toBeNull();
    expect(document.body.textContent).toContain("Star Gift Box");
  });

  it("renders leaderboard and whatsapp pages as compact status-driven utility pages", async () => {
    vi.spyOn(h5MemberModule, "getCurrentMemberSession").mockResolvedValue({
      accountId: "38271456",
      phone: "13800000000",
      publicUserId: "h5-38271456",
      displayName: "Demo Member",
      inviteCode: "INV-ABCD1234",
    });
    vi.spyOn(h5MemberModule, "getMemberHomeDashboard").mockResolvedValue(createDashboardState());
    vi.spyOn(h5MemberModule, "getMaskedPhone").mockResolvedValue("138****0000");
    vi.spyOn(h5MemberModule, "getLeaderboardApi").mockResolvedValue({
      rankings: [{ rank: 1, userId: "38271456", score: 120 }],
    });
    vi.spyOn(h5MemberModule, "getWhatsAppBinding").mockResolvedValue({
      isBound: true,
      phoneNumber: "+1 202 555 0101",
      lastUpdatedAt: "2026-06-11T05:00:00Z",
    });

    vi.spyOn(h5MemberModule, "getMessagesApi").mockResolvedValue({
      items: [],
      total: 0,
    });
    await renderApp("/h5/leaderboard?site_key=mall-cn", vi.fn());
    expect(document.querySelector(".h5-member-leaderboard-list")).not.toBeNull();
    expect(document.querySelector(".h5-member-list-row")).not.toBeNull();
    expect(document.body.textContent).toContain("382***56");

    await renderApp("/h5/whatsapp?site_key=mall-cn", vi.fn());
    expect(document.querySelector(".h5-chat-container")).not.toBeNull();
    expect(document.querySelector(".h5-chat-messages")).not.toBeNull();
  });

  it("keeps a local preview visible when image send responses omit image_url", async () => {
    Object.defineProperty(URL, "createObjectURL", {
      configurable: true,
      value: vi.fn(() => "blob:chat-preview-1"),
    });

    vi.spyOn(h5MemberModule, "getCurrentMemberSession").mockResolvedValue({
      accountId: "38271456",
      phone: "13800000000",
      publicUserId: "h5-38271456",
      displayName: "Demo Member",
      inviteCode: "INV-ABCD1234",
    });
    vi.spyOn(h5MemberModule, "getMemberHomeDashboard").mockResolvedValue(createDashboardState());
    vi.spyOn(h5MemberModule, "getMaskedPhone").mockResolvedValue("138****0000");
    vi.spyOn(h5MemberModule, "getWhatsAppBinding").mockResolvedValue({
      isBound: true,
      phoneNumber: "+1 202 555 0101",
      lastUpdatedAt: "2026-06-11T05:00:00Z",
    });
    vi.spyOn(h5MemberModule, "getMessagesApi").mockResolvedValue({
      items: [],
      total: 0,
    });
    vi.spyOn(h5MemberModule, "sendMessageApi").mockResolvedValue({
      id: "msg-image-1",
      content: "Image",
      type: "image",
      direction: "outbound",
      status: "sent",
      timestamp: "2026-06-24T00:00:00.000Z",
    });

    await renderApp("/h5/whatsapp?site_key=mall-cn", vi.fn());

    const fileInput = document.querySelector(".h5-chat-file-input") as HTMLInputElement | null;
    expect(fileInput).not.toBeNull();

    await act(async () => {
      fireEvent.change(fileInput!, {
        target: {
          files: [new File(["image"], "chat-photo.png", { type: "image/png" })],
        },
      });
    });
    await flushEffects();

    const previewImage = document.querySelector(".h5-chat-bubble-image img") as HTMLImageElement | null;
    expect(previewImage).not.toBeNull();
    expect(previewImage?.getAttribute("src")).toBe("blob:chat-preview-1");
  });

  it("localizes the invite page retry fallback inside the h5 app shell", async () => {
    window.localStorage.setItem("h5-lang", "zh-CN");

    vi.spyOn(h5MemberModule, "getCurrentMemberSession").mockResolvedValue({
      accountId: "38271456",
      phone: "13800000000",
      publicUserId: "h5-38271456",
      displayName: "Demo Member",
      inviteCode: "INV-ABCD1234",
    });
    vi.spyOn(h5MemberModule, "getMemberHomeDashboard").mockResolvedValue(createDashboardState());
    vi.spyOn(h5MemberModule, "getMaskedPhone").mockResolvedValue("138****0000");
    vi.spyOn(h5MemberModule, "getInviteInfoApi").mockRejectedValue(new Error("邀请信息加载失败"));
    vi.spyOn(h5MemberModule, "getInviteRecordsApi").mockResolvedValue([]);

    await renderApp("/h5/invite?site_key=mall-cn", vi.fn());

    expect(document.body.textContent).toContain("邀请信息加载失败");
    expect(document.body.textContent).toContain("重试");
    expect(document.body.textContent).not.toContain("Retry");
  });

  it("keeps the verification page available even when WhatsApp binding status cannot be loaded", async () => {
    vi.spyOn(h5MemberModule, "getCurrentMemberSession").mockResolvedValue({
      accountId: "38271456",
      phone: "13800000000",
      publicUserId: "h5-38271456",
      displayName: "Demo Member",
      inviteCode: "INV-ABCD1234",
    });
    vi.spyOn(h5MemberModule, "getMemberHomeDashboard").mockResolvedValue(createDashboardState());
    vi.spyOn(h5MemberModule, "getMaskedPhone").mockResolvedValue("138****0000");
    vi.spyOn(h5MemberModule, "getWhatsAppBinding").mockRejectedValue(new Error("WhatsApp binding unavailable"));
    vi.spyOn(h5MemberModule, "getMemberVerificationSummary").mockResolvedValue({
      currentStatus: "under_review",
      hasActiveRequest: true,
      activeRequest: {
        id: "vr-1",
        requestType: "identity",
        status: "under_review",
        notes: "Please verify my identity.",
        reviewNote: null,
        reviewerActorId: null,
        reviewedAt: null,
        createdAt: "2026-06-11T10:00:00Z",
        updatedAt: "2026-06-11T10:05:00Z",
        documents: [],
      },
      history: [
        {
          id: "vr-1",
          requestType: "identity",
          status: "under_review",
          notes: "Please verify my identity.",
          reviewNote: null,
          reviewerActorId: null,
          reviewedAt: null,
          createdAt: "2026-06-11T10:00:00Z",
          updatedAt: "2026-06-11T10:05:00Z",
          documents: [],
        },
      ],
    });
    vi.spyOn(h5MemberModule, "listMemberVerificationRequests").mockResolvedValue([
      {
        id: "vr-1",
        requestType: "identity",
        status: "under_review",
        notes: "Please verify my identity.",
        reviewNote: null,
        reviewerActorId: null,
        reviewedAt: null,
        createdAt: "2026-06-11T10:00:00Z",
        updatedAt: "2026-06-11T10:05:00Z",
        documents: [],
      },
    ]);
    vi.spyOn(h5MemberModule, "getMemberVerificationRequestDetail").mockResolvedValue({
      id: "vr-1",
      requestType: "identity",
      status: "under_review",
      notes: "Please verify my identity.",
      reviewNote: null,
      reviewerActorId: null,
      reviewedAt: null,
      createdAt: "2026-06-11T10:00:00Z",
      updatedAt: "2026-06-11T10:05:00Z",
      documents: [],
    });

    await renderApp("/h5/verification?site_key=mall-cn", vi.fn());

    expect(document.querySelector(".h5-member-detail-grid")).not.toBeNull();
    expect(document.querySelector(".h5-member-verification-status-flow")).not.toBeNull();
    expect(document.body.textContent).not.toContain("WhatsApp binding unavailable");
  });

  it("keeps the verification page summary visible when request detail loading fails", async () => {
    vi.spyOn(h5MemberModule, "getCurrentMemberSession").mockResolvedValue({
      accountId: "38271456",
      phone: "13800000000",
      publicUserId: "h5-38271456",
      displayName: "Demo Member",
      inviteCode: "INV-ABCD1234",
    });
    vi.spyOn(h5MemberModule, "getMemberHomeDashboard").mockResolvedValue(createDashboardState());
    vi.spyOn(h5MemberModule, "getMaskedPhone").mockResolvedValue("138****0000");
    vi.spyOn(h5MemberModule, "getMemberVerificationSummary").mockResolvedValue({
      currentStatus: "under_review",
      hasActiveRequest: true,
      activeRequest: {
        id: "vr-1",
        requestType: "identity",
        status: "under_review",
        notes: "Active request summary notes.",
        reviewNote: null,
        reviewerActorId: null,
        reviewedAt: null,
        createdAt: "2026-06-11T10:00:00Z",
        updatedAt: "2026-06-11T10:05:00Z",
        documents: [],
      },
      history: [
        {
          id: "vr-1",
          requestType: "identity",
          status: "under_review",
          notes: "Active request summary notes.",
          reviewNote: null,
          reviewerActorId: null,
          reviewedAt: null,
          createdAt: "2026-06-11T10:00:00Z",
          updatedAt: "2026-06-11T10:05:00Z",
          documents: [],
        },
      ],
    });
    vi.spyOn(h5MemberModule, "listMemberVerificationRequests").mockResolvedValue([
      {
        id: "vr-1",
        requestType: "identity",
        status: "under_review",
        notes: "Active request list notes.",
        reviewNote: null,
        reviewerActorId: null,
        reviewedAt: null,
        createdAt: "2026-06-11T10:00:00Z",
        updatedAt: "2026-06-11T10:05:00Z",
        documents: [],
      },
    ]);
    vi.spyOn(h5MemberModule, "getMemberVerificationRequestDetail").mockRejectedValue(new Error("Verification detail unavailable"));

    await renderApp("/h5/verification?site_key=mall-cn", vi.fn());

    expect(document.querySelector(".h5-member-detail-grid")).not.toBeNull();
    expect(document.querySelector(".h5-member-verification-status-flow")).not.toBeNull();
    expect(document.body.textContent).toContain("Active request summary notes.");
    expect(document.body.textContent).not.toContain("Verification detail unavailable");
  });

  it("renders the platform review note on the verification detail card", async () => {
    const reviewedRequest = {
      id: "vr-review-note",
      requestType: "identity",
      status: "rejected",
      notes: "My submitted document note.",
      reviewNote: "Please upload a clearer back-side document.",
      reviewerActorId: "risk-reviewer-3",
      reviewedAt: "2026-06-12T05:00:00Z",
      createdAt: "2026-06-12T04:00:00Z",
      updatedAt: "2026-06-12T05:00:00Z",
      documents: [],
    };
    vi.spyOn(h5MemberModule, "getCurrentMemberSession").mockResolvedValue({
      accountId: "38271456",
      phone: "13800000000",
      publicUserId: "h5-38271456",
      displayName: "Demo Member",
      inviteCode: "INV-ABCD1234",
    });
    vi.spyOn(h5MemberModule, "getMaskedPhone").mockResolvedValue("138****0000");
    vi.spyOn(h5MemberModule, "getMemberHomeDashboard").mockResolvedValue(createDashboardState());
    vi.spyOn(h5MemberModule, "getMemberVerificationSummary").mockResolvedValue({
      currentStatus: "rejected",
      hasActiveRequest: false,
      activeRequest: null,
      history: [reviewedRequest],
    });
    vi.spyOn(h5MemberModule, "listMemberVerificationRequests").mockResolvedValue([reviewedRequest]);
    vi.spyOn(h5MemberModule, "getMemberVerificationRequestDetail").mockResolvedValue(reviewedRequest);

    await renderApp("/h5/verification?site_key=mall-cn", vi.fn());

    expect(document.body.textContent).toContain("申请备注");
    expect(document.body.textContent).toContain("My submitted document note.");
    expect(document.body.textContent).toContain("审核备注");
    expect(document.body.textContent).toContain("Please upload a clearer back-side document.");
  });

  it("locks the verification page after submitting a new request and refreshes the visible state", async () => {
    const submittedRequest = {
      id: "vr-new",
      requestType: "identity",
      status: "pending",
      notes: "Please review my newly submitted identity documents.",
      reviewNote: null,
      reviewerActorId: null,
      reviewedAt: null,
      createdAt: "2026-06-12T11:00:00Z",
      updatedAt: "2026-06-12T11:01:00Z",
      documents: [],
    };
    const submitVerificationApiSpy = vi.spyOn(h5MemberModule, "submitVerificationApi").mockResolvedValue({
      id: submittedRequest.id,
      status: "pending",
    });
    const summarySpy = vi
      .spyOn(h5MemberModule, "getMemberVerificationSummary")
      .mockResolvedValueOnce({
        currentStatus: "not_submitted",
        hasActiveRequest: false,
        activeRequest: null,
        history: [],
      })
      .mockResolvedValueOnce({
        currentStatus: "pending",
        hasActiveRequest: true,
        activeRequest: submittedRequest,
        history: [submittedRequest],
      });

    vi.spyOn(h5MemberModule, "getCurrentMemberSession").mockResolvedValue({
      accountId: "38271456",
      phone: "13800000000",
      publicUserId: "h5-38271456",
      displayName: "Demo Member",
      inviteCode: "INV-ABCD1234",
    });
    vi
      .spyOn(h5MemberModule, "getMemberHomeDashboard")
      .mockResolvedValue({
        ...createDashboardState(),
        verification: {
          currentStatus: "pending",
          hasActiveRequest: true,
        },
      });
    vi.spyOn(h5MemberModule, "getMaskedPhone").mockResolvedValue("138****0000");
    vi
      .spyOn(h5MemberModule, "listMemberVerificationRequests")
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([submittedRequest]);
    vi.spyOn(h5MemberModule, "getMemberVerificationRequestDetail").mockResolvedValue(submittedRequest);

    await renderApp("/h5/verification?site_key=mall-cn", vi.fn());

    const form = document.querySelector(".h5-form") as HTMLFormElement | null;
    const nameInput = form?.querySelectorAll("input")[1] as HTMLInputElement | undefined;
    const textarea = form?.querySelector("textarea") as HTMLTextAreaElement | null;
    const submitButton = form?.querySelector('button[type="submit"]') as HTMLButtonElement | null;
    expect(form).not.toBeNull();
    expect(nameInput).toBeDefined();
    expect(textarea).not.toBeNull();
    expect(submitButton?.disabled).toBe(true);

    await act(async () => {
      if (nameInput) {
        setInputValue(nameInput, "Demo Member");
      }
      if (textarea) {
        setTextareaValue(textarea, "Please review my newly submitted identity documents.");
      }
    });
    expect(submitButton?.disabled).toBe(false);

    await act(async () => {
      form?.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    });
    await flushEffects();

    expect(submitVerificationApiSpy).toHaveBeenCalledWith({
      name: "Demo Member",
      idNumber: undefined,
    });
    expect(summarySpy).toHaveBeenCalledTimes(2);
    expect(document.querySelector(".h5-member-verification-status-flow")).not.toBeNull();
    expect(document.body.textContent).toContain("Please review my newly submitted identity documents.");
    expect(document.querySelector(".h5-member-verification-status-flow")).not.toBeNull();
    expect(document.querySelector(".h5-member-verification-form")).toBeNull();
  });

  it("keeps the newly submitted verification request visible when the follow-up refresh fails", async () => {
    const submittedRequest = {
      id: "vr-new-refresh-fallback",
      requestType: "identity",
      status: "pending",
      notes: "Keep this request visible even if the refresh fails.",
      reviewNote: null,
      reviewerActorId: null,
      reviewedAt: null,
      createdAt: "2026-06-12T12:00:00Z",
      updatedAt: "2026-06-12T12:01:00Z",
      documents: [],
    };
    vi.spyOn(h5MemberModule, "submitVerificationApi").mockResolvedValue({
      id: submittedRequest.id,
      status: "pending",
    });
    vi.spyOn(h5MemberModule, "getMemberVerificationSummary")
      .mockResolvedValueOnce({
        currentStatus: "not_submitted",
        hasActiveRequest: false,
        activeRequest: null,
        history: [],
      })
      .mockRejectedValueOnce(new Error("Verification summary refresh failed"));
    vi.spyOn(h5MemberModule, "getMemberHomeDashboard")
      .mockResolvedValueOnce(createDashboardState())
      .mockResolvedValueOnce({
        ...createDashboardState(),
        verification: {
          currentStatus: "pending",
          hasActiveRequest: true,
        },
      });
    vi.spyOn(h5MemberModule, "getCurrentMemberSession").mockResolvedValue({
      accountId: "38271456",
      phone: "13800000000",
      publicUserId: "h5-38271456",
      displayName: "Demo Member",
      inviteCode: "INV-ABCD1234",
    });
    vi.spyOn(h5MemberModule, "getMaskedPhone").mockResolvedValue("138****0000");
    vi.spyOn(h5MemberModule, "listMemberVerificationRequests")
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([]);
    vi.spyOn(h5MemberModule, "getMemberVerificationRequestDetail").mockResolvedValue(submittedRequest);

    await renderApp("/h5/verification?site_key=mall-cn", vi.fn());

    const form = document.querySelector(".h5-form") as HTMLFormElement | null;
    const nameInput = form?.querySelectorAll("input")[1] as HTMLInputElement | undefined;
    const textarea = form?.querySelector("textarea") as HTMLTextAreaElement | null;
    expect(form).not.toBeNull();
    expect(nameInput).toBeDefined();
    expect(textarea).not.toBeNull();

    await act(async () => {
      if (nameInput) {
        setInputValue(nameInput, "Fallback Member");
      }
      if (textarea) {
        setTextareaValue(textarea, "Keep this request visible even if the refresh fails.");
      }
    });

    await act(async () => {
      form?.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    });
    await flushEffects();

    expect(document.body.textContent).toContain("Keep this request visible even if the refresh fails.");
    expect(document.querySelector(".h5-member-verification-status-flow")).not.toBeNull();
    expect(document.body.textContent).not.toContain("Verification summary refresh failed");
    expect(document.querySelector(".h5-member-verification-form")).toBeNull();
  });

  it("switches the current verification detail when a history row is opened", async () => {
    const currentDetail = {
      id: "vr-1",
      requestType: "identity",
      status: "under_review",
      notes: "Current verification request detail A.",
      reviewNote: null,
      reviewerActorId: null,
      reviewedAt: null,
      createdAt: "2026-06-11T09:00:00Z",
      updatedAt: "2026-06-11T09:10:00Z",
      documents: [
        {
          id: "doc-a",
          fileName: "review-front-a.png",
          mimeType: "image/png",
          storageKey: "member-verification/review-front-a.png",
          metadataJson: null,
          createdAt: "2026-06-11T09:01:00Z",
        },
      ],
    };
    const approvedDetail = {
      id: "vr-2",
      requestType: "identity",
      status: "approved",
      notes: "Approved verification request detail B.",
      reviewNote: null,
      reviewerActorId: null,
      reviewedAt: "2026-06-10T08:10:00Z",
      createdAt: "2026-06-10T08:00:00Z",
      updatedAt: "2026-06-10T08:10:00Z",
      documents: [
        {
          id: "doc-b",
          fileName: "approved-passport-b.png",
          mimeType: "image/png",
          storageKey: "member-verification/approved-passport-b.png",
          metadataJson: null,
          createdAt: "2026-06-10T08:01:00Z",
        },
      ],
    };
    const detailSpy = vi
      .spyOn(h5MemberModule, "getMemberVerificationRequestDetail")
      .mockResolvedValueOnce(currentDetail)
      .mockResolvedValueOnce(approvedDetail);

    vi.spyOn(h5MemberModule, "getCurrentMemberSession").mockResolvedValue({
      accountId: "38271456",
      phone: "13800000000",
      publicUserId: "h5-38271456",
      displayName: "Demo Member",
      inviteCode: "INV-ABCD1234",
    });
    vi.spyOn(h5MemberModule, "getMemberHomeDashboard").mockResolvedValue(createDashboardState());
    vi.spyOn(h5MemberModule, "getMaskedPhone").mockResolvedValue("138****0000");
    vi.spyOn(h5MemberModule, "getMemberVerificationSummary").mockResolvedValue({
      currentStatus: "under_review",
      hasActiveRequest: true,
      activeRequest: {
        ...currentDetail,
        documents: [],
      },
      history: [
        {
          ...currentDetail,
          documents: [],
        },
        {
          ...approvedDetail,
          documents: [],
        },
      ],
    });
    vi.spyOn(h5MemberModule, "listMemberVerificationRequests").mockResolvedValue([
      {
        ...currentDetail,
        documents: [],
      },
      {
        ...approvedDetail,
        documents: [],
      },
    ]);

    await renderApp("/h5/verification?site_key=mall-cn", vi.fn());

    expect(document.body.textContent).toContain("review-front-a.png");
    expect(document.body.textContent).not.toContain("approved-passport-b.png");

    const historyButtons = document.querySelectorAll(".h5-member-list-row-button");
    expect(historyButtons.length).toBeGreaterThan(1);

    await act(async () => {
      (historyButtons[1] as HTMLButtonElement | undefined)?.click();
    });
    await flushEffects();

    expect(detailSpy).toHaveBeenNthCalledWith(2, "vr-2");
    expect(document.body.textContent).toContain("Approved verification request detail B.");
    expect(document.body.textContent).toContain("approved-passport-b.png");
  });

  it("keeps the local preview url on mock image messages", async () => {
    const sent = await h5MemberModule.sendMessageApi(
      "default",
      "Image",
      "image",
      "blob:chat-preview-1",
    );

    expect(sent.type).toBe("image");
    expect(sent.image_url).toBe("blob:chat-preview-1");
  });
});
