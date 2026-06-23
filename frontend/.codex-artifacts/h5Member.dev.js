import.meta.env = {"BASE_URL": "/", "DEV": true, "MODE": "development", "PROD": false, "SSR": false, "VITE_API_PROXY_TARGET": "http://localhost:8000"};import axios from "/node_modules/.vite/deps/axios.js?v=1453f96a";
import { t } from "/src/pages/h5-member/i18n/index.ts";
import { sessionManager } from "/src/services/h5SessionManager.ts";
const MEMBER_ACCOUNTS_KEY = "frontend.h5.member-accounts.v1";
const MEMBER_STATES_KEY = "frontend.h5.member-states.v1";
const MEMBER_SESSION_KEY = "frontend.h5.member-session.v1";
const DEFAULT_MEMBER_PHONE = "13800000000";
const DEFAULT_MEMBER_PASSWORD = "demo123456";
const ACCOUNT_ID_LENGTH = 8;
const DEFAULT_WITHDRAW_THRESHOLD = 100;
function getServiceErrorMessage(key) {
  return t(`serviceErrors.${key}`);
}
function getServiceMessage(key, params) {
  return t(`serviceMessages.${key}`, params);
}
function getSeedDataText(key, params) {
  return t(`seedData.${key}`, params);
}
function createServiceError(key) {
  return new Error(getServiceErrorMessage(key));
}
function getAuthRequiredMessage() {
  return getServiceErrorMessage("authRequired");
}
class ApiRequestError extends Error {
  status;
  constructor(status, detail) {
    super(
      detail || getServiceErrorMessage("requestFailedStatus").replace("{{status}}", String(status))
    );
    this.name = "ApiRequestError";
    this.status = status;
  }
}
export class H5AuthRequiredError extends Error {
  constructor(message = getAuthRequiredMessage()) {
    super(message);
    this.name = "H5AuthRequiredError";
  }
}
export function isH5AuthRequiredError(error) {
  return error instanceof H5AuthRequiredError;
}
export function resolveH5ApiBaseUrl(envApiBaseUrl, isDev) {
  const trimmed = envApiBaseUrl?.trim();
  if (trimmed) {
    return trimmed;
  }
  void isDev;
  return "";
}
const resolvedApiBaseUrl = resolveH5ApiBaseUrl(
  import.meta.env.VITE_API_BASE_URL,
  import.meta.env.DEV
);
export const h5Api = axios.create({
  baseURL: resolvedApiBaseUrl,
  timeout: 1e4,
  withCredentials: true
});
let _isRefreshing = false;
let _pendingQueue = [];
h5Api.interceptors.request.use(
  (config) => {
    if (sessionManager.shouldRefresh()) {
      sessionManager.refreshToken().catch(() => {
      });
    }
    const authHeaders = sessionManager.authHeader();
    if (authHeaders.Authorization) {
      config.headers.Authorization = authHeaders.Authorization;
    }
    return config;
  },
  (error) => Promise.reject(error)
);
h5Api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    if (!originalRequest) return Promise.reject(error);
    if (!error.response) {
      const message = getServiceErrorMessage("networkFailed");
      if (typeof window !== "undefined") {
        window.alert(message);
      }
      return Promise.reject(error);
    }
    const { status } = error.response;
    if (status === 401 && !originalRequest._retry) {
      if (_isRefreshing) {
        return new Promise((resolve, reject) => {
          _pendingQueue.push((token) => {
            if (token) {
              originalRequest.headers.Authorization = `Bearer ${token}`;
              resolve(h5Api(originalRequest));
            } else {
              reject(error);
            }
          });
        });
      }
      originalRequest._retry = true;
      _isRefreshing = true;
      try {
        const success = await sessionManager.refreshToken();
        if (success) {
          const newToken = sessionManager.getAccessToken();
          _pendingQueue.forEach((cb) => cb(newToken));
          _pendingQueue = [];
          originalRequest.headers.Authorization = `Bearer ${newToken}`;
          return h5Api(originalRequest);
        } else {
          _pendingQueue.forEach((cb) => cb(null));
          _pendingQueue = [];
          sessionManager.clearSession();
          return Promise.reject(error);
        }
      } catch (refreshError) {
        _pendingQueue.forEach((cb) => cb(null));
        _pendingQueue = [];
        return Promise.reject(refreshError);
      } finally {
        _isRefreshing = false;
      }
    }
    if (status >= 500 && status < 600 && originalRequest.method?.toUpperCase() === "GET" && !originalRequest._retry5xx) {
      originalRequest._retry5xx = true;
      await new Promise((resolve) => setTimeout(resolve, 2e3));
      return h5Api(originalRequest);
    }
    return Promise.reject(error);
  }
);
const apiMode = import.meta.env.VITE_API_MODE === "real" ? "real" : "mock";
function isBrowser() {
  return typeof window !== "undefined" && typeof window.localStorage !== "undefined";
}
function nowIso() {
  return (/* @__PURE__ */ new Date()).toISOString();
}
function readStorage(key, fallback) {
  if (!isBrowser()) {
    return fallback;
  }
  const raw = window.localStorage.getItem(key);
  if (!raw) {
    return fallback;
  }
  try {
    return JSON.parse(raw);
  } catch {
    return fallback;
  }
}
function writeStorage(key, value) {
  if (!isBrowser()) {
    return;
  }
  window.localStorage.setItem(key, JSON.stringify(value));
}
async function requestJson(input, init) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15e3);
  try {
    const response = await fetch(input, {
      credentials: "include",
      signal: controller.signal,
      ...init
    });
    if (!response.ok) {
      const rawText = await response.text();
      let detail = rawText;
      if (rawText) {
        try {
          const parsed = JSON.parse(rawText);
          if (typeof parsed.detail === "string" && parsed.detail.trim()) {
            detail = parsed.detail;
          }
        } catch {
          detail = rawText;
        }
      }
      throw new ApiRequestError(response.status, detail);
    }
    const contentType = response.headers.get("content-type")?.toLowerCase() ?? "";
    if (contentType.includes("text/html")) {
      throw new TypeError("Expected JSON response but received HTML.");
    }
    return await response.json();
  } catch (error) {
    if (error?.name === "AbortError") {
      throw createServiceError("requestTimeout");
    }
    throw error;
  } finally {
    clearTimeout(timeout);
  }
}
function isLegacyFallbackEnabled() {
  const configured = import.meta.env.VITE_H5_MEMBER_LEGACY_FALLBACK;
  if (configured === "true") {
    return true;
  }
  if (configured === "false") {
    return false;
  }
  return import.meta.env.DEV;
}
function canUseLegacyFallback(error) {
  if (!isLegacyFallbackEnabled()) {
    return false;
  }
  if (error instanceof TypeError || error instanceof SyntaxError) {
    return true;
  }
  return error instanceof ApiRequestError && error.status === 404;
}
function getBackendUnavailableError() {
  return createServiceError("authServiceUnavailable");
}
async function refreshBackendAuthSession() {
  try {
    const response = await requestJson("/api/h5/auth/refresh", {
      method: "POST"
    });
    const profile = buildProfileFromAuthPayload(response);
    syncLegacyMemberCacheFromProfile(profile);
    return true;
  } catch (error) {
    if (error instanceof ApiRequestError) {
      return false;
    }
    throw error;
  }
}
async function tryBackendAuthRequest(request, options) {
  try {
    return await request();
  } catch (error) {
    if (error instanceof ApiRequestError && error.status === 401) {
      if (options?.allowRefresh) {
        const refreshed = await refreshBackendAuthSession();
        if (refreshed) {
          return await request();
        }
        if (isLegacyFallbackEnabled()) {
          return null;
        }
      }
      return "unauthenticated";
    }
    if (canUseLegacyFallback(error)) {
      return null;
    }
    throw error;
  }
}
async function requestBackendMemberDomain(input, init) {
  const response = await tryBackendAuthRequest(() => requestJson(input, init), {
    allowRefresh: true
  });
  if (response === "unauthenticated") {
    writeSession(null);
    throw new H5AuthRequiredError();
  }
  return response;
}
function createId(prefix) {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return `${prefix}-${crypto.randomUUID()}`;
  }
  return `${prefix}-${Math.random().toString(36).slice(2, 10)}`;
}
function randomDigits(length) {
  let value = "";
  while (value.length < length) {
    value += Math.floor(Math.random() * 10).toString();
  }
  return value.slice(0, length);
}
function readMemberAccounts() {
  const seeded = seedMemberAccounts();
  const stored = readStorage(MEMBER_ACCOUNTS_KEY, seeded);
  if (isBrowser() && !window.localStorage.getItem(MEMBER_ACCOUNTS_KEY)) {
    writeStorage(MEMBER_ACCOUNTS_KEY, stored);
  }
  return stored;
}
function writeMemberAccounts(accounts) {
  writeStorage(MEMBER_ACCOUNTS_KEY, accounts);
}
function readMemberStates() {
  const seeded = seedMemberStates();
  const stored = readStorage(MEMBER_STATES_KEY, seeded);
  if (isBrowser() && !window.localStorage.getItem(MEMBER_STATES_KEY)) {
    writeStorage(MEMBER_STATES_KEY, stored);
  }
  return stored;
}
function writeMemberStates(states) {
  writeStorage(MEMBER_STATES_KEY, states);
}
function readSession() {
  return readStorage(MEMBER_SESSION_KEY, null);
}
function writeSession(session) {
  if (!isBrowser()) {
    return;
  }
  if (session === null) {
    window.localStorage.removeItem(MEMBER_SESSION_KEY);
    return;
  }
  writeStorage(MEMBER_SESSION_KEY, session);
}
function buildSessionFromAuthPayload(payload) {
  const memberNo = payload.member.memberNo?.trim() || payload.member.accountId;
  return {
    accountId: memberNo,
    phone: payload.member.phone,
    publicUserId: payload.member.publicUserId,
    displayName: payload.member.displayName?.trim() || payload.member.publicUserId,
    inviteCode: payload.member.inviteCode?.trim() || generateInviteCode(memberNo),
    avatarUrl: null
  };
}
function buildProfileFromAuthPayload(payload) {
  const session = buildSessionFromAuthPayload(payload);
  return {
    ...session,
    accountIdMasked: payload.member.accountIdMasked?.trim() || maskAccountId(session.accountId),
    createdAt: payload.member.createdAt
  };
}
function syncLegacyMemberCacheFromProfile(profile) {
  ensureSeededStorage();
  const accounts = readMemberAccounts();
  const existing = accounts.find((item) => item.accountId === profile.accountId);
  const nextAccount = {
    id: existing?.id ?? createId("member"),
    accountId: profile.accountId,
    phone: profile.phone,
    password: existing?.password ?? DEFAULT_MEMBER_PASSWORD,
    publicUserId: profile.publicUserId,
    displayName: profile.displayName,
    inviteCode: profile.inviteCode,
    createdAt: profile.createdAt,
    avatarUrl: existing?.avatarUrl ?? profile.avatarUrl ?? null
  };
  const nextAccounts = accounts.filter((item) => item.accountId !== profile.accountId);
  nextAccounts.push(nextAccount);
  writeMemberAccounts(nextAccounts);
  const states = readMemberStates();
  if (!states[profile.accountId]) {
    states[profile.accountId] = cloneStateTemplate();
    writeMemberStates(states);
  }
  writeSession({
    accountId: profile.accountId,
    phone: profile.phone,
    publicUserId: profile.publicUserId,
    displayName: profile.displayName,
    inviteCode: profile.inviteCode,
    avatarUrl: profile.avatarUrl ?? nextAccount.avatarUrl ?? null
  });
}
function mapSiteBrandFromBackend(site) {
  const base = getSiteBrand(site.siteKey);
  return {
    ...base,
    site_key: site.siteKey,
    brand_name: site.brandName
  };
}
function mapTaskPackageItemFromBackend(item) {
  return {
    id: item.id,
    product_name: item.productName,
    image_url: item.imageUrl ?? "",
    price: item.price,
    currency: item.currency,
    completed_at: item.completedAt,
    order_id: item.orderId
  };
}
function mapTaskPackageFromBackend(pkg) {
  return {
    id: pkg.id,
    title: pkg.title,
    description: pkg.description ?? "",
    type: pkg.type,
    status: pkg.status,
    rewardRatio: pkg.rewardRatio,
    claimedAt: pkg.claimedAt,
    expiresAt: pkg.expiresAt,
    dispatchedAt: pkg.dispatchedAt,
    completionWindowHours: pkg.completionWindowHours,
    items: pkg.items.map((item) => mapTaskPackageItemFromBackend(item)),
    promotion: pkg.promotion ? {
      metric: pkg.promotion.metric,
      current: pkg.promotion.current,
      target: pkg.promotion.target,
      inviteCode: pkg.promotion.inviteCode ?? ""
    } : null,
    taskBalanceAwardedAt: pkg.taskBalanceAwardedAt,
    totalCommission: pkg.totalCommission,
    currentCommission: pkg.currentCommission,
    completedItems: pkg.completedItems,
    totalItems: pkg.totalItems,
    countdownSeconds: pkg.countdownSeconds
  };
}
function mapWalletSummaryFromBackend(wallet) {
  return {
    systemBalance: wallet.systemBalance,
    taskBalance: wallet.taskBalance,
    currency: wallet.currency,
    withdrawThreshold: wallet.withdrawThreshold,
    canWithdraw: wallet.canWithdraw,
    shortfallAmount: wallet.shortfallAmount
  };
}
function mapOrderFromBackend(order) {
  return {
    id: order.id,
    orderNo: order.orderNo,
    packageId: order.packageId ?? "",
    packageTitle: order.packageTitle ?? "",
    productName: order.productName,
    amount: order.amount,
    currency: order.currency,
    status: order.status,
    createdAt: order.createdAt,
    sourceLabel: order.sourceLabel ?? ""
  };
}
function mapWalletTransactionFromBackend(transaction) {
  return {
    id: transaction.id,
    ledgerType: transaction.ledgerType,
    transactionType: transaction.transactionType,
    direction: transaction.direction,
    amount: transaction.amount,
    currency: transaction.currency,
    status: transaction.status,
    note: transaction.note ?? "",
    createdAt: transaction.createdAt
  };
}
function mapWithdrawalFromBackend(withdrawal) {
  return {
    id: withdrawal.id,
    amount: withdrawal.amount,
    currency: withdrawal.currency,
    status: withdrawal.status,
    createdAt: withdrawal.createdAt
  };
}
function mapLeaderboardEntryFromBackend(entry) {
  return {
    rank: entry.rank,
    accountIdMasked: entry.accountIdMasked,
    amount: entry.amount,
    currency: entry.currency
  };
}
function mapMessageFromBackend(message) {
  return {
    id: message.id,
    category: message.category,
    title: message.title,
    body: message.bodyText,
    createdAt: message.createdAt,
    isRead: message.isRead
  };
}
function mapVerificationDocumentFromBackend(document) {
  return {
    id: document.id,
    fileName: document.fileName ?? document.file_name ?? "",
    mimeType: document.mimeType ?? document.mime_type ?? null,
    storageKey: document.storageKey ?? document.storage_key ?? null,
    metadataJson: document.metadataJson ?? document.metadata_json ?? null,
    createdAt: document.createdAt ?? document.created_at ?? nowIso()
  };
}
function mapVerificationRequestFromBackend(request) {
  return {
    id: request.id,
    requestType: request.requestType ?? request.request_type ?? "",
    status: request.status,
    notes: request.notes,
    reviewNote: request.reviewNote ?? request.review_note ?? null,
    reviewerActorId: request.reviewerActorId ?? request.reviewer_actor_id ?? null,
    reviewedAt: request.reviewedAt ?? request.reviewed_at ?? null,
    createdAt: request.createdAt ?? request.created_at ?? nowIso(),
    updatedAt: request.updatedAt ?? request.updated_at ?? nowIso(),
    documents: request.documents.map((item) => mapVerificationDocumentFromBackend(item))
  };
}
function mapVerificationSummaryFromBackend(summary) {
  return {
    currentStatus: summary.currentStatus ?? summary.current_status ?? "not_submitted",
    hasActiveRequest: summary.hasActiveRequest ?? summary.has_active_request ?? false,
    activeRequest: summary.activeRequest ?? summary.active_request ? mapVerificationRequestFromBackend(summary.activeRequest ?? summary.active_request) : null,
    history: summary.history.map((item) => mapVerificationRequestFromBackend(item))
  };
}
function mapFragmentDropFromBackend(drop) {
  return {
    id: drop.id,
    fragmentId: drop.fragmentId,
    fragmentName: drop.fragmentName,
    source: drop.source,
    createdAt: drop.createdAt
  };
}
function mapShippingAddressFromBackend(address) {
  return {
    receiver: address.receiver,
    phone: address.phone,
    country: address.country,
    province: address.province,
    city: address.city,
    addressLine: address.addressLine
  };
}
function mapShippingOrderFromBackend(order) {
  return {
    id: order.id,
    rewardName: order.rewardName,
    status: order.status,
    createdAt: order.createdAt,
    address: order.address ? mapShippingAddressFromBackend(order.address) : null
  };
}
function mapFragmentOverviewFromBackend(overview) {
  return {
    inventory: overview.inventory.map((item) => ({
      id: item.id,
      name: item.name,
      rarity: item.rarity,
      color: item.color,
      owned: item.owned,
      required: item.required
    })),
    dropLogs: overview.dropLogs.map((item) => mapFragmentDropFromBackend(item)),
    rewardName: overview.rewardName,
    shippingOrders: overview.shippingOrders.map((item) => mapShippingOrderFromBackend(item))
  };
}
function getEmptyHomeFragmentSummary() {
  return {
    rewardName: null,
    completedCount: 0,
    totalCount: 0,
    missingCount: 0,
    canExchange: false,
    shippingOrderCount: 0,
    latestShippingStatus: null
  };
}
function getEmptyHomeVerificationSummary() {
  return {
    currentStatus: "not_submitted",
    hasActiveRequest: false
  };
}
function getEmptyVerificationSummary() {
  return {
    ...getEmptyHomeVerificationSummary(),
    activeRequest: null,
    history: []
  };
}
function mapHomeVerificationSummaryFromBackend(summary) {
  if (!summary) {
    return getEmptyHomeVerificationSummary();
  }
  return {
    currentStatus: summary.currentStatus,
    hasActiveRequest: summary.hasActiveRequest
  };
}
function buildVerificationSummaryFromRequests(requests) {
  if (requests.length === 0) {
    return getEmptyVerificationSummary();
  }
  const sorted = [...requests].sort((left, right) => right.createdAt.localeCompare(left.createdAt));
  const activeRequest = sorted.find((item) => item.status === "pending") ?? null;
  return {
    currentStatus: activeRequest?.status ?? sorted[0]?.status ?? "not_submitted",
    hasActiveRequest: activeRequest !== null,
    activeRequest,
    history: sorted
  };
}
function buildHomeVerificationSummaryFromState(state) {
  const summary = buildVerificationSummaryFromRequests(state.verificationRequests ?? []);
  return {
    currentStatus: summary.currentStatus,
    hasActiveRequest: summary.hasActiveRequest
  };
}
function mapHomeFragmentSummaryFromBackend(summary) {
  if (!summary) {
    return getEmptyHomeFragmentSummary();
  }
  return {
    rewardName: summary.rewardName,
    completedCount: summary.completedCount,
    totalCount: summary.totalCount,
    missingCount: summary.missingCount,
    canExchange: summary.canExchange,
    shippingOrderCount: summary.shippingOrderCount,
    latestShippingStatus: summary.latestShippingStatus
  };
}
function buildHomeFragmentSummaryFromOverview(overview) {
  const completedCount = overview.inventory.filter((item) => item.owned >= item.required).length;
  const totalCount = overview.inventory.length;
  const missingCount = overview.inventory.reduce(
    (sum, item) => sum + Math.max(0, item.required - item.owned),
    0
  );
  return {
    rewardName: overview.rewardName,
    completedCount,
    totalCount,
    missingCount,
    canExchange: totalCount > 0 && completedCount === totalCount,
    shippingOrderCount: overview.shippingOrders.length,
    latestShippingStatus: overview.shippingOrders[0]?.status ?? null
  };
}
function mapWhatsAppBindingFromBackend(binding) {
  return {
    isBound: binding.isBound,
    bindingStatus: binding.bindingStatus ?? (binding.isBound ? "bound" : "not_started"),
    requestId: binding.requestId ?? null,
    phoneNumber: binding.phoneNumber,
    requestedAt: binding.requestedAt ?? null,
    startCount: binding.startCount ?? 0,
    lastUpdatedAt: binding.lastUpdatedAt
  };
}
function seedMemberAccounts() {
  return [
    {
      id: "member-demo-1",
      accountId: "38271456",
      phone: DEFAULT_MEMBER_PHONE,
      password: DEFAULT_MEMBER_PASSWORD,
      publicUserId: "h5-38271456",
      displayName: getSeedDataText("memberDisplayName"),
      inviteCode: "INV38271456",
      createdAt: nowIso()
    }
  ];
}
function createPackageItem(packageId, index, price) {
  return {
    id: `${packageId}-item-${index + 1}`,
    product_name: `Task Product ${index + 1}`,
    image_url: `https://picsum.photos/seed/${packageId}-${index + 1}/160/160`,
    price,
    currency: "USD",
    completed_at: null,
    order_id: null
  };
}
function seedTaskPackages() {
  const now = Date.now();
  const activeClaimedAt = new Date(now - 1e3 * 60 * 60 * 3).toISOString();
  const activeExpiresAt = new Date(now + 1e3 * 60 * 60 * 18).toISOString();
  return [
    {
      id: "pkg-rookie-1",
      title: getSeedDataText("packageRookieTitle"),
      description: getSeedDataText("packageRookieDescription"),
      type: "rookie",
      status: "pending_claim",
      rewardRatio: 0.18,
      claimedAt: null,
      expiresAt: null,
      dispatchedAt: nowIso(),
      completionWindowHours: 24,
      items: [18, 22, 26, 31, 35].map((price, index) => createPackageItem("pkg-rookie-1", index, price)),
      promotion: null,
      taskBalanceAwardedAt: null
    },
    {
      id: "pkg-growth-1",
      title: getSeedDataText("packageGrowthTitle"),
      description: getSeedDataText("packageGrowthDescription"),
      type: "growth",
      status: "active",
      rewardRatio: 0.24,
      claimedAt: activeClaimedAt,
      expiresAt: activeExpiresAt,
      dispatchedAt: nowIso(),
      completionWindowHours: 24,
      items: [29, 33, 36, 42, 48].map((price, index) => createPackageItem("pkg-growth-1", index, price)),
      promotion: null,
      taskBalanceAwardedAt: null
    },
    {
      id: "pkg-promotion-1",
      title: getSeedDataText("packagePromotionTitle"),
      description: getSeedDataText("packagePromotionDescription"),
      type: "promotion",
      status: "pending_claim",
      rewardRatio: 0.12,
      claimedAt: null,
      expiresAt: null,
      dispatchedAt: nowIso(),
      completionWindowHours: 24,
      items: [],
      promotion: {
        metric: "invited_registrations",
        current: 3,
        target: 10,
        inviteCode: "PROMO-38271456"
      },
      taskBalanceAwardedAt: null
    }
  ];
}
function seedTransactions() {
  return [
    {
      id: "wallet-recharge-seed",
      ledgerType: "system",
      transactionType: "recharge",
      direction: "credit",
      amount: 300,
      currency: "USD",
      status: "paid",
      note: "Prototype top-up",
      createdAt: new Date(Date.now() - 1e3 * 60 * 60 * 12).toISOString()
    },
    {
      id: "wallet-task-seed",
      ledgerType: "task",
      transactionType: "task_reward",
      direction: "credit",
      amount: 88,
      currency: "USD",
      status: "paid",
      note: "Previous completed task package reward",
      createdAt: new Date(Date.now() - 1e3 * 60 * 60 * 6).toISOString()
    },
    {
      id: "wallet-withdraw-seed",
      ledgerType: "system",
      transactionType: "withdraw_paid",
      direction: "debit",
      amount: 120,
      currency: "USD",
      status: "paid",
      note: "Previous paid withdrawal",
      createdAt: new Date(Date.now() - 1e3 * 60 * 60 * 3).toISOString()
    }
  ];
}
function seedMessages() {
  return [
    {
      id: "msg-task-1",
      category: "task",
      title: getSeedDataText("messageTaskTitle"),
      body: getSeedDataText("messageTaskBody"),
      createdAt: new Date(Date.now() - 1e3 * 60 * 60 * 4).toISOString(),
      isRead: false
    },
    {
      id: "msg-wallet-1",
      category: "wallet",
      title: getSeedDataText("messageWalletTitle"),
      body: getSeedDataText("messageWalletBody"),
      createdAt: new Date(Date.now() - 1e3 * 60 * 60 * 2).toISOString(),
      isRead: false
    },
    {
      id: "msg-fragment-1",
      category: "fragment",
      title: getSeedDataText("messageFragmentTitle"),
      body: getSeedDataText("messageFragmentBody"),
      createdAt: new Date(Date.now() - 1e3 * 60 * 30).toISOString(),
      isRead: true
    }
  ];
}
function seedMemberStates() {
  return {
    "38271456": {
      wallet: {
        systemBalance: 420,
        taskBalance: 88,
        currency: "USD",
        withdrawThreshold: DEFAULT_WITHDRAW_THRESHOLD
      },
      taskPackages: seedTaskPackages(),
      orders: [
        {
          id: "order-seed-1",
          orderNo: "ORD-10001",
          packageId: "pkg-growth-1",
          packageTitle: getSeedDataText("packageGrowthTitle"),
          productName: "Task Product 1",
          amount: 29,
          currency: "USD",
          status: "paid",
          createdAt: new Date(Date.now() - 1e3 * 60 * 60 * 2).toISOString(),
          sourceLabel: getSeedDataText("packageGrowthTitle")
        }
      ],
      transactions: seedTransactions(),
      withdrawRequests: [
        {
          id: "withdraw-seed-1",
          amount: 120,
          currency: "USD",
          status: "paid",
          createdAt: new Date(Date.now() - 1e3 * 60 * 60 * 3).toISOString()
        }
      ],
      messages: seedMessages(),
      fragmentInventory: {
        "fragment-sun": 1,
        "fragment-moon": 0,
        "fragment-star": 2
      },
      fragmentDropLogs: [
        {
          id: "drop-seed-1",
          fragmentId: "fragment-star",
          fragmentName: getSeedDataText("fragmentStarName"),
          source: "task",
          createdAt: new Date(Date.now() - 1e3 * 60 * 20).toISOString()
        }
      ],
      shippingOrders: [
        {
          id: "shipping-seed-1",
          rewardName: getSeedDataText("rewardName"),
          status: "shipped",
          createdAt: new Date(Date.now() - 1e3 * 60 * 60 * 48).toISOString(),
          address: {
            receiver: "Demo User",
            phone: "13800000000",
            country: "China",
            province: "Guangdong",
            city: "Shenzhen",
            addressLine: "Nanshan Science Park"
          }
        }
      ],
      checkedInDate: null,
      verificationRequests: [],
      whatsappBinding: {
        isBound: false,
        bindingStatus: "not_started",
        requestId: null,
        phoneNumber: null,
        requestedAt: null,
        startCount: 0,
        lastUpdatedAt: null
      }
    }
  };
}
function getSiteBrand(siteKey) {
  if (siteKey === "flash-sale") {
    return {
      site_key: "flash-sale",
      brand_name: "Flash Sale Hub",
      tagline: "Fast orders, fast rewards.",
      accent_color: "#1459c7"
    };
  }
  if (siteKey === "daily-cn") {
    return {
      site_key: "daily-cn",
      brand_name: "Daily Member Club",
      tagline: "Check in, collect fragments, unlock rewards.",
      accent_color: "#0f766e"
    };
  }
  return {
    site_key: siteKey?.trim() || "mall-cn",
    brand_name: "Member Rewards Center",
    tagline: "Task packages, wallet, support, and fragments in one place.",
    accent_color: "#1677ff"
  };
}
function cloneStateTemplate() {
  const seeded = seedMemberStates()["38271456"];
  return JSON.parse(JSON.stringify(seeded));
}
function ensureSeededStorage() {
  readMemberAccounts();
  readMemberStates();
}
function getRequiredSession() {
  ensureSeededStorage();
  const session = readSession();
  if (!session) {
    throw createServiceError("authRequired");
  }
  return session;
}
function getStateForAccount(accountId) {
  ensureSeededStorage();
  const states = readMemberStates();
  const existing = states[accountId];
  if (existing) {
    const normalized = normalizeMemberState(existing);
    states[accountId] = normalized;
    writeMemberStates(states);
    return normalized;
  }
  const next = cloneStateTemplate();
  states[accountId] = next;
  writeMemberStates(states);
  return next;
}
function updateStateForAccount(accountId, updater) {
  const states = readMemberStates();
  const current = getStateForAccount(accountId);
  const next = normalizeMemberState(updater(JSON.parse(JSON.stringify(current))));
  states[accountId] = next;
  writeMemberStates(states);
  return next;
}
function normalizeMemberState(state) {
  state.verificationRequests = state.verificationRequests ?? [];
  const now = Date.now();
  state.taskPackages = state.taskPackages.map((pkg) => {
    if (pkg.status === "active" && pkg.expiresAt && new Date(pkg.expiresAt).getTime() <= now) {
      return { ...pkg, status: "expired" };
    }
    return pkg;
  });
  return state;
}
function calculatePackageTotalCommission(pkg) {
  return Number(
    pkg.items.reduce((sum, item) => sum + item.price, 0) * pkg.rewardRatio
  );
}
function calculatePackageCurrentCommission(pkg) {
  return Number(
    pkg.items.filter((item) => item.completed_at).reduce((sum, item) => sum + item.price, 0) * pkg.rewardRatio
  );
}
function getCompletedItemCount(pkg) {
  return pkg.items.filter((item) => item.completed_at).length;
}
function mapTaskPackage(pkg) {
  const countdownSeconds = pkg.expiresAt ? Math.max(0, Math.round((new Date(pkg.expiresAt).getTime() - Date.now()) / 1e3)) : pkg.completionWindowHours * 3600;
  return {
    ...pkg,
    totalCommission: calculatePackageTotalCommission(pkg),
    currentCommission: calculatePackageCurrentCommission(pkg),
    completedItems: getCompletedItemCount(pkg),
    totalItems: pkg.items.length,
    countdownSeconds
  };
}
function getUnreadMessageCount(messages) {
  return messages.filter((item) => !item.isRead).length;
}
function getWalletSummaryFromState(state) {
  const shortfall = Math.max(0, state.wallet.withdrawThreshold - state.wallet.systemBalance);
  return {
    systemBalance: Number(state.wallet.systemBalance.toFixed(2)),
    taskBalance: Number(state.wallet.taskBalance.toFixed(2)),
    currency: state.wallet.currency,
    withdrawThreshold: state.wallet.withdrawThreshold,
    canWithdraw: shortfall === 0,
    shortfallAmount: Number(shortfall.toFixed(2))
  };
}
function getFragmentDefinitions() {
  return [
    { id: "fragment-sun", name: getSeedDataText("fragmentSunName"), rarity: "common", color: "#f59e0b" },
    { id: "fragment-moon", name: getSeedDataText("fragmentMoonName"), rarity: "rare", color: "#6366f1" },
    { id: "fragment-star", name: getSeedDataText("fragmentStarName"), rarity: "epic", color: "#ef4444" }
  ];
}
function buildFragmentOverview(state) {
  return {
    inventory: getFragmentDefinitions().map((fragment) => ({
      ...fragment,
      owned: state.fragmentInventory[fragment.id] ?? 0,
      required: 1
    })),
    dropLogs: [...state.fragmentDropLogs].sort((left, right) => right.createdAt.localeCompare(left.createdAt)),
    rewardName: getSeedDataText("rewardName"),
    shippingOrders: [...state.shippingOrders].sort((left, right) => right.createdAt.localeCompare(left.createdAt))
  };
}
function appendMessage(state, category, title, body) {
  state.messages.unshift({
    id: createId("msg"),
    category,
    title,
    body,
    createdAt: nowIso(),
    isRead: false
  });
}
function appendLocalizedMessage(state, category, titleKey, bodyKey, options) {
  appendMessage(
    state,
    category,
    getServiceMessage(titleKey, options?.titleParams),
    getServiceMessage(bodyKey, options?.bodyParams)
  );
}
function appendTransaction(state, transaction) {
  state.transactions.unshift({
    id: createId("txn"),
    createdAt: nowIso(),
    ...transaction
  });
}
function maskPhone(phone) {
  if (phone.length < 7) {
    return phone;
  }
  return `${phone.slice(0, 3)}****${phone.slice(-4)}`;
}
export function maskAccountId(accountId) {
  if (accountId.length <= 5) {
    return accountId;
  }
  return `${accountId.slice(0, 3)}***${accountId.slice(-2)}`;
}
function todayKey() {
  return (/* @__PURE__ */ new Date()).toISOString().slice(0, 10);
}
function generateInviteCode(accountId) {
  return `INV${accountId}`;
}
function generateUniqueNumericAccountId() {
  const existing = new Set(readMemberAccounts().map((item) => item.accountId));
  let candidate = randomDigits(ACCOUNT_ID_LENGTH);
  while (existing.has(candidate)) {
    candidate = randomDigits(ACCOUNT_ID_LENGTH);
  }
  return candidate;
}
function getLeaderboardBaseEntries() {
  return [
    { accountId: "12864472", amount: 5200, currency: "USD" },
    { accountId: "87342155", amount: 4760, currency: "USD" },
    { accountId: "54021863", amount: 3980, currency: "USD" },
    { accountId: "74190538", amount: 3510, currency: "USD" }
  ];
}
export async function getCurrentMemberSession() {
  const stored = readSession();
  if (!stored) {
    if (isLegacyFallbackEnabled()) {
      ensureSeededStorage();
      return readSession();
    }
    return null;
  }
  const authResponse = await tryBackendAuthRequest(
    () => requestJson("/api/h5/auth/me"),
    {
      allowRefresh: true
    }
  );
  if (authResponse === "unauthenticated") {
    writeSession(null);
    return null;
  }
  if (authResponse) {
    const profile = buildProfileFromAuthPayload(authResponse);
    syncLegacyMemberCacheFromProfile(profile);
    return {
      accountId: profile.accountId,
      phone: profile.phone,
      publicUserId: profile.publicUserId,
      displayName: profile.displayName,
      inviteCode: profile.inviteCode
    };
  }
  if (!isLegacyFallbackEnabled()) {
    throw getBackendUnavailableError();
  }
  ensureSeededStorage();
  return readSession();
}
export async function getCurrentMemberProfile() {
  const authResponse = await tryBackendAuthRequest(
    () => requestJson("/api/h5/auth/me"),
    {
      allowRefresh: true
    }
  );
  if (authResponse === "unauthenticated") {
    writeSession(null);
    return null;
  }
  if (authResponse) {
    const profile = buildProfileFromAuthPayload(authResponse);
    syncLegacyMemberCacheFromProfile(profile);
    return profile;
  }
  if (!isLegacyFallbackEnabled()) {
    throw getBackendUnavailableError();
  }
  const session = await getCurrentMemberSession();
  if (!session) {
    return null;
  }
  const account = readMemberAccounts().find((item) => item.accountId === session.accountId);
  if (!account) {
    return null;
  }
  return {
    ...session,
    accountIdMasked: maskAccountId(session.accountId),
    createdAt: account.createdAt,
    avatarUrl: account.avatarUrl ?? null
  };
}
export async function updateMemberProfile(payload) {
  const session = getRequiredSession();
  const phone = payload.phone.trim();
  if (!phone) {
    throw createServiceError("phoneRequired");
  }
  const accounts = readMemberAccounts();
  const currentAccount = accounts.find((item) => item.accountId === session.accountId);
  if (!currentAccount) {
    throw createServiceError("memberNotFound");
  }
  if (accounts.some((item) => item.accountId !== session.accountId && item.phone === phone)) {
    throw createServiceError("phoneInUse");
  }
  const nextAccount = {
    ...currentAccount,
    phone,
    avatarUrl: payload.avatarUrl === void 0 ? currentAccount.avatarUrl ?? null : payload.avatarUrl
  };
  writeMemberAccounts(accounts.map((item) => item.accountId === session.accountId ? nextAccount : item));
  const nextSession = {
    ...session,
    phone: nextAccount.phone,
    avatarUrl: nextAccount.avatarUrl ?? null
  };
  writeSession(nextSession);
  return {
    ...nextSession,
    accountIdMasked: maskAccountId(nextSession.accountId),
    createdAt: nextAccount.createdAt,
    avatarUrl: nextAccount.avatarUrl ?? null
  };
}
export async function updateMemberPassword(payload) {
  const session = getRequiredSession();
  const currentPassword = payload.currentPassword.trim();
  const nextPassword = payload.nextPassword.trim();
  const confirmPassword = payload.confirmPassword.trim();
  if (!currentPassword || !nextPassword || !confirmPassword) {
    throw createServiceError("passwordFieldsRequired");
  }
  if (nextPassword.length < 6) {
    throw createServiceError("passwordTooShort");
  }
  if (nextPassword !== confirmPassword) {
    throw createServiceError("passwordMismatch");
  }
  const accounts = readMemberAccounts();
  const currentAccount = accounts.find((item) => item.accountId === session.accountId);
  if (!currentAccount) {
    throw createServiceError("memberNotFound");
  }
  if (currentAccount.password !== currentPassword) {
    throw createServiceError("currentPasswordIncorrect");
  }
  writeMemberAccounts(
    accounts.map(
      (item) => item.accountId === session.accountId ? {
        ...item,
        password: nextPassword
      } : item
    )
  );
}
export async function registerMember(payload) {
  try {
    const backendResponse = await tryBackendAuthRequest(
      () => requestJson("/api/h5/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          siteKey: payload.siteKey,
          phone: payload.phone.trim(),
          password: payload.password.trim(),
          confirmPassword: payload.confirmPassword?.trim() || payload.password.trim(),
          ...payload.displayName?.trim() ? { displayName: payload.displayName.trim() } : {}
        }),
        signal: AbortSignal.timeout(3e3)
      })
    );
    if (backendResponse === "unauthenticated") {
      if (isLegacyFallbackEnabled()) {
        const legacy2 = tryLegacyRegister(payload);
        if (legacy2) return legacy2;
      }
      throw createServiceError("registerAuthFailed");
    }
    if (backendResponse) {
      const profile = buildProfileFromAuthPayload(backendResponse);
      syncLegacyMemberCacheFromProfile(profile);
      return profile;
    }
  } catch (error) {
    if (error instanceof ApiRequestError && error.status === 409) {
      throw new Error(error.message || getServiceErrorMessage("registerFailed"));
    }
    if (isLegacyFallbackEnabled()) {
      const legacy2 = tryLegacyRegister(payload);
      if (legacy2) return legacy2;
    }
    if (error instanceof ApiRequestError && canUseLegacyFallback(error)) {
      const legacy2 = tryLegacyRegister(payload);
      if (legacy2) return legacy2;
    }
    throw error;
  }
  if (!isLegacyFallbackEnabled()) {
    throw getBackendUnavailableError();
  }
  const legacy = tryLegacyRegister(payload);
  if (!legacy) {
    throw createServiceError("registerFailed");
  }
  return legacy;
}
function tryLegacyRegister(payload) {
  ensureSeededStorage();
  const phone = payload.phone.trim();
  const password = payload.password.trim();
  if (!phone || !password) return null;
  const accounts = readMemberAccounts();
  if (accounts.some((item) => item.phone === phone)) {
    return null;
  }
  const accountId = generateUniqueNumericAccountId();
  const account = {
    id: createId("member"),
    accountId,
    phone,
    password,
    publicUserId: `h5-${accountId}`,
    displayName: payload.displayName?.trim() || getSeedDataText("memberDisplayNameWithSuffix", { suffix: accountId.slice(-4) }),
    inviteCode: generateInviteCode(accountId),
    createdAt: nowIso(),
    avatarUrl: null
  };
  accounts.push(account);
  writeMemberAccounts(accounts);
  const states = readMemberStates();
  states[accountId] = cloneStateTemplate();
  writeMemberStates(states);
  const session = {
    accountId,
    phone,
    publicUserId: account.publicUserId,
    displayName: account.displayName,
    inviteCode: account.inviteCode,
    avatarUrl: account.avatarUrl ?? null
  };
  writeSession(session);
  return {
    ...session,
    accountIdMasked: maskAccountId(session.accountId),
    createdAt: account.createdAt,
    avatarUrl: account.avatarUrl ?? null
  };
}
async function loginMemberResolved(payload) {
  try {
    const backendResponse = await requestJson("/api/h5/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        siteKey: payload.siteKey,
        phone: payload.phone.trim(),
        password: payload.password.trim()
      }),
      signal: AbortSignal.timeout(3e3)
    });
    const profile = buildProfileFromAuthPayload(backendResponse);
    syncLegacyMemberCacheFromProfile(profile);
    return profile;
  } catch (error) {
    if (error instanceof ApiRequestError && error.status === 401) {
      if (isLegacyFallbackEnabled()) {
        const legacy2 = tryLegacyLogin(payload.phone.trim(), payload.password.trim());
        if (legacy2) return legacy2;
      }
      const normalizedDetail = (error.message ?? "").trim();
      if (normalizedDetail && !/phone or password is invalid/i.test(normalizedDetail) && !/手机号或密码错误/.test(normalizedDetail)) {
        throw new Error(normalizedDetail);
      }
      throw createServiceError("invalidCredentials");
    }
    if (isLegacyFallbackEnabled()) {
      const legacy2 = tryLegacyLogin(payload.phone.trim(), payload.password.trim());
      if (legacy2) return legacy2;
    }
    if (!canUseLegacyFallback(error)) {
      throw createServiceError("backendUnavailable");
    }
  }
  if (!isLegacyFallbackEnabled()) {
    throw getBackendUnavailableError();
  }
  ensureSeededStorage();
  const legacy = tryLegacyLogin(payload.phone.trim(), payload.password.trim());
  if (!legacy) {
    throw createServiceError("invalidCredentials");
  }
  return legacy;
}
function tryLegacyLogin(phone, password) {
  const account = readMemberAccounts().find(
    (item) => item.phone === phone && item.password === password
  );
  if (!account) return null;
  const session = {
    accountId: account.accountId,
    phone: account.phone,
    publicUserId: account.publicUserId,
    displayName: account.displayName,
    inviteCode: account.inviteCode,
    avatarUrl: account.avatarUrl ?? null
  };
  writeSession(session);
  return {
    ...session,
    accountIdMasked: maskAccountId(session.accountId),
    createdAt: account.createdAt,
    avatarUrl: account.avatarUrl ?? null
  };
}
export async function loginMember(payload) {
  return loginMemberResolved(payload);
}
export async function logoutMember() {
  try {
    const logoutResponse = await tryBackendAuthRequest(
      () => requestJson("/api/h5/auth/logout", {
        method: "POST"
      })
    );
    if (logoutResponse === "unauthenticated") {
      writeSession(null);
      return;
    }
  } catch (error) {
    if (!canUseLegacyFallback(error) && !(error instanceof TypeError)) {
      throw error;
    }
  } finally {
    writeSession(null);
  }
}
export async function getMemberHomeDashboard(siteKey) {
  const homeResponse = await tryBackendAuthRequest(
    () => requestJson("/api/h5/member/home"),
    {
      allowRefresh: true
    }
  );
  if (homeResponse === "unauthenticated") {
    writeSession(null);
    throw new H5AuthRequiredError();
  }
  if (homeResponse) {
    const profile = buildProfileFromAuthPayload({
      member: homeResponse.member,
      site: homeResponse.site
    });
    syncLegacyMemberCacheFromProfile(profile);
    return {
      site: mapSiteBrandFromBackend(homeResponse.site),
      member: profile,
      wallet: {
        systemBalance: homeResponse.wallet.systemBalance ?? 0,
        taskBalance: homeResponse.wallet.taskBalance ?? 0,
        currency: homeResponse.wallet.currency ?? "USD",
        withdrawThreshold: DEFAULT_WITHDRAW_THRESHOLD,
        canWithdraw: (homeResponse.wallet.systemBalance ?? 0) >= DEFAULT_WITHDRAW_THRESHOLD,
        shortfallAmount: Math.max(
          0,
          DEFAULT_WITHDRAW_THRESHOLD - (homeResponse.wallet.systemBalance ?? 0)
        )
      },
      unreadCount: homeResponse.unreadMessageCount,
      pendingClaimCount: homeResponse.pendingClaimCount,
      activeCount: homeResponse.activeCount,
      expiringCount: homeResponse.expiringCount,
      recentMessages: homeResponse.recentMessages.map((item) => ({
        id: item.id,
        category: item.category,
        title: item.title,
        body: item.bodyText,
        createdAt: item.createdAt,
        isRead: item.isRead
      })),
      leaderboard: homeResponse.leaderboard.map((item) => ({
        rank: item.rank,
        accountIdMasked: item.accountIdMasked,
        amount: item.amount,
        currency: item.currency
      })),
      verification: mapHomeVerificationSummaryFromBackend(homeResponse.verification),
      fragments: mapHomeFragmentSummaryFromBackend(homeResponse.fragments)
    };
  }
  if (!isLegacyFallbackEnabled()) {
    throw getBackendUnavailableError();
  }
  const session = getRequiredSession();
  const account = readMemberAccounts().find((item) => item.accountId === session.accountId);
  const state = getStateForAccount(session.accountId);
  const packages = state.taskPackages.map((pkg) => mapTaskPackage(pkg));
  const fragmentOverview = buildFragmentOverview(state);
  return {
    site: getSiteBrand(siteKey),
    member: {
      ...session,
      accountIdMasked: maskAccountId(session.accountId),
      createdAt: account.createdAt,
      avatarUrl: account.avatarUrl ?? null
    },
    wallet: getWalletSummaryFromState(state),
    unreadCount: getUnreadMessageCount(state.messages),
    pendingClaimCount: packages.filter((pkg) => pkg.status === "pending_claim").length,
    activeCount: packages.filter((pkg) => pkg.status === "active").length,
    expiringCount: packages.filter((pkg) => pkg.status === "active" && pkg.countdownSeconds <= 6 * 3600).length,
    recentMessages: [...state.messages].slice(0, 5),
    leaderboard: (await getWithdrawLeaderboard()).slice(0, 5),
    verification: buildHomeVerificationSummaryFromState(state),
    fragments: buildHomeFragmentSummaryFromOverview(fragmentOverview)
  };
}
export async function listTaskPackages() {
  const backendPackages = await requestBackendMemberDomain("/api/h5/task-packages");
  if (backendPackages) {
    return backendPackages.map((pkg) => mapTaskPackageFromBackend(pkg));
  }
  const session = getRequiredSession();
  const state = getStateForAccount(session.accountId);
  return state.taskPackages.map((pkg) => mapTaskPackage(pkg));
}
export async function getTaskPackageDetail(packageId) {
  const backendPackage = await requestBackendMemberDomain(
    `/api/h5/task-packages/${encodeURIComponent(packageId)}`
  );
  if (backendPackage) {
    return mapTaskPackageFromBackend(backendPackage);
  }
  const pkg = (await listTaskPackages()).find((item) => item.id === packageId);
  if (!pkg) {
    throw createServiceError("taskPackageNotFound");
  }
  return pkg;
}
export async function claimTaskPackage(packageId) {
  const backendPackage = await requestBackendMemberDomain(
    `/api/h5/task-packages/${encodeURIComponent(packageId)}/claim`,
    {
      method: "POST"
    }
  );
  if (backendPackage) {
    return mapTaskPackageFromBackend(backendPackage);
  }
  const session = getRequiredSession();
  const nextState = updateStateForAccount(session.accountId, (state) => {
    const pkg = state.taskPackages.find((item) => item.id === packageId);
    if (!pkg) {
      throw createServiceError("taskPackageNotFound");
    }
    if (pkg.status !== "pending_claim") {
      return state;
    }
    const claimedAt = nowIso();
    pkg.status = "active";
    pkg.claimedAt = claimedAt;
    pkg.expiresAt = new Date(Date.now() + pkg.completionWindowHours * 3600 * 1e3).toISOString();
    appendLocalizedMessage(state, "task", "packageClaimTitle", "packageClaimBody", {
      titleParams: { title: pkg.title }
    });
    return state;
  });
  const updated = nextState.taskPackages.find((item) => item.id === packageId);
  return mapTaskPackage(updated);
}
export async function completeTaskPackagePurchase(packageId, itemId) {
  const backendPurchase = await requestBackendMemberDomain(
    `/api/h5/task-packages/${encodeURIComponent(packageId)}/items/${encodeURIComponent(itemId)}/purchase`,
    {
      method: "POST"
    }
  );
  if (backendPurchase) {
    return {
      success: backendPurchase.success,
      order: backendPurchase.order ? mapOrderFromBackend(backendPurchase.order) : void 0,
      taskPackage: mapTaskPackageFromBackend(backendPurchase.taskPackage),
      wallet: mapWalletSummaryFromBackend(backendPurchase.wallet),
      fragmentDrop: backendPurchase.fragmentDrop ? mapFragmentDropFromBackend(backendPurchase.fragmentDrop) : null,
      reason: backendPurchase.reason ?? void 0
    };
  }
  const session = getRequiredSession();
  let operationResult = null;
  const nextState = updateStateForAccount(session.accountId, (state) => {
    const pkg = state.taskPackages.find((item2) => item2.id === packageId);
    if (!pkg) {
      throw createServiceError("taskPackageNotFound");
    }
    if (pkg.status !== "active") {
      operationResult = { success: false, taskPackage: pkg, reason: getServiceErrorMessage("taskPackageUnavailable") };
      return state;
    }
    if (pkg.expiresAt && new Date(pkg.expiresAt).getTime() <= Date.now()) {
      pkg.status = "expired";
      operationResult = { success: false, taskPackage: pkg, reason: getServiceErrorMessage("taskPackageExpired") };
      return state;
    }
    const item = pkg.items.find((entry) => entry.id === itemId);
    if (!item) {
      throw createServiceError("taskItemNotFound");
    }
    if (item.completed_at) {
      operationResult = { success: true, taskPackage: pkg, reason: getServiceErrorMessage("taskItemCompleted") };
      return state;
    }
    if (state.wallet.systemBalance < item.price) {
      operationResult = { success: false, taskPackage: pkg, reason: getServiceErrorMessage("systemBalanceInsufficient") };
      return state;
    }
    state.wallet.systemBalance = Number((state.wallet.systemBalance - item.price).toFixed(2));
    const order = {
      id: createId("order"),
      orderNo: `ORD-${Math.random().toString().slice(2, 10)}`,
      packageId: pkg.id,
      packageTitle: pkg.title,
      productName: item.product_name,
      amount: item.price,
      currency: item.currency,
      status: "paid",
      createdAt: nowIso(),
      sourceLabel: pkg.title
    };
    item.completed_at = order.createdAt;
    item.order_id = order.id;
    state.orders.unshift(order);
    appendTransaction(state, {
      ledgerType: "system",
      transactionType: "purchase",
      direction: "debit",
      amount: item.price,
      currency: item.currency,
      status: "paid",
      note: `${pkg.title} / ${item.product_name}`
    });
    appendLocalizedMessage(state, "order", "purchaseSuccessTitle", "purchaseSuccessBody", {
      titleParams: { product: item.product_name }
    });
    let fragmentDrop = null;
    const completedItems = pkg.items.filter((entry) => entry.completed_at).length;
    if (pkg.items.length > 0 && completedItems === pkg.items.length) {
      pkg.status = "completed";
      pkg.taskBalanceAwardedAt = nowIso();
      const rewardAmount = Number(calculatePackageTotalCommission(pkg).toFixed(2));
      state.wallet.taskBalance = Number((state.wallet.taskBalance + rewardAmount).toFixed(2));
      appendTransaction(state, {
        ledgerType: "task",
        transactionType: "task_reward",
        direction: "credit",
        amount: rewardAmount,
        currency: state.wallet.currency,
        status: "paid",
        note: `${pkg.title} completed`
      });
      appendLocalizedMessage(state, "task", "packageCompletedTitle", "packageCompletedBody", {
        titleParams: { title: pkg.title }
      });
      fragmentDrop = createFragmentDrop(state, "task");
    }
    operationResult = { success: true, order, taskPackage: pkg, fragmentDrop };
    return state;
  });
  if (!operationResult) {
    throw createServiceError("purchaseInitFailed");
  }
  const settledResult = operationResult;
  return {
    ...settledResult,
    taskPackage: mapTaskPackage(settledResult.taskPackage),
    wallet: getWalletSummaryFromState(nextState)
  };
}
function createFragmentDrop(state, source) {
  const definitions = getFragmentDefinitions();
  const index = state.fragmentDropLogs.length % definitions.length;
  const fragment = definitions[index];
  state.fragmentInventory[fragment.id] = (state.fragmentInventory[fragment.id] ?? 0) + 1;
  const drop = {
    id: createId("fragment-drop"),
    fragmentId: fragment.id,
    fragmentName: fragment.name,
    source,
    createdAt: nowIso()
  };
  state.fragmentDropLogs.unshift(drop);
  appendLocalizedMessage(
    state,
    "fragment",
    "fragmentObtainedTitle",
    source === "checkin" ? "fragmentObtainedBodyCheckin" : "fragmentObtainedBodyTask",
    {
      titleParams: { fragment: fragment.name }
    }
  );
  return drop;
}
export async function listMemberOrders() {
  const backendOrders = await requestBackendMemberDomain("/api/h5/orders");
  if (backendOrders) {
    return backendOrders.map((order) => mapOrderFromBackend(order));
  }
  const session = getRequiredSession();
  const state = getStateForAccount(session.accountId);
  return [...state.orders].sort((left, right) => right.createdAt.localeCompare(left.createdAt));
}
export async function getWalletSummary() {
  const backendWallet = await requestBackendMemberDomain("/api/h5/wallet");
  if (backendWallet) {
    return mapWalletSummaryFromBackend(backendWallet);
  }
  const session = getRequiredSession();
  return getWalletSummaryFromState(getStateForAccount(session.accountId));
}
export async function listWalletTransactions() {
  const backendTransactions = await requestBackendMemberDomain(
    "/api/h5/wallet/transactions"
  );
  if (backendTransactions) {
    return backendTransactions.map((item) => mapWalletTransactionFromBackend(item));
  }
  const session = getRequiredSession();
  const state = getStateForAccount(session.accountId);
  return [...state.transactions].sort((left, right) => right.createdAt.localeCompare(left.createdAt));
}
export async function listWithdrawRequests() {
  const backendWithdrawals = await requestBackendMemberDomain(
    "/api/h5/withdrawals"
  );
  if (backendWithdrawals) {
    return backendWithdrawals.map((item) => mapWithdrawalFromBackend(item));
  }
  const session = getRequiredSession();
  const state = getStateForAccount(session.accountId);
  return [...state.withdrawRequests].sort((left, right) => right.createdAt.localeCompare(left.createdAt));
}
export async function createRechargeOrder(amount) {
  const backendWallet = await requestBackendMemberDomain(
    "/api/h5/wallet/recharges",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ amount })
    }
  );
  if (backendWallet) {
    return mapWalletSummaryFromBackend(backendWallet);
  }
  const session = getRequiredSession();
  const sanitizedAmount = Number(amount.toFixed(2));
  if (sanitizedAmount <= 0) {
    throw createServiceError("rechargeAmountInvalid");
  }
  const state = updateStateForAccount(session.accountId, (draft) => {
    draft.wallet.systemBalance = Number((draft.wallet.systemBalance + sanitizedAmount).toFixed(2));
    appendTransaction(draft, {
      ledgerType: "system",
      transactionType: "recharge",
      direction: "credit",
      amount: sanitizedAmount,
      currency: draft.wallet.currency,
      status: "paid",
      note: "Prototype recharge"
    });
    appendLocalizedMessage(draft, "wallet", "rechargeTitle", "rechargeBody", {
      bodyParams: { amount: sanitizedAmount.toFixed(2) }
    });
    return draft;
  });
  return getWalletSummaryFromState(state);
}
export async function transferTaskBalanceToSystem(amount) {
  const backendWallet = await requestBackendMemberDomain(
    "/api/h5/wallet/transfers",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ amount })
    }
  );
  if (backendWallet) {
    return mapWalletSummaryFromBackend(backendWallet);
  }
  const session = getRequiredSession();
  const sanitizedAmount = Number(amount.toFixed(2));
  if (sanitizedAmount <= 0) {
    throw createServiceError("transferAmountInvalid");
  }
  const state = updateStateForAccount(session.accountId, (draft) => {
    if (draft.wallet.taskBalance < sanitizedAmount) {
      throw createServiceError("taskBalanceInsufficient");
    }
    draft.wallet.taskBalance = Number((draft.wallet.taskBalance - sanitizedAmount).toFixed(2));
    draft.wallet.systemBalance = Number((draft.wallet.systemBalance + sanitizedAmount).toFixed(2));
    appendTransaction(draft, {
      ledgerType: "task",
      transactionType: "task_to_system_transfer",
      direction: "debit",
      amount: sanitizedAmount,
      currency: draft.wallet.currency,
      status: "paid",
      note: "Transfer out from task balance"
    });
    appendTransaction(draft, {
      ledgerType: "system",
      transactionType: "task_to_system_transfer",
      direction: "credit",
      amount: sanitizedAmount,
      currency: draft.wallet.currency,
      status: "paid",
      note: "Transfer in from task balance"
    });
    appendLocalizedMessage(draft, "wallet", "transferTitle", "transferBody");
    return draft;
  });
  return getWalletSummaryFromState(state);
}
export async function createWithdrawRequest(amount) {
  const backendWithdrawal = await requestBackendMemberDomain(
    "/api/h5/withdrawals",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ amount })
    }
  );
  if (backendWithdrawal) {
    return getWalletSummary();
  }
  const session = getRequiredSession();
  const sanitizedAmount = Number(amount.toFixed(2));
  const state = updateStateForAccount(session.accountId, (draft) => {
    if (draft.wallet.systemBalance < draft.wallet.withdrawThreshold) {
      throw createServiceError("withdrawThresholdNotMet");
    }
    if (sanitizedAmount <= 0) {
      throw createServiceError("withdrawAmountInvalid");
    }
    if (draft.wallet.systemBalance < sanitizedAmount) {
      throw createServiceError("systemBalanceInsufficient");
    }
    draft.wallet.systemBalance = Number((draft.wallet.systemBalance - sanitizedAmount).toFixed(2));
    draft.withdrawRequests.unshift({
      id: createId("withdraw"),
      amount: sanitizedAmount,
      currency: draft.wallet.currency,
      status: "submitted",
      createdAt: nowIso()
    });
    appendTransaction(draft, {
      ledgerType: "system",
      transactionType: "withdraw_request",
      direction: "debit",
      amount: sanitizedAmount,
      currency: draft.wallet.currency,
      status: "submitted",
      note: "Withdrawal request submitted"
    });
    appendLocalizedMessage(draft, "wallet", "withdrawTitle", "withdrawBody");
    return draft;
  });
  return getWalletSummaryFromState(state);
}
export async function getWithdrawLeaderboard() {
  const backendLeaderboard = await requestBackendMemberDomain(
    "/api/h5/withdraw-leaderboard"
  );
  if (backendLeaderboard) {
    return backendLeaderboard.map((item) => mapLeaderboardEntryFromBackend(item));
  }
  const states = readMemberStates();
  const dynamic = Object.entries(states).map(([accountId, state]) => ({
    accountId,
    amount: state.withdrawRequests.filter((item) => item.status === "paid").reduce((sum, item) => sum + item.amount, 0),
    currency: state.wallet.currency
  }));
  return [...getLeaderboardBaseEntries(), ...dynamic].filter((item) => item.amount > 0).sort((left, right) => right.amount - left.amount).slice(0, 10).map((item, index) => ({
    rank: index + 1,
    accountIdMasked: maskAccountId(item.accountId),
    amount: Number(item.amount.toFixed(2)),
    currency: item.currency
  }));
}
export async function listMemberMessages() {
  const backendMessages = await requestBackendMemberDomain("/api/h5/messages");
  if (backendMessages) {
    return backendMessages.map((item) => mapMessageFromBackend(item));
  }
  const session = getRequiredSession();
  const state = getStateForAccount(session.accountId);
  return [...state.messages].sort((left, right) => right.createdAt.localeCompare(left.createdAt));
}
export async function markMessageRead(messageId) {
  const backendMessage = await requestBackendMemberDomain(
    `/api/h5/messages/${encodeURIComponent(messageId)}/read`,
    {
      method: "POST"
    }
  );
  if (backendMessage) {
    return;
  }
  const session = getRequiredSession();
  updateStateForAccount(session.accountId, (draft) => {
    const item = draft.messages.find((entry) => entry.id === messageId);
    if (item) {
      item.isRead = true;
    }
    return draft;
  });
}
export async function markAllMessagesRead() {
  const backendResult = await requestBackendMemberDomain(
    "/api/h5/messages/read-all",
    {
      method: "POST"
    }
  );
  if (backendResult) {
    return;
  }
  const session = getRequiredSession();
  updateStateForAccount(session.accountId, (draft) => {
    draft.messages = draft.messages.map((item) => ({ ...item, isRead: true }));
    return draft;
  });
}
export async function getMemberVerificationSummary() {
  const backendSummary = await requestBackendMemberDomain(
    "/api/h5/member/verification"
  );
  if (backendSummary) {
    return mapVerificationSummaryFromBackend(backendSummary);
  }
  const session = getRequiredSession();
  const state = getStateForAccount(session.accountId);
  return buildVerificationSummaryFromRequests(state.verificationRequests ?? []);
}
export async function listMemberVerificationRequests() {
  const backendRequests = await requestBackendMemberDomain(
    "/api/h5/member/verification/requests"
  );
  if (backendRequests) {
    return backendRequests.map((item) => mapVerificationRequestFromBackend(item));
  }
  const session = getRequiredSession();
  const state = getStateForAccount(session.accountId);
  return [...state.verificationRequests ?? []].sort((left, right) => right.createdAt.localeCompare(left.createdAt));
}
export async function createMemberVerificationRequest(payload) {
  const requestPayload = {
    requestType: payload.requestType?.trim() || "identity",
    notes: payload.notes?.trim() || null,
    documents: (payload.documents ?? []).map((item) => ({
      fileName: item.fileName.trim(),
      mimeType: item.mimeType?.trim() || null,
      storageKey: item.storageKey?.trim() || null,
      metadataJson: item.metadataJson ?? null
    }))
  };
  const backendRequest = await requestBackendMemberDomain(
    "/api/h5/member/verification/requests",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(requestPayload)
    }
  );
  if (backendRequest) {
    return mapVerificationRequestFromBackend(backendRequest);
  }
  const session = getRequiredSession();
  const state = updateStateForAccount(session.accountId, (draft) => {
    const currentSummary = buildVerificationSummaryFromRequests(draft.verificationRequests ?? []);
    if (currentSummary.hasActiveRequest) {
      throw new Error("An active verification request already exists.");
    }
    const createdAt = nowIso();
    const nextRequest = {
      id: createId("verification-request"),
      requestType: requestPayload.requestType,
      status: "pending",
      notes: requestPayload.notes,
      reviewNote: null,
      reviewerActorId: null,
      reviewedAt: null,
      createdAt,
      updatedAt: createdAt,
      documents: requestPayload.documents.map((item) => ({
        id: createId("verification-document"),
        fileName: item.fileName,
        mimeType: item.mimeType,
        storageKey: item.storageKey,
        metadataJson: item.metadataJson,
        createdAt
      }))
    };
    draft.verificationRequests = [nextRequest, ...draft.verificationRequests ?? []];
    appendLocalizedMessage(draft, "system", "verificationSubmittedTitle", "verificationSubmittedBody");
    return draft;
  });
  return state.verificationRequests[0];
}
export async function getMemberVerificationRequestDetail(requestId) {
  const backendRequest = await requestBackendMemberDomain(
    `/api/h5/member/verification/requests/${encodeURIComponent(requestId)}`
  );
  if (backendRequest) {
    return mapVerificationRequestFromBackend(backendRequest);
  }
  const requests = await listMemberVerificationRequests();
  const request = requests.find((item) => item.id === requestId);
  if (!request) {
    throw createServiceError("verificationRequestNotFound");
  }
  return request;
}
export async function performDailyCheckIn() {
  const backendOverview = await requestBackendMemberDomain(
    "/api/h5/fragments/check-in",
    {
      method: "POST"
    }
  );
  if (backendOverview) {
    return mapFragmentOverviewFromBackend(backendOverview);
  }
  const session = getRequiredSession();
  const state = updateStateForAccount(session.accountId, (draft) => {
    if (draft.checkedInDate === todayKey()) {
      throw createServiceError("alreadyCheckedIn");
    }
    draft.checkedInDate = todayKey();
    createFragmentDrop(draft, "checkin");
    appendLocalizedMessage(draft, "system", "checkinTitle", "checkinBody");
    return draft;
  });
  return buildFragmentOverview(state);
}
export async function getFragmentsOverview() {
  const backendOverview = await requestBackendMemberDomain("/api/h5/fragments");
  if (backendOverview) {
    return mapFragmentOverviewFromBackend(backendOverview);
  }
  const session = getRequiredSession();
  return buildFragmentOverview(getStateForAccount(session.accountId));
}
export async function createFragmentExchange(payload) {
  const backendOverview = await requestBackendMemberDomain(
    "/api/h5/fragments/exchanges",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    }
  );
  if (backendOverview) {
    return mapFragmentOverviewFromBackend(backendOverview);
  }
  const session = getRequiredSession();
  const state = updateStateForAccount(session.accountId, (draft) => {
    const overview = buildFragmentOverview(draft);
    const lacks = overview.inventory.find((item) => item.owned < item.required);
    if (lacks) {
      throw createServiceError("fragmentsIncomplete");
    }
    for (const item of overview.inventory) {
      draft.fragmentInventory[item.id] = Math.max(0, (draft.fragmentInventory[item.id] ?? 0) - item.required);
    }
    draft.shippingOrders.unshift({
      id: createId("shipping"),
      rewardName: overview.rewardName,
      status: "submitted",
      createdAt: nowIso(),
      address: payload
    });
    appendLocalizedMessage(draft, "fragment", "exchangeTitle", "exchangeBody");
    return draft;
  });
  return buildFragmentOverview(state);
}
export async function getRewardShippingOrders() {
  const backendOrders = await requestBackendMemberDomain(
    "/api/h5/rewards/shipping"
  );
  if (backendOrders) {
    return backendOrders.map((item) => mapShippingOrderFromBackend(item));
  }
  const session = getRequiredSession();
  const state = getStateForAccount(session.accountId);
  return [...state.shippingOrders].sort((left, right) => right.createdAt.localeCompare(left.createdAt));
}
export async function getWhatsAppBinding() {
  const backendBinding = await requestBackendMemberDomain(
    "/api/h5/whatsapp-binding"
  );
  if (backendBinding) {
    return mapWhatsAppBindingFromBackend(backendBinding);
  }
  const session = getRequiredSession();
  return getStateForAccount(session.accountId).whatsappBinding;
}
export async function startWhatsAppBinding() {
  const backendBinding = await requestBackendMemberDomain(
    "/api/h5/whatsapp-binding/start",
    {
      method: "POST"
    }
  );
  if (backendBinding) {
    return mapWhatsAppBindingFromBackend(backendBinding);
  }
  const session = getRequiredSession();
  const state = updateStateForAccount(session.accountId, (draft) => {
    draft.whatsappBinding = {
      isBound: false,
      bindingStatus: "pending",
      requestId: draft.whatsappBinding.requestId ?? `wa-bind-${session.accountId}`,
      phoneNumber: null,
      requestedAt: nowIso(),
      startCount: (draft.whatsappBinding.startCount ?? 0) + 1,
      lastUpdatedAt: nowIso()
    };
    appendLocalizedMessage(draft, "system", "whatsappOpenedTitle", "whatsappOpenedBody");
    return draft;
  });
  return state.whatsappBinding;
}
export async function getMemberSupportContext() {
  const session = getRequiredSession();
  return {
    accountId: session.accountId,
    publicUserId: session.publicUserId
  };
}
export async function getMaskedPhone() {
  const session = getRequiredSession();
  return maskPhone(session.phone);
}
export async function loginApi(phone, password, siteKey) {
  if (apiMode === "real") {
    const res = await h5Api.post("/api/h5/auth/login", {
      phone,
      password,
      siteKey: siteKey || "mall-cn"
    });
    sessionManager.setSession(res.data.access_token, res.data.refresh_token, res.data.expires_in);
    return res.data;
  }
  const profile = await loginMember({ siteKey: siteKey || "mall-cn", phone, password });
  const user = {
    accountId: profile.accountId,
    phone: profile.phone,
    publicUserId: profile.publicUserId,
    displayName: profile.displayName,
    inviteCode: profile.inviteCode,
    avatarUrl: profile.avatarUrl ?? null
  };
  const fakeToken = `mock-at-${Date.now()}`;
  const fakeRefresh = `mock-rt-${Date.now()}`;
  sessionManager.setSession(fakeToken, fakeRefresh, 7200);
  sessionManager.setUserInfo({
    accountId: user.accountId,
    phone: user.phone,
    publicUserId: user.publicUserId,
    displayName: user.displayName,
    inviteCode: user.inviteCode,
    avatarUrl: user.avatarUrl
  });
  return { access_token: fakeToken, refresh_token: fakeRefresh, expires_in: 7200, user };
}
export async function registerApi(payload) {
  if (apiMode === "real") {
    const res = await h5Api.post("/api/h5/auth/register", payload);
    sessionManager.setSession(res.data.access_token, res.data.refresh_token, res.data.expires_in);
    return res.data;
  }
  const profile = await registerMember(payload);
  const user = {
    accountId: profile.accountId,
    phone: profile.phone,
    publicUserId: profile.publicUserId,
    displayName: profile.displayName,
    inviteCode: profile.inviteCode,
    avatarUrl: profile.avatarUrl ?? null
  };
  const fakeToken = `mock-at-${Date.now()}`;
  const fakeRefresh = `mock-rt-${Date.now()}`;
  sessionManager.setSession(fakeToken, fakeRefresh, 7200);
  sessionManager.setUserInfo({
    accountId: user.accountId,
    phone: user.phone,
    publicUserId: user.publicUserId,
    displayName: user.displayName,
    inviteCode: user.inviteCode,
    avatarUrl: user.avatarUrl
  });
  return { access_token: fakeToken, refresh_token: fakeRefresh, expires_in: 7200, user };
}
export async function refreshTokenApi() {
  if (apiMode === "real") {
    const refreshToken = sessionManager.getRefreshToken();
    const res = await h5Api.post("/api/h5/auth/refresh", {
      refresh_token: refreshToken
    });
    sessionManager.setSession(res.data.access_token, res.data.refresh_token, res.data.expires_in);
    return res.data;
  }
  const success = await refreshBackendAuthSession();
  if (!success) {
    throw new Error("Token refresh failed");
  }
  return {
    access_token: sessionManager.getAccessToken() ?? "",
    refresh_token: sessionManager.getRefreshToken() ?? "",
    expires_in: 7200
  };
}
export async function logoutApi() {
  if (apiMode === "real") {
    await h5Api.post("/api/h5/auth/logout");
    sessionManager.clearSession();
    return;
  }
  await logoutMember();
  sessionManager.clearSession();
}
export async function getUserInfoApi() {
  if (apiMode === "real") {
    const res = await h5Api.get("/api/h5/auth/me");
    const profile = buildProfileFromAuthPayload({
      member: res.data.member,
      site: res.data.site
    });
    syncLegacyMemberCacheFromProfile(profile);
    return profile;
  }
  return getCurrentMemberProfile();
}
export async function updateProfileApi(payload) {
  if (apiMode === "real") {
    const res = await h5Api.put("/api/h5/profile", payload);
    return res.data;
  }
  return updateMemberProfile(payload);
}
export async function updateAvatarApi(file) {
  if (apiMode === "real") {
    const formData = new FormData();
    formData.append("file", file);
    const res = await h5Api.post("/api/h5/profile/avatar", formData, {
      headers: { "Content-Type": "multipart/form-data" }
    });
    return res.data;
  }
  const session = getRequiredSession();
  const fakeUrl = URL.createObjectURL(file);
  const accounts = readMemberAccounts();
  writeMemberAccounts(
    accounts.map(
      (item) => item.accountId === session.accountId ? { ...item, avatarUrl: fakeUrl } : item
    )
  );
  const nextSession = { ...session, avatarUrl: fakeUrl };
  writeSession(nextSession);
  return { avatarUrl: fakeUrl };
}
export async function changePasswordApi(payload) {
  if (apiMode === "real") {
    await h5Api.put("/api/h5/profile/password", payload);
    return;
  }
  return updateMemberPassword(payload);
}
export async function getTaskPackagesApi(params) {
  if (apiMode === "real") {
    const res = await h5Api.get("/api/h5/tasks", { params });
    return res.data.items ?? res.data;
  }
  return listTaskPackages();
}
export async function getTaskPackageDetailApi(id) {
  if (apiMode === "real") {
    const res = await h5Api.get(`/api/h5/tasks/${encodeURIComponent(id)}`);
    return res.data;
  }
  try {
    return await getTaskPackageDetail(id);
  } catch {
    return null;
  }
}
export async function submitTaskApi(id, data) {
  if (apiMode === "real") {
    await h5Api.post(`/api/h5/tasks/${encodeURIComponent(id)}/submit`, data);
    return true;
  }
  return true;
}
export async function uploadTaskProofApi(id, file, onProgress) {
  if (apiMode === "real") {
    const form = new FormData();
    form.append("file", file);
    const res = await h5Api.post(`/api/h5/tasks/${encodeURIComponent(id)}/proof`, form, {
      headers: { "Content-Type": "multipart/form-data" },
      onUploadProgress: (e) => {
        if (e.total) onProgress?.(Math.round(e.loaded / e.total * 100));
      }
    });
    return res.data.url ?? res.data;
  }
  return URL.createObjectURL(file);
}
export async function getWalletBalanceApi() {
  if (apiMode === "real") {
    const res = await h5Api.get(H5_API_ENDPOINTS.wallet.balance);
    return res.data;
  }
  const session = getRequiredSession();
  const state = getStateForAccount(session.accountId);
  return getWalletSummaryFromState(state);
}
export async function getWalletTransactionsApi(params) {
  if (apiMode === "real") {
    const res = await h5Api.get(H5_API_ENDPOINTS.wallet.transactions, { params });
    return res.data;
  }
  const session = getRequiredSession();
  const state = getStateForAccount(session.accountId);
  const allTransactions = [...state.transactions].sort(
    (left, right) => right.createdAt.localeCompare(left.createdAt)
  );
  const filtered = params.type ? allTransactions.filter((item) => item.transactionType === params.type) : allTransactions;
  const size = params.size ?? 20;
  const start = (params.page - 1) * size;
  return {
    items: filtered.slice(start, start + size),
    total: filtered.length
  };
}
export async function rechargeApi(amount, channel) {
  if (apiMode === "real") {
    const res = await h5Api.post(H5_API_ENDPOINTS.wallet.recharge, { amount, channel });
    return res.data;
  }
  await createRechargeOrder(amount);
  return { id: `mock_recharge_${Date.now()}`, status: "completed" };
}
export async function getRechargeStatusApi(id) {
  if (apiMode === "real") {
    const res = await h5Api.get(H5_API_ENDPOINTS.wallet.rechargeStatus(id));
    return res.data.status;
  }
  return "completed";
}
export async function getNotificationsCountApi() {
  if (apiMode === "real") {
    const res = await h5Api.get(H5_API_ENDPOINTS.notificationsUnreadCount);
    return res.data;
  }
  const session = getRequiredSession();
  const state = getStateForAccount(session.accountId);
  return { unreadCount: getUnreadMessageCount(state.messages) };
}
export async function getWithdrawalsApi(params) {
  if (apiMode === "real") {
    const res = await h5Api.get(H5_API_ENDPOINTS.withdrawals.list, { params });
    return res.data;
  }
  const session = getRequiredSession();
  const state = getStateForAccount(session.accountId);
  const requests = [...state.withdrawRequests].sort(
    (left, right) => right.createdAt.localeCompare(left.createdAt)
  );
  const page = params.page ?? 1;
  const size = params.size ?? 20;
  return { items: requests.slice((page - 1) * size, page * size), total: requests.length };
}
export async function submitWithdrawApi(amount, accountInfo) {
  if (apiMode === "real") {
    const res = await h5Api.post(H5_API_ENDPOINTS.withdrawals.list, { amount, account_info: accountInfo });
    return res.data;
  }
  await createWithdrawRequest(amount);
  return { id: `mock-${Date.now()}`, status: "submitted" };
}
export async function getWithdrawDetailApi(id) {
  if (apiMode === "real") {
    const res = await h5Api.get(H5_API_ENDPOINTS.withdrawals.detail(id));
    return res.data;
  }
  const session = getRequiredSession();
  const state = getStateForAccount(session.accountId);
  return state.withdrawRequests.find((r) => r.id === id) ?? null;
}
function getMockVerificationStatus() {
  const raw = isBrowser() ? window.localStorage.getItem("mock_verification_status") : null;
  if (raw) {
    try {
      return JSON.parse(raw);
    } catch {
    }
  }
  return { status: "unverified" };
}
function getMockWhatsAppBindingStatus() {
  const raw = isBrowser() ? window.localStorage.getItem("mock_whatsapp_binding") : null;
  if (raw) {
    try {
      return JSON.parse(raw);
    } catch {
    }
  }
  return { status: "not_bound" };
}
export async function getVerificationStatusApi() {
  if (apiMode === "real") {
    const res = await h5Api.get("/api/h5/verifications/status");
    return res.data;
  }
  return getMockVerificationStatus();
}
export async function submitVerificationApi(data) {
  if (apiMode === "real") {
    const res = await h5Api.post("/api/h5/verifications", data);
    return res.data;
  }
  const mockId = `mock-${Date.now()}`;
  if (isBrowser()) {
    window.localStorage.setItem(
      "mock_verification_status",
      JSON.stringify({ status: "pending", name: data.name, idNumber: data.idNumber, photos: data.photos, submittedAt: nowIso() })
    );
  }
  return { id: mockId, status: "pending" };
}
export async function uploadVerificationPhotosApi(id, files) {
  if (apiMode === "real") {
    const form = new FormData();
    files.forEach((f) => form.append("photos", f));
    await h5Api.post(`/api/h5/verifications/${id}/photos`, form, {
      headers: { "Content-Type": "multipart/form-data" }
    });
    return true;
  }
  return true;
}
export async function getWhatsAppBindingStatusApi() {
  if (apiMode === "real") {
    const res = await h5Api.get("/api/h5/whatsapp-bindings/status");
    return res.data;
  }
  return getMockWhatsAppBindingStatus();
}
export async function startWhatsAppBindingApi(phone) {
  if (apiMode === "real") {
    const res = await h5Api.post("/api/h5/whatsapp-bindings", { phone });
    return res.data;
  }
  const mockId = `mock-${Date.now()}`;
  if (isBrowser()) {
    window.localStorage.setItem(
      "mock_whatsapp_binding",
      JSON.stringify({ status: "pending", phone, requestedAt: nowIso(), id: mockId })
    );
  }
  return { id: mockId, status: "pending" };
}
function getMessages() {
  const session = getRequiredSession();
  const state = getStateForAccount(session.accountId);
  return [...state.messages].sort((left, right) => right.createdAt.localeCompare(left.createdAt));
}
const mockTicketsStore = [];
function getSupportTickets() {
  return [...mockTicketsStore];
}
function getSupportTicketById(id) {
  return mockTicketsStore.find((t2) => t2.id === id) ?? null;
}
function addTicketReply(ticketId, message) {
  const ticket = mockTicketsStore.find((t2) => t2.id === ticketId);
  if (!ticket) return false;
  ticket.messages.push({
    id: "msg-" + Date.now(),
    sender_type: "user",
    sender_name: "user",
    content: message,
    created_at: (/* @__PURE__ */ new Date()).toISOString(),
    internal_only: false
  });
  ticket.last_reply_at = (/* @__PURE__ */ new Date()).toISOString();
  ticket.updated_at = (/* @__PURE__ */ new Date()).toISOString();
  return true;
}
export async function getNotificationsApi(params) {
  if (apiMode === "real") {
    const res = await h5Api.get("/api/h5/notifications", { params });
    return res.data;
  }
  const msgs = getMessages();
  const page = params.page ?? 1;
  const size = params.size ?? 20;
  return { items: msgs.slice((page - 1) * size, page * size), total: msgs.length };
}
export async function markNotificationReadApi(id) {
  if (apiMode === "real") {
    await h5Api.put("/api/h5/notifications/" + encodeURIComponent(id) + "/read");
    return true;
  }
  return markMessageRead(id);
}
export async function markAllNotificationsReadApi() {
  if (apiMode === "real") {
    await h5Api.put("/api/h5/notifications/read-all");
    return true;
  }
  return markAllMessagesRead();
}
export async function getTicketsApi(params) {
  if (apiMode === "real") {
    const res = await h5Api.get("/api/h5/tickets", { params });
    return res.data;
  }
  const tickets = getSupportTickets();
  const page = params.page ?? 1;
  const size = params.size ?? 20;
  return { items: tickets.slice((page - 1) * size, page * size), total: tickets.length };
}
export async function createTicketApi(data) {
  if (apiMode === "real") {
    const res = await h5Api.post("/api/h5/tickets", data);
    return res.data;
  }
  const now = (/* @__PURE__ */ new Date()).toISOString();
  const id = "mock-" + Date.now();
  mockTicketsStore.unshift({
    id,
    category: data.category,
    priority: data.priority,
    subject: data.subject,
    description: data.description,
    status: "open",
    created_at: now,
    updated_at: now,
    last_reply_at: now,
    messages: [{
      id: id + "-msg-0",
      sender_type: "user",
      sender_name: "user",
      content: data.description,
      created_at: now,
      internal_only: false
    }]
  });
  return { id };
}
export async function getTicketDetailApi(id) {
  if (apiMode === "real") {
    const res = await h5Api.get("/api/h5/tickets/" + encodeURIComponent(id));
    return res.data;
  }
  return getSupportTicketById(id);
}
export async function replyToTicketApi(ticketId, message) {
  if (apiMode === "real") {
    await h5Api.post("/api/h5/tickets/" + encodeURIComponent(ticketId) + "/messages", { message });
    return true;
  }
  return addTicketReply(ticketId, message);
}
function getMockLeaderboard() {
  return {
    rankings: [
      { rank: 1, userId: "12864472", score: 5200 },
      { rank: 2, userId: "87342155", score: 4760 },
      { rank: 3, userId: "54021863", score: 3980 },
      { rank: 4, userId: "74190538", score: 3510 }
    ]
  };
}
export async function getLeaderboardApi() {
  if (apiMode === "real") {
    const res = await h5Api.get("/api/h5/leaderboard");
    return res.data;
  }
  return getMockLeaderboard();
}
export async function getPromotionsApi() {
  if (apiMode === "real") {
    const res = await h5Api.get("/api/h5/promotions");
    return res.data;
  }
  return { items: [] };
}
export async function joinPromotionApi(id) {
  if (apiMode === "real") {
    const res = await h5Api.post(`/api/h5/promotions/${id}/join`);
    return res.data;
  }
  return { success: true };
}
function getMockOrders(params) {
  const session = getRequiredSession();
  const state = getStateForAccount(session.accountId);
  let filtered = state.orders;
  if (params.status && params.status !== "all") {
    filtered = filtered.filter((o) => o.status === params.status);
  }
  const page = params.page ?? 1;
  const size = params.size ?? 20;
  const sorted = [...filtered].sort((a, b) => b.createdAt.localeCompare(a.createdAt));
  return { items: sorted.slice((page - 1) * size, page * size), total: sorted.length };
}
export async function getProductsApi() {
  if (apiMode === "real") {
    const res = await h5Api.get("/api/h5/commerce/products");
    return res.data.items ?? res.data;
  }
  return [];
}
export async function getProductDetailApi(id) {
  if (apiMode === "real") {
    const res = await h5Api.get(`/api/h5/commerce/products/${id}`);
    return res.data;
  }
  return null;
}
export async function createOrderApi(productId, quantity) {
  if (apiMode === "real") {
    const res = await h5Api.post("/api/h5/commerce/orders", { product_id: productId, quantity });
    return res.data;
  }
  return { id: `mock-${Date.now()}` };
}
export async function getOrdersApi(params) {
  if (apiMode === "real") {
    const res = await h5Api.get("/api/h5/commerce/orders", { params });
    return res.data;
  }
  return getMockOrders(params);
}
export async function getOrderDetailApi(id) {
  if (apiMode === "real") {
    const res = await h5Api.get(`/api/h5/commerce/orders/${id}`);
    return res.data;
  }
  return null;
}
export async function getLogisticsApi(orderId) {
  if (apiMode === "real") {
    const res = await h5Api.get(`/api/h5/commerce/orders/${orderId}/logistics`);
    return res.data;
  }
  return { status: "pending", steps: [] };
}
function getMockFragments() {
  const session = getRequiredSession();
  const state = getStateForAccount(session.accountId);
  const overview = buildFragmentOverview(state);
  return {
    items: overview.inventory,
    overview
  };
}
export async function getFragmentsApi() {
  if (apiMode === "real") {
    const res = await h5Api.get("/api/h5/fragments");
    return res.data;
  }
  return getMockFragments();
}
export async function getFragmentDetailApi(id) {
  if (apiMode === "real") {
    const res = await h5Api.get("/api/h5/fragments/" + encodeURIComponent(id));
    return res.data;
  }
  return null;
}
export async function checkInFragmentApi() {
  if (apiMode === "real") {
    const res = await h5Api.post("/api/h5/fragments/check-in");
    return res.data;
  }
  return { success: true, fragment: { id: "mock-" + Date.now() } };
}
export async function exchangeFragmentsApi(data) {
  if (apiMode === "real") {
    const res = await h5Api.post("/api/h5/fragments/exchanges", data);
    return res.data;
  }
  return { id: "mock-" + Date.now(), status: "submitted" };
}
export async function getShippingStatusApi(exchangeId) {
  if (apiMode === "real") {
    const res = await h5Api.get("/api/h5/rewards/shipping/" + encodeURIComponent(exchangeId));
    return res.data;
  }
  return { status: "pending" };
}
export async function subscribeMailingApi(email) {
  if (apiMode === "real") {
    await h5Api.post("/api/h5/mailing/subscribe", { email });
    return true;
  }
  return true;
}
export async function unsubscribeMailingApi(email) {
  if (apiMode === "real") {
    await h5Api.post("/api/h5/mailing/unsubscribe", { email });
    return true;
  }
  return true;
}
export const H5_API_ENDPOINTS = {
  wallet: {
    balance: "/api/h5/wallet/balance",
    transactions: "/api/h5/wallet/transactions",
    recharge: "/api/h5/wallet/recharge",
    rechargeStatus: (id) => `/api/h5/wallet/recharge/${id}/status`
  },
  withdrawals: {
    list: "/api/h5/withdrawals",
    detail: (id) => `/api/h5/withdrawals/${id}`
  },
  tasks: {
    list: "/api/h5/tasks",
    detail: (id) => `/api/h5/tasks/${id}`,
    submit: (id) => `/api/h5/tasks/${id}/submit`,
    proof: (id) => `/api/h5/tasks/${id}/proof`
  },
  notifications: "/api/h5/notifications",
  notificationsUnreadCount: "/api/h5/notifications?unread=true&count_only=true",
  tickets: {
    list: "/api/h5/tickets",
    detail: (id) => `/api/h5/tickets/${id}`
  },
  verifications: {
    list: "/api/h5/verifications",
    photos: (id) => `/api/h5/verifications/${id}/photos`
  },
  whatsappBindings: "/api/h5/whatsapp-bindings",
  commerce: {
    products: "/api/h5/commerce/products",
    orders: "/api/h5/commerce/orders"
  },
  fragments: "/api/h5/fragments",
  promotions: "/api/h5/promotions",
  leaderboard: "/api/h5/leaderboard"
};
export async function getMessagesApi(params) {
  if (apiMode === "real") {
    const res = await h5Api.get("/api/h5/messages", { params });
    return res.data;
  }
  const mockMsgs = [
    { id: "m1", content: getSeedDataText("chatWelcomeInbound"), type: "text", direction: "inbound", status: "read", timestamp: new Date(Date.now() - 36e5).toISOString() },
    { id: "m2", content: getSeedDataText("chatWelcomeOutbound"), type: "text", direction: "outbound", status: "read", timestamp: new Date(Date.now() - 35e5).toISOString() },
    { id: "m3", content: getSeedDataText("chatWelcomeReply"), type: "text", direction: "inbound", status: "read", timestamp: new Date(Date.now() - 34e5).toISOString() }
  ];
  const page = params.page ?? 1;
  const size = params.size ?? 20;
  return { items: mockMsgs.slice((page - 1) * size, page * size), total: mockMsgs.length };
}
export async function sendMessageApi(conversationId, content, type = "text") {
  if (apiMode === "real") {
    const res = await h5Api.post("/api/h5/messages", { conversation_id: conversationId, content, type });
    return res.data;
  }
  return {
    id: `mock-${Date.now()}`,
    content,
    type,
    direction: "outbound",
    status: "sent",
    timestamp: (/* @__PURE__ */ new Date()).toISOString()
  };
}
const SIGN_IN_GOAL_DAYS = 7;
const SIGN_IN_GOAL_REWARD = 5;
function getMockSignInStatus() {
  const session = getRequiredSession();
  const state = getStateForAccount(session.accountId);
  const checked = state.checkedInDate === todayKey();
  const consecutiveDays = checked ? 5 : 3;
  return {
    consecutiveDays,
    todaySignedIn: checked,
    goalDays: SIGN_IN_GOAL_DAYS,
    goalReward: SIGN_IN_GOAL_REWARD,
    isCompleted: consecutiveDays >= SIGN_IN_GOAL_DAYS
  };
}
function getMockTaskInstances() {
  const session = getRequiredSession();
  const state = getStateForAccount(session.accountId);
  const packages = state.taskPackages.filter(
    (p) => p.status === "pending_claim" || p.status === "active" || p.status === "completed" || p.status === "expired"
  );
  return packages.map((pkg) => {
    const completedCount = pkg.items.filter((i) => i.completed_at).length;
    const totalCount = pkg.items.length;
    const totalCommission = pkg.items.reduce((sum, item) => sum + item.price * pkg.rewardRatio, 0);
    const currentCommission = pkg.items.filter((item) => Boolean(item.completed_at)).reduce((sum, item) => sum + item.price * pkg.rewardRatio, 0);
    const countdownSeconds = pkg.status === "pending_claim" ? pkg.completionWindowHours * 3600 : pkg.expiresAt ? Math.max(0, Math.floor((new Date(pkg.expiresAt).getTime() - Date.now()) / 1e3)) : 0;
    const products = pkg.items.map((item, idx) => {
      let status = "pending";
      if (pkg.status === "pending_claim") {
        status = "pending";
      } else if (item.completed_at) {
        status = "completed";
      } else if (idx === 0 || pkg.items[idx - 1]?.completed_at) {
        status = "available";
      }
      return {
        id: item.id,
        productName: item.product_name,
        imageUrl: item.image_url,
        price: item.price,
        currency: item.currency,
        status
      };
    });
    return {
      id: pkg.id,
      title: pkg.title,
      description: pkg.description,
      type: pkg.type,
      status: pkg.status,
      rewardRatio: pkg.rewardRatio,
      rewardAmount: totalCommission,
      products,
      completedCount,
      totalCount,
      systemBalance: state.wallet.systemBalance,
      totalCommission,
      currentCommission,
      countdownSeconds,
      completionWindowHours: pkg.completionWindowHours
    };
  });
}
function getMockTaskInstanceDetail(instanceId) {
  const instances = getMockTaskInstances();
  return instances.find((i) => i.id === instanceId) ?? null;
}
function getMockInviteLink() {
  const session = getRequiredSession();
  const origin = typeof window !== "undefined" ? window.location.origin : "http://127.0.0.1:5173";
  const url = new URL("/h5/register", origin);
  url.searchParams.set("invite_code", session.inviteCode);
  return url.toString();
}
function getMockInviteInfo() {
  const link = getMockInviteLink();
  return {
    inviteLink: link,
    invitedCount: 8,
    earnedAmount: 31,
    maxInvites: 20,
    remainingInvites: 12
  };
}
function getMockInviteRecords() {
  return [
    { id: "inv1", userIdMasked: "U****91", type: "registration", createdAt: "2026-06-10T09:16:00.000Z", rewardAmount: 2 },
    { id: "inv2", userIdMasked: "U****52", type: "registration_recharge", createdAt: "2026-06-08T10:42:00.000Z", rewardAmount: 5 },
    { id: "inv3", userIdMasked: "U****73", type: "registration", createdAt: "2026-06-05T12:08:00.000Z", rewardAmount: 2 },
    { id: "inv4", userIdMasked: "U****34", type: "registration", createdAt: "2026-06-03T14:30:00.000Z", rewardAmount: 2 },
    { id: "inv5", userIdMasked: "U****25", type: "registration_recharge", createdAt: "2026-06-01T08:00:00.000Z", rewardAmount: 5 }
  ];
}
export async function getSignInStatusApi() {
  if (apiMode === "real") {
    const res = await h5Api.get("/api/h5/sign-in/status");
    return res.data;
  }
  return getMockSignInStatus();
}
export async function performSignInApi() {
  if (apiMode === "real") {
    const res = await h5Api.post("/api/h5/sign-in");
    return res.data;
  }
  const session = getRequiredSession();
  const state = updateStateForAccount(session.accountId, (draft) => {
    if (draft.checkedInDate === todayKey()) {
      throw createServiceError("alreadyCheckedIn");
    }
    draft.checkedInDate = todayKey();
    appendLocalizedMessage(draft, "system", "checkinTitle", "checkinBody");
    return draft;
  });
  return {
    consecutiveDays: 5,
    todaySignedIn: true,
    goalDays: SIGN_IN_GOAL_DAYS,
    goalReward: SIGN_IN_GOAL_REWARD,
    isCompleted: false
  };
}
export async function getTaskInstancesApi() {
  if (apiMode === "real") {
    const res = await h5Api.get("/api/h5/task-instances", { params: { user_id: "me" } });
    return res.data;
  }
  return getMockTaskInstances();
}
export async function getTaskInstanceDetailApi(id) {
  if (apiMode === "real") {
    const res = await h5Api.get(`/api/h5/task-instances/${encodeURIComponent(id)}`);
    return res.data;
  }
  return getMockTaskInstanceDetail(id);
}
export async function startProductApi(instanceId, productId) {
  if (apiMode === "real") {
    const res = await h5Api.post(`/api/h5/task-instances/${encodeURIComponent(instanceId)}/start-product`, { product_id: productId });
    return res.data;
  }
  const session = getRequiredSession();
  updateStateForAccount(session.accountId, (draft) => {
    const pkg = draft.taskPackages.find((p) => p.id === instanceId);
    if (!pkg) return draft;
    const item = pkg.items.find((i) => i.id === productId);
    if (!item) return draft;
    if (draft.wallet.systemBalance < item.price) {
      throw createServiceError("balanceInsufficient");
    }
    draft.wallet.systemBalance -= item.price;
    item.completed_at = (/* @__PURE__ */ new Date()).toISOString();
    return draft;
  });
  return { success: true };
}
export async function retryProductApi(instanceId, productId) {
  if (apiMode === "real") {
    const res = await h5Api.post(`/api/h5/task-instances/${encodeURIComponent(instanceId)}/retry-product`, { product_id: productId });
    return res.data;
  }
  return startProductApi(instanceId, productId);
}
export async function getInviteInfoApi() {
  if (apiMode === "real") {
    const res = await h5Api.get("/api/h5/invites/my-link");
    return res.data;
  }
  return getMockInviteInfo();
}
export async function getInviteRecordsApi() {
  if (apiMode === "real") {
    const res = await h5Api.get("/api/h5/invites/my-records");
    return res.data;
  }
  return getMockInviteRecords();
}
const requestCache = /* @__PURE__ */ new Map();
const REQUEST_DEDUP_TTL = 5e3;
async function dedupRequest(key, fetcher) {
  const cached = requestCache.get(key);
  if (cached && Date.now() - cached.timestamp < REQUEST_DEDUP_TTL) {
    return cached.promise;
  }
  const promise = fetcher();
  requestCache.set(key, { promise, timestamp: Date.now() });
  promise.finally(() => {
    setTimeout(() => {
      if (requestCache.get(key)?.promise === promise) {
        requestCache.delete(key);
      }
    }, REQUEST_DEDUP_TTL);
  });
  return promise;
}

//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJzb3VyY2VzIjpbImg1TWVtYmVyLnRzIl0sInNvdXJjZXNDb250ZW50IjpbImltcG9ydCBheGlvcywgeyBBeGlvc0Vycm9yLCBBeGlvc1Jlc3BvbnNlLCBJbnRlcm5hbEF4aW9zUmVxdWVzdENvbmZpZyB9IGZyb20gXCJheGlvc1wiO1xyXG5pbXBvcnQgeyB0IH0gZnJvbSBcIi4uL3BhZ2VzL2g1LW1lbWJlci9pMThuXCI7XHJcbmltcG9ydCB7IHNlc3Npb25NYW5hZ2VyIH0gZnJvbSBcIi4vaDVTZXNzaW9uTWFuYWdlclwiO1xyXG5cclxudHlwZSBKc29uT2JqZWN0ID0gUmVjb3JkPHN0cmluZywgdW5rbm93bj47XHJcbmV4cG9ydCB0eXBlIEg1VGFza1BhY2thZ2VTdGF0dXMgPSBcInBlbmRpbmdfY2xhaW1cIiB8IFwiYWN0aXZlXCIgfCBcImNvbXBsZXRlZFwiIHwgXCJleHBpcmVkXCI7XHJcbmV4cG9ydCB0eXBlIEg1VGFza1BhY2thZ2VUeXBlID0gXCJyb29raWVcIiB8IFwiZ3Jvd3RoXCIgfCBcInByb21vdGlvblwiO1xyXG5leHBvcnQgdHlwZSBINVByb21vdGlvbk1ldHJpYyA9IFwiaW52aXRlZF9yZWdpc3RyYXRpb25zXCIgfCBcInJlY2hhcmdlZF9pbnZpdGVlc1wiO1xyXG5leHBvcnQgdHlwZSBINVdpdGhkcmF3U3RhdHVzID0gXCJzdWJtaXR0ZWRcIiB8IFwicmV2aWV3aW5nXCIgfCBcImFwcHJvdmVkXCIgfCBcInJlamVjdGVkXCIgfCBcInBhaWRcIjtcclxuZXhwb3J0IHR5cGUgSDVSZXdhcmRTaGlwcGluZ1N0YXR1cyA9XHJcbiAgfCBcInBlbmRpbmdfYWRkcmVzc1wiXHJcbiAgfCBcInN1Ym1pdHRlZFwiXHJcbiAgfCBcInBhY2tpbmdcIlxyXG4gIHwgXCJzaGlwcGVkXCJcclxuICB8IFwiZGVsaXZlcmVkXCJcclxuICB8IFwiY29tcGxldGVkXCI7XHJcbmV4cG9ydCB0eXBlIEg1V2FsbGV0VHJhbnNhY3Rpb25UeXBlID1cclxuICB8IFwicmVjaGFyZ2VcIlxyXG4gIHwgXCJwdXJjaGFzZVwiXHJcbiAgfCBcInRhc2tfcmV3YXJkXCJcclxuICB8IFwidGFza190b19zeXN0ZW1fdHJhbnNmZXJcIlxyXG4gIHwgXCJ3aXRoZHJhd19yZXF1ZXN0XCJcclxuICB8IFwid2l0aGRyYXdfcGFpZFwiXHJcbiAgfCBcIndpdGhkcmF3X3JlamVjdGVkXCI7XHJcbmV4cG9ydCB0eXBlIEg1TWVzc2FnZUNhdGVnb3J5ID0gXCJ0YXNrXCIgfCBcIndhbGxldFwiIHwgXCJvcmRlclwiIHwgXCJzdXBwb3J0XCIgfCBcImZyYWdtZW50XCIgfCBcInN5c3RlbVwiO1xyXG5cclxuZXhwb3J0IHR5cGUgSDVTaXRlQnJhbmQgPSB7XHJcbiAgc2l0ZV9rZXk6IHN0cmluZztcclxuICBicmFuZF9uYW1lOiBzdHJpbmc7XHJcbiAgdGFnbGluZTogc3RyaW5nO1xyXG4gIGFjY2VudF9jb2xvcjogc3RyaW5nO1xyXG59O1xyXG5cclxuZXhwb3J0IHR5cGUgSDVNZW1iZXJTZXNzaW9uID0ge1xyXG4gIGFjY291bnRJZDogc3RyaW5nO1xyXG4gIHBob25lOiBzdHJpbmc7XHJcbiAgcHVibGljVXNlcklkOiBzdHJpbmc7XHJcbiAgZGlzcGxheU5hbWU6IHN0cmluZztcclxuICBpbnZpdGVDb2RlOiBzdHJpbmc7XHJcbiAgYXZhdGFyVXJsPzogc3RyaW5nIHwgbnVsbDtcclxufTtcclxuXHJcbmV4cG9ydCB0eXBlIEg1TWVtYmVyUHJvZmlsZSA9IEg1TWVtYmVyU2Vzc2lvbiAmIHtcclxuICBhY2NvdW50SWRNYXNrZWQ6IHN0cmluZztcclxuICBjcmVhdGVkQXQ6IHN0cmluZztcclxufTtcclxuXHJcbmV4cG9ydCB0eXBlIEg1VGFza1BhY2thZ2VJdGVtID0ge1xyXG4gIGlkOiBzdHJpbmc7XHJcbiAgcHJvZHVjdF9uYW1lOiBzdHJpbmc7XHJcbiAgaW1hZ2VfdXJsOiBzdHJpbmc7XHJcbiAgcHJpY2U6IG51bWJlcjtcclxuICBjdXJyZW5jeTogc3RyaW5nO1xyXG4gIGNvbXBsZXRlZF9hdDogc3RyaW5nIHwgbnVsbDtcclxuICBvcmRlcl9pZDogc3RyaW5nIHwgbnVsbDtcclxufTtcclxuXHJcbmV4cG9ydCB0eXBlIEg1UHJvbW90aW9uUHJvZ3Jlc3MgPSB7XHJcbiAgbWV0cmljOiBINVByb21vdGlvbk1ldHJpYztcclxuICBjdXJyZW50OiBudW1iZXI7XHJcbiAgdGFyZ2V0OiBudW1iZXI7XHJcbiAgaW52aXRlQ29kZTogc3RyaW5nO1xyXG59O1xyXG5cclxuZXhwb3J0IHR5cGUgSDVUYXNrUGFja2FnZSA9IHtcclxuICBpZDogc3RyaW5nO1xyXG4gIHRpdGxlOiBzdHJpbmc7XHJcbiAgZGVzY3JpcHRpb246IHN0cmluZztcclxuICB0eXBlOiBINVRhc2tQYWNrYWdlVHlwZTtcclxuICBzdGF0dXM6IEg1VGFza1BhY2thZ2VTdGF0dXM7XHJcbiAgcmV3YXJkUmF0aW86IG51bWJlcjtcclxuICBjbGFpbWVkQXQ6IHN0cmluZyB8IG51bGw7XHJcbiAgZXhwaXJlc0F0OiBzdHJpbmcgfCBudWxsO1xyXG4gIGRpc3BhdGNoZWRBdDogc3RyaW5nO1xyXG4gIGNvbXBsZXRpb25XaW5kb3dIb3VyczogbnVtYmVyO1xyXG4gIGl0ZW1zOiBINVRhc2tQYWNrYWdlSXRlbVtdO1xyXG4gIHByb21vdGlvbjogSDVQcm9tb3Rpb25Qcm9ncmVzcyB8IG51bGw7XHJcbiAgdGFza0JhbGFuY2VBd2FyZGVkQXQ6IHN0cmluZyB8IG51bGw7XHJcbn07XHJcblxyXG5leHBvcnQgdHlwZSBINU1lbWJlck9yZGVyID0ge1xyXG4gIGlkOiBzdHJpbmc7XHJcbiAgb3JkZXJObzogc3RyaW5nO1xyXG4gIHBhY2thZ2VJZDogc3RyaW5nO1xyXG4gIHBhY2thZ2VUaXRsZTogc3RyaW5nO1xyXG4gIHByb2R1Y3ROYW1lOiBzdHJpbmc7XHJcbiAgYW1vdW50OiBudW1iZXI7XHJcbiAgY3VycmVuY3k6IHN0cmluZztcclxuICBzdGF0dXM6IFwicGFpZFwiIHwgXCJmYWlsZWRcIiB8IFwicHJvY2Vzc2luZ1wiIHwgXCJwZW5kaW5nXCI7XHJcbiAgY3JlYXRlZEF0OiBzdHJpbmc7XHJcbiAgc291cmNlTGFiZWw6IHN0cmluZztcclxufTtcclxuXHJcbmV4cG9ydCB0eXBlIEg1V2FsbGV0VHJhbnNhY3Rpb24gPSB7XHJcbiAgaWQ6IHN0cmluZztcclxuICBsZWRnZXJUeXBlOiBcInN5c3RlbVwiIHwgXCJ0YXNrXCI7XHJcbiAgdHJhbnNhY3Rpb25UeXBlOiBINVdhbGxldFRyYW5zYWN0aW9uVHlwZTtcclxuICBkaXJlY3Rpb246IFwiY3JlZGl0XCIgfCBcImRlYml0XCI7XHJcbiAgYW1vdW50OiBudW1iZXI7XHJcbiAgY3VycmVuY3k6IHN0cmluZztcclxuICBzdGF0dXM6IFwic3VibWl0dGVkXCIgfCBcInByb2Nlc3NpbmdcIiB8IFwicGFpZFwiIHwgXCJmYWlsZWRcIjtcclxuICBub3RlOiBzdHJpbmc7XHJcbiAgY3JlYXRlZEF0OiBzdHJpbmc7XHJcbn07XHJcblxyXG5leHBvcnQgdHlwZSBINVdhbGxldFN1bW1hcnkgPSB7XHJcbiAgc3lzdGVtQmFsYW5jZTogbnVtYmVyO1xyXG4gIHRhc2tCYWxhbmNlOiBudW1iZXI7XHJcbiAgY3VycmVuY3k6IHN0cmluZztcclxuICB3aXRoZHJhd1RocmVzaG9sZDogbnVtYmVyO1xyXG4gIGNhbldpdGhkcmF3OiBib29sZWFuO1xyXG4gIHNob3J0ZmFsbEFtb3VudDogbnVtYmVyO1xyXG59O1xyXG5cclxuZXhwb3J0IHR5cGUgSDVXaXRoZHJhd1JlcXVlc3QgPSB7XHJcbiAgaWQ6IHN0cmluZztcclxuICBhbW91bnQ6IG51bWJlcjtcclxuICBjdXJyZW5jeTogc3RyaW5nO1xyXG4gIHN0YXR1czogSDVXaXRoZHJhd1N0YXR1cztcclxuICBjcmVhdGVkQXQ6IHN0cmluZztcclxufTtcclxuXHJcbmV4cG9ydCB0eXBlIEg1TGVhZGVyYm9hcmRFbnRyeSA9IHtcclxuICByYW5rOiBudW1iZXI7XHJcbiAgYWNjb3VudElkTWFza2VkOiBzdHJpbmc7XHJcbiAgYW1vdW50OiBudW1iZXI7XHJcbiAgY3VycmVuY3k6IHN0cmluZztcclxufTtcclxuXHJcbmV4cG9ydCB0eXBlIEg1TWVzc2FnZUl0ZW0gPSB7XHJcbiAgaWQ6IHN0cmluZztcclxuICBjYXRlZ29yeTogSDVNZXNzYWdlQ2F0ZWdvcnk7XHJcbiAgdGl0bGU6IHN0cmluZztcclxuICBib2R5OiBzdHJpbmc7XHJcbiAgY3JlYXRlZEF0OiBzdHJpbmc7XHJcbiAgaXNSZWFkOiBib29sZWFuO1xyXG59O1xyXG5cclxuZXhwb3J0IHR5cGUgSDVGcmFnbWVudERlZmluaXRpb24gPSB7XHJcbiAgaWQ6IHN0cmluZztcclxuICBuYW1lOiBzdHJpbmc7XHJcbiAgcmFyaXR5OiBcImNvbW1vblwiIHwgXCJyYXJlXCIgfCBcImVwaWNcIjtcclxuICBjb2xvcjogc3RyaW5nO1xyXG59O1xyXG5cclxuZXhwb3J0IHR5cGUgSDVGcmFnbWVudEludmVudG9yeUl0ZW0gPSBINUZyYWdtZW50RGVmaW5pdGlvbiAmIHtcclxuICBvd25lZDogbnVtYmVyO1xyXG4gIHJlcXVpcmVkOiBudW1iZXI7XHJcbn07XHJcblxyXG5leHBvcnQgdHlwZSBINUZyYWdtZW50RHJvcExvZyA9IHtcclxuICBpZDogc3RyaW5nO1xyXG4gIGZyYWdtZW50SWQ6IHN0cmluZztcclxuICBmcmFnbWVudE5hbWU6IHN0cmluZztcclxuICBzb3VyY2U6IFwiY2hlY2tpblwiIHwgXCJ0YXNrXCI7XHJcbiAgY3JlYXRlZEF0OiBzdHJpbmc7XHJcbn07XHJcblxyXG5leHBvcnQgdHlwZSBINVNoaXBwaW5nQWRkcmVzcyA9IHtcclxuICByZWNlaXZlcjogc3RyaW5nO1xyXG4gIHBob25lOiBzdHJpbmc7XHJcbiAgY291bnRyeTogc3RyaW5nO1xyXG4gIHByb3ZpbmNlOiBzdHJpbmc7XHJcbiAgY2l0eTogc3RyaW5nO1xyXG4gIGFkZHJlc3NMaW5lOiBzdHJpbmc7XHJcbn07XHJcblxyXG5leHBvcnQgdHlwZSBINVJld2FyZFNoaXBwaW5nT3JkZXIgPSB7XHJcbiAgaWQ6IHN0cmluZztcclxuICByZXdhcmROYW1lOiBzdHJpbmc7XHJcbiAgc3RhdHVzOiBINVJld2FyZFNoaXBwaW5nU3RhdHVzO1xyXG4gIGNyZWF0ZWRBdDogc3RyaW5nO1xyXG4gIGFkZHJlc3M6IEg1U2hpcHBpbmdBZGRyZXNzIHwgbnVsbDtcclxufTtcclxuXHJcbmV4cG9ydCB0eXBlIEg1RnJhZ21lbnRPdmVydmlldyA9IHtcclxuICBpbnZlbnRvcnk6IEg1RnJhZ21lbnRJbnZlbnRvcnlJdGVtW107XHJcbiAgZHJvcExvZ3M6IEg1RnJhZ21lbnREcm9wTG9nW107XHJcbiAgcmV3YXJkTmFtZTogc3RyaW5nO1xyXG4gIHNoaXBwaW5nT3JkZXJzOiBINVJld2FyZFNoaXBwaW5nT3JkZXJbXTtcclxufTtcclxuXHJcbmV4cG9ydCB0eXBlIEg1SG9tZUZyYWdtZW50U3VtbWFyeSA9IHtcclxuICByZXdhcmROYW1lOiBzdHJpbmcgfCBudWxsO1xyXG4gIGNvbXBsZXRlZENvdW50OiBudW1iZXI7XHJcbiAgdG90YWxDb3VudDogbnVtYmVyO1xyXG4gIG1pc3NpbmdDb3VudDogbnVtYmVyO1xyXG4gIGNhbkV4Y2hhbmdlOiBib29sZWFuO1xyXG4gIHNoaXBwaW5nT3JkZXJDb3VudDogbnVtYmVyO1xyXG4gIGxhdGVzdFNoaXBwaW5nU3RhdHVzOiBINVJld2FyZFNoaXBwaW5nU3RhdHVzIHwgbnVsbDtcclxufTtcclxuXHJcbmV4cG9ydCB0eXBlIEg1SG9tZVZlcmlmaWNhdGlvblN1bW1hcnkgPSB7XHJcbiAgY3VycmVudFN0YXR1czogc3RyaW5nO1xyXG4gIGhhc0FjdGl2ZVJlcXVlc3Q6IGJvb2xlYW47XHJcbn07XHJcblxyXG5leHBvcnQgdHlwZSBINU1lbWJlclZlcmlmaWNhdGlvbkRvY3VtZW50ID0ge1xyXG4gIGlkOiBzdHJpbmc7XHJcbiAgZmlsZU5hbWU6IHN0cmluZztcclxuICBtaW1lVHlwZTogc3RyaW5nIHwgbnVsbDtcclxuICBzdG9yYWdlS2V5OiBzdHJpbmcgfCBudWxsO1xyXG4gIG1ldGFkYXRhSnNvbjogSnNvbk9iamVjdCB8IG51bGw7XHJcbiAgY3JlYXRlZEF0OiBzdHJpbmc7XHJcbn07XHJcblxyXG5leHBvcnQgdHlwZSBINU1lbWJlclZlcmlmaWNhdGlvblJlcXVlc3QgPSB7XHJcbiAgaWQ6IHN0cmluZztcclxuICByZXF1ZXN0VHlwZTogc3RyaW5nO1xyXG4gIHN0YXR1czogc3RyaW5nO1xyXG4gIG5vdGVzOiBzdHJpbmcgfCBudWxsO1xyXG4gIHJldmlld05vdGU6IHN0cmluZyB8IG51bGw7XHJcbiAgcmV2aWV3ZXJBY3RvcklkOiBzdHJpbmcgfCBudWxsO1xyXG4gIHJldmlld2VkQXQ6IHN0cmluZyB8IG51bGw7XHJcbiAgY3JlYXRlZEF0OiBzdHJpbmc7XHJcbiAgdXBkYXRlZEF0OiBzdHJpbmc7XHJcbiAgZG9jdW1lbnRzOiBINU1lbWJlclZlcmlmaWNhdGlvbkRvY3VtZW50W107XHJcbn07XHJcblxyXG5leHBvcnQgdHlwZSBINU1lbWJlclZlcmlmaWNhdGlvblN1bW1hcnkgPSB7XHJcbiAgY3VycmVudFN0YXR1czogc3RyaW5nO1xyXG4gIGhhc0FjdGl2ZVJlcXVlc3Q6IGJvb2xlYW47XHJcbiAgYWN0aXZlUmVxdWVzdDogSDVNZW1iZXJWZXJpZmljYXRpb25SZXF1ZXN0IHwgbnVsbDtcclxuICBoaXN0b3J5OiBINU1lbWJlclZlcmlmaWNhdGlvblJlcXVlc3RbXTtcclxufTtcclxuXHJcbmV4cG9ydCB0eXBlIEg1TWVtYmVyVmVyaWZpY2F0aW9uRG9jdW1lbnRJbnB1dCA9IHtcclxuICBmaWxlTmFtZTogc3RyaW5nO1xyXG4gIG1pbWVUeXBlPzogc3RyaW5nIHwgbnVsbDtcclxuICBzdG9yYWdlS2V5Pzogc3RyaW5nIHwgbnVsbDtcclxuICBtZXRhZGF0YUpzb24/OiBKc29uT2JqZWN0IHwgbnVsbDtcclxufTtcclxuXHJcbmV4cG9ydCB0eXBlIEg1TWVtYmVyVmVyaWZpY2F0aW9uQ3JlYXRlSW5wdXQgPSB7XHJcbiAgcmVxdWVzdFR5cGU/OiBzdHJpbmc7XHJcbiAgbm90ZXM/OiBzdHJpbmcgfCBudWxsO1xyXG4gIGRvY3VtZW50cz86IEg1TWVtYmVyVmVyaWZpY2F0aW9uRG9jdW1lbnRJbnB1dFtdO1xyXG59O1xyXG5cclxuZXhwb3J0IHR5cGUgSDVXaGF0c0FwcEJpbmRpbmcgPSB7XHJcbiAgaXNCb3VuZDogYm9vbGVhbjtcclxuICBiaW5kaW5nU3RhdHVzPzogc3RyaW5nO1xyXG4gIHJlcXVlc3RJZD86IHN0cmluZyB8IG51bGw7XHJcbiAgcGhvbmVOdW1iZXI6IHN0cmluZyB8IG51bGw7XHJcbiAgcmVxdWVzdGVkQXQ/OiBzdHJpbmcgfCBudWxsO1xyXG4gIHN0YXJ0Q291bnQ/OiBudW1iZXI7XHJcbiAgbGFzdFVwZGF0ZWRBdDogc3RyaW5nIHwgbnVsbDtcclxufTtcclxuXHJcbmV4cG9ydCB0eXBlIEg1SG9tZURhc2hib2FyZCA9IHtcclxuICBzaXRlOiBINVNpdGVCcmFuZDtcclxuICBtZW1iZXI6IEg1TWVtYmVyUHJvZmlsZTtcclxuICB3YWxsZXQ6IEg1V2FsbGV0U3VtbWFyeTtcclxuICB1bnJlYWRDb3VudDogbnVtYmVyO1xyXG4gIHBlbmRpbmdDbGFpbUNvdW50OiBudW1iZXI7XHJcbiAgYWN0aXZlQ291bnQ6IG51bWJlcjtcclxuICBleHBpcmluZ0NvdW50OiBudW1iZXI7XHJcbiAgcmVjZW50TWVzc2FnZXM6IEg1TWVzc2FnZUl0ZW1bXTtcclxuICBsZWFkZXJib2FyZDogSDVMZWFkZXJib2FyZEVudHJ5W107XHJcbiAgdmVyaWZpY2F0aW9uOiBINUhvbWVWZXJpZmljYXRpb25TdW1tYXJ5O1xyXG4gIGZyYWdtZW50czogSDVIb21lRnJhZ21lbnRTdW1tYXJ5O1xyXG59O1xyXG5cclxudHlwZSBTdG9yZWRNZW1iZXJBY2NvdW50ID0ge1xyXG4gIGlkOiBzdHJpbmc7XHJcbiAgYWNjb3VudElkOiBzdHJpbmc7XHJcbiAgcGhvbmU6IHN0cmluZztcclxuICBwYXNzd29yZDogc3RyaW5nO1xyXG4gIHB1YmxpY1VzZXJJZDogc3RyaW5nO1xyXG4gIGRpc3BsYXlOYW1lOiBzdHJpbmc7XHJcbiAgaW52aXRlQ29kZTogc3RyaW5nO1xyXG4gIGNyZWF0ZWRBdDogc3RyaW5nO1xyXG4gIGF2YXRhclVybD86IHN0cmluZyB8IG51bGw7XHJcbn07XHJcblxyXG50eXBlIFN0b3JlZE1lbWJlclN0YXRlID0ge1xyXG4gIHdhbGxldDoge1xyXG4gICAgc3lzdGVtQmFsYW5jZTogbnVtYmVyO1xyXG4gICAgdGFza0JhbGFuY2U6IG51bWJlcjtcclxuICAgIGN1cnJlbmN5OiBzdHJpbmc7XHJcbiAgICB3aXRoZHJhd1RocmVzaG9sZDogbnVtYmVyO1xyXG4gIH07XHJcbiAgdGFza1BhY2thZ2VzOiBINVRhc2tQYWNrYWdlW107XHJcbiAgb3JkZXJzOiBINU1lbWJlck9yZGVyW107XHJcbiAgdHJhbnNhY3Rpb25zOiBINVdhbGxldFRyYW5zYWN0aW9uW107XHJcbiAgd2l0aGRyYXdSZXF1ZXN0czogSDVXaXRoZHJhd1JlcXVlc3RbXTtcclxuICBtZXNzYWdlczogSDVNZXNzYWdlSXRlbVtdO1xyXG4gIGZyYWdtZW50SW52ZW50b3J5OiBSZWNvcmQ8c3RyaW5nLCBudW1iZXI+O1xyXG4gIGZyYWdtZW50RHJvcExvZ3M6IEg1RnJhZ21lbnREcm9wTG9nW107XHJcbiAgc2hpcHBpbmdPcmRlcnM6IEg1UmV3YXJkU2hpcHBpbmdPcmRlcltdO1xyXG4gIGNoZWNrZWRJbkRhdGU6IHN0cmluZyB8IG51bGw7XHJcbiAgdmVyaWZpY2F0aW9uUmVxdWVzdHM6IEg1TWVtYmVyVmVyaWZpY2F0aW9uUmVxdWVzdFtdO1xyXG4gIHdoYXRzYXBwQmluZGluZzogSDVXaGF0c0FwcEJpbmRpbmc7XHJcbn07XHJcblxyXG5jb25zdCBNRU1CRVJfQUNDT1VOVFNfS0VZID0gXCJmcm9udGVuZC5oNS5tZW1iZXItYWNjb3VudHMudjFcIjtcclxuY29uc3QgTUVNQkVSX1NUQVRFU19LRVkgPSBcImZyb250ZW5kLmg1Lm1lbWJlci1zdGF0ZXMudjFcIjtcclxuY29uc3QgTUVNQkVSX1NFU1NJT05fS0VZID0gXCJmcm9udGVuZC5oNS5tZW1iZXItc2Vzc2lvbi52MVwiO1xyXG5jb25zdCBERUZBVUxUX01FTUJFUl9QSE9ORSA9IFwiMTM4MDAwMDAwMDBcIjtcclxuY29uc3QgREVGQVVMVF9NRU1CRVJfUEFTU1dPUkQgPSBcImRlbW8xMjM0NTZcIjtcclxuY29uc3QgQUNDT1VOVF9JRF9MRU5HVEggPSA4O1xyXG5jb25zdCBERUZBVUxUX1dJVEhEUkFXX1RIUkVTSE9MRCA9IDEwMDtcclxuXHJcbmZ1bmN0aW9uIGdldFNlcnZpY2VFcnJvck1lc3NhZ2Uoa2V5OiBzdHJpbmcpOiBzdHJpbmcge1xyXG4gIHJldHVybiB0KGBzZXJ2aWNlRXJyb3JzLiR7a2V5fWApO1xyXG59XHJcblxyXG5mdW5jdGlvbiBnZXRTZXJ2aWNlTWVzc2FnZShcclxuICBrZXk6IHN0cmluZyxcclxuICBwYXJhbXM/OiBSZWNvcmQ8c3RyaW5nLCBzdHJpbmcgfCBudW1iZXI+LFxyXG4pOiBzdHJpbmcge1xyXG4gIHJldHVybiB0KGBzZXJ2aWNlTWVzc2FnZXMuJHtrZXl9YCwgcGFyYW1zKTtcclxufVxyXG5cclxuZnVuY3Rpb24gZ2V0U2VlZERhdGFUZXh0KFxyXG4gIGtleTogc3RyaW5nLFxyXG4gIHBhcmFtcz86IFJlY29yZDxzdHJpbmcsIHN0cmluZyB8IG51bWJlcj4sXHJcbik6IHN0cmluZyB7XHJcbiAgcmV0dXJuIHQoYHNlZWREYXRhLiR7a2V5fWAsIHBhcmFtcyk7XHJcbn1cclxuXHJcbmZ1bmN0aW9uIGNyZWF0ZVNlcnZpY2VFcnJvcihrZXk6IHN0cmluZyk6IEVycm9yIHtcclxuICByZXR1cm4gbmV3IEVycm9yKGdldFNlcnZpY2VFcnJvck1lc3NhZ2Uoa2V5KSk7XHJcbn1cclxuXHJcbmZ1bmN0aW9uIGdldEF1dGhSZXF1aXJlZE1lc3NhZ2UoKTogc3RyaW5nIHtcclxuICByZXR1cm4gZ2V0U2VydmljZUVycm9yTWVzc2FnZShcImF1dGhSZXF1aXJlZFwiKTtcclxufVxyXG5cclxudHlwZSBCYWNrZW5kTWVtYmVyQXV0aFJlc3BvbnNlID0ge1xyXG4gIG1lbWJlcjoge1xyXG4gICAgYWNjb3VudElkOiBzdHJpbmc7XHJcbiAgICBhY2NvdW50SWRNYXNrZWQ/OiBzdHJpbmcgfCBudWxsO1xyXG4gICAgY3JlYXRlZEF0OiBzdHJpbmc7XHJcbiAgICBkaXNwbGF5TmFtZT86IHN0cmluZyB8IG51bGw7XHJcbiAgICBpbnZpdGVDb2RlPzogc3RyaW5nIHwgbnVsbDtcclxuICAgIG1lbWJlck5vPzogc3RyaW5nIHwgbnVsbDtcclxuICAgIHBob25lOiBzdHJpbmc7XHJcbiAgICBwdWJsaWNVc2VySWQ6IHN0cmluZztcclxuICB9O1xyXG4gIHNpdGU6IHtcclxuICAgIHNpdGVLZXk6IHN0cmluZztcclxuICAgIGJyYW5kTmFtZTogc3RyaW5nO1xyXG4gIH07XHJcbn07XHJcblxyXG50eXBlIEJhY2tlbmRNZW1iZXJIb21lUmVzcG9uc2UgPSB7XHJcbiAgbWVtYmVyOiB7XHJcbiAgICBhY2NvdW50SWQ6IHN0cmluZztcclxuICAgIGFjY291bnRJZE1hc2tlZD86IHN0cmluZyB8IG51bGw7XHJcbiAgICBjcmVhdGVkQXQ6IHN0cmluZztcclxuICAgIGRpc3BsYXlOYW1lPzogc3RyaW5nIHwgbnVsbDtcclxuICAgIGludml0ZUNvZGU/OiBzdHJpbmcgfCBudWxsO1xyXG4gICAgbWVtYmVyTm8/OiBzdHJpbmcgfCBudWxsO1xyXG4gICAgcGhvbmU6IHN0cmluZztcclxuICAgIHB1YmxpY1VzZXJJZDogc3RyaW5nO1xyXG4gIH07XHJcbiAgc2l0ZToge1xyXG4gICAgc2l0ZUtleTogc3RyaW5nO1xyXG4gICAgYnJhbmROYW1lOiBzdHJpbmc7XHJcbiAgfTtcclxuICB3YWxsZXQ6IHtcclxuICAgIHN5c3RlbUJhbGFuY2U6IG51bWJlciB8IG51bGw7XHJcbiAgICB0YXNrQmFsYW5jZTogbnVtYmVyIHwgbnVsbDtcclxuICAgIGN1cnJlbmN5OiBzdHJpbmcgfCBudWxsO1xyXG4gIH07XHJcbiAgdW5yZWFkTWVzc2FnZUNvdW50OiBudW1iZXI7XHJcbiAgcGVuZGluZ0NsYWltQ291bnQ6IG51bWJlcjtcclxuICBhY3RpdmVDb3VudDogbnVtYmVyO1xyXG4gIGV4cGlyaW5nQ291bnQ6IG51bWJlcjtcclxuICByZWNlbnRNZXNzYWdlczogQXJyYXk8e1xyXG4gICAgaWQ6IHN0cmluZztcclxuICAgIGNhdGVnb3J5OiBINU1lc3NhZ2VDYXRlZ29yeTtcclxuICAgIHRpdGxlOiBzdHJpbmc7XHJcbiAgICBib2R5VGV4dDogc3RyaW5nO1xyXG4gICAgaXNSZWFkOiBib29sZWFuO1xyXG4gICAgY3JlYXRlZEF0OiBzdHJpbmc7XHJcbiAgfT47XHJcbiAgbGVhZGVyYm9hcmQ6IEFycmF5PHtcclxuICAgIHJhbms6IG51bWJlcjtcclxuICAgIGFjY291bnRJZE1hc2tlZDogc3RyaW5nO1xyXG4gICAgYW1vdW50OiBudW1iZXI7XHJcbiAgICBjdXJyZW5jeTogc3RyaW5nO1xyXG4gIH0+O1xyXG4gIHZlcmlmaWNhdGlvbj86IHtcclxuICAgIGN1cnJlbnRTdGF0dXM6IHN0cmluZztcclxuICAgIGhhc0FjdGl2ZVJlcXVlc3Q6IGJvb2xlYW47XHJcbiAgfTtcclxuICBmcmFnbWVudHM/OiB7XHJcbiAgICByZXdhcmROYW1lOiBzdHJpbmcgfCBudWxsO1xyXG4gICAgY29tcGxldGVkQ291bnQ6IG51bWJlcjtcclxuICAgIHRvdGFsQ291bnQ6IG51bWJlcjtcclxuICAgIG1pc3NpbmdDb3VudDogbnVtYmVyO1xyXG4gICAgY2FuRXhjaGFuZ2U6IGJvb2xlYW47XHJcbiAgICBzaGlwcGluZ09yZGVyQ291bnQ6IG51bWJlcjtcclxuICAgIGxhdGVzdFNoaXBwaW5nU3RhdHVzOiBINVJld2FyZFNoaXBwaW5nU3RhdHVzIHwgbnVsbDtcclxuICB9O1xyXG59O1xyXG5cclxudHlwZSBCYWNrZW5kTWVtYmVyVmVyaWZpY2F0aW9uRG9jdW1lbnRSZXNwb25zZSA9IHtcclxuICBpZDogc3RyaW5nO1xyXG4gIGZpbGVOYW1lPzogc3RyaW5nO1xyXG4gIGZpbGVfbmFtZT86IHN0cmluZztcclxuICBtaW1lVHlwZT86IHN0cmluZyB8IG51bGw7XHJcbiAgbWltZV90eXBlPzogc3RyaW5nIHwgbnVsbDtcclxuICBzdG9yYWdlS2V5Pzogc3RyaW5nIHwgbnVsbDtcclxuICBzdG9yYWdlX2tleT86IHN0cmluZyB8IG51bGw7XHJcbiAgbWV0YWRhdGFKc29uPzogSnNvbk9iamVjdCB8IG51bGw7XHJcbiAgbWV0YWRhdGFfanNvbj86IEpzb25PYmplY3QgfCBudWxsO1xyXG4gIGNyZWF0ZWRBdD86IHN0cmluZztcclxuICBjcmVhdGVkX2F0Pzogc3RyaW5nO1xyXG59O1xyXG5cclxudHlwZSBCYWNrZW5kTWVtYmVyVmVyaWZpY2F0aW9uUmVxdWVzdFJlc3BvbnNlID0ge1xyXG4gIGlkOiBzdHJpbmc7XHJcbiAgcmVxdWVzdFR5cGU/OiBzdHJpbmc7XHJcbiAgcmVxdWVzdF90eXBlPzogc3RyaW5nO1xyXG4gIHN0YXR1czogc3RyaW5nO1xyXG4gIG5vdGVzOiBzdHJpbmcgfCBudWxsO1xyXG4gIHJldmlld05vdGU/OiBzdHJpbmcgfCBudWxsO1xyXG4gIHJldmlld19ub3RlPzogc3RyaW5nIHwgbnVsbDtcclxuICByZXZpZXdlckFjdG9ySWQ/OiBzdHJpbmcgfCBudWxsO1xyXG4gIHJldmlld2VyX2FjdG9yX2lkPzogc3RyaW5nIHwgbnVsbDtcclxuICByZXZpZXdlZEF0Pzogc3RyaW5nIHwgbnVsbDtcclxuICByZXZpZXdlZF9hdD86IHN0cmluZyB8IG51bGw7XHJcbiAgY3JlYXRlZEF0Pzogc3RyaW5nO1xyXG4gIGNyZWF0ZWRfYXQ/OiBzdHJpbmc7XHJcbiAgdXBkYXRlZEF0Pzogc3RyaW5nO1xyXG4gIHVwZGF0ZWRfYXQ/OiBzdHJpbmc7XHJcbiAgZG9jdW1lbnRzOiBCYWNrZW5kTWVtYmVyVmVyaWZpY2F0aW9uRG9jdW1lbnRSZXNwb25zZVtdO1xyXG59O1xyXG5cclxudHlwZSBCYWNrZW5kTWVtYmVyVmVyaWZpY2F0aW9uU3VtbWFyeVJlc3BvbnNlID0ge1xyXG4gIGN1cnJlbnRTdGF0dXM/OiBzdHJpbmc7XHJcbiAgY3VycmVudF9zdGF0dXM/OiBzdHJpbmc7XHJcbiAgaGFzQWN0aXZlUmVxdWVzdD86IGJvb2xlYW47XHJcbiAgaGFzX2FjdGl2ZV9yZXF1ZXN0PzogYm9vbGVhbjtcclxuICBhY3RpdmVSZXF1ZXN0PzogQmFja2VuZE1lbWJlclZlcmlmaWNhdGlvblJlcXVlc3RSZXNwb25zZSB8IG51bGw7XHJcbiAgYWN0aXZlX3JlcXVlc3Q/OiBCYWNrZW5kTWVtYmVyVmVyaWZpY2F0aW9uUmVxdWVzdFJlc3BvbnNlIHwgbnVsbDtcclxuICBoaXN0b3J5OiBCYWNrZW5kTWVtYmVyVmVyaWZpY2F0aW9uUmVxdWVzdFJlc3BvbnNlW107XHJcbn07XHJcblxyXG50eXBlIEJhY2tlbmRUYXNrUGFja2FnZUl0ZW1SZXNwb25zZSA9IHtcclxuICBpZDogc3RyaW5nO1xyXG4gIHByb2R1Y3ROYW1lOiBzdHJpbmc7XHJcbiAgaW1hZ2VVcmw/OiBzdHJpbmcgfCBudWxsO1xyXG4gIHByaWNlOiBudW1iZXI7XHJcbiAgY3VycmVuY3k6IHN0cmluZztcclxuICBjb21wbGV0ZWRBdDogc3RyaW5nIHwgbnVsbDtcclxuICBvcmRlcklkOiBzdHJpbmcgfCBudWxsO1xyXG59O1xyXG5cclxudHlwZSBCYWNrZW5kVGFza1BhY2thZ2VQcm9tb3Rpb25SZXNwb25zZSA9IHtcclxuICBtZXRyaWM6IEg1UHJvbW90aW9uTWV0cmljO1xyXG4gIGN1cnJlbnQ6IG51bWJlcjtcclxuICB0YXJnZXQ6IG51bWJlcjtcclxuICBpbnZpdGVDb2RlPzogc3RyaW5nIHwgbnVsbDtcclxufTtcclxuXHJcbnR5cGUgQmFja2VuZFRhc2tQYWNrYWdlUmVzcG9uc2UgPSB7XHJcbiAgaWQ6IHN0cmluZztcclxuICB0aXRsZTogc3RyaW5nO1xyXG4gIGRlc2NyaXB0aW9uOiBzdHJpbmcgfCBudWxsO1xyXG4gIHR5cGU6IEg1VGFza1BhY2thZ2VUeXBlO1xyXG4gIHN0YXR1czogSDVUYXNrUGFja2FnZVN0YXR1cztcclxuICByZXdhcmRSYXRpbzogbnVtYmVyO1xyXG4gIGNsYWltZWRBdDogc3RyaW5nIHwgbnVsbDtcclxuICBleHBpcmVzQXQ6IHN0cmluZyB8IG51bGw7XHJcbiAgZGlzcGF0Y2hlZEF0OiBzdHJpbmc7XHJcbiAgY29tcGxldGlvbldpbmRvd0hvdXJzOiBudW1iZXI7XHJcbiAgaXRlbXM6IEJhY2tlbmRUYXNrUGFja2FnZUl0ZW1SZXNwb25zZVtdO1xyXG4gIHByb21vdGlvbjogQmFja2VuZFRhc2tQYWNrYWdlUHJvbW90aW9uUmVzcG9uc2UgfCBudWxsO1xyXG4gIHRhc2tCYWxhbmNlQXdhcmRlZEF0OiBzdHJpbmcgfCBudWxsO1xyXG4gIHRvdGFsQ29tbWlzc2lvbjogbnVtYmVyO1xyXG4gIGN1cnJlbnRDb21taXNzaW9uOiBudW1iZXI7XHJcbiAgY29tcGxldGVkSXRlbXM6IG51bWJlcjtcclxuICB0b3RhbEl0ZW1zOiBudW1iZXI7XHJcbiAgY291bnRkb3duU2Vjb25kczogbnVtYmVyO1xyXG59O1xyXG5cclxudHlwZSBCYWNrZW5kV2FsbGV0U3VtbWFyeVJlc3BvbnNlID0ge1xyXG4gIHN5c3RlbUJhbGFuY2U6IG51bWJlcjtcclxuICB0YXNrQmFsYW5jZTogbnVtYmVyO1xyXG4gIGN1cnJlbmN5OiBzdHJpbmc7XHJcbiAgd2l0aGRyYXdUaHJlc2hvbGQ6IG51bWJlcjtcclxuICBjYW5XaXRoZHJhdzogYm9vbGVhbjtcclxuICBzaG9ydGZhbGxBbW91bnQ6IG51bWJlcjtcclxufTtcclxuXHJcbnR5cGUgQmFja2VuZFdhbGxldFRyYW5zYWN0aW9uUmVzcG9uc2UgPSB7XHJcbiAgaWQ6IHN0cmluZztcclxuICBsZWRnZXJUeXBlOiBcInN5c3RlbVwiIHwgXCJ0YXNrXCI7XHJcbiAgdHJhbnNhY3Rpb25UeXBlOiBINVdhbGxldFRyYW5zYWN0aW9uVHlwZTtcclxuICBkaXJlY3Rpb246IFwiY3JlZGl0XCIgfCBcImRlYml0XCI7XHJcbiAgYW1vdW50OiBudW1iZXI7XHJcbiAgY3VycmVuY3k6IHN0cmluZztcclxuICBzdGF0dXM6IFwic3VibWl0dGVkXCIgfCBcInByb2Nlc3NpbmdcIiB8IFwicGFpZFwiIHwgXCJmYWlsZWRcIjtcclxuICBub3RlOiBzdHJpbmcgfCBudWxsO1xyXG4gIGNyZWF0ZWRBdDogc3RyaW5nO1xyXG59O1xyXG5cclxudHlwZSBCYWNrZW5kTWVtYmVyT3JkZXJSZXNwb25zZSA9IHtcclxuICBpZDogc3RyaW5nO1xyXG4gIG9yZGVyTm86IHN0cmluZztcclxuICBwYWNrYWdlSWQ6IHN0cmluZyB8IG51bGw7XHJcbiAgcGFja2FnZVRpdGxlOiBzdHJpbmcgfCBudWxsO1xyXG4gIHByb2R1Y3ROYW1lOiBzdHJpbmc7XHJcbiAgYW1vdW50OiBudW1iZXI7XHJcbiAgY3VycmVuY3k6IHN0cmluZztcclxuICBzdGF0dXM6IFwicGFpZFwiIHwgXCJmYWlsZWRcIiB8IFwicHJvY2Vzc2luZ1wiO1xyXG4gIGNyZWF0ZWRBdDogc3RyaW5nO1xyXG4gIHNvdXJjZUxhYmVsOiBzdHJpbmcgfCBudWxsO1xyXG59O1xyXG5cclxudHlwZSBCYWNrZW5kV2l0aGRyYXdhbFJlc3BvbnNlID0ge1xyXG4gIGlkOiBzdHJpbmc7XHJcbiAgcmVxdWVzdE5vOiBzdHJpbmc7XHJcbiAgYW1vdW50OiBudW1iZXI7XHJcbiAgY3VycmVuY3k6IHN0cmluZztcclxuICBzdGF0dXM6IEg1V2l0aGRyYXdTdGF0dXM7XHJcbiAgcmVqZWN0aW9uUmVhc29uOiBzdHJpbmcgfCBudWxsO1xyXG4gIGNyZWF0ZWRBdDogc3RyaW5nO1xyXG4gIHJldmlld2VkQXQ6IHN0cmluZyB8IG51bGw7XHJcbiAgcGFpZEF0OiBzdHJpbmcgfCBudWxsO1xyXG4gIGhpc3Rvcnk6IEFycmF5PFJlY29yZDxzdHJpbmcsIHVua25vd24+PjtcclxufTtcclxuXHJcbnR5cGUgQmFja2VuZFdpdGhkcmF3TGVhZGVyYm9hcmRSZXNwb25zZSA9IHtcclxuICByYW5rOiBudW1iZXI7XHJcbiAgYWNjb3VudElkTWFza2VkOiBzdHJpbmc7XHJcbiAgYW1vdW50OiBudW1iZXI7XHJcbiAgY3VycmVuY3k6IHN0cmluZztcclxufTtcclxuXHJcbnR5cGUgQmFja2VuZE1lbWJlck1lc3NhZ2VSZXNwb25zZSA9IHtcclxuICBpZDogc3RyaW5nO1xyXG4gIGNhdGVnb3J5OiBINU1lc3NhZ2VDYXRlZ29yeTtcclxuICB0aXRsZTogc3RyaW5nO1xyXG4gIGJvZHlUZXh0OiBzdHJpbmc7XHJcbiAgaXNSZWFkOiBib29sZWFuO1xyXG4gIHJlYWRBdDogc3RyaW5nIHwgbnVsbDtcclxuICBjcmVhdGVkQXQ6IHN0cmluZztcclxufTtcclxuXHJcbnR5cGUgQmFja2VuZEZyYWdtZW50SW52ZW50b3J5SXRlbVJlc3BvbnNlID0ge1xyXG4gIGlkOiBzdHJpbmc7XHJcbiAgZnJhZ21lbnRLZXk6IHN0cmluZztcclxuICBuYW1lOiBzdHJpbmc7XHJcbiAgcmFyaXR5OiBcImNvbW1vblwiIHwgXCJyYXJlXCIgfCBcImVwaWNcIjtcclxuICBjb2xvcjogc3RyaW5nO1xyXG4gIG93bmVkOiBudW1iZXI7XHJcbiAgcmVxdWlyZWQ6IG51bWJlcjtcclxufTtcclxuXHJcbnR5cGUgQmFja2VuZEZyYWdtZW50RHJvcExvZ1Jlc3BvbnNlID0ge1xyXG4gIGlkOiBzdHJpbmc7XHJcbiAgZnJhZ21lbnRJZDogc3RyaW5nO1xyXG4gIGZyYWdtZW50S2V5OiBzdHJpbmc7XHJcbiAgZnJhZ21lbnROYW1lOiBzdHJpbmc7XHJcbiAgc291cmNlOiBcImNoZWNraW5cIiB8IFwidGFza1wiO1xyXG4gIGNyZWF0ZWRBdDogc3RyaW5nO1xyXG59O1xyXG5cclxudHlwZSBCYWNrZW5kUmV3YXJkU2hpcHBpbmdBZGRyZXNzUmVzcG9uc2UgPSB7XHJcbiAgcmVjZWl2ZXI6IHN0cmluZztcclxuICBwaG9uZTogc3RyaW5nO1xyXG4gIGNvdW50cnk6IHN0cmluZztcclxuICBwcm92aW5jZTogc3RyaW5nO1xyXG4gIGNpdHk6IHN0cmluZztcclxuICBhZGRyZXNzTGluZTogc3RyaW5nO1xyXG59O1xyXG5cclxudHlwZSBCYWNrZW5kUmV3YXJkU2hpcHBpbmdPcmRlclJlc3BvbnNlID0ge1xyXG4gIGlkOiBzdHJpbmc7XHJcbiAgcmV3YXJkTmFtZTogc3RyaW5nO1xyXG4gIHN0YXR1czogSDVSZXdhcmRTaGlwcGluZ1N0YXR1cztcclxuICBjcmVhdGVkQXQ6IHN0cmluZztcclxuICBhZGRyZXNzOiBCYWNrZW5kUmV3YXJkU2hpcHBpbmdBZGRyZXNzUmVzcG9uc2UgfCBudWxsO1xyXG59O1xyXG5cclxudHlwZSBCYWNrZW5kRnJhZ21lbnRPdmVydmlld1Jlc3BvbnNlID0ge1xyXG4gIGludmVudG9yeTogQmFja2VuZEZyYWdtZW50SW52ZW50b3J5SXRlbVJlc3BvbnNlW107XHJcbiAgZHJvcExvZ3M6IEJhY2tlbmRGcmFnbWVudERyb3BMb2dSZXNwb25zZVtdO1xyXG4gIHJld2FyZE5hbWU6IHN0cmluZztcclxuICBzaGlwcGluZ09yZGVyczogQmFja2VuZFJld2FyZFNoaXBwaW5nT3JkZXJSZXNwb25zZVtdO1xyXG59O1xyXG5cclxudHlwZSBCYWNrZW5kVGFza1BhY2thZ2VQdXJjaGFzZVJlc3BvbnNlID0ge1xyXG4gIHN1Y2Nlc3M6IGJvb2xlYW47XHJcbiAgb3JkZXI6IEJhY2tlbmRNZW1iZXJPcmRlclJlc3BvbnNlIHwgbnVsbDtcclxuICB0YXNrUGFja2FnZTogQmFja2VuZFRhc2tQYWNrYWdlUmVzcG9uc2U7XHJcbiAgd2FsbGV0OiBCYWNrZW5kV2FsbGV0U3VtbWFyeVJlc3BvbnNlO1xyXG4gIGZyYWdtZW50RHJvcDogQmFja2VuZEZyYWdtZW50RHJvcExvZ1Jlc3BvbnNlIHwgbnVsbDtcclxuICByZWFzb246IHN0cmluZyB8IG51bGw7XHJcbn07XHJcblxyXG50eXBlIEJhY2tlbmRXaGF0c0FwcEJpbmRpbmdSZXNwb25zZSA9IHtcclxuICBpc0JvdW5kOiBib29sZWFuO1xyXG4gIGJpbmRpbmdTdGF0dXM/OiBzdHJpbmcgfCBudWxsO1xyXG4gIHJlcXVlc3RJZD86IHN0cmluZyB8IG51bGw7XHJcbiAgcGhvbmVOdW1iZXI6IHN0cmluZyB8IG51bGw7XHJcbiAgcmVxdWVzdGVkQXQ/OiBzdHJpbmcgfCBudWxsO1xyXG4gIHN0YXJ0Q291bnQ/OiBudW1iZXIgfCBudWxsO1xyXG4gIGxhc3RVcGRhdGVkQXQ6IHN0cmluZyB8IG51bGw7XHJcbn07XHJcblxyXG5jbGFzcyBBcGlSZXF1ZXN0RXJyb3IgZXh0ZW5kcyBFcnJvciB7XHJcbiAgc3RhdHVzOiBudW1iZXI7XHJcblxyXG4gIGNvbnN0cnVjdG9yKHN0YXR1czogbnVtYmVyLCBkZXRhaWw6IHN0cmluZykge1xyXG4gICAgc3VwZXIoXHJcbiAgICAgIGRldGFpbCB8fCBnZXRTZXJ2aWNlRXJyb3JNZXNzYWdlKFwicmVxdWVzdEZhaWxlZFN0YXR1c1wiKS5yZXBsYWNlKFwie3tzdGF0dXN9fVwiLCBTdHJpbmcoc3RhdHVzKSksXHJcbiAgICApO1xyXG4gICAgdGhpcy5uYW1lID0gXCJBcGlSZXF1ZXN0RXJyb3JcIjtcclxuICAgIHRoaXMuc3RhdHVzID0gc3RhdHVzO1xyXG4gIH1cclxufVxyXG5cclxuZXhwb3J0IGNsYXNzIEg1QXV0aFJlcXVpcmVkRXJyb3IgZXh0ZW5kcyBFcnJvciB7XHJcbiAgY29uc3RydWN0b3IobWVzc2FnZSA9IGdldEF1dGhSZXF1aXJlZE1lc3NhZ2UoKSkge1xyXG4gICAgc3VwZXIobWVzc2FnZSk7XHJcbiAgICB0aGlzLm5hbWUgPSBcIkg1QXV0aFJlcXVpcmVkRXJyb3JcIjtcclxuICB9XHJcbn1cclxuXHJcbmV4cG9ydCBmdW5jdGlvbiBpc0g1QXV0aFJlcXVpcmVkRXJyb3IoZXJyb3I6IHVua25vd24pOiBib29sZWFuIHtcclxuICByZXR1cm4gZXJyb3IgaW5zdGFuY2VvZiBINUF1dGhSZXF1aXJlZEVycm9yO1xyXG59XHJcblxyXG4vLyDilIDilIDilIAgSDUgQXhpb3Mg5a6e5L6L77yI5bim6Ieq5Yqo6Ym05p2DICYg5Yi35paw5oum5oiq5Zmo77yJ4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSAXHJcblxyXG5leHBvcnQgZnVuY3Rpb24gcmVzb2x2ZUg1QXBpQmFzZVVybChcbiAgZW52QXBpQmFzZVVybDogc3RyaW5nIHwgdW5kZWZpbmVkLFxuICBpc0RldjogYm9vbGVhbixcbik6IHN0cmluZyB7XG4gIGNvbnN0IHRyaW1tZWQgPSBlbnZBcGlCYXNlVXJsPy50cmltKCk7XG4gIGlmICh0cmltbWVkKSB7XG4gICAgcmV0dXJuIHRyaW1tZWQ7XG4gIH1cbiAgLy8gS2VlcCBINSBvbiBzYW1lLW9yaWdpbiByZXF1ZXN0cyBieSBkZWZhdWx0IHNvIGxvY2FsLWRldmljZSBhbmQgTEFOLWRldmljZVxuICAvLyBicm93c2VycyBib3RoIGdvIHRocm91Z2ggdGhlIFZpdGUgcHJveHkgaW5zdGVhZCBvZiB0aGVpciBvd24gbG9jYWxob3N0LlxuICB2b2lkIGlzRGV2O1xuICByZXR1cm4gXCJcIjtcbn1cblxyXG5jb25zdCByZXNvbHZlZEFwaUJhc2VVcmwgPSByZXNvbHZlSDVBcGlCYXNlVXJsKFxyXG4gIGltcG9ydC5tZXRhLmVudi5WSVRFX0FQSV9CQVNFX1VSTCBhcyBzdHJpbmcgfCB1bmRlZmluZWQsXHJcbiAgaW1wb3J0Lm1ldGEuZW52LkRFVixcclxuKTtcclxuXHJcbmV4cG9ydCBjb25zdCBoNUFwaSA9IGF4aW9zLmNyZWF0ZSh7XHJcbiAgYmFzZVVSTDogcmVzb2x2ZWRBcGlCYXNlVXJsLFxyXG4gIHRpbWVvdXQ6IDEwMDAwLFxyXG4gIHdpdGhDcmVkZW50aWFsczogdHJ1ZSxcclxufSk7XHJcblxyXG4vKiog5piv5ZCm5q2j5Zyo5Yi35pawIHRva2VuICovXHJcbmxldCBfaXNSZWZyZXNoaW5nID0gZmFsc2U7XHJcblxyXG4vKiog562J5b6FIHRva2VuIOWIt+aWsOacn+mXtOenr+WOi+eahOivt+axguWbnuiwgyAqL1xyXG5sZXQgX3BlbmRpbmdRdWV1ZTogQXJyYXk8KHRva2VuOiBzdHJpbmcgfCBudWxsKSA9PiB2b2lkPiA9IFtdO1xyXG5cclxuLy8g4pSA4pSAIFJlcXVlc3Qg5oum5oiq5ZmoIOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgFxyXG5cclxuaDVBcGkuaW50ZXJjZXB0b3JzLnJlcXVlc3QudXNlKFxyXG4gIChjb25maWc6IEludGVybmFsQXhpb3NSZXF1ZXN0Q29uZmlnKSA9PiB7XHJcbiAgICAvLyBUb2tlbiDljbPlsIbov4fmnJ/ml7blvILmraXnu63mnJ/vvIjkuI3pmLvloZ7lvZPliY3or7fmsYLvvIlcclxuICAgIGlmIChzZXNzaW9uTWFuYWdlci5zaG91bGRSZWZyZXNoKCkpIHtcclxuICAgICAgc2Vzc2lvbk1hbmFnZXIucmVmcmVzaFRva2VuKCkuY2F0Y2goKCkgPT4ge1xyXG4gICAgICAgIC8vIOe7reacn+Wksei0peW3suWcqCBzZXNzaW9uTWFuYWdlciDkuK3lpITnkIZcclxuICAgICAgfSk7XHJcbiAgICB9XHJcblxyXG4gICAgLy8g6ZmE5YqgIEF1dGhvcml6YXRpb24gaGVhZGVyXHJcbiAgICBjb25zdCBhdXRoSGVhZGVycyA9IHNlc3Npb25NYW5hZ2VyLmF1dGhIZWFkZXIoKTtcclxuICAgIGlmIChhdXRoSGVhZGVycy5BdXRob3JpemF0aW9uKSB7XHJcbiAgICAgIGNvbmZpZy5oZWFkZXJzLkF1dGhvcml6YXRpb24gPSBhdXRoSGVhZGVycy5BdXRob3JpemF0aW9uO1xyXG4gICAgfVxyXG5cclxuICAgIHJldHVybiBjb25maWc7XHJcbiAgfSxcclxuICAoZXJyb3IpID0+IFByb21pc2UucmVqZWN0KGVycm9yKSxcclxuKTtcclxuXHJcbi8vIOKUgOKUgCBSZXNwb25zZSDmi6bmiKrlmagg4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSAXHJcblxyXG5oNUFwaS5pbnRlcmNlcHRvcnMucmVzcG9uc2UudXNlKFxyXG4gIChyZXNwb25zZTogQXhpb3NSZXNwb25zZSkgPT4gcmVzcG9uc2UsXHJcbiAgYXN5bmMgKGVycm9yOiBBeGlvc0Vycm9yKSA9PiB7XHJcbiAgICBjb25zdCBvcmlnaW5hbFJlcXVlc3QgPSBlcnJvci5jb25maWcgYXMgSW50ZXJuYWxBeGlvc1JlcXVlc3RDb25maWcgJiB7XHJcbiAgICAgIF9yZXRyeT86IGJvb2xlYW47XHJcbiAgICAgIF9yZXRyeTV4eD86IGJvb2xlYW47XHJcbiAgICB9O1xyXG5cclxuICAgIC8vIOW/hemhu+imgeaciSBjb25maWfvvIzlkKbliJnml6Dms5Xph43or5VcclxuICAgIGlmICghb3JpZ2luYWxSZXF1ZXN0KSByZXR1cm4gUHJvbWlzZS5yZWplY3QoZXJyb3IpO1xyXG5cclxuICAgIC8vIDEpIOe9kee7nOmUmeivr++8iOaXoOWTjeW6lO+8ieKGkiBUb2FzdCDmj5DnpLpcclxuICAgIGlmICghZXJyb3IucmVzcG9uc2UpIHtcclxuICAgICAgY29uc3QgbWVzc2FnZSA9IGdldFNlcnZpY2VFcnJvck1lc3NhZ2UoXCJuZXR3b3JrRmFpbGVkXCIpO1xyXG4gICAgICBpZiAodHlwZW9mIHdpbmRvdyAhPT0gXCJ1bmRlZmluZWRcIikge1xyXG4gICAgICAgIHdpbmRvdy5hbGVydChtZXNzYWdlKTtcclxuICAgICAgfVxyXG4gICAgICByZXR1cm4gUHJvbWlzZS5yZWplY3QoZXJyb3IpO1xyXG4gICAgfVxyXG5cclxuICAgIGNvbnN0IHsgc3RhdHVzIH0gPSBlcnJvci5yZXNwb25zZTtcclxuXHJcbiAgICAvLyAyKSA0MDEg4oaSIOiHquWKqOe7reacn++8iOWNlemYn+WIl++8iVxyXG4gICAgaWYgKHN0YXR1cyA9PT0gNDAxICYmICFvcmlnaW5hbFJlcXVlc3QuX3JldHJ5KSB7XHJcbiAgICAgIGlmIChfaXNSZWZyZXNoaW5nKSB7XHJcbiAgICAgICAgLy8g5bey5pyJ5Yi35paw5Zyo6L+b6KGM5Lit77yM5bCG5b2T5YmN6K+35rGC5Yqg5YWl6Zif5YiX562J5b6FXHJcbiAgICAgICAgcmV0dXJuIG5ldyBQcm9taXNlPEF4aW9zUmVzcG9uc2U+KChyZXNvbHZlLCByZWplY3QpID0+IHtcclxuICAgICAgICAgIF9wZW5kaW5nUXVldWUucHVzaCgodG9rZW46IHN0cmluZyB8IG51bGwpID0+IHtcclxuICAgICAgICAgICAgaWYgKHRva2VuKSB7XHJcbiAgICAgICAgICAgICAgb3JpZ2luYWxSZXF1ZXN0LmhlYWRlcnMuQXV0aG9yaXphdGlvbiA9IGBCZWFyZXIgJHt0b2tlbn1gO1xyXG4gICAgICAgICAgICAgIHJlc29sdmUoaDVBcGkob3JpZ2luYWxSZXF1ZXN0KSk7XHJcbiAgICAgICAgICAgIH0gZWxzZSB7XHJcbiAgICAgICAgICAgICAgcmVqZWN0KGVycm9yKTtcclxuICAgICAgICAgICAgfVxyXG4gICAgICAgICAgfSk7XHJcbiAgICAgICAgfSk7XHJcbiAgICAgIH1cclxuXHJcbiAgICAgIC8vIOmmluS4qiA0MDHvvIzlkK/liqjliLfmlrBcclxuICAgICAgb3JpZ2luYWxSZXF1ZXN0Ll9yZXRyeSA9IHRydWU7XHJcbiAgICAgIF9pc1JlZnJlc2hpbmcgPSB0cnVlO1xyXG5cclxuICAgICAgdHJ5IHtcclxuICAgICAgICBjb25zdCBzdWNjZXNzID0gYXdhaXQgc2Vzc2lvbk1hbmFnZXIucmVmcmVzaFRva2VuKCk7XHJcbiAgICAgICAgaWYgKHN1Y2Nlc3MpIHtcclxuICAgICAgICAgIGNvbnN0IG5ld1Rva2VuID0gc2Vzc2lvbk1hbmFnZXIuZ2V0QWNjZXNzVG9rZW4oKTtcclxuICAgICAgICAgIC8vIOWkhOeQhumYn+WIl+S4reeahOetieW+heivt+axglxyXG4gICAgICAgICAgX3BlbmRpbmdRdWV1ZS5mb3JFYWNoKChjYikgPT4gY2IobmV3VG9rZW4pKTtcclxuICAgICAgICAgIF9wZW5kaW5nUXVldWUgPSBbXTtcclxuICAgICAgICAgIC8vIOmHjeivleW9k+WJjeivt+axglxyXG4gICAgICAgICAgb3JpZ2luYWxSZXF1ZXN0LmhlYWRlcnMuQXV0aG9yaXphdGlvbiA9IGBCZWFyZXIgJHtuZXdUb2tlbn1gO1xyXG4gICAgICAgICAgcmV0dXJuIGg1QXBpKG9yaWdpbmFsUmVxdWVzdCk7XHJcbiAgICAgICAgfSBlbHNlIHtcclxuICAgICAgICAgIC8vIOWIt+aWsOWksei0pSDihpIg5ouS57ud5omA5pyJ5o6S6Zif6K+35rGCXHJcbiAgICAgICAgICBfcGVuZGluZ1F1ZXVlLmZvckVhY2goKGNiKSA9PiBjYihudWxsKSk7XHJcbiAgICAgICAgICBfcGVuZGluZ1F1ZXVlID0gW107XHJcbiAgICAgICAgICBzZXNzaW9uTWFuYWdlci5jbGVhclNlc3Npb24oKTtcclxuICAgICAgICAgIHJldHVybiBQcm9taXNlLnJlamVjdChlcnJvcik7XHJcbiAgICAgICAgfVxyXG4gICAgICB9IGNhdGNoIChyZWZyZXNoRXJyb3IpIHtcclxuICAgICAgICBfcGVuZGluZ1F1ZXVlLmZvckVhY2goKGNiKSA9PiBjYihudWxsKSk7XHJcbiAgICAgICAgX3BlbmRpbmdRdWV1ZSA9IFtdO1xyXG4gICAgICAgIHJldHVybiBQcm9taXNlLnJlamVjdChyZWZyZXNoRXJyb3IpO1xyXG4gICAgICB9IGZpbmFsbHkge1xyXG4gICAgICAgIF9pc1JlZnJlc2hpbmcgPSBmYWxzZTtcclxuICAgICAgfVxyXG4gICAgfVxyXG5cclxuICAgIC8vIDMpIDV4eCDihpIgR0VUIOivt+axguiHquWKqOmHjeivleS4gOasoe+8iDJzIOW7tui/n++8iVxyXG4gICAgaWYgKFxyXG4gICAgICBzdGF0dXMgPj0gNTAwICYmXHJcbiAgICAgIHN0YXR1cyA8IDYwMCAmJlxyXG4gICAgICBvcmlnaW5hbFJlcXVlc3QubWV0aG9kPy50b1VwcGVyQ2FzZSgpID09PSBcIkdFVFwiICYmXHJcbiAgICAgICFvcmlnaW5hbFJlcXVlc3QuX3JldHJ5NXh4XHJcbiAgICApIHtcclxuICAgICAgb3JpZ2luYWxSZXF1ZXN0Ll9yZXRyeTV4eCA9IHRydWU7XHJcbiAgICAgIGF3YWl0IG5ldyBQcm9taXNlKChyZXNvbHZlKSA9PiBzZXRUaW1lb3V0KHJlc29sdmUsIDIwMDApKTtcclxuICAgICAgcmV0dXJuIGg1QXBpKG9yaWdpbmFsUmVxdWVzdCk7XHJcbiAgICB9XHJcblxyXG4gICAgcmV0dXJuIFByb21pc2UucmVqZWN0KGVycm9yKTtcclxuICB9LFxyXG4pO1xyXG5cclxuLy8g4pSA4pSA4pSAIEFQSSBNb2RlIChtb2NrL3JlYWwgc3dpdGNoKSDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIBcclxuXHJcbnR5cGUgQXBpTW9kZSA9ICdtb2NrJyB8ICdyZWFsJztcclxuY29uc3QgYXBpTW9kZTogQXBpTW9kZSA9IChpbXBvcnQubWV0YS5lbnYuVklURV9BUElfTU9ERSBhcyBzdHJpbmcpID09PSAncmVhbCcgPyAncmVhbCcgOiAnbW9jayc7XHJcblxyXG4vKiogQXV0aCBBUEkg5ZON5bqU57G75Z6LICovXHJcbmV4cG9ydCB0eXBlIEg1TG9naW5SZXNwb25zZSA9IHtcclxuICBhY2Nlc3NfdG9rZW46IHN0cmluZztcclxuICByZWZyZXNoX3Rva2VuOiBzdHJpbmc7XHJcbiAgZXhwaXJlc19pbjogbnVtYmVyO1xyXG4gIHVzZXI6IEg1TWVtYmVyU2Vzc2lvbjtcclxufTtcclxuXHJcblxyXG5mdW5jdGlvbiBpc0Jyb3dzZXIoKTogYm9vbGVhbiB7XHJcbiAgcmV0dXJuIHR5cGVvZiB3aW5kb3cgIT09IFwidW5kZWZpbmVkXCIgJiYgdHlwZW9mIHdpbmRvdy5sb2NhbFN0b3JhZ2UgIT09IFwidW5kZWZpbmVkXCI7XHJcbn1cclxuXHJcbmZ1bmN0aW9uIG5vd0lzbygpOiBzdHJpbmcge1xyXG4gIHJldHVybiBuZXcgRGF0ZSgpLnRvSVNPU3RyaW5nKCk7XHJcbn1cclxuXHJcbmZ1bmN0aW9uIHJlYWRTdG9yYWdlPFQ+KGtleTogc3RyaW5nLCBmYWxsYmFjazogVCk6IFQge1xyXG4gIGlmICghaXNCcm93c2VyKCkpIHtcclxuICAgIHJldHVybiBmYWxsYmFjaztcclxuICB9XHJcbiAgY29uc3QgcmF3ID0gd2luZG93LmxvY2FsU3RvcmFnZS5nZXRJdGVtKGtleSk7XHJcbiAgaWYgKCFyYXcpIHtcclxuICAgIHJldHVybiBmYWxsYmFjaztcclxuICB9XHJcbiAgdHJ5IHtcclxuICAgIHJldHVybiBKU09OLnBhcnNlKHJhdykgYXMgVDtcclxuICB9IGNhdGNoIHtcclxuICAgIHJldHVybiBmYWxsYmFjaztcclxuICB9XHJcbn1cclxuXHJcbmZ1bmN0aW9uIHdyaXRlU3RvcmFnZTxUPihrZXk6IHN0cmluZywgdmFsdWU6IFQpOiB2b2lkIHtcclxuICBpZiAoIWlzQnJvd3NlcigpKSB7XHJcbiAgICByZXR1cm47XHJcbiAgfVxyXG4gIHdpbmRvdy5sb2NhbFN0b3JhZ2Uuc2V0SXRlbShrZXksIEpTT04uc3RyaW5naWZ5KHZhbHVlKSk7XHJcbn1cclxuXHJcbmFzeW5jIGZ1bmN0aW9uIHJlcXVlc3RKc29uPFQ+KGlucHV0OiBzdHJpbmcsIGluaXQ/OiBSZXF1ZXN0SW5pdCk6IFByb21pc2U8VD4ge1xyXG4gIGNvbnN0IGNvbnRyb2xsZXIgPSBuZXcgQWJvcnRDb250cm9sbGVyKCk7XHJcbiAgY29uc3QgdGltZW91dCA9IHNldFRpbWVvdXQoKCkgPT4gY29udHJvbGxlci5hYm9ydCgpLCAxNTAwMCk7XHJcbiAgdHJ5IHtcclxuICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgZmV0Y2goaW5wdXQsIHtcclxuICAgICAgY3JlZGVudGlhbHM6IFwiaW5jbHVkZVwiLFxyXG4gICAgICBzaWduYWw6IGNvbnRyb2xsZXIuc2lnbmFsLFxyXG4gICAgICAuLi5pbml0LFxyXG4gICAgfSk7XHJcbiAgICBpZiAoIXJlc3BvbnNlLm9rKSB7XHJcbiAgICAgIGNvbnN0IHJhd1RleHQgPSBhd2FpdCByZXNwb25zZS50ZXh0KCk7XHJcbiAgICAgIGxldCBkZXRhaWwgPSByYXdUZXh0O1xyXG4gICAgICBpZiAocmF3VGV4dCkge1xyXG4gICAgICAgIHRyeSB7XHJcbiAgICAgICAgICBjb25zdCBwYXJzZWQgPSBKU09OLnBhcnNlKHJhd1RleHQpIGFzIHsgZGV0YWlsPzogdW5rbm93biB9O1xyXG4gICAgICAgICAgaWYgKHR5cGVvZiBwYXJzZWQuZGV0YWlsID09PSBcInN0cmluZ1wiICYmIHBhcnNlZC5kZXRhaWwudHJpbSgpKSB7XHJcbiAgICAgICAgICAgIGRldGFpbCA9IHBhcnNlZC5kZXRhaWw7XHJcbiAgICAgICAgICB9XHJcbiAgICAgICAgfSBjYXRjaCB7XHJcbiAgICAgICAgICBkZXRhaWwgPSByYXdUZXh0O1xyXG4gICAgICAgIH1cclxuICAgICAgfVxyXG4gICAgICB0aHJvdyBuZXcgQXBpUmVxdWVzdEVycm9yKHJlc3BvbnNlLnN0YXR1cywgZGV0YWlsKTtcclxuICAgIH1cclxuICAgIGNvbnN0IGNvbnRlbnRUeXBlID0gcmVzcG9uc2UuaGVhZGVycy5nZXQoXCJjb250ZW50LXR5cGVcIik/LnRvTG93ZXJDYXNlKCkgPz8gXCJcIjtcclxuICAgIGlmIChjb250ZW50VHlwZS5pbmNsdWRlcyhcInRleHQvaHRtbFwiKSkge1xyXG4gICAgICB0aHJvdyBuZXcgVHlwZUVycm9yKFwiRXhwZWN0ZWQgSlNPTiByZXNwb25zZSBidXQgcmVjZWl2ZWQgSFRNTC5cIik7XHJcbiAgICB9XHJcbiAgICByZXR1cm4gKGF3YWl0IHJlc3BvbnNlLmpzb24oKSkgYXMgVDtcclxuICB9IGNhdGNoIChlcnJvcikge1xyXG4gICAgaWYgKChlcnJvciBhcyBET01FeGNlcHRpb24pPy5uYW1lID09PSBcIkFib3J0RXJyb3JcIikge1xyXG4gICAgICB0aHJvdyBjcmVhdGVTZXJ2aWNlRXJyb3IoXCJyZXF1ZXN0VGltZW91dFwiKTtcclxuICAgIH1cclxuICAgIHRocm93IGVycm9yO1xyXG4gIH0gZmluYWxseSB7XHJcbiAgICBjbGVhclRpbWVvdXQodGltZW91dCk7XHJcbiAgfVxyXG59XHJcblxyXG50eXBlIEJhY2tlbmRBdXRoTG9va3VwUmVzdWx0PFQ+ID0gVCB8IG51bGwgfCBcInVuYXV0aGVudGljYXRlZFwiO1xyXG5cclxuZnVuY3Rpb24gaXNMZWdhY3lGYWxsYmFja0VuYWJsZWQoKTogYm9vbGVhbiB7XHJcbiAgY29uc3QgY29uZmlndXJlZCA9IGltcG9ydC5tZXRhLmVudi5WSVRFX0g1X01FTUJFUl9MRUdBQ1lfRkFMTEJBQ0s7XHJcbiAgaWYgKGNvbmZpZ3VyZWQgPT09IFwidHJ1ZVwiKSB7XHJcbiAgICByZXR1cm4gdHJ1ZTtcclxuICB9XHJcbiAgaWYgKGNvbmZpZ3VyZWQgPT09IFwiZmFsc2VcIikge1xyXG4gICAgcmV0dXJuIGZhbHNlO1xyXG4gIH1cclxuICByZXR1cm4gaW1wb3J0Lm1ldGEuZW52LkRFVjtcclxufVxyXG5cclxuZnVuY3Rpb24gY2FuVXNlTGVnYWN5RmFsbGJhY2soZXJyb3I6IHVua25vd24pOiBib29sZWFuIHtcclxuICBpZiAoIWlzTGVnYWN5RmFsbGJhY2tFbmFibGVkKCkpIHtcclxuICAgIHJldHVybiBmYWxzZTtcclxuICB9XHJcbiAgaWYgKGVycm9yIGluc3RhbmNlb2YgVHlwZUVycm9yIHx8IGVycm9yIGluc3RhbmNlb2YgU3ludGF4RXJyb3IpIHtcclxuICAgIHJldHVybiB0cnVlO1xyXG4gIH1cclxuICByZXR1cm4gZXJyb3IgaW5zdGFuY2VvZiBBcGlSZXF1ZXN0RXJyb3IgJiYgZXJyb3Iuc3RhdHVzID09PSA0MDQ7XHJcbn1cclxuXHJcbmZ1bmN0aW9uIGdldEJhY2tlbmRVbmF2YWlsYWJsZUVycm9yKCk6IEVycm9yIHtcclxuICByZXR1cm4gY3JlYXRlU2VydmljZUVycm9yKFwiYXV0aFNlcnZpY2VVbmF2YWlsYWJsZVwiKTtcclxufVxyXG5cclxuYXN5bmMgZnVuY3Rpb24gcmVmcmVzaEJhY2tlbmRBdXRoU2Vzc2lvbigpOiBQcm9taXNlPGJvb2xlYW4+IHtcclxuICB0cnkge1xyXG4gICAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCByZXF1ZXN0SnNvbjxCYWNrZW5kTWVtYmVyQXV0aFJlc3BvbnNlPihcIi9hcGkvaDUvYXV0aC9yZWZyZXNoXCIsIHtcclxuICAgICAgbWV0aG9kOiBcIlBPU1RcIixcclxuICAgIH0pO1xyXG4gICAgY29uc3QgcHJvZmlsZSA9IGJ1aWxkUHJvZmlsZUZyb21BdXRoUGF5bG9hZChyZXNwb25zZSk7XHJcbiAgICBzeW5jTGVnYWN5TWVtYmVyQ2FjaGVGcm9tUHJvZmlsZShwcm9maWxlKTtcclxuICAgIHJldHVybiB0cnVlO1xyXG4gIH0gY2F0Y2ggKGVycm9yKSB7XHJcbiAgICBpZiAoZXJyb3IgaW5zdGFuY2VvZiBBcGlSZXF1ZXN0RXJyb3IpIHtcclxuICAgICAgcmV0dXJuIGZhbHNlO1xyXG4gICAgfVxyXG4gICAgdGhyb3cgZXJyb3I7XHJcbiAgfVxyXG59XHJcblxyXG5hc3luYyBmdW5jdGlvbiB0cnlCYWNrZW5kQXV0aFJlcXVlc3Q8VD4oXHJcbiAgcmVxdWVzdDogKCkgPT4gUHJvbWlzZTxUPixcclxuICBvcHRpb25zPzoge1xyXG4gICAgYWxsb3dSZWZyZXNoPzogYm9vbGVhbjtcclxuICB9LFxyXG4pOiBQcm9taXNlPEJhY2tlbmRBdXRoTG9va3VwUmVzdWx0PFQ+PiB7XHJcbiAgdHJ5IHtcclxuICAgIHJldHVybiBhd2FpdCByZXF1ZXN0KCk7XHJcbiAgfSBjYXRjaCAoZXJyb3IpIHtcclxuICAgIGlmIChlcnJvciBpbnN0YW5jZW9mIEFwaVJlcXVlc3RFcnJvciAmJiBlcnJvci5zdGF0dXMgPT09IDQwMSkge1xyXG4gICAgICBpZiAob3B0aW9ucz8uYWxsb3dSZWZyZXNoKSB7XHJcbiAgICAgICAgY29uc3QgcmVmcmVzaGVkID0gYXdhaXQgcmVmcmVzaEJhY2tlbmRBdXRoU2Vzc2lvbigpO1xyXG4gICAgICAgIGlmIChyZWZyZXNoZWQpIHtcclxuICAgICAgICAgIHJldHVybiBhd2FpdCByZXF1ZXN0KCk7XHJcbiAgICAgICAgfVxyXG4gICAgICAgIGlmIChpc0xlZ2FjeUZhbGxiYWNrRW5hYmxlZCgpKSB7XHJcbiAgICAgICAgICByZXR1cm4gbnVsbDtcclxuICAgICAgICB9XHJcbiAgICAgIH1cclxuICAgICAgcmV0dXJuIFwidW5hdXRoZW50aWNhdGVkXCI7XHJcbiAgICB9XHJcbiAgICBpZiAoY2FuVXNlTGVnYWN5RmFsbGJhY2soZXJyb3IpKSB7XHJcbiAgICAgIHJldHVybiBudWxsO1xyXG4gICAgfVxyXG4gICAgdGhyb3cgZXJyb3I7XHJcbiAgfVxyXG59XHJcblxyXG5hc3luYyBmdW5jdGlvbiByZXF1ZXN0QmFja2VuZE1lbWJlckRvbWFpbjxUPihcclxuICBpbnB1dDogc3RyaW5nLFxyXG4gIGluaXQ/OiBSZXF1ZXN0SW5pdCxcclxuKTogUHJvbWlzZTxUIHwgbnVsbD4ge1xyXG4gIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgdHJ5QmFja2VuZEF1dGhSZXF1ZXN0PFQ+KCgpID0+IHJlcXVlc3RKc29uKGlucHV0LCBpbml0KSwge1xyXG4gICAgYWxsb3dSZWZyZXNoOiB0cnVlLFxyXG4gIH0pO1xyXG4gIGlmIChyZXNwb25zZSA9PT0gXCJ1bmF1dGhlbnRpY2F0ZWRcIikge1xyXG4gICAgd3JpdGVTZXNzaW9uKG51bGwpO1xyXG4gICAgdGhyb3cgbmV3IEg1QXV0aFJlcXVpcmVkRXJyb3IoKTtcclxuICB9XHJcbiAgcmV0dXJuIHJlc3BvbnNlO1xyXG59XHJcblxyXG5mdW5jdGlvbiBjcmVhdGVJZChwcmVmaXg6IHN0cmluZyk6IHN0cmluZyB7XHJcbiAgaWYgKHR5cGVvZiBjcnlwdG8gIT09IFwidW5kZWZpbmVkXCIgJiYgdHlwZW9mIGNyeXB0by5yYW5kb21VVUlEID09PSBcImZ1bmN0aW9uXCIpIHtcclxuICAgIHJldHVybiBgJHtwcmVmaXh9LSR7Y3J5cHRvLnJhbmRvbVVVSUQoKX1gO1xyXG4gIH1cclxuICByZXR1cm4gYCR7cHJlZml4fS0ke01hdGgucmFuZG9tKCkudG9TdHJpbmcoMzYpLnNsaWNlKDIsIDEwKX1gO1xyXG59XHJcblxyXG5mdW5jdGlvbiByYW5kb21EaWdpdHMobGVuZ3RoOiBudW1iZXIpOiBzdHJpbmcge1xyXG4gIGxldCB2YWx1ZSA9IFwiXCI7XHJcbiAgd2hpbGUgKHZhbHVlLmxlbmd0aCA8IGxlbmd0aCkge1xyXG4gICAgdmFsdWUgKz0gTWF0aC5mbG9vcihNYXRoLnJhbmRvbSgpICogMTApLnRvU3RyaW5nKCk7XHJcbiAgfVxyXG4gIHJldHVybiB2YWx1ZS5zbGljZSgwLCBsZW5ndGgpO1xyXG59XHJcblxyXG5mdW5jdGlvbiByZWFkTWVtYmVyQWNjb3VudHMoKTogU3RvcmVkTWVtYmVyQWNjb3VudFtdIHtcclxuICBjb25zdCBzZWVkZWQgPSBzZWVkTWVtYmVyQWNjb3VudHMoKTtcclxuICBjb25zdCBzdG9yZWQgPSByZWFkU3RvcmFnZTxTdG9yZWRNZW1iZXJBY2NvdW50W10+KE1FTUJFUl9BQ0NPVU5UU19LRVksIHNlZWRlZCk7XHJcbiAgaWYgKGlzQnJvd3NlcigpICYmICF3aW5kb3cubG9jYWxTdG9yYWdlLmdldEl0ZW0oTUVNQkVSX0FDQ09VTlRTX0tFWSkpIHtcclxuICAgIHdyaXRlU3RvcmFnZShNRU1CRVJfQUNDT1VOVFNfS0VZLCBzdG9yZWQpO1xyXG4gIH1cclxuICByZXR1cm4gc3RvcmVkO1xyXG59XHJcblxyXG5mdW5jdGlvbiB3cml0ZU1lbWJlckFjY291bnRzKGFjY291bnRzOiBTdG9yZWRNZW1iZXJBY2NvdW50W10pOiB2b2lkIHtcclxuICB3cml0ZVN0b3JhZ2UoTUVNQkVSX0FDQ09VTlRTX0tFWSwgYWNjb3VudHMpO1xyXG59XHJcblxyXG5mdW5jdGlvbiByZWFkTWVtYmVyU3RhdGVzKCk6IFJlY29yZDxzdHJpbmcsIFN0b3JlZE1lbWJlclN0YXRlPiB7XHJcbiAgY29uc3Qgc2VlZGVkID0gc2VlZE1lbWJlclN0YXRlcygpO1xyXG4gIGNvbnN0IHN0b3JlZCA9IHJlYWRTdG9yYWdlPFJlY29yZDxzdHJpbmcsIFN0b3JlZE1lbWJlclN0YXRlPj4oTUVNQkVSX1NUQVRFU19LRVksIHNlZWRlZCk7XHJcbiAgaWYgKGlzQnJvd3NlcigpICYmICF3aW5kb3cubG9jYWxTdG9yYWdlLmdldEl0ZW0oTUVNQkVSX1NUQVRFU19LRVkpKSB7XHJcbiAgICB3cml0ZVN0b3JhZ2UoTUVNQkVSX1NUQVRFU19LRVksIHN0b3JlZCk7XHJcbiAgfVxyXG4gIHJldHVybiBzdG9yZWQ7XHJcbn1cclxuXHJcbmZ1bmN0aW9uIHdyaXRlTWVtYmVyU3RhdGVzKHN0YXRlczogUmVjb3JkPHN0cmluZywgU3RvcmVkTWVtYmVyU3RhdGU+KTogdm9pZCB7XHJcbiAgd3JpdGVTdG9yYWdlKE1FTUJFUl9TVEFURVNfS0VZLCBzdGF0ZXMpO1xyXG59XHJcblxyXG5mdW5jdGlvbiByZWFkU2Vzc2lvbigpOiBINU1lbWJlclNlc3Npb24gfCBudWxsIHtcclxuICByZXR1cm4gcmVhZFN0b3JhZ2U8SDVNZW1iZXJTZXNzaW9uIHwgbnVsbD4oTUVNQkVSX1NFU1NJT05fS0VZLCBudWxsKTtcclxufVxyXG5cclxuZnVuY3Rpb24gd3JpdGVTZXNzaW9uKHNlc3Npb246IEg1TWVtYmVyU2Vzc2lvbiB8IG51bGwpOiB2b2lkIHtcclxuICBpZiAoIWlzQnJvd3NlcigpKSB7XHJcbiAgICByZXR1cm47XHJcbiAgfVxyXG4gIGlmIChzZXNzaW9uID09PSBudWxsKSB7XHJcbiAgICB3aW5kb3cubG9jYWxTdG9yYWdlLnJlbW92ZUl0ZW0oTUVNQkVSX1NFU1NJT05fS0VZKTtcclxuICAgIHJldHVybjtcclxuICB9XHJcbiAgd3JpdGVTdG9yYWdlKE1FTUJFUl9TRVNTSU9OX0tFWSwgc2Vzc2lvbik7XHJcbn1cclxuXHJcbmZ1bmN0aW9uIGJ1aWxkU2Vzc2lvbkZyb21BdXRoUGF5bG9hZChwYXlsb2FkOiBCYWNrZW5kTWVtYmVyQXV0aFJlc3BvbnNlKTogSDVNZW1iZXJTZXNzaW9uIHtcclxuICBjb25zdCBtZW1iZXJObyA9IHBheWxvYWQubWVtYmVyLm1lbWJlck5vPy50cmltKCkgfHwgcGF5bG9hZC5tZW1iZXIuYWNjb3VudElkO1xyXG4gIHJldHVybiB7XHJcbiAgICBhY2NvdW50SWQ6IG1lbWJlck5vLFxyXG4gICAgcGhvbmU6IHBheWxvYWQubWVtYmVyLnBob25lLFxyXG4gICAgcHVibGljVXNlcklkOiBwYXlsb2FkLm1lbWJlci5wdWJsaWNVc2VySWQsXHJcbiAgICBkaXNwbGF5TmFtZTogcGF5bG9hZC5tZW1iZXIuZGlzcGxheU5hbWU/LnRyaW0oKSB8fCBwYXlsb2FkLm1lbWJlci5wdWJsaWNVc2VySWQsXHJcbiAgICBpbnZpdGVDb2RlOiBwYXlsb2FkLm1lbWJlci5pbnZpdGVDb2RlPy50cmltKCkgfHwgZ2VuZXJhdGVJbnZpdGVDb2RlKG1lbWJlck5vKSxcclxuICAgIGF2YXRhclVybDogbnVsbCxcclxuICB9O1xyXG59XHJcblxyXG5mdW5jdGlvbiBidWlsZFByb2ZpbGVGcm9tQXV0aFBheWxvYWQocGF5bG9hZDogQmFja2VuZE1lbWJlckF1dGhSZXNwb25zZSk6IEg1TWVtYmVyUHJvZmlsZSB7XHJcbiAgY29uc3Qgc2Vzc2lvbiA9IGJ1aWxkU2Vzc2lvbkZyb21BdXRoUGF5bG9hZChwYXlsb2FkKTtcclxuICByZXR1cm4ge1xyXG4gICAgLi4uc2Vzc2lvbixcclxuICAgIGFjY291bnRJZE1hc2tlZDogcGF5bG9hZC5tZW1iZXIuYWNjb3VudElkTWFza2VkPy50cmltKCkgfHwgbWFza0FjY291bnRJZChzZXNzaW9uLmFjY291bnRJZCksXHJcbiAgICBjcmVhdGVkQXQ6IHBheWxvYWQubWVtYmVyLmNyZWF0ZWRBdCxcclxuICB9O1xyXG59XHJcblxyXG5mdW5jdGlvbiBzeW5jTGVnYWN5TWVtYmVyQ2FjaGVGcm9tUHJvZmlsZShwcm9maWxlOiBINU1lbWJlclByb2ZpbGUpOiB2b2lkIHtcclxuICBlbnN1cmVTZWVkZWRTdG9yYWdlKCk7XHJcbiAgY29uc3QgYWNjb3VudHMgPSByZWFkTWVtYmVyQWNjb3VudHMoKTtcclxuICBjb25zdCBleGlzdGluZyA9IGFjY291bnRzLmZpbmQoKGl0ZW0pID0+IGl0ZW0uYWNjb3VudElkID09PSBwcm9maWxlLmFjY291bnRJZCk7XHJcbiAgY29uc3QgbmV4dEFjY291bnQ6IFN0b3JlZE1lbWJlckFjY291bnQgPSB7XHJcbiAgICBpZDogZXhpc3Rpbmc/LmlkID8/IGNyZWF0ZUlkKFwibWVtYmVyXCIpLFxyXG4gICAgYWNjb3VudElkOiBwcm9maWxlLmFjY291bnRJZCxcclxuICAgIHBob25lOiBwcm9maWxlLnBob25lLFxyXG4gICAgcGFzc3dvcmQ6IGV4aXN0aW5nPy5wYXNzd29yZCA/PyBERUZBVUxUX01FTUJFUl9QQVNTV09SRCxcclxuICAgIHB1YmxpY1VzZXJJZDogcHJvZmlsZS5wdWJsaWNVc2VySWQsXHJcbiAgICBkaXNwbGF5TmFtZTogcHJvZmlsZS5kaXNwbGF5TmFtZSxcclxuICAgIGludml0ZUNvZGU6IHByb2ZpbGUuaW52aXRlQ29kZSxcclxuICAgIGNyZWF0ZWRBdDogcHJvZmlsZS5jcmVhdGVkQXQsXHJcbiAgICBhdmF0YXJVcmw6IGV4aXN0aW5nPy5hdmF0YXJVcmwgPz8gcHJvZmlsZS5hdmF0YXJVcmwgPz8gbnVsbCxcclxuICB9O1xyXG4gIGNvbnN0IG5leHRBY2NvdW50cyA9IGFjY291bnRzLmZpbHRlcigoaXRlbSkgPT4gaXRlbS5hY2NvdW50SWQgIT09IHByb2ZpbGUuYWNjb3VudElkKTtcclxuICBuZXh0QWNjb3VudHMucHVzaChuZXh0QWNjb3VudCk7XHJcbiAgd3JpdGVNZW1iZXJBY2NvdW50cyhuZXh0QWNjb3VudHMpO1xyXG5cclxuICBjb25zdCBzdGF0ZXMgPSByZWFkTWVtYmVyU3RhdGVzKCk7XHJcbiAgaWYgKCFzdGF0ZXNbcHJvZmlsZS5hY2NvdW50SWRdKSB7XHJcbiAgICBzdGF0ZXNbcHJvZmlsZS5hY2NvdW50SWRdID0gY2xvbmVTdGF0ZVRlbXBsYXRlKCk7XHJcbiAgICB3cml0ZU1lbWJlclN0YXRlcyhzdGF0ZXMpO1xyXG4gIH1cclxuXHJcbiAgd3JpdGVTZXNzaW9uKHtcclxuICAgIGFjY291bnRJZDogcHJvZmlsZS5hY2NvdW50SWQsXHJcbiAgICBwaG9uZTogcHJvZmlsZS5waG9uZSxcclxuICAgIHB1YmxpY1VzZXJJZDogcHJvZmlsZS5wdWJsaWNVc2VySWQsXHJcbiAgICBkaXNwbGF5TmFtZTogcHJvZmlsZS5kaXNwbGF5TmFtZSxcclxuICAgIGludml0ZUNvZGU6IHByb2ZpbGUuaW52aXRlQ29kZSxcclxuICAgIGF2YXRhclVybDogcHJvZmlsZS5hdmF0YXJVcmwgPz8gbmV4dEFjY291bnQuYXZhdGFyVXJsID8/IG51bGwsXHJcbiAgfSk7XHJcbn1cclxuXHJcbmZ1bmN0aW9uIG1hcFNpdGVCcmFuZEZyb21CYWNrZW5kKHNpdGU6IEJhY2tlbmRNZW1iZXJBdXRoUmVzcG9uc2VbXCJzaXRlXCJdKTogSDVTaXRlQnJhbmQge1xyXG4gIGNvbnN0IGJhc2UgPSBnZXRTaXRlQnJhbmQoc2l0ZS5zaXRlS2V5KTtcclxuICByZXR1cm4ge1xyXG4gICAgLi4uYmFzZSxcclxuICAgIHNpdGVfa2V5OiBzaXRlLnNpdGVLZXksXHJcbiAgICBicmFuZF9uYW1lOiBzaXRlLmJyYW5kTmFtZSxcclxuICB9O1xyXG59XHJcblxyXG5mdW5jdGlvbiBtYXBUYXNrUGFja2FnZUl0ZW1Gcm9tQmFja2VuZChcclxuICBpdGVtOiBCYWNrZW5kVGFza1BhY2thZ2VJdGVtUmVzcG9uc2UsXHJcbik6IEg1VGFza1BhY2thZ2VJdGVtIHtcclxuICByZXR1cm4ge1xyXG4gICAgaWQ6IGl0ZW0uaWQsXHJcbiAgICBwcm9kdWN0X25hbWU6IGl0ZW0ucHJvZHVjdE5hbWUsXHJcbiAgICBpbWFnZV91cmw6IGl0ZW0uaW1hZ2VVcmwgPz8gXCJcIixcclxuICAgIHByaWNlOiBpdGVtLnByaWNlLFxyXG4gICAgY3VycmVuY3k6IGl0ZW0uY3VycmVuY3ksXHJcbiAgICBjb21wbGV0ZWRfYXQ6IGl0ZW0uY29tcGxldGVkQXQsXHJcbiAgICBvcmRlcl9pZDogaXRlbS5vcmRlcklkLFxyXG4gIH07XHJcbn1cclxuXHJcbmZ1bmN0aW9uIG1hcFRhc2tQYWNrYWdlRnJvbUJhY2tlbmQoXHJcbiAgcGtnOiBCYWNrZW5kVGFza1BhY2thZ2VSZXNwb25zZSxcclxuKTogSDVUYXNrUGFja2FnZSAmIHtcclxuICB0b3RhbENvbW1pc3Npb246IG51bWJlcjtcclxuICBjdXJyZW50Q29tbWlzc2lvbjogbnVtYmVyO1xyXG4gIGNvbXBsZXRlZEl0ZW1zOiBudW1iZXI7XHJcbiAgdG90YWxJdGVtczogbnVtYmVyO1xyXG4gIGNvdW50ZG93blNlY29uZHM6IG51bWJlcjtcclxufSB7XHJcbiAgcmV0dXJuIHtcclxuICAgIGlkOiBwa2cuaWQsXHJcbiAgICB0aXRsZTogcGtnLnRpdGxlLFxyXG4gICAgZGVzY3JpcHRpb246IHBrZy5kZXNjcmlwdGlvbiA/PyBcIlwiLFxyXG4gICAgdHlwZTogcGtnLnR5cGUsXHJcbiAgICBzdGF0dXM6IHBrZy5zdGF0dXMsXHJcbiAgICByZXdhcmRSYXRpbzogcGtnLnJld2FyZFJhdGlvLFxyXG4gICAgY2xhaW1lZEF0OiBwa2cuY2xhaW1lZEF0LFxyXG4gICAgZXhwaXJlc0F0OiBwa2cuZXhwaXJlc0F0LFxyXG4gICAgZGlzcGF0Y2hlZEF0OiBwa2cuZGlzcGF0Y2hlZEF0LFxyXG4gICAgY29tcGxldGlvbldpbmRvd0hvdXJzOiBwa2cuY29tcGxldGlvbldpbmRvd0hvdXJzLFxyXG4gICAgaXRlbXM6IHBrZy5pdGVtcy5tYXAoKGl0ZW0pID0+IG1hcFRhc2tQYWNrYWdlSXRlbUZyb21CYWNrZW5kKGl0ZW0pKSxcclxuICAgIHByb21vdGlvbjogcGtnLnByb21vdGlvblxyXG4gICAgICA/IHtcclxuICAgICAgICAgIG1ldHJpYzogcGtnLnByb21vdGlvbi5tZXRyaWMsXHJcbiAgICAgICAgICBjdXJyZW50OiBwa2cucHJvbW90aW9uLmN1cnJlbnQsXHJcbiAgICAgICAgICB0YXJnZXQ6IHBrZy5wcm9tb3Rpb24udGFyZ2V0LFxyXG4gICAgICAgICAgaW52aXRlQ29kZTogcGtnLnByb21vdGlvbi5pbnZpdGVDb2RlID8/IFwiXCIsXHJcbiAgICAgICAgfVxyXG4gICAgICA6IG51bGwsXHJcbiAgICB0YXNrQmFsYW5jZUF3YXJkZWRBdDogcGtnLnRhc2tCYWxhbmNlQXdhcmRlZEF0LFxyXG4gICAgdG90YWxDb21taXNzaW9uOiBwa2cudG90YWxDb21taXNzaW9uLFxyXG4gICAgY3VycmVudENvbW1pc3Npb246IHBrZy5jdXJyZW50Q29tbWlzc2lvbixcclxuICAgIGNvbXBsZXRlZEl0ZW1zOiBwa2cuY29tcGxldGVkSXRlbXMsXHJcbiAgICB0b3RhbEl0ZW1zOiBwa2cudG90YWxJdGVtcyxcclxuICAgIGNvdW50ZG93blNlY29uZHM6IHBrZy5jb3VudGRvd25TZWNvbmRzLFxyXG4gIH07XHJcbn1cclxuXHJcbmZ1bmN0aW9uIG1hcFdhbGxldFN1bW1hcnlGcm9tQmFja2VuZChcclxuICB3YWxsZXQ6IEJhY2tlbmRXYWxsZXRTdW1tYXJ5UmVzcG9uc2UsXHJcbik6IEg1V2FsbGV0U3VtbWFyeSB7XHJcbiAgcmV0dXJuIHtcclxuICAgIHN5c3RlbUJhbGFuY2U6IHdhbGxldC5zeXN0ZW1CYWxhbmNlLFxyXG4gICAgdGFza0JhbGFuY2U6IHdhbGxldC50YXNrQmFsYW5jZSxcclxuICAgIGN1cnJlbmN5OiB3YWxsZXQuY3VycmVuY3ksXHJcbiAgICB3aXRoZHJhd1RocmVzaG9sZDogd2FsbGV0LndpdGhkcmF3VGhyZXNob2xkLFxyXG4gICAgY2FuV2l0aGRyYXc6IHdhbGxldC5jYW5XaXRoZHJhdyxcclxuICAgIHNob3J0ZmFsbEFtb3VudDogd2FsbGV0LnNob3J0ZmFsbEFtb3VudCxcclxuICB9O1xyXG59XHJcblxyXG5mdW5jdGlvbiBtYXBPcmRlckZyb21CYWNrZW5kKG9yZGVyOiBCYWNrZW5kTWVtYmVyT3JkZXJSZXNwb25zZSk6IEg1TWVtYmVyT3JkZXIge1xyXG4gIHJldHVybiB7XHJcbiAgICBpZDogb3JkZXIuaWQsXHJcbiAgICBvcmRlck5vOiBvcmRlci5vcmRlck5vLFxyXG4gICAgcGFja2FnZUlkOiBvcmRlci5wYWNrYWdlSWQgPz8gXCJcIixcclxuICAgIHBhY2thZ2VUaXRsZTogb3JkZXIucGFja2FnZVRpdGxlID8/IFwiXCIsXHJcbiAgICBwcm9kdWN0TmFtZTogb3JkZXIucHJvZHVjdE5hbWUsXHJcbiAgICBhbW91bnQ6IG9yZGVyLmFtb3VudCxcclxuICAgIGN1cnJlbmN5OiBvcmRlci5jdXJyZW5jeSxcclxuICAgIHN0YXR1czogb3JkZXIuc3RhdHVzLFxyXG4gICAgY3JlYXRlZEF0OiBvcmRlci5jcmVhdGVkQXQsXHJcbiAgICBzb3VyY2VMYWJlbDogb3JkZXIuc291cmNlTGFiZWwgPz8gXCJcIixcclxuICB9O1xyXG59XHJcblxyXG5mdW5jdGlvbiBtYXBXYWxsZXRUcmFuc2FjdGlvbkZyb21CYWNrZW5kKFxyXG4gIHRyYW5zYWN0aW9uOiBCYWNrZW5kV2FsbGV0VHJhbnNhY3Rpb25SZXNwb25zZSxcclxuKTogSDVXYWxsZXRUcmFuc2FjdGlvbiB7XHJcbiAgcmV0dXJuIHtcclxuICAgIGlkOiB0cmFuc2FjdGlvbi5pZCxcclxuICAgIGxlZGdlclR5cGU6IHRyYW5zYWN0aW9uLmxlZGdlclR5cGUsXHJcbiAgICB0cmFuc2FjdGlvblR5cGU6IHRyYW5zYWN0aW9uLnRyYW5zYWN0aW9uVHlwZSxcclxuICAgIGRpcmVjdGlvbjogdHJhbnNhY3Rpb24uZGlyZWN0aW9uLFxyXG4gICAgYW1vdW50OiB0cmFuc2FjdGlvbi5hbW91bnQsXHJcbiAgICBjdXJyZW5jeTogdHJhbnNhY3Rpb24uY3VycmVuY3ksXHJcbiAgICBzdGF0dXM6IHRyYW5zYWN0aW9uLnN0YXR1cyxcclxuICAgIG5vdGU6IHRyYW5zYWN0aW9uLm5vdGUgPz8gXCJcIixcclxuICAgIGNyZWF0ZWRBdDogdHJhbnNhY3Rpb24uY3JlYXRlZEF0LFxyXG4gIH07XHJcbn1cclxuXHJcbmZ1bmN0aW9uIG1hcFdpdGhkcmF3YWxGcm9tQmFja2VuZChcclxuICB3aXRoZHJhd2FsOiBCYWNrZW5kV2l0aGRyYXdhbFJlc3BvbnNlLFxyXG4pOiBINVdpdGhkcmF3UmVxdWVzdCB7XHJcbiAgcmV0dXJuIHtcclxuICAgIGlkOiB3aXRoZHJhd2FsLmlkLFxyXG4gICAgYW1vdW50OiB3aXRoZHJhd2FsLmFtb3VudCxcclxuICAgIGN1cnJlbmN5OiB3aXRoZHJhd2FsLmN1cnJlbmN5LFxyXG4gICAgc3RhdHVzOiB3aXRoZHJhd2FsLnN0YXR1cyxcclxuICAgIGNyZWF0ZWRBdDogd2l0aGRyYXdhbC5jcmVhdGVkQXQsXHJcbiAgfTtcclxufVxyXG5cclxuZnVuY3Rpb24gbWFwTGVhZGVyYm9hcmRFbnRyeUZyb21CYWNrZW5kKFxyXG4gIGVudHJ5OiBCYWNrZW5kV2l0aGRyYXdMZWFkZXJib2FyZFJlc3BvbnNlLFxyXG4pOiBINUxlYWRlcmJvYXJkRW50cnkge1xyXG4gIHJldHVybiB7XHJcbiAgICByYW5rOiBlbnRyeS5yYW5rLFxyXG4gICAgYWNjb3VudElkTWFza2VkOiBlbnRyeS5hY2NvdW50SWRNYXNrZWQsXHJcbiAgICBhbW91bnQ6IGVudHJ5LmFtb3VudCxcclxuICAgIGN1cnJlbmN5OiBlbnRyeS5jdXJyZW5jeSxcclxuICB9O1xyXG59XHJcblxyXG5mdW5jdGlvbiBtYXBNZXNzYWdlRnJvbUJhY2tlbmQobWVzc2FnZTogQmFja2VuZE1lbWJlck1lc3NhZ2VSZXNwb25zZSk6IEg1TWVzc2FnZUl0ZW0ge1xyXG4gIHJldHVybiB7XHJcbiAgICBpZDogbWVzc2FnZS5pZCxcclxuICAgIGNhdGVnb3J5OiBtZXNzYWdlLmNhdGVnb3J5LFxyXG4gICAgdGl0bGU6IG1lc3NhZ2UudGl0bGUsXHJcbiAgICBib2R5OiBtZXNzYWdlLmJvZHlUZXh0LFxyXG4gICAgY3JlYXRlZEF0OiBtZXNzYWdlLmNyZWF0ZWRBdCxcclxuICAgIGlzUmVhZDogbWVzc2FnZS5pc1JlYWQsXHJcbiAgfTtcclxufVxyXG5cclxuZnVuY3Rpb24gbWFwVmVyaWZpY2F0aW9uRG9jdW1lbnRGcm9tQmFja2VuZChcclxuICBkb2N1bWVudDogQmFja2VuZE1lbWJlclZlcmlmaWNhdGlvbkRvY3VtZW50UmVzcG9uc2UsXHJcbik6IEg1TWVtYmVyVmVyaWZpY2F0aW9uRG9jdW1lbnQge1xyXG4gIHJldHVybiB7XHJcbiAgICBpZDogZG9jdW1lbnQuaWQsXHJcbiAgICBmaWxlTmFtZTogZG9jdW1lbnQuZmlsZU5hbWUgPz8gZG9jdW1lbnQuZmlsZV9uYW1lID8/IFwiXCIsXHJcbiAgICBtaW1lVHlwZTogZG9jdW1lbnQubWltZVR5cGUgPz8gZG9jdW1lbnQubWltZV90eXBlID8/IG51bGwsXHJcbiAgICBzdG9yYWdlS2V5OiBkb2N1bWVudC5zdG9yYWdlS2V5ID8/IGRvY3VtZW50LnN0b3JhZ2Vfa2V5ID8/IG51bGwsXHJcbiAgICBtZXRhZGF0YUpzb246IGRvY3VtZW50Lm1ldGFkYXRhSnNvbiA/PyBkb2N1bWVudC5tZXRhZGF0YV9qc29uID8/IG51bGwsXHJcbiAgICBjcmVhdGVkQXQ6IGRvY3VtZW50LmNyZWF0ZWRBdCA/PyBkb2N1bWVudC5jcmVhdGVkX2F0ID8/IG5vd0lzbygpLFxyXG4gIH07XHJcbn1cclxuXHJcbmZ1bmN0aW9uIG1hcFZlcmlmaWNhdGlvblJlcXVlc3RGcm9tQmFja2VuZChcclxuICByZXF1ZXN0OiBCYWNrZW5kTWVtYmVyVmVyaWZpY2F0aW9uUmVxdWVzdFJlc3BvbnNlLFxyXG4pOiBINU1lbWJlclZlcmlmaWNhdGlvblJlcXVlc3Qge1xyXG4gIHJldHVybiB7XHJcbiAgICBpZDogcmVxdWVzdC5pZCxcclxuICAgIHJlcXVlc3RUeXBlOiByZXF1ZXN0LnJlcXVlc3RUeXBlID8/IHJlcXVlc3QucmVxdWVzdF90eXBlID8/IFwiXCIsXHJcbiAgICBzdGF0dXM6IHJlcXVlc3Quc3RhdHVzLFxyXG4gICAgbm90ZXM6IHJlcXVlc3Qubm90ZXMsXHJcbiAgICByZXZpZXdOb3RlOiByZXF1ZXN0LnJldmlld05vdGUgPz8gcmVxdWVzdC5yZXZpZXdfbm90ZSA/PyBudWxsLFxyXG4gICAgcmV2aWV3ZXJBY3RvcklkOiByZXF1ZXN0LnJldmlld2VyQWN0b3JJZCA/PyByZXF1ZXN0LnJldmlld2VyX2FjdG9yX2lkID8/IG51bGwsXHJcbiAgICByZXZpZXdlZEF0OiByZXF1ZXN0LnJldmlld2VkQXQgPz8gcmVxdWVzdC5yZXZpZXdlZF9hdCA/PyBudWxsLFxyXG4gICAgY3JlYXRlZEF0OiByZXF1ZXN0LmNyZWF0ZWRBdCA/PyByZXF1ZXN0LmNyZWF0ZWRfYXQgPz8gbm93SXNvKCksXHJcbiAgICB1cGRhdGVkQXQ6IHJlcXVlc3QudXBkYXRlZEF0ID8/IHJlcXVlc3QudXBkYXRlZF9hdCA/PyBub3dJc28oKSxcclxuICAgIGRvY3VtZW50czogcmVxdWVzdC5kb2N1bWVudHMubWFwKChpdGVtKSA9PiBtYXBWZXJpZmljYXRpb25Eb2N1bWVudEZyb21CYWNrZW5kKGl0ZW0pKSxcclxuICB9O1xyXG59XHJcblxyXG5mdW5jdGlvbiBtYXBWZXJpZmljYXRpb25TdW1tYXJ5RnJvbUJhY2tlbmQoXHJcbiAgc3VtbWFyeTogQmFja2VuZE1lbWJlclZlcmlmaWNhdGlvblN1bW1hcnlSZXNwb25zZSxcclxuKTogSDVNZW1iZXJWZXJpZmljYXRpb25TdW1tYXJ5IHtcclxuICByZXR1cm4ge1xyXG4gICAgY3VycmVudFN0YXR1czogc3VtbWFyeS5jdXJyZW50U3RhdHVzID8/IHN1bW1hcnkuY3VycmVudF9zdGF0dXMgPz8gXCJub3Rfc3VibWl0dGVkXCIsXHJcbiAgICBoYXNBY3RpdmVSZXF1ZXN0OiBzdW1tYXJ5Lmhhc0FjdGl2ZVJlcXVlc3QgPz8gc3VtbWFyeS5oYXNfYWN0aXZlX3JlcXVlc3QgPz8gZmFsc2UsXHJcbiAgICBhY3RpdmVSZXF1ZXN0OiAoc3VtbWFyeS5hY3RpdmVSZXF1ZXN0ID8/IHN1bW1hcnkuYWN0aXZlX3JlcXVlc3QpXHJcbiAgICAgID8gbWFwVmVyaWZpY2F0aW9uUmVxdWVzdEZyb21CYWNrZW5kKHN1bW1hcnkuYWN0aXZlUmVxdWVzdCA/PyBzdW1tYXJ5LmFjdGl2ZV9yZXF1ZXN0ISlcclxuICAgICAgOiBudWxsLFxyXG4gICAgaGlzdG9yeTogc3VtbWFyeS5oaXN0b3J5Lm1hcCgoaXRlbSkgPT4gbWFwVmVyaWZpY2F0aW9uUmVxdWVzdEZyb21CYWNrZW5kKGl0ZW0pKSxcclxuICB9O1xyXG59XHJcblxyXG5mdW5jdGlvbiBtYXBGcmFnbWVudERyb3BGcm9tQmFja2VuZChcclxuICBkcm9wOiBCYWNrZW5kRnJhZ21lbnREcm9wTG9nUmVzcG9uc2UsXHJcbik6IEg1RnJhZ21lbnREcm9wTG9nIHtcclxuICByZXR1cm4ge1xyXG4gICAgaWQ6IGRyb3AuaWQsXHJcbiAgICBmcmFnbWVudElkOiBkcm9wLmZyYWdtZW50SWQsXHJcbiAgICBmcmFnbWVudE5hbWU6IGRyb3AuZnJhZ21lbnROYW1lLFxyXG4gICAgc291cmNlOiBkcm9wLnNvdXJjZSxcclxuICAgIGNyZWF0ZWRBdDogZHJvcC5jcmVhdGVkQXQsXHJcbiAgfTtcclxufVxyXG5cclxuZnVuY3Rpb24gbWFwU2hpcHBpbmdBZGRyZXNzRnJvbUJhY2tlbmQoXHJcbiAgYWRkcmVzczogQmFja2VuZFJld2FyZFNoaXBwaW5nQWRkcmVzc1Jlc3BvbnNlLFxyXG4pOiBINVNoaXBwaW5nQWRkcmVzcyB7XHJcbiAgcmV0dXJuIHtcclxuICAgIHJlY2VpdmVyOiBhZGRyZXNzLnJlY2VpdmVyLFxyXG4gICAgcGhvbmU6IGFkZHJlc3MucGhvbmUsXHJcbiAgICBjb3VudHJ5OiBhZGRyZXNzLmNvdW50cnksXHJcbiAgICBwcm92aW5jZTogYWRkcmVzcy5wcm92aW5jZSxcclxuICAgIGNpdHk6IGFkZHJlc3MuY2l0eSxcclxuICAgIGFkZHJlc3NMaW5lOiBhZGRyZXNzLmFkZHJlc3NMaW5lLFxyXG4gIH07XHJcbn1cclxuXHJcbmZ1bmN0aW9uIG1hcFNoaXBwaW5nT3JkZXJGcm9tQmFja2VuZChcclxuICBvcmRlcjogQmFja2VuZFJld2FyZFNoaXBwaW5nT3JkZXJSZXNwb25zZSxcclxuKTogSDVSZXdhcmRTaGlwcGluZ09yZGVyIHtcclxuICByZXR1cm4ge1xyXG4gICAgaWQ6IG9yZGVyLmlkLFxyXG4gICAgcmV3YXJkTmFtZTogb3JkZXIucmV3YXJkTmFtZSxcclxuICAgIHN0YXR1czogb3JkZXIuc3RhdHVzLFxyXG4gICAgY3JlYXRlZEF0OiBvcmRlci5jcmVhdGVkQXQsXHJcbiAgICBhZGRyZXNzOiBvcmRlci5hZGRyZXNzID8gbWFwU2hpcHBpbmdBZGRyZXNzRnJvbUJhY2tlbmQob3JkZXIuYWRkcmVzcykgOiBudWxsLFxyXG4gIH07XHJcbn1cclxuXHJcbmZ1bmN0aW9uIG1hcEZyYWdtZW50T3ZlcnZpZXdGcm9tQmFja2VuZChcclxuICBvdmVydmlldzogQmFja2VuZEZyYWdtZW50T3ZlcnZpZXdSZXNwb25zZSxcclxuKTogSDVGcmFnbWVudE92ZXJ2aWV3IHtcclxuICByZXR1cm4ge1xyXG4gICAgaW52ZW50b3J5OiBvdmVydmlldy5pbnZlbnRvcnkubWFwKChpdGVtKSA9PiAoe1xyXG4gICAgICBpZDogaXRlbS5pZCxcclxuICAgICAgbmFtZTogaXRlbS5uYW1lLFxyXG4gICAgICByYXJpdHk6IGl0ZW0ucmFyaXR5LFxyXG4gICAgICBjb2xvcjogaXRlbS5jb2xvcixcclxuICAgICAgb3duZWQ6IGl0ZW0ub3duZWQsXHJcbiAgICAgIHJlcXVpcmVkOiBpdGVtLnJlcXVpcmVkLFxyXG4gICAgfSkpLFxyXG4gICAgZHJvcExvZ3M6IG92ZXJ2aWV3LmRyb3BMb2dzLm1hcCgoaXRlbSkgPT4gbWFwRnJhZ21lbnREcm9wRnJvbUJhY2tlbmQoaXRlbSkpLFxyXG4gICAgcmV3YXJkTmFtZTogb3ZlcnZpZXcucmV3YXJkTmFtZSxcclxuICAgIHNoaXBwaW5nT3JkZXJzOiBvdmVydmlldy5zaGlwcGluZ09yZGVycy5tYXAoKGl0ZW0pID0+IG1hcFNoaXBwaW5nT3JkZXJGcm9tQmFja2VuZChpdGVtKSksXHJcbiAgfTtcclxufVxyXG5cclxuZnVuY3Rpb24gZ2V0RW1wdHlIb21lRnJhZ21lbnRTdW1tYXJ5KCk6IEg1SG9tZUZyYWdtZW50U3VtbWFyeSB7XHJcbiAgcmV0dXJuIHtcclxuICAgIHJld2FyZE5hbWU6IG51bGwsXHJcbiAgICBjb21wbGV0ZWRDb3VudDogMCxcclxuICAgIHRvdGFsQ291bnQ6IDAsXHJcbiAgICBtaXNzaW5nQ291bnQ6IDAsXHJcbiAgICBjYW5FeGNoYW5nZTogZmFsc2UsXHJcbiAgICBzaGlwcGluZ09yZGVyQ291bnQ6IDAsXHJcbiAgICBsYXRlc3RTaGlwcGluZ1N0YXR1czogbnVsbCxcclxuICB9O1xyXG59XHJcblxyXG5mdW5jdGlvbiBnZXRFbXB0eUhvbWVWZXJpZmljYXRpb25TdW1tYXJ5KCk6IEg1SG9tZVZlcmlmaWNhdGlvblN1bW1hcnkge1xyXG4gIHJldHVybiB7XHJcbiAgICBjdXJyZW50U3RhdHVzOiBcIm5vdF9zdWJtaXR0ZWRcIixcclxuICAgIGhhc0FjdGl2ZVJlcXVlc3Q6IGZhbHNlLFxyXG4gIH07XHJcbn1cclxuXHJcbmZ1bmN0aW9uIGdldEVtcHR5VmVyaWZpY2F0aW9uU3VtbWFyeSgpOiBINU1lbWJlclZlcmlmaWNhdGlvblN1bW1hcnkge1xyXG4gIHJldHVybiB7XHJcbiAgICAuLi5nZXRFbXB0eUhvbWVWZXJpZmljYXRpb25TdW1tYXJ5KCksXHJcbiAgICBhY3RpdmVSZXF1ZXN0OiBudWxsLFxyXG4gICAgaGlzdG9yeTogW10sXHJcbiAgfTtcclxufVxyXG5cclxuZnVuY3Rpb24gbWFwSG9tZVZlcmlmaWNhdGlvblN1bW1hcnlGcm9tQmFja2VuZChcclxuICBzdW1tYXJ5OiBCYWNrZW5kTWVtYmVySG9tZVJlc3BvbnNlW1widmVyaWZpY2F0aW9uXCJdLFxyXG4pOiBINUhvbWVWZXJpZmljYXRpb25TdW1tYXJ5IHtcclxuICBpZiAoIXN1bW1hcnkpIHtcclxuICAgIHJldHVybiBnZXRFbXB0eUhvbWVWZXJpZmljYXRpb25TdW1tYXJ5KCk7XHJcbiAgfVxyXG4gIHJldHVybiB7XHJcbiAgICBjdXJyZW50U3RhdHVzOiBzdW1tYXJ5LmN1cnJlbnRTdGF0dXMsXHJcbiAgICBoYXNBY3RpdmVSZXF1ZXN0OiBzdW1tYXJ5Lmhhc0FjdGl2ZVJlcXVlc3QsXHJcbiAgfTtcclxufVxyXG5cclxuZnVuY3Rpb24gYnVpbGRWZXJpZmljYXRpb25TdW1tYXJ5RnJvbVJlcXVlc3RzKFxyXG4gIHJlcXVlc3RzOiBINU1lbWJlclZlcmlmaWNhdGlvblJlcXVlc3RbXSxcclxuKTogSDVNZW1iZXJWZXJpZmljYXRpb25TdW1tYXJ5IHtcclxuICBpZiAocmVxdWVzdHMubGVuZ3RoID09PSAwKSB7XHJcbiAgICByZXR1cm4gZ2V0RW1wdHlWZXJpZmljYXRpb25TdW1tYXJ5KCk7XHJcbiAgfVxyXG4gIGNvbnN0IHNvcnRlZCA9IFsuLi5yZXF1ZXN0c10uc29ydCgobGVmdCwgcmlnaHQpID0+IHJpZ2h0LmNyZWF0ZWRBdC5sb2NhbGVDb21wYXJlKGxlZnQuY3JlYXRlZEF0KSk7XHJcbiAgY29uc3QgYWN0aXZlUmVxdWVzdCA9IHNvcnRlZC5maW5kKChpdGVtKSA9PiBpdGVtLnN0YXR1cyA9PT0gXCJwZW5kaW5nXCIpID8/IG51bGw7XHJcbiAgcmV0dXJuIHtcclxuICAgIGN1cnJlbnRTdGF0dXM6IGFjdGl2ZVJlcXVlc3Q/LnN0YXR1cyA/PyBzb3J0ZWRbMF0/LnN0YXR1cyA/PyBcIm5vdF9zdWJtaXR0ZWRcIixcclxuICAgIGhhc0FjdGl2ZVJlcXVlc3Q6IGFjdGl2ZVJlcXVlc3QgIT09IG51bGwsXHJcbiAgICBhY3RpdmVSZXF1ZXN0LFxyXG4gICAgaGlzdG9yeTogc29ydGVkLFxyXG4gIH07XHJcbn1cclxuXHJcbmZ1bmN0aW9uIGJ1aWxkSG9tZVZlcmlmaWNhdGlvblN1bW1hcnlGcm9tU3RhdGUoXHJcbiAgc3RhdGU6IFN0b3JlZE1lbWJlclN0YXRlLFxyXG4pOiBINUhvbWVWZXJpZmljYXRpb25TdW1tYXJ5IHtcclxuICBjb25zdCBzdW1tYXJ5ID0gYnVpbGRWZXJpZmljYXRpb25TdW1tYXJ5RnJvbVJlcXVlc3RzKHN0YXRlLnZlcmlmaWNhdGlvblJlcXVlc3RzID8/IFtdKTtcclxuICByZXR1cm4ge1xyXG4gICAgY3VycmVudFN0YXR1czogc3VtbWFyeS5jdXJyZW50U3RhdHVzLFxyXG4gICAgaGFzQWN0aXZlUmVxdWVzdDogc3VtbWFyeS5oYXNBY3RpdmVSZXF1ZXN0LFxyXG4gIH07XHJcbn1cclxuXHJcbmZ1bmN0aW9uIG1hcEhvbWVGcmFnbWVudFN1bW1hcnlGcm9tQmFja2VuZChcclxuICBzdW1tYXJ5OiBCYWNrZW5kTWVtYmVySG9tZVJlc3BvbnNlW1wiZnJhZ21lbnRzXCJdLFxyXG4pOiBINUhvbWVGcmFnbWVudFN1bW1hcnkge1xyXG4gIGlmICghc3VtbWFyeSkge1xyXG4gICAgcmV0dXJuIGdldEVtcHR5SG9tZUZyYWdtZW50U3VtbWFyeSgpO1xyXG4gIH1cclxuICByZXR1cm4ge1xyXG4gICAgcmV3YXJkTmFtZTogc3VtbWFyeS5yZXdhcmROYW1lLFxyXG4gICAgY29tcGxldGVkQ291bnQ6IHN1bW1hcnkuY29tcGxldGVkQ291bnQsXHJcbiAgICB0b3RhbENvdW50OiBzdW1tYXJ5LnRvdGFsQ291bnQsXHJcbiAgICBtaXNzaW5nQ291bnQ6IHN1bW1hcnkubWlzc2luZ0NvdW50LFxyXG4gICAgY2FuRXhjaGFuZ2U6IHN1bW1hcnkuY2FuRXhjaGFuZ2UsXHJcbiAgICBzaGlwcGluZ09yZGVyQ291bnQ6IHN1bW1hcnkuc2hpcHBpbmdPcmRlckNvdW50LFxyXG4gICAgbGF0ZXN0U2hpcHBpbmdTdGF0dXM6IHN1bW1hcnkubGF0ZXN0U2hpcHBpbmdTdGF0dXMsXHJcbiAgfTtcclxufVxyXG5cclxuZnVuY3Rpb24gYnVpbGRIb21lRnJhZ21lbnRTdW1tYXJ5RnJvbU92ZXJ2aWV3KFxyXG4gIG92ZXJ2aWV3OiBINUZyYWdtZW50T3ZlcnZpZXcsXHJcbik6IEg1SG9tZUZyYWdtZW50U3VtbWFyeSB7XHJcbiAgY29uc3QgY29tcGxldGVkQ291bnQgPSBvdmVydmlldy5pbnZlbnRvcnkuZmlsdGVyKChpdGVtKSA9PiBpdGVtLm93bmVkID49IGl0ZW0ucmVxdWlyZWQpLmxlbmd0aDtcclxuICBjb25zdCB0b3RhbENvdW50ID0gb3ZlcnZpZXcuaW52ZW50b3J5Lmxlbmd0aDtcclxuICBjb25zdCBtaXNzaW5nQ291bnQgPSBvdmVydmlldy5pbnZlbnRvcnkucmVkdWNlKFxyXG4gICAgKHN1bSwgaXRlbSkgPT4gc3VtICsgTWF0aC5tYXgoMCwgaXRlbS5yZXF1aXJlZCAtIGl0ZW0ub3duZWQpLFxyXG4gICAgMCxcclxuICApO1xyXG4gIHJldHVybiB7XHJcbiAgICByZXdhcmROYW1lOiBvdmVydmlldy5yZXdhcmROYW1lLFxyXG4gICAgY29tcGxldGVkQ291bnQsXHJcbiAgICB0b3RhbENvdW50LFxyXG4gICAgbWlzc2luZ0NvdW50LFxyXG4gICAgY2FuRXhjaGFuZ2U6IHRvdGFsQ291bnQgPiAwICYmIGNvbXBsZXRlZENvdW50ID09PSB0b3RhbENvdW50LFxyXG4gICAgc2hpcHBpbmdPcmRlckNvdW50OiBvdmVydmlldy5zaGlwcGluZ09yZGVycy5sZW5ndGgsXHJcbiAgICBsYXRlc3RTaGlwcGluZ1N0YXR1czogb3ZlcnZpZXcuc2hpcHBpbmdPcmRlcnNbMF0/LnN0YXR1cyA/PyBudWxsLFxyXG4gIH07XHJcbn1cclxuXHJcbmZ1bmN0aW9uIG1hcFdoYXRzQXBwQmluZGluZ0Zyb21CYWNrZW5kKFxyXG4gIGJpbmRpbmc6IEJhY2tlbmRXaGF0c0FwcEJpbmRpbmdSZXNwb25zZSxcclxuKTogSDVXaGF0c0FwcEJpbmRpbmcge1xyXG4gIHJldHVybiB7XHJcbiAgICBpc0JvdW5kOiBiaW5kaW5nLmlzQm91bmQsXHJcbiAgICBiaW5kaW5nU3RhdHVzOiBiaW5kaW5nLmJpbmRpbmdTdGF0dXMgPz8gKGJpbmRpbmcuaXNCb3VuZCA/IFwiYm91bmRcIiA6IFwibm90X3N0YXJ0ZWRcIiksXHJcbiAgICByZXF1ZXN0SWQ6IGJpbmRpbmcucmVxdWVzdElkID8/IG51bGwsXHJcbiAgICBwaG9uZU51bWJlcjogYmluZGluZy5waG9uZU51bWJlcixcclxuICAgIHJlcXVlc3RlZEF0OiBiaW5kaW5nLnJlcXVlc3RlZEF0ID8/IG51bGwsXHJcbiAgICBzdGFydENvdW50OiBiaW5kaW5nLnN0YXJ0Q291bnQgPz8gMCxcclxuICAgIGxhc3RVcGRhdGVkQXQ6IGJpbmRpbmcubGFzdFVwZGF0ZWRBdCxcclxuICB9O1xyXG59XHJcblxyXG5mdW5jdGlvbiBzZWVkTWVtYmVyQWNjb3VudHMoKTogU3RvcmVkTWVtYmVyQWNjb3VudFtdIHtcclxuICByZXR1cm4gW1xyXG4gICAge1xyXG4gICAgICBpZDogXCJtZW1iZXItZGVtby0xXCIsXHJcbiAgICAgIGFjY291bnRJZDogXCIzODI3MTQ1NlwiLFxyXG4gICAgICBwaG9uZTogREVGQVVMVF9NRU1CRVJfUEhPTkUsXHJcbiAgICAgIHBhc3N3b3JkOiBERUZBVUxUX01FTUJFUl9QQVNTV09SRCxcclxuICAgICAgcHVibGljVXNlcklkOiBcImg1LTM4MjcxNDU2XCIsXHJcbiAgICAgIGRpc3BsYXlOYW1lOiBnZXRTZWVkRGF0YVRleHQoXCJtZW1iZXJEaXNwbGF5TmFtZVwiKSxcclxuICAgICAgaW52aXRlQ29kZTogXCJJTlYzODI3MTQ1NlwiLFxyXG4gICAgICBjcmVhdGVkQXQ6IG5vd0lzbygpLFxyXG4gICAgfSxcclxuICBdO1xyXG59XHJcblxyXG5mdW5jdGlvbiBjcmVhdGVQYWNrYWdlSXRlbShwYWNrYWdlSWQ6IHN0cmluZywgaW5kZXg6IG51bWJlciwgcHJpY2U6IG51bWJlcik6IEg1VGFza1BhY2thZ2VJdGVtIHtcclxuICByZXR1cm4ge1xyXG4gICAgaWQ6IGAke3BhY2thZ2VJZH0taXRlbS0ke2luZGV4ICsgMX1gLFxyXG4gICAgcHJvZHVjdF9uYW1lOiBgVGFzayBQcm9kdWN0ICR7aW5kZXggKyAxfWAsXHJcbiAgICBpbWFnZV91cmw6IGBodHRwczovL3BpY3N1bS5waG90b3Mvc2VlZC8ke3BhY2thZ2VJZH0tJHtpbmRleCArIDF9LzE2MC8xNjBgLFxyXG4gICAgcHJpY2UsXHJcbiAgICBjdXJyZW5jeTogXCJVU0RcIixcclxuICAgIGNvbXBsZXRlZF9hdDogbnVsbCxcclxuICAgIG9yZGVyX2lkOiBudWxsLFxyXG4gIH07XHJcbn1cclxuXHJcbmZ1bmN0aW9uIHNlZWRUYXNrUGFja2FnZXMoKTogSDVUYXNrUGFja2FnZVtdIHtcclxuICBjb25zdCBub3cgPSBEYXRlLm5vdygpO1xyXG4gIGNvbnN0IGFjdGl2ZUNsYWltZWRBdCA9IG5ldyBEYXRlKG5vdyAtIDEwMDAgKiA2MCAqIDYwICogMykudG9JU09TdHJpbmcoKTtcclxuICBjb25zdCBhY3RpdmVFeHBpcmVzQXQgPSBuZXcgRGF0ZShub3cgKyAxMDAwICogNjAgKiA2MCAqIDE4KS50b0lTT1N0cmluZygpO1xyXG4gIHJldHVybiBbXHJcbiAgICB7XHJcbiAgICAgIGlkOiBcInBrZy1yb29raWUtMVwiLFxyXG4gICAgICB0aXRsZTogZ2V0U2VlZERhdGFUZXh0KFwicGFja2FnZVJvb2tpZVRpdGxlXCIpLFxyXG4gICAgICBkZXNjcmlwdGlvbjogZ2V0U2VlZERhdGFUZXh0KFwicGFja2FnZVJvb2tpZURlc2NyaXB0aW9uXCIpLFxyXG4gICAgICB0eXBlOiBcInJvb2tpZVwiLFxyXG4gICAgICBzdGF0dXM6IFwicGVuZGluZ19jbGFpbVwiLFxyXG4gICAgICByZXdhcmRSYXRpbzogMC4xOCxcclxuICAgICAgY2xhaW1lZEF0OiBudWxsLFxyXG4gICAgICBleHBpcmVzQXQ6IG51bGwsXHJcbiAgICAgIGRpc3BhdGNoZWRBdDogbm93SXNvKCksXHJcbiAgICAgIGNvbXBsZXRpb25XaW5kb3dIb3VyczogMjQsXHJcbiAgICAgIGl0ZW1zOiBbMTgsIDIyLCAyNiwgMzEsIDM1XS5tYXAoKHByaWNlLCBpbmRleCkgPT4gY3JlYXRlUGFja2FnZUl0ZW0oXCJwa2ctcm9va2llLTFcIiwgaW5kZXgsIHByaWNlKSksXHJcbiAgICAgIHByb21vdGlvbjogbnVsbCxcclxuICAgICAgdGFza0JhbGFuY2VBd2FyZGVkQXQ6IG51bGwsXHJcbiAgICB9LFxyXG4gICAge1xyXG4gICAgICBpZDogXCJwa2ctZ3Jvd3RoLTFcIixcclxuICAgICAgdGl0bGU6IGdldFNlZWREYXRhVGV4dChcInBhY2thZ2VHcm93dGhUaXRsZVwiKSxcclxuICAgICAgZGVzY3JpcHRpb246IGdldFNlZWREYXRhVGV4dChcInBhY2thZ2VHcm93dGhEZXNjcmlwdGlvblwiKSxcclxuICAgICAgdHlwZTogXCJncm93dGhcIixcclxuICAgICAgc3RhdHVzOiBcImFjdGl2ZVwiLFxyXG4gICAgICByZXdhcmRSYXRpbzogMC4yNCxcclxuICAgICAgY2xhaW1lZEF0OiBhY3RpdmVDbGFpbWVkQXQsXHJcbiAgICAgIGV4cGlyZXNBdDogYWN0aXZlRXhwaXJlc0F0LFxyXG4gICAgICBkaXNwYXRjaGVkQXQ6IG5vd0lzbygpLFxyXG4gICAgICBjb21wbGV0aW9uV2luZG93SG91cnM6IDI0LFxyXG4gICAgICBpdGVtczogWzI5LCAzMywgMzYsIDQyLCA0OF0ubWFwKChwcmljZSwgaW5kZXgpID0+IGNyZWF0ZVBhY2thZ2VJdGVtKFwicGtnLWdyb3d0aC0xXCIsIGluZGV4LCBwcmljZSkpLFxyXG4gICAgICBwcm9tb3Rpb246IG51bGwsXHJcbiAgICAgIHRhc2tCYWxhbmNlQXdhcmRlZEF0OiBudWxsLFxyXG4gICAgfSxcclxuICAgIHtcclxuICAgICAgaWQ6IFwicGtnLXByb21vdGlvbi0xXCIsXHJcbiAgICAgIHRpdGxlOiBnZXRTZWVkRGF0YVRleHQoXCJwYWNrYWdlUHJvbW90aW9uVGl0bGVcIiksXHJcbiAgICAgIGRlc2NyaXB0aW9uOiBnZXRTZWVkRGF0YVRleHQoXCJwYWNrYWdlUHJvbW90aW9uRGVzY3JpcHRpb25cIiksXHJcbiAgICAgIHR5cGU6IFwicHJvbW90aW9uXCIsXHJcbiAgICAgIHN0YXR1czogXCJwZW5kaW5nX2NsYWltXCIsXHJcbiAgICAgIHJld2FyZFJhdGlvOiAwLjEyLFxyXG4gICAgICBjbGFpbWVkQXQ6IG51bGwsXHJcbiAgICAgIGV4cGlyZXNBdDogbnVsbCxcclxuICAgICAgZGlzcGF0Y2hlZEF0OiBub3dJc28oKSxcclxuICAgICAgY29tcGxldGlvbldpbmRvd0hvdXJzOiAyNCxcclxuICAgICAgaXRlbXM6IFtdLFxyXG4gICAgICBwcm9tb3Rpb246IHtcclxuICAgICAgICBtZXRyaWM6IFwiaW52aXRlZF9yZWdpc3RyYXRpb25zXCIsXHJcbiAgICAgICAgY3VycmVudDogMyxcclxuICAgICAgICB0YXJnZXQ6IDEwLFxyXG4gICAgICAgIGludml0ZUNvZGU6IFwiUFJPTU8tMzgyNzE0NTZcIixcclxuICAgICAgfSxcclxuICAgICAgdGFza0JhbGFuY2VBd2FyZGVkQXQ6IG51bGwsXHJcbiAgICB9LFxyXG4gIF07XHJcbn1cclxuXHJcbmZ1bmN0aW9uIHNlZWRUcmFuc2FjdGlvbnMoKTogSDVXYWxsZXRUcmFuc2FjdGlvbltdIHtcclxuICByZXR1cm4gW1xyXG4gICAge1xyXG4gICAgICBpZDogXCJ3YWxsZXQtcmVjaGFyZ2Utc2VlZFwiLFxyXG4gICAgICBsZWRnZXJUeXBlOiBcInN5c3RlbVwiLFxyXG4gICAgICB0cmFuc2FjdGlvblR5cGU6IFwicmVjaGFyZ2VcIixcclxuICAgICAgZGlyZWN0aW9uOiBcImNyZWRpdFwiLFxyXG4gICAgICBhbW91bnQ6IDMwMCxcclxuICAgICAgY3VycmVuY3k6IFwiVVNEXCIsXHJcbiAgICAgIHN0YXR1czogXCJwYWlkXCIsXHJcbiAgICAgIG5vdGU6IFwiUHJvdG90eXBlIHRvcC11cFwiLFxyXG4gICAgICBjcmVhdGVkQXQ6IG5ldyBEYXRlKERhdGUubm93KCkgLSAxMDAwICogNjAgKiA2MCAqIDEyKS50b0lTT1N0cmluZygpLFxyXG4gICAgfSxcclxuICAgIHtcclxuICAgICAgaWQ6IFwid2FsbGV0LXRhc2stc2VlZFwiLFxyXG4gICAgICBsZWRnZXJUeXBlOiBcInRhc2tcIixcclxuICAgICAgdHJhbnNhY3Rpb25UeXBlOiBcInRhc2tfcmV3YXJkXCIsXHJcbiAgICAgIGRpcmVjdGlvbjogXCJjcmVkaXRcIixcclxuICAgICAgYW1vdW50OiA4OCxcclxuICAgICAgY3VycmVuY3k6IFwiVVNEXCIsXHJcbiAgICAgIHN0YXR1czogXCJwYWlkXCIsXHJcbiAgICAgIG5vdGU6IFwiUHJldmlvdXMgY29tcGxldGVkIHRhc2sgcGFja2FnZSByZXdhcmRcIixcclxuICAgICAgY3JlYXRlZEF0OiBuZXcgRGF0ZShEYXRlLm5vdygpIC0gMTAwMCAqIDYwICogNjAgKiA2KS50b0lTT1N0cmluZygpLFxyXG4gICAgfSxcclxuICAgIHtcclxuICAgICAgaWQ6IFwid2FsbGV0LXdpdGhkcmF3LXNlZWRcIixcclxuICAgICAgbGVkZ2VyVHlwZTogXCJzeXN0ZW1cIixcclxuICAgICAgdHJhbnNhY3Rpb25UeXBlOiBcIndpdGhkcmF3X3BhaWRcIixcclxuICAgICAgZGlyZWN0aW9uOiBcImRlYml0XCIsXHJcbiAgICAgIGFtb3VudDogMTIwLFxyXG4gICAgICBjdXJyZW5jeTogXCJVU0RcIixcclxuICAgICAgc3RhdHVzOiBcInBhaWRcIixcclxuICAgICAgbm90ZTogXCJQcmV2aW91cyBwYWlkIHdpdGhkcmF3YWxcIixcclxuICAgICAgY3JlYXRlZEF0OiBuZXcgRGF0ZShEYXRlLm5vdygpIC0gMTAwMCAqIDYwICogNjAgKiAzKS50b0lTT1N0cmluZygpLFxyXG4gICAgfSxcclxuICBdO1xyXG59XHJcblxyXG5mdW5jdGlvbiBzZWVkTWVzc2FnZXMoKTogSDVNZXNzYWdlSXRlbVtdIHtcclxuICByZXR1cm4gW1xyXG4gICAge1xyXG4gICAgICBpZDogXCJtc2ctdGFzay0xXCIsXHJcbiAgICAgIGNhdGVnb3J5OiBcInRhc2tcIixcclxuICAgICAgdGl0bGU6IGdldFNlZWREYXRhVGV4dChcIm1lc3NhZ2VUYXNrVGl0bGVcIiksXHJcbiAgICAgIGJvZHk6IGdldFNlZWREYXRhVGV4dChcIm1lc3NhZ2VUYXNrQm9keVwiKSxcclxuICAgICAgY3JlYXRlZEF0OiBuZXcgRGF0ZShEYXRlLm5vdygpIC0gMTAwMCAqIDYwICogNjAgKiA0KS50b0lTT1N0cmluZygpLFxyXG4gICAgICBpc1JlYWQ6IGZhbHNlLFxyXG4gICAgfSxcclxuICAgIHtcclxuICAgICAgaWQ6IFwibXNnLXdhbGxldC0xXCIsXHJcbiAgICAgIGNhdGVnb3J5OiBcIndhbGxldFwiLFxyXG4gICAgICB0aXRsZTogZ2V0U2VlZERhdGFUZXh0KFwibWVzc2FnZVdhbGxldFRpdGxlXCIpLFxyXG4gICAgICBib2R5OiBnZXRTZWVkRGF0YVRleHQoXCJtZXNzYWdlV2FsbGV0Qm9keVwiKSxcclxuICAgICAgY3JlYXRlZEF0OiBuZXcgRGF0ZShEYXRlLm5vdygpIC0gMTAwMCAqIDYwICogNjAgKiAyKS50b0lTT1N0cmluZygpLFxyXG4gICAgICBpc1JlYWQ6IGZhbHNlLFxyXG4gICAgfSxcclxuICAgIHtcclxuICAgICAgaWQ6IFwibXNnLWZyYWdtZW50LTFcIixcclxuICAgICAgY2F0ZWdvcnk6IFwiZnJhZ21lbnRcIixcclxuICAgICAgdGl0bGU6IGdldFNlZWREYXRhVGV4dChcIm1lc3NhZ2VGcmFnbWVudFRpdGxlXCIpLFxyXG4gICAgICBib2R5OiBnZXRTZWVkRGF0YVRleHQoXCJtZXNzYWdlRnJhZ21lbnRCb2R5XCIpLFxyXG4gICAgICBjcmVhdGVkQXQ6IG5ldyBEYXRlKERhdGUubm93KCkgLSAxMDAwICogNjAgKiAzMCkudG9JU09TdHJpbmcoKSxcclxuICAgICAgaXNSZWFkOiB0cnVlLFxyXG4gICAgfSxcclxuICBdO1xyXG59XHJcblxyXG5mdW5jdGlvbiBzZWVkTWVtYmVyU3RhdGVzKCk6IFJlY29yZDxzdHJpbmcsIFN0b3JlZE1lbWJlclN0YXRlPiB7XHJcbiAgcmV0dXJuIHtcclxuICAgIFwiMzgyNzE0NTZcIjoge1xyXG4gICAgICB3YWxsZXQ6IHtcclxuICAgICAgICBzeXN0ZW1CYWxhbmNlOiA0MjAsXHJcbiAgICAgICAgdGFza0JhbGFuY2U6IDg4LFxyXG4gICAgICAgIGN1cnJlbmN5OiBcIlVTRFwiLFxyXG4gICAgICAgIHdpdGhkcmF3VGhyZXNob2xkOiBERUZBVUxUX1dJVEhEUkFXX1RIUkVTSE9MRCxcclxuICAgICAgfSxcclxuICAgICAgdGFza1BhY2thZ2VzOiBzZWVkVGFza1BhY2thZ2VzKCksXHJcbiAgICAgIG9yZGVyczogW1xyXG4gICAgICAgIHtcclxuICAgICAgICAgIGlkOiBcIm9yZGVyLXNlZWQtMVwiLFxyXG4gICAgICAgICAgb3JkZXJObzogXCJPUkQtMTAwMDFcIixcclxuICAgICAgICAgIHBhY2thZ2VJZDogXCJwa2ctZ3Jvd3RoLTFcIixcclxuICAgICAgICAgIHBhY2thZ2VUaXRsZTogZ2V0U2VlZERhdGFUZXh0KFwicGFja2FnZUdyb3d0aFRpdGxlXCIpLFxyXG4gICAgICAgICAgcHJvZHVjdE5hbWU6IFwiVGFzayBQcm9kdWN0IDFcIixcclxuICAgICAgICAgIGFtb3VudDogMjksXHJcbiAgICAgICAgICBjdXJyZW5jeTogXCJVU0RcIixcclxuICAgICAgICAgIHN0YXR1czogXCJwYWlkXCIsXHJcbiAgICAgICAgICBjcmVhdGVkQXQ6IG5ldyBEYXRlKERhdGUubm93KCkgLSAxMDAwICogNjAgKiA2MCAqIDIpLnRvSVNPU3RyaW5nKCksXHJcbiAgICAgICAgICBzb3VyY2VMYWJlbDogZ2V0U2VlZERhdGFUZXh0KFwicGFja2FnZUdyb3d0aFRpdGxlXCIpLFxyXG4gICAgICAgIH0sXHJcbiAgICAgIF0sXHJcbiAgICAgIHRyYW5zYWN0aW9uczogc2VlZFRyYW5zYWN0aW9ucygpLFxyXG4gICAgICB3aXRoZHJhd1JlcXVlc3RzOiBbXHJcbiAgICAgICAge1xyXG4gICAgICAgICAgaWQ6IFwid2l0aGRyYXctc2VlZC0xXCIsXHJcbiAgICAgICAgICBhbW91bnQ6IDEyMCxcclxuICAgICAgICAgIGN1cnJlbmN5OiBcIlVTRFwiLFxyXG4gICAgICAgICAgc3RhdHVzOiBcInBhaWRcIixcclxuICAgICAgICAgIGNyZWF0ZWRBdDogbmV3IERhdGUoRGF0ZS5ub3coKSAtIDEwMDAgKiA2MCAqIDYwICogMykudG9JU09TdHJpbmcoKSxcclxuICAgICAgICB9LFxyXG4gICAgICBdLFxyXG4gICAgICBtZXNzYWdlczogc2VlZE1lc3NhZ2VzKCksXHJcbiAgICAgIGZyYWdtZW50SW52ZW50b3J5OiB7XHJcbiAgICAgICAgXCJmcmFnbWVudC1zdW5cIjogMSxcclxuICAgICAgICBcImZyYWdtZW50LW1vb25cIjogMCxcclxuICAgICAgICBcImZyYWdtZW50LXN0YXJcIjogMixcclxuICAgICAgfSxcclxuICAgICAgZnJhZ21lbnREcm9wTG9nczogW1xyXG4gICAgICAgIHtcclxuICAgICAgICAgIGlkOiBcImRyb3Atc2VlZC0xXCIsXHJcbiAgICAgICAgICBmcmFnbWVudElkOiBcImZyYWdtZW50LXN0YXJcIixcclxuICAgICAgICAgIGZyYWdtZW50TmFtZTogZ2V0U2VlZERhdGFUZXh0KFwiZnJhZ21lbnRTdGFyTmFtZVwiKSxcclxuICAgICAgICAgIHNvdXJjZTogXCJ0YXNrXCIsXHJcbiAgICAgICAgICBjcmVhdGVkQXQ6IG5ldyBEYXRlKERhdGUubm93KCkgLSAxMDAwICogNjAgKiAyMCkudG9JU09TdHJpbmcoKSxcclxuICAgICAgICB9LFxyXG4gICAgICBdLFxyXG4gICAgICBzaGlwcGluZ09yZGVyczogW1xyXG4gICAgICAgIHtcclxuICAgICAgICAgIGlkOiBcInNoaXBwaW5nLXNlZWQtMVwiLFxyXG4gICAgICAgICAgcmV3YXJkTmFtZTogZ2V0U2VlZERhdGFUZXh0KFwicmV3YXJkTmFtZVwiKSxcclxuICAgICAgICAgIHN0YXR1czogXCJzaGlwcGVkXCIsXHJcbiAgICAgICAgICBjcmVhdGVkQXQ6IG5ldyBEYXRlKERhdGUubm93KCkgLSAxMDAwICogNjAgKiA2MCAqIDQ4KS50b0lTT1N0cmluZygpLFxyXG4gICAgICAgICAgYWRkcmVzczoge1xyXG4gICAgICAgICAgICByZWNlaXZlcjogXCJEZW1vIFVzZXJcIixcclxuICAgICAgICAgICAgcGhvbmU6IFwiMTM4MDAwMDAwMDBcIixcclxuICAgICAgICAgICAgY291bnRyeTogXCJDaGluYVwiLFxyXG4gICAgICAgICAgICBwcm92aW5jZTogXCJHdWFuZ2RvbmdcIixcclxuICAgICAgICAgICAgY2l0eTogXCJTaGVuemhlblwiLFxyXG4gICAgICAgICAgICBhZGRyZXNzTGluZTogXCJOYW5zaGFuIFNjaWVuY2UgUGFya1wiLFxyXG4gICAgICAgICAgfSxcclxuICAgICAgICB9LFxyXG4gICAgICBdLFxyXG4gICAgICBjaGVja2VkSW5EYXRlOiBudWxsLFxyXG4gICAgICB2ZXJpZmljYXRpb25SZXF1ZXN0czogW10sXHJcbiAgICAgIHdoYXRzYXBwQmluZGluZzoge1xyXG4gICAgICAgIGlzQm91bmQ6IGZhbHNlLFxyXG4gICAgICAgIGJpbmRpbmdTdGF0dXM6IFwibm90X3N0YXJ0ZWRcIixcclxuICAgICAgICByZXF1ZXN0SWQ6IG51bGwsXHJcbiAgICAgICAgcGhvbmVOdW1iZXI6IG51bGwsXHJcbiAgICAgICAgcmVxdWVzdGVkQXQ6IG51bGwsXHJcbiAgICAgICAgc3RhcnRDb3VudDogMCxcclxuICAgICAgICBsYXN0VXBkYXRlZEF0OiBudWxsLFxyXG4gICAgICB9LFxyXG4gICAgfSxcclxuICB9O1xyXG59XHJcblxyXG5mdW5jdGlvbiBnZXRTaXRlQnJhbmQoc2l0ZUtleTogc3RyaW5nIHwgdW5kZWZpbmVkKTogSDVTaXRlQnJhbmQge1xyXG4gIGlmIChzaXRlS2V5ID09PSBcImZsYXNoLXNhbGVcIikge1xyXG4gICAgcmV0dXJuIHtcclxuICAgICAgc2l0ZV9rZXk6IFwiZmxhc2gtc2FsZVwiLFxyXG4gICAgICBicmFuZF9uYW1lOiBcIkZsYXNoIFNhbGUgSHViXCIsXHJcbiAgICAgIHRhZ2xpbmU6IFwiRmFzdCBvcmRlcnMsIGZhc3QgcmV3YXJkcy5cIixcclxuICAgICAgYWNjZW50X2NvbG9yOiBcIiMxNDU5YzdcIixcclxuICAgIH07XHJcbiAgfVxyXG4gIGlmIChzaXRlS2V5ID09PSBcImRhaWx5LWNuXCIpIHtcclxuICAgIHJldHVybiB7XHJcbiAgICAgIHNpdGVfa2V5OiBcImRhaWx5LWNuXCIsXHJcbiAgICAgIGJyYW5kX25hbWU6IFwiRGFpbHkgTWVtYmVyIENsdWJcIixcclxuICAgICAgdGFnbGluZTogXCJDaGVjayBpbiwgY29sbGVjdCBmcmFnbWVudHMsIHVubG9jayByZXdhcmRzLlwiLFxyXG4gICAgICBhY2NlbnRfY29sb3I6IFwiIzBmNzY2ZVwiLFxyXG4gICAgfTtcclxuICB9XHJcbiAgcmV0dXJuIHtcclxuICAgIHNpdGVfa2V5OiBzaXRlS2V5Py50cmltKCkgfHwgXCJtYWxsLWNuXCIsXHJcbiAgICBicmFuZF9uYW1lOiBcIk1lbWJlciBSZXdhcmRzIENlbnRlclwiLFxyXG4gICAgdGFnbGluZTogXCJUYXNrIHBhY2thZ2VzLCB3YWxsZXQsIHN1cHBvcnQsIGFuZCBmcmFnbWVudHMgaW4gb25lIHBsYWNlLlwiLFxyXG4gICAgYWNjZW50X2NvbG9yOiBcIiMxNjc3ZmZcIixcclxuICB9O1xyXG59XHJcblxyXG5mdW5jdGlvbiBjbG9uZVN0YXRlVGVtcGxhdGUoKTogU3RvcmVkTWVtYmVyU3RhdGUge1xyXG4gIGNvbnN0IHNlZWRlZCA9IHNlZWRNZW1iZXJTdGF0ZXMoKVtcIjM4MjcxNDU2XCJdO1xyXG4gIHJldHVybiBKU09OLnBhcnNlKEpTT04uc3RyaW5naWZ5KHNlZWRlZCkpIGFzIFN0b3JlZE1lbWJlclN0YXRlO1xyXG59XHJcblxyXG5mdW5jdGlvbiBlbnN1cmVTZWVkZWRTdG9yYWdlKCk6IHZvaWQge1xyXG4gIHJlYWRNZW1iZXJBY2NvdW50cygpO1xyXG4gIHJlYWRNZW1iZXJTdGF0ZXMoKTtcclxufVxyXG5cclxuZnVuY3Rpb24gZ2V0UmVxdWlyZWRTZXNzaW9uKCk6IEg1TWVtYmVyU2Vzc2lvbiB7XHJcbiAgZW5zdXJlU2VlZGVkU3RvcmFnZSgpO1xyXG4gIGNvbnN0IHNlc3Npb24gPSByZWFkU2Vzc2lvbigpO1xyXG4gIGlmICghc2Vzc2lvbikge1xyXG4gICAgdGhyb3cgY3JlYXRlU2VydmljZUVycm9yKFwiYXV0aFJlcXVpcmVkXCIpO1xyXG4gIH1cclxuICByZXR1cm4gc2Vzc2lvbjtcclxufVxyXG5cclxuZnVuY3Rpb24gZ2V0U3RhdGVGb3JBY2NvdW50KGFjY291bnRJZDogc3RyaW5nKTogU3RvcmVkTWVtYmVyU3RhdGUge1xyXG4gIGVuc3VyZVNlZWRlZFN0b3JhZ2UoKTtcclxuICBjb25zdCBzdGF0ZXMgPSByZWFkTWVtYmVyU3RhdGVzKCk7XHJcbiAgY29uc3QgZXhpc3RpbmcgPSBzdGF0ZXNbYWNjb3VudElkXTtcclxuICBpZiAoZXhpc3RpbmcpIHtcclxuICAgIGNvbnN0IG5vcm1hbGl6ZWQgPSBub3JtYWxpemVNZW1iZXJTdGF0ZShleGlzdGluZyk7XHJcbiAgICBzdGF0ZXNbYWNjb3VudElkXSA9IG5vcm1hbGl6ZWQ7XHJcbiAgICB3cml0ZU1lbWJlclN0YXRlcyhzdGF0ZXMpO1xyXG4gICAgcmV0dXJuIG5vcm1hbGl6ZWQ7XHJcbiAgfVxyXG4gIGNvbnN0IG5leHQgPSBjbG9uZVN0YXRlVGVtcGxhdGUoKTtcclxuICBzdGF0ZXNbYWNjb3VudElkXSA9IG5leHQ7XHJcbiAgd3JpdGVNZW1iZXJTdGF0ZXMoc3RhdGVzKTtcclxuICByZXR1cm4gbmV4dDtcclxufVxyXG5cclxuZnVuY3Rpb24gdXBkYXRlU3RhdGVGb3JBY2NvdW50KFxyXG4gIGFjY291bnRJZDogc3RyaW5nLFxyXG4gIHVwZGF0ZXI6IChzdGF0ZTogU3RvcmVkTWVtYmVyU3RhdGUpID0+IFN0b3JlZE1lbWJlclN0YXRlLFxyXG4pOiBTdG9yZWRNZW1iZXJTdGF0ZSB7XHJcbiAgY29uc3Qgc3RhdGVzID0gcmVhZE1lbWJlclN0YXRlcygpO1xyXG4gIGNvbnN0IGN1cnJlbnQgPSBnZXRTdGF0ZUZvckFjY291bnQoYWNjb3VudElkKTtcclxuICBjb25zdCBuZXh0ID0gbm9ybWFsaXplTWVtYmVyU3RhdGUodXBkYXRlcihKU09OLnBhcnNlKEpTT04uc3RyaW5naWZ5KGN1cnJlbnQpKSBhcyBTdG9yZWRNZW1iZXJTdGF0ZSkpO1xyXG4gIHN0YXRlc1thY2NvdW50SWRdID0gbmV4dDtcclxuICB3cml0ZU1lbWJlclN0YXRlcyhzdGF0ZXMpO1xyXG4gIHJldHVybiBuZXh0O1xyXG59XHJcblxyXG5mdW5jdGlvbiBub3JtYWxpemVNZW1iZXJTdGF0ZShzdGF0ZTogU3RvcmVkTWVtYmVyU3RhdGUpOiBTdG9yZWRNZW1iZXJTdGF0ZSB7XHJcbiAgc3RhdGUudmVyaWZpY2F0aW9uUmVxdWVzdHMgPSBzdGF0ZS52ZXJpZmljYXRpb25SZXF1ZXN0cyA/PyBbXTtcclxuICBjb25zdCBub3cgPSBEYXRlLm5vdygpO1xyXG4gIHN0YXRlLnRhc2tQYWNrYWdlcyA9IHN0YXRlLnRhc2tQYWNrYWdlcy5tYXAoKHBrZykgPT4ge1xyXG4gICAgaWYgKHBrZy5zdGF0dXMgPT09IFwiYWN0aXZlXCIgJiYgcGtnLmV4cGlyZXNBdCAmJiBuZXcgRGF0ZShwa2cuZXhwaXJlc0F0KS5nZXRUaW1lKCkgPD0gbm93KSB7XHJcbiAgICAgIHJldHVybiB7IC4uLnBrZywgc3RhdHVzOiBcImV4cGlyZWRcIiB9O1xyXG4gICAgfVxyXG4gICAgcmV0dXJuIHBrZztcclxuICB9KTtcclxuICByZXR1cm4gc3RhdGU7XHJcbn1cclxuXHJcbmZ1bmN0aW9uIGNhbGN1bGF0ZVBhY2thZ2VUb3RhbENvbW1pc3Npb24ocGtnOiBINVRhc2tQYWNrYWdlKTogbnVtYmVyIHtcclxuICByZXR1cm4gTnVtYmVyKFxyXG4gICAgcGtnLml0ZW1zLnJlZHVjZSgoc3VtLCBpdGVtKSA9PiBzdW0gKyBpdGVtLnByaWNlLCAwKSAqIHBrZy5yZXdhcmRSYXRpbyxcclxuICApO1xyXG59XHJcblxyXG5mdW5jdGlvbiBjYWxjdWxhdGVQYWNrYWdlQ3VycmVudENvbW1pc3Npb24ocGtnOiBINVRhc2tQYWNrYWdlKTogbnVtYmVyIHtcclxuICByZXR1cm4gTnVtYmVyKFxyXG4gICAgcGtnLml0ZW1zXHJcbiAgICAgIC5maWx0ZXIoKGl0ZW0pID0+IGl0ZW0uY29tcGxldGVkX2F0KVxyXG4gICAgICAucmVkdWNlKChzdW0sIGl0ZW0pID0+IHN1bSArIGl0ZW0ucHJpY2UsIDApICogcGtnLnJld2FyZFJhdGlvLFxyXG4gICk7XHJcbn1cclxuXHJcbmZ1bmN0aW9uIGdldENvbXBsZXRlZEl0ZW1Db3VudChwa2c6IEg1VGFza1BhY2thZ2UpOiBudW1iZXIge1xyXG4gIHJldHVybiBwa2cuaXRlbXMuZmlsdGVyKChpdGVtKSA9PiBpdGVtLmNvbXBsZXRlZF9hdCkubGVuZ3RoO1xyXG59XHJcblxyXG5mdW5jdGlvbiBtYXBUYXNrUGFja2FnZShwa2c6IEg1VGFza1BhY2thZ2UpOiBINVRhc2tQYWNrYWdlICYge1xyXG4gIHRvdGFsQ29tbWlzc2lvbjogbnVtYmVyO1xyXG4gIGN1cnJlbnRDb21taXNzaW9uOiBudW1iZXI7XHJcbiAgY29tcGxldGVkSXRlbXM6IG51bWJlcjtcclxuICB0b3RhbEl0ZW1zOiBudW1iZXI7XHJcbiAgY291bnRkb3duU2Vjb25kczogbnVtYmVyO1xyXG59IHtcclxuICBjb25zdCBjb3VudGRvd25TZWNvbmRzID0gcGtnLmV4cGlyZXNBdFxyXG4gICAgPyBNYXRoLm1heCgwLCBNYXRoLnJvdW5kKChuZXcgRGF0ZShwa2cuZXhwaXJlc0F0KS5nZXRUaW1lKCkgLSBEYXRlLm5vdygpKSAvIDEwMDApKVxyXG4gICAgOiBwa2cuY29tcGxldGlvbldpbmRvd0hvdXJzICogMzYwMDtcclxuICByZXR1cm4ge1xyXG4gICAgLi4ucGtnLFxyXG4gICAgdG90YWxDb21taXNzaW9uOiBjYWxjdWxhdGVQYWNrYWdlVG90YWxDb21taXNzaW9uKHBrZyksXHJcbiAgICBjdXJyZW50Q29tbWlzc2lvbjogY2FsY3VsYXRlUGFja2FnZUN1cnJlbnRDb21taXNzaW9uKHBrZyksXHJcbiAgICBjb21wbGV0ZWRJdGVtczogZ2V0Q29tcGxldGVkSXRlbUNvdW50KHBrZyksXHJcbiAgICB0b3RhbEl0ZW1zOiBwa2cuaXRlbXMubGVuZ3RoLFxyXG4gICAgY291bnRkb3duU2Vjb25kcyxcclxuICB9O1xyXG59XHJcblxyXG5mdW5jdGlvbiBnZXRVbnJlYWRNZXNzYWdlQ291bnQobWVzc2FnZXM6IEg1TWVzc2FnZUl0ZW1bXSk6IG51bWJlciB7XHJcbiAgcmV0dXJuIG1lc3NhZ2VzLmZpbHRlcigoaXRlbSkgPT4gIWl0ZW0uaXNSZWFkKS5sZW5ndGg7XHJcbn1cclxuXHJcbmZ1bmN0aW9uIGdldFdhbGxldFN1bW1hcnlGcm9tU3RhdGUoc3RhdGU6IFN0b3JlZE1lbWJlclN0YXRlKTogSDVXYWxsZXRTdW1tYXJ5IHtcclxuICBjb25zdCBzaG9ydGZhbGwgPSBNYXRoLm1heCgwLCBzdGF0ZS53YWxsZXQud2l0aGRyYXdUaHJlc2hvbGQgLSBzdGF0ZS53YWxsZXQuc3lzdGVtQmFsYW5jZSk7XHJcbiAgcmV0dXJuIHtcclxuICAgIHN5c3RlbUJhbGFuY2U6IE51bWJlcihzdGF0ZS53YWxsZXQuc3lzdGVtQmFsYW5jZS50b0ZpeGVkKDIpKSxcclxuICAgIHRhc2tCYWxhbmNlOiBOdW1iZXIoc3RhdGUud2FsbGV0LnRhc2tCYWxhbmNlLnRvRml4ZWQoMikpLFxyXG4gICAgY3VycmVuY3k6IHN0YXRlLndhbGxldC5jdXJyZW5jeSxcclxuICAgIHdpdGhkcmF3VGhyZXNob2xkOiBzdGF0ZS53YWxsZXQud2l0aGRyYXdUaHJlc2hvbGQsXHJcbiAgICBjYW5XaXRoZHJhdzogc2hvcnRmYWxsID09PSAwLFxyXG4gICAgc2hvcnRmYWxsQW1vdW50OiBOdW1iZXIoc2hvcnRmYWxsLnRvRml4ZWQoMikpLFxyXG4gIH07XHJcbn1cclxuXHJcbmZ1bmN0aW9uIGdldEZyYWdtZW50RGVmaW5pdGlvbnMoKTogSDVGcmFnbWVudERlZmluaXRpb25bXSB7XHJcbiAgcmV0dXJuIFtcclxuICAgIHsgaWQ6IFwiZnJhZ21lbnQtc3VuXCIsIG5hbWU6IGdldFNlZWREYXRhVGV4dChcImZyYWdtZW50U3VuTmFtZVwiKSwgcmFyaXR5OiBcImNvbW1vblwiLCBjb2xvcjogXCIjZjU5ZTBiXCIgfSxcclxuICAgIHsgaWQ6IFwiZnJhZ21lbnQtbW9vblwiLCBuYW1lOiBnZXRTZWVkRGF0YVRleHQoXCJmcmFnbWVudE1vb25OYW1lXCIpLCByYXJpdHk6IFwicmFyZVwiLCBjb2xvcjogXCIjNjM2NmYxXCIgfSxcclxuICAgIHsgaWQ6IFwiZnJhZ21lbnQtc3RhclwiLCBuYW1lOiBnZXRTZWVkRGF0YVRleHQoXCJmcmFnbWVudFN0YXJOYW1lXCIpLCByYXJpdHk6IFwiZXBpY1wiLCBjb2xvcjogXCIjZWY0NDQ0XCIgfSxcclxuICBdO1xyXG59XHJcblxyXG5mdW5jdGlvbiBidWlsZEZyYWdtZW50T3ZlcnZpZXcoc3RhdGU6IFN0b3JlZE1lbWJlclN0YXRlKTogSDVGcmFnbWVudE92ZXJ2aWV3IHtcclxuICByZXR1cm4ge1xyXG4gICAgaW52ZW50b3J5OiBnZXRGcmFnbWVudERlZmluaXRpb25zKCkubWFwKChmcmFnbWVudCkgPT4gKHtcclxuICAgICAgLi4uZnJhZ21lbnQsXHJcbiAgICAgIG93bmVkOiBzdGF0ZS5mcmFnbWVudEludmVudG9yeVtmcmFnbWVudC5pZF0gPz8gMCxcclxuICAgICAgcmVxdWlyZWQ6IDEsXHJcbiAgICB9KSksXHJcbiAgICBkcm9wTG9nczogWy4uLnN0YXRlLmZyYWdtZW50RHJvcExvZ3NdLnNvcnQoKGxlZnQsIHJpZ2h0KSA9PiByaWdodC5jcmVhdGVkQXQubG9jYWxlQ29tcGFyZShsZWZ0LmNyZWF0ZWRBdCkpLFxyXG4gICAgcmV3YXJkTmFtZTogZ2V0U2VlZERhdGFUZXh0KFwicmV3YXJkTmFtZVwiKSxcclxuICAgIHNoaXBwaW5nT3JkZXJzOiBbLi4uc3RhdGUuc2hpcHBpbmdPcmRlcnNdLnNvcnQoKGxlZnQsIHJpZ2h0KSA9PiByaWdodC5jcmVhdGVkQXQubG9jYWxlQ29tcGFyZShsZWZ0LmNyZWF0ZWRBdCkpLFxyXG4gIH07XHJcbn1cclxuXHJcbmZ1bmN0aW9uIGFwcGVuZE1lc3NhZ2Uoc3RhdGU6IFN0b3JlZE1lbWJlclN0YXRlLCBjYXRlZ29yeTogSDVNZXNzYWdlQ2F0ZWdvcnksIHRpdGxlOiBzdHJpbmcsIGJvZHk6IHN0cmluZyk6IHZvaWQge1xyXG4gIHN0YXRlLm1lc3NhZ2VzLnVuc2hpZnQoe1xyXG4gICAgaWQ6IGNyZWF0ZUlkKFwibXNnXCIpLFxyXG4gICAgY2F0ZWdvcnksXHJcbiAgICB0aXRsZSxcclxuICAgIGJvZHksXHJcbiAgICBjcmVhdGVkQXQ6IG5vd0lzbygpLFxyXG4gICAgaXNSZWFkOiBmYWxzZSxcclxuICB9KTtcclxufVxyXG5cclxuZnVuY3Rpb24gYXBwZW5kTG9jYWxpemVkTWVzc2FnZShcclxuICBzdGF0ZTogU3RvcmVkTWVtYmVyU3RhdGUsXHJcbiAgY2F0ZWdvcnk6IEg1TWVzc2FnZUNhdGVnb3J5LFxyXG4gIHRpdGxlS2V5OiBzdHJpbmcsXHJcbiAgYm9keUtleTogc3RyaW5nLFxyXG4gIG9wdGlvbnM/OiB7XHJcbiAgICB0aXRsZVBhcmFtcz86IFJlY29yZDxzdHJpbmcsIHN0cmluZyB8IG51bWJlcj47XHJcbiAgICBib2R5UGFyYW1zPzogUmVjb3JkPHN0cmluZywgc3RyaW5nIHwgbnVtYmVyPjtcclxuICB9LFxyXG4pOiB2b2lkIHtcclxuICBhcHBlbmRNZXNzYWdlKFxyXG4gICAgc3RhdGUsXHJcbiAgICBjYXRlZ29yeSxcclxuICAgIGdldFNlcnZpY2VNZXNzYWdlKHRpdGxlS2V5LCBvcHRpb25zPy50aXRsZVBhcmFtcyksXHJcbiAgICBnZXRTZXJ2aWNlTWVzc2FnZShib2R5S2V5LCBvcHRpb25zPy5ib2R5UGFyYW1zKSxcclxuICApO1xyXG59XHJcblxyXG5mdW5jdGlvbiBhcHBlbmRUcmFuc2FjdGlvbihcclxuICBzdGF0ZTogU3RvcmVkTWVtYmVyU3RhdGUsXHJcbiAgdHJhbnNhY3Rpb246IE9taXQ8SDVXYWxsZXRUcmFuc2FjdGlvbiwgXCJpZFwiIHwgXCJjcmVhdGVkQXRcIj4sXHJcbik6IHZvaWQge1xyXG4gIHN0YXRlLnRyYW5zYWN0aW9ucy51bnNoaWZ0KHtcclxuICAgIGlkOiBjcmVhdGVJZChcInR4blwiKSxcclxuICAgIGNyZWF0ZWRBdDogbm93SXNvKCksXHJcbiAgICAuLi50cmFuc2FjdGlvbixcclxuICB9KTtcclxufVxyXG5cclxuZnVuY3Rpb24gbWFza1Bob25lKHBob25lOiBzdHJpbmcpOiBzdHJpbmcge1xyXG4gIGlmIChwaG9uZS5sZW5ndGggPCA3KSB7XHJcbiAgICByZXR1cm4gcGhvbmU7XHJcbiAgfVxyXG4gIHJldHVybiBgJHtwaG9uZS5zbGljZSgwLCAzKX0qKioqJHtwaG9uZS5zbGljZSgtNCl9YDtcclxufVxyXG5cclxuZXhwb3J0IGZ1bmN0aW9uIG1hc2tBY2NvdW50SWQoYWNjb3VudElkOiBzdHJpbmcpOiBzdHJpbmcge1xyXG4gIGlmIChhY2NvdW50SWQubGVuZ3RoIDw9IDUpIHtcclxuICAgIHJldHVybiBhY2NvdW50SWQ7XHJcbiAgfVxyXG4gIHJldHVybiBgJHthY2NvdW50SWQuc2xpY2UoMCwgMyl9KioqJHthY2NvdW50SWQuc2xpY2UoLTIpfWA7XHJcbn1cclxuXHJcbmZ1bmN0aW9uIHRvZGF5S2V5KCk6IHN0cmluZyB7XHJcbiAgcmV0dXJuIG5ldyBEYXRlKCkudG9JU09TdHJpbmcoKS5zbGljZSgwLCAxMCk7XHJcbn1cclxuXHJcbmZ1bmN0aW9uIGdlbmVyYXRlSW52aXRlQ29kZShhY2NvdW50SWQ6IHN0cmluZyk6IHN0cmluZyB7XHJcbiAgcmV0dXJuIGBJTlYke2FjY291bnRJZH1gO1xyXG59XHJcblxyXG5mdW5jdGlvbiBnZW5lcmF0ZVVuaXF1ZU51bWVyaWNBY2NvdW50SWQoKTogc3RyaW5nIHtcclxuICBjb25zdCBleGlzdGluZyA9IG5ldyBTZXQocmVhZE1lbWJlckFjY291bnRzKCkubWFwKChpdGVtKSA9PiBpdGVtLmFjY291bnRJZCkpO1xyXG4gIGxldCBjYW5kaWRhdGUgPSByYW5kb21EaWdpdHMoQUNDT1VOVF9JRF9MRU5HVEgpO1xyXG4gIHdoaWxlIChleGlzdGluZy5oYXMoY2FuZGlkYXRlKSkge1xyXG4gICAgY2FuZGlkYXRlID0gcmFuZG9tRGlnaXRzKEFDQ09VTlRfSURfTEVOR1RIKTtcclxuICB9XHJcbiAgcmV0dXJuIGNhbmRpZGF0ZTtcclxufVxyXG5cclxuZnVuY3Rpb24gZ2V0TGVhZGVyYm9hcmRCYXNlRW50cmllcygpOiBBcnJheTx7IGFjY291bnRJZDogc3RyaW5nOyBhbW91bnQ6IG51bWJlcjsgY3VycmVuY3k6IHN0cmluZyB9PiB7XHJcbiAgcmV0dXJuIFtcclxuICAgIHsgYWNjb3VudElkOiBcIjEyODY0NDcyXCIsIGFtb3VudDogNTIwMCwgY3VycmVuY3k6IFwiVVNEXCIgfSxcclxuICAgIHsgYWNjb3VudElkOiBcIjg3MzQyMTU1XCIsIGFtb3VudDogNDc2MCwgY3VycmVuY3k6IFwiVVNEXCIgfSxcclxuICAgIHsgYWNjb3VudElkOiBcIjU0MDIxODYzXCIsIGFtb3VudDogMzk4MCwgY3VycmVuY3k6IFwiVVNEXCIgfSxcclxuICAgIHsgYWNjb3VudElkOiBcIjc0MTkwNTM4XCIsIGFtb3VudDogMzUxMCwgY3VycmVuY3k6IFwiVVNEXCIgfSxcclxuICBdO1xyXG59XHJcblxyXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gZ2V0Q3VycmVudE1lbWJlclNlc3Npb24oKTogUHJvbWlzZTxINU1lbWJlclNlc3Npb24gfCBudWxsPiB7XHJcbiAgLy8gU2hvcnQtY2lyY3VpdDogaWYgbm8gSDUgc2Vzc2lvbiBleGlzdHMgaW4gc3RvcmFnZSwgc2tpcCB0aGUgbmV0d29yayBwcm9iZS5cclxuICAvLyBUaGlzIHByZXZlbnRzIGEgc3B1cmlvdXMgNDAxIEdFVCAvYXBpL2g1L2F1dGgvbWUgaW4gYWRtaW4tY29uc29sZSBjb250ZXh0LlxyXG4gIGNvbnN0IHN0b3JlZCA9IHJlYWRTZXNzaW9uKCk7XHJcbiAgaWYgKCFzdG9yZWQpIHtcclxuICAgIGlmIChpc0xlZ2FjeUZhbGxiYWNrRW5hYmxlZCgpKSB7XHJcbiAgICAgIGVuc3VyZVNlZWRlZFN0b3JhZ2UoKTtcclxuICAgICAgcmV0dXJuIHJlYWRTZXNzaW9uKCk7XHJcbiAgICB9XHJcbiAgICByZXR1cm4gbnVsbDtcclxuICB9XHJcbiAgY29uc3QgYXV0aFJlc3BvbnNlID0gYXdhaXQgdHJ5QmFja2VuZEF1dGhSZXF1ZXN0PEJhY2tlbmRNZW1iZXJBdXRoUmVzcG9uc2U+KCgpID0+XHJcbiAgICByZXF1ZXN0SnNvbihcIi9hcGkvaDUvYXV0aC9tZVwiKSxcclxuICAgIHtcclxuICAgICAgYWxsb3dSZWZyZXNoOiB0cnVlLFxyXG4gICAgfSxcclxuICApO1xyXG4gIGlmIChhdXRoUmVzcG9uc2UgPT09IFwidW5hdXRoZW50aWNhdGVkXCIpIHtcclxuICAgIHdyaXRlU2Vzc2lvbihudWxsKTtcclxuICAgIHJldHVybiBudWxsO1xyXG4gIH1cclxuICBpZiAoYXV0aFJlc3BvbnNlKSB7XHJcbiAgICBjb25zdCBwcm9maWxlID0gYnVpbGRQcm9maWxlRnJvbUF1dGhQYXlsb2FkKGF1dGhSZXNwb25zZSk7XHJcbiAgICBzeW5jTGVnYWN5TWVtYmVyQ2FjaGVGcm9tUHJvZmlsZShwcm9maWxlKTtcclxuICAgIHJldHVybiB7XHJcbiAgICAgIGFjY291bnRJZDogcHJvZmlsZS5hY2NvdW50SWQsXHJcbiAgICAgIHBob25lOiBwcm9maWxlLnBob25lLFxyXG4gICAgICBwdWJsaWNVc2VySWQ6IHByb2ZpbGUucHVibGljVXNlcklkLFxyXG4gICAgICBkaXNwbGF5TmFtZTogcHJvZmlsZS5kaXNwbGF5TmFtZSxcclxuICAgICAgaW52aXRlQ29kZTogcHJvZmlsZS5pbnZpdGVDb2RlLFxyXG4gICAgfTtcclxuICB9XHJcbiAgaWYgKCFpc0xlZ2FjeUZhbGxiYWNrRW5hYmxlZCgpKSB7XHJcbiAgICB0aHJvdyBnZXRCYWNrZW5kVW5hdmFpbGFibGVFcnJvcigpO1xyXG4gIH1cclxuICBlbnN1cmVTZWVkZWRTdG9yYWdlKCk7XHJcbiAgcmV0dXJuIHJlYWRTZXNzaW9uKCk7XHJcbn1cclxuXHJcbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBnZXRDdXJyZW50TWVtYmVyUHJvZmlsZSgpOiBQcm9taXNlPEg1TWVtYmVyUHJvZmlsZSB8IG51bGw+IHtcclxuICBjb25zdCBhdXRoUmVzcG9uc2UgPSBhd2FpdCB0cnlCYWNrZW5kQXV0aFJlcXVlc3Q8QmFja2VuZE1lbWJlckF1dGhSZXNwb25zZT4oKCkgPT5cclxuICAgIHJlcXVlc3RKc29uKFwiL2FwaS9oNS9hdXRoL21lXCIpLFxyXG4gICAge1xyXG4gICAgICBhbGxvd1JlZnJlc2g6IHRydWUsXHJcbiAgICB9LFxyXG4gICk7XHJcbiAgaWYgKGF1dGhSZXNwb25zZSA9PT0gXCJ1bmF1dGhlbnRpY2F0ZWRcIikge1xyXG4gICAgd3JpdGVTZXNzaW9uKG51bGwpO1xyXG4gICAgcmV0dXJuIG51bGw7XHJcbiAgfVxyXG4gIGlmIChhdXRoUmVzcG9uc2UpIHtcclxuICAgIGNvbnN0IHByb2ZpbGUgPSBidWlsZFByb2ZpbGVGcm9tQXV0aFBheWxvYWQoYXV0aFJlc3BvbnNlKTtcclxuICAgIHN5bmNMZWdhY3lNZW1iZXJDYWNoZUZyb21Qcm9maWxlKHByb2ZpbGUpO1xyXG4gICAgcmV0dXJuIHByb2ZpbGU7XHJcbiAgfVxyXG4gIGlmICghaXNMZWdhY3lGYWxsYmFja0VuYWJsZWQoKSkge1xyXG4gICAgdGhyb3cgZ2V0QmFja2VuZFVuYXZhaWxhYmxlRXJyb3IoKTtcclxuICB9XHJcblxyXG4gIGNvbnN0IHNlc3Npb24gPSBhd2FpdCBnZXRDdXJyZW50TWVtYmVyU2Vzc2lvbigpO1xyXG4gIGlmICghc2Vzc2lvbikge1xyXG4gICAgcmV0dXJuIG51bGw7XHJcbiAgfVxyXG4gIGNvbnN0IGFjY291bnQgPSByZWFkTWVtYmVyQWNjb3VudHMoKS5maW5kKChpdGVtKSA9PiBpdGVtLmFjY291bnRJZCA9PT0gc2Vzc2lvbi5hY2NvdW50SWQpO1xyXG4gIGlmICghYWNjb3VudCkge1xyXG4gICAgcmV0dXJuIG51bGw7XHJcbiAgfVxyXG4gIHJldHVybiB7XHJcbiAgICAuLi5zZXNzaW9uLFxyXG4gICAgYWNjb3VudElkTWFza2VkOiBtYXNrQWNjb3VudElkKHNlc3Npb24uYWNjb3VudElkKSxcclxuICAgIGNyZWF0ZWRBdDogYWNjb3VudC5jcmVhdGVkQXQsXHJcbiAgICBhdmF0YXJVcmw6IGFjY291bnQuYXZhdGFyVXJsID8/IG51bGwsXHJcbiAgfTtcclxufVxyXG5cclxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIHVwZGF0ZU1lbWJlclByb2ZpbGUocGF5bG9hZDoge1xyXG4gIHBob25lOiBzdHJpbmc7XHJcbiAgYXZhdGFyVXJsPzogc3RyaW5nIHwgbnVsbDtcclxufSk6IFByb21pc2U8SDVNZW1iZXJQcm9maWxlPiB7XHJcbiAgY29uc3Qgc2Vzc2lvbiA9IGdldFJlcXVpcmVkU2Vzc2lvbigpO1xyXG4gIGNvbnN0IHBob25lID0gcGF5bG9hZC5waG9uZS50cmltKCk7XHJcbiAgaWYgKCFwaG9uZSkge1xyXG4gICAgdGhyb3cgY3JlYXRlU2VydmljZUVycm9yKFwicGhvbmVSZXF1aXJlZFwiKTtcclxuICB9XHJcblxyXG4gIGNvbnN0IGFjY291bnRzID0gcmVhZE1lbWJlckFjY291bnRzKCk7XHJcbiAgY29uc3QgY3VycmVudEFjY291bnQgPSBhY2NvdW50cy5maW5kKChpdGVtKSA9PiBpdGVtLmFjY291bnRJZCA9PT0gc2Vzc2lvbi5hY2NvdW50SWQpO1xyXG4gIGlmICghY3VycmVudEFjY291bnQpIHtcclxuICAgIHRocm93IGNyZWF0ZVNlcnZpY2VFcnJvcihcIm1lbWJlck5vdEZvdW5kXCIpO1xyXG4gIH1cclxuICBpZiAoYWNjb3VudHMuc29tZSgoaXRlbSkgPT4gaXRlbS5hY2NvdW50SWQgIT09IHNlc3Npb24uYWNjb3VudElkICYmIGl0ZW0ucGhvbmUgPT09IHBob25lKSkge1xyXG4gICAgdGhyb3cgY3JlYXRlU2VydmljZUVycm9yKFwicGhvbmVJblVzZVwiKTtcclxuICB9XHJcblxyXG4gIGNvbnN0IG5leHRBY2NvdW50OiBTdG9yZWRNZW1iZXJBY2NvdW50ID0ge1xyXG4gICAgLi4uY3VycmVudEFjY291bnQsXHJcbiAgICBwaG9uZSxcclxuICAgIGF2YXRhclVybDogcGF5bG9hZC5hdmF0YXJVcmwgPT09IHVuZGVmaW5lZCA/IGN1cnJlbnRBY2NvdW50LmF2YXRhclVybCA/PyBudWxsIDogcGF5bG9hZC5hdmF0YXJVcmwsXHJcbiAgfTtcclxuICB3cml0ZU1lbWJlckFjY291bnRzKGFjY291bnRzLm1hcCgoaXRlbSkgPT4gKGl0ZW0uYWNjb3VudElkID09PSBzZXNzaW9uLmFjY291bnRJZCA/IG5leHRBY2NvdW50IDogaXRlbSkpKTtcclxuXHJcbiAgY29uc3QgbmV4dFNlc3Npb246IEg1TWVtYmVyU2Vzc2lvbiA9IHtcclxuICAgIC4uLnNlc3Npb24sXHJcbiAgICBwaG9uZTogbmV4dEFjY291bnQucGhvbmUsXHJcbiAgICBhdmF0YXJVcmw6IG5leHRBY2NvdW50LmF2YXRhclVybCA/PyBudWxsLFxyXG4gIH07XHJcbiAgd3JpdGVTZXNzaW9uKG5leHRTZXNzaW9uKTtcclxuXHJcbiAgcmV0dXJuIHtcclxuICAgIC4uLm5leHRTZXNzaW9uLFxyXG4gICAgYWNjb3VudElkTWFza2VkOiBtYXNrQWNjb3VudElkKG5leHRTZXNzaW9uLmFjY291bnRJZCksXHJcbiAgICBjcmVhdGVkQXQ6IG5leHRBY2NvdW50LmNyZWF0ZWRBdCxcclxuICAgIGF2YXRhclVybDogbmV4dEFjY291bnQuYXZhdGFyVXJsID8/IG51bGwsXHJcbiAgfTtcclxufVxyXG5cclxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIHVwZGF0ZU1lbWJlclBhc3N3b3JkKHBheWxvYWQ6IHtcclxuICBjdXJyZW50UGFzc3dvcmQ6IHN0cmluZztcclxuICBuZXh0UGFzc3dvcmQ6IHN0cmluZztcclxuICBjb25maXJtUGFzc3dvcmQ6IHN0cmluZztcclxufSk6IFByb21pc2U8dm9pZD4ge1xyXG4gIGNvbnN0IHNlc3Npb24gPSBnZXRSZXF1aXJlZFNlc3Npb24oKTtcclxuICBjb25zdCBjdXJyZW50UGFzc3dvcmQgPSBwYXlsb2FkLmN1cnJlbnRQYXNzd29yZC50cmltKCk7XHJcbiAgY29uc3QgbmV4dFBhc3N3b3JkID0gcGF5bG9hZC5uZXh0UGFzc3dvcmQudHJpbSgpO1xyXG4gIGNvbnN0IGNvbmZpcm1QYXNzd29yZCA9IHBheWxvYWQuY29uZmlybVBhc3N3b3JkLnRyaW0oKTtcclxuICBpZiAoIWN1cnJlbnRQYXNzd29yZCB8fCAhbmV4dFBhc3N3b3JkIHx8ICFjb25maXJtUGFzc3dvcmQpIHtcclxuICAgIHRocm93IGNyZWF0ZVNlcnZpY2VFcnJvcihcInBhc3N3b3JkRmllbGRzUmVxdWlyZWRcIik7XHJcbiAgfVxyXG4gIGlmIChuZXh0UGFzc3dvcmQubGVuZ3RoIDwgNikge1xyXG4gICAgdGhyb3cgY3JlYXRlU2VydmljZUVycm9yKFwicGFzc3dvcmRUb29TaG9ydFwiKTtcclxuICB9XHJcbiAgaWYgKG5leHRQYXNzd29yZCAhPT0gY29uZmlybVBhc3N3b3JkKSB7XHJcbiAgICB0aHJvdyBjcmVhdGVTZXJ2aWNlRXJyb3IoXCJwYXNzd29yZE1pc21hdGNoXCIpO1xyXG4gIH1cclxuXHJcbiAgY29uc3QgYWNjb3VudHMgPSByZWFkTWVtYmVyQWNjb3VudHMoKTtcclxuICBjb25zdCBjdXJyZW50QWNjb3VudCA9IGFjY291bnRzLmZpbmQoKGl0ZW0pID0+IGl0ZW0uYWNjb3VudElkID09PSBzZXNzaW9uLmFjY291bnRJZCk7XHJcbiAgaWYgKCFjdXJyZW50QWNjb3VudCkge1xyXG4gICAgdGhyb3cgY3JlYXRlU2VydmljZUVycm9yKFwibWVtYmVyTm90Rm91bmRcIik7XHJcbiAgfVxyXG4gIGlmIChjdXJyZW50QWNjb3VudC5wYXNzd29yZCAhPT0gY3VycmVudFBhc3N3b3JkKSB7XHJcbiAgICB0aHJvdyBjcmVhdGVTZXJ2aWNlRXJyb3IoXCJjdXJyZW50UGFzc3dvcmRJbmNvcnJlY3RcIik7XHJcbiAgfVxyXG5cclxuICB3cml0ZU1lbWJlckFjY291bnRzKFxyXG4gICAgYWNjb3VudHMubWFwKChpdGVtKSA9PlxyXG4gICAgICBpdGVtLmFjY291bnRJZCA9PT0gc2Vzc2lvbi5hY2NvdW50SWRcclxuICAgICAgICA/IHtcclxuICAgICAgICAgICAgLi4uaXRlbSxcclxuICAgICAgICAgICAgcGFzc3dvcmQ6IG5leHRQYXNzd29yZCxcclxuICAgICAgICAgIH1cclxuICAgICAgICA6IGl0ZW0sXHJcbiAgICApLFxyXG4gICk7XHJcbn1cclxuXHJcbmV4cG9ydCBhc3luYyBmdW5jdGlvbiByZWdpc3Rlck1lbWJlcihwYXlsb2FkOiB7XHJcbiAgc2l0ZUtleTogc3RyaW5nO1xyXG4gIHBob25lOiBzdHJpbmc7XHJcbiAgcGFzc3dvcmQ6IHN0cmluZztcclxuICBjb25maXJtUGFzc3dvcmQ/OiBzdHJpbmc7XHJcbiAgZGlzcGxheU5hbWU/OiBzdHJpbmc7XHJcbn0pOiBQcm9taXNlPEg1TWVtYmVyUHJvZmlsZT4ge1xyXG4gIHRyeSB7XHJcbiAgICBjb25zdCBiYWNrZW5kUmVzcG9uc2UgPSBhd2FpdCB0cnlCYWNrZW5kQXV0aFJlcXVlc3Q8QmFja2VuZE1lbWJlckF1dGhSZXNwb25zZT4oKCkgPT5cclxuICAgICAgcmVxdWVzdEpzb24oXCIvYXBpL2g1L2F1dGgvcmVnaXN0ZXJcIiwge1xyXG4gICAgICAgIG1ldGhvZDogXCJQT1NUXCIsXHJcbiAgICAgICAgaGVhZGVyczogeyBcIkNvbnRlbnQtVHlwZVwiOiBcImFwcGxpY2F0aW9uL2pzb25cIiB9LFxyXG4gICAgICAgIGJvZHk6IEpTT04uc3RyaW5naWZ5KHtcclxuICAgICAgICAgIHNpdGVLZXk6IHBheWxvYWQuc2l0ZUtleSxcclxuICAgICAgICAgIHBob25lOiBwYXlsb2FkLnBob25lLnRyaW0oKSxcclxuICAgICAgICAgIHBhc3N3b3JkOiBwYXlsb2FkLnBhc3N3b3JkLnRyaW0oKSxcclxuICAgICAgICAgIGNvbmZpcm1QYXNzd29yZDogcGF5bG9hZC5jb25maXJtUGFzc3dvcmQ/LnRyaW0oKSB8fCBwYXlsb2FkLnBhc3N3b3JkLnRyaW0oKSxcclxuICAgICAgICAgIC4uLihwYXlsb2FkLmRpc3BsYXlOYW1lPy50cmltKCkgPyB7IGRpc3BsYXlOYW1lOiBwYXlsb2FkLmRpc3BsYXlOYW1lLnRyaW0oKSB9IDoge30pLFxyXG4gICAgICAgIH0pLFxyXG4gICAgICAgIHNpZ25hbDogQWJvcnRTaWduYWwudGltZW91dCgzMDAwKSwgICAgICB9KSxcclxuICAgICk7XHJcbiAgICBpZiAoYmFja2VuZFJlc3BvbnNlID09PSBcInVuYXV0aGVudGljYXRlZFwiKSB7XHJcbiAgICAgIC8vIOWQjuerr+acquiupOivge+8jOWwneivlSBsb2NhbFN0b3JhZ2Ug5rOo5YaMXHJcbiAgICAgIGlmIChpc0xlZ2FjeUZhbGxiYWNrRW5hYmxlZCgpKSB7XHJcbiAgICAgICAgY29uc3QgbGVnYWN5ID0gdHJ5TGVnYWN5UmVnaXN0ZXIocGF5bG9hZCk7XHJcbiAgICAgICAgaWYgKGxlZ2FjeSkgcmV0dXJuIGxlZ2FjeTtcclxuICAgICAgfVxyXG4gICAgICB0aHJvdyBjcmVhdGVTZXJ2aWNlRXJyb3IoXCJyZWdpc3RlckF1dGhGYWlsZWRcIik7XHJcbiAgICB9XHJcbiAgICBpZiAoYmFja2VuZFJlc3BvbnNlKSB7XHJcbiAgICAgIGNvbnN0IHByb2ZpbGUgPSBidWlsZFByb2ZpbGVGcm9tQXV0aFBheWxvYWQoYmFja2VuZFJlc3BvbnNlKTtcclxuICAgICAgc3luY0xlZ2FjeU1lbWJlckNhY2hlRnJvbVByb2ZpbGUocHJvZmlsZSk7XHJcbiAgICAgIHJldHVybiBwcm9maWxlO1xyXG4gICAgfVxyXG4gIH0gY2F0Y2ggKGVycm9yKSB7XHJcbiAgICAvLyA0MDkg4oCUIOWQjuerr+i/lOWbnuS6huWFt+S9k+S4muWKoemUmeivr++8jOmAj+S8oOWunumZhea2iOaBr1xyXG4gICAgaWYgKGVycm9yIGluc3RhbmNlb2YgQXBpUmVxdWVzdEVycm9yICYmIGVycm9yLnN0YXR1cyA9PT0gNDA5KSB7XHJcbiAgICAgIHRocm93IG5ldyBFcnJvcihlcnJvci5tZXNzYWdlIHx8IGdldFNlcnZpY2VFcnJvck1lc3NhZ2UoXCJyZWdpc3RlckZhaWxlZFwiKSk7XHJcbiAgICB9XHJcbiAgICAvLyDnvZHnu5wv6LaF5pe26ZSZ6K+vIOKAlCDlsJ3or5UgbG9jYWxTdG9yYWdlIOWbnumAgFxyXG4gICAgaWYgKGlzTGVnYWN5RmFsbGJhY2tFbmFibGVkKCkpIHtcclxuICAgICAgY29uc3QgbGVnYWN5ID0gdHJ5TGVnYWN5UmVnaXN0ZXIocGF5bG9hZCk7XHJcbiAgICAgIGlmIChsZWdhY3kpIHJldHVybiBsZWdhY3k7XHJcbiAgICB9XHJcbiAgICAvLyDmnI3liqHkuI3lj6/ovr7vvIg0MDQg562J77yJ4oCUIOWwneivlSBsb2NhbFN0b3JhZ2Ug5Zue6YCAXHJcbiAgICBpZiAoZXJyb3IgaW5zdGFuY2VvZiBBcGlSZXF1ZXN0RXJyb3IgJiYgY2FuVXNlTGVnYWN5RmFsbGJhY2soZXJyb3IpKSB7XHJcbiAgICAgIGNvbnN0IGxlZ2FjeSA9IHRyeUxlZ2FjeVJlZ2lzdGVyKHBheWxvYWQpO1xyXG4gICAgICBpZiAobGVnYWN5KSByZXR1cm4gbGVnYWN5O1xyXG4gICAgfVxyXG4gICAgdGhyb3cgZXJyb3I7XHJcbiAgfVxyXG4gIGlmICghaXNMZWdhY3lGYWxsYmFja0VuYWJsZWQoKSkge1xyXG4gICAgdGhyb3cgZ2V0QmFja2VuZFVuYXZhaWxhYmxlRXJyb3IoKTtcclxuICB9XHJcblxyXG4gIGNvbnN0IGxlZ2FjeSA9IHRyeUxlZ2FjeVJlZ2lzdGVyKHBheWxvYWQpO1xyXG4gIGlmICghbGVnYWN5KSB7XHJcbiAgICB0aHJvdyBjcmVhdGVTZXJ2aWNlRXJyb3IoXCJyZWdpc3RlckZhaWxlZFwiKTtcclxuICB9XHJcbiAgcmV0dXJuIGxlZ2FjeTtcclxufVxyXG5cclxuLyoqIFRyeSB0byByZWdpc3RlciB1c2luZyBsZWdhY3kgbG9jYWxTdG9yYWdlIG1vY2sgZGF0YS4gUmV0dXJucyBudWxsIG9uIGZhaWx1cmUuICovXHJcbmZ1bmN0aW9uIHRyeUxlZ2FjeVJlZ2lzdGVyKHBheWxvYWQ6IHtcclxuICBzaXRlS2V5OiBzdHJpbmc7XHJcbiAgcGhvbmU6IHN0cmluZztcclxuICBwYXNzd29yZDogc3RyaW5nO1xyXG4gIGNvbmZpcm1QYXNzd29yZD86IHN0cmluZztcclxuICBkaXNwbGF5TmFtZT86IHN0cmluZztcclxufSk6IEg1TWVtYmVyUHJvZmlsZSB8IG51bGwge1xyXG4gIGVuc3VyZVNlZWRlZFN0b3JhZ2UoKTtcclxuICBjb25zdCBwaG9uZSA9IHBheWxvYWQucGhvbmUudHJpbSgpO1xyXG4gIGNvbnN0IHBhc3N3b3JkID0gcGF5bG9hZC5wYXNzd29yZC50cmltKCk7XHJcbiAgaWYgKCFwaG9uZSB8fCAhcGFzc3dvcmQpIHJldHVybiBudWxsO1xyXG4gIGNvbnN0IGFjY291bnRzID0gcmVhZE1lbWJlckFjY291bnRzKCk7XHJcbiAgaWYgKGFjY291bnRzLnNvbWUoKGl0ZW0pID0+IGl0ZW0ucGhvbmUgPT09IHBob25lKSkge1xyXG4gICAgcmV0dXJuIG51bGw7IC8vIGNhbGxlciBzaG91bGQgcHJvdmlkZSBhIG1lYW5pbmdmdWwgbWVzc2FnZVxyXG4gIH1cclxuICBjb25zdCBhY2NvdW50SWQgPSBnZW5lcmF0ZVVuaXF1ZU51bWVyaWNBY2NvdW50SWQoKTtcclxuICBjb25zdCBhY2NvdW50OiBTdG9yZWRNZW1iZXJBY2NvdW50ID0ge1xyXG4gICAgaWQ6IGNyZWF0ZUlkKFwibWVtYmVyXCIpLFxyXG4gICAgYWNjb3VudElkLFxyXG4gICAgcGhvbmUsXHJcbiAgICBwYXNzd29yZCxcclxuICAgIHB1YmxpY1VzZXJJZDogYGg1LSR7YWNjb3VudElkfWAsXHJcbiAgICBkaXNwbGF5TmFtZTpcclxuICAgICAgcGF5bG9hZC5kaXNwbGF5TmFtZT8udHJpbSgpIHx8XHJcbiAgICAgIGdldFNlZWREYXRhVGV4dChcIm1lbWJlckRpc3BsYXlOYW1lV2l0aFN1ZmZpeFwiLCB7IHN1ZmZpeDogYWNjb3VudElkLnNsaWNlKC00KSB9KSxcclxuICAgIGludml0ZUNvZGU6IGdlbmVyYXRlSW52aXRlQ29kZShhY2NvdW50SWQpLFxyXG4gICAgY3JlYXRlZEF0OiBub3dJc28oKSxcclxuICAgIGF2YXRhclVybDogbnVsbCxcclxuICB9O1xyXG4gIGFjY291bnRzLnB1c2goYWNjb3VudCk7XHJcbiAgd3JpdGVNZW1iZXJBY2NvdW50cyhhY2NvdW50cyk7XHJcbiAgY29uc3Qgc3RhdGVzID0gcmVhZE1lbWJlclN0YXRlcygpO1xyXG4gIHN0YXRlc1thY2NvdW50SWRdID0gY2xvbmVTdGF0ZVRlbXBsYXRlKCk7XHJcbiAgd3JpdGVNZW1iZXJTdGF0ZXMoc3RhdGVzKTtcclxuICBjb25zdCBzZXNzaW9uOiBINU1lbWJlclNlc3Npb24gPSB7XHJcbiAgICBhY2NvdW50SWQsXHJcbiAgICBwaG9uZSxcclxuICAgIHB1YmxpY1VzZXJJZDogYWNjb3VudC5wdWJsaWNVc2VySWQsXHJcbiAgICBkaXNwbGF5TmFtZTogYWNjb3VudC5kaXNwbGF5TmFtZSxcclxuICAgIGludml0ZUNvZGU6IGFjY291bnQuaW52aXRlQ29kZSxcclxuICAgIGF2YXRhclVybDogYWNjb3VudC5hdmF0YXJVcmwgPz8gbnVsbCxcclxuICB9O1xyXG4gIHdyaXRlU2Vzc2lvbihzZXNzaW9uKTtcclxuICByZXR1cm4ge1xyXG4gICAgLi4uc2Vzc2lvbixcclxuICAgIGFjY291bnRJZE1hc2tlZDogbWFza0FjY291bnRJZChzZXNzaW9uLmFjY291bnRJZCksXHJcbiAgICBjcmVhdGVkQXQ6IGFjY291bnQuY3JlYXRlZEF0LFxyXG4gICAgYXZhdGFyVXJsOiBhY2NvdW50LmF2YXRhclVybCA/PyBudWxsLFxyXG4gIH07XHJcbn1cclxuXHJcbmFzeW5jIGZ1bmN0aW9uIGxvZ2luTWVtYmVyUmVzb2x2ZWQocGF5bG9hZDoge1xyXG4gIHNpdGVLZXk6IHN0cmluZztcclxuICBwaG9uZTogc3RyaW5nO1xyXG4gIHBhc3N3b3JkOiBzdHJpbmc7XHJcbn0pOiBQcm9taXNlPEg1TWVtYmVyUHJvZmlsZT4ge1xyXG4gIC8vIOWwneivleWQjuerr+iupOivge+8iOW4pui+g+efrei2heaXtumBv+WFjeaXoOmZkOetieW+he+8iVxyXG4gIHRyeSB7XHJcbiAgICBjb25zdCBiYWNrZW5kUmVzcG9uc2UgPSBhd2FpdCByZXF1ZXN0SnNvbjxCYWNrZW5kTWVtYmVyQXV0aFJlc3BvbnNlPihcIi9hcGkvaDUvYXV0aC9sb2dpblwiLCB7XHJcbiAgICAgIG1ldGhvZDogXCJQT1NUXCIsXHJcbiAgICAgIGhlYWRlcnM6IHsgXCJDb250ZW50LVR5cGVcIjogXCJhcHBsaWNhdGlvbi9qc29uXCIgfSxcclxuICAgICAgYm9keTogSlNPTi5zdHJpbmdpZnkoe1xyXG4gICAgICAgIHNpdGVLZXk6IHBheWxvYWQuc2l0ZUtleSxcclxuICAgICAgICBwaG9uZTogcGF5bG9hZC5waG9uZS50cmltKCksXHJcbiAgICAgICAgcGFzc3dvcmQ6IHBheWxvYWQucGFzc3dvcmQudHJpbSgpLFxyXG4gICAgICB9KSxcclxuICAgICAgc2lnbmFsOiBBYm9ydFNpZ25hbC50aW1lb3V0KDMwMDApLFxyXG4gICAgfSk7XHJcbiAgICBjb25zdCBwcm9maWxlID0gYnVpbGRQcm9maWxlRnJvbUF1dGhQYXlsb2FkKGJhY2tlbmRSZXNwb25zZSk7XHJcbiAgICBzeW5jTGVnYWN5TWVtYmVyQ2FjaGVGcm9tUHJvZmlsZShwcm9maWxlKTtcclxuICAgIHJldHVybiBwcm9maWxlO1xyXG4gIH0gY2F0Y2ggKGVycm9yKSB7XHJcbiAgICBpZiAoZXJyb3IgaW5zdGFuY2VvZiBBcGlSZXF1ZXN0RXJyb3IgJiYgZXJyb3Iuc3RhdHVzID09PSA0MDEpIHtcclxuICAgICAgLy8gNDAxIOKAlCDlkI7nq6/orqTor4HlpLHotKXvvIzlsJ3or5UgbG9jYWxTdG9yYWdlIOWbnumAgFxyXG4gICAgICBpZiAoaXNMZWdhY3lGYWxsYmFja0VuYWJsZWQoKSkge1xyXG4gICAgICAgIGNvbnN0IGxlZ2FjeSA9IHRyeUxlZ2FjeUxvZ2luKHBheWxvYWQucGhvbmUudHJpbSgpLCBwYXlsb2FkLnBhc3N3b3JkLnRyaW0oKSk7XHJcbiAgICAgICAgaWYgKGxlZ2FjeSkgcmV0dXJuIGxlZ2FjeTtcclxuICAgICAgfVxyXG4gICAgICBjb25zdCBub3JtYWxpemVkRGV0YWlsID0gKGVycm9yLm1lc3NhZ2UgPz8gXCJcIikudHJpbSgpO1xyXG4gICAgICBpZiAoXHJcbiAgICAgICAgbm9ybWFsaXplZERldGFpbCAmJlxyXG4gICAgICAgICEvcGhvbmUgb3IgcGFzc3dvcmQgaXMgaW52YWxpZC9pLnRlc3Qobm9ybWFsaXplZERldGFpbCkgJiZcclxuICAgICAgICAhL+aJi+acuuWPt+aIluWvhueggemUmeivry8udGVzdChub3JtYWxpemVkRGV0YWlsKVxyXG4gICAgICApIHtcclxuICAgICAgICB0aHJvdyBuZXcgRXJyb3Iobm9ybWFsaXplZERldGFpbCk7XHJcbiAgICAgIH1cclxuICAgICAgdGhyb3cgY3JlYXRlU2VydmljZUVycm9yKFwiaW52YWxpZENyZWRlbnRpYWxzXCIpO1xyXG4gICAgfVxyXG4gICAgLy8g572R57ucL+i2heaXtumUmeivryDigJQg5bCd6K+VIGxvY2FsU3RvcmFnZSDlm57pgIBcclxuICAgIGlmIChpc0xlZ2FjeUZhbGxiYWNrRW5hYmxlZCgpKSB7XHJcbiAgICAgIGNvbnN0IGxlZ2FjeSA9IHRyeUxlZ2FjeUxvZ2luKHBheWxvYWQucGhvbmUudHJpbSgpLCBwYXlsb2FkLnBhc3N3b3JkLnRyaW0oKSk7XHJcbiAgICAgIGlmIChsZWdhY3kpIHJldHVybiBsZWdhY3k7XHJcbiAgICB9XHJcbiAgICAvLyDlkI7nq6/kuI3lj6/ovr5cclxuICAgIGlmICghY2FuVXNlTGVnYWN5RmFsbGJhY2soZXJyb3IpKSB7XHJcbiAgICAgIHRocm93IGNyZWF0ZVNlcnZpY2VFcnJvcihcImJhY2tlbmRVbmF2YWlsYWJsZVwiKTtcclxuICAgIH1cclxuICB9XHJcbiAgaWYgKCFpc0xlZ2FjeUZhbGxiYWNrRW5hYmxlZCgpKSB7XHJcbiAgICB0aHJvdyBnZXRCYWNrZW5kVW5hdmFpbGFibGVFcnJvcigpO1xyXG4gIH1cclxuXHJcbiAgZW5zdXJlU2VlZGVkU3RvcmFnZSgpO1xyXG4gIGNvbnN0IGxlZ2FjeSA9IHRyeUxlZ2FjeUxvZ2luKHBheWxvYWQucGhvbmUudHJpbSgpLCBwYXlsb2FkLnBhc3N3b3JkLnRyaW0oKSk7XHJcbiAgaWYgKCFsZWdhY3kpIHtcclxuICAgIHRocm93IGNyZWF0ZVNlcnZpY2VFcnJvcihcImludmFsaWRDcmVkZW50aWFsc1wiKTtcclxuICB9XHJcbiAgcmV0dXJuIGxlZ2FjeTtcclxufVxyXG5cclxuLyoqIFRyeSB0byBsb2dpbiB1c2luZyBsZWdhY3kgbG9jYWxTdG9yYWdlIG1vY2sgZGF0YS4gUmV0dXJucyBudWxsIGlmIG5vdCBmb3VuZC4gKi9cclxuZnVuY3Rpb24gdHJ5TGVnYWN5TG9naW4ocGhvbmU6IHN0cmluZywgcGFzc3dvcmQ6IHN0cmluZyk6IEg1TWVtYmVyUHJvZmlsZSB8IG51bGwge1xyXG4gIGNvbnN0IGFjY291bnQgPSByZWFkTWVtYmVyQWNjb3VudHMoKS5maW5kKFxyXG4gICAgKGl0ZW0pID0+IGl0ZW0ucGhvbmUgPT09IHBob25lICYmIGl0ZW0ucGFzc3dvcmQgPT09IHBhc3N3b3JkLFxyXG4gICk7XHJcbiAgaWYgKCFhY2NvdW50KSByZXR1cm4gbnVsbDtcclxuICBjb25zdCBzZXNzaW9uOiBINU1lbWJlclNlc3Npb24gPSB7XHJcbiAgICBhY2NvdW50SWQ6IGFjY291bnQuYWNjb3VudElkLFxyXG4gICAgcGhvbmU6IGFjY291bnQucGhvbmUsXHJcbiAgICBwdWJsaWNVc2VySWQ6IGFjY291bnQucHVibGljVXNlcklkLFxyXG4gICAgZGlzcGxheU5hbWU6IGFjY291bnQuZGlzcGxheU5hbWUsXHJcbiAgICBpbnZpdGVDb2RlOiBhY2NvdW50Lmludml0ZUNvZGUsXHJcbiAgICBhdmF0YXJVcmw6IGFjY291bnQuYXZhdGFyVXJsID8/IG51bGwsXHJcbiAgfTtcclxuICB3cml0ZVNlc3Npb24oc2Vzc2lvbik7XHJcbiAgcmV0dXJuIHtcclxuICAgIC4uLnNlc3Npb24sXHJcbiAgICBhY2NvdW50SWRNYXNrZWQ6IG1hc2tBY2NvdW50SWQoc2Vzc2lvbi5hY2NvdW50SWQpLFxyXG4gICAgY3JlYXRlZEF0OiBhY2NvdW50LmNyZWF0ZWRBdCxcclxuICAgIGF2YXRhclVybDogYWNjb3VudC5hdmF0YXJVcmwgPz8gbnVsbCxcclxuICB9O1xyXG59XHJcblxyXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gbG9naW5NZW1iZXIocGF5bG9hZDoge1xyXG4gIHNpdGVLZXk6IHN0cmluZztcclxuICBwaG9uZTogc3RyaW5nO1xyXG4gIHBhc3N3b3JkOiBzdHJpbmc7XHJcbn0pOiBQcm9taXNlPEg1TWVtYmVyUHJvZmlsZT4ge1xyXG4gIHJldHVybiBsb2dpbk1lbWJlclJlc29sdmVkKHBheWxvYWQpO1xyXG59XHJcblxyXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gbG9nb3V0TWVtYmVyKCk6IFByb21pc2U8dm9pZD4ge1xyXG4gIHRyeSB7XHJcbiAgICBjb25zdCBsb2dvdXRSZXNwb25zZSA9IGF3YWl0IHRyeUJhY2tlbmRBdXRoUmVxdWVzdCgoKSA9PlxyXG4gICAgICByZXF1ZXN0SnNvbihcIi9hcGkvaDUvYXV0aC9sb2dvdXRcIiwge1xyXG4gICAgICAgIG1ldGhvZDogXCJQT1NUXCIsXHJcbiAgICAgIH0pLFxyXG4gICAgKTtcclxuICAgICAgaWYgKGxvZ291dFJlc3BvbnNlID09PSBcInVuYXV0aGVudGljYXRlZFwiKSB7XHJcbiAgICAgICAgd3JpdGVTZXNzaW9uKG51bGwpO1xyXG4gICAgICAgIHJldHVybjtcclxuICAgICAgfVxyXG4gICAgfSBjYXRjaCAoZXJyb3IpIHtcclxuICAgIGlmICghY2FuVXNlTGVnYWN5RmFsbGJhY2soZXJyb3IpICYmICEoZXJyb3IgaW5zdGFuY2VvZiBUeXBlRXJyb3IpKSB7XHJcbiAgICAgIHRocm93IGVycm9yO1xyXG4gICAgfVxyXG4gIH0gZmluYWxseSB7XHJcbiAgICB3cml0ZVNlc3Npb24obnVsbCk7XHJcbiAgfVxyXG59XHJcblxyXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gZ2V0TWVtYmVySG9tZURhc2hib2FyZChzaXRlS2V5Pzogc3RyaW5nKTogUHJvbWlzZTxINUhvbWVEYXNoYm9hcmQ+IHtcclxuICBjb25zdCBob21lUmVzcG9uc2UgPSBhd2FpdCB0cnlCYWNrZW5kQXV0aFJlcXVlc3Q8QmFja2VuZE1lbWJlckhvbWVSZXNwb25zZT4oKCkgPT5cclxuICAgIHJlcXVlc3RKc29uKFwiL2FwaS9oNS9tZW1iZXIvaG9tZVwiKSxcclxuICAgIHtcclxuICAgICAgYWxsb3dSZWZyZXNoOiB0cnVlLFxyXG4gICAgfSxcclxuICApO1xyXG4gIGlmIChob21lUmVzcG9uc2UgPT09IFwidW5hdXRoZW50aWNhdGVkXCIpIHtcclxuICAgIHdyaXRlU2Vzc2lvbihudWxsKTtcclxuICAgIHRocm93IG5ldyBINUF1dGhSZXF1aXJlZEVycm9yKCk7XHJcbiAgfVxyXG4gIGlmIChob21lUmVzcG9uc2UpIHtcclxuICAgIGNvbnN0IHByb2ZpbGUgPSBidWlsZFByb2ZpbGVGcm9tQXV0aFBheWxvYWQoe1xyXG4gICAgICBtZW1iZXI6IGhvbWVSZXNwb25zZS5tZW1iZXIsXHJcbiAgICAgIHNpdGU6IGhvbWVSZXNwb25zZS5zaXRlLFxyXG4gICAgfSk7XHJcbiAgICBzeW5jTGVnYWN5TWVtYmVyQ2FjaGVGcm9tUHJvZmlsZShwcm9maWxlKTtcclxuICAgIHJldHVybiB7XHJcbiAgICAgIHNpdGU6IG1hcFNpdGVCcmFuZEZyb21CYWNrZW5kKGhvbWVSZXNwb25zZS5zaXRlKSxcclxuICAgICAgbWVtYmVyOiBwcm9maWxlLFxyXG4gICAgICB3YWxsZXQ6IHtcclxuICAgICAgICBzeXN0ZW1CYWxhbmNlOiBob21lUmVzcG9uc2Uud2FsbGV0LnN5c3RlbUJhbGFuY2UgPz8gMCxcclxuICAgICAgICB0YXNrQmFsYW5jZTogaG9tZVJlc3BvbnNlLndhbGxldC50YXNrQmFsYW5jZSA/PyAwLFxyXG4gICAgICAgIGN1cnJlbmN5OiBob21lUmVzcG9uc2Uud2FsbGV0LmN1cnJlbmN5ID8/IFwiVVNEXCIsXHJcbiAgICAgICAgd2l0aGRyYXdUaHJlc2hvbGQ6IERFRkFVTFRfV0lUSERSQVdfVEhSRVNIT0xELFxyXG4gICAgICAgIGNhbldpdGhkcmF3OlxyXG4gICAgICAgICAgKGhvbWVSZXNwb25zZS53YWxsZXQuc3lzdGVtQmFsYW5jZSA/PyAwKSA+PSBERUZBVUxUX1dJVEhEUkFXX1RIUkVTSE9MRCxcclxuICAgICAgICBzaG9ydGZhbGxBbW91bnQ6IE1hdGgubWF4KFxyXG4gICAgICAgICAgMCxcclxuICAgICAgICAgIERFRkFVTFRfV0lUSERSQVdfVEhSRVNIT0xEIC0gKGhvbWVSZXNwb25zZS53YWxsZXQuc3lzdGVtQmFsYW5jZSA/PyAwKSxcclxuICAgICAgICApLFxyXG4gICAgICB9LFxyXG4gICAgICB1bnJlYWRDb3VudDogaG9tZVJlc3BvbnNlLnVucmVhZE1lc3NhZ2VDb3VudCxcclxuICAgICAgcGVuZGluZ0NsYWltQ291bnQ6IGhvbWVSZXNwb25zZS5wZW5kaW5nQ2xhaW1Db3VudCxcclxuICAgICAgYWN0aXZlQ291bnQ6IGhvbWVSZXNwb25zZS5hY3RpdmVDb3VudCxcclxuICAgICAgZXhwaXJpbmdDb3VudDogaG9tZVJlc3BvbnNlLmV4cGlyaW5nQ291bnQsXHJcbiAgICAgIHJlY2VudE1lc3NhZ2VzOiBob21lUmVzcG9uc2UucmVjZW50TWVzc2FnZXMubWFwKChpdGVtKSA9PiAoe1xyXG4gICAgICAgIGlkOiBpdGVtLmlkLFxyXG4gICAgICAgIGNhdGVnb3J5OiBpdGVtLmNhdGVnb3J5LFxyXG4gICAgICAgIHRpdGxlOiBpdGVtLnRpdGxlLFxyXG4gICAgICAgIGJvZHk6IGl0ZW0uYm9keVRleHQsXHJcbiAgICAgICAgY3JlYXRlZEF0OiBpdGVtLmNyZWF0ZWRBdCxcclxuICAgICAgICBpc1JlYWQ6IGl0ZW0uaXNSZWFkLFxyXG4gICAgICB9KSksXHJcbiAgICAgIGxlYWRlcmJvYXJkOiBob21lUmVzcG9uc2UubGVhZGVyYm9hcmQubWFwKChpdGVtKSA9PiAoe1xyXG4gICAgICAgIHJhbms6IGl0ZW0ucmFuayxcclxuICAgICAgICBhY2NvdW50SWRNYXNrZWQ6IGl0ZW0uYWNjb3VudElkTWFza2VkLFxyXG4gICAgICAgIGFtb3VudDogaXRlbS5hbW91bnQsXHJcbiAgICAgICAgY3VycmVuY3k6IGl0ZW0uY3VycmVuY3ksXHJcbiAgICAgIH0pKSxcclxuICAgICAgdmVyaWZpY2F0aW9uOiBtYXBIb21lVmVyaWZpY2F0aW9uU3VtbWFyeUZyb21CYWNrZW5kKGhvbWVSZXNwb25zZS52ZXJpZmljYXRpb24pLFxyXG4gICAgICBmcmFnbWVudHM6IG1hcEhvbWVGcmFnbWVudFN1bW1hcnlGcm9tQmFja2VuZChob21lUmVzcG9uc2UuZnJhZ21lbnRzKSxcclxuICAgIH07XHJcbiAgfVxyXG4gIGlmICghaXNMZWdhY3lGYWxsYmFja0VuYWJsZWQoKSkge1xyXG4gICAgdGhyb3cgZ2V0QmFja2VuZFVuYXZhaWxhYmxlRXJyb3IoKTtcclxuICB9XHJcblxyXG4gIGNvbnN0IHNlc3Npb24gPSBnZXRSZXF1aXJlZFNlc3Npb24oKTtcclxuICBjb25zdCBhY2NvdW50ID0gcmVhZE1lbWJlckFjY291bnRzKCkuZmluZCgoaXRlbSkgPT4gaXRlbS5hY2NvdW50SWQgPT09IHNlc3Npb24uYWNjb3VudElkKSE7XHJcbiAgY29uc3Qgc3RhdGUgPSBnZXRTdGF0ZUZvckFjY291bnQoc2Vzc2lvbi5hY2NvdW50SWQpO1xyXG4gIGNvbnN0IHBhY2thZ2VzID0gc3RhdGUudGFza1BhY2thZ2VzLm1hcCgocGtnKSA9PiBtYXBUYXNrUGFja2FnZShwa2cpKTtcclxuICBjb25zdCBmcmFnbWVudE92ZXJ2aWV3ID0gYnVpbGRGcmFnbWVudE92ZXJ2aWV3KHN0YXRlKTtcclxuICByZXR1cm4ge1xyXG4gICAgc2l0ZTogZ2V0U2l0ZUJyYW5kKHNpdGVLZXkpLFxyXG4gICAgbWVtYmVyOiB7XHJcbiAgICAgIC4uLnNlc3Npb24sXHJcbiAgICAgIGFjY291bnRJZE1hc2tlZDogbWFza0FjY291bnRJZChzZXNzaW9uLmFjY291bnRJZCksXHJcbiAgICAgIGNyZWF0ZWRBdDogYWNjb3VudC5jcmVhdGVkQXQsXHJcbiAgICAgIGF2YXRhclVybDogYWNjb3VudC5hdmF0YXJVcmwgPz8gbnVsbCxcclxuICAgIH0sXHJcbiAgICB3YWxsZXQ6IGdldFdhbGxldFN1bW1hcnlGcm9tU3RhdGUoc3RhdGUpLFxyXG4gICAgdW5yZWFkQ291bnQ6IGdldFVucmVhZE1lc3NhZ2VDb3VudChzdGF0ZS5tZXNzYWdlcyksXHJcbiAgICBwZW5kaW5nQ2xhaW1Db3VudDogcGFja2FnZXMuZmlsdGVyKChwa2cpID0+IHBrZy5zdGF0dXMgPT09IFwicGVuZGluZ19jbGFpbVwiKS5sZW5ndGgsXHJcbiAgICBhY3RpdmVDb3VudDogcGFja2FnZXMuZmlsdGVyKChwa2cpID0+IHBrZy5zdGF0dXMgPT09IFwiYWN0aXZlXCIpLmxlbmd0aCxcclxuICAgIGV4cGlyaW5nQ291bnQ6IHBhY2thZ2VzLmZpbHRlcigocGtnKSA9PiBwa2cuc3RhdHVzID09PSBcImFjdGl2ZVwiICYmIHBrZy5jb3VudGRvd25TZWNvbmRzIDw9IDYgKiAzNjAwKS5sZW5ndGgsXHJcbiAgICByZWNlbnRNZXNzYWdlczogWy4uLnN0YXRlLm1lc3NhZ2VzXS5zbGljZSgwLCA1KSxcclxuICAgIGxlYWRlcmJvYXJkOiAoYXdhaXQgZ2V0V2l0aGRyYXdMZWFkZXJib2FyZCgpKS5zbGljZSgwLCA1KSxcclxuICAgIHZlcmlmaWNhdGlvbjogYnVpbGRIb21lVmVyaWZpY2F0aW9uU3VtbWFyeUZyb21TdGF0ZShzdGF0ZSksXHJcbiAgICBmcmFnbWVudHM6IGJ1aWxkSG9tZUZyYWdtZW50U3VtbWFyeUZyb21PdmVydmlldyhmcmFnbWVudE92ZXJ2aWV3KSxcclxuICB9O1xyXG59XHJcblxyXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gbGlzdFRhc2tQYWNrYWdlcygpOiBQcm9taXNlPFxyXG4gIEFycmF5PEg1VGFza1BhY2thZ2UgJiB7IHRvdGFsQ29tbWlzc2lvbjogbnVtYmVyOyBjdXJyZW50Q29tbWlzc2lvbjogbnVtYmVyOyBjb21wbGV0ZWRJdGVtczogbnVtYmVyOyB0b3RhbEl0ZW1zOiBudW1iZXI7IGNvdW50ZG93blNlY29uZHM6IG51bWJlciB9PlxyXG4+IHtcclxuICBjb25zdCBiYWNrZW5kUGFja2FnZXMgPSBhd2FpdCByZXF1ZXN0QmFja2VuZE1lbWJlckRvbWFpbjxCYWNrZW5kVGFza1BhY2thZ2VSZXNwb25zZVtdPihcIi9hcGkvaDUvdGFzay1wYWNrYWdlc1wiKTtcclxuICBpZiAoYmFja2VuZFBhY2thZ2VzKSB7XHJcbiAgICByZXR1cm4gYmFja2VuZFBhY2thZ2VzLm1hcCgocGtnKSA9PiBtYXBUYXNrUGFja2FnZUZyb21CYWNrZW5kKHBrZykpO1xyXG4gIH1cclxuICBjb25zdCBzZXNzaW9uID0gZ2V0UmVxdWlyZWRTZXNzaW9uKCk7XHJcbiAgY29uc3Qgc3RhdGUgPSBnZXRTdGF0ZUZvckFjY291bnQoc2Vzc2lvbi5hY2NvdW50SWQpO1xyXG4gIHJldHVybiBzdGF0ZS50YXNrUGFja2FnZXMubWFwKChwa2cpID0+IG1hcFRhc2tQYWNrYWdlKHBrZykpO1xyXG59XHJcblxyXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gZ2V0VGFza1BhY2thZ2VEZXRhaWwoXHJcbiAgcGFja2FnZUlkOiBzdHJpbmcsXHJcbik6IFByb21pc2U8XHJcbiAgSDVUYXNrUGFja2FnZSAmIHsgdG90YWxDb21taXNzaW9uOiBudW1iZXI7IGN1cnJlbnRDb21taXNzaW9uOiBudW1iZXI7IGNvbXBsZXRlZEl0ZW1zOiBudW1iZXI7IHRvdGFsSXRlbXM6IG51bWJlcjsgY291bnRkb3duU2Vjb25kczogbnVtYmVyIH1cclxuPiB7XHJcbiAgY29uc3QgYmFja2VuZFBhY2thZ2UgPSBhd2FpdCByZXF1ZXN0QmFja2VuZE1lbWJlckRvbWFpbjxCYWNrZW5kVGFza1BhY2thZ2VSZXNwb25zZT4oXHJcbiAgICBgL2FwaS9oNS90YXNrLXBhY2thZ2VzLyR7ZW5jb2RlVVJJQ29tcG9uZW50KHBhY2thZ2VJZCl9YCxcclxuICApO1xyXG4gIGlmIChiYWNrZW5kUGFja2FnZSkge1xyXG4gICAgcmV0dXJuIG1hcFRhc2tQYWNrYWdlRnJvbUJhY2tlbmQoYmFja2VuZFBhY2thZ2UpO1xyXG4gIH1cclxuICBjb25zdCBwa2cgPSAoYXdhaXQgbGlzdFRhc2tQYWNrYWdlcygpKS5maW5kKChpdGVtKSA9PiBpdGVtLmlkID09PSBwYWNrYWdlSWQpO1xyXG4gIGlmICghcGtnKSB7XHJcbiAgICB0aHJvdyBjcmVhdGVTZXJ2aWNlRXJyb3IoXCJ0YXNrUGFja2FnZU5vdEZvdW5kXCIpO1xyXG4gIH1cclxuICByZXR1cm4gcGtnO1xyXG59XHJcblxyXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gY2xhaW1UYXNrUGFja2FnZShcclxuICBwYWNrYWdlSWQ6IHN0cmluZyxcclxuKTogUHJvbWlzZTxcclxuICBINVRhc2tQYWNrYWdlICYgeyB0b3RhbENvbW1pc3Npb246IG51bWJlcjsgY3VycmVudENvbW1pc3Npb246IG51bWJlcjsgY29tcGxldGVkSXRlbXM6IG51bWJlcjsgdG90YWxJdGVtczogbnVtYmVyOyBjb3VudGRvd25TZWNvbmRzOiBudW1iZXIgfVxyXG4+IHtcclxuICBjb25zdCBiYWNrZW5kUGFja2FnZSA9IGF3YWl0IHJlcXVlc3RCYWNrZW5kTWVtYmVyRG9tYWluPEJhY2tlbmRUYXNrUGFja2FnZVJlc3BvbnNlPihcclxuICAgIGAvYXBpL2g1L3Rhc2stcGFja2FnZXMvJHtlbmNvZGVVUklDb21wb25lbnQocGFja2FnZUlkKX0vY2xhaW1gLFxyXG4gICAge1xyXG4gICAgICBtZXRob2Q6IFwiUE9TVFwiLFxyXG4gICAgfSxcclxuICApO1xyXG4gIGlmIChiYWNrZW5kUGFja2FnZSkge1xyXG4gICAgcmV0dXJuIG1hcFRhc2tQYWNrYWdlRnJvbUJhY2tlbmQoYmFja2VuZFBhY2thZ2UpO1xyXG4gIH1cclxuICBjb25zdCBzZXNzaW9uID0gZ2V0UmVxdWlyZWRTZXNzaW9uKCk7XHJcbiAgY29uc3QgbmV4dFN0YXRlID0gdXBkYXRlU3RhdGVGb3JBY2NvdW50KHNlc3Npb24uYWNjb3VudElkLCAoc3RhdGUpID0+IHtcclxuICAgIGNvbnN0IHBrZyA9IHN0YXRlLnRhc2tQYWNrYWdlcy5maW5kKChpdGVtKSA9PiBpdGVtLmlkID09PSBwYWNrYWdlSWQpO1xyXG4gICAgaWYgKCFwa2cpIHtcclxuICAgICAgdGhyb3cgY3JlYXRlU2VydmljZUVycm9yKFwidGFza1BhY2thZ2VOb3RGb3VuZFwiKTtcclxuICAgIH1cclxuICAgIGlmIChwa2cuc3RhdHVzICE9PSBcInBlbmRpbmdfY2xhaW1cIikge1xyXG4gICAgICByZXR1cm4gc3RhdGU7XHJcbiAgICB9XHJcbiAgICBjb25zdCBjbGFpbWVkQXQgPSBub3dJc28oKTtcclxuICAgIHBrZy5zdGF0dXMgPSBcImFjdGl2ZVwiO1xyXG4gICAgcGtnLmNsYWltZWRBdCA9IGNsYWltZWRBdDtcclxuICAgIHBrZy5leHBpcmVzQXQgPSBuZXcgRGF0ZShEYXRlLm5vdygpICsgcGtnLmNvbXBsZXRpb25XaW5kb3dIb3VycyAqIDM2MDAgKiAxMDAwKS50b0lTT1N0cmluZygpO1xyXG4gICAgYXBwZW5kTG9jYWxpemVkTWVzc2FnZShzdGF0ZSwgXCJ0YXNrXCIsIFwicGFja2FnZUNsYWltVGl0bGVcIiwgXCJwYWNrYWdlQ2xhaW1Cb2R5XCIsIHtcclxuICAgICAgdGl0bGVQYXJhbXM6IHsgdGl0bGU6IHBrZy50aXRsZSB9LFxyXG4gICAgfSk7XHJcbiAgICByZXR1cm4gc3RhdGU7XHJcbiAgfSk7XHJcbiAgY29uc3QgdXBkYXRlZCA9IG5leHRTdGF0ZS50YXNrUGFja2FnZXMuZmluZCgoaXRlbSkgPT4gaXRlbS5pZCA9PT0gcGFja2FnZUlkKSE7XHJcbiAgcmV0dXJuIG1hcFRhc2tQYWNrYWdlKHVwZGF0ZWQpO1xyXG59XHJcblxyXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gY29tcGxldGVUYXNrUGFja2FnZVB1cmNoYXNlKFxyXG4gIHBhY2thZ2VJZDogc3RyaW5nLFxyXG4gIGl0ZW1JZDogc3RyaW5nLFxyXG4pOiBQcm9taXNlPHtcclxuICBzdWNjZXNzOiBib29sZWFuO1xyXG4gIG9yZGVyPzogSDVNZW1iZXJPcmRlcjtcclxuICB0YXNrUGFja2FnZTogSDVUYXNrUGFja2FnZSAmIHsgdG90YWxDb21taXNzaW9uOiBudW1iZXI7IGN1cnJlbnRDb21taXNzaW9uOiBudW1iZXI7IGNvbXBsZXRlZEl0ZW1zOiBudW1iZXI7IHRvdGFsSXRlbXM6IG51bWJlcjsgY291bnRkb3duU2Vjb25kczogbnVtYmVyIH07XHJcbiAgd2FsbGV0OiBINVdhbGxldFN1bW1hcnk7XHJcbiAgZnJhZ21lbnREcm9wPzogSDVGcmFnbWVudERyb3BMb2cgfCBudWxsO1xyXG4gIHJlYXNvbj86IHN0cmluZztcclxufT4ge1xyXG4gIGNvbnN0IGJhY2tlbmRQdXJjaGFzZSA9IGF3YWl0IHJlcXVlc3RCYWNrZW5kTWVtYmVyRG9tYWluPEJhY2tlbmRUYXNrUGFja2FnZVB1cmNoYXNlUmVzcG9uc2U+KFxyXG4gICAgYC9hcGkvaDUvdGFzay1wYWNrYWdlcy8ke2VuY29kZVVSSUNvbXBvbmVudChwYWNrYWdlSWQpfS9pdGVtcy8ke2VuY29kZVVSSUNvbXBvbmVudChpdGVtSWQpfS9wdXJjaGFzZWAsXHJcbiAgICB7XHJcbiAgICAgIG1ldGhvZDogXCJQT1NUXCIsXHJcbiAgICB9LFxyXG4gICk7XHJcbiAgaWYgKGJhY2tlbmRQdXJjaGFzZSkge1xyXG4gICAgcmV0dXJuIHtcclxuICAgICAgc3VjY2VzczogYmFja2VuZFB1cmNoYXNlLnN1Y2Nlc3MsXHJcbiAgICAgIG9yZGVyOiBiYWNrZW5kUHVyY2hhc2Uub3JkZXIgPyBtYXBPcmRlckZyb21CYWNrZW5kKGJhY2tlbmRQdXJjaGFzZS5vcmRlcikgOiB1bmRlZmluZWQsXHJcbiAgICAgIHRhc2tQYWNrYWdlOiBtYXBUYXNrUGFja2FnZUZyb21CYWNrZW5kKGJhY2tlbmRQdXJjaGFzZS50YXNrUGFja2FnZSksXHJcbiAgICAgIHdhbGxldDogbWFwV2FsbGV0U3VtbWFyeUZyb21CYWNrZW5kKGJhY2tlbmRQdXJjaGFzZS53YWxsZXQpLFxyXG4gICAgICBmcmFnbWVudERyb3A6IGJhY2tlbmRQdXJjaGFzZS5mcmFnbWVudERyb3BcclxuICAgICAgICA/IG1hcEZyYWdtZW50RHJvcEZyb21CYWNrZW5kKGJhY2tlbmRQdXJjaGFzZS5mcmFnbWVudERyb3ApXHJcbiAgICAgICAgOiBudWxsLFxyXG4gICAgICByZWFzb246IGJhY2tlbmRQdXJjaGFzZS5yZWFzb24gPz8gdW5kZWZpbmVkLFxyXG4gICAgfTtcclxuICB9XHJcbiAgY29uc3Qgc2Vzc2lvbiA9IGdldFJlcXVpcmVkU2Vzc2lvbigpO1xyXG4gIGxldCBvcGVyYXRpb25SZXN1bHQ6IHtcclxuICAgIHN1Y2Nlc3M6IGJvb2xlYW47XHJcbiAgICBvcmRlcj86IEg1TWVtYmVyT3JkZXI7XHJcbiAgICB0YXNrUGFja2FnZTogSDVUYXNrUGFja2FnZTtcclxuICAgIGZyYWdtZW50RHJvcD86IEg1RnJhZ21lbnREcm9wTG9nIHwgbnVsbDtcclxuICAgIHJlYXNvbj86IHN0cmluZztcclxuICB9IHwgbnVsbCA9IG51bGw7XHJcbiAgY29uc3QgbmV4dFN0YXRlID0gdXBkYXRlU3RhdGVGb3JBY2NvdW50KHNlc3Npb24uYWNjb3VudElkLCAoc3RhdGUpID0+IHtcclxuICAgIGNvbnN0IHBrZyA9IHN0YXRlLnRhc2tQYWNrYWdlcy5maW5kKChpdGVtKSA9PiBpdGVtLmlkID09PSBwYWNrYWdlSWQpO1xyXG4gICAgaWYgKCFwa2cpIHtcclxuICAgICAgdGhyb3cgY3JlYXRlU2VydmljZUVycm9yKFwidGFza1BhY2thZ2VOb3RGb3VuZFwiKTtcclxuICAgIH1cclxuICAgIGlmIChwa2cuc3RhdHVzICE9PSBcImFjdGl2ZVwiKSB7XHJcbiAgICAgIG9wZXJhdGlvblJlc3VsdCA9IHsgc3VjY2VzczogZmFsc2UsIHRhc2tQYWNrYWdlOiBwa2csIHJlYXNvbjogZ2V0U2VydmljZUVycm9yTWVzc2FnZShcInRhc2tQYWNrYWdlVW5hdmFpbGFibGVcIikgfTtcclxuICAgICAgcmV0dXJuIHN0YXRlO1xyXG4gICAgfVxyXG4gICAgaWYgKHBrZy5leHBpcmVzQXQgJiYgbmV3IERhdGUocGtnLmV4cGlyZXNBdCkuZ2V0VGltZSgpIDw9IERhdGUubm93KCkpIHtcclxuICAgICAgcGtnLnN0YXR1cyA9IFwiZXhwaXJlZFwiO1xyXG4gICAgICBvcGVyYXRpb25SZXN1bHQgPSB7IHN1Y2Nlc3M6IGZhbHNlLCB0YXNrUGFja2FnZTogcGtnLCByZWFzb246IGdldFNlcnZpY2VFcnJvck1lc3NhZ2UoXCJ0YXNrUGFja2FnZUV4cGlyZWRcIikgfTtcclxuICAgICAgcmV0dXJuIHN0YXRlO1xyXG4gICAgfVxyXG4gICAgY29uc3QgaXRlbSA9IHBrZy5pdGVtcy5maW5kKChlbnRyeSkgPT4gZW50cnkuaWQgPT09IGl0ZW1JZCk7XHJcbiAgICBpZiAoIWl0ZW0pIHtcclxuICAgICAgdGhyb3cgY3JlYXRlU2VydmljZUVycm9yKFwidGFza0l0ZW1Ob3RGb3VuZFwiKTtcclxuICAgIH1cclxuICAgIGlmIChpdGVtLmNvbXBsZXRlZF9hdCkge1xyXG4gICAgICBvcGVyYXRpb25SZXN1bHQgPSB7IHN1Y2Nlc3M6IHRydWUsIHRhc2tQYWNrYWdlOiBwa2csIHJlYXNvbjogZ2V0U2VydmljZUVycm9yTWVzc2FnZShcInRhc2tJdGVtQ29tcGxldGVkXCIpIH07XHJcbiAgICAgIHJldHVybiBzdGF0ZTtcclxuICAgIH1cclxuICAgIGlmIChzdGF0ZS53YWxsZXQuc3lzdGVtQmFsYW5jZSA8IGl0ZW0ucHJpY2UpIHtcclxuICAgICAgb3BlcmF0aW9uUmVzdWx0ID0geyBzdWNjZXNzOiBmYWxzZSwgdGFza1BhY2thZ2U6IHBrZywgcmVhc29uOiBnZXRTZXJ2aWNlRXJyb3JNZXNzYWdlKFwic3lzdGVtQmFsYW5jZUluc3VmZmljaWVudFwiKSB9O1xyXG4gICAgICByZXR1cm4gc3RhdGU7XHJcbiAgICB9XHJcbiAgICBzdGF0ZS53YWxsZXQuc3lzdGVtQmFsYW5jZSA9IE51bWJlcigoc3RhdGUud2FsbGV0LnN5c3RlbUJhbGFuY2UgLSBpdGVtLnByaWNlKS50b0ZpeGVkKDIpKTtcclxuICAgIGNvbnN0IG9yZGVyOiBINU1lbWJlck9yZGVyID0ge1xyXG4gICAgICBpZDogY3JlYXRlSWQoXCJvcmRlclwiKSxcclxuICAgICAgb3JkZXJObzogYE9SRC0ke01hdGgucmFuZG9tKCkudG9TdHJpbmcoKS5zbGljZSgyLCAxMCl9YCxcclxuICAgICAgcGFja2FnZUlkOiBwa2cuaWQsXHJcbiAgICAgIHBhY2thZ2VUaXRsZTogcGtnLnRpdGxlLFxyXG4gICAgICBwcm9kdWN0TmFtZTogaXRlbS5wcm9kdWN0X25hbWUsXHJcbiAgICAgIGFtb3VudDogaXRlbS5wcmljZSxcclxuICAgICAgY3VycmVuY3k6IGl0ZW0uY3VycmVuY3ksXHJcbiAgICAgIHN0YXR1czogXCJwYWlkXCIsXHJcbiAgICAgIGNyZWF0ZWRBdDogbm93SXNvKCksXHJcbiAgICAgIHNvdXJjZUxhYmVsOiBwa2cudGl0bGUsXHJcbiAgICB9O1xyXG4gICAgaXRlbS5jb21wbGV0ZWRfYXQgPSBvcmRlci5jcmVhdGVkQXQ7XHJcbiAgICBpdGVtLm9yZGVyX2lkID0gb3JkZXIuaWQ7XHJcbiAgICBzdGF0ZS5vcmRlcnMudW5zaGlmdChvcmRlcik7XHJcbiAgICBhcHBlbmRUcmFuc2FjdGlvbihzdGF0ZSwge1xyXG4gICAgICBsZWRnZXJUeXBlOiBcInN5c3RlbVwiLFxyXG4gICAgICB0cmFuc2FjdGlvblR5cGU6IFwicHVyY2hhc2VcIixcclxuICAgICAgZGlyZWN0aW9uOiBcImRlYml0XCIsXHJcbiAgICAgIGFtb3VudDogaXRlbS5wcmljZSxcclxuICAgICAgY3VycmVuY3k6IGl0ZW0uY3VycmVuY3ksXHJcbiAgICAgIHN0YXR1czogXCJwYWlkXCIsXHJcbiAgICAgIG5vdGU6IGAke3BrZy50aXRsZX0gLyAke2l0ZW0ucHJvZHVjdF9uYW1lfWAsXHJcbiAgICB9KTtcclxuICAgIGFwcGVuZExvY2FsaXplZE1lc3NhZ2Uoc3RhdGUsIFwib3JkZXJcIiwgXCJwdXJjaGFzZVN1Y2Nlc3NUaXRsZVwiLCBcInB1cmNoYXNlU3VjY2Vzc0JvZHlcIiwge1xyXG4gICAgICB0aXRsZVBhcmFtczogeyBwcm9kdWN0OiBpdGVtLnByb2R1Y3RfbmFtZSB9LFxyXG4gICAgfSk7XHJcblxyXG4gICAgbGV0IGZyYWdtZW50RHJvcDogSDVGcmFnbWVudERyb3BMb2cgfCBudWxsID0gbnVsbDtcclxuICAgIGNvbnN0IGNvbXBsZXRlZEl0ZW1zID0gcGtnLml0ZW1zLmZpbHRlcigoZW50cnkpID0+IGVudHJ5LmNvbXBsZXRlZF9hdCkubGVuZ3RoO1xyXG4gICAgaWYgKHBrZy5pdGVtcy5sZW5ndGggPiAwICYmIGNvbXBsZXRlZEl0ZW1zID09PSBwa2cuaXRlbXMubGVuZ3RoKSB7XHJcbiAgICAgIHBrZy5zdGF0dXMgPSBcImNvbXBsZXRlZFwiO1xyXG4gICAgICBwa2cudGFza0JhbGFuY2VBd2FyZGVkQXQgPSBub3dJc28oKTtcclxuICAgICAgY29uc3QgcmV3YXJkQW1vdW50ID0gTnVtYmVyKGNhbGN1bGF0ZVBhY2thZ2VUb3RhbENvbW1pc3Npb24ocGtnKS50b0ZpeGVkKDIpKTtcclxuICAgICAgc3RhdGUud2FsbGV0LnRhc2tCYWxhbmNlID0gTnVtYmVyKChzdGF0ZS53YWxsZXQudGFza0JhbGFuY2UgKyByZXdhcmRBbW91bnQpLnRvRml4ZWQoMikpO1xyXG4gICAgICBhcHBlbmRUcmFuc2FjdGlvbihzdGF0ZSwge1xyXG4gICAgICAgIGxlZGdlclR5cGU6IFwidGFza1wiLFxyXG4gICAgICAgIHRyYW5zYWN0aW9uVHlwZTogXCJ0YXNrX3Jld2FyZFwiLFxyXG4gICAgICAgIGRpcmVjdGlvbjogXCJjcmVkaXRcIixcclxuICAgICAgICBhbW91bnQ6IHJld2FyZEFtb3VudCxcclxuICAgICAgICBjdXJyZW5jeTogc3RhdGUud2FsbGV0LmN1cnJlbmN5LFxyXG4gICAgICAgIHN0YXR1czogXCJwYWlkXCIsXHJcbiAgICAgICAgbm90ZTogYCR7cGtnLnRpdGxlfSBjb21wbGV0ZWRgLFxyXG4gICAgICB9KTtcclxuICAgICAgYXBwZW5kTG9jYWxpemVkTWVzc2FnZShzdGF0ZSwgXCJ0YXNrXCIsIFwicGFja2FnZUNvbXBsZXRlZFRpdGxlXCIsIFwicGFja2FnZUNvbXBsZXRlZEJvZHlcIiwge1xyXG4gICAgICAgIHRpdGxlUGFyYW1zOiB7IHRpdGxlOiBwa2cudGl0bGUgfSxcclxuICAgICAgfSk7XHJcbiAgICAgIGZyYWdtZW50RHJvcCA9IGNyZWF0ZUZyYWdtZW50RHJvcChzdGF0ZSwgXCJ0YXNrXCIpO1xyXG4gICAgfVxyXG4gICAgb3BlcmF0aW9uUmVzdWx0ID0geyBzdWNjZXNzOiB0cnVlLCBvcmRlciwgdGFza1BhY2thZ2U6IHBrZywgZnJhZ21lbnREcm9wIH07XHJcbiAgICByZXR1cm4gc3RhdGU7XHJcbiAgfSk7XHJcblxyXG4gIGlmICghb3BlcmF0aW9uUmVzdWx0KSB7XHJcbiAgICB0aHJvdyBjcmVhdGVTZXJ2aWNlRXJyb3IoXCJwdXJjaGFzZUluaXRGYWlsZWRcIik7XHJcbiAgfVxyXG4gIGNvbnN0IHNldHRsZWRSZXN1bHQgPSBvcGVyYXRpb25SZXN1bHQgYXMge1xyXG4gICAgc3VjY2VzczogYm9vbGVhbjtcclxuICAgIG9yZGVyPzogSDVNZW1iZXJPcmRlcjtcclxuICAgIHRhc2tQYWNrYWdlOiBINVRhc2tQYWNrYWdlO1xyXG4gICAgZnJhZ21lbnREcm9wPzogSDVGcmFnbWVudERyb3BMb2cgfCBudWxsO1xyXG4gICAgcmVhc29uPzogc3RyaW5nO1xyXG4gIH07XHJcbiAgcmV0dXJuIHtcclxuICAgIC4uLnNldHRsZWRSZXN1bHQsXHJcbiAgICB0YXNrUGFja2FnZTogbWFwVGFza1BhY2thZ2Uoc2V0dGxlZFJlc3VsdC50YXNrUGFja2FnZSksXHJcbiAgICB3YWxsZXQ6IGdldFdhbGxldFN1bW1hcnlGcm9tU3RhdGUobmV4dFN0YXRlKSxcclxuICB9O1xyXG59XHJcblxyXG5mdW5jdGlvbiBjcmVhdGVGcmFnbWVudERyb3AoXHJcbiAgc3RhdGU6IFN0b3JlZE1lbWJlclN0YXRlLFxyXG4gIHNvdXJjZTogXCJjaGVja2luXCIgfCBcInRhc2tcIixcclxuKTogSDVGcmFnbWVudERyb3BMb2cge1xyXG4gIGNvbnN0IGRlZmluaXRpb25zID0gZ2V0RnJhZ21lbnREZWZpbml0aW9ucygpO1xyXG4gIGNvbnN0IGluZGV4ID0gc3RhdGUuZnJhZ21lbnREcm9wTG9ncy5sZW5ndGggJSBkZWZpbml0aW9ucy5sZW5ndGg7XHJcbiAgY29uc3QgZnJhZ21lbnQgPSBkZWZpbml0aW9uc1tpbmRleF07XHJcbiAgc3RhdGUuZnJhZ21lbnRJbnZlbnRvcnlbZnJhZ21lbnQuaWRdID0gKHN0YXRlLmZyYWdtZW50SW52ZW50b3J5W2ZyYWdtZW50LmlkXSA/PyAwKSArIDE7XHJcbiAgY29uc3QgZHJvcDogSDVGcmFnbWVudERyb3BMb2cgPSB7XHJcbiAgICBpZDogY3JlYXRlSWQoXCJmcmFnbWVudC1kcm9wXCIpLFxyXG4gICAgZnJhZ21lbnRJZDogZnJhZ21lbnQuaWQsXHJcbiAgICBmcmFnbWVudE5hbWU6IGZyYWdtZW50Lm5hbWUsXHJcbiAgICBzb3VyY2UsXHJcbiAgICBjcmVhdGVkQXQ6IG5vd0lzbygpLFxyXG4gIH07XHJcbiAgc3RhdGUuZnJhZ21lbnREcm9wTG9ncy51bnNoaWZ0KGRyb3ApO1xyXG4gIGFwcGVuZExvY2FsaXplZE1lc3NhZ2UoXHJcbiAgICBzdGF0ZSxcclxuICAgIFwiZnJhZ21lbnRcIixcclxuICAgIFwiZnJhZ21lbnRPYnRhaW5lZFRpdGxlXCIsXHJcbiAgICBzb3VyY2UgPT09IFwiY2hlY2tpblwiID8gXCJmcmFnbWVudE9idGFpbmVkQm9keUNoZWNraW5cIiA6IFwiZnJhZ21lbnRPYnRhaW5lZEJvZHlUYXNrXCIsXHJcbiAgICB7XHJcbiAgICAgIHRpdGxlUGFyYW1zOiB7IGZyYWdtZW50OiBmcmFnbWVudC5uYW1lIH0sXHJcbiAgICB9LFxyXG4gICk7XHJcbiAgcmV0dXJuIGRyb3A7XHJcbn1cclxuXHJcbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBsaXN0TWVtYmVyT3JkZXJzKCk6IFByb21pc2U8SDVNZW1iZXJPcmRlcltdPiB7XHJcbiAgY29uc3QgYmFja2VuZE9yZGVycyA9IGF3YWl0IHJlcXVlc3RCYWNrZW5kTWVtYmVyRG9tYWluPEJhY2tlbmRNZW1iZXJPcmRlclJlc3BvbnNlW10+KFwiL2FwaS9oNS9vcmRlcnNcIik7XHJcbiAgaWYgKGJhY2tlbmRPcmRlcnMpIHtcclxuICAgIHJldHVybiBiYWNrZW5kT3JkZXJzLm1hcCgob3JkZXIpID0+IG1hcE9yZGVyRnJvbUJhY2tlbmQob3JkZXIpKTtcclxuICB9XHJcbiAgY29uc3Qgc2Vzc2lvbiA9IGdldFJlcXVpcmVkU2Vzc2lvbigpO1xyXG4gIGNvbnN0IHN0YXRlID0gZ2V0U3RhdGVGb3JBY2NvdW50KHNlc3Npb24uYWNjb3VudElkKTtcclxuICByZXR1cm4gWy4uLnN0YXRlLm9yZGVyc10uc29ydCgobGVmdCwgcmlnaHQpID0+IHJpZ2h0LmNyZWF0ZWRBdC5sb2NhbGVDb21wYXJlKGxlZnQuY3JlYXRlZEF0KSk7XHJcbn1cclxuXHJcbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBnZXRXYWxsZXRTdW1tYXJ5KCk6IFByb21pc2U8SDVXYWxsZXRTdW1tYXJ5PiB7XHJcbiAgY29uc3QgYmFja2VuZFdhbGxldCA9IGF3YWl0IHJlcXVlc3RCYWNrZW5kTWVtYmVyRG9tYWluPEJhY2tlbmRXYWxsZXRTdW1tYXJ5UmVzcG9uc2U+KFwiL2FwaS9oNS93YWxsZXRcIik7XHJcbiAgaWYgKGJhY2tlbmRXYWxsZXQpIHtcclxuICAgIHJldHVybiBtYXBXYWxsZXRTdW1tYXJ5RnJvbUJhY2tlbmQoYmFja2VuZFdhbGxldCk7XHJcbiAgfVxyXG4gIGNvbnN0IHNlc3Npb24gPSBnZXRSZXF1aXJlZFNlc3Npb24oKTtcclxuICByZXR1cm4gZ2V0V2FsbGV0U3VtbWFyeUZyb21TdGF0ZShnZXRTdGF0ZUZvckFjY291bnQoc2Vzc2lvbi5hY2NvdW50SWQpKTtcclxufVxyXG5cclxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGxpc3RXYWxsZXRUcmFuc2FjdGlvbnMoKTogUHJvbWlzZTxINVdhbGxldFRyYW5zYWN0aW9uW10+IHtcclxuICBjb25zdCBiYWNrZW5kVHJhbnNhY3Rpb25zID0gYXdhaXQgcmVxdWVzdEJhY2tlbmRNZW1iZXJEb21haW48QmFja2VuZFdhbGxldFRyYW5zYWN0aW9uUmVzcG9uc2VbXT4oXHJcbiAgICBcIi9hcGkvaDUvd2FsbGV0L3RyYW5zYWN0aW9uc1wiLFxyXG4gICk7XHJcbiAgaWYgKGJhY2tlbmRUcmFuc2FjdGlvbnMpIHtcclxuICAgIHJldHVybiBiYWNrZW5kVHJhbnNhY3Rpb25zLm1hcCgoaXRlbSkgPT4gbWFwV2FsbGV0VHJhbnNhY3Rpb25Gcm9tQmFja2VuZChpdGVtKSk7XHJcbiAgfVxyXG4gIGNvbnN0IHNlc3Npb24gPSBnZXRSZXF1aXJlZFNlc3Npb24oKTtcclxuICBjb25zdCBzdGF0ZSA9IGdldFN0YXRlRm9yQWNjb3VudChzZXNzaW9uLmFjY291bnRJZCk7XHJcbiAgcmV0dXJuIFsuLi5zdGF0ZS50cmFuc2FjdGlvbnNdLnNvcnQoKGxlZnQsIHJpZ2h0KSA9PiByaWdodC5jcmVhdGVkQXQubG9jYWxlQ29tcGFyZShsZWZ0LmNyZWF0ZWRBdCkpO1xyXG59XHJcblxyXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gbGlzdFdpdGhkcmF3UmVxdWVzdHMoKTogUHJvbWlzZTxINVdpdGhkcmF3UmVxdWVzdFtdPiB7XHJcbiAgY29uc3QgYmFja2VuZFdpdGhkcmF3YWxzID0gYXdhaXQgcmVxdWVzdEJhY2tlbmRNZW1iZXJEb21haW48QmFja2VuZFdpdGhkcmF3YWxSZXNwb25zZVtdPihcclxuICAgIFwiL2FwaS9oNS93aXRoZHJhd2Fsc1wiLFxyXG4gICk7XHJcbiAgaWYgKGJhY2tlbmRXaXRoZHJhd2Fscykge1xyXG4gICAgcmV0dXJuIGJhY2tlbmRXaXRoZHJhd2Fscy5tYXAoKGl0ZW0pID0+IG1hcFdpdGhkcmF3YWxGcm9tQmFja2VuZChpdGVtKSk7XHJcbiAgfVxyXG4gIGNvbnN0IHNlc3Npb24gPSBnZXRSZXF1aXJlZFNlc3Npb24oKTtcclxuICBjb25zdCBzdGF0ZSA9IGdldFN0YXRlRm9yQWNjb3VudChzZXNzaW9uLmFjY291bnRJZCk7XHJcbiAgcmV0dXJuIFsuLi5zdGF0ZS53aXRoZHJhd1JlcXVlc3RzXS5zb3J0KChsZWZ0LCByaWdodCkgPT4gcmlnaHQuY3JlYXRlZEF0LmxvY2FsZUNvbXBhcmUobGVmdC5jcmVhdGVkQXQpKTtcclxufVxyXG5cclxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGNyZWF0ZVJlY2hhcmdlT3JkZXIoYW1vdW50OiBudW1iZXIpOiBQcm9taXNlPEg1V2FsbGV0U3VtbWFyeT4ge1xyXG4gIGNvbnN0IGJhY2tlbmRXYWxsZXQgPSBhd2FpdCByZXF1ZXN0QmFja2VuZE1lbWJlckRvbWFpbjxCYWNrZW5kV2FsbGV0U3VtbWFyeVJlc3BvbnNlPihcclxuICAgIFwiL2FwaS9oNS93YWxsZXQvcmVjaGFyZ2VzXCIsXHJcbiAgICB7XHJcbiAgICAgIG1ldGhvZDogXCJQT1NUXCIsXHJcbiAgICAgIGhlYWRlcnM6IHsgXCJDb250ZW50LVR5cGVcIjogXCJhcHBsaWNhdGlvbi9qc29uXCIgfSxcclxuICAgICAgYm9keTogSlNPTi5zdHJpbmdpZnkoeyBhbW91bnQgfSksXHJcbiAgICB9LFxyXG4gICk7XHJcbiAgaWYgKGJhY2tlbmRXYWxsZXQpIHtcclxuICAgIHJldHVybiBtYXBXYWxsZXRTdW1tYXJ5RnJvbUJhY2tlbmQoYmFja2VuZFdhbGxldCk7XHJcbiAgfVxyXG4gIGNvbnN0IHNlc3Npb24gPSBnZXRSZXF1aXJlZFNlc3Npb24oKTtcclxuICBjb25zdCBzYW5pdGl6ZWRBbW91bnQgPSBOdW1iZXIoYW1vdW50LnRvRml4ZWQoMikpO1xyXG4gIGlmIChzYW5pdGl6ZWRBbW91bnQgPD0gMCkge1xyXG4gICAgdGhyb3cgY3JlYXRlU2VydmljZUVycm9yKFwicmVjaGFyZ2VBbW91bnRJbnZhbGlkXCIpO1xyXG4gIH1cclxuICBjb25zdCBzdGF0ZSA9IHVwZGF0ZVN0YXRlRm9yQWNjb3VudChzZXNzaW9uLmFjY291bnRJZCwgKGRyYWZ0KSA9PiB7XHJcbiAgICBkcmFmdC53YWxsZXQuc3lzdGVtQmFsYW5jZSA9IE51bWJlcigoZHJhZnQud2FsbGV0LnN5c3RlbUJhbGFuY2UgKyBzYW5pdGl6ZWRBbW91bnQpLnRvRml4ZWQoMikpO1xyXG4gICAgYXBwZW5kVHJhbnNhY3Rpb24oZHJhZnQsIHtcclxuICAgICAgbGVkZ2VyVHlwZTogXCJzeXN0ZW1cIixcclxuICAgICAgdHJhbnNhY3Rpb25UeXBlOiBcInJlY2hhcmdlXCIsXHJcbiAgICAgIGRpcmVjdGlvbjogXCJjcmVkaXRcIixcclxuICAgICAgYW1vdW50OiBzYW5pdGl6ZWRBbW91bnQsXHJcbiAgICAgIGN1cnJlbmN5OiBkcmFmdC53YWxsZXQuY3VycmVuY3ksXHJcbiAgICAgIHN0YXR1czogXCJwYWlkXCIsXHJcbiAgICAgIG5vdGU6IFwiUHJvdG90eXBlIHJlY2hhcmdlXCIsXHJcbiAgICB9KTtcclxuICAgIGFwcGVuZExvY2FsaXplZE1lc3NhZ2UoZHJhZnQsIFwid2FsbGV0XCIsIFwicmVjaGFyZ2VUaXRsZVwiLCBcInJlY2hhcmdlQm9keVwiLCB7XHJcbiAgICAgIGJvZHlQYXJhbXM6IHsgYW1vdW50OiBzYW5pdGl6ZWRBbW91bnQudG9GaXhlZCgyKSB9LFxyXG4gICAgfSk7XHJcbiAgICByZXR1cm4gZHJhZnQ7XHJcbiAgfSk7XHJcbiAgcmV0dXJuIGdldFdhbGxldFN1bW1hcnlGcm9tU3RhdGUoc3RhdGUpO1xyXG59XHJcblxyXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gdHJhbnNmZXJUYXNrQmFsYW5jZVRvU3lzdGVtKGFtb3VudDogbnVtYmVyKTogUHJvbWlzZTxINVdhbGxldFN1bW1hcnk+IHtcclxuICBjb25zdCBiYWNrZW5kV2FsbGV0ID0gYXdhaXQgcmVxdWVzdEJhY2tlbmRNZW1iZXJEb21haW48QmFja2VuZFdhbGxldFN1bW1hcnlSZXNwb25zZT4oXHJcbiAgICBcIi9hcGkvaDUvd2FsbGV0L3RyYW5zZmVyc1wiLFxyXG4gICAge1xyXG4gICAgICBtZXRob2Q6IFwiUE9TVFwiLFxyXG4gICAgICBoZWFkZXJzOiB7IFwiQ29udGVudC1UeXBlXCI6IFwiYXBwbGljYXRpb24vanNvblwiIH0sXHJcbiAgICAgIGJvZHk6IEpTT04uc3RyaW5naWZ5KHsgYW1vdW50IH0pLFxyXG4gICAgfSxcclxuICApO1xyXG4gIGlmIChiYWNrZW5kV2FsbGV0KSB7XHJcbiAgICByZXR1cm4gbWFwV2FsbGV0U3VtbWFyeUZyb21CYWNrZW5kKGJhY2tlbmRXYWxsZXQpO1xyXG4gIH1cclxuICBjb25zdCBzZXNzaW9uID0gZ2V0UmVxdWlyZWRTZXNzaW9uKCk7XHJcbiAgY29uc3Qgc2FuaXRpemVkQW1vdW50ID0gTnVtYmVyKGFtb3VudC50b0ZpeGVkKDIpKTtcclxuICBpZiAoc2FuaXRpemVkQW1vdW50IDw9IDApIHtcclxuICAgIHRocm93IGNyZWF0ZVNlcnZpY2VFcnJvcihcInRyYW5zZmVyQW1vdW50SW52YWxpZFwiKTtcclxuICB9XHJcbiAgY29uc3Qgc3RhdGUgPSB1cGRhdGVTdGF0ZUZvckFjY291bnQoc2Vzc2lvbi5hY2NvdW50SWQsIChkcmFmdCkgPT4ge1xyXG4gICAgaWYgKGRyYWZ0LndhbGxldC50YXNrQmFsYW5jZSA8IHNhbml0aXplZEFtb3VudCkge1xyXG4gICAgICB0aHJvdyBjcmVhdGVTZXJ2aWNlRXJyb3IoXCJ0YXNrQmFsYW5jZUluc3VmZmljaWVudFwiKTtcclxuICAgIH1cclxuICAgIGRyYWZ0LndhbGxldC50YXNrQmFsYW5jZSA9IE51bWJlcigoZHJhZnQud2FsbGV0LnRhc2tCYWxhbmNlIC0gc2FuaXRpemVkQW1vdW50KS50b0ZpeGVkKDIpKTtcclxuICAgIGRyYWZ0LndhbGxldC5zeXN0ZW1CYWxhbmNlID0gTnVtYmVyKChkcmFmdC53YWxsZXQuc3lzdGVtQmFsYW5jZSArIHNhbml0aXplZEFtb3VudCkudG9GaXhlZCgyKSk7XHJcbiAgICBhcHBlbmRUcmFuc2FjdGlvbihkcmFmdCwge1xyXG4gICAgICBsZWRnZXJUeXBlOiBcInRhc2tcIixcclxuICAgICAgdHJhbnNhY3Rpb25UeXBlOiBcInRhc2tfdG9fc3lzdGVtX3RyYW5zZmVyXCIsXHJcbiAgICAgIGRpcmVjdGlvbjogXCJkZWJpdFwiLFxyXG4gICAgICBhbW91bnQ6IHNhbml0aXplZEFtb3VudCxcclxuICAgICAgY3VycmVuY3k6IGRyYWZ0LndhbGxldC5jdXJyZW5jeSxcclxuICAgICAgc3RhdHVzOiBcInBhaWRcIixcclxuICAgICAgbm90ZTogXCJUcmFuc2ZlciBvdXQgZnJvbSB0YXNrIGJhbGFuY2VcIixcclxuICAgIH0pO1xyXG4gICAgYXBwZW5kVHJhbnNhY3Rpb24oZHJhZnQsIHtcclxuICAgICAgbGVkZ2VyVHlwZTogXCJzeXN0ZW1cIixcclxuICAgICAgdHJhbnNhY3Rpb25UeXBlOiBcInRhc2tfdG9fc3lzdGVtX3RyYW5zZmVyXCIsXHJcbiAgICAgIGRpcmVjdGlvbjogXCJjcmVkaXRcIixcclxuICAgICAgYW1vdW50OiBzYW5pdGl6ZWRBbW91bnQsXHJcbiAgICAgIGN1cnJlbmN5OiBkcmFmdC53YWxsZXQuY3VycmVuY3ksXHJcbiAgICAgIHN0YXR1czogXCJwYWlkXCIsXHJcbiAgICAgIG5vdGU6IFwiVHJhbnNmZXIgaW4gZnJvbSB0YXNrIGJhbGFuY2VcIixcclxuICAgIH0pO1xyXG4gICAgYXBwZW5kTG9jYWxpemVkTWVzc2FnZShkcmFmdCwgXCJ3YWxsZXRcIiwgXCJ0cmFuc2ZlclRpdGxlXCIsIFwidHJhbnNmZXJCb2R5XCIpO1xyXG4gICAgcmV0dXJuIGRyYWZ0O1xyXG4gIH0pO1xyXG4gIHJldHVybiBnZXRXYWxsZXRTdW1tYXJ5RnJvbVN0YXRlKHN0YXRlKTtcclxufVxyXG5cclxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGNyZWF0ZVdpdGhkcmF3UmVxdWVzdChhbW91bnQ6IG51bWJlcik6IFByb21pc2U8SDVXYWxsZXRTdW1tYXJ5PiB7XHJcbiAgY29uc3QgYmFja2VuZFdpdGhkcmF3YWwgPSBhd2FpdCByZXF1ZXN0QmFja2VuZE1lbWJlckRvbWFpbjxCYWNrZW5kV2l0aGRyYXdhbFJlc3BvbnNlPihcclxuICAgIFwiL2FwaS9oNS93aXRoZHJhd2Fsc1wiLFxyXG4gICAge1xyXG4gICAgICBtZXRob2Q6IFwiUE9TVFwiLFxyXG4gICAgICBoZWFkZXJzOiB7IFwiQ29udGVudC1UeXBlXCI6IFwiYXBwbGljYXRpb24vanNvblwiIH0sXHJcbiAgICAgIGJvZHk6IEpTT04uc3RyaW5naWZ5KHsgYW1vdW50IH0pLFxyXG4gICAgfSxcclxuICApO1xyXG4gIGlmIChiYWNrZW5kV2l0aGRyYXdhbCkge1xyXG4gICAgcmV0dXJuIGdldFdhbGxldFN1bW1hcnkoKTtcclxuICB9XHJcbiAgY29uc3Qgc2Vzc2lvbiA9IGdldFJlcXVpcmVkU2Vzc2lvbigpO1xyXG4gIGNvbnN0IHNhbml0aXplZEFtb3VudCA9IE51bWJlcihhbW91bnQudG9GaXhlZCgyKSk7XHJcbiAgY29uc3Qgc3RhdGUgPSB1cGRhdGVTdGF0ZUZvckFjY291bnQoc2Vzc2lvbi5hY2NvdW50SWQsIChkcmFmdCkgPT4ge1xyXG4gICAgaWYgKGRyYWZ0LndhbGxldC5zeXN0ZW1CYWxhbmNlIDwgZHJhZnQud2FsbGV0LndpdGhkcmF3VGhyZXNob2xkKSB7XHJcbiAgICAgIHRocm93IGNyZWF0ZVNlcnZpY2VFcnJvcihcIndpdGhkcmF3VGhyZXNob2xkTm90TWV0XCIpO1xyXG4gICAgfVxyXG4gICAgaWYgKHNhbml0aXplZEFtb3VudCA8PSAwKSB7XHJcbiAgICAgIHRocm93IGNyZWF0ZVNlcnZpY2VFcnJvcihcIndpdGhkcmF3QW1vdW50SW52YWxpZFwiKTtcclxuICAgIH1cclxuICAgIGlmIChkcmFmdC53YWxsZXQuc3lzdGVtQmFsYW5jZSA8IHNhbml0aXplZEFtb3VudCkge1xyXG4gICAgICB0aHJvdyBjcmVhdGVTZXJ2aWNlRXJyb3IoXCJzeXN0ZW1CYWxhbmNlSW5zdWZmaWNpZW50XCIpO1xyXG4gICAgfVxyXG4gICAgZHJhZnQud2FsbGV0LnN5c3RlbUJhbGFuY2UgPSBOdW1iZXIoKGRyYWZ0LndhbGxldC5zeXN0ZW1CYWxhbmNlIC0gc2FuaXRpemVkQW1vdW50KS50b0ZpeGVkKDIpKTtcclxuICAgIGRyYWZ0LndpdGhkcmF3UmVxdWVzdHMudW5zaGlmdCh7XHJcbiAgICAgIGlkOiBjcmVhdGVJZChcIndpdGhkcmF3XCIpLFxyXG4gICAgICBhbW91bnQ6IHNhbml0aXplZEFtb3VudCxcclxuICAgICAgY3VycmVuY3k6IGRyYWZ0LndhbGxldC5jdXJyZW5jeSxcclxuICAgICAgc3RhdHVzOiBcInN1Ym1pdHRlZFwiLFxyXG4gICAgICBjcmVhdGVkQXQ6IG5vd0lzbygpLFxyXG4gICAgfSk7XHJcbiAgICBhcHBlbmRUcmFuc2FjdGlvbihkcmFmdCwge1xyXG4gICAgICBsZWRnZXJUeXBlOiBcInN5c3RlbVwiLFxyXG4gICAgICB0cmFuc2FjdGlvblR5cGU6IFwid2l0aGRyYXdfcmVxdWVzdFwiLFxyXG4gICAgICBkaXJlY3Rpb246IFwiZGViaXRcIixcclxuICAgICAgYW1vdW50OiBzYW5pdGl6ZWRBbW91bnQsXHJcbiAgICAgIGN1cnJlbmN5OiBkcmFmdC53YWxsZXQuY3VycmVuY3ksXHJcbiAgICAgIHN0YXR1czogXCJzdWJtaXR0ZWRcIixcclxuICAgICAgbm90ZTogXCJXaXRoZHJhd2FsIHJlcXVlc3Qgc3VibWl0dGVkXCIsXHJcbiAgICB9KTtcclxuICAgIGFwcGVuZExvY2FsaXplZE1lc3NhZ2UoZHJhZnQsIFwid2FsbGV0XCIsIFwid2l0aGRyYXdUaXRsZVwiLCBcIndpdGhkcmF3Qm9keVwiKTtcclxuICAgIHJldHVybiBkcmFmdDtcclxuICB9KTtcclxuICByZXR1cm4gZ2V0V2FsbGV0U3VtbWFyeUZyb21TdGF0ZShzdGF0ZSk7XHJcbn1cclxuXHJcbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBnZXRXaXRoZHJhd0xlYWRlcmJvYXJkKCk6IFByb21pc2U8SDVMZWFkZXJib2FyZEVudHJ5W10+IHtcclxuICBjb25zdCBiYWNrZW5kTGVhZGVyYm9hcmQgPSBhd2FpdCByZXF1ZXN0QmFja2VuZE1lbWJlckRvbWFpbjxCYWNrZW5kV2l0aGRyYXdMZWFkZXJib2FyZFJlc3BvbnNlW10+KFxyXG4gICAgXCIvYXBpL2g1L3dpdGhkcmF3LWxlYWRlcmJvYXJkXCIsXHJcbiAgKTtcclxuICBpZiAoYmFja2VuZExlYWRlcmJvYXJkKSB7XHJcbiAgICByZXR1cm4gYmFja2VuZExlYWRlcmJvYXJkLm1hcCgoaXRlbSkgPT4gbWFwTGVhZGVyYm9hcmRFbnRyeUZyb21CYWNrZW5kKGl0ZW0pKTtcclxuICB9XHJcbiAgY29uc3Qgc3RhdGVzID0gcmVhZE1lbWJlclN0YXRlcygpO1xyXG4gIGNvbnN0IGR5bmFtaWMgPSBPYmplY3QuZW50cmllcyhzdGF0ZXMpLm1hcCgoW2FjY291bnRJZCwgc3RhdGVdKSA9PiAoe1xyXG4gICAgYWNjb3VudElkLFxyXG4gICAgYW1vdW50OiBzdGF0ZS53aXRoZHJhd1JlcXVlc3RzXHJcbiAgICAgIC5maWx0ZXIoKGl0ZW0pID0+IGl0ZW0uc3RhdHVzID09PSBcInBhaWRcIilcclxuICAgICAgLnJlZHVjZSgoc3VtLCBpdGVtKSA9PiBzdW0gKyBpdGVtLmFtb3VudCwgMCksXHJcbiAgICBjdXJyZW5jeTogc3RhdGUud2FsbGV0LmN1cnJlbmN5LFxyXG4gIH0pKTtcclxuICByZXR1cm4gWy4uLmdldExlYWRlcmJvYXJkQmFzZUVudHJpZXMoKSwgLi4uZHluYW1pY11cclxuICAgIC5maWx0ZXIoKGl0ZW0pID0+IGl0ZW0uYW1vdW50ID4gMClcclxuICAgIC5zb3J0KChsZWZ0LCByaWdodCkgPT4gcmlnaHQuYW1vdW50IC0gbGVmdC5hbW91bnQpXHJcbiAgICAuc2xpY2UoMCwgMTApXHJcbiAgICAubWFwKChpdGVtLCBpbmRleCkgPT4gKHtcclxuICAgICAgcmFuazogaW5kZXggKyAxLFxyXG4gICAgICBhY2NvdW50SWRNYXNrZWQ6IG1hc2tBY2NvdW50SWQoaXRlbS5hY2NvdW50SWQpLFxyXG4gICAgICBhbW91bnQ6IE51bWJlcihpdGVtLmFtb3VudC50b0ZpeGVkKDIpKSxcclxuICAgICAgY3VycmVuY3k6IGl0ZW0uY3VycmVuY3ksXHJcbiAgICB9KSk7XHJcbn1cclxuXHJcbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBsaXN0TWVtYmVyTWVzc2FnZXMoKTogUHJvbWlzZTxINU1lc3NhZ2VJdGVtW10+IHtcclxuICBjb25zdCBiYWNrZW5kTWVzc2FnZXMgPSBhd2FpdCByZXF1ZXN0QmFja2VuZE1lbWJlckRvbWFpbjxCYWNrZW5kTWVtYmVyTWVzc2FnZVJlc3BvbnNlW10+KFwiL2FwaS9oNS9tZXNzYWdlc1wiKTtcclxuICBpZiAoYmFja2VuZE1lc3NhZ2VzKSB7XHJcbiAgICByZXR1cm4gYmFja2VuZE1lc3NhZ2VzLm1hcCgoaXRlbSkgPT4gbWFwTWVzc2FnZUZyb21CYWNrZW5kKGl0ZW0pKTtcclxuICB9XHJcbiAgY29uc3Qgc2Vzc2lvbiA9IGdldFJlcXVpcmVkU2Vzc2lvbigpO1xyXG4gIGNvbnN0IHN0YXRlID0gZ2V0U3RhdGVGb3JBY2NvdW50KHNlc3Npb24uYWNjb3VudElkKTtcclxuICByZXR1cm4gWy4uLnN0YXRlLm1lc3NhZ2VzXS5zb3J0KChsZWZ0LCByaWdodCkgPT4gcmlnaHQuY3JlYXRlZEF0LmxvY2FsZUNvbXBhcmUobGVmdC5jcmVhdGVkQXQpKTtcclxufVxyXG5cclxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIG1hcmtNZXNzYWdlUmVhZChtZXNzYWdlSWQ6IHN0cmluZyk6IFByb21pc2U8dm9pZD4ge1xyXG4gIGNvbnN0IGJhY2tlbmRNZXNzYWdlID0gYXdhaXQgcmVxdWVzdEJhY2tlbmRNZW1iZXJEb21haW48QmFja2VuZE1lbWJlck1lc3NhZ2VSZXNwb25zZT4oXHJcbiAgICBgL2FwaS9oNS9tZXNzYWdlcy8ke2VuY29kZVVSSUNvbXBvbmVudChtZXNzYWdlSWQpfS9yZWFkYCxcclxuICAgIHtcclxuICAgICAgbWV0aG9kOiBcIlBPU1RcIixcclxuICAgIH0sXHJcbiAgKTtcclxuICBpZiAoYmFja2VuZE1lc3NhZ2UpIHtcclxuICAgIHJldHVybjtcclxuICB9XHJcbiAgY29uc3Qgc2Vzc2lvbiA9IGdldFJlcXVpcmVkU2Vzc2lvbigpO1xyXG4gIHVwZGF0ZVN0YXRlRm9yQWNjb3VudChzZXNzaW9uLmFjY291bnRJZCwgKGRyYWZ0KSA9PiB7XHJcbiAgICBjb25zdCBpdGVtID0gZHJhZnQubWVzc2FnZXMuZmluZCgoZW50cnkpID0+IGVudHJ5LmlkID09PSBtZXNzYWdlSWQpO1xyXG4gICAgaWYgKGl0ZW0pIHtcclxuICAgICAgaXRlbS5pc1JlYWQgPSB0cnVlO1xyXG4gICAgfVxyXG4gICAgcmV0dXJuIGRyYWZ0O1xyXG4gIH0pO1xyXG59XHJcblxyXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gbWFya0FsbE1lc3NhZ2VzUmVhZCgpOiBQcm9taXNlPHZvaWQ+IHtcclxuICBjb25zdCBiYWNrZW5kUmVzdWx0ID0gYXdhaXQgcmVxdWVzdEJhY2tlbmRNZW1iZXJEb21haW48eyB1cGRhdGVkOiBudW1iZXIgfT4oXHJcbiAgICBcIi9hcGkvaDUvbWVzc2FnZXMvcmVhZC1hbGxcIixcclxuICAgIHtcclxuICAgICAgbWV0aG9kOiBcIlBPU1RcIixcclxuICAgIH0sXHJcbiAgKTtcclxuICBpZiAoYmFja2VuZFJlc3VsdCkge1xyXG4gICAgcmV0dXJuO1xyXG4gIH1cclxuICBjb25zdCBzZXNzaW9uID0gZ2V0UmVxdWlyZWRTZXNzaW9uKCk7XHJcbiAgdXBkYXRlU3RhdGVGb3JBY2NvdW50KHNlc3Npb24uYWNjb3VudElkLCAoZHJhZnQpID0+IHtcclxuICAgIGRyYWZ0Lm1lc3NhZ2VzID0gZHJhZnQubWVzc2FnZXMubWFwKChpdGVtKSA9PiAoeyAuLi5pdGVtLCBpc1JlYWQ6IHRydWUgfSkpO1xyXG4gICAgcmV0dXJuIGRyYWZ0O1xyXG4gIH0pO1xyXG59XHJcblxyXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gZ2V0TWVtYmVyVmVyaWZpY2F0aW9uU3VtbWFyeSgpOiBQcm9taXNlPEg1TWVtYmVyVmVyaWZpY2F0aW9uU3VtbWFyeT4ge1xyXG4gIGNvbnN0IGJhY2tlbmRTdW1tYXJ5ID0gYXdhaXQgcmVxdWVzdEJhY2tlbmRNZW1iZXJEb21haW48QmFja2VuZE1lbWJlclZlcmlmaWNhdGlvblN1bW1hcnlSZXNwb25zZT4oXHJcbiAgICBcIi9hcGkvaDUvbWVtYmVyL3ZlcmlmaWNhdGlvblwiLFxyXG4gICk7XHJcbiAgaWYgKGJhY2tlbmRTdW1tYXJ5KSB7XHJcbiAgICByZXR1cm4gbWFwVmVyaWZpY2F0aW9uU3VtbWFyeUZyb21CYWNrZW5kKGJhY2tlbmRTdW1tYXJ5KTtcclxuICB9XHJcbiAgY29uc3Qgc2Vzc2lvbiA9IGdldFJlcXVpcmVkU2Vzc2lvbigpO1xyXG4gIGNvbnN0IHN0YXRlID0gZ2V0U3RhdGVGb3JBY2NvdW50KHNlc3Npb24uYWNjb3VudElkKTtcclxuICByZXR1cm4gYnVpbGRWZXJpZmljYXRpb25TdW1tYXJ5RnJvbVJlcXVlc3RzKHN0YXRlLnZlcmlmaWNhdGlvblJlcXVlc3RzID8/IFtdKTtcclxufVxyXG5cclxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGxpc3RNZW1iZXJWZXJpZmljYXRpb25SZXF1ZXN0cygpOiBQcm9taXNlPEg1TWVtYmVyVmVyaWZpY2F0aW9uUmVxdWVzdFtdPiB7XHJcbiAgY29uc3QgYmFja2VuZFJlcXVlc3RzID0gYXdhaXQgcmVxdWVzdEJhY2tlbmRNZW1iZXJEb21haW48QmFja2VuZE1lbWJlclZlcmlmaWNhdGlvblJlcXVlc3RSZXNwb25zZVtdPihcclxuICAgIFwiL2FwaS9oNS9tZW1iZXIvdmVyaWZpY2F0aW9uL3JlcXVlc3RzXCIsXHJcbiAgKTtcclxuICBpZiAoYmFja2VuZFJlcXVlc3RzKSB7XHJcbiAgICByZXR1cm4gYmFja2VuZFJlcXVlc3RzLm1hcCgoaXRlbSkgPT4gbWFwVmVyaWZpY2F0aW9uUmVxdWVzdEZyb21CYWNrZW5kKGl0ZW0pKTtcclxuICB9XHJcbiAgY29uc3Qgc2Vzc2lvbiA9IGdldFJlcXVpcmVkU2Vzc2lvbigpO1xyXG4gIGNvbnN0IHN0YXRlID0gZ2V0U3RhdGVGb3JBY2NvdW50KHNlc3Npb24uYWNjb3VudElkKTtcclxuICByZXR1cm4gWy4uLihzdGF0ZS52ZXJpZmljYXRpb25SZXF1ZXN0cyA/PyBbXSldLnNvcnQoKGxlZnQsIHJpZ2h0KSA9PiByaWdodC5jcmVhdGVkQXQubG9jYWxlQ29tcGFyZShsZWZ0LmNyZWF0ZWRBdCkpO1xyXG59XHJcblxyXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gY3JlYXRlTWVtYmVyVmVyaWZpY2F0aW9uUmVxdWVzdChcclxuICBwYXlsb2FkOiBINU1lbWJlclZlcmlmaWNhdGlvbkNyZWF0ZUlucHV0LFxyXG4pOiBQcm9taXNlPEg1TWVtYmVyVmVyaWZpY2F0aW9uUmVxdWVzdD4ge1xyXG4gIGNvbnN0IHJlcXVlc3RQYXlsb2FkID0ge1xyXG4gICAgcmVxdWVzdFR5cGU6IHBheWxvYWQucmVxdWVzdFR5cGU/LnRyaW0oKSB8fCBcImlkZW50aXR5XCIsXHJcbiAgICBub3RlczogcGF5bG9hZC5ub3Rlcz8udHJpbSgpIHx8IG51bGwsXHJcbiAgICBkb2N1bWVudHM6IChwYXlsb2FkLmRvY3VtZW50cyA/PyBbXSkubWFwKChpdGVtKSA9PiAoe1xyXG4gICAgICBmaWxlTmFtZTogaXRlbS5maWxlTmFtZS50cmltKCksXHJcbiAgICAgIG1pbWVUeXBlOiBpdGVtLm1pbWVUeXBlPy50cmltKCkgfHwgbnVsbCxcclxuICAgICAgc3RvcmFnZUtleTogaXRlbS5zdG9yYWdlS2V5Py50cmltKCkgfHwgbnVsbCxcclxuICAgICAgbWV0YWRhdGFKc29uOiBpdGVtLm1ldGFkYXRhSnNvbiA/PyBudWxsLFxyXG4gICAgfSkpLFxyXG4gIH07XHJcbiAgY29uc3QgYmFja2VuZFJlcXVlc3QgPSBhd2FpdCByZXF1ZXN0QmFja2VuZE1lbWJlckRvbWFpbjxCYWNrZW5kTWVtYmVyVmVyaWZpY2F0aW9uUmVxdWVzdFJlc3BvbnNlPihcclxuICAgIFwiL2FwaS9oNS9tZW1iZXIvdmVyaWZpY2F0aW9uL3JlcXVlc3RzXCIsXHJcbiAgICB7XHJcbiAgICAgIG1ldGhvZDogXCJQT1NUXCIsXHJcbiAgICAgIGhlYWRlcnM6IHsgXCJDb250ZW50LVR5cGVcIjogXCJhcHBsaWNhdGlvbi9qc29uXCIgfSxcclxuICAgICAgYm9keTogSlNPTi5zdHJpbmdpZnkocmVxdWVzdFBheWxvYWQpLFxyXG4gICAgfSxcclxuICApO1xyXG4gIGlmIChiYWNrZW5kUmVxdWVzdCkge1xyXG4gICAgcmV0dXJuIG1hcFZlcmlmaWNhdGlvblJlcXVlc3RGcm9tQmFja2VuZChiYWNrZW5kUmVxdWVzdCk7XHJcbiAgfVxyXG4gIGNvbnN0IHNlc3Npb24gPSBnZXRSZXF1aXJlZFNlc3Npb24oKTtcclxuICBjb25zdCBzdGF0ZSA9IHVwZGF0ZVN0YXRlRm9yQWNjb3VudChzZXNzaW9uLmFjY291bnRJZCwgKGRyYWZ0KSA9PiB7XHJcbiAgICBjb25zdCBjdXJyZW50U3VtbWFyeSA9IGJ1aWxkVmVyaWZpY2F0aW9uU3VtbWFyeUZyb21SZXF1ZXN0cyhkcmFmdC52ZXJpZmljYXRpb25SZXF1ZXN0cyA/PyBbXSk7XHJcbiAgICBpZiAoY3VycmVudFN1bW1hcnkuaGFzQWN0aXZlUmVxdWVzdCkge1xyXG4gICAgICB0aHJvdyBuZXcgRXJyb3IoXCJBbiBhY3RpdmUgdmVyaWZpY2F0aW9uIHJlcXVlc3QgYWxyZWFkeSBleGlzdHMuXCIpO1xyXG4gICAgfVxyXG4gICAgY29uc3QgY3JlYXRlZEF0ID0gbm93SXNvKCk7XHJcbiAgICBjb25zdCBuZXh0UmVxdWVzdDogSDVNZW1iZXJWZXJpZmljYXRpb25SZXF1ZXN0ID0ge1xyXG4gICAgICBpZDogY3JlYXRlSWQoXCJ2ZXJpZmljYXRpb24tcmVxdWVzdFwiKSxcclxuICAgICAgcmVxdWVzdFR5cGU6IHJlcXVlc3RQYXlsb2FkLnJlcXVlc3RUeXBlLFxyXG4gICAgICBzdGF0dXM6IFwicGVuZGluZ1wiLFxyXG4gICAgICBub3RlczogcmVxdWVzdFBheWxvYWQubm90ZXMsXHJcbiAgICAgIHJldmlld05vdGU6IG51bGwsXHJcbiAgICAgIHJldmlld2VyQWN0b3JJZDogbnVsbCxcclxuICAgICAgcmV2aWV3ZWRBdDogbnVsbCxcclxuICAgICAgY3JlYXRlZEF0LFxyXG4gICAgICB1cGRhdGVkQXQ6IGNyZWF0ZWRBdCxcclxuICAgICAgZG9jdW1lbnRzOiByZXF1ZXN0UGF5bG9hZC5kb2N1bWVudHMubWFwKChpdGVtKSA9PiAoe1xyXG4gICAgICAgIGlkOiBjcmVhdGVJZChcInZlcmlmaWNhdGlvbi1kb2N1bWVudFwiKSxcclxuICAgICAgICBmaWxlTmFtZTogaXRlbS5maWxlTmFtZSxcclxuICAgICAgICBtaW1lVHlwZTogaXRlbS5taW1lVHlwZSxcclxuICAgICAgICBzdG9yYWdlS2V5OiBpdGVtLnN0b3JhZ2VLZXksXHJcbiAgICAgICAgbWV0YWRhdGFKc29uOiBpdGVtLm1ldGFkYXRhSnNvbixcclxuICAgICAgICBjcmVhdGVkQXQsXHJcbiAgICAgIH0pKSxcclxuICAgIH07XHJcbiAgICBkcmFmdC52ZXJpZmljYXRpb25SZXF1ZXN0cyA9IFtuZXh0UmVxdWVzdCwgLi4uKGRyYWZ0LnZlcmlmaWNhdGlvblJlcXVlc3RzID8/IFtdKV07XHJcbiAgICBhcHBlbmRMb2NhbGl6ZWRNZXNzYWdlKGRyYWZ0LCBcInN5c3RlbVwiLCBcInZlcmlmaWNhdGlvblN1Ym1pdHRlZFRpdGxlXCIsIFwidmVyaWZpY2F0aW9uU3VibWl0dGVkQm9keVwiKTtcclxuICAgIHJldHVybiBkcmFmdDtcclxuICB9KTtcclxuICByZXR1cm4gc3RhdGUudmVyaWZpY2F0aW9uUmVxdWVzdHNbMF0hO1xyXG59XHJcblxyXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gZ2V0TWVtYmVyVmVyaWZpY2F0aW9uUmVxdWVzdERldGFpbChcclxuICByZXF1ZXN0SWQ6IHN0cmluZyxcclxuKTogUHJvbWlzZTxINU1lbWJlclZlcmlmaWNhdGlvblJlcXVlc3Q+IHtcclxuICBjb25zdCBiYWNrZW5kUmVxdWVzdCA9IGF3YWl0IHJlcXVlc3RCYWNrZW5kTWVtYmVyRG9tYWluPEJhY2tlbmRNZW1iZXJWZXJpZmljYXRpb25SZXF1ZXN0UmVzcG9uc2U+KFxyXG4gICAgYC9hcGkvaDUvbWVtYmVyL3ZlcmlmaWNhdGlvbi9yZXF1ZXN0cy8ke2VuY29kZVVSSUNvbXBvbmVudChyZXF1ZXN0SWQpfWAsXHJcbiAgKTtcclxuICBpZiAoYmFja2VuZFJlcXVlc3QpIHtcclxuICAgIHJldHVybiBtYXBWZXJpZmljYXRpb25SZXF1ZXN0RnJvbUJhY2tlbmQoYmFja2VuZFJlcXVlc3QpO1xyXG4gIH1cclxuICBjb25zdCByZXF1ZXN0cyA9IGF3YWl0IGxpc3RNZW1iZXJWZXJpZmljYXRpb25SZXF1ZXN0cygpO1xyXG4gIGNvbnN0IHJlcXVlc3QgPSByZXF1ZXN0cy5maW5kKChpdGVtKSA9PiBpdGVtLmlkID09PSByZXF1ZXN0SWQpO1xyXG4gIGlmICghcmVxdWVzdCkge1xyXG4gICAgdGhyb3cgY3JlYXRlU2VydmljZUVycm9yKFwidmVyaWZpY2F0aW9uUmVxdWVzdE5vdEZvdW5kXCIpO1xyXG4gIH1cclxuICByZXR1cm4gcmVxdWVzdDtcclxufVxyXG5cclxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIHBlcmZvcm1EYWlseUNoZWNrSW4oKTogUHJvbWlzZTxINUZyYWdtZW50T3ZlcnZpZXc+IHtcclxuICBjb25zdCBiYWNrZW5kT3ZlcnZpZXcgPSBhd2FpdCByZXF1ZXN0QmFja2VuZE1lbWJlckRvbWFpbjxCYWNrZW5kRnJhZ21lbnRPdmVydmlld1Jlc3BvbnNlPihcclxuICAgIFwiL2FwaS9oNS9mcmFnbWVudHMvY2hlY2staW5cIixcclxuICAgIHtcclxuICAgICAgbWV0aG9kOiBcIlBPU1RcIixcclxuICAgIH0sXHJcbiAgKTtcclxuICBpZiAoYmFja2VuZE92ZXJ2aWV3KSB7XHJcbiAgICByZXR1cm4gbWFwRnJhZ21lbnRPdmVydmlld0Zyb21CYWNrZW5kKGJhY2tlbmRPdmVydmlldyk7XHJcbiAgfVxyXG4gIGNvbnN0IHNlc3Npb24gPSBnZXRSZXF1aXJlZFNlc3Npb24oKTtcclxuICBjb25zdCBzdGF0ZSA9IHVwZGF0ZVN0YXRlRm9yQWNjb3VudChzZXNzaW9uLmFjY291bnRJZCwgKGRyYWZ0KSA9PiB7XHJcbiAgICBpZiAoZHJhZnQuY2hlY2tlZEluRGF0ZSA9PT0gdG9kYXlLZXkoKSkge1xyXG4gICAgICB0aHJvdyBjcmVhdGVTZXJ2aWNlRXJyb3IoXCJhbHJlYWR5Q2hlY2tlZEluXCIpO1xyXG4gICAgfVxyXG4gICAgZHJhZnQuY2hlY2tlZEluRGF0ZSA9IHRvZGF5S2V5KCk7XHJcbiAgICBjcmVhdGVGcmFnbWVudERyb3AoZHJhZnQsIFwiY2hlY2tpblwiKTtcclxuICAgIGFwcGVuZExvY2FsaXplZE1lc3NhZ2UoZHJhZnQsIFwic3lzdGVtXCIsIFwiY2hlY2tpblRpdGxlXCIsIFwiY2hlY2tpbkJvZHlcIik7XHJcbiAgICByZXR1cm4gZHJhZnQ7XHJcbiAgfSk7XHJcbiAgcmV0dXJuIGJ1aWxkRnJhZ21lbnRPdmVydmlldyhzdGF0ZSk7XHJcbn1cclxuXHJcbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBnZXRGcmFnbWVudHNPdmVydmlldygpOiBQcm9taXNlPEg1RnJhZ21lbnRPdmVydmlldz4ge1xyXG4gIGNvbnN0IGJhY2tlbmRPdmVydmlldyA9IGF3YWl0IHJlcXVlc3RCYWNrZW5kTWVtYmVyRG9tYWluPEJhY2tlbmRGcmFnbWVudE92ZXJ2aWV3UmVzcG9uc2U+KFwiL2FwaS9oNS9mcmFnbWVudHNcIik7XHJcbiAgaWYgKGJhY2tlbmRPdmVydmlldykge1xyXG4gICAgcmV0dXJuIG1hcEZyYWdtZW50T3ZlcnZpZXdGcm9tQmFja2VuZChiYWNrZW5kT3ZlcnZpZXcpO1xyXG4gIH1cclxuICBjb25zdCBzZXNzaW9uID0gZ2V0UmVxdWlyZWRTZXNzaW9uKCk7XHJcbiAgcmV0dXJuIGJ1aWxkRnJhZ21lbnRPdmVydmlldyhnZXRTdGF0ZUZvckFjY291bnQoc2Vzc2lvbi5hY2NvdW50SWQpKTtcclxufVxyXG5cclxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGNyZWF0ZUZyYWdtZW50RXhjaGFuZ2UocGF5bG9hZDogSDVTaGlwcGluZ0FkZHJlc3MpOiBQcm9taXNlPEg1RnJhZ21lbnRPdmVydmlldz4ge1xyXG4gIGNvbnN0IGJhY2tlbmRPdmVydmlldyA9IGF3YWl0IHJlcXVlc3RCYWNrZW5kTWVtYmVyRG9tYWluPEJhY2tlbmRGcmFnbWVudE92ZXJ2aWV3UmVzcG9uc2U+KFxyXG4gICAgXCIvYXBpL2g1L2ZyYWdtZW50cy9leGNoYW5nZXNcIixcclxuICAgIHtcclxuICAgICAgbWV0aG9kOiBcIlBPU1RcIixcclxuICAgICAgaGVhZGVyczogeyBcIkNvbnRlbnQtVHlwZVwiOiBcImFwcGxpY2F0aW9uL2pzb25cIiB9LFxyXG4gICAgICBib2R5OiBKU09OLnN0cmluZ2lmeShwYXlsb2FkKSxcclxuICAgIH0sXHJcbiAgKTtcclxuICBpZiAoYmFja2VuZE92ZXJ2aWV3KSB7XHJcbiAgICByZXR1cm4gbWFwRnJhZ21lbnRPdmVydmlld0Zyb21CYWNrZW5kKGJhY2tlbmRPdmVydmlldyk7XHJcbiAgfVxyXG4gIGNvbnN0IHNlc3Npb24gPSBnZXRSZXF1aXJlZFNlc3Npb24oKTtcclxuICBjb25zdCBzdGF0ZSA9IHVwZGF0ZVN0YXRlRm9yQWNjb3VudChzZXNzaW9uLmFjY291bnRJZCwgKGRyYWZ0KSA9PiB7XHJcbiAgICBjb25zdCBvdmVydmlldyA9IGJ1aWxkRnJhZ21lbnRPdmVydmlldyhkcmFmdCk7XHJcbiAgICBjb25zdCBsYWNrcyA9IG92ZXJ2aWV3LmludmVudG9yeS5maW5kKChpdGVtKSA9PiBpdGVtLm93bmVkIDwgaXRlbS5yZXF1aXJlZCk7XHJcbiAgICBpZiAobGFja3MpIHtcclxuICAgICAgdGhyb3cgY3JlYXRlU2VydmljZUVycm9yKFwiZnJhZ21lbnRzSW5jb21wbGV0ZVwiKTtcclxuICAgIH1cclxuICAgIGZvciAoY29uc3QgaXRlbSBvZiBvdmVydmlldy5pbnZlbnRvcnkpIHtcclxuICAgICAgZHJhZnQuZnJhZ21lbnRJbnZlbnRvcnlbaXRlbS5pZF0gPSBNYXRoLm1heCgwLCAoZHJhZnQuZnJhZ21lbnRJbnZlbnRvcnlbaXRlbS5pZF0gPz8gMCkgLSBpdGVtLnJlcXVpcmVkKTtcclxuICAgIH1cclxuICAgIGRyYWZ0LnNoaXBwaW5nT3JkZXJzLnVuc2hpZnQoe1xyXG4gICAgICBpZDogY3JlYXRlSWQoXCJzaGlwcGluZ1wiKSxcclxuICAgICAgcmV3YXJkTmFtZTogb3ZlcnZpZXcucmV3YXJkTmFtZSxcclxuICAgICAgc3RhdHVzOiBcInN1Ym1pdHRlZFwiLFxyXG4gICAgICBjcmVhdGVkQXQ6IG5vd0lzbygpLFxyXG4gICAgICBhZGRyZXNzOiBwYXlsb2FkLFxyXG4gICAgfSk7XHJcbiAgICBhcHBlbmRMb2NhbGl6ZWRNZXNzYWdlKGRyYWZ0LCBcImZyYWdtZW50XCIsIFwiZXhjaGFuZ2VUaXRsZVwiLCBcImV4Y2hhbmdlQm9keVwiKTtcclxuICAgIHJldHVybiBkcmFmdDtcclxuICB9KTtcclxuICByZXR1cm4gYnVpbGRGcmFnbWVudE92ZXJ2aWV3KHN0YXRlKTtcclxufVxyXG5cclxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGdldFJld2FyZFNoaXBwaW5nT3JkZXJzKCk6IFByb21pc2U8SDVSZXdhcmRTaGlwcGluZ09yZGVyW10+IHtcclxuICBjb25zdCBiYWNrZW5kT3JkZXJzID0gYXdhaXQgcmVxdWVzdEJhY2tlbmRNZW1iZXJEb21haW48QmFja2VuZFJld2FyZFNoaXBwaW5nT3JkZXJSZXNwb25zZVtdPihcclxuICAgIFwiL2FwaS9oNS9yZXdhcmRzL3NoaXBwaW5nXCIsXHJcbiAgKTtcclxuICBpZiAoYmFja2VuZE9yZGVycykge1xyXG4gICAgcmV0dXJuIGJhY2tlbmRPcmRlcnMubWFwKChpdGVtKSA9PiBtYXBTaGlwcGluZ09yZGVyRnJvbUJhY2tlbmQoaXRlbSkpO1xyXG4gIH1cclxuICBjb25zdCBzZXNzaW9uID0gZ2V0UmVxdWlyZWRTZXNzaW9uKCk7XHJcbiAgY29uc3Qgc3RhdGUgPSBnZXRTdGF0ZUZvckFjY291bnQoc2Vzc2lvbi5hY2NvdW50SWQpO1xyXG4gIHJldHVybiBbLi4uc3RhdGUuc2hpcHBpbmdPcmRlcnNdLnNvcnQoKGxlZnQsIHJpZ2h0KSA9PiByaWdodC5jcmVhdGVkQXQubG9jYWxlQ29tcGFyZShsZWZ0LmNyZWF0ZWRBdCkpO1xyXG59XHJcblxyXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gZ2V0V2hhdHNBcHBCaW5kaW5nKCk6IFByb21pc2U8SDVXaGF0c0FwcEJpbmRpbmc+IHtcclxuICBjb25zdCBiYWNrZW5kQmluZGluZyA9IGF3YWl0IHJlcXVlc3RCYWNrZW5kTWVtYmVyRG9tYWluPEJhY2tlbmRXaGF0c0FwcEJpbmRpbmdSZXNwb25zZT4oXHJcbiAgICBcIi9hcGkvaDUvd2hhdHNhcHAtYmluZGluZ1wiLFxyXG4gICk7XHJcbiAgaWYgKGJhY2tlbmRCaW5kaW5nKSB7XHJcbiAgICByZXR1cm4gbWFwV2hhdHNBcHBCaW5kaW5nRnJvbUJhY2tlbmQoYmFja2VuZEJpbmRpbmcpO1xyXG4gIH1cclxuICBjb25zdCBzZXNzaW9uID0gZ2V0UmVxdWlyZWRTZXNzaW9uKCk7XHJcbiAgcmV0dXJuIGdldFN0YXRlRm9yQWNjb3VudChzZXNzaW9uLmFjY291bnRJZCkud2hhdHNhcHBCaW5kaW5nO1xyXG59XHJcblxyXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gc3RhcnRXaGF0c0FwcEJpbmRpbmcoKTogUHJvbWlzZTxINVdoYXRzQXBwQmluZGluZz4ge1xyXG4gIGNvbnN0IGJhY2tlbmRCaW5kaW5nID0gYXdhaXQgcmVxdWVzdEJhY2tlbmRNZW1iZXJEb21haW48QmFja2VuZFdoYXRzQXBwQmluZGluZ1Jlc3BvbnNlPihcclxuICAgIFwiL2FwaS9oNS93aGF0c2FwcC1iaW5kaW5nL3N0YXJ0XCIsXHJcbiAgICB7XHJcbiAgICAgIG1ldGhvZDogXCJQT1NUXCIsXHJcbiAgICB9LFxyXG4gICk7XHJcbiAgaWYgKGJhY2tlbmRCaW5kaW5nKSB7XHJcbiAgICByZXR1cm4gbWFwV2hhdHNBcHBCaW5kaW5nRnJvbUJhY2tlbmQoYmFja2VuZEJpbmRpbmcpO1xyXG4gIH1cclxuICBjb25zdCBzZXNzaW9uID0gZ2V0UmVxdWlyZWRTZXNzaW9uKCk7XHJcbiAgY29uc3Qgc3RhdGUgPSB1cGRhdGVTdGF0ZUZvckFjY291bnQoc2Vzc2lvbi5hY2NvdW50SWQsIChkcmFmdCkgPT4ge1xyXG4gICAgZHJhZnQud2hhdHNhcHBCaW5kaW5nID0ge1xyXG4gICAgICBpc0JvdW5kOiBmYWxzZSxcclxuICAgICAgYmluZGluZ1N0YXR1czogXCJwZW5kaW5nXCIsXHJcbiAgICAgIHJlcXVlc3RJZDogZHJhZnQud2hhdHNhcHBCaW5kaW5nLnJlcXVlc3RJZCA/PyBgd2EtYmluZC0ke3Nlc3Npb24uYWNjb3VudElkfWAsXHJcbiAgICAgIHBob25lTnVtYmVyOiBudWxsLFxyXG4gICAgICByZXF1ZXN0ZWRBdDogbm93SXNvKCksXHJcbiAgICAgIHN0YXJ0Q291bnQ6IChkcmFmdC53aGF0c2FwcEJpbmRpbmcuc3RhcnRDb3VudCA/PyAwKSArIDEsXHJcbiAgICAgIGxhc3RVcGRhdGVkQXQ6IG5vd0lzbygpLFxyXG4gICAgfTtcclxuICAgIGFwcGVuZExvY2FsaXplZE1lc3NhZ2UoZHJhZnQsIFwic3lzdGVtXCIsIFwid2hhdHNhcHBPcGVuZWRUaXRsZVwiLCBcIndoYXRzYXBwT3BlbmVkQm9keVwiKTtcclxuICAgIHJldHVybiBkcmFmdDtcclxuICB9KTtcclxuICByZXR1cm4gc3RhdGUud2hhdHNhcHBCaW5kaW5nO1xyXG59XHJcblxyXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gZ2V0TWVtYmVyU3VwcG9ydENvbnRleHQoKTogUHJvbWlzZTx7XHJcbiAgYWNjb3VudElkOiBzdHJpbmc7XHJcbiAgcHVibGljVXNlcklkOiBzdHJpbmc7XHJcbn0+IHtcclxuICBjb25zdCBzZXNzaW9uID0gZ2V0UmVxdWlyZWRTZXNzaW9uKCk7XHJcbiAgcmV0dXJuIHtcclxuICAgIGFjY291bnRJZDogc2Vzc2lvbi5hY2NvdW50SWQsXHJcbiAgICBwdWJsaWNVc2VySWQ6IHNlc3Npb24ucHVibGljVXNlcklkLFxyXG4gIH07XHJcbn1cclxuXHJcbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBnZXRNYXNrZWRQaG9uZSgpOiBQcm9taXNlPHN0cmluZz4ge1xyXG4gIGNvbnN0IHNlc3Npb24gPSBnZXRSZXF1aXJlZFNlc3Npb24oKTtcclxuICByZXR1cm4gbWFza1Bob25lKHNlc3Npb24ucGhvbmUpO1xyXG59XHJcblxyXG4vLyDilIDilIDilIAgQXV0aCBBUEkgKG1vY2svcmVhbCBkdWFsLW1vZGUpIOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgFxyXG5cclxuLyoqIOeZu+W9lSAqL1xyXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gbG9naW5BcGkoXHJcbiAgcGhvbmU6IHN0cmluZyxcclxuICBwYXNzd29yZDogc3RyaW5nLFxyXG4gIHNpdGVLZXk/OiBzdHJpbmcsXHJcbik6IFByb21pc2U8SDVMb2dpblJlc3BvbnNlPiB7XHJcbiAgaWYgKGFwaU1vZGUgPT09ICdyZWFsJykge1xyXG4gICAgY29uc3QgcmVzID0gYXdhaXQgaDVBcGkucG9zdDxINUxvZ2luUmVzcG9uc2U+KCcvYXBpL2g1L2F1dGgvbG9naW4nLCB7XHJcbiAgICAgIHBob25lLFxyXG4gICAgICBwYXNzd29yZCxcclxuICAgICAgc2l0ZUtleTogc2l0ZUtleSB8fCAnbWFsbC1jbicsXHJcbiAgICB9KTtcclxuICAgIHNlc3Npb25NYW5hZ2VyLnNldFNlc3Npb24ocmVzLmRhdGEuYWNjZXNzX3Rva2VuLCByZXMuZGF0YS5yZWZyZXNoX3Rva2VuLCByZXMuZGF0YS5leHBpcmVzX2luKTtcclxuICAgIHJldHVybiByZXMuZGF0YTtcclxuICB9XHJcbiAgLy8gTW9jayBmYWxsYmFja1xyXG4gIGNvbnN0IHByb2ZpbGUgPSBhd2FpdCBsb2dpbk1lbWJlcih7IHNpdGVLZXk6IHNpdGVLZXkgfHwgJ21hbGwtY24nLCBwaG9uZSwgcGFzc3dvcmQgfSk7XHJcbiAgY29uc3QgdXNlcjogSDVNZW1iZXJTZXNzaW9uID0ge1xyXG4gICAgYWNjb3VudElkOiBwcm9maWxlLmFjY291bnRJZCxcclxuICAgIHBob25lOiBwcm9maWxlLnBob25lLFxyXG4gICAgcHVibGljVXNlcklkOiBwcm9maWxlLnB1YmxpY1VzZXJJZCxcclxuICAgIGRpc3BsYXlOYW1lOiBwcm9maWxlLmRpc3BsYXlOYW1lLFxyXG4gICAgaW52aXRlQ29kZTogcHJvZmlsZS5pbnZpdGVDb2RlLFxyXG4gICAgYXZhdGFyVXJsOiBwcm9maWxlLmF2YXRhclVybCA/PyBudWxsLFxyXG4gIH07XHJcbiAgY29uc3QgZmFrZVRva2VuID0gYG1vY2stYXQtJHtEYXRlLm5vdygpfWA7XHJcbiAgY29uc3QgZmFrZVJlZnJlc2ggPSBgbW9jay1ydC0ke0RhdGUubm93KCl9YDtcclxuICBzZXNzaW9uTWFuYWdlci5zZXRTZXNzaW9uKGZha2VUb2tlbiwgZmFrZVJlZnJlc2gsIDcyMDApO1xyXG4gIHNlc3Npb25NYW5hZ2VyLnNldFVzZXJJbmZvKHtcclxuICAgIGFjY291bnRJZDogdXNlci5hY2NvdW50SWQsXHJcbiAgICBwaG9uZTogdXNlci5waG9uZSxcclxuICAgIHB1YmxpY1VzZXJJZDogdXNlci5wdWJsaWNVc2VySWQsXHJcbiAgICBkaXNwbGF5TmFtZTogdXNlci5kaXNwbGF5TmFtZSxcclxuICAgIGludml0ZUNvZGU6IHVzZXIuaW52aXRlQ29kZSxcclxuICAgIGF2YXRhclVybDogdXNlci5hdmF0YXJVcmwsXHJcbiAgfSk7XHJcbiAgcmV0dXJuIHsgYWNjZXNzX3Rva2VuOiBmYWtlVG9rZW4sIHJlZnJlc2hfdG9rZW46IGZha2VSZWZyZXNoLCBleHBpcmVzX2luOiA3MjAwLCB1c2VyIH07XHJcbn1cclxuXHJcbi8qKiDms6jlhowgKi9cclxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIHJlZ2lzdGVyQXBpKHBheWxvYWQ6IHtcclxuICBzaXRlS2V5OiBzdHJpbmc7XHJcbiAgcGhvbmU6IHN0cmluZztcclxuICBwYXNzd29yZDogc3RyaW5nO1xyXG4gIGNvbmZpcm1QYXNzd29yZD86IHN0cmluZztcclxuICBkaXNwbGF5TmFtZT86IHN0cmluZztcclxufSk6IFByb21pc2U8SDVMb2dpblJlc3BvbnNlPiB7XHJcbiAgaWYgKGFwaU1vZGUgPT09ICdyZWFsJykge1xyXG4gICAgY29uc3QgcmVzID0gYXdhaXQgaDVBcGkucG9zdDxINUxvZ2luUmVzcG9uc2U+KCcvYXBpL2g1L2F1dGgvcmVnaXN0ZXInLCBwYXlsb2FkKTtcclxuICAgIHNlc3Npb25NYW5hZ2VyLnNldFNlc3Npb24ocmVzLmRhdGEuYWNjZXNzX3Rva2VuLCByZXMuZGF0YS5yZWZyZXNoX3Rva2VuLCByZXMuZGF0YS5leHBpcmVzX2luKTtcclxuICAgIHJldHVybiByZXMuZGF0YTtcclxuICB9XHJcbiAgLy8gTW9jayBmYWxsYmFja1xyXG4gIGNvbnN0IHByb2ZpbGUgPSBhd2FpdCByZWdpc3Rlck1lbWJlcihwYXlsb2FkKTtcclxuICBjb25zdCB1c2VyOiBINU1lbWJlclNlc3Npb24gPSB7XHJcbiAgICBhY2NvdW50SWQ6IHByb2ZpbGUuYWNjb3VudElkLFxyXG4gICAgcGhvbmU6IHByb2ZpbGUucGhvbmUsXHJcbiAgICBwdWJsaWNVc2VySWQ6IHByb2ZpbGUucHVibGljVXNlcklkLFxyXG4gICAgZGlzcGxheU5hbWU6IHByb2ZpbGUuZGlzcGxheU5hbWUsXHJcbiAgICBpbnZpdGVDb2RlOiBwcm9maWxlLmludml0ZUNvZGUsXHJcbiAgICBhdmF0YXJVcmw6IHByb2ZpbGUuYXZhdGFyVXJsID8/IG51bGwsXHJcbiAgfTtcclxuICBjb25zdCBmYWtlVG9rZW4gPSBgbW9jay1hdC0ke0RhdGUubm93KCl9YDtcclxuICBjb25zdCBmYWtlUmVmcmVzaCA9IGBtb2NrLXJ0LSR7RGF0ZS5ub3coKX1gO1xyXG4gIHNlc3Npb25NYW5hZ2VyLnNldFNlc3Npb24oZmFrZVRva2VuLCBmYWtlUmVmcmVzaCwgNzIwMCk7XHJcbiAgc2Vzc2lvbk1hbmFnZXIuc2V0VXNlckluZm8oe1xyXG4gICAgYWNjb3VudElkOiB1c2VyLmFjY291bnRJZCxcclxuICAgIHBob25lOiB1c2VyLnBob25lLFxyXG4gICAgcHVibGljVXNlcklkOiB1c2VyLnB1YmxpY1VzZXJJZCxcclxuICAgIGRpc3BsYXlOYW1lOiB1c2VyLmRpc3BsYXlOYW1lLFxyXG4gICAgaW52aXRlQ29kZTogdXNlci5pbnZpdGVDb2RlLFxyXG4gICAgYXZhdGFyVXJsOiB1c2VyLmF2YXRhclVybCxcclxuICB9KTtcclxuICByZXR1cm4geyBhY2Nlc3NfdG9rZW46IGZha2VUb2tlbiwgcmVmcmVzaF90b2tlbjogZmFrZVJlZnJlc2gsIGV4cGlyZXNfaW46IDcyMDAsIHVzZXIgfTtcclxufVxyXG5cclxuLyoqIOWIt+aWsCB0b2tlbiAqL1xyXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gcmVmcmVzaFRva2VuQXBpKCk6IFByb21pc2U8eyBhY2Nlc3NfdG9rZW46IHN0cmluZzsgcmVmcmVzaF90b2tlbjogc3RyaW5nOyBleHBpcmVzX2luOiBudW1iZXIgfT4ge1xyXG4gIGlmIChhcGlNb2RlID09PSAncmVhbCcpIHtcclxuICAgIGNvbnN0IHJlZnJlc2hUb2tlbiA9IHNlc3Npb25NYW5hZ2VyLmdldFJlZnJlc2hUb2tlbigpO1xyXG4gICAgY29uc3QgcmVzID0gYXdhaXQgaDVBcGkucG9zdDx7IGFjY2Vzc190b2tlbjogc3RyaW5nOyByZWZyZXNoX3Rva2VuOiBzdHJpbmc7IGV4cGlyZXNfaW46IG51bWJlciB9PignL2FwaS9oNS9hdXRoL3JlZnJlc2gnLCB7XHJcbiAgICAgIHJlZnJlc2hfdG9rZW46IHJlZnJlc2hUb2tlbixcclxuICAgIH0pO1xyXG4gICAgc2Vzc2lvbk1hbmFnZXIuc2V0U2Vzc2lvbihyZXMuZGF0YS5hY2Nlc3NfdG9rZW4sIHJlcy5kYXRhLnJlZnJlc2hfdG9rZW4sIHJlcy5kYXRhLmV4cGlyZXNfaW4pO1xyXG4gICAgcmV0dXJuIHJlcy5kYXRhO1xyXG4gIH1cclxuICAvLyBNb2NrIGZhbGxiYWNrOiB1c2UgZXhpc3RpbmcgcmVmcmVzaEJhY2tlbmRBdXRoU2Vzc2lvblxyXG4gIGNvbnN0IHN1Y2Nlc3MgPSBhd2FpdCByZWZyZXNoQmFja2VuZEF1dGhTZXNzaW9uKCk7XHJcbiAgaWYgKCFzdWNjZXNzKSB7XHJcbiAgICB0aHJvdyBuZXcgRXJyb3IoJ1Rva2VuIHJlZnJlc2ggZmFpbGVkJyk7XHJcbiAgfVxyXG4gIHJldHVybiB7XHJcbiAgICBhY2Nlc3NfdG9rZW46IHNlc3Npb25NYW5hZ2VyLmdldEFjY2Vzc1Rva2VuKCkgPz8gJycsXHJcbiAgICByZWZyZXNoX3Rva2VuOiBzZXNzaW9uTWFuYWdlci5nZXRSZWZyZXNoVG9rZW4oKSA/PyAnJyxcclxuICAgIGV4cGlyZXNfaW46IDcyMDAsXHJcbiAgfTtcclxufVxyXG5cclxuLyoqIOeZu+WHuiAqL1xyXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gbG9nb3V0QXBpKCk6IFByb21pc2U8dm9pZD4ge1xyXG4gIGlmIChhcGlNb2RlID09PSAncmVhbCcpIHtcclxuICAgIGF3YWl0IGg1QXBpLnBvc3QoJy9hcGkvaDUvYXV0aC9sb2dvdXQnKTtcclxuICAgIHNlc3Npb25NYW5hZ2VyLmNsZWFyU2Vzc2lvbigpO1xyXG4gICAgcmV0dXJuO1xyXG4gIH1cclxuICAvLyBNb2NrIGZhbGxiYWNrXHJcbiAgYXdhaXQgbG9nb3V0TWVtYmVyKCk7XHJcbiAgc2Vzc2lvbk1hbmFnZXIuY2xlYXJTZXNzaW9uKCk7XHJcbn1cclxuXHJcbi8qKiDojrflj5bnlKjmiLfkv6Hmga8gKi9cclxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGdldFVzZXJJbmZvQXBpKCk6IFByb21pc2U8SDVNZW1iZXJQcm9maWxlIHwgbnVsbD4ge1xyXG4gIGlmIChhcGlNb2RlID09PSAncmVhbCcpIHtcclxuICAgIGNvbnN0IHJlcyA9IGF3YWl0IGg1QXBpLmdldDx7IG1lbWJlcjogQmFja2VuZE1lbWJlckF1dGhSZXNwb25zZVsnbWVtYmVyJ107IHNpdGU6IEJhY2tlbmRNZW1iZXJBdXRoUmVzcG9uc2VbJ3NpdGUnXSB9PignL2FwaS9oNS9hdXRoL21lJyk7XHJcbiAgICBjb25zdCBwcm9maWxlID0gYnVpbGRQcm9maWxlRnJvbUF1dGhQYXlsb2FkKHtcclxuICAgICAgbWVtYmVyOiByZXMuZGF0YS5tZW1iZXIsXHJcbiAgICAgIHNpdGU6IHJlcy5kYXRhLnNpdGUsXHJcbiAgICB9KTtcclxuICAgIHN5bmNMZWdhY3lNZW1iZXJDYWNoZUZyb21Qcm9maWxlKHByb2ZpbGUpO1xyXG4gICAgcmV0dXJuIHByb2ZpbGU7XHJcbiAgfVxyXG4gIC8vIE1vY2sgZmFsbGJhY2tcclxuICByZXR1cm4gZ2V0Q3VycmVudE1lbWJlclByb2ZpbGUoKTtcclxufVxyXG5cclxuLyoqIOabtOaWsOS4quS6uuS/oeaBryAqL1xyXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gdXBkYXRlUHJvZmlsZUFwaShwYXlsb2FkOiB7XHJcbiAgcGhvbmU6IHN0cmluZztcclxuICBhdmF0YXJVcmw/OiBzdHJpbmcgfCBudWxsO1xyXG59KTogUHJvbWlzZTxINU1lbWJlclByb2ZpbGU+IHtcclxuICBpZiAoYXBpTW9kZSA9PT0gJ3JlYWwnKSB7XHJcbiAgICBjb25zdCByZXMgPSBhd2FpdCBoNUFwaS5wdXQ8SDVNZW1iZXJQcm9maWxlPignL2FwaS9oNS9wcm9maWxlJywgcGF5bG9hZCk7XHJcbiAgICByZXR1cm4gcmVzLmRhdGE7XHJcbiAgfVxyXG4gIC8vIE1vY2sgZmFsbGJhY2tcclxuICByZXR1cm4gdXBkYXRlTWVtYmVyUHJvZmlsZShwYXlsb2FkKTtcclxufVxyXG5cclxuLyoqIOS4iuS8oOWktOWDj++8iG11bHRpcGFydO+8iSAqL1xyXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gdXBkYXRlQXZhdGFyQXBpKGZpbGU6IEZpbGUpOiBQcm9taXNlPHsgYXZhdGFyVXJsOiBzdHJpbmcgfT4ge1xyXG4gIGlmIChhcGlNb2RlID09PSAncmVhbCcpIHtcclxuICAgIGNvbnN0IGZvcm1EYXRhID0gbmV3IEZvcm1EYXRhKCk7XHJcbiAgICBmb3JtRGF0YS5hcHBlbmQoJ2ZpbGUnLCBmaWxlKTtcclxuICAgIGNvbnN0IHJlcyA9IGF3YWl0IGg1QXBpLnBvc3Q8eyBhdmF0YXJVcmw6IHN0cmluZyB9PignL2FwaS9oNS9wcm9maWxlL2F2YXRhcicsIGZvcm1EYXRhLCB7XHJcbiAgICAgIGhlYWRlcnM6IHsgJ0NvbnRlbnQtVHlwZSc6ICdtdWx0aXBhcnQvZm9ybS1kYXRhJyB9LFxyXG4gICAgfSk7XHJcbiAgICByZXR1cm4gcmVzLmRhdGE7XHJcbiAgfVxyXG4gIC8vIE1vY2sgZmFsbGJhY2s6IHNpbXVsYXRlIGF2YXRhciB1cGxvYWQgYnkgc3RvcmluZyBhIGZha2UgVVJMXHJcbiAgY29uc3Qgc2Vzc2lvbiA9IGdldFJlcXVpcmVkU2Vzc2lvbigpO1xyXG4gIGNvbnN0IGZha2VVcmwgPSBVUkwuY3JlYXRlT2JqZWN0VVJMKGZpbGUpO1xyXG4gIGNvbnN0IGFjY291bnRzID0gcmVhZE1lbWJlckFjY291bnRzKCk7XHJcbiAgd3JpdGVNZW1iZXJBY2NvdW50cyhcclxuICAgIGFjY291bnRzLm1hcCgoaXRlbSkgPT5cclxuICAgICAgaXRlbS5hY2NvdW50SWQgPT09IHNlc3Npb24uYWNjb3VudElkID8geyAuLi5pdGVtLCBhdmF0YXJVcmw6IGZha2VVcmwgfSA6IGl0ZW0sXHJcbiAgICApLFxyXG4gICk7XHJcbiAgY29uc3QgbmV4dFNlc3Npb24gPSB7IC4uLnNlc3Npb24sIGF2YXRhclVybDogZmFrZVVybCB9O1xyXG4gIHdyaXRlU2Vzc2lvbihuZXh0U2Vzc2lvbik7XHJcbiAgcmV0dXJuIHsgYXZhdGFyVXJsOiBmYWtlVXJsIH07XHJcbn1cclxuXHJcbi8qKiDkv67mlLnlr4bnoIEgKi9cclxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGNoYW5nZVBhc3N3b3JkQXBpKHBheWxvYWQ6IHtcclxuICBjdXJyZW50UGFzc3dvcmQ6IHN0cmluZztcclxuICBuZXh0UGFzc3dvcmQ6IHN0cmluZztcclxuICBjb25maXJtUGFzc3dvcmQ6IHN0cmluZztcclxufSk6IFByb21pc2U8dm9pZD4ge1xyXG4gIGlmIChhcGlNb2RlID09PSAncmVhbCcpIHtcclxuICAgIGF3YWl0IGg1QXBpLnB1dCgnL2FwaS9oNS9wcm9maWxlL3Bhc3N3b3JkJywgcGF5bG9hZCk7XHJcbiAgICByZXR1cm47XHJcbiAgfVxyXG4gIC8vIE1vY2sgZmFsbGJhY2tcclxuICByZXR1cm4gdXBkYXRlTWVtYmVyUGFzc3dvcmQocGF5bG9hZCk7XHJcbn1cclxuXHJcbi8vIOKUgOKUgOKUgCBUYXNrIEFQSSAobW9jay9yZWFsIGR1YWwtbW9kZSkg4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSAXHJcblxyXG4vKiog6I635Y+W5Lu75Yqh5YyF5YiX6KGoICovXHJcbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBnZXRUYXNrUGFja2FnZXNBcGkocGFyYW1zPzoge1xyXG4gIHBhZ2U/OiBudW1iZXI7XHJcbiAgc2l6ZT86IG51bWJlcjtcclxuICBzdGF0dXM/OiBzdHJpbmc7XHJcbn0pOiBQcm9taXNlPFxyXG4gIEFycmF5PEg1VGFza1BhY2thZ2UgJiB7IHRvdGFsQ29tbWlzc2lvbjogbnVtYmVyOyBjdXJyZW50Q29tbWlzc2lvbjogbnVtYmVyOyBjb21wbGV0ZWRJdGVtczogbnVtYmVyOyB0b3RhbEl0ZW1zOiBudW1iZXI7IGNvdW50ZG93blNlY29uZHM6IG51bWJlciB9PlxyXG4+IHtcclxuICBpZiAoYXBpTW9kZSA9PT0gJ3JlYWwnKSB7XHJcbiAgICBjb25zdCByZXMgPSBhd2FpdCBoNUFwaS5nZXQoJy9hcGkvaDUvdGFza3MnLCB7IHBhcmFtcyB9KTtcclxuICAgIHJldHVybiByZXMuZGF0YS5pdGVtcyA/PyByZXMuZGF0YTtcclxuICB9XHJcbiAgLy8gTW9jayBmYWxsYmFjayAtIHVzZSBleGlzdGluZyBsaXN0VGFza1BhY2thZ2VzXHJcbiAgcmV0dXJuIGxpc3RUYXNrUGFja2FnZXMoKTtcclxufVxyXG5cclxuLyoqIOiOt+WPluS7u+WKoeWMheivpuaDhSAqL1xyXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gZ2V0VGFza1BhY2thZ2VEZXRhaWxBcGkoaWQ6IHN0cmluZyk6IFByb21pc2U8XHJcbiAgKEg1VGFza1BhY2thZ2UgJiB7IHRvdGFsQ29tbWlzc2lvbjogbnVtYmVyOyBjdXJyZW50Q29tbWlzc2lvbjogbnVtYmVyOyBjb21wbGV0ZWRJdGVtczogbnVtYmVyOyB0b3RhbEl0ZW1zOiBudW1iZXI7IGNvdW50ZG93blNlY29uZHM6IG51bWJlciB9KSB8IG51bGxcclxuPiB7XHJcbiAgaWYgKGFwaU1vZGUgPT09ICdyZWFsJykge1xyXG4gICAgY29uc3QgcmVzID0gYXdhaXQgaDVBcGkuZ2V0KGAvYXBpL2g1L3Rhc2tzLyR7ZW5jb2RlVVJJQ29tcG9uZW50KGlkKX1gKTtcclxuICAgIHJldHVybiByZXMuZGF0YTtcclxuICB9XHJcbiAgLy8gTW9jayBmYWxsYmFja1xyXG4gIHRyeSB7XHJcbiAgICByZXR1cm4gYXdhaXQgZ2V0VGFza1BhY2thZ2VEZXRhaWwoaWQpO1xyXG4gIH0gY2F0Y2gge1xyXG4gICAgcmV0dXJuIG51bGw7XHJcbiAgfVxyXG59XHJcblxyXG4vKiog5o+Q5Lqk5Lu75YqhICovXHJcbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBzdWJtaXRUYXNrQXBpKGlkOiBzdHJpbmcsIGRhdGE6IHVua25vd24pOiBQcm9taXNlPGJvb2xlYW4+IHtcclxuICBpZiAoYXBpTW9kZSA9PT0gJ3JlYWwnKSB7XHJcbiAgICBhd2FpdCBoNUFwaS5wb3N0KGAvYXBpL2g1L3Rhc2tzLyR7ZW5jb2RlVVJJQ29tcG9uZW50KGlkKX0vc3VibWl0YCwgZGF0YSk7XHJcbiAgICByZXR1cm4gdHJ1ZTtcclxuICB9XHJcbiAgcmV0dXJuIHRydWU7IC8vIE1vY2s6IGFsd2F5cyBzdWNjZWVkXHJcbn1cclxuXHJcbi8qKiDkuIrkvKDku7vliqHlh63or4EgKi9cclxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIHVwbG9hZFRhc2tQcm9vZkFwaShcclxuICBpZDogc3RyaW5nLFxyXG4gIGZpbGU6IEZpbGUsXHJcbiAgb25Qcm9ncmVzcz86IChwY3Q6IG51bWJlcikgPT4gdm9pZCxcclxuKTogUHJvbWlzZTxzdHJpbmc+IHtcclxuICBpZiAoYXBpTW9kZSA9PT0gJ3JlYWwnKSB7XHJcbiAgICBjb25zdCBmb3JtID0gbmV3IEZvcm1EYXRhKCk7XHJcbiAgICBmb3JtLmFwcGVuZCgnZmlsZScsIGZpbGUpO1xyXG4gICAgY29uc3QgcmVzID0gYXdhaXQgaDVBcGkucG9zdChgL2FwaS9oNS90YXNrcy8ke2VuY29kZVVSSUNvbXBvbmVudChpZCl9L3Byb29mYCwgZm9ybSwge1xyXG4gICAgICBoZWFkZXJzOiB7ICdDb250ZW50LVR5cGUnOiAnbXVsdGlwYXJ0L2Zvcm0tZGF0YScgfSxcclxuICAgICAgb25VcGxvYWRQcm9ncmVzczogKGUpID0+IHtcclxuICAgICAgICBpZiAoZS50b3RhbCkgb25Qcm9ncmVzcz8uKE1hdGgucm91bmQoKGUubG9hZGVkIC8gZS50b3RhbCkgKiAxMDApKTtcclxuICAgICAgfSxcclxuICAgIH0pO1xyXG4gICAgcmV0dXJuIHJlcy5kYXRhLnVybCA/PyByZXMuZGF0YTtcclxuICB9XHJcbiAgLy8gTW9jazogc2ltdWxhdGUgdXBsb2FkXHJcbiAgcmV0dXJuIFVSTC5jcmVhdGVPYmplY3RVUkwoZmlsZSk7XHJcbn1cclxuXHJcbi8vIOKUgOKUgOKUgCBXYWxsZXQgLyBUYXNrcyAvIOWFtuS7luaooeWdl+eahCBBUEkgRW5kcG9pbnQg6aKE6KeI77yIUGhhc2UgMy00IOWNoOS9je+8ieKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgFxyXG5cclxuLy8g4pSA4pSA4pSAIFdhbGxldCAvIE5vdGlmaWNhdGlvbnMgQVBJIOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgFxyXG5cclxuLyoqIOiOt+WPlumSseWMheS9meminSAqL1xyXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gZ2V0V2FsbGV0QmFsYW5jZUFwaSgpOiBQcm9taXNlPEg1V2FsbGV0U3VtbWFyeT4ge1xyXG4gIGlmIChhcGlNb2RlID09PSAncmVhbCcpIHtcclxuICAgIGNvbnN0IHJlcyA9IGF3YWl0IGg1QXBpLmdldDxINVdhbGxldFN1bW1hcnk+KEg1X0FQSV9FTkRQT0lOVFMud2FsbGV0LmJhbGFuY2UpO1xyXG4gICAgcmV0dXJuIHJlcy5kYXRhO1xyXG4gIH1cclxuICAvLyBNb2NrIGZhbGxiYWNrXHJcbiAgY29uc3Qgc2Vzc2lvbiA9IGdldFJlcXVpcmVkU2Vzc2lvbigpO1xyXG4gIGNvbnN0IHN0YXRlID0gZ2V0U3RhdGVGb3JBY2NvdW50KHNlc3Npb24uYWNjb3VudElkKTtcclxuICByZXR1cm4gZ2V0V2FsbGV0U3VtbWFyeUZyb21TdGF0ZShzdGF0ZSk7XHJcbn1cclxuXHJcbi8qKiDojrflj5bpkrHljIXkuqTmmJPorrDlvZXvvIjliIbpobXvvIkgKi9cclxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGdldFdhbGxldFRyYW5zYWN0aW9uc0FwaShwYXJhbXM6IHtcclxuICBwYWdlOiBudW1iZXI7XHJcbiAgc2l6ZT86IG51bWJlcjtcclxuICB0eXBlPzogc3RyaW5nO1xyXG59KTogUHJvbWlzZTx7IGl0ZW1zOiBINVdhbGxldFRyYW5zYWN0aW9uW107IHRvdGFsOiBudW1iZXIgfT4ge1xyXG4gIGlmIChhcGlNb2RlID09PSAncmVhbCcpIHtcclxuICAgIGNvbnN0IHJlcyA9IGF3YWl0IGg1QXBpLmdldChINV9BUElfRU5EUE9JTlRTLndhbGxldC50cmFuc2FjdGlvbnMsIHsgcGFyYW1zIH0pO1xyXG4gICAgcmV0dXJuIHJlcy5kYXRhO1xyXG4gIH1cclxuICAvLyBNb2NrIGZhbGxiYWNrXHJcbiAgY29uc3Qgc2Vzc2lvbiA9IGdldFJlcXVpcmVkU2Vzc2lvbigpO1xyXG4gIGNvbnN0IHN0YXRlID0gZ2V0U3RhdGVGb3JBY2NvdW50KHNlc3Npb24uYWNjb3VudElkKTtcclxuICBjb25zdCBhbGxUcmFuc2FjdGlvbnMgPSBbLi4uc3RhdGUudHJhbnNhY3Rpb25zXS5zb3J0KChsZWZ0LCByaWdodCkgPT5cclxuICAgIHJpZ2h0LmNyZWF0ZWRBdC5sb2NhbGVDb21wYXJlKGxlZnQuY3JlYXRlZEF0KSxcclxuICApO1xyXG4gIGNvbnN0IGZpbHRlcmVkID0gcGFyYW1zLnR5cGVcclxuICAgID8gYWxsVHJhbnNhY3Rpb25zLmZpbHRlcigoaXRlbSkgPT4gaXRlbS50cmFuc2FjdGlvblR5cGUgPT09IHBhcmFtcy50eXBlKVxyXG4gICAgOiBhbGxUcmFuc2FjdGlvbnM7XHJcbiAgY29uc3Qgc2l6ZSA9IHBhcmFtcy5zaXplID8/IDIwO1xyXG4gIGNvbnN0IHN0YXJ0ID0gKHBhcmFtcy5wYWdlIC0gMSkgKiBzaXplO1xyXG4gIHJldHVybiB7XHJcbiAgICBpdGVtczogZmlsdGVyZWQuc2xpY2Uoc3RhcnQsIHN0YXJ0ICsgc2l6ZSksXHJcbiAgICB0b3RhbDogZmlsdGVyZWQubGVuZ3RoLFxyXG4gIH07XHJcbn1cclxuXHJcbi8qKiDlj5HotbflhYXlgLwgKi9cclxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIHJlY2hhcmdlQXBpKFxyXG4gIGFtb3VudDogbnVtYmVyLFxyXG4gIGNoYW5uZWw6IHN0cmluZyxcclxuKTogUHJvbWlzZTx7IGlkOiBzdHJpbmc7IHN0YXR1czogc3RyaW5nIH0+IHtcclxuICBpZiAoYXBpTW9kZSA9PT0gJ3JlYWwnKSB7XHJcbiAgICBjb25zdCByZXMgPSBhd2FpdCBoNUFwaS5wb3N0KEg1X0FQSV9FTkRQT0lOVFMud2FsbGV0LnJlY2hhcmdlLCB7IGFtb3VudCwgY2hhbm5lbCB9KTtcclxuICAgIHJldHVybiByZXMuZGF0YTtcclxuICB9XHJcbiAgLy8gTW9jayBmYWxsYmFja1xyXG4gIGF3YWl0IGNyZWF0ZVJlY2hhcmdlT3JkZXIoYW1vdW50KTtcclxuICByZXR1cm4geyBpZDogYG1vY2tfcmVjaGFyZ2VfJHtEYXRlLm5vdygpfWAsIHN0YXR1czogJ2NvbXBsZXRlZCcgfTtcclxufVxyXG5cclxuLyoqIOafpeivouWFheWAvOeKtuaAgSAqL1xyXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gZ2V0UmVjaGFyZ2VTdGF0dXNBcGkoaWQ6IHN0cmluZyk6IFByb21pc2U8c3RyaW5nPiB7XHJcbiAgaWYgKGFwaU1vZGUgPT09ICdyZWFsJykge1xyXG4gICAgY29uc3QgcmVzID0gYXdhaXQgaDVBcGkuZ2V0KEg1X0FQSV9FTkRQT0lOVFMud2FsbGV0LnJlY2hhcmdlU3RhdHVzKGlkKSk7XHJcbiAgICByZXR1cm4gcmVzLmRhdGEuc3RhdHVzO1xyXG4gIH1cclxuICByZXR1cm4gJ2NvbXBsZXRlZCc7XHJcbn1cclxuXHJcbi8qKiDojrflj5bmnKror7vpgJrnn6XmlbDph48gKi9cclxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGdldE5vdGlmaWNhdGlvbnNDb3VudEFwaSgpOiBQcm9taXNlPHsgdW5yZWFkQ291bnQ6IG51bWJlciB9PiB7XHJcbiAgaWYgKGFwaU1vZGUgPT09ICdyZWFsJykge1xyXG4gICAgY29uc3QgcmVzID0gYXdhaXQgaDVBcGkuZ2V0PHsgdW5yZWFkQ291bnQ6IG51bWJlciB9PihINV9BUElfRU5EUE9JTlRTLm5vdGlmaWNhdGlvbnNVbnJlYWRDb3VudCk7XHJcbiAgICByZXR1cm4gcmVzLmRhdGE7XHJcbiAgfVxyXG4gIC8vIE1vY2sgZmFsbGJhY2tcclxuICBjb25zdCBzZXNzaW9uID0gZ2V0UmVxdWlyZWRTZXNzaW9uKCk7XHJcbiAgY29uc3Qgc3RhdGUgPSBnZXRTdGF0ZUZvckFjY291bnQoc2Vzc2lvbi5hY2NvdW50SWQpO1xyXG4gIHJldHVybiB7IHVucmVhZENvdW50OiBnZXRVbnJlYWRNZXNzYWdlQ291bnQoc3RhdGUubWVzc2FnZXMpIH07XHJcbn1cclxuXHJcbi8vIOKUgOKUgOKUgCBXaXRoZHJhdyBBUEkg4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSAXHJcblxyXG4vKiog6I635Y+W5o+Q546w6K6w5b2V77yI5YiG6aG177yJICovXHJcbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBnZXRXaXRoZHJhd2Fsc0FwaShwYXJhbXM6IHtcclxuICBwYWdlPzogbnVtYmVyO1xyXG4gIHNpemU/OiBudW1iZXI7XHJcbn0pOiBQcm9taXNlPHsgaXRlbXM6IEg1V2l0aGRyYXdSZXF1ZXN0W107IHRvdGFsOiBudW1iZXIgfT4ge1xyXG4gIGlmIChhcGlNb2RlID09PSAncmVhbCcpIHtcclxuICAgIGNvbnN0IHJlcyA9IGF3YWl0IGg1QXBpLmdldChINV9BUElfRU5EUE9JTlRTLndpdGhkcmF3YWxzLmxpc3QsIHsgcGFyYW1zIH0pO1xyXG4gICAgcmV0dXJuIHJlcy5kYXRhO1xyXG4gIH1cclxuICBjb25zdCBzZXNzaW9uID0gZ2V0UmVxdWlyZWRTZXNzaW9uKCk7XHJcbiAgY29uc3Qgc3RhdGUgPSBnZXRTdGF0ZUZvckFjY291bnQoc2Vzc2lvbi5hY2NvdW50SWQpO1xyXG4gIGNvbnN0IHJlcXVlc3RzID0gWy4uLnN0YXRlLndpdGhkcmF3UmVxdWVzdHNdLnNvcnQoKGxlZnQsIHJpZ2h0KSA9PlxyXG4gICAgcmlnaHQuY3JlYXRlZEF0LmxvY2FsZUNvbXBhcmUobGVmdC5jcmVhdGVkQXQpLFxyXG4gICk7XHJcbiAgY29uc3QgcGFnZSA9IHBhcmFtcy5wYWdlID8/IDE7XHJcbiAgY29uc3Qgc2l6ZSA9IHBhcmFtcy5zaXplID8/IDIwO1xyXG4gIHJldHVybiB7IGl0ZW1zOiByZXF1ZXN0cy5zbGljZSgocGFnZSAtIDEpICogc2l6ZSwgcGFnZSAqIHNpemUpLCB0b3RhbDogcmVxdWVzdHMubGVuZ3RoIH07XHJcbn1cclxuXHJcbi8qKiDmj5DkuqTmj5DnjrDnlLPor7cgKi9cclxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIHN1Ym1pdFdpdGhkcmF3QXBpKFxyXG4gIGFtb3VudDogbnVtYmVyLFxyXG4gIGFjY291bnRJbmZvPzogc3RyaW5nLFxyXG4pOiBQcm9taXNlPHsgaWQ6IHN0cmluZzsgc3RhdHVzOiBzdHJpbmcgfT4ge1xyXG4gIGlmIChhcGlNb2RlID09PSAncmVhbCcpIHtcclxuICAgIGNvbnN0IHJlcyA9IGF3YWl0IGg1QXBpLnBvc3QoSDVfQVBJX0VORFBPSU5UUy53aXRoZHJhd2Fscy5saXN0LCB7IGFtb3VudCwgYWNjb3VudF9pbmZvOiBhY2NvdW50SW5mbyB9KTtcclxuICAgIHJldHVybiByZXMuZGF0YTtcclxuICB9XHJcbiAgLy8gTW9jayBmYWxsYmFja1xyXG4gIGF3YWl0IGNyZWF0ZVdpdGhkcmF3UmVxdWVzdChhbW91bnQpO1xyXG4gIHJldHVybiB7IGlkOiBgbW9jay0ke0RhdGUubm93KCl9YCwgc3RhdHVzOiAnc3VibWl0dGVkJyB9O1xyXG59XHJcblxyXG4vKiog6I635Y+W5o+Q546w6K+m5oOFICovXHJcbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBnZXRXaXRoZHJhd0RldGFpbEFwaShpZDogc3RyaW5nKTogUHJvbWlzZTxINVdpdGhkcmF3UmVxdWVzdCB8IG51bGw+IHtcclxuICBpZiAoYXBpTW9kZSA9PT0gJ3JlYWwnKSB7XHJcbiAgICBjb25zdCByZXMgPSBhd2FpdCBoNUFwaS5nZXQoSDVfQVBJX0VORFBPSU5UUy53aXRoZHJhd2Fscy5kZXRhaWwoaWQpKTtcclxuICAgIHJldHVybiByZXMuZGF0YTtcclxuICB9XHJcbiAgY29uc3Qgc2Vzc2lvbiA9IGdldFJlcXVpcmVkU2Vzc2lvbigpO1xyXG4gIGNvbnN0IHN0YXRlID0gZ2V0U3RhdGVGb3JBY2NvdW50KHNlc3Npb24uYWNjb3VudElkKTtcclxuICByZXR1cm4gc3RhdGUud2l0aGRyYXdSZXF1ZXN0cy5maW5kKChyKSA9PiByLmlkID09PSBpZCkgPz8gbnVsbDtcclxufVxyXG5cclxuLy8g4pSA4pSA4pSAIE1vY2sgaGVscGVyIGZvciB2ZXJpZmljYXRpb24gJiBXaGF0c0FwcCAobG9jYWxTdG9yYWdlKSDilIDilIDilIDilIDilIDilIBcclxuXHJcbmZ1bmN0aW9uIGdldE1vY2tWZXJpZmljYXRpb25TdGF0dXMoKToge1xyXG4gIHN0YXR1czogc3RyaW5nO1xyXG4gIG5hbWU/OiBzdHJpbmc7XHJcbiAgaWROdW1iZXI/OiBzdHJpbmc7XHJcbiAgcGhvdG9zPzogc3RyaW5nW107XHJcbiAgc3VibWl0dGVkQXQ/OiBzdHJpbmc7XHJcbiAgcmV2aWV3Tm90ZT86IHN0cmluZztcclxufSB7XHJcbiAgY29uc3QgcmF3ID0gaXNCcm93c2VyKCkgPyB3aW5kb3cubG9jYWxTdG9yYWdlLmdldEl0ZW0oJ21vY2tfdmVyaWZpY2F0aW9uX3N0YXR1cycpIDogbnVsbDtcclxuICBpZiAocmF3KSB7XHJcbiAgICB0cnkge1xyXG4gICAgICByZXR1cm4gSlNPTi5wYXJzZShyYXcpO1xyXG4gICAgfSBjYXRjaCB7XHJcbiAgICAgIC8qIGlnbm9yZSAqL1xyXG4gICAgfVxyXG4gIH1cclxuICByZXR1cm4geyBzdGF0dXM6ICd1bnZlcmlmaWVkJyB9O1xyXG59XHJcblxyXG5mdW5jdGlvbiBnZXRNb2NrV2hhdHNBcHBCaW5kaW5nU3RhdHVzKCk6IHtcclxuICBzdGF0dXM6IHN0cmluZztcclxuICBwaG9uZT86IHN0cmluZztcclxuICByZXF1ZXN0ZWRBdD86IHN0cmluZztcclxuICBpZD86IHN0cmluZztcclxufSB7XHJcbiAgY29uc3QgcmF3ID0gaXNCcm93c2VyKCkgPyB3aW5kb3cubG9jYWxTdG9yYWdlLmdldEl0ZW0oJ21vY2tfd2hhdHNhcHBfYmluZGluZycpIDogbnVsbDtcclxuICBpZiAocmF3KSB7XHJcbiAgICB0cnkge1xyXG4gICAgICByZXR1cm4gSlNPTi5wYXJzZShyYXcpO1xyXG4gICAgfSBjYXRjaCB7XHJcbiAgICAgIC8qIGlnbm9yZSAqL1xyXG4gICAgfVxyXG4gIH1cclxuICByZXR1cm4geyBzdGF0dXM6ICdub3RfYm91bmQnIH07XHJcbn1cclxuXHJcbi8vIOKUgOKUgOKUgCBWZXJpZmljYXRpb24gQVBJIChtb2NrL3JlYWwgZHVhbC1tb2RlKSDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIBcclxuXHJcbi8qKiDojrflj5borqTor4HnirbmgIEgKi9cclxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGdldFZlcmlmaWNhdGlvblN0YXR1c0FwaSgpOiBQcm9taXNlPHtcclxuICBzdGF0dXM6IHN0cmluZztcclxuICBuYW1lPzogc3RyaW5nO1xyXG4gIGlkTnVtYmVyPzogc3RyaW5nO1xyXG4gIHBob3Rvcz86IHN0cmluZ1tdO1xyXG4gIHN1Ym1pdHRlZEF0Pzogc3RyaW5nO1xyXG4gIHJldmlld05vdGU/OiBzdHJpbmc7XHJcbn0+IHtcclxuICBpZiAoYXBpTW9kZSA9PT0gJ3JlYWwnKSB7XHJcbiAgICBjb25zdCByZXMgPSBhd2FpdCBoNUFwaS5nZXQoJy9hcGkvaDUvdmVyaWZpY2F0aW9ucy9zdGF0dXMnKTtcclxuICAgIHJldHVybiByZXMuZGF0YTtcclxuICB9XHJcbiAgcmV0dXJuIGdldE1vY2tWZXJpZmljYXRpb25TdGF0dXMoKTtcclxufVxyXG5cclxuLyoqIOaPkOS6pOiupOivgSAqL1xyXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gc3VibWl0VmVyaWZpY2F0aW9uQXBpKGRhdGE6IHtcclxuICBuYW1lOiBzdHJpbmc7XHJcbiAgaWROdW1iZXI/OiBzdHJpbmc7XHJcbiAgcGhvdG9zPzogc3RyaW5nW107XHJcbn0pOiBQcm9taXNlPHsgaWQ6IHN0cmluZzsgc3RhdHVzOiBzdHJpbmcgfT4ge1xyXG4gIGlmIChhcGlNb2RlID09PSAncmVhbCcpIHtcclxuICAgIGNvbnN0IHJlcyA9IGF3YWl0IGg1QXBpLnBvc3QoJy9hcGkvaDUvdmVyaWZpY2F0aW9ucycsIGRhdGEpO1xyXG4gICAgcmV0dXJuIHJlcy5kYXRhO1xyXG4gIH1cclxuICAvLyBNb2NrOiBwZXJzaXN0IHRvIGxvY2FsU3RvcmFnZVxyXG4gIGNvbnN0IG1vY2tJZCA9IGBtb2NrLSR7RGF0ZS5ub3coKX1gO1xyXG4gIGlmIChpc0Jyb3dzZXIoKSkge1xyXG4gICAgd2luZG93LmxvY2FsU3RvcmFnZS5zZXRJdGVtKFxyXG4gICAgICAnbW9ja192ZXJpZmljYXRpb25fc3RhdHVzJyxcclxuICAgICAgSlNPTi5zdHJpbmdpZnkoeyBzdGF0dXM6ICdwZW5kaW5nJywgbmFtZTogZGF0YS5uYW1lLCBpZE51bWJlcjogZGF0YS5pZE51bWJlciwgcGhvdG9zOiBkYXRhLnBob3Rvcywgc3VibWl0dGVkQXQ6IG5vd0lzbygpIH0pLFxyXG4gICAgKTtcclxuICB9XHJcbiAgcmV0dXJuIHsgaWQ6IG1vY2tJZCwgc3RhdHVzOiAncGVuZGluZycgfTtcclxufVxyXG5cclxuLyoqIOS4iuS8oOiupOivgeeFp+eJhyAqL1xyXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gdXBsb2FkVmVyaWZpY2F0aW9uUGhvdG9zQXBpKGlkOiBzdHJpbmcsIGZpbGVzOiBGaWxlW10pOiBQcm9taXNlPGJvb2xlYW4+IHtcclxuICBpZiAoYXBpTW9kZSA9PT0gJ3JlYWwnKSB7XHJcbiAgICBjb25zdCBmb3JtID0gbmV3IEZvcm1EYXRhKCk7XHJcbiAgICBmaWxlcy5mb3JFYWNoKChmKSA9PiBmb3JtLmFwcGVuZCgncGhvdG9zJywgZikpO1xyXG4gICAgYXdhaXQgaDVBcGkucG9zdChgL2FwaS9oNS92ZXJpZmljYXRpb25zLyR7aWR9L3Bob3Rvc2AsIGZvcm0sIHtcclxuICAgICAgaGVhZGVyczogeyAnQ29udGVudC1UeXBlJzogJ211bHRpcGFydC9mb3JtLWRhdGEnIH0sXHJcbiAgICB9KTtcclxuICAgIHJldHVybiB0cnVlO1xyXG4gIH1cclxuICByZXR1cm4gdHJ1ZTtcclxufVxyXG5cclxuLy8g4pSA4pSA4pSAIFdoYXRzQXBwIEJpbmRpbmcgQVBJIChtb2NrL3JlYWwgZHVhbC1tb2RlKSDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIBcclxuXHJcbi8qKiDojrflj5YgV2hhdHNBcHAg57uR5a6a54q25oCBICovXHJcbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBnZXRXaGF0c0FwcEJpbmRpbmdTdGF0dXNBcGkoKTogUHJvbWlzZTx7XHJcbiAgc3RhdHVzOiBzdHJpbmc7XHJcbiAgcGhvbmU/OiBzdHJpbmc7XHJcbiAgcmVxdWVzdGVkQXQ/OiBzdHJpbmc7XHJcbiAgaWQ/OiBzdHJpbmc7XHJcbn0+IHtcclxuICBpZiAoYXBpTW9kZSA9PT0gJ3JlYWwnKSB7XHJcbiAgICBjb25zdCByZXMgPSBhd2FpdCBoNUFwaS5nZXQoJy9hcGkvaDUvd2hhdHNhcHAtYmluZGluZ3Mvc3RhdHVzJyk7XHJcbiAgICByZXR1cm4gcmVzLmRhdGE7XHJcbiAgfVxyXG4gIHJldHVybiBnZXRNb2NrV2hhdHNBcHBCaW5kaW5nU3RhdHVzKCk7XHJcbn1cclxuXHJcbi8qKiDlj5HotbcgV2hhdHNBcHAg57uR5a6aICovXHJcbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBzdGFydFdoYXRzQXBwQmluZGluZ0FwaShwaG9uZTogc3RyaW5nKTogUHJvbWlzZTx7IGlkOiBzdHJpbmc7IHN0YXR1czogc3RyaW5nIH0+IHtcclxuICBpZiAoYXBpTW9kZSA9PT0gJ3JlYWwnKSB7XHJcbiAgICBjb25zdCByZXMgPSBhd2FpdCBoNUFwaS5wb3N0KCcvYXBpL2g1L3doYXRzYXBwLWJpbmRpbmdzJywgeyBwaG9uZSB9KTtcclxuICAgIHJldHVybiByZXMuZGF0YTtcclxuICB9XHJcbiAgLy8gTW9jazogcGVyc2lzdCB0byBsb2NhbFN0b3JhZ2VcclxuICBjb25zdCBtb2NrSWQgPSBgbW9jay0ke0RhdGUubm93KCl9YDtcclxuICBpZiAoaXNCcm93c2VyKCkpIHtcclxuICAgIHdpbmRvdy5sb2NhbFN0b3JhZ2Uuc2V0SXRlbShcclxuICAgICAgJ21vY2tfd2hhdHNhcHBfYmluZGluZycsXHJcbiAgICAgIEpTT04uc3RyaW5naWZ5KHsgc3RhdHVzOiAncGVuZGluZycsIHBob25lLCByZXF1ZXN0ZWRBdDogbm93SXNvKCksIGlkOiBtb2NrSWQgfSksXHJcbiAgICApO1xyXG4gIH1cclxuICByZXR1cm4geyBpZDogbW9ja0lkLCBzdGF0dXM6ICdwZW5kaW5nJyB9O1xyXG59XHJcblxyXG4vLyDilIDilIDilIAgTW9jayBoZWxwZXIgZm9yIG5vdGlmaWNhdGlvbi90aWNrZXQgQVBJIGZhbGxiYWNrIOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgFxyXG5cclxuZnVuY3Rpb24gZ2V0TWVzc2FnZXMoKTogSDVNZXNzYWdlSXRlbVtdIHtcclxuICBjb25zdCBzZXNzaW9uID0gZ2V0UmVxdWlyZWRTZXNzaW9uKCk7XHJcbiAgY29uc3Qgc3RhdGUgPSBnZXRTdGF0ZUZvckFjY291bnQoc2Vzc2lvbi5hY2NvdW50SWQpO1xyXG4gIHJldHVybiBbLi4uc3RhdGUubWVzc2FnZXNdLnNvcnQoKGxlZnQsIHJpZ2h0KSA9PiByaWdodC5jcmVhdGVkQXQubG9jYWxlQ29tcGFyZShsZWZ0LmNyZWF0ZWRBdCkpO1xyXG59XHJcblxyXG5jb25zdCBtb2NrVGlja2V0c1N0b3JlOiBBcnJheTx7XHJcbiAgaWQ6IHN0cmluZztcclxuICBjYXRlZ29yeTogc3RyaW5nO1xyXG4gIHByaW9yaXR5OiBzdHJpbmc7XHJcbiAgc3ViamVjdDogc3RyaW5nO1xyXG4gIGRlc2NyaXB0aW9uOiBzdHJpbmc7XHJcbiAgc3RhdHVzOiBzdHJpbmc7XHJcbiAgY3JlYXRlZF9hdDogc3RyaW5nO1xyXG4gIHVwZGF0ZWRfYXQ6IHN0cmluZztcclxuICBsYXN0X3JlcGx5X2F0OiBzdHJpbmcgfCBudWxsO1xyXG4gIG1lc3NhZ2VzOiBBcnJheTx7IGlkOiBzdHJpbmc7IHNlbmRlcl90eXBlOiBzdHJpbmc7IHNlbmRlcl9uYW1lOiBzdHJpbmc7IGNvbnRlbnQ6IHN0cmluZzsgY3JlYXRlZF9hdDogc3RyaW5nOyBpbnRlcm5hbF9vbmx5OiBib29sZWFuIH0+O1xyXG59PiA9IFtdO1xyXG5cclxuZnVuY3Rpb24gZ2V0U3VwcG9ydFRpY2tldHMoKTogdW5rbm93bltdIHtcclxuICByZXR1cm4gWy4uLm1vY2tUaWNrZXRzU3RvcmVdO1xyXG59XHJcblxyXG5mdW5jdGlvbiBnZXRTdXBwb3J0VGlja2V0QnlJZChpZDogc3RyaW5nKTogdW5rbm93biB8IG51bGwge1xyXG4gIHJldHVybiBtb2NrVGlja2V0c1N0b3JlLmZpbmQoKHQpID0+IHQuaWQgPT09IGlkKSA/PyBudWxsO1xyXG59XHJcblxyXG5mdW5jdGlvbiBhZGRUaWNrZXRSZXBseSh0aWNrZXRJZDogc3RyaW5nLCBtZXNzYWdlOiBzdHJpbmcpOiBib29sZWFuIHtcclxuICBjb25zdCB0aWNrZXQgPSBtb2NrVGlja2V0c1N0b3JlLmZpbmQoKHQpID0+IHQuaWQgPT09IHRpY2tldElkKTtcclxuICBpZiAoIXRpY2tldCkgcmV0dXJuIGZhbHNlO1xyXG4gIHRpY2tldC5tZXNzYWdlcy5wdXNoKHtcclxuICAgIGlkOiAnbXNnLScgKyBEYXRlLm5vdygpLFxyXG4gICAgc2VuZGVyX3R5cGU6ICd1c2VyJyxcclxuICAgIHNlbmRlcl9uYW1lOiAndXNlcicsXHJcbiAgICBjb250ZW50OiBtZXNzYWdlLFxyXG4gICAgY3JlYXRlZF9hdDogbmV3IERhdGUoKS50b0lTT1N0cmluZygpLFxyXG4gICAgaW50ZXJuYWxfb25seTogZmFsc2UsXHJcbiAgfSk7XHJcbiAgdGlja2V0Lmxhc3RfcmVwbHlfYXQgPSBuZXcgRGF0ZSgpLnRvSVNPU3RyaW5nKCk7XHJcbiAgdGlja2V0LnVwZGF0ZWRfYXQgPSBuZXcgRGF0ZSgpLnRvSVNPU3RyaW5nKCk7XHJcbiAgcmV0dXJuIHRydWU7XHJcbn1cclxuXHJcbi8vIOKUgOKUgOKUgCBINTItMDEyOiBOb3RpZmljYXRpb24gKyBUaWNrZXQgQVBJIGZ1bmN0aW9ucyDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIBcclxuXHJcbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBnZXROb3RpZmljYXRpb25zQXBpKHBhcmFtczogeyBwYWdlPzogbnVtYmVyOyBzaXplPzogbnVtYmVyIH0pOiBQcm9taXNlPHsgaXRlbXM6IEg1TWVzc2FnZUl0ZW1bXTsgdG90YWw6IG51bWJlciB9PiB7XHJcbiAgaWYgKGFwaU1vZGUgPT09ICdyZWFsJykge1xyXG4gICAgY29uc3QgcmVzID0gYXdhaXQgaDVBcGkuZ2V0KCcvYXBpL2g1L25vdGlmaWNhdGlvbnMnLCB7IHBhcmFtcyB9KTtcclxuICAgIHJldHVybiByZXMuZGF0YTtcclxuICB9XHJcbiAgY29uc3QgbXNncyA9IGdldE1lc3NhZ2VzKCk7XHJcbiAgY29uc3QgcGFnZSA9IHBhcmFtcy5wYWdlID8/IDE7XHJcbiAgY29uc3Qgc2l6ZSA9IHBhcmFtcy5zaXplID8/IDIwO1xyXG4gIHJldHVybiB7IGl0ZW1zOiBtc2dzLnNsaWNlKChwYWdlIC0gMSkgKiBzaXplLCBwYWdlICogc2l6ZSksIHRvdGFsOiBtc2dzLmxlbmd0aCB9O1xyXG59XHJcblxyXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gbWFya05vdGlmaWNhdGlvblJlYWRBcGkoaWQ6IHN0cmluZyk6IFByb21pc2U8Ym9vbGVhbj4ge1xyXG4gIGlmIChhcGlNb2RlID09PSAncmVhbCcpIHtcclxuICAgIGF3YWl0IGg1QXBpLnB1dCgnL2FwaS9oNS9ub3RpZmljYXRpb25zLycgKyBlbmNvZGVVUklDb21wb25lbnQoaWQpICsgJy9yZWFkJyk7XHJcbiAgICByZXR1cm4gdHJ1ZTtcclxuICB9XHJcbiAgcmV0dXJuIG1hcmtNZXNzYWdlUmVhZChpZCkgYXMgdW5rbm93biBhcyBib29sZWFuO1xyXG59XHJcblxyXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gbWFya0FsbE5vdGlmaWNhdGlvbnNSZWFkQXBpKCk6IFByb21pc2U8Ym9vbGVhbj4ge1xyXG4gIGlmIChhcGlNb2RlID09PSAncmVhbCcpIHtcclxuICAgIGF3YWl0IGg1QXBpLnB1dCgnL2FwaS9oNS9ub3RpZmljYXRpb25zL3JlYWQtYWxsJyk7XHJcbiAgICByZXR1cm4gdHJ1ZTtcclxuICB9XHJcbiAgcmV0dXJuIG1hcmtBbGxNZXNzYWdlc1JlYWQoKSBhcyB1bmtub3duIGFzIGJvb2xlYW47XHJcbn1cclxuXHJcbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBnZXRUaWNrZXRzQXBpKHBhcmFtczogeyBwYWdlPzogbnVtYmVyOyBzaXplPzogbnVtYmVyIH0pOiBQcm9taXNlPHsgaXRlbXM6IHVua25vd25bXTsgdG90YWw6IG51bWJlciB9PiB7XHJcbiAgaWYgKGFwaU1vZGUgPT09ICdyZWFsJykge1xyXG4gICAgY29uc3QgcmVzID0gYXdhaXQgaDVBcGkuZ2V0KCcvYXBpL2g1L3RpY2tldHMnLCB7IHBhcmFtcyB9KTtcclxuICAgIHJldHVybiByZXMuZGF0YTtcclxuICB9XHJcbiAgY29uc3QgdGlja2V0cyA9IGdldFN1cHBvcnRUaWNrZXRzKCk7XHJcbiAgY29uc3QgcGFnZSA9IHBhcmFtcy5wYWdlID8/IDE7XHJcbiAgY29uc3Qgc2l6ZSA9IHBhcmFtcy5zaXplID8/IDIwO1xyXG4gIHJldHVybiB7IGl0ZW1zOiB0aWNrZXRzLnNsaWNlKChwYWdlIC0gMSkgKiBzaXplLCBwYWdlICogc2l6ZSksIHRvdGFsOiB0aWNrZXRzLmxlbmd0aCB9O1xyXG59XHJcblxyXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gY3JlYXRlVGlja2V0QXBpKGRhdGE6IHsgY2F0ZWdvcnk6IHN0cmluZzsgcHJpb3JpdHk6IHN0cmluZzsgc3ViamVjdDogc3RyaW5nOyBkZXNjcmlwdGlvbjogc3RyaW5nIH0pOiBQcm9taXNlPHsgaWQ6IHN0cmluZyB9PiB7XHJcbiAgaWYgKGFwaU1vZGUgPT09ICdyZWFsJykge1xyXG4gICAgY29uc3QgcmVzID0gYXdhaXQgaDVBcGkucG9zdCgnL2FwaS9oNS90aWNrZXRzJywgZGF0YSk7XHJcbiAgICByZXR1cm4gcmVzLmRhdGE7XHJcbiAgfVxyXG4gIGNvbnN0IG5vdyA9IG5ldyBEYXRlKCkudG9JU09TdHJpbmcoKTtcclxuICBjb25zdCBpZCA9ICdtb2NrLScgKyBEYXRlLm5vdygpO1xyXG4gIG1vY2tUaWNrZXRzU3RvcmUudW5zaGlmdCh7XHJcbiAgICBpZCxcclxuICAgIGNhdGVnb3J5OiBkYXRhLmNhdGVnb3J5LFxyXG4gICAgcHJpb3JpdHk6IGRhdGEucHJpb3JpdHksXHJcbiAgICBzdWJqZWN0OiBkYXRhLnN1YmplY3QsXHJcbiAgICBkZXNjcmlwdGlvbjogZGF0YS5kZXNjcmlwdGlvbixcclxuICAgIHN0YXR1czogJ29wZW4nLFxyXG4gICAgY3JlYXRlZF9hdDogbm93LFxyXG4gICAgdXBkYXRlZF9hdDogbm93LFxyXG4gICAgbGFzdF9yZXBseV9hdDogbm93LFxyXG4gICAgbWVzc2FnZXM6IFt7XHJcbiAgICAgIGlkOiBpZCArICctbXNnLTAnLFxyXG4gICAgICBzZW5kZXJfdHlwZTogJ3VzZXInLFxyXG4gICAgICBzZW5kZXJfbmFtZTogJ3VzZXInLFxyXG4gICAgICBjb250ZW50OiBkYXRhLmRlc2NyaXB0aW9uLFxyXG4gICAgICBjcmVhdGVkX2F0OiBub3csXHJcbiAgICAgIGludGVybmFsX29ubHk6IGZhbHNlLFxyXG4gICAgfV0sXHJcbiAgfSk7XHJcbiAgcmV0dXJuIHsgaWQgfTtcclxufVxyXG5cclxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGdldFRpY2tldERldGFpbEFwaShpZDogc3RyaW5nKTogUHJvbWlzZTx1bmtub3duIHwgbnVsbD4ge1xyXG4gIGlmIChhcGlNb2RlID09PSAncmVhbCcpIHtcclxuICAgIGNvbnN0IHJlcyA9IGF3YWl0IGg1QXBpLmdldCgnL2FwaS9oNS90aWNrZXRzLycgKyBlbmNvZGVVUklDb21wb25lbnQoaWQpKTtcclxuICAgIHJldHVybiByZXMuZGF0YTtcclxuICB9XHJcbiAgcmV0dXJuIGdldFN1cHBvcnRUaWNrZXRCeUlkKGlkKTtcclxufVxyXG5cclxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIHJlcGx5VG9UaWNrZXRBcGkodGlja2V0SWQ6IHN0cmluZywgbWVzc2FnZTogc3RyaW5nKTogUHJvbWlzZTxib29sZWFuPiB7XHJcbiAgaWYgKGFwaU1vZGUgPT09ICdyZWFsJykge1xyXG4gICAgYXdhaXQgaDVBcGkucG9zdCgnL2FwaS9oNS90aWNrZXRzLycgKyBlbmNvZGVVUklDb21wb25lbnQodGlja2V0SWQpICsgJy9tZXNzYWdlcycsIHsgbWVzc2FnZSB9KTtcclxuICAgIHJldHVybiB0cnVlO1xyXG4gIH1cclxuICByZXR1cm4gYWRkVGlja2V0UmVwbHkodGlja2V0SWQsIG1lc3NhZ2UpO1xyXG59XHJcblxyXG5mdW5jdGlvbiBnZXRNb2NrTGVhZGVyYm9hcmQoKTogeyByYW5raW5nczogeyByYW5rOiBudW1iZXI7IHVzZXJJZDogc3RyaW5nOyBzY29yZTogbnVtYmVyIH1bXSB9IHtcclxuICByZXR1cm4ge1xyXG4gICAgcmFua2luZ3M6IFtcclxuICAgICAgeyByYW5rOiAxLCB1c2VySWQ6IFwiMTI4NjQ0NzJcIiwgc2NvcmU6IDUyMDAgfSxcclxuICAgICAgeyByYW5rOiAyLCB1c2VySWQ6IFwiODczNDIxNTVcIiwgc2NvcmU6IDQ3NjAgfSxcclxuICAgICAgeyByYW5rOiAzLCB1c2VySWQ6IFwiNTQwMjE4NjNcIiwgc2NvcmU6IDM5ODAgfSxcclxuICAgICAgeyByYW5rOiA0LCB1c2VySWQ6IFwiNzQxOTA1MzhcIiwgc2NvcmU6IDM1MTAgfSxcclxuICAgIF0sXHJcbiAgfTtcclxufVxyXG5cclxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGdldExlYWRlcmJvYXJkQXBpKCk6IFByb21pc2U8eyByYW5raW5nczogeyByYW5rOiBudW1iZXI7IHVzZXJJZDogc3RyaW5nOyBzY29yZTogbnVtYmVyIH1bXSB9PiB7XHJcbiAgaWYgKGFwaU1vZGUgPT09ICdyZWFsJykge1xyXG4gICAgY29uc3QgcmVzID0gYXdhaXQgaDVBcGkuZ2V0KCcvYXBpL2g1L2xlYWRlcmJvYXJkJyk7XHJcbiAgICByZXR1cm4gcmVzLmRhdGE7XHJcbiAgfVxyXG4gIHJldHVybiBnZXRNb2NrTGVhZGVyYm9hcmQoKTtcclxufVxyXG5cclxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGdldFByb21vdGlvbnNBcGkoKTogUHJvbWlzZTx7IGl0ZW1zOiB1bmtub3duW10gfT4ge1xyXG4gIGlmIChhcGlNb2RlID09PSAncmVhbCcpIHtcclxuICAgIGNvbnN0IHJlcyA9IGF3YWl0IGg1QXBpLmdldCgnL2FwaS9oNS9wcm9tb3Rpb25zJyk7XHJcbiAgICByZXR1cm4gcmVzLmRhdGE7XHJcbiAgfVxyXG4gIHJldHVybiB7IGl0ZW1zOiBbXSB9O1xyXG59XHJcblxyXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gam9pblByb21vdGlvbkFwaShpZDogc3RyaW5nKTogUHJvbWlzZTx7IHN1Y2Nlc3M6IGJvb2xlYW4gfT4ge1xyXG4gIGlmIChhcGlNb2RlID09PSAncmVhbCcpIHtcclxuICAgIGNvbnN0IHJlcyA9IGF3YWl0IGg1QXBpLnBvc3QoYC9hcGkvaDUvcHJvbW90aW9ucy8ke2lkfS9qb2luYCk7XHJcbiAgICByZXR1cm4gcmVzLmRhdGE7XHJcbiAgfVxyXG4gIHJldHVybiB7IHN1Y2Nlc3M6IHRydWUgfTtcclxufVxyXG5cclxuLy8g4pSA4pSA4pSAIE1vY2sgaGVscGVycyBmb3IgY29tbWVyY2UgQVBJIOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgFxyXG5cclxuZnVuY3Rpb24gZ2V0TW9ja09yZGVycyhwYXJhbXM6IHsgcGFnZT86IG51bWJlcjsgc2l6ZT86IG51bWJlcjsgc3RhdHVzPzogc3RyaW5nIH0pOiB7IGl0ZW1zOiBINU1lbWJlck9yZGVyW107IHRvdGFsOiBudW1iZXIgfSB7XHJcbiAgY29uc3Qgc2Vzc2lvbiA9IGdldFJlcXVpcmVkU2Vzc2lvbigpO1xyXG4gIGNvbnN0IHN0YXRlID0gZ2V0U3RhdGVGb3JBY2NvdW50KHNlc3Npb24uYWNjb3VudElkKTtcclxuICBsZXQgZmlsdGVyZWQgPSBzdGF0ZS5vcmRlcnM7XHJcbiAgaWYgKHBhcmFtcy5zdGF0dXMgJiYgcGFyYW1zLnN0YXR1cyAhPT0gJ2FsbCcpIHtcclxuICAgIGZpbHRlcmVkID0gZmlsdGVyZWQuZmlsdGVyKChvKSA9PiBvLnN0YXR1cyA9PT0gcGFyYW1zLnN0YXR1cyk7XHJcbiAgfVxyXG4gIGNvbnN0IHBhZ2UgPSBwYXJhbXMucGFnZSA/PyAxO1xyXG4gIGNvbnN0IHNpemUgPSBwYXJhbXMuc2l6ZSA/PyAyMDtcclxuICBjb25zdCBzb3J0ZWQgPSBbLi4uZmlsdGVyZWRdLnNvcnQoKGEsIGIpID0+IGIuY3JlYXRlZEF0LmxvY2FsZUNvbXBhcmUoYS5jcmVhdGVkQXQpKTtcclxuICByZXR1cm4geyBpdGVtczogc29ydGVkLnNsaWNlKChwYWdlIC0gMSkgKiBzaXplLCBwYWdlICogc2l6ZSksIHRvdGFsOiBzb3J0ZWQubGVuZ3RoIH07XHJcbn1cclxuXHJcbi8vIOKUgOKUgOKUgCBINTItMDEzOiBDb21tZXJjZSBBUEkgZnVuY3Rpb25zIOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgFxyXG5cclxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGdldFByb2R1Y3RzQXBpKCk6IFByb21pc2U8eyBpZDogc3RyaW5nOyBuYW1lOiBzdHJpbmc7IHByaWNlOiBudW1iZXI7IGltYWdlX3VybDogc3RyaW5nOyB9W10+IHtcclxuICBpZiAoYXBpTW9kZSA9PT0gJ3JlYWwnKSB7XHJcbiAgICBjb25zdCByZXMgPSBhd2FpdCBoNUFwaS5nZXQoJy9hcGkvaDUvY29tbWVyY2UvcHJvZHVjdHMnKTtcclxuICAgIHJldHVybiByZXMuZGF0YS5pdGVtcyA/PyByZXMuZGF0YTtcclxuICB9XHJcbiAgcmV0dXJuIFtdO1xyXG59XHJcblxyXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gZ2V0UHJvZHVjdERldGFpbEFwaShpZDogc3RyaW5nKTogUHJvbWlzZTx1bmtub3duIHwgbnVsbD4ge1xyXG4gIGlmIChhcGlNb2RlID09PSAncmVhbCcpIHtcclxuICAgIGNvbnN0IHJlcyA9IGF3YWl0IGg1QXBpLmdldChgL2FwaS9oNS9jb21tZXJjZS9wcm9kdWN0cy8ke2lkfWApO1xyXG4gICAgcmV0dXJuIHJlcy5kYXRhO1xyXG4gIH1cclxuICByZXR1cm4gbnVsbDtcclxufVxyXG5cclxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGNyZWF0ZU9yZGVyQXBpKHByb2R1Y3RJZDogc3RyaW5nLCBxdWFudGl0eTogbnVtYmVyKTogUHJvbWlzZTx7IGlkOiBzdHJpbmcgfT4ge1xyXG4gIGlmIChhcGlNb2RlID09PSAncmVhbCcpIHtcclxuICAgIGNvbnN0IHJlcyA9IGF3YWl0IGg1QXBpLnBvc3QoJy9hcGkvaDUvY29tbWVyY2Uvb3JkZXJzJywgeyBwcm9kdWN0X2lkOiBwcm9kdWN0SWQsIHF1YW50aXR5IH0pO1xyXG4gICAgcmV0dXJuIHJlcy5kYXRhO1xyXG4gIH1cclxuICByZXR1cm4geyBpZDogYG1vY2stJHtEYXRlLm5vdygpfWAgfTtcclxufVxyXG5cclxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGdldE9yZGVyc0FwaShwYXJhbXM6IHsgcGFnZT86IG51bWJlcjsgc2l6ZT86IG51bWJlcjsgc3RhdHVzPzogc3RyaW5nIH0pOiBQcm9taXNlPHsgaXRlbXM6IHVua25vd25bXTsgdG90YWw6IG51bWJlciB9PiB7XHJcbiAgaWYgKGFwaU1vZGUgPT09ICdyZWFsJykge1xyXG4gICAgY29uc3QgcmVzID0gYXdhaXQgaDVBcGkuZ2V0KCcvYXBpL2g1L2NvbW1lcmNlL29yZGVycycsIHsgcGFyYW1zIH0pO1xyXG4gICAgcmV0dXJuIHJlcy5kYXRhO1xyXG4gIH1cclxuICByZXR1cm4gZ2V0TW9ja09yZGVycyhwYXJhbXMpO1xyXG59XHJcblxyXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gZ2V0T3JkZXJEZXRhaWxBcGkoaWQ6IHN0cmluZyk6IFByb21pc2U8dW5rbm93biB8IG51bGw+IHtcclxuICBpZiAoYXBpTW9kZSA9PT0gJ3JlYWwnKSB7XHJcbiAgICBjb25zdCByZXMgPSBhd2FpdCBoNUFwaS5nZXQoYC9hcGkvaDUvY29tbWVyY2Uvb3JkZXJzLyR7aWR9YCk7XHJcbiAgICByZXR1cm4gcmVzLmRhdGE7XHJcbiAgfVxyXG4gIHJldHVybiBudWxsO1xyXG59XHJcblxyXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gZ2V0TG9naXN0aWNzQXBpKG9yZGVySWQ6IHN0cmluZyk6IFByb21pc2U8eyBzdGF0dXM6IHN0cmluZzsgdHJhY2tpbmdfbnVtYmVyPzogc3RyaW5nOyBzdGVwczogdW5rbm93bltdIH0+IHtcclxuICBpZiAoYXBpTW9kZSA9PT0gJ3JlYWwnKSB7XHJcbiAgICBjb25zdCByZXMgPSBhd2FpdCBoNUFwaS5nZXQoYC9hcGkvaDUvY29tbWVyY2Uvb3JkZXJzLyR7b3JkZXJJZH0vbG9naXN0aWNzYCk7XHJcbiAgICByZXR1cm4gcmVzLmRhdGE7XHJcbiAgfVxyXG4gIHJldHVybiB7IHN0YXR1czogJ3BlbmRpbmcnLCBzdGVwczogW10gfTtcclxufVxyXG5cclxuLy8g4pSA4pSA4pSAIEg1Mi0wMTQ6IEZyYWdtZW50ICsgTWFpbGluZyBBUEkgZnVuY3Rpb25zIOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgFxyXG5cclxuZnVuY3Rpb24gZ2V0TW9ja0ZyYWdtZW50cygpOiB7IGl0ZW1zOiB1bmtub3duW107IG92ZXJ2aWV3OiB1bmtub3duIH0ge1xyXG4gIGNvbnN0IHNlc3Npb24gPSBnZXRSZXF1aXJlZFNlc3Npb24oKTtcclxuICBjb25zdCBzdGF0ZSA9IGdldFN0YXRlRm9yQWNjb3VudChzZXNzaW9uLmFjY291bnRJZCk7XHJcbiAgY29uc3Qgb3ZlcnZpZXcgPSBidWlsZEZyYWdtZW50T3ZlcnZpZXcoc3RhdGUpO1xyXG4gIHJldHVybiB7XHJcbiAgICBpdGVtczogb3ZlcnZpZXcuaW52ZW50b3J5LFxyXG4gICAgb3ZlcnZpZXcsXHJcbiAgfTtcclxufVxyXG5cclxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGdldEZyYWdtZW50c0FwaSgpOiBQcm9taXNlPHsgaXRlbXM6IHVua25vd25bXTsgb3ZlcnZpZXc6IHVua25vd24gfT4ge1xyXG4gIGlmIChhcGlNb2RlID09PSAncmVhbCcpIHtcclxuICAgIGNvbnN0IHJlcyA9IGF3YWl0IGg1QXBpLmdldCgnL2FwaS9oNS9mcmFnbWVudHMnKTtcclxuICAgIHJldHVybiByZXMuZGF0YTtcclxuICB9XHJcbiAgcmV0dXJuIGdldE1vY2tGcmFnbWVudHMoKTtcclxufVxyXG5cclxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGdldEZyYWdtZW50RGV0YWlsQXBpKGlkOiBzdHJpbmcpOiBQcm9taXNlPHVua25vd24gfCBudWxsPiB7XHJcbiAgaWYgKGFwaU1vZGUgPT09ICdyZWFsJykge1xyXG4gICAgY29uc3QgcmVzID0gYXdhaXQgaDVBcGkuZ2V0KCcvYXBpL2g1L2ZyYWdtZW50cy8nICsgZW5jb2RlVVJJQ29tcG9uZW50KGlkKSk7XHJcbiAgICByZXR1cm4gcmVzLmRhdGE7XHJcbiAgfVxyXG4gIHJldHVybiBudWxsO1xyXG59XHJcblxyXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gY2hlY2tJbkZyYWdtZW50QXBpKCk6IFByb21pc2U8eyBzdWNjZXNzOiBib29sZWFuOyBmcmFnbWVudDogdW5rbm93biB9PiB7XHJcbiAgaWYgKGFwaU1vZGUgPT09ICdyZWFsJykge1xyXG4gICAgY29uc3QgcmVzID0gYXdhaXQgaDVBcGkucG9zdCgnL2FwaS9oNS9mcmFnbWVudHMvY2hlY2staW4nKTtcclxuICAgIHJldHVybiByZXMuZGF0YTtcclxuICB9XHJcbiAgcmV0dXJuIHsgc3VjY2VzczogdHJ1ZSwgZnJhZ21lbnQ6IHsgaWQ6ICdtb2NrLScgKyBEYXRlLm5vdygpIH0gfTtcclxufVxyXG5cclxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGV4Y2hhbmdlRnJhZ21lbnRzQXBpKGRhdGE6IHsgaXRlbV9pZDogc3RyaW5nOyBhZGRyZXNzOiB1bmtub3duIH0pOiBQcm9taXNlPHsgaWQ6IHN0cmluZzsgc3RhdHVzOiBzdHJpbmcgfT4ge1xyXG4gIGlmIChhcGlNb2RlID09PSAncmVhbCcpIHtcclxuICAgIGNvbnN0IHJlcyA9IGF3YWl0IGg1QXBpLnBvc3QoJy9hcGkvaDUvZnJhZ21lbnRzL2V4Y2hhbmdlcycsIGRhdGEpO1xyXG4gICAgcmV0dXJuIHJlcy5kYXRhO1xyXG4gIH1cclxuICByZXR1cm4geyBpZDogJ21vY2stJyArIERhdGUubm93KCksIHN0YXR1czogJ3N1Ym1pdHRlZCcgfTtcclxufVxyXG5cclxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGdldFNoaXBwaW5nU3RhdHVzQXBpKGV4Y2hhbmdlSWQ6IHN0cmluZyk6IFByb21pc2U8eyBzdGF0dXM6IHN0cmluZzsgdHJhY2tpbmdfbnVtYmVyPzogc3RyaW5nIH0+IHtcclxuICBpZiAoYXBpTW9kZSA9PT0gJ3JlYWwnKSB7XHJcbiAgICBjb25zdCByZXMgPSBhd2FpdCBoNUFwaS5nZXQoJy9hcGkvaDUvcmV3YXJkcy9zaGlwcGluZy8nICsgZW5jb2RlVVJJQ29tcG9uZW50KGV4Y2hhbmdlSWQpKTtcclxuICAgIHJldHVybiByZXMuZGF0YTtcclxuICB9XHJcbiAgcmV0dXJuIHsgc3RhdHVzOiAncGVuZGluZycgfTtcclxufVxyXG5cclxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIHN1YnNjcmliZU1haWxpbmdBcGkoZW1haWw6IHN0cmluZyk6IFByb21pc2U8Ym9vbGVhbj4ge1xyXG4gIGlmIChhcGlNb2RlID09PSAncmVhbCcpIHtcclxuICAgIGF3YWl0IGg1QXBpLnBvc3QoJy9hcGkvaDUvbWFpbGluZy9zdWJzY3JpYmUnLCB7IGVtYWlsIH0pO1xyXG4gICAgcmV0dXJuIHRydWU7XHJcbiAgfVxyXG4gIHJldHVybiB0cnVlO1xyXG59XHJcblxyXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gdW5zdWJzY3JpYmVNYWlsaW5nQXBpKGVtYWlsOiBzdHJpbmcpOiBQcm9taXNlPGJvb2xlYW4+IHtcclxuICBpZiAoYXBpTW9kZSA9PT0gJ3JlYWwnKSB7XHJcbiAgICBhd2FpdCBoNUFwaS5wb3N0KCcvYXBpL2g1L21haWxpbmcvdW5zdWJzY3JpYmUnLCB7IGVtYWlsIH0pO1xyXG4gICAgcmV0dXJuIHRydWU7XHJcbiAgfVxyXG4gIHJldHVybiB0cnVlO1xyXG59XHJcblxyXG5leHBvcnQgY29uc3QgSDVfQVBJX0VORFBPSU5UUyA9IHtcclxuICB3YWxsZXQ6IHtcclxuICAgIGJhbGFuY2U6ICcvYXBpL2g1L3dhbGxldC9iYWxhbmNlJyxcclxuICAgIHRyYW5zYWN0aW9uczogJy9hcGkvaDUvd2FsbGV0L3RyYW5zYWN0aW9ucycsXHJcbiAgICByZWNoYXJnZTogJy9hcGkvaDUvd2FsbGV0L3JlY2hhcmdlJyxcclxuICAgIHJlY2hhcmdlU3RhdHVzOiAoaWQ6IHN0cmluZykgPT4gYC9hcGkvaDUvd2FsbGV0L3JlY2hhcmdlLyR7aWR9L3N0YXR1c2AsXHJcbiAgfSxcclxuICB3aXRoZHJhd2Fsczoge1xyXG4gICAgbGlzdDogJy9hcGkvaDUvd2l0aGRyYXdhbHMnLFxyXG4gICAgZGV0YWlsOiAoaWQ6IHN0cmluZykgPT4gYC9hcGkvaDUvd2l0aGRyYXdhbHMvJHtpZH1gLFxyXG4gIH0sXHJcbiAgdGFza3M6IHtcclxuICAgIGxpc3Q6ICcvYXBpL2g1L3Rhc2tzJyxcclxuICAgIGRldGFpbDogKGlkOiBzdHJpbmcpID0+IGAvYXBpL2g1L3Rhc2tzLyR7aWR9YCxcclxuICAgIHN1Ym1pdDogKGlkOiBzdHJpbmcpID0+IGAvYXBpL2g1L3Rhc2tzLyR7aWR9L3N1Ym1pdGAsXHJcbiAgICBwcm9vZjogKGlkOiBzdHJpbmcpID0+IGAvYXBpL2g1L3Rhc2tzLyR7aWR9L3Byb29mYCxcclxuICB9LFxyXG4gIG5vdGlmaWNhdGlvbnM6ICcvYXBpL2g1L25vdGlmaWNhdGlvbnMnLFxyXG4gIG5vdGlmaWNhdGlvbnNVbnJlYWRDb3VudDogJy9hcGkvaDUvbm90aWZpY2F0aW9ucz91bnJlYWQ9dHJ1ZSZjb3VudF9vbmx5PXRydWUnLFxyXG4gIHRpY2tldHM6IHtcclxuICAgIGxpc3Q6ICcvYXBpL2g1L3RpY2tldHMnLFxyXG4gICAgZGV0YWlsOiAoaWQ6IHN0cmluZykgPT4gYC9hcGkvaDUvdGlja2V0cy8ke2lkfWAsXHJcbiAgfSxcclxuICB2ZXJpZmljYXRpb25zOiB7XHJcbiAgICBsaXN0OiAnL2FwaS9oNS92ZXJpZmljYXRpb25zJyxcclxuICAgIHBob3RvczogKGlkOiBzdHJpbmcpID0+IGAvYXBpL2g1L3ZlcmlmaWNhdGlvbnMvJHtpZH0vcGhvdG9zYCxcclxuICB9LFxyXG4gIHdoYXRzYXBwQmluZGluZ3M6ICcvYXBpL2g1L3doYXRzYXBwLWJpbmRpbmdzJyxcclxuICBjb21tZXJjZToge1xyXG4gICAgcHJvZHVjdHM6ICcvYXBpL2g1L2NvbW1lcmNlL3Byb2R1Y3RzJyxcclxuICAgIG9yZGVyczogJy9hcGkvaDUvY29tbWVyY2Uvb3JkZXJzJyxcclxuICB9LFxyXG4gIGZyYWdtZW50czogJy9hcGkvaDUvZnJhZ21lbnRzJyxcclxuICBwcm9tb3Rpb25zOiAnL2FwaS9oNS9wcm9tb3Rpb25zJyxcclxuICBsZWFkZXJib2FyZDogJy9hcGkvaDUvbGVhZGVyYm9hcmQnLFxyXG59IGFzIGNvbnN0O1xyXG5cclxuLy8g4pSA4pSA4pSAIEg1Mi0wMTY6IENoYXQgbWVzc2FnZSB0eXBlcyDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIBcclxuXHJcbmV4cG9ydCB0eXBlIEg1Q2hhdE1lc3NhZ2UgPSB7XHJcbiAgaWQ6IHN0cmluZztcclxuICBjb250ZW50OiBzdHJpbmc7XHJcbiAgdHlwZTogJ3RleHQnIHwgJ2ltYWdlJyB8ICdzeXN0ZW0nO1xyXG4gIGltYWdlX3VybD86IHN0cmluZztcclxuICBkaXJlY3Rpb246ICdpbmJvdW5kJyB8ICdvdXRib3VuZCc7XHJcbiAgc3RhdHVzOiAnc2VuZGluZycgfCAnc2VudCcgfCAnZGVsaXZlcmVkJyB8ICdyZWFkJztcclxuICB0aW1lc3RhbXA6IHN0cmluZztcclxufTtcclxuXHJcbi8vIOKUgOKUgOKUgCBINTItMDE2OiBDaGF0IEFQSSBmdW5jdGlvbnMg4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSAXHJcblxyXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gZ2V0TWVzc2FnZXNBcGkocGFyYW1zOiB7IHBhZ2U/OiBudW1iZXI7IHNpemU/OiBudW1iZXI7IGNvbnZlcnNhdGlvbl9pZD86IHN0cmluZyB9KTogUHJvbWlzZTx7IGl0ZW1zOiBINUNoYXRNZXNzYWdlW107IHRvdGFsOiBudW1iZXIgfT4ge1xyXG4gIGlmIChhcGlNb2RlID09PSAncmVhbCcpIHtcclxuICAgIGNvbnN0IHJlcyA9IGF3YWl0IGg1QXBpLmdldCgnL2FwaS9oNS9tZXNzYWdlcycsIHsgcGFyYW1zIH0pO1xyXG4gICAgcmV0dXJuIHJlcy5kYXRhO1xyXG4gIH1cclxuICAvLyBNb2NrOiByZXR1cm4gc2FtcGxlIG1lc3NhZ2VzXHJcbiAgY29uc3QgbW9ja01zZ3M6IEg1Q2hhdE1lc3NhZ2VbXSA9IFtcclxuICAgIHsgaWQ6ICdtMScsIGNvbnRlbnQ6IGdldFNlZWREYXRhVGV4dChcImNoYXRXZWxjb21lSW5ib3VuZFwiKSwgdHlwZTogJ3RleHQnLCBkaXJlY3Rpb246ICdpbmJvdW5kJywgc3RhdHVzOiAncmVhZCcsIHRpbWVzdGFtcDogbmV3IERhdGUoRGF0ZS5ub3coKSAtIDM2MDAwMDApLnRvSVNPU3RyaW5nKCkgfSxcclxuICAgIHsgaWQ6ICdtMicsIGNvbnRlbnQ6IGdldFNlZWREYXRhVGV4dChcImNoYXRXZWxjb21lT3V0Ym91bmRcIiksIHR5cGU6ICd0ZXh0JywgZGlyZWN0aW9uOiAnb3V0Ym91bmQnLCBzdGF0dXM6ICdyZWFkJywgdGltZXN0YW1wOiBuZXcgRGF0ZShEYXRlLm5vdygpIC0gMzUwMDAwMCkudG9JU09TdHJpbmcoKSB9LFxyXG4gICAgeyBpZDogJ20zJywgY29udGVudDogZ2V0U2VlZERhdGFUZXh0KFwiY2hhdFdlbGNvbWVSZXBseVwiKSwgdHlwZTogJ3RleHQnLCBkaXJlY3Rpb246ICdpbmJvdW5kJywgc3RhdHVzOiAncmVhZCcsIHRpbWVzdGFtcDogbmV3IERhdGUoRGF0ZS5ub3coKSAtIDM0MDAwMDApLnRvSVNPU3RyaW5nKCkgfSxcclxuICBdO1xyXG4gIGNvbnN0IHBhZ2UgPSBwYXJhbXMucGFnZSA/PyAxO1xyXG4gIGNvbnN0IHNpemUgPSBwYXJhbXMuc2l6ZSA/PyAyMDtcclxuICByZXR1cm4geyBpdGVtczogbW9ja01zZ3Muc2xpY2UoKHBhZ2UgLSAxKSAqIHNpemUsIHBhZ2UgKiBzaXplKSwgdG90YWw6IG1vY2tNc2dzLmxlbmd0aCB9O1xyXG59XHJcblxyXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gc2VuZE1lc3NhZ2VBcGkoY29udmVyc2F0aW9uSWQ6IHN0cmluZywgY29udGVudDogc3RyaW5nLCB0eXBlOiBzdHJpbmcgPSAndGV4dCcpOiBQcm9taXNlPEg1Q2hhdE1lc3NhZ2U+IHtcclxuICBpZiAoYXBpTW9kZSA9PT0gJ3JlYWwnKSB7XHJcbiAgICBjb25zdCByZXMgPSBhd2FpdCBoNUFwaS5wb3N0KCcvYXBpL2g1L21lc3NhZ2VzJywgeyBjb252ZXJzYXRpb25faWQ6IGNvbnZlcnNhdGlvbklkLCBjb250ZW50LCB0eXBlIH0pO1xyXG4gICAgcmV0dXJuIHJlcy5kYXRhO1xyXG4gIH1cclxuICByZXR1cm4ge1xyXG4gICAgaWQ6IGBtb2NrLSR7RGF0ZS5ub3coKX1gLFxyXG4gICAgY29udGVudCxcclxuICAgIHR5cGU6IHR5cGUgYXMgJ3RleHQnIHwgJ2ltYWdlJyxcclxuICAgIGRpcmVjdGlvbjogJ291dGJvdW5kJyxcclxuICAgIHN0YXR1czogJ3NlbnQnLFxyXG4gICAgdGltZXN0YW1wOiBuZXcgRGF0ZSgpLnRvSVNPU3RyaW5nKCksXHJcbiAgfTtcclxufVxyXG5cclxuLy8g4pSA4pSAIFNpZ24taW4gVHlwZXMg4pSA4pSAXHJcblxyXG5leHBvcnQgdHlwZSBINVNpZ25JblN0YXR1cyA9IHtcclxuICBjb25zZWN1dGl2ZURheXM6IG51bWJlcjtcclxuICB0b2RheVNpZ25lZEluOiBib29sZWFuO1xyXG4gIGdvYWxEYXlzOiBudW1iZXI7XHJcbiAgZ29hbFJld2FyZDogbnVtYmVyO1xyXG4gIGlzQ29tcGxldGVkOiBib29sZWFuO1xyXG59O1xyXG5cclxuLy8g4pSA4pSAIFRhc2sgSW5zdGFuY2UgVHlwZXMg4pSA4pSAXHJcblxyXG5leHBvcnQgdHlwZSBINVRhc2tQcm9kdWN0U3RhdHVzID0gXCJwZW5kaW5nXCIgfCBcImF2YWlsYWJsZVwiIHwgXCJydW5uaW5nXCIgfCBcImNvbXBsZXRlZFwiIHwgXCJmYWlsZWRcIjtcclxuXHJcbmV4cG9ydCB0eXBlIEg1VGFza1Byb2R1Y3QgPSB7XHJcbiAgaWQ6IHN0cmluZztcclxuICBwcm9kdWN0TmFtZTogc3RyaW5nO1xyXG4gIGltYWdlVXJsOiBzdHJpbmc7XHJcbiAgcHJpY2U6IG51bWJlcjtcclxuICBjdXJyZW5jeTogc3RyaW5nO1xyXG4gIHN0YXR1czogSDVUYXNrUHJvZHVjdFN0YXR1cztcclxufTtcclxuXHJcbmV4cG9ydCB0eXBlIEg1VGFza0luc3RhbmNlID0ge1xyXG4gIGlkOiBzdHJpbmc7XHJcbiAgdGl0bGU6IHN0cmluZztcclxuICBkZXNjcmlwdGlvbjogc3RyaW5nO1xyXG4gIHR5cGU6IEg1VGFza1BhY2thZ2VUeXBlO1xyXG4gIHN0YXR1czogSDVUYXNrUGFja2FnZVN0YXR1cztcclxuICByZXdhcmRSYXRpbzogbnVtYmVyO1xyXG4gIHJld2FyZEFtb3VudDogbnVtYmVyO1xyXG4gIHByb2R1Y3RzOiBINVRhc2tQcm9kdWN0W107XHJcbiAgY29tcGxldGVkQ291bnQ6IG51bWJlcjtcclxuICB0b3RhbENvdW50OiBudW1iZXI7XHJcbiAgc3lzdGVtQmFsYW5jZTogbnVtYmVyO1xyXG4gIHRvdGFsQ29tbWlzc2lvbj86IG51bWJlcjtcclxuICBjdXJyZW50Q29tbWlzc2lvbj86IG51bWJlcjtcclxuICBjb3VudGRvd25TZWNvbmRzPzogbnVtYmVyO1xyXG4gIGNvbXBsZXRpb25XaW5kb3dIb3Vycz86IG51bWJlcjtcclxufTtcclxuXHJcbi8vIOKUgOKUgCBJbnZpdGUgVHlwZXMg4pSA4pSAXHJcblxyXG5leHBvcnQgdHlwZSBINUludml0ZVJlY29yZCA9IHtcclxuICBpZDogc3RyaW5nO1xyXG4gIHVzZXJJZE1hc2tlZDogc3RyaW5nO1xyXG4gIHR5cGU6IFwicmVnaXN0cmF0aW9uXCIgfCBcInJlZ2lzdHJhdGlvbl9yZWNoYXJnZVwiO1xyXG4gIGNyZWF0ZWRBdDogc3RyaW5nO1xyXG4gIHJld2FyZEFtb3VudDogbnVtYmVyO1xyXG59O1xyXG5cclxuZXhwb3J0IHR5cGUgSDVJbnZpdGVJbmZvID0ge1xyXG4gIGludml0ZUxpbms6IHN0cmluZztcclxuICBpbnZpdGVkQ291bnQ6IG51bWJlcjtcclxuICBlYXJuZWRBbW91bnQ6IG51bWJlcjtcclxuICBtYXhJbnZpdGVzOiBudW1iZXI7XHJcbiAgcmVtYWluaW5nSW52aXRlczogbnVtYmVyO1xyXG59O1xyXG5cclxuLy8g4pSA4pSAIE1vY2sgU2lnbi1JbiDilIDilIBcclxuXHJcbmNvbnN0IFNJR05fSU5fR09BTF9EQVlTID0gNztcclxuY29uc3QgU0lHTl9JTl9HT0FMX1JFV0FSRCA9IDU7XHJcblxyXG5mdW5jdGlvbiBnZXRNb2NrU2lnbkluU3RhdHVzKCk6IEg1U2lnbkluU3RhdHVzIHtcclxuICBjb25zdCBzZXNzaW9uID0gZ2V0UmVxdWlyZWRTZXNzaW9uKCk7XHJcbiAgY29uc3Qgc3RhdGUgPSBnZXRTdGF0ZUZvckFjY291bnQoc2Vzc2lvbi5hY2NvdW50SWQpO1xyXG4gIGNvbnN0IGNoZWNrZWQgPSBzdGF0ZS5jaGVja2VkSW5EYXRlID09PSB0b2RheUtleSgpO1xyXG4gIGNvbnN0IGNvbnNlY3V0aXZlRGF5cyA9IGNoZWNrZWQgPyA1IDogMztcclxuICByZXR1cm4ge1xyXG4gICAgY29uc2VjdXRpdmVEYXlzLFxyXG4gICAgdG9kYXlTaWduZWRJbjogY2hlY2tlZCxcclxuICAgIGdvYWxEYXlzOiBTSUdOX0lOX0dPQUxfREFZUyxcclxuICAgIGdvYWxSZXdhcmQ6IFNJR05fSU5fR09BTF9SRVdBUkQsXHJcbiAgICBpc0NvbXBsZXRlZDogY29uc2VjdXRpdmVEYXlzID49IFNJR05fSU5fR09BTF9EQVlTLFxyXG4gIH07XHJcbn1cclxuXHJcbi8vIOKUgOKUgCBNb2NrIFRhc2sgSW5zdGFuY2Ug4pSA4pSAXHJcblxyXG5mdW5jdGlvbiBnZXRNb2NrVGFza0luc3RhbmNlcygpOiBINVRhc2tJbnN0YW5jZVtdIHtcclxuICBjb25zdCBzZXNzaW9uID0gZ2V0UmVxdWlyZWRTZXNzaW9uKCk7XHJcbiAgY29uc3Qgc3RhdGUgPSBnZXRTdGF0ZUZvckFjY291bnQoc2Vzc2lvbi5hY2NvdW50SWQpO1xyXG4gIGNvbnN0IHBhY2thZ2VzID0gc3RhdGUudGFza1BhY2thZ2VzLmZpbHRlcihcclxuICAgIHAgPT4gcC5zdGF0dXMgPT09IFwicGVuZGluZ19jbGFpbVwiIHx8IHAuc3RhdHVzID09PSBcImFjdGl2ZVwiIHx8IHAuc3RhdHVzID09PSBcImNvbXBsZXRlZFwiIHx8IHAuc3RhdHVzID09PSBcImV4cGlyZWRcIixcclxuICApO1xyXG4gIHJldHVybiBwYWNrYWdlcy5tYXAoKHBrZykgPT4ge1xyXG4gICAgY29uc3QgY29tcGxldGVkQ291bnQgPSBwa2cuaXRlbXMuZmlsdGVyKGkgPT4gaS5jb21wbGV0ZWRfYXQpLmxlbmd0aDtcclxuICAgIGNvbnN0IHRvdGFsQ291bnQgPSBwa2cuaXRlbXMubGVuZ3RoO1xyXG4gICAgY29uc3QgdG90YWxDb21taXNzaW9uID0gcGtnLml0ZW1zLnJlZHVjZSgoc3VtLCBpdGVtKSA9PiBzdW0gKyBpdGVtLnByaWNlICogcGtnLnJld2FyZFJhdGlvLCAwKTtcclxuICAgIGNvbnN0IGN1cnJlbnRDb21taXNzaW9uID0gcGtnLml0ZW1zXHJcbiAgICAgIC5maWx0ZXIoKGl0ZW0pID0+IEJvb2xlYW4oaXRlbS5jb21wbGV0ZWRfYXQpKVxyXG4gICAgICAucmVkdWNlKChzdW0sIGl0ZW0pID0+IHN1bSArIGl0ZW0ucHJpY2UgKiBwa2cucmV3YXJkUmF0aW8sIDApO1xyXG4gICAgY29uc3QgY291bnRkb3duU2Vjb25kcyA9IHBrZy5zdGF0dXMgPT09IFwicGVuZGluZ19jbGFpbVwiXHJcbiAgICAgID8gcGtnLmNvbXBsZXRpb25XaW5kb3dIb3VycyAqIDM2MDBcclxuICAgICAgOiBwa2cuZXhwaXJlc0F0XHJcbiAgICAgICAgPyBNYXRoLm1heCgwLCBNYXRoLmZsb29yKChuZXcgRGF0ZShwa2cuZXhwaXJlc0F0KS5nZXRUaW1lKCkgLSBEYXRlLm5vdygpKSAvIDEwMDApKVxyXG4gICAgICAgIDogMDtcclxuICAgIGNvbnN0IHByb2R1Y3RzOiBINVRhc2tQcm9kdWN0W10gPSBwa2cuaXRlbXMubWFwKChpdGVtLCBpZHgpID0+IHtcclxuICAgICAgbGV0IHN0YXR1czogSDVUYXNrUHJvZHVjdFN0YXR1cyA9IFwicGVuZGluZ1wiO1xyXG4gICAgICBpZiAocGtnLnN0YXR1cyA9PT0gXCJwZW5kaW5nX2NsYWltXCIpIHtcclxuICAgICAgICBzdGF0dXMgPSBcInBlbmRpbmdcIjtcclxuICAgICAgfSBlbHNlIGlmIChpdGVtLmNvbXBsZXRlZF9hdCkge1xyXG4gICAgICAgIHN0YXR1cyA9IFwiY29tcGxldGVkXCI7XHJcbiAgICAgIH0gZWxzZSBpZiAoaWR4ID09PSAwIHx8IHBrZy5pdGVtc1tpZHggLSAxXT8uY29tcGxldGVkX2F0KSB7XHJcbiAgICAgICAgc3RhdHVzID0gXCJhdmFpbGFibGVcIjtcclxuICAgICAgfVxyXG4gICAgICByZXR1cm4ge1xyXG4gICAgICAgIGlkOiBpdGVtLmlkLFxyXG4gICAgICAgIHByb2R1Y3ROYW1lOiBpdGVtLnByb2R1Y3RfbmFtZSxcclxuICAgICAgICBpbWFnZVVybDogaXRlbS5pbWFnZV91cmwsXHJcbiAgICAgICAgcHJpY2U6IGl0ZW0ucHJpY2UsXHJcbiAgICAgICAgY3VycmVuY3k6IGl0ZW0uY3VycmVuY3ksXHJcbiAgICAgICAgc3RhdHVzLFxyXG4gICAgICB9O1xyXG4gICAgfSk7XHJcbiAgICByZXR1cm4ge1xyXG4gICAgICBpZDogcGtnLmlkLFxyXG4gICAgICB0aXRsZTogcGtnLnRpdGxlLFxyXG4gICAgICBkZXNjcmlwdGlvbjogcGtnLmRlc2NyaXB0aW9uLFxyXG4gICAgICB0eXBlOiBwa2cudHlwZSxcclxuICAgICAgc3RhdHVzOiBwa2cuc3RhdHVzLFxyXG4gICAgICByZXdhcmRSYXRpbzogcGtnLnJld2FyZFJhdGlvLFxyXG4gICAgICByZXdhcmRBbW91bnQ6IHRvdGFsQ29tbWlzc2lvbixcclxuICAgICAgcHJvZHVjdHMsXHJcbiAgICAgIGNvbXBsZXRlZENvdW50LFxyXG4gICAgICB0b3RhbENvdW50LFxyXG4gICAgICBzeXN0ZW1CYWxhbmNlOiBzdGF0ZS53YWxsZXQuc3lzdGVtQmFsYW5jZSxcclxuICAgICAgdG90YWxDb21taXNzaW9uLFxyXG4gICAgICBjdXJyZW50Q29tbWlzc2lvbixcclxuICAgICAgY291bnRkb3duU2Vjb25kcyxcclxuICAgICAgY29tcGxldGlvbldpbmRvd0hvdXJzOiBwa2cuY29tcGxldGlvbldpbmRvd0hvdXJzLFxyXG4gICAgfTtcclxuICB9KTtcclxufVxyXG5cclxuZnVuY3Rpb24gZ2V0TW9ja1Rhc2tJbnN0YW5jZURldGFpbChpbnN0YW5jZUlkOiBzdHJpbmcpOiBINVRhc2tJbnN0YW5jZSB8IG51bGwge1xyXG4gIGNvbnN0IGluc3RhbmNlcyA9IGdldE1vY2tUYXNrSW5zdGFuY2VzKCk7XHJcbiAgcmV0dXJuIGluc3RhbmNlcy5maW5kKGkgPT4gaS5pZCA9PT0gaW5zdGFuY2VJZCkgPz8gbnVsbDtcclxufVxyXG5cclxuLy8g4pSA4pSAIE1vY2sgSW52aXRlIOKUgOKUgFxyXG5cclxuZnVuY3Rpb24gZ2V0TW9ja0ludml0ZUxpbmsoKTogc3RyaW5nIHtcclxuICBjb25zdCBzZXNzaW9uID0gZ2V0UmVxdWlyZWRTZXNzaW9uKCk7XHJcbiAgY29uc3Qgb3JpZ2luID0gdHlwZW9mIHdpbmRvdyAhPT0gXCJ1bmRlZmluZWRcIiA/IHdpbmRvdy5sb2NhdGlvbi5vcmlnaW4gOiBcImh0dHA6Ly8xMjcuMC4wLjE6NTE3M1wiO1xyXG4gIGNvbnN0IHVybCA9IG5ldyBVUkwoXCIvaDUvcmVnaXN0ZXJcIiwgb3JpZ2luKTtcclxuICB1cmwuc2VhcmNoUGFyYW1zLnNldChcImludml0ZV9jb2RlXCIsIHNlc3Npb24uaW52aXRlQ29kZSk7XHJcbiAgcmV0dXJuIHVybC50b1N0cmluZygpO1xyXG59XHJcblxyXG5mdW5jdGlvbiBnZXRNb2NrSW52aXRlSW5mbygpOiBINUludml0ZUluZm8ge1xyXG4gIGNvbnN0IGxpbmsgPSBnZXRNb2NrSW52aXRlTGluaygpO1xyXG4gIHJldHVybiB7XHJcbiAgICBpbnZpdGVMaW5rOiBsaW5rLFxyXG4gICAgaW52aXRlZENvdW50OiA4LFxyXG4gICAgZWFybmVkQW1vdW50OiAzMSxcclxuICAgIG1heEludml0ZXM6IDIwLFxyXG4gICAgcmVtYWluaW5nSW52aXRlczogMTIsXHJcbiAgfTtcclxufVxyXG5cclxuZnVuY3Rpb24gZ2V0TW9ja0ludml0ZVJlY29yZHMoKTogSDVJbnZpdGVSZWNvcmRbXSB7XHJcbiAgcmV0dXJuIFtcclxuICAgIHsgaWQ6IFwiaW52MVwiLCB1c2VySWRNYXNrZWQ6IFwiVSoqKio5MVwiLCB0eXBlOiBcInJlZ2lzdHJhdGlvblwiLCBjcmVhdGVkQXQ6IFwiMjAyNi0wNi0xMFQwOToxNjowMC4wMDBaXCIsIHJld2FyZEFtb3VudDogMiB9LFxyXG4gICAgeyBpZDogXCJpbnYyXCIsIHVzZXJJZE1hc2tlZDogXCJVKioqKjUyXCIsIHR5cGU6IFwicmVnaXN0cmF0aW9uX3JlY2hhcmdlXCIsIGNyZWF0ZWRBdDogXCIyMDI2LTA2LTA4VDEwOjQyOjAwLjAwMFpcIiwgcmV3YXJkQW1vdW50OiA1IH0sXHJcbiAgICB7IGlkOiBcImludjNcIiwgdXNlcklkTWFza2VkOiBcIlUqKioqNzNcIiwgdHlwZTogXCJyZWdpc3RyYXRpb25cIiwgY3JlYXRlZEF0OiBcIjIwMjYtMDYtMDVUMTI6MDg6MDAuMDAwWlwiLCByZXdhcmRBbW91bnQ6IDIgfSxcclxuICAgIHsgaWQ6IFwiaW52NFwiLCB1c2VySWRNYXNrZWQ6IFwiVSoqKiozNFwiLCB0eXBlOiBcInJlZ2lzdHJhdGlvblwiLCBjcmVhdGVkQXQ6IFwiMjAyNi0wNi0wM1QxNDozMDowMC4wMDBaXCIsIHJld2FyZEFtb3VudDogMiB9LFxyXG4gICAgeyBpZDogXCJpbnY1XCIsIHVzZXJJZE1hc2tlZDogXCJVKioqKjI1XCIsIHR5cGU6IFwicmVnaXN0cmF0aW9uX3JlY2hhcmdlXCIsIGNyZWF0ZWRBdDogXCIyMDI2LTA2LTAxVDA4OjAwOjAwLjAwMFpcIiwgcmV3YXJkQW1vdW50OiA1IH0sXHJcbiAgXTtcclxufVxyXG5cclxuLy8g4pSA4pSAIEV4cG9ydGVkIEFQSSBGdW5jdGlvbnMg4pSA4pSAXHJcblxyXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gZ2V0U2lnbkluU3RhdHVzQXBpKCk6IFByb21pc2U8SDVTaWduSW5TdGF0dXM+IHtcclxuICBpZiAoYXBpTW9kZSA9PT0gJ3JlYWwnKSB7XHJcbiAgICBjb25zdCByZXMgPSBhd2FpdCBoNUFwaS5nZXQoJy9hcGkvaDUvc2lnbi1pbi9zdGF0dXMnKTtcclxuICAgIHJldHVybiByZXMuZGF0YTtcclxuICB9XHJcbiAgcmV0dXJuIGdldE1vY2tTaWduSW5TdGF0dXMoKTtcclxufVxyXG5cclxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIHBlcmZvcm1TaWduSW5BcGkoKTogUHJvbWlzZTxINVNpZ25JblN0YXR1cz4ge1xyXG4gIGlmIChhcGlNb2RlID09PSAncmVhbCcpIHtcclxuICAgIGNvbnN0IHJlcyA9IGF3YWl0IGg1QXBpLnBvc3QoJy9hcGkvaDUvc2lnbi1pbicpO1xyXG4gICAgcmV0dXJuIHJlcy5kYXRhO1xyXG4gIH1cclxuICBjb25zdCBzZXNzaW9uID0gZ2V0UmVxdWlyZWRTZXNzaW9uKCk7XHJcbiAgY29uc3Qgc3RhdGUgPSB1cGRhdGVTdGF0ZUZvckFjY291bnQoc2Vzc2lvbi5hY2NvdW50SWQsIChkcmFmdCkgPT4ge1xyXG4gICAgaWYgKGRyYWZ0LmNoZWNrZWRJbkRhdGUgPT09IHRvZGF5S2V5KCkpIHtcclxuICAgICAgdGhyb3cgY3JlYXRlU2VydmljZUVycm9yKFwiYWxyZWFkeUNoZWNrZWRJblwiKTtcclxuICAgIH1cclxuICAgIGRyYWZ0LmNoZWNrZWRJbkRhdGUgPSB0b2RheUtleSgpO1xyXG4gICAgYXBwZW5kTG9jYWxpemVkTWVzc2FnZShkcmFmdCwgXCJzeXN0ZW1cIiwgXCJjaGVja2luVGl0bGVcIiwgXCJjaGVja2luQm9keVwiKTtcclxuICAgIHJldHVybiBkcmFmdDtcclxuICB9KTtcclxuICByZXR1cm4ge1xyXG4gICAgY29uc2VjdXRpdmVEYXlzOiA1LFxyXG4gICAgdG9kYXlTaWduZWRJbjogdHJ1ZSxcclxuICAgIGdvYWxEYXlzOiBTSUdOX0lOX0dPQUxfREFZUyxcclxuICAgIGdvYWxSZXdhcmQ6IFNJR05fSU5fR09BTF9SRVdBUkQsXHJcbiAgICBpc0NvbXBsZXRlZDogZmFsc2UsXHJcbiAgfTtcclxufVxyXG5cclxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGdldFRhc2tJbnN0YW5jZXNBcGkoKTogUHJvbWlzZTxINVRhc2tJbnN0YW5jZVtdPiB7XHJcbiAgaWYgKGFwaU1vZGUgPT09ICdyZWFsJykge1xyXG4gICAgY29uc3QgcmVzID0gYXdhaXQgaDVBcGkuZ2V0KCcvYXBpL2g1L3Rhc2staW5zdGFuY2VzJywgeyBwYXJhbXM6IHsgdXNlcl9pZDogJ21lJyB9IH0pO1xyXG4gICAgcmV0dXJuIHJlcy5kYXRhO1xyXG4gIH1cclxuICByZXR1cm4gZ2V0TW9ja1Rhc2tJbnN0YW5jZXMoKTtcclxufVxyXG5cclxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGdldFRhc2tJbnN0YW5jZURldGFpbEFwaShpZDogc3RyaW5nKTogUHJvbWlzZTxINVRhc2tJbnN0YW5jZSB8IG51bGw+IHtcclxuICBpZiAoYXBpTW9kZSA9PT0gJ3JlYWwnKSB7XHJcbiAgICBjb25zdCByZXMgPSBhd2FpdCBoNUFwaS5nZXQoYC9hcGkvaDUvdGFzay1pbnN0YW5jZXMvJHtlbmNvZGVVUklDb21wb25lbnQoaWQpfWApO1xyXG4gICAgcmV0dXJuIHJlcy5kYXRhO1xyXG4gIH1cclxuICByZXR1cm4gZ2V0TW9ja1Rhc2tJbnN0YW5jZURldGFpbChpZCk7XHJcbn1cclxuXHJcbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBzdGFydFByb2R1Y3RBcGkoaW5zdGFuY2VJZDogc3RyaW5nLCBwcm9kdWN0SWQ6IHN0cmluZyk6IFByb21pc2U8eyBzdWNjZXNzOiBib29sZWFuOyByZWFzb24/OiBzdHJpbmcgfT4ge1xyXG4gIGlmIChhcGlNb2RlID09PSAncmVhbCcpIHtcclxuICAgIGNvbnN0IHJlcyA9IGF3YWl0IGg1QXBpLnBvc3QoYC9hcGkvaDUvdGFzay1pbnN0YW5jZXMvJHtlbmNvZGVVUklDb21wb25lbnQoaW5zdGFuY2VJZCl9L3N0YXJ0LXByb2R1Y3RgLCB7IHByb2R1Y3RfaWQ6IHByb2R1Y3RJZCB9KTtcclxuICAgIHJldHVybiByZXMuZGF0YTtcclxuICB9XHJcbiAgLy8gTW9jazogZGVkdWN0IGJhbGFuY2UgYW5kIG1hcmsgcHJvZHVjdCBhcyBjb21wbGV0ZWRcclxuICBjb25zdCBzZXNzaW9uID0gZ2V0UmVxdWlyZWRTZXNzaW9uKCk7XHJcbiAgdXBkYXRlU3RhdGVGb3JBY2NvdW50KHNlc3Npb24uYWNjb3VudElkLCAoZHJhZnQpID0+IHtcclxuICAgIGNvbnN0IHBrZyA9IGRyYWZ0LnRhc2tQYWNrYWdlcy5maW5kKHAgPT4gcC5pZCA9PT0gaW5zdGFuY2VJZCk7XHJcbiAgICBpZiAoIXBrZykgcmV0dXJuIGRyYWZ0O1xyXG4gICAgY29uc3QgaXRlbSA9IHBrZy5pdGVtcy5maW5kKGkgPT4gaS5pZCA9PT0gcHJvZHVjdElkKTtcclxuICAgIGlmICghaXRlbSkgcmV0dXJuIGRyYWZ0O1xyXG4gICAgaWYgKGRyYWZ0LndhbGxldC5zeXN0ZW1CYWxhbmNlIDwgaXRlbS5wcmljZSkge1xyXG4gICAgICB0aHJvdyBjcmVhdGVTZXJ2aWNlRXJyb3IoXCJiYWxhbmNlSW5zdWZmaWNpZW50XCIpO1xyXG4gICAgfVxyXG4gICAgZHJhZnQud2FsbGV0LnN5c3RlbUJhbGFuY2UgLT0gaXRlbS5wcmljZTtcclxuICAgIGl0ZW0uY29tcGxldGVkX2F0ID0gbmV3IERhdGUoKS50b0lTT1N0cmluZygpO1xyXG4gICAgcmV0dXJuIGRyYWZ0O1xyXG4gIH0pO1xyXG4gIHJldHVybiB7IHN1Y2Nlc3M6IHRydWUgfTtcclxufVxyXG5cclxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIHJldHJ5UHJvZHVjdEFwaShpbnN0YW5jZUlkOiBzdHJpbmcsIHByb2R1Y3RJZDogc3RyaW5nKTogUHJvbWlzZTx7IHN1Y2Nlc3M6IGJvb2xlYW47IHJlYXNvbj86IHN0cmluZyB9PiB7XHJcbiAgaWYgKGFwaU1vZGUgPT09ICdyZWFsJykge1xyXG4gICAgY29uc3QgcmVzID0gYXdhaXQgaDVBcGkucG9zdChgL2FwaS9oNS90YXNrLWluc3RhbmNlcy8ke2VuY29kZVVSSUNvbXBvbmVudChpbnN0YW5jZUlkKX0vcmV0cnktcHJvZHVjdGAsIHsgcHJvZHVjdF9pZDogcHJvZHVjdElkIH0pO1xyXG4gICAgcmV0dXJuIHJlcy5kYXRhO1xyXG4gIH1cclxuICByZXR1cm4gc3RhcnRQcm9kdWN0QXBpKGluc3RhbmNlSWQsIHByb2R1Y3RJZCk7XHJcbn1cclxuXHJcbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBnZXRJbnZpdGVJbmZvQXBpKCk6IFByb21pc2U8SDVJbnZpdGVJbmZvPiB7XHJcbiAgaWYgKGFwaU1vZGUgPT09ICdyZWFsJykge1xyXG4gICAgY29uc3QgcmVzID0gYXdhaXQgaDVBcGkuZ2V0KCcvYXBpL2g1L2ludml0ZXMvbXktbGluaycpO1xyXG4gICAgcmV0dXJuIHJlcy5kYXRhO1xyXG4gIH1cclxuICByZXR1cm4gZ2V0TW9ja0ludml0ZUluZm8oKTtcclxufVxyXG5cclxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGdldEludml0ZVJlY29yZHNBcGkoKTogUHJvbWlzZTxINUludml0ZVJlY29yZFtdPiB7XHJcbiAgaWYgKGFwaU1vZGUgPT09ICdyZWFsJykge1xyXG4gICAgY29uc3QgcmVzID0gYXdhaXQgaDVBcGkuZ2V0KCcvYXBpL2g1L2ludml0ZXMvbXktcmVjb3JkcycpO1xyXG4gICAgcmV0dXJuIHJlcy5kYXRhO1xyXG4gIH1cclxuICByZXR1cm4gZ2V0TW9ja0ludml0ZVJlY29yZHMoKTtcclxufVxyXG5cclxuLy8g4pSA4pSAIFJlcXVlc3QgZGVkdXBsaWNhdGlvbiB1dGlsaXR5IOKUgOKUgFxyXG5jb25zdCByZXF1ZXN0Q2FjaGUgPSBuZXcgTWFwPHN0cmluZywgeyBwcm9taXNlOiBQcm9taXNlPHVua25vd24+OyB0aW1lc3RhbXA6IG51bWJlciB9PigpO1xyXG5jb25zdCBSRVFVRVNUX0RFRFVQX1RUTCA9IDUwMDA7IC8vIDUgc2Vjb25kc1xyXG5cclxuYXN5bmMgZnVuY3Rpb24gZGVkdXBSZXF1ZXN0PFQ+KGtleTogc3RyaW5nLCBmZXRjaGVyOiAoKSA9PiBQcm9taXNlPFQ+KTogUHJvbWlzZTxUPiB7XHJcbiAgY29uc3QgY2FjaGVkID0gcmVxdWVzdENhY2hlLmdldChrZXkpO1xyXG4gIGlmIChjYWNoZWQgJiYgRGF0ZS5ub3coKSAtIGNhY2hlZC50aW1lc3RhbXAgPCBSRVFVRVNUX0RFRFVQX1RUTCkge1xyXG4gICAgcmV0dXJuIGNhY2hlZC5wcm9taXNlIGFzIFByb21pc2U8VD47XHJcbiAgfVxyXG4gIGNvbnN0IHByb21pc2UgPSBmZXRjaGVyKCk7XHJcbiAgcmVxdWVzdENhY2hlLnNldChrZXksIHsgcHJvbWlzZSwgdGltZXN0YW1wOiBEYXRlLm5vdygpIH0pO1xyXG4gIHByb21pc2UuZmluYWxseSgoKSA9PiB7XHJcbiAgICAvLyBDbGVhbiB1cCBhZnRlciBUVExcclxuICAgIHNldFRpbWVvdXQoKCkgPT4ge1xyXG4gICAgICBpZiAocmVxdWVzdENhY2hlLmdldChrZXkpPy5wcm9taXNlID09PSBwcm9taXNlKSB7XHJcbiAgICAgICAgcmVxdWVzdENhY2hlLmRlbGV0ZShrZXkpO1xyXG4gICAgICB9XHJcbiAgICB9LCBSRVFVRVNUX0RFRFVQX1RUTCk7XHJcbiAgfSk7XHJcbiAgcmV0dXJuIHByb21pc2U7XHJcbn1cclxu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