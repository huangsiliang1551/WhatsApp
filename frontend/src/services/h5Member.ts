import axios, { AxiosError, AxiosResponse, InternalAxiosRequestConfig } from "axios";
import { t } from "../pages/h5-member/i18n";
import { sessionManager } from "./h5SessionManager";

type JsonObject = Record<string, unknown>;
export type H5TaskPackageStatus = "pending_claim" | "active" | "completed" | "expired";
export type H5TaskPackageType = "rookie" | "growth" | "promotion";
export type H5PromotionMetric = "invited_registrations" | "recharged_invitees";
export type H5WithdrawStatus = "submitted" | "reviewing" | "approved" | "rejected" | "paid";
export type H5RewardShippingStatus =
  | "pending_address"
  | "submitted"
  | "packing"
  | "shipped"
  | "delivered"
  | "completed";
export type H5WalletTransactionType =
  | "recharge"
  | "bonus_grant"
  | "purchase"
  | "recharge_repair"
  | "task_reward"
  | "task_to_system_transfer"
  | "withdraw_reject_refund"
  | "withdraw_request"
  | "withdraw_paid"
  | "withdraw_rejected";
export type H5MessageCategory = "task" | "wallet" | "order" | "support" | "fragment" | "system";

export type H5SiteBrand = {
  site_key: string;
  brand_name: string;
  tagline: string;
  accent_color: string;
  default_language?: string;
};

export type H5MemberSession = {
  accountId: string;
  phone: string;
  publicUserId: string;
  displayName: string;
  inviteCode: string;
  avatarUrl?: string | null;
  languageCode?: string;
};

export type H5MemberProfile = H5MemberSession & {
  accountIdMasked: string;
  createdAt: string;
};

export type H5TaskPackageItem = {
  id: string;
  product_name: string;
  image_url: string;
  price: number;
  currency: string;
  completed_at: string | null;
  order_id: string | null;
};

export type H5PromotionProgress = {
  metric: H5PromotionMetric;
  current: number;
  target: number;
  inviteCode: string;
};

export type H5TaskPackage = {
  id: string;
  title: string;
  description: string;
  type: H5TaskPackageType;
  status: H5TaskPackageStatus;
  rewardRatio: number;
  claimedAt: string | null;
  expiresAt: string | null;
  dispatchedAt: string;
  completionWindowHours: number;
  items: H5TaskPackageItem[];
  promotion: H5PromotionProgress | null;
  taskBalanceAwardedAt: string | null;
};

export type H5MemberOrder = {
  id: string;
  orderNo: string;
  packageId: string;
  packageTitle: string;
  productName: string;
  amount: number;
  currency: string;
  status: "paid" | "failed" | "processing" | "pending";
  createdAt: string;
  sourceLabel: string;
};

export type H5WalletTransaction = {
  id: string;
  ledgerType: "system" | "task";
  transactionType: H5WalletTransactionType;
  direction: "credit" | "debit";
  amount: number;
  currency: string;
  status: "submitted" | "processing" | "paid" | "failed";
  note: string;
  displayCategory?: string;
  displayTitle?: string;
  createdAt: string;
};

export type H5WalletSummary = {
  systemBalance: number;
  taskBalance: number;
  currency: string;
  withdrawThreshold: number;
  canWithdraw: boolean;
  shortfallAmount: number;
};

export type H5WithdrawRequest = {
  id: string;
  amount: number;
  cashAmount: number;
  bonusAmount: number;
  actualPayoutAmount: number | null;
  currency: string;
  status: H5WithdrawStatus;
  rejectionReason: string | null;
  createdAt: string;
};

export type H5LeaderboardEntry = {
  rank: number;
  accountIdMasked: string;
  amount: number;
  currency: string;
};

export type H5MessageItem = {
  id: string;
  category: H5MessageCategory;
  title: string;
  body: string;
  createdAt: string;
  isRead: boolean;
};

export type H5FragmentDefinition = {
  id: string;
  name: string;
  rarity: "common" | "rare" | "epic";
  color: string;
};

export type H5FragmentInventoryItem = H5FragmentDefinition & {
  owned: number;
  required: number;
};

export type H5FragmentDropLog = {
  id: string;
  fragmentId: string;
  fragmentName: string;
  source: "checkin" | "task";
  createdAt: string;
};

export type H5ShippingAddress = {
  receiver: string;
  phone: string;
  country: string;
  province: string;
  city: string;
  addressLine: string;
};

export type H5RewardShippingOrder = {
  id: string;
  rewardName: string;
  status: H5RewardShippingStatus;
  createdAt: string;
  address: H5ShippingAddress | null;
};

export type H5FragmentOverview = {
  inventory: H5FragmentInventoryItem[];
  dropLogs: H5FragmentDropLog[];
  rewardName: string;
  shippingOrders: H5RewardShippingOrder[];
};

export type H5HomeFragmentSummary = {
  rewardName: string | null;
  completedCount: number;
  totalCount: number;
  missingCount: number;
  canExchange: boolean;
  shippingOrderCount: number;
  latestShippingStatus: H5RewardShippingStatus | null;
};

export type H5HomeVerificationSummary = {
  currentStatus: string;
  hasActiveRequest: boolean;
};

export type H5MemberVerificationDocument = {
  id: string;
  fileName: string;
  mimeType: string | null;
  storageKey: string | null;
  metadataJson: JsonObject | null;
  createdAt: string;
};

export type H5MemberVerificationRequest = {
  id: string;
  requestType: string;
  status: string;
  notes: string | null;
  reviewNote: string | null;
  reviewerActorId: string | null;
  reviewedAt: string | null;
  createdAt: string;
  updatedAt: string;
  documents: H5MemberVerificationDocument[];
};

export type H5MemberVerificationSummary = {
  currentStatus: string;
  hasActiveRequest: boolean;
  activeRequest: H5MemberVerificationRequest | null;
  history: H5MemberVerificationRequest[];
};

export type H5MemberVerificationDocumentInput = {
  fileName: string;
  mimeType?: string | null;
  storageKey?: string | null;
  metadataJson?: JsonObject | null;
};

export type H5MemberVerificationCreateInput = {
  requestType?: string;
  notes?: string | null;
  documents?: H5MemberVerificationDocumentInput[];
};

export type H5WhatsAppBinding = {
  isBound: boolean;
  bindingStatus?: string;
  requestId?: string | null;
  phoneNumber: string | null;
  requestedAt?: string | null;
  startCount?: number;
  lastUpdatedAt: string | null;
};

export type H5HomeDashboard = {
  site: H5SiteBrand;
  member: H5MemberProfile;
  wallet: H5WalletSummary;
  unreadCount: number;
  pendingClaimCount: number;
  activeCount: number;
  expiringCount: number;
  recentMessages: H5MessageItem[];
  leaderboard: H5LeaderboardEntry[];
  verification: H5HomeVerificationSummary;
  fragments: H5HomeFragmentSummary;
};

type StoredMemberAccount = {
  id: string;
  accountId: string;
  phone: string;
  password: string;
  publicUserId: string;
  displayName: string;
  inviteCode: string;
  createdAt: string;
  avatarUrl?: string | null;
};

type StoredMemberState = {
  wallet: {
    systemBalance: number;
    taskBalance: number;
    currency: string;
    withdrawThreshold: number;
  };
  taskPackages: H5TaskPackage[];
  orders: H5MemberOrder[];
  transactions: H5WalletTransaction[];
  withdrawRequests: H5WithdrawRequest[];
  messages: H5MessageItem[];
  fragmentInventory: Record<string, number>;
  fragmentDropLogs: H5FragmentDropLog[];
  shippingOrders: H5RewardShippingOrder[];
  checkedInDate: string | null;
  verificationRequests: H5MemberVerificationRequest[];
  whatsappBinding: H5WhatsAppBinding;
};

const MEMBER_ACCOUNTS_KEY = "frontend.h5.member-accounts.v1";
const MEMBER_STATES_KEY = "frontend.h5.member-states.v1";
const MEMBER_SESSION_KEY = "frontend.h5.member-session.v1";
const DEFAULT_MEMBER_PHONE = "13800000000";
const DEFAULT_MEMBER_PASSWORD = "demo123456";
const ACCOUNT_ID_LENGTH = 8;
const DEFAULT_WITHDRAW_THRESHOLD = 100;

function getServiceErrorMessage(key: string): string {
  return t(`serviceErrors.${key}`);
}

function getServiceMessage(
  key: string,
  params?: Record<string, string | number>,
): string {
  return t(`serviceMessages.${key}`, params);
}

function getSeedDataText(
  key: string,
  params?: Record<string, string | number>,
): string {
  return t(`seedData.${key}`, params);
}

function createServiceError(key: string): Error {
  return new Error(getServiceErrorMessage(key));
}

function getAuthRequiredMessage(): string {
  return getServiceErrorMessage("authRequired");
}

type BackendMemberAuthResponse = {
  member: {
    accountId: string;
    accountIdMasked?: string | null;
    createdAt: string;
    displayName?: string | null;
    inviteCode?: string | null;
    languageCode?: string | null;
    language_code?: string | null;
    memberNo?: string | null;
    phone: string;
    publicUserId: string;
  };
  site: {
    siteKey: string;
    brandName: string;
    defaultLanguage?: string | null;
    default_language?: string | null;
  };
};

type BackendMemberHomeResponse = {
  member: {
    accountId: string;
    accountIdMasked?: string | null;
    createdAt: string;
    displayName?: string | null;
    inviteCode?: string | null;
    languageCode?: string | null;
    language_code?: string | null;
    memberNo?: string | null;
    phone: string;
    publicUserId: string;
  };
  site: {
    siteKey: string;
    brandName: string;
    defaultLanguage?: string | null;
    default_language?: string | null;
  };
  wallet: {
    systemBalance: number | null;
    taskBalance: number | null;
    currency: string | null;
  };
  unreadMessageCount: number;
  pendingClaimCount: number;
  activeCount: number;
  expiringCount: number;
  recentMessages: Array<{
    id: string;
    category: H5MessageCategory;
    title: string;
    bodyText: string;
    isRead: boolean;
    createdAt: string;
  }>;
  leaderboard: Array<{
    rank: number;
    accountIdMasked: string;
    amount: number;
    currency: string;
  }>;
  verification?: {
    currentStatus: string;
    hasActiveRequest: boolean;
  };
  fragments?: {
    rewardName: string | null;
    completedCount: number;
    totalCount: number;
    missingCount: number;
    canExchange: boolean;
    shippingOrderCount: number;
    latestShippingStatus: H5RewardShippingStatus | null;
  };
};

type BackendMemberVerificationDocumentResponse = {
  id: string;
  fileName?: string;
  file_name?: string;
  mimeType?: string | null;
  mime_type?: string | null;
  storageKey?: string | null;
  storage_key?: string | null;
  metadataJson?: JsonObject | null;
  metadata_json?: JsonObject | null;
  createdAt?: string;
  created_at?: string;
};

type BackendMemberVerificationRequestResponse = {
  id: string;
  requestType?: string;
  request_type?: string;
  status: string;
  notes: string | null;
  reviewNote?: string | null;
  review_note?: string | null;
  reviewerActorId?: string | null;
  reviewer_actor_id?: string | null;
  reviewedAt?: string | null;
  reviewed_at?: string | null;
  createdAt?: string;
  created_at?: string;
  updatedAt?: string;
  updated_at?: string;
  documents: BackendMemberVerificationDocumentResponse[];
};

type BackendMemberVerificationSummaryResponse = {
  currentStatus?: string;
  current_status?: string;
  hasActiveRequest?: boolean;
  has_active_request?: boolean;
  activeRequest?: BackendMemberVerificationRequestResponse | null;
  active_request?: BackendMemberVerificationRequestResponse | null;
  history: BackendMemberVerificationRequestResponse[];
};

type BackendTaskPackageItemResponse = {
  id: string;
  productName: string;
  imageUrl?: string | null;
  price: number;
  currency: string;
  completedAt: string | null;
  orderId: string | null;
};

type BackendTaskPackagePromotionResponse = {
  metric: H5PromotionMetric;
  current: number;
  target: number;
  inviteCode?: string | null;
};

type BackendTaskPackageResponse = {
  id: string;
  title: string;
  description: string | null;
  type: H5TaskPackageType;
  status: H5TaskPackageStatus;
  rewardRatio: number;
  claimedAt: string | null;
  expiresAt: string | null;
  dispatchedAt: string;
  completionWindowHours: number;
  items: BackendTaskPackageItemResponse[];
  promotion: BackendTaskPackagePromotionResponse | null;
  taskBalanceAwardedAt: string | null;
  totalCommission: number;
  currentCommission: number;
  completedItems: number;
  totalItems: number;
  countdownSeconds: number;
};

type BackendWalletSummaryResponse = {
  systemBalance: number;
  taskBalance: number;
  currency: string;
  withdrawThreshold: number;
  canWithdraw: boolean;
  shortfallAmount: number;
};

type BackendWalletTransactionResponse = {
  id: string;
  ledgerType: "system" | "task";
  transactionType: H5WalletTransactionType;
  direction: "credit" | "debit";
  amount: number;
  currency: string;
  status: "submitted" | "processing" | "paid" | "failed";
  note: string | null;
  displayCategory?: string | null;
  displayTitle?: string | null;
  createdAt: string;
};

type BackendMemberOrderResponse = {
  id: string;
  orderNo: string;
  packageId: string | null;
  packageTitle: string | null;
  productName: string;
  amount: number;
  currency: string;
  status: "paid" | "failed" | "processing";
  createdAt: string;
  sourceLabel: string | null;
};

type BackendWithdrawalResponse = {
  id: string;
  requestNo: string;
  amount: number;
  cashAmount: number;
  bonusAmount: number;
  actualPayoutAmount: number | null;
  currency: string;
  status: H5WithdrawStatus;
  rejectionReason: string | null;
  createdAt: string;
  reviewedAt: string | null;
  paidAt: string | null;
  history: Array<Record<string, unknown>>;
};

type BackendWithdrawLeaderboardResponse = {
  rank: number;
  accountIdMasked: string;
  amount: number;
  currency: string;
};

type BackendMemberMessageResponse = {
  id: string;
  category: H5MessageCategory;
  title: string;
  bodyText: string;
  isRead: boolean;
  readAt: string | null;
  createdAt: string;
};

type BackendFragmentInventoryItemResponse = {
  id: string;
  fragmentKey: string;
  name: string;
  rarity: "common" | "rare" | "epic";
  color: string;
  owned: number;
  required: number;
};

type BackendFragmentDropLogResponse = {
  id: string;
  fragmentId: string;
  fragmentKey: string;
  fragmentName: string;
  source: "checkin" | "task";
  createdAt: string;
};

type BackendRewardShippingAddressResponse = {
  receiver: string;
  phone: string;
  country: string;
  province: string;
  city: string;
  addressLine: string;
};

type BackendRewardShippingOrderResponse = {
  id: string;
  rewardName: string;
  status: H5RewardShippingStatus;
  createdAt: string;
  address: BackendRewardShippingAddressResponse | null;
};

type BackendFragmentOverviewResponse = {
  inventory: BackendFragmentInventoryItemResponse[];
  dropLogs: BackendFragmentDropLogResponse[];
  rewardName: string;
  shippingOrders: BackendRewardShippingOrderResponse[];
};

type BackendTaskPackagePurchaseResponse = {
  success: boolean;
  order: BackendMemberOrderResponse | null;
  taskPackage: BackendTaskPackageResponse;
  wallet: BackendWalletSummaryResponse;
  fragmentDrop: BackendFragmentDropLogResponse | null;
  reason: string | null;
};

type BackendWhatsAppBindingResponse = {
  isBound: boolean;
  bindingStatus?: string | null;
  requestId?: string | null;
  phoneNumber: string | null;
  requestedAt?: string | null;
  startCount?: number | null;
  lastUpdatedAt: string | null;
};

class ApiRequestError extends Error {
  status: number;

  constructor(status: number, detail: string) {
    super(
      detail || getServiceErrorMessage("requestFailedStatus").replace("{{status}}", String(status)),
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

export function isH5AuthRequiredError(error: unknown): boolean {
  return error instanceof H5AuthRequiredError;
}

// ─── H5 Axios 实例（带自动鉴权 & 刷新拦截器）─────────────

export function resolveH5ApiBaseUrl(
  envApiBaseUrl: string | undefined,
  isDev: boolean,
): string {
  const trimmed = envApiBaseUrl?.trim();
  if (trimmed) {
    return trimmed;
  }
  // Keep H5 on same-origin requests by default so local-device and LAN-device
  // browsers both go through the Vite proxy instead of their own localhost.
  void isDev;
  return "";
}

const resolvedApiBaseUrl = resolveH5ApiBaseUrl(
  import.meta.env.VITE_API_BASE_URL as string | undefined,
  import.meta.env.DEV,
);

export const h5Api = axios.create({
  baseURL: resolvedApiBaseUrl,
  timeout: 10000,
  withCredentials: true,
});

/** 是否正在刷新 token */
let _isRefreshing = false;

/** 等待 token 刷新期间积压的请求回调 */
let _pendingQueue: Array<(token: string | null) => void> = [];

// ── Request 拦截器 ──────────────────────────────────────

h5Api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    // Token 即将过期时异步续期（不阻塞当前请求）
    if (sessionManager.shouldRefresh()) {
      sessionManager.refreshToken().catch(() => {
        // 续期失败已在 sessionManager 中处理
      });
    }

    // 附加 Authorization header
    const authHeaders = sessionManager.authHeader();
    if (authHeaders.Authorization) {
      config.headers.Authorization = authHeaders.Authorization;
    }

    return config;
  },
  (error) => Promise.reject(error),
);

// ── Response 拦截器 ─────────────────────────────────────

h5Api.interceptors.response.use(
  (response: AxiosResponse) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & {
      _retry?: boolean;
      _retry5xx?: boolean;
    };

    // 必须要有 config，否则无法重试
    if (!originalRequest) return Promise.reject(error);

    // 1) 网络错误（无响应）→ Toast 提示
    if (!error.response) {
      const message = getServiceErrorMessage("networkFailed");
      if (typeof window !== "undefined") {
        window.alert(message);
      }
      return Promise.reject(error);
    }

    const { status } = error.response;

    // 2) 401 → 自动续期（单队列）
    if (status === 401 && !originalRequest._retry) {
      if (_isRefreshing) {
        // 已有刷新在进行中，将当前请求加入队列等待
        return new Promise<AxiosResponse>((resolve, reject) => {
          _pendingQueue.push((token: string | null) => {
            if (token) {
              originalRequest.headers.Authorization = `Bearer ${token}`;
              resolve(h5Api(originalRequest));
            } else {
              reject(error);
            }
          });
        });
      }

      // 首个 401，启动刷新
      originalRequest._retry = true;
      _isRefreshing = true;

      try {
        const success = await sessionManager.refreshToken();
        if (success) {
          const newToken = sessionManager.getAccessToken();
          // 处理队列中的等待请求
          _pendingQueue.forEach((cb) => cb(newToken));
          _pendingQueue = [];
          // 重试当前请求
          originalRequest.headers.Authorization = `Bearer ${newToken}`;
          return h5Api(originalRequest);
        } else {
          // 刷新失败 → 拒绝所有排队请求
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

    // 3) 5xx → GET 请求自动重试一次（2s 延迟）
    if (
      status >= 500 &&
      status < 600 &&
      originalRequest.method?.toUpperCase() === "GET" &&
      !originalRequest._retry5xx
    ) {
      originalRequest._retry5xx = true;
      await new Promise((resolve) => setTimeout(resolve, 2000));
      return h5Api(originalRequest);
    }

    return Promise.reject(error);
  },
);

// ─── API Mode (mock/real switch) ──────────────────────────

type ApiMode = 'mock' | 'real';
const apiMode: ApiMode = (import.meta.env.VITE_API_MODE as string) === 'real' ? 'real' : 'mock';

/** Auth API 响应类型 */
export type H5LoginResponse = {
  access_token: string;
  refresh_token: string;
  expires_in: number;
  user: H5MemberSession;
};


function isBrowser(): boolean {
  return typeof window !== "undefined" && typeof window.localStorage !== "undefined";
}

function nowIso(): string {
  return new Date().toISOString();
}

function readStorage<T>(key: string, fallback: T): T {
  if (!isBrowser()) {
    return fallback;
  }
  const raw = window.localStorage.getItem(key);
  if (!raw) {
    return fallback;
  }
  try {
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

function writeStorage<T>(key: string, value: T): void {
  if (!isBrowser()) {
    return;
  }
  window.localStorage.setItem(key, JSON.stringify(value));
}

async function requestJson<T>(input: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);
  try {
    const response = await fetch(input, {
      credentials: "include",
      signal: controller.signal,
      ...init,
    });
    if (!response.ok) {
      const rawText = await response.text();
      let detail = rawText;
      if (rawText) {
        try {
          const parsed = JSON.parse(rawText) as { detail?: unknown };
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
    return (await response.json()) as T;
  } catch (error) {
    if ((error as DOMException)?.name === "AbortError") {
      throw createServiceError("requestTimeout");
    }
    throw error;
  } finally {
    clearTimeout(timeout);
  }
}

type BackendAuthLookupResult<T> = T | null | "unauthenticated";

function isLegacyFallbackEnabled(): boolean {
  const configured = import.meta.env.VITE_H5_MEMBER_LEGACY_FALLBACK;
  if (configured === "true") {
    return true;
  }
  if (configured === "false") {
    return false;
  }
  return import.meta.env.DEV;
}

function canUseLegacyFallback(error: unknown): boolean {
  if (!isLegacyFallbackEnabled()) {
    return false;
  }
  if (error instanceof TypeError || error instanceof SyntaxError) {
    return true;
  }
  return error instanceof ApiRequestError && error.status === 404;
}

function getBackendUnavailableError(): Error {
  return createServiceError("authServiceUnavailable");
}

function hasBackendAuthCookies(): boolean {
  if (typeof document === "undefined") {
    return false;
  }
  const cookie = document.cookie || "";
  return cookie.includes("h5_member_session=") || cookie.includes("h5_member_refresh=");
}

async function refreshBackendAuthSession(): Promise<boolean> {
  try {
    const response = await requestJson<BackendMemberAuthResponse>("/api/h5/auth/refresh", {
      method: "POST",
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

async function tryBackendAuthRequest<T>(
  request: () => Promise<T>,
  options?: {
    allowRefresh?: boolean;
  },
): Promise<BackendAuthLookupResult<T>> {
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

async function requestBackendMemberDomain<T>(
  input: string,
  init?: RequestInit,
): Promise<T | null> {
  const response = await tryBackendAuthRequest<T>(() => requestJson(input, init), {
    allowRefresh: true,
  });
  if (response === "unauthenticated") {
    writeSession(null);
    throw new H5AuthRequiredError();
  }
  return response;
}

function createId(prefix: string): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return `${prefix}-${crypto.randomUUID()}`;
  }
  return `${prefix}-${Math.random().toString(36).slice(2, 10)}`;
}

function randomDigits(length: number): string {
  let value = "";
  while (value.length < length) {
    value += Math.floor(Math.random() * 10).toString();
  }
  return value.slice(0, length);
}

function readMemberAccounts(): StoredMemberAccount[] {
  const seeded = seedMemberAccounts();
  const stored = readStorage<StoredMemberAccount[]>(MEMBER_ACCOUNTS_KEY, seeded);
  if (isBrowser() && !window.localStorage.getItem(MEMBER_ACCOUNTS_KEY)) {
    writeStorage(MEMBER_ACCOUNTS_KEY, stored);
  }
  return stored;
}

function writeMemberAccounts(accounts: StoredMemberAccount[]): void {
  writeStorage(MEMBER_ACCOUNTS_KEY, accounts);
}

function readMemberStates(): Record<string, StoredMemberState> {
  const seeded = seedMemberStates();
  const stored = readStorage<Record<string, StoredMemberState>>(MEMBER_STATES_KEY, seeded);
  if (isBrowser() && !window.localStorage.getItem(MEMBER_STATES_KEY)) {
    writeStorage(MEMBER_STATES_KEY, stored);
  }
  return stored;
}

function writeMemberStates(states: Record<string, StoredMemberState>): void {
  writeStorage(MEMBER_STATES_KEY, states);
}

function readSession(): H5MemberSession | null {
  return readStorage<H5MemberSession | null>(MEMBER_SESSION_KEY, null);
}

function writeSession(session: H5MemberSession | null): void {
  if (!isBrowser()) {
    return;
  }
  if (session === null) {
    window.localStorage.removeItem(MEMBER_SESSION_KEY);
    return;
  }
  writeStorage(MEMBER_SESSION_KEY, session);
}

function buildSessionFromAuthPayload(payload: BackendMemberAuthResponse): H5MemberSession {
  const memberNo = payload.member.memberNo?.trim() || payload.member.accountId;
  return {
    accountId: memberNo,
    phone: payload.member.phone,
    publicUserId: payload.member.publicUserId,
    displayName: payload.member.displayName?.trim() || payload.member.publicUserId,
    inviteCode: payload.member.inviteCode?.trim() || generateInviteCode(memberNo),
    avatarUrl: null,
    languageCode: payload.member.languageCode ?? payload.member.language_code ?? undefined,
  };
}

function buildProfileFromAuthPayload(payload: BackendMemberAuthResponse): H5MemberProfile {
  const session = buildSessionFromAuthPayload(payload);
  return {
    ...session,
    accountIdMasked: payload.member.accountIdMasked?.trim() || maskAccountId(session.accountId),
    createdAt: payload.member.createdAt,
  };
}

function syncLegacyMemberCacheFromProfile(profile: H5MemberProfile): void {
  ensureSeededStorage();
  const accounts = readMemberAccounts();
  const existing = accounts.find((item) => item.accountId === profile.accountId);
  const nextAccount: StoredMemberAccount = {
    id: existing?.id ?? createId("member"),
    accountId: profile.accountId,
    phone: profile.phone,
    password: existing?.password ?? DEFAULT_MEMBER_PASSWORD,
    publicUserId: profile.publicUserId,
    displayName: profile.displayName,
    inviteCode: profile.inviteCode,
    createdAt: profile.createdAt,
    avatarUrl: existing?.avatarUrl ?? profile.avatarUrl ?? null,
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
    avatarUrl: profile.avatarUrl ?? nextAccount.avatarUrl ?? null,
  });
}

function mapSiteBrandFromBackend(site: BackendMemberAuthResponse["site"]): H5SiteBrand {
  const base = getSiteBrand(site.siteKey);
  return {
    ...base,
    site_key: site.siteKey,
    brand_name: site.brandName,
    default_language: site.defaultLanguage ?? site.default_language ?? base.default_language,
  };
}

function mapTaskPackageItemFromBackend(
  item: BackendTaskPackageItemResponse,
): H5TaskPackageItem {
  return {
    id: item.id,
    product_name: item.productName,
    image_url: item.imageUrl ?? "",
    price: item.price,
    currency: item.currency,
    completed_at: item.completedAt,
    order_id: item.orderId,
  };
}

function mapTaskPackageFromBackend(
  pkg: BackendTaskPackageResponse,
): H5TaskPackage & {
  totalCommission: number;
  currentCommission: number;
  completedItems: number;
  totalItems: number;
  countdownSeconds: number;
} {
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
    promotion: pkg.promotion
      ? {
          metric: pkg.promotion.metric,
          current: pkg.promotion.current,
          target: pkg.promotion.target,
          inviteCode: pkg.promotion.inviteCode ?? "",
        }
      : null,
    taskBalanceAwardedAt: pkg.taskBalanceAwardedAt,
    totalCommission: pkg.totalCommission,
    currentCommission: pkg.currentCommission,
    completedItems: pkg.completedItems,
    totalItems: pkg.totalItems,
    countdownSeconds: pkg.countdownSeconds,
  };
}

function mapWalletSummaryFromBackend(
  wallet: BackendWalletSummaryResponse,
): H5WalletSummary {
  return {
    systemBalance: wallet.systemBalance,
    taskBalance: wallet.taskBalance,
    currency: wallet.currency,
    withdrawThreshold: wallet.withdrawThreshold,
    canWithdraw: wallet.canWithdraw,
    shortfallAmount: wallet.shortfallAmount,
  };
}

function mapOrderFromBackend(order: BackendMemberOrderResponse): H5MemberOrder {
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
    sourceLabel: order.sourceLabel ?? "",
  };
}

function mapWalletTransactionFromBackend(
  transaction: BackendWalletTransactionResponse,
): H5WalletTransaction {
  const displayTitle = transaction.displayTitle ?? transaction.note ?? "";
  return {
    id: transaction.id,
    ledgerType: transaction.ledgerType,
    transactionType: transaction.transactionType,
    direction: transaction.direction,
    amount: transaction.amount,
    currency: transaction.currency,
    status: transaction.status,
    note: displayTitle,
    displayCategory: transaction.displayCategory ?? undefined,
    displayTitle,
    createdAt: transaction.createdAt,
  };
}

function mapWithdrawalFromBackend(
  withdrawal: BackendWithdrawalResponse,
): H5WithdrawRequest {
  return {
    id: withdrawal.id,
    amount: withdrawal.amount,
    cashAmount: withdrawal.cashAmount,
    bonusAmount: withdrawal.bonusAmount,
    actualPayoutAmount: withdrawal.actualPayoutAmount,
    currency: withdrawal.currency,
    status: withdrawal.status,
    rejectionReason: withdrawal.rejectionReason,
    createdAt: withdrawal.createdAt,
  };
}

function mapLeaderboardEntryFromBackend(
  entry: BackendWithdrawLeaderboardResponse,
): H5LeaderboardEntry {
  return {
    rank: entry.rank,
    accountIdMasked: entry.accountIdMasked,
    amount: entry.amount,
    currency: entry.currency,
  };
}

function mapMessageFromBackend(message: BackendMemberMessageResponse): H5MessageItem {
  return {
    id: message.id,
    category: message.category,
    title: message.title,
    body: message.bodyText,
    createdAt: message.createdAt,
    isRead: message.isRead,
  };
}

function mapVerificationDocumentFromBackend(
  document: BackendMemberVerificationDocumentResponse,
): H5MemberVerificationDocument {
  return {
    id: document.id,
    fileName: document.fileName ?? document.file_name ?? "",
    mimeType: document.mimeType ?? document.mime_type ?? null,
    storageKey: document.storageKey ?? document.storage_key ?? null,
    metadataJson: document.metadataJson ?? document.metadata_json ?? null,
    createdAt: document.createdAt ?? document.created_at ?? nowIso(),
  };
}

function mapVerificationRequestFromBackend(
  request: BackendMemberVerificationRequestResponse,
): H5MemberVerificationRequest {
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
    documents: request.documents.map((item) => mapVerificationDocumentFromBackend(item)),
  };
}

function mapVerificationSummaryFromBackend(
  summary: BackendMemberVerificationSummaryResponse,
): H5MemberVerificationSummary {
  return {
    currentStatus: summary.currentStatus ?? summary.current_status ?? "not_submitted",
    hasActiveRequest: summary.hasActiveRequest ?? summary.has_active_request ?? false,
    activeRequest: (summary.activeRequest ?? summary.active_request)
      ? mapVerificationRequestFromBackend(summary.activeRequest ?? summary.active_request!)
      : null,
    history: summary.history.map((item) => mapVerificationRequestFromBackend(item)),
  };
}

function mapFragmentDropFromBackend(
  drop: BackendFragmentDropLogResponse,
): H5FragmentDropLog {
  return {
    id: drop.id,
    fragmentId: drop.fragmentId,
    fragmentName: drop.fragmentName,
    source: drop.source,
    createdAt: drop.createdAt,
  };
}

function mapShippingAddressFromBackend(
  address: BackendRewardShippingAddressResponse,
): H5ShippingAddress {
  return {
    receiver: address.receiver,
    phone: address.phone,
    country: address.country,
    province: address.province,
    city: address.city,
    addressLine: address.addressLine,
  };
}

function mapShippingOrderFromBackend(
  order: BackendRewardShippingOrderResponse,
): H5RewardShippingOrder {
  return {
    id: order.id,
    rewardName: order.rewardName,
    status: order.status,
    createdAt: order.createdAt,
    address: order.address ? mapShippingAddressFromBackend(order.address) : null,
  };
}

function mapFragmentOverviewFromBackend(
  overview: BackendFragmentOverviewResponse,
): H5FragmentOverview {
  return {
    inventory: overview.inventory.map((item) => ({
      id: item.id,
      name: item.name,
      rarity: item.rarity,
      color: item.color,
      owned: item.owned,
      required: item.required,
    })),
    dropLogs: overview.dropLogs.map((item) => mapFragmentDropFromBackend(item)),
    rewardName: overview.rewardName,
    shippingOrders: overview.shippingOrders.map((item) => mapShippingOrderFromBackend(item)),
  };
}

function getEmptyHomeFragmentSummary(): H5HomeFragmentSummary {
  return {
    rewardName: null,
    completedCount: 0,
    totalCount: 0,
    missingCount: 0,
    canExchange: false,
    shippingOrderCount: 0,
    latestShippingStatus: null,
  };
}

function getEmptyHomeVerificationSummary(): H5HomeVerificationSummary {
  return {
    currentStatus: "not_submitted",
    hasActiveRequest: false,
  };
}

function getEmptyVerificationSummary(): H5MemberVerificationSummary {
  return {
    ...getEmptyHomeVerificationSummary(),
    activeRequest: null,
    history: [],
  };
}

function mapHomeVerificationSummaryFromBackend(
  summary: BackendMemberHomeResponse["verification"],
): H5HomeVerificationSummary {
  if (!summary) {
    return getEmptyHomeVerificationSummary();
  }
  return {
    currentStatus: summary.currentStatus,
    hasActiveRequest: summary.hasActiveRequest,
  };
}

function buildVerificationSummaryFromRequests(
  requests: H5MemberVerificationRequest[],
): H5MemberVerificationSummary {
  if (requests.length === 0) {
    return getEmptyVerificationSummary();
  }
  const sorted = [...requests].sort((left, right) => right.createdAt.localeCompare(left.createdAt));
  const activeRequest = sorted.find((item) => item.status === "pending") ?? null;
  return {
    currentStatus: activeRequest?.status ?? sorted[0]?.status ?? "not_submitted",
    hasActiveRequest: activeRequest !== null,
    activeRequest,
    history: sorted,
  };
}

function buildHomeVerificationSummaryFromState(
  state: StoredMemberState,
): H5HomeVerificationSummary {
  const summary = buildVerificationSummaryFromRequests(state.verificationRequests ?? []);
  return {
    currentStatus: summary.currentStatus,
    hasActiveRequest: summary.hasActiveRequest,
  };
}

function mapHomeFragmentSummaryFromBackend(
  summary: BackendMemberHomeResponse["fragments"],
): H5HomeFragmentSummary {
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
    latestShippingStatus: summary.latestShippingStatus,
  };
}

function buildHomeFragmentSummaryFromOverview(
  overview: H5FragmentOverview,
): H5HomeFragmentSummary {
  const completedCount = overview.inventory.filter((item) => item.owned >= item.required).length;
  const totalCount = overview.inventory.length;
  const missingCount = overview.inventory.reduce(
    (sum, item) => sum + Math.max(0, item.required - item.owned),
    0,
  );
  return {
    rewardName: overview.rewardName,
    completedCount,
    totalCount,
    missingCount,
    canExchange: totalCount > 0 && completedCount === totalCount,
    shippingOrderCount: overview.shippingOrders.length,
    latestShippingStatus: overview.shippingOrders[0]?.status ?? null,
  };
}

function mapWhatsAppBindingFromBackend(
  binding: BackendWhatsAppBindingResponse,
): H5WhatsAppBinding {
  return {
    isBound: binding.isBound,
    bindingStatus: binding.bindingStatus ?? (binding.isBound ? "bound" : "not_started"),
    requestId: binding.requestId ?? null,
    phoneNumber: binding.phoneNumber,
    requestedAt: binding.requestedAt ?? null,
    startCount: binding.startCount ?? 0,
    lastUpdatedAt: binding.lastUpdatedAt,
  };
}

function seedMemberAccounts(): StoredMemberAccount[] {
  return [
    {
      id: "member-demo-1",
      accountId: "38271456",
      phone: DEFAULT_MEMBER_PHONE,
      password: DEFAULT_MEMBER_PASSWORD,
      publicUserId: "h5-38271456",
      displayName: getSeedDataText("memberDisplayName"),
      inviteCode: "INV38271456",
      createdAt: nowIso(),
    },
  ];
}

function createPackageItem(packageId: string, index: number, price: number): H5TaskPackageItem {
  return {
    id: `${packageId}-item-${index + 1}`,
    product_name: `Task Product ${index + 1}`,
    image_url: `https://picsum.photos/seed/${packageId}-${index + 1}/160/160`,
    price,
    currency: "USD",
    completed_at: null,
    order_id: null,
  };
}

function seedTaskPackages(): H5TaskPackage[] {
  const now = Date.now();
  const activeClaimedAt = new Date(now - 1000 * 60 * 60 * 3).toISOString();
  const activeExpiresAt = new Date(now + 1000 * 60 * 60 * 18).toISOString();
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
      taskBalanceAwardedAt: null,
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
      taskBalanceAwardedAt: null,
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
        inviteCode: "PROMO-38271456",
      },
      taskBalanceAwardedAt: null,
    },
  ];
}

function seedTransactions(): H5WalletTransaction[] {
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
      createdAt: new Date(Date.now() - 1000 * 60 * 60 * 12).toISOString(),
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
      createdAt: new Date(Date.now() - 1000 * 60 * 60 * 6).toISOString(),
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
      createdAt: new Date(Date.now() - 1000 * 60 * 60 * 3).toISOString(),
    },
  ];
}

function seedMessages(): H5MessageItem[] {
  return [
    {
      id: "msg-task-1",
      category: "task",
      title: getSeedDataText("messageTaskTitle"),
      body: getSeedDataText("messageTaskBody"),
      createdAt: new Date(Date.now() - 1000 * 60 * 60 * 4).toISOString(),
      isRead: false,
    },
    {
      id: "msg-wallet-1",
      category: "wallet",
      title: getSeedDataText("messageWalletTitle"),
      body: getSeedDataText("messageWalletBody"),
      createdAt: new Date(Date.now() - 1000 * 60 * 60 * 2).toISOString(),
      isRead: false,
    },
    {
      id: "msg-fragment-1",
      category: "fragment",
      title: getSeedDataText("messageFragmentTitle"),
      body: getSeedDataText("messageFragmentBody"),
      createdAt: new Date(Date.now() - 1000 * 60 * 30).toISOString(),
      isRead: true,
    },
  ];
}

function seedMemberStates(): Record<string, StoredMemberState> {
  return {
    "38271456": {
      wallet: {
        systemBalance: 420,
        taskBalance: 88,
        currency: "USD",
        withdrawThreshold: DEFAULT_WITHDRAW_THRESHOLD,
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
          createdAt: new Date(Date.now() - 1000 * 60 * 60 * 2).toISOString(),
          sourceLabel: getSeedDataText("packageGrowthTitle"),
        },
      ],
      transactions: seedTransactions(),
      withdrawRequests: [
        {
          id: "withdraw-seed-1",
          amount: 120,
          cashAmount: 100,
          bonusAmount: 20,
          actualPayoutAmount: 118.8,
          rejectionReason: null,
          currency: "USD",
          status: "paid",
          createdAt: new Date(Date.now() - 1000 * 60 * 60 * 3).toISOString(),
        },
      ],
      messages: seedMessages(),
      fragmentInventory: {
        "fragment-sun": 1,
        "fragment-moon": 0,
        "fragment-star": 2,
      },
      fragmentDropLogs: [
        {
          id: "drop-seed-1",
          fragmentId: "fragment-star",
          fragmentName: getSeedDataText("fragmentStarName"),
          source: "task",
          createdAt: new Date(Date.now() - 1000 * 60 * 20).toISOString(),
        },
      ],
      shippingOrders: [
        {
          id: "shipping-seed-1",
          rewardName: getSeedDataText("rewardName"),
          status: "shipped",
          createdAt: new Date(Date.now() - 1000 * 60 * 60 * 48).toISOString(),
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
      checkedInDate: null,
      verificationRequests: [],
      whatsappBinding: {
        isBound: false,
        bindingStatus: "not_started",
        requestId: null,
        phoneNumber: null,
        requestedAt: null,
        startCount: 0,
        lastUpdatedAt: null,
      },
    },
  };
}

function getSiteBrand(siteKey: string | undefined): H5SiteBrand {
  if (siteKey === "flash-sale") {
    return {
      site_key: "flash-sale",
      brand_name: "Flash Sale Hub",
      tagline: "Fast orders, fast rewards.",
      accent_color: "#1459c7",
    };
  }
  if (siteKey === "daily-cn") {
    return {
      site_key: "daily-cn",
      brand_name: "Daily Member Club",
      tagline: "Check in, collect fragments, unlock rewards.",
      accent_color: "#0f766e",
    };
  }
  return {
    site_key: siteKey?.trim() || "mall-cn",
    brand_name: "Member Rewards Center",
    tagline: "Task packages, wallet, support, and fragments in one place.",
    accent_color: "#1677ff",
  };
}

function cloneStateTemplate(): StoredMemberState {
  const seeded = seedMemberStates()["38271456"];
  return JSON.parse(JSON.stringify(seeded)) as StoredMemberState;
}

function ensureSeededStorage(): void {
  readMemberAccounts();
  readMemberStates();
}

function getRequiredSession(): H5MemberSession {
  ensureSeededStorage();
  const session = readSession();
  if (!session) {
    throw createServiceError("authRequired");
  }
  return session;
}

function getStateForAccount(accountId: string): StoredMemberState {
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

function updateStateForAccount(
  accountId: string,
  updater: (state: StoredMemberState) => StoredMemberState,
): StoredMemberState {
  const states = readMemberStates();
  const current = getStateForAccount(accountId);
  const next = normalizeMemberState(updater(JSON.parse(JSON.stringify(current)) as StoredMemberState));
  states[accountId] = next;
  writeMemberStates(states);
  return next;
}

function normalizeMemberState(state: StoredMemberState): StoredMemberState {
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

function calculatePackageTotalCommission(pkg: H5TaskPackage): number {
  return Number(
    pkg.items.reduce((sum, item) => sum + item.price, 0) * pkg.rewardRatio,
  );
}

function calculatePackageCurrentCommission(pkg: H5TaskPackage): number {
  return Number(
    pkg.items
      .filter((item) => item.completed_at)
      .reduce((sum, item) => sum + item.price, 0) * pkg.rewardRatio,
  );
}

function getCompletedItemCount(pkg: H5TaskPackage): number {
  return pkg.items.filter((item) => item.completed_at).length;
}

function mapTaskPackage(pkg: H5TaskPackage): H5TaskPackage & {
  totalCommission: number;
  currentCommission: number;
  completedItems: number;
  totalItems: number;
  countdownSeconds: number;
} {
  const countdownSeconds = pkg.expiresAt
    ? Math.max(0, Math.round((new Date(pkg.expiresAt).getTime() - Date.now()) / 1000))
    : pkg.completionWindowHours * 3600;
  return {
    ...pkg,
    totalCommission: calculatePackageTotalCommission(pkg),
    currentCommission: calculatePackageCurrentCommission(pkg),
    completedItems: getCompletedItemCount(pkg),
    totalItems: pkg.items.length,
    countdownSeconds,
  };
}

function getUnreadMessageCount(messages: H5MessageItem[]): number {
  return messages.filter((item) => !item.isRead).length;
}

function getWalletSummaryFromState(state: StoredMemberState): H5WalletSummary {
  const shortfall = Math.max(0, state.wallet.withdrawThreshold - state.wallet.systemBalance);
  return {
    systemBalance: Number(state.wallet.systemBalance.toFixed(2)),
    taskBalance: Number(state.wallet.taskBalance.toFixed(2)),
    currency: state.wallet.currency,
    withdrawThreshold: state.wallet.withdrawThreshold,
    canWithdraw: shortfall === 0,
    shortfallAmount: Number(shortfall.toFixed(2)),
  };
}

function getFragmentDefinitions(): H5FragmentDefinition[] {
  return [
    { id: "fragment-sun", name: getSeedDataText("fragmentSunName"), rarity: "common", color: "#f59e0b" },
    { id: "fragment-moon", name: getSeedDataText("fragmentMoonName"), rarity: "rare", color: "#6366f1" },
    { id: "fragment-star", name: getSeedDataText("fragmentStarName"), rarity: "epic", color: "#ef4444" },
  ];
}

function buildFragmentOverview(state: StoredMemberState): H5FragmentOverview {
  return {
    inventory: getFragmentDefinitions().map((fragment) => ({
      ...fragment,
      owned: state.fragmentInventory[fragment.id] ?? 0,
      required: 1,
    })),
    dropLogs: [...state.fragmentDropLogs].sort((left, right) => right.createdAt.localeCompare(left.createdAt)),
    rewardName: getSeedDataText("rewardName"),
    shippingOrders: [...state.shippingOrders].sort((left, right) => right.createdAt.localeCompare(left.createdAt)),
  };
}

function appendMessage(state: StoredMemberState, category: H5MessageCategory, title: string, body: string): void {
  state.messages.unshift({
    id: createId("msg"),
    category,
    title,
    body,
    createdAt: nowIso(),
    isRead: false,
  });
}

function appendLocalizedMessage(
  state: StoredMemberState,
  category: H5MessageCategory,
  titleKey: string,
  bodyKey: string,
  options?: {
    titleParams?: Record<string, string | number>;
    bodyParams?: Record<string, string | number>;
  },
): void {
  appendMessage(
    state,
    category,
    getServiceMessage(titleKey, options?.titleParams),
    getServiceMessage(bodyKey, options?.bodyParams),
  );
}

function appendTransaction(
  state: StoredMemberState,
  transaction: Omit<H5WalletTransaction, "id" | "createdAt">,
): void {
  state.transactions.unshift({
    id: createId("txn"),
    createdAt: nowIso(),
    ...transaction,
  });
}

function maskPhone(phone: string): string {
  if (phone.length < 7) {
    return phone;
  }
  return `${phone.slice(0, 3)}****${phone.slice(-4)}`;
}

export function maskAccountId(accountId: string): string {
  if (accountId.length <= 5) {
    return accountId;
  }
  return `${accountId.slice(0, 3)}***${accountId.slice(-2)}`;
}

function todayKey(): string {
  return new Date().toISOString().slice(0, 10);
}

function generateInviteCode(accountId: string): string {
  return `INV${accountId}`;
}

function generateUniqueNumericAccountId(): string {
  const existing = new Set(readMemberAccounts().map((item) => item.accountId));
  let candidate = randomDigits(ACCOUNT_ID_LENGTH);
  while (existing.has(candidate)) {
    candidate = randomDigits(ACCOUNT_ID_LENGTH);
  }
  return candidate;
}

function getLeaderboardBaseEntries(): Array<{ accountId: string; amount: number; currency: string }> {
  return [
    { accountId: "12864472", amount: 5200, currency: "USD" },
    { accountId: "87342155", amount: 4760, currency: "USD" },
    { accountId: "54021863", amount: 3980, currency: "USD" },
    { accountId: "74190538", amount: 3510, currency: "USD" },
  ];
}

export async function getCurrentMemberSession(): Promise<H5MemberSession | null> {
  // Short-circuit: if no H5 session exists in storage, skip the network probe.
  // This prevents a spurious 401 GET /api/h5/auth/me in admin-console context.
  const stored = readSession();
  if (!stored) {
    if (isLegacyFallbackEnabled()) {
      ensureSeededStorage();
      return readSession();
    }
    return null;
  }
  if (!hasBackendAuthCookies()) {
    if (isLegacyFallbackEnabled()) {
      return stored;
    }
    writeSession(null);
    return null;
  }
  const authResponse = await tryBackendAuthRequest<BackendMemberAuthResponse>(() =>
    requestJson("/api/h5/auth/me"),
    {
      allowRefresh: true,
    },
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
      inviteCode: profile.inviteCode,
    };
  }
  if (!isLegacyFallbackEnabled()) {
    throw getBackendUnavailableError();
  }
  ensureSeededStorage();
  return readSession();
}

export async function getCurrentMemberProfile(): Promise<H5MemberProfile | null> {
  const authResponse = await tryBackendAuthRequest<BackendMemberAuthResponse>(() =>
    requestJson("/api/h5/auth/me"),
    {
      allowRefresh: true,
    },
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
    avatarUrl: account.avatarUrl ?? null,
  };
}

export async function updateMemberProfile(payload: {
  phone: string;
  avatarUrl?: string | null;
}): Promise<H5MemberProfile> {
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

  const nextAccount: StoredMemberAccount = {
    ...currentAccount,
    phone,
    avatarUrl: payload.avatarUrl === undefined ? currentAccount.avatarUrl ?? null : payload.avatarUrl,
  };
  writeMemberAccounts(accounts.map((item) => (item.accountId === session.accountId ? nextAccount : item)));

  const nextSession: H5MemberSession = {
    ...session,
    phone: nextAccount.phone,
    avatarUrl: nextAccount.avatarUrl ?? null,
  };
  writeSession(nextSession);

  return {
    ...nextSession,
    accountIdMasked: maskAccountId(nextSession.accountId),
    createdAt: nextAccount.createdAt,
    avatarUrl: nextAccount.avatarUrl ?? null,
  };
}

export async function updateMemberPassword(payload: {
  currentPassword: string;
  nextPassword: string;
  confirmPassword: string;
}): Promise<void> {
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
    accounts.map((item) =>
      item.accountId === session.accountId
        ? {
            ...item,
            password: nextPassword,
          }
        : item,
    ),
  );
}

export async function registerMember(payload: {
  siteKey: string;
  phone: string;
  password: string;
  confirmPassword?: string;
  displayName?: string;
}): Promise<H5MemberProfile> {
  try {
    const backendResponse = await tryBackendAuthRequest<BackendMemberAuthResponse>(() =>
      requestJson("/api/h5/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          siteKey: payload.siteKey,
          phone: payload.phone.trim(),
          password: payload.password.trim(),
          confirmPassword: payload.confirmPassword?.trim() || payload.password.trim(),
          ...(payload.displayName?.trim() ? { displayName: payload.displayName.trim() } : {}),
        }),
        signal: AbortSignal.timeout(3000),      }),
    );
    if (backendResponse === "unauthenticated") {
      // 后端未认证，尝试 localStorage 注册
      if (isLegacyFallbackEnabled()) {
        const legacy = tryLegacyRegister(payload);
        if (legacy) return legacy;
      }
      throw createServiceError("registerAuthFailed");
    }
    if (backendResponse) {
      const profile = buildProfileFromAuthPayload(backendResponse);
      syncLegacyMemberCacheFromProfile(profile);
      return profile;
    }
  } catch (error) {
    // 409 — 后端返回了具体业务错误，透传实际消息
    if (error instanceof ApiRequestError && error.status === 409) {
      throw new Error(error.message || getServiceErrorMessage("registerFailed"));
    }
    // 网络/超时错误 — 尝试 localStorage 回退
    if (isLegacyFallbackEnabled()) {
      const legacy = tryLegacyRegister(payload);
      if (legacy) return legacy;
    }
    // 服务不可达（404 等）— 尝试 localStorage 回退
    if (error instanceof ApiRequestError && canUseLegacyFallback(error)) {
      const legacy = tryLegacyRegister(payload);
      if (legacy) return legacy;
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

/** Try to register using legacy localStorage mock data. Returns null on failure. */
function tryLegacyRegister(payload: {
  siteKey: string;
  phone: string;
  password: string;
  confirmPassword?: string;
  displayName?: string;
}): H5MemberProfile | null {
  ensureSeededStorage();
  const phone = payload.phone.trim();
  const password = payload.password.trim();
  if (!phone || !password) return null;
  const accounts = readMemberAccounts();
  if (accounts.some((item) => item.phone === phone)) {
    return null; // caller should provide a meaningful message
  }
  const accountId = generateUniqueNumericAccountId();
  const account: StoredMemberAccount = {
    id: createId("member"),
    accountId,
    phone,
    password,
    publicUserId: `h5-${accountId}`,
    displayName:
      payload.displayName?.trim() ||
      getSeedDataText("memberDisplayNameWithSuffix", { suffix: accountId.slice(-4) }),
    inviteCode: generateInviteCode(accountId),
    createdAt: nowIso(),
    avatarUrl: null,
  };
  accounts.push(account);
  writeMemberAccounts(accounts);
  const states = readMemberStates();
  states[accountId] = cloneStateTemplate();
  writeMemberStates(states);
  const session: H5MemberSession = {
    accountId,
    phone,
    publicUserId: account.publicUserId,
    displayName: account.displayName,
    inviteCode: account.inviteCode,
    avatarUrl: account.avatarUrl ?? null,
  };
  writeSession(session);
  return {
    ...session,
    accountIdMasked: maskAccountId(session.accountId),
    createdAt: account.createdAt,
    avatarUrl: account.avatarUrl ?? null,
  };
}

async function loginMemberResolved(payload: {
  siteKey: string;
  phone: string;
  password: string;
}): Promise<H5MemberProfile> {
  // 尝试后端认证（带较短超时避免无限等待）
  try {
    const backendResponse = await requestJson<BackendMemberAuthResponse>("/api/h5/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        siteKey: payload.siteKey,
        phone: payload.phone.trim(),
        password: payload.password.trim(),
      }),
      signal: AbortSignal.timeout(3000),
    });
    const profile = buildProfileFromAuthPayload(backendResponse);
    syncLegacyMemberCacheFromProfile(profile);
    return profile;
  } catch (error) {
    if (error instanceof ApiRequestError && error.status === 401) {
      // 401 — 后端认证失败，尝试 localStorage 回退
      if (isLegacyFallbackEnabled()) {
        const legacy = tryLegacyLogin(payload.phone.trim(), payload.password.trim());
        if (legacy) return legacy;
      }
      const normalizedDetail = (error.message ?? "").trim();
      if (
        normalizedDetail &&
        !/phone or password is invalid/i.test(normalizedDetail) &&
        !/手机号或密码错误/.test(normalizedDetail)
      ) {
        throw new Error(normalizedDetail);
      }
      throw createServiceError("invalidCredentials");
    }
    // 网络/超时错误 — 尝试 localStorage 回退
    if (isLegacyFallbackEnabled()) {
      const legacy = tryLegacyLogin(payload.phone.trim(), payload.password.trim());
      if (legacy) return legacy;
    }
    // 后端不可达
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

/** Try to login using legacy localStorage mock data. Returns null if not found. */
function tryLegacyLogin(phone: string, password: string): H5MemberProfile | null {
  const account = readMemberAccounts().find(
    (item) => item.phone === phone && item.password === password,
  );
  if (!account) return null;
  const session: H5MemberSession = {
    accountId: account.accountId,
    phone: account.phone,
    publicUserId: account.publicUserId,
    displayName: account.displayName,
    inviteCode: account.inviteCode,
    avatarUrl: account.avatarUrl ?? null,
  };
  writeSession(session);
  return {
    ...session,
    accountIdMasked: maskAccountId(session.accountId),
    createdAt: account.createdAt,
    avatarUrl: account.avatarUrl ?? null,
  };
}

export async function loginMember(payload: {
  siteKey: string;
  phone: string;
  password: string;
}): Promise<H5MemberProfile> {
  return loginMemberResolved(payload);
}

export async function logoutMember(): Promise<void> {
  try {
    const logoutResponse = await tryBackendAuthRequest(() =>
      requestJson("/api/h5/auth/logout", {
        method: "POST",
      }),
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

export async function getMemberHomeDashboard(siteKey?: string): Promise<H5HomeDashboard> {
  const homeResponse = await tryBackendAuthRequest<BackendMemberHomeResponse>(() =>
    requestJson("/api/h5/member/home"),
    {
      allowRefresh: true,
    },
  );
  if (homeResponse === "unauthenticated") {
    writeSession(null);
    throw new H5AuthRequiredError();
  }
  if (homeResponse) {
    const profile = buildProfileFromAuthPayload({
      member: homeResponse.member,
      site: homeResponse.site,
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
        canWithdraw:
          (homeResponse.wallet.systemBalance ?? 0) >= DEFAULT_WITHDRAW_THRESHOLD,
        shortfallAmount: Math.max(
          0,
          DEFAULT_WITHDRAW_THRESHOLD - (homeResponse.wallet.systemBalance ?? 0),
        ),
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
        isRead: item.isRead,
      })),
      leaderboard: homeResponse.leaderboard.map((item) => ({
        rank: item.rank,
        accountIdMasked: item.accountIdMasked,
        amount: item.amount,
        currency: item.currency,
      })),
      verification: mapHomeVerificationSummaryFromBackend(homeResponse.verification),
      fragments: mapHomeFragmentSummaryFromBackend(homeResponse.fragments),
    };
  }
  if (!isLegacyFallbackEnabled()) {
    throw getBackendUnavailableError();
  }

  const session = getRequiredSession();
  const account = readMemberAccounts().find((item) => item.accountId === session.accountId)!;
  const state = getStateForAccount(session.accountId);
  const packages = state.taskPackages.map((pkg) => mapTaskPackage(pkg));
  const fragmentOverview = buildFragmentOverview(state);
  return {
    site: getSiteBrand(siteKey),
    member: {
      ...session,
      accountIdMasked: maskAccountId(session.accountId),
      createdAt: account.createdAt,
      avatarUrl: account.avatarUrl ?? null,
    },
    wallet: getWalletSummaryFromState(state),
    unreadCount: getUnreadMessageCount(state.messages),
    pendingClaimCount: packages.filter((pkg) => pkg.status === "pending_claim").length,
    activeCount: packages.filter((pkg) => pkg.status === "active").length,
    expiringCount: packages.filter((pkg) => pkg.status === "active" && pkg.countdownSeconds <= 6 * 3600).length,
    recentMessages: [...state.messages].slice(0, 5),
    leaderboard: (await getWithdrawLeaderboard()).slice(0, 5),
    verification: buildHomeVerificationSummaryFromState(state),
    fragments: buildHomeFragmentSummaryFromOverview(fragmentOverview),
  };
}

export async function listTaskPackages(): Promise<
  Array<H5TaskPackage & { totalCommission: number; currentCommission: number; completedItems: number; totalItems: number; countdownSeconds: number }>
> {
  const backendPackages = await requestBackendMemberDomain<BackendTaskPackageResponse[]>("/api/h5/task-packages");
  if (backendPackages) {
    return backendPackages.map((pkg) => mapTaskPackageFromBackend(pkg));
  }
  const session = getRequiredSession();
  const state = getStateForAccount(session.accountId);
  return state.taskPackages.map((pkg) => mapTaskPackage(pkg));
}

export async function getTaskPackageDetail(
  packageId: string,
): Promise<
  H5TaskPackage & { totalCommission: number; currentCommission: number; completedItems: number; totalItems: number; countdownSeconds: number }
> {
  const backendPackage = await requestBackendMemberDomain<BackendTaskPackageResponse>(
    `/api/h5/task-packages/${encodeURIComponent(packageId)}`,
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

export async function claimTaskPackage(
  packageId: string,
): Promise<
  H5TaskPackage & { totalCommission: number; currentCommission: number; completedItems: number; totalItems: number; countdownSeconds: number }
> {
  const backendPackage = await requestBackendMemberDomain<BackendTaskPackageResponse>(
    `/api/h5/task-packages/${encodeURIComponent(packageId)}/claim`,
    {
      method: "POST",
    },
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
    pkg.expiresAt = new Date(Date.now() + pkg.completionWindowHours * 3600 * 1000).toISOString();
    appendLocalizedMessage(state, "task", "packageClaimTitle", "packageClaimBody", {
      titleParams: { title: pkg.title },
    });
    return state;
  });
  const updated = nextState.taskPackages.find((item) => item.id === packageId)!;
  return mapTaskPackage(updated);
}

export async function completeTaskPackagePurchase(
  packageId: string,
  itemId: string,
): Promise<{
  success: boolean;
  order?: H5MemberOrder;
  taskPackage: H5TaskPackage & { totalCommission: number; currentCommission: number; completedItems: number; totalItems: number; countdownSeconds: number };
  wallet: H5WalletSummary;
  fragmentDrop?: H5FragmentDropLog | null;
  reason?: string;
}> {
  const backendPurchase = await requestBackendMemberDomain<BackendTaskPackagePurchaseResponse>(
    `/api/h5/task-packages/${encodeURIComponent(packageId)}/items/${encodeURIComponent(itemId)}/purchase`,
    {
      method: "POST",
    },
  );
  if (backendPurchase) {
    return {
      success: backendPurchase.success,
      order: backendPurchase.order ? mapOrderFromBackend(backendPurchase.order) : undefined,
      taskPackage: mapTaskPackageFromBackend(backendPurchase.taskPackage),
      wallet: mapWalletSummaryFromBackend(backendPurchase.wallet),
      fragmentDrop: backendPurchase.fragmentDrop
        ? mapFragmentDropFromBackend(backendPurchase.fragmentDrop)
        : null,
      reason: backendPurchase.reason ?? undefined,
    };
  }
  const session = getRequiredSession();
  let operationResult: {
    success: boolean;
    order?: H5MemberOrder;
    taskPackage: H5TaskPackage;
    fragmentDrop?: H5FragmentDropLog | null;
    reason?: string;
  } | null = null;
  const nextState = updateStateForAccount(session.accountId, (state) => {
    const pkg = state.taskPackages.find((item) => item.id === packageId);
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
    const order: H5MemberOrder = {
      id: createId("order"),
      orderNo: `ORD-${Math.random().toString().slice(2, 10)}`,
      packageId: pkg.id,
      packageTitle: pkg.title,
      productName: item.product_name,
      amount: item.price,
      currency: item.currency,
      status: "paid",
      createdAt: nowIso(),
      sourceLabel: pkg.title,
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
      note: `${pkg.title} / ${item.product_name}`,
    });
    appendLocalizedMessage(state, "order", "purchaseSuccessTitle", "purchaseSuccessBody", {
      titleParams: { product: item.product_name },
    });

    let fragmentDrop: H5FragmentDropLog | null = null;
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
        note: `${pkg.title} completed`,
      });
      appendLocalizedMessage(state, "task", "packageCompletedTitle", "packageCompletedBody", {
        titleParams: { title: pkg.title },
      });
      fragmentDrop = createFragmentDrop(state, "task");
    }
    operationResult = { success: true, order, taskPackage: pkg, fragmentDrop };
    return state;
  });

  if (!operationResult) {
    throw createServiceError("purchaseInitFailed");
  }
  const settledResult = operationResult as {
    success: boolean;
    order?: H5MemberOrder;
    taskPackage: H5TaskPackage;
    fragmentDrop?: H5FragmentDropLog | null;
    reason?: string;
  };
  return {
    ...settledResult,
    taskPackage: mapTaskPackage(settledResult.taskPackage),
    wallet: getWalletSummaryFromState(nextState),
  };
}

function createFragmentDrop(
  state: StoredMemberState,
  source: "checkin" | "task",
): H5FragmentDropLog {
  const definitions = getFragmentDefinitions();
  const index = state.fragmentDropLogs.length % definitions.length;
  const fragment = definitions[index];
  state.fragmentInventory[fragment.id] = (state.fragmentInventory[fragment.id] ?? 0) + 1;
  const drop: H5FragmentDropLog = {
    id: createId("fragment-drop"),
    fragmentId: fragment.id,
    fragmentName: fragment.name,
    source,
    createdAt: nowIso(),
  };
  state.fragmentDropLogs.unshift(drop);
  appendLocalizedMessage(
    state,
    "fragment",
    "fragmentObtainedTitle",
    source === "checkin" ? "fragmentObtainedBodyCheckin" : "fragmentObtainedBodyTask",
    {
      titleParams: { fragment: fragment.name },
    },
  );
  return drop;
}

export async function listMemberOrders(): Promise<H5MemberOrder[]> {
  const backendOrders = await requestBackendMemberDomain<BackendMemberOrderResponse[]>("/api/h5/orders");
  if (backendOrders) {
    return backendOrders.map((order) => mapOrderFromBackend(order));
  }
  const session = getRequiredSession();
  const state = getStateForAccount(session.accountId);
  return [...state.orders].sort((left, right) => right.createdAt.localeCompare(left.createdAt));
}

export async function getWalletSummary(): Promise<H5WalletSummary> {
  const backendWallet = await requestBackendMemberDomain<BackendWalletSummaryResponse>("/api/h5/wallet");
  if (backendWallet) {
    return mapWalletSummaryFromBackend(backendWallet);
  }
  const session = getRequiredSession();
  return getWalletSummaryFromState(getStateForAccount(session.accountId));
}

export async function listWalletTransactions(): Promise<H5WalletTransaction[]> {
  const backendTransactions = await requestBackendMemberDomain<BackendWalletTransactionResponse[]>(
    "/api/h5/wallet/transactions",
  );
  if (backendTransactions) {
    return backendTransactions.map((item) => mapWalletTransactionFromBackend(item));
  }
  const session = getRequiredSession();
  const state = getStateForAccount(session.accountId);
  return [...state.transactions].sort((left, right) => right.createdAt.localeCompare(left.createdAt));
}

export async function listWithdrawRequests(): Promise<H5WithdrawRequest[]> {
  const backendWithdrawals = await requestBackendMemberDomain<BackendWithdrawalResponse[]>(
    "/api/h5/withdrawals",
  );
  if (backendWithdrawals) {
    return backendWithdrawals.map((item) => mapWithdrawalFromBackend(item));
  }
  const session = getRequiredSession();
  const state = getStateForAccount(session.accountId);
  return [...state.withdrawRequests].sort((left, right) => right.createdAt.localeCompare(left.createdAt));
}

export async function createRechargeOrder(amount: number): Promise<H5WalletSummary> {
  const backendWallet = await requestBackendMemberDomain<BackendWalletSummaryResponse>(
    "/api/h5/wallet/recharges",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ amount }),
    },
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
      note: "Prototype recharge",
    });
    appendLocalizedMessage(draft, "wallet", "rechargeTitle", "rechargeBody", {
      bodyParams: { amount: sanitizedAmount.toFixed(2) },
    });
    return draft;
  });
  return getWalletSummaryFromState(state);
}

export async function transferTaskBalanceToSystem(amount: number): Promise<H5WalletSummary> {
  const backendWallet = await requestBackendMemberDomain<BackendWalletSummaryResponse>(
    "/api/h5/wallet/transfers",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ amount }),
    },
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
      note: "Transfer out from task balance",
    });
    appendTransaction(draft, {
      ledgerType: "system",
      transactionType: "task_to_system_transfer",
      direction: "credit",
      amount: sanitizedAmount,
      currency: draft.wallet.currency,
      status: "paid",
      note: "Transfer in from task balance",
    });
    appendLocalizedMessage(draft, "wallet", "transferTitle", "transferBody");
    return draft;
  });
  return getWalletSummaryFromState(state);
}

export async function createWithdrawRequest(amount: number): Promise<H5WalletSummary> {
  const backendWithdrawal = await requestBackendMemberDomain<BackendWithdrawalResponse>(
    "/api/h5/withdrawals",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ amount }),
    },
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
      cashAmount: sanitizedAmount,
      bonusAmount: 0,
      actualPayoutAmount: null,
      currency: draft.wallet.currency,
      status: "submitted",
      rejectionReason: null,
      createdAt: nowIso(),
    });
    appendTransaction(draft, {
      ledgerType: "system",
      transactionType: "withdraw_request",
      direction: "debit",
      amount: sanitizedAmount,
      currency: draft.wallet.currency,
      status: "submitted",
      note: "Withdrawal request submitted",
    });
    appendLocalizedMessage(draft, "wallet", "withdrawTitle", "withdrawBody");
    return draft;
  });
  return getWalletSummaryFromState(state);
}

export async function getWithdrawLeaderboard(): Promise<H5LeaderboardEntry[]> {
  const backendLeaderboard = await requestBackendMemberDomain<BackendWithdrawLeaderboardResponse[]>(
    "/api/h5/withdraw-leaderboard",
  );
  if (backendLeaderboard) {
    return backendLeaderboard.map((item) => mapLeaderboardEntryFromBackend(item));
  }
  const states = readMemberStates();
  const dynamic = Object.entries(states).map(([accountId, state]) => ({
    accountId,
    amount: state.withdrawRequests
      .filter((item) => item.status === "paid")
      .reduce((sum, item) => sum + item.amount, 0),
    currency: state.wallet.currency,
  }));
  return [...getLeaderboardBaseEntries(), ...dynamic]
    .filter((item) => item.amount > 0)
    .sort((left, right) => right.amount - left.amount)
    .slice(0, 10)
    .map((item, index) => ({
      rank: index + 1,
      accountIdMasked: maskAccountId(item.accountId),
      amount: Number(item.amount.toFixed(2)),
      currency: item.currency,
    }));
}

export async function listMemberMessages(): Promise<H5MessageItem[]> {
  const backendMessages = await requestBackendMemberDomain<BackendMemberMessageResponse[]>("/api/h5/messages");
  if (backendMessages) {
    return backendMessages.map((item) => mapMessageFromBackend(item));
  }
  const session = getRequiredSession();
  const state = getStateForAccount(session.accountId);
  return [...state.messages].sort((left, right) => right.createdAt.localeCompare(left.createdAt));
}

export async function markMessageRead(messageId: string): Promise<void> {
  const backendMessage = await requestBackendMemberDomain<BackendMemberMessageResponse>(
    `/api/h5/messages/${encodeURIComponent(messageId)}/read`,
    {
      method: "POST",
    },
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

export async function markAllMessagesRead(): Promise<void> {
  const backendResult = await requestBackendMemberDomain<{ updated: number }>(
    "/api/h5/messages/read-all",
    {
      method: "POST",
    },
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

export async function getMemberVerificationSummary(): Promise<H5MemberVerificationSummary> {
  const backendSummary = await requestBackendMemberDomain<BackendMemberVerificationSummaryResponse>(
    "/api/h5/member/verification",
  );
  if (backendSummary) {
    return mapVerificationSummaryFromBackend(backendSummary);
  }
  const session = getRequiredSession();
  const state = getStateForAccount(session.accountId);
  return buildVerificationSummaryFromRequests(state.verificationRequests ?? []);
}

export async function listMemberVerificationRequests(): Promise<H5MemberVerificationRequest[]> {
  const backendRequests = await requestBackendMemberDomain<BackendMemberVerificationRequestResponse[]>(
    "/api/h5/member/verification/requests",
  );
  if (backendRequests) {
    return backendRequests.map((item) => mapVerificationRequestFromBackend(item));
  }
  const session = getRequiredSession();
  const state = getStateForAccount(session.accountId);
  return [...(state.verificationRequests ?? [])].sort((left, right) => right.createdAt.localeCompare(left.createdAt));
}

export async function createMemberVerificationRequest(
  payload: H5MemberVerificationCreateInput,
): Promise<H5MemberVerificationRequest> {
  const requestPayload = {
    requestType: payload.requestType?.trim() || "identity",
    notes: payload.notes?.trim() || null,
    documents: (payload.documents ?? []).map((item) => ({
      fileName: item.fileName.trim(),
      mimeType: item.mimeType?.trim() || null,
      storageKey: item.storageKey?.trim() || null,
      metadataJson: item.metadataJson ?? null,
    })),
  };
  const backendRequest = await requestBackendMemberDomain<BackendMemberVerificationRequestResponse>(
    "/api/h5/member/verification/requests",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(requestPayload),
    },
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
    const nextRequest: H5MemberVerificationRequest = {
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
        createdAt,
      })),
    };
    draft.verificationRequests = [nextRequest, ...(draft.verificationRequests ?? [])];
    appendLocalizedMessage(draft, "system", "verificationSubmittedTitle", "verificationSubmittedBody");
    return draft;
  });
  return state.verificationRequests[0]!;
}

export async function getMemberVerificationRequestDetail(
  requestId: string,
): Promise<H5MemberVerificationRequest> {
  const backendRequest = await requestBackendMemberDomain<BackendMemberVerificationRequestResponse>(
    `/api/h5/member/verification/requests/${encodeURIComponent(requestId)}`,
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

export async function performDailyCheckIn(): Promise<H5FragmentOverview> {
  const backendOverview = await requestBackendMemberDomain<BackendFragmentOverviewResponse>(
    "/api/h5/fragments/check-in",
    {
      method: "POST",
    },
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

export async function getFragmentsOverview(): Promise<H5FragmentOverview> {
  const backendOverview = await requestBackendMemberDomain<BackendFragmentOverviewResponse>("/api/h5/fragments");
  if (backendOverview) {
    return mapFragmentOverviewFromBackend(backendOverview);
  }
  const session = getRequiredSession();
  return buildFragmentOverview(getStateForAccount(session.accountId));
}

export async function createFragmentExchange(payload: H5ShippingAddress): Promise<H5FragmentOverview> {
  const backendOverview = await requestBackendMemberDomain<BackendFragmentOverviewResponse>(
    "/api/h5/fragments/exchanges",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
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
      address: payload,
    });
    appendLocalizedMessage(draft, "fragment", "exchangeTitle", "exchangeBody");
    return draft;
  });
  return buildFragmentOverview(state);
}

export async function getRewardShippingOrders(): Promise<H5RewardShippingOrder[]> {
  const backendOrders = await requestBackendMemberDomain<BackendRewardShippingOrderResponse[]>(
    "/api/h5/rewards/shipping",
  );
  if (backendOrders) {
    return backendOrders.map((item) => mapShippingOrderFromBackend(item));
  }
  const session = getRequiredSession();
  const state = getStateForAccount(session.accountId);
  return [...state.shippingOrders].sort((left, right) => right.createdAt.localeCompare(left.createdAt));
}

export async function getWhatsAppBinding(): Promise<H5WhatsAppBinding> {
  const backendBinding = await requestBackendMemberDomain<BackendWhatsAppBindingResponse>(
    "/api/h5/whatsapp-binding",
  );
  if (backendBinding) {
    return mapWhatsAppBindingFromBackend(backendBinding);
  }
  const session = getRequiredSession();
  return getStateForAccount(session.accountId).whatsappBinding;
}

export async function startWhatsAppBinding(): Promise<H5WhatsAppBinding> {
  const backendBinding = await requestBackendMemberDomain<BackendWhatsAppBindingResponse>(
    "/api/h5/whatsapp-binding/start",
    {
      method: "POST",
    },
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
      lastUpdatedAt: nowIso(),
    };
    appendLocalizedMessage(draft, "system", "whatsappOpenedTitle", "whatsappOpenedBody");
    return draft;
  });
  return state.whatsappBinding;
}

export async function getMemberSupportContext(): Promise<{
  accountId: string;
  publicUserId: string;
}> {
  const session = getRequiredSession();
  return {
    accountId: session.accountId,
    publicUserId: session.publicUserId,
  };
}

export async function getMaskedPhone(): Promise<string> {
  const session = getRequiredSession();
  return maskPhone(session.phone);
}

// ─── Auth API (mock/real dual-mode) ───────────────────────

/** 登录 */
export async function loginApi(
  phone: string,
  password: string,
  siteKey?: string,
): Promise<H5LoginResponse> {
  if (apiMode === 'real') {
    const res = await h5Api.post<H5LoginResponse>('/api/h5/auth/login', {
      phone,
      password,
      siteKey: siteKey || 'mall-cn',
    });
    sessionManager.setSession(res.data.access_token, res.data.refresh_token, res.data.expires_in);
    return res.data;
  }
  // Mock fallback
  const profile = await loginMember({ siteKey: siteKey || 'mall-cn', phone, password });
  const user: H5MemberSession = {
    accountId: profile.accountId,
    phone: profile.phone,
    publicUserId: profile.publicUserId,
    displayName: profile.displayName,
    inviteCode: profile.inviteCode,
    avatarUrl: profile.avatarUrl ?? null,
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
    avatarUrl: user.avatarUrl,
  });
  return { access_token: fakeToken, refresh_token: fakeRefresh, expires_in: 7200, user };
}

/** 注册 */
export async function registerApi(payload: {
  siteKey: string;
  phone: string;
  password: string;
  confirmPassword?: string;
  displayName?: string;
}): Promise<H5LoginResponse> {
  if (apiMode === 'real') {
    const res = await h5Api.post<H5LoginResponse>('/api/h5/auth/register', payload);
    sessionManager.setSession(res.data.access_token, res.data.refresh_token, res.data.expires_in);
    return res.data;
  }
  // Mock fallback
  const profile = await registerMember(payload);
  const user: H5MemberSession = {
    accountId: profile.accountId,
    phone: profile.phone,
    publicUserId: profile.publicUserId,
    displayName: profile.displayName,
    inviteCode: profile.inviteCode,
    avatarUrl: profile.avatarUrl ?? null,
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
    avatarUrl: user.avatarUrl,
  });
  return { access_token: fakeToken, refresh_token: fakeRefresh, expires_in: 7200, user };
}

/** 刷新 token */
export async function refreshTokenApi(): Promise<{ access_token: string; refresh_token: string; expires_in: number }> {
  if (apiMode === 'real') {
    const refreshToken = sessionManager.getRefreshToken();
    const res = await h5Api.post<{ access_token: string; refresh_token: string; expires_in: number }>('/api/h5/auth/refresh', {
      refresh_token: refreshToken,
    });
    sessionManager.setSession(res.data.access_token, res.data.refresh_token, res.data.expires_in);
    return res.data;
  }
  // Mock fallback: use existing refreshBackendAuthSession
  const success = await refreshBackendAuthSession();
  if (!success) {
    throw new Error('Token refresh failed');
  }
  return {
    access_token: sessionManager.getAccessToken() ?? '',
    refresh_token: sessionManager.getRefreshToken() ?? '',
    expires_in: 7200,
  };
}

/** 登出 */
export async function logoutApi(): Promise<void> {
  if (apiMode === 'real') {
    await h5Api.post('/api/h5/auth/logout');
    sessionManager.clearSession();
    return;
  }
  // Mock fallback
  await logoutMember();
  sessionManager.clearSession();
}

/** 获取用户信息 */
export async function getUserInfoApi(): Promise<H5MemberProfile | null> {
  if (apiMode === 'real') {
    const res = await h5Api.get<{ member: BackendMemberAuthResponse['member']; site: BackendMemberAuthResponse['site'] }>('/api/h5/auth/me');
    const profile = buildProfileFromAuthPayload({
      member: res.data.member,
      site: res.data.site,
    });
    syncLegacyMemberCacheFromProfile(profile);
    return profile;
  }
  // Mock fallback
  return getCurrentMemberProfile();
}

/** 更新个人信息 */
export async function updateProfileApi(payload: {
  phone: string;
  avatarUrl?: string | null;
}): Promise<H5MemberProfile> {
  if (apiMode === 'real') {
    const res = await h5Api.put<H5MemberProfile>('/api/h5/profile', payload);
    return res.data;
  }
  // Mock fallback
  return updateMemberProfile(payload);
}

/** 上传头像（multipart） */
export async function updateAvatarApi(file: File): Promise<{ avatarUrl: string }> {
  if (apiMode === 'real') {
    const formData = new FormData();
    formData.append('file', file);
    const res = await h5Api.post<{ avatarUrl: string }>('/api/h5/profile/avatar', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return res.data;
  }
  // Mock fallback: simulate avatar upload by storing a fake URL
  const session = getRequiredSession();
  const fakeUrl = URL.createObjectURL(file);
  const accounts = readMemberAccounts();
  writeMemberAccounts(
    accounts.map((item) =>
      item.accountId === session.accountId ? { ...item, avatarUrl: fakeUrl } : item,
    ),
  );
  const nextSession = { ...session, avatarUrl: fakeUrl };
  writeSession(nextSession);
  return { avatarUrl: fakeUrl };
}

/** 修改密码 */
export async function changePasswordApi(payload: {
  currentPassword: string;
  nextPassword: string;
  confirmPassword: string;
}): Promise<void> {
  if (apiMode === 'real') {
    await h5Api.put('/api/h5/profile/password', payload);
    return;
  }
  // Mock fallback
  return updateMemberPassword(payload);
}

// ─── Task API (mock/real dual-mode) ──────────────────────────────

/** 获取任务包列表 */
export async function getTaskPackagesApi(params?: {
  page?: number;
  size?: number;
  status?: string;
}): Promise<
  Array<H5TaskPackage & { totalCommission: number; currentCommission: number; completedItems: number; totalItems: number; countdownSeconds: number }>
> {
  if (apiMode === 'real') {
    const res = await h5Api.get('/api/h5/tasks', { params });
    return res.data.items ?? res.data;
  }
  // Mock fallback - use existing listTaskPackages
  return listTaskPackages();
}

/** 获取任务包详情 */
export async function getTaskPackageDetailApi(id: string): Promise<
  (H5TaskPackage & { totalCommission: number; currentCommission: number; completedItems: number; totalItems: number; countdownSeconds: number }) | null
> {
  if (apiMode === 'real') {
    const res = await h5Api.get(`/api/h5/tasks/${encodeURIComponent(id)}`);
    return res.data;
  }
  // Mock fallback
  try {
    return await getTaskPackageDetail(id);
  } catch {
    return null;
  }
}

/** 提交任务 */
export async function submitTaskApi(id: string, data: unknown): Promise<boolean> {
  if (apiMode === 'real') {
    await h5Api.post(`/api/h5/tasks/${encodeURIComponent(id)}/submit`, data);
    return true;
  }
  return true; // Mock: always succeed
}

/** 上传任务凭证 */
export async function uploadTaskProofApi(
  id: string,
  file: File,
  onProgress?: (pct: number) => void,
): Promise<string> {
  if (apiMode === 'real') {
    const form = new FormData();
    form.append('file', file);
    const res = await h5Api.post(`/api/h5/tasks/${encodeURIComponent(id)}/proof`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (e) => {
        if (e.total) onProgress?.(Math.round((e.loaded / e.total) * 100));
      },
    });
    return res.data.url ?? res.data;
  }
  // Mock: simulate upload
  return URL.createObjectURL(file);
}

// ─── Wallet / Tasks / 其他模块的 API Endpoint 预览（Phase 3-4 占位）────────

// ─── Wallet / Notifications API ──────────────────────────────────

/** 获取钱包余额 */
export async function getWalletBalanceApi(): Promise<H5WalletSummary> {
  if (apiMode === 'real') {
    const backendWallet = await requestBackendMemberDomain<BackendWalletSummaryResponse>(
      H5_API_ENDPOINTS.wallet.balance,
    );
    if (backendWallet) {
      return mapWalletSummaryFromBackend(backendWallet);
    }
  }
  // Mock fallback
  const session = getRequiredSession();
  const state = getStateForAccount(session.accountId);
  return getWalletSummaryFromState(state);
}

/** 获取钱包交易记录（分页） */
export async function getWalletTransactionsApi(params: {
  page: number;
  size?: number;
  type?: string;
}): Promise<{ items: H5WalletTransaction[]; total: number }> {
  if (apiMode === 'real') {
    const backendTransactions = await requestBackendMemberDomain<BackendWalletTransactionResponse[]>(
      H5_API_ENDPOINTS.wallet.transactions,
    );
    if (backendTransactions) {
      const allTransactions = backendTransactions.map((item) => mapWalletTransactionFromBackend(item));
      const filtered = params.type
        ? allTransactions.filter((item) => item.transactionType === params.type)
        : allTransactions;
      const size = params.size ?? 20;
      const start = (params.page - 1) * size;
      return {
        items: filtered.slice(start, start + size),
        total: filtered.length,
      };
    }
  }
  // Mock fallback
  const session = getRequiredSession();
  const state = getStateForAccount(session.accountId);
  const allTransactions = [...state.transactions].sort((left, right) =>
    right.createdAt.localeCompare(left.createdAt),
  );
  const filtered = params.type
    ? allTransactions.filter((item) => item.transactionType === params.type)
      : allTransactions;
  const size = params.size ?? 20;
  const start = (params.page - 1) * size;
  return {
    items: filtered.slice(start, start + size),
    total: filtered.length,
  };
}

/** 发起充值 */
export async function rechargeApi(
  amount: number,
  channel: string,
): Promise<{ id: string; status: string }> {
  if (apiMode === 'real') {
    const backendWallet = await requestBackendMemberDomain<BackendWalletSummaryResponse>(
      H5_API_ENDPOINTS.wallet.recharge,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ amount }),
      },
    );
    if (backendWallet) {
      return { id: "", status: "completed" };
    }
  }
  // Mock fallback
  await createRechargeOrder(amount);
  return { id: `mock_recharge_${Date.now()}`, status: 'completed' };
}

/** 查询充值状态 */
export async function getRechargeStatusApi(id: string): Promise<string> {
  if (apiMode === 'real') {
    return "completed";
  }
  return 'completed';
}

/** 获取未读通知数量 */
export async function getNotificationsCountApi(): Promise<{ unreadCount: number }> {
  if (apiMode === 'real') {
    const res = await h5Api.get<{ unreadCount: number }>(H5_API_ENDPOINTS.notificationsUnreadCount);
    return res.data;
  }
  // Mock fallback
  const session = getRequiredSession();
  const state = getStateForAccount(session.accountId);
  return { unreadCount: getUnreadMessageCount(state.messages) };
}

// ─── Withdraw API ────────────────────────────────────────────────

/** 获取提现记录（分页） */
export async function getWithdrawalsApi(params: {
  page?: number;
  size?: number;
}): Promise<{ items: H5WithdrawRequest[]; total: number }> {
  if (apiMode === 'real') {
    const backendWithdrawals = await requestBackendMemberDomain<BackendWithdrawalResponse[]>(
      H5_API_ENDPOINTS.withdrawals.list,
    );
    if (backendWithdrawals) {
      const requests = backendWithdrawals.map((item) => mapWithdrawalFromBackend(item));
      const page = params.page ?? 1;
      const size = params.size ?? 20;
      return {
        items: requests.slice((page - 1) * size, page * size),
        total: requests.length,
      };
    }
  }
  const session = getRequiredSession();
  const state = getStateForAccount(session.accountId);
  const requests = [...state.withdrawRequests].sort((left, right) =>
    right.createdAt.localeCompare(left.createdAt),
  );
  const page = params.page ?? 1;
  const size = params.size ?? 20;
  return { items: requests.slice((page - 1) * size, page * size), total: requests.length };
}

/** 提交提现申请 */
export async function submitWithdrawApi(
  amount: number,
  accountInfo?: string,
): Promise<{ id: string; status: string }> {
  if (apiMode === 'real') {
    const res = await h5Api.post(H5_API_ENDPOINTS.withdrawals.list, { amount, account_info: accountInfo });
    return res.data;
  }
  // Mock fallback
  await createWithdrawRequest(amount);
  return { id: `mock-${Date.now()}`, status: 'submitted' };
}

/** 获取提现详情 */
export async function getWithdrawDetailApi(id: string): Promise<H5WithdrawRequest | null> {
  if (apiMode === 'real') {
    const res = await h5Api.get(H5_API_ENDPOINTS.withdrawals.detail(id));
    return res.data;
  }
  const session = getRequiredSession();
  const state = getStateForAccount(session.accountId);
  return state.withdrawRequests.find((r) => r.id === id) ?? null;
}

// ─── Mock helper for verification & WhatsApp (localStorage) ──────

function getMockVerificationStatus(): {
  status: string;
  name?: string;
  idNumber?: string;
  photos?: string[];
  submittedAt?: string;
  reviewNote?: string;
} {
  const raw = isBrowser() ? window.localStorage.getItem('mock_verification_status') : null;
  if (raw) {
    try {
      return JSON.parse(raw);
    } catch {
      /* ignore */
    }
  }
  return { status: 'unverified' };
}

function getMockWhatsAppBindingStatus(): {
  status: string;
  phone?: string;
  requestedAt?: string;
  id?: string;
} {
  const raw = isBrowser() ? window.localStorage.getItem('mock_whatsapp_binding') : null;
  if (raw) {
    try {
      return JSON.parse(raw);
    } catch {
      /* ignore */
    }
  }
  return { status: 'not_bound' };
}

// ─── Verification API (mock/real dual-mode) ─────────────────────

/** 获取认证状态 */
export async function getVerificationStatusApi(): Promise<{
  status: string;
  name?: string;
  idNumber?: string;
  photos?: string[];
  submittedAt?: string;
  reviewNote?: string;
}> {
  if (apiMode === 'real') {
    const res = await h5Api.get('/api/h5/verifications/status');
    return res.data;
  }
  return getMockVerificationStatus();
}

/** 提交认证 */
export async function submitVerificationApi(data: {
  name: string;
  idNumber?: string;
  photos?: string[];
}): Promise<{ id: string; status: string }> {
  if (apiMode === 'real') {
    const res = await h5Api.post('/api/h5/verifications', data);
    return res.data;
  }
  // Mock: persist to localStorage
  const mockId = `mock-${Date.now()}`;
  if (isBrowser()) {
    window.localStorage.setItem(
      'mock_verification_status',
      JSON.stringify({ status: 'pending', name: data.name, idNumber: data.idNumber, photos: data.photos, submittedAt: nowIso() }),
    );
  }
  return { id: mockId, status: 'pending' };
}

/** 上传认证照片 */
export async function uploadVerificationPhotosApi(id: string, files: File[]): Promise<boolean> {
  if (apiMode === 'real') {
    const form = new FormData();
    files.forEach((f) => form.append('photos', f));
    await h5Api.post(`/api/h5/verifications/${id}/photos`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return true;
  }
  return true;
}

// ─── WhatsApp Binding API (mock/real dual-mode) ─────────────────

/** 获取 WhatsApp 绑定状态 */
export async function getWhatsAppBindingStatusApi(): Promise<{
  status: string;
  phone?: string;
  requestedAt?: string;
  id?: string;
}> {
  if (apiMode === 'real') {
    const res = await h5Api.get('/api/h5/whatsapp-bindings/status');
    return res.data;
  }
  return getMockWhatsAppBindingStatus();
}

/** 发起 WhatsApp 绑定 */
export async function startWhatsAppBindingApi(phone: string): Promise<{ id: string; status: string }> {
  if (apiMode === 'real') {
    const res = await h5Api.post('/api/h5/whatsapp-bindings', { phone });
    return res.data;
  }
  // Mock: persist to localStorage
  const mockId = `mock-${Date.now()}`;
  if (isBrowser()) {
    window.localStorage.setItem(
      'mock_whatsapp_binding',
      JSON.stringify({ status: 'pending', phone, requestedAt: nowIso(), id: mockId }),
    );
  }
  return { id: mockId, status: 'pending' };
}

// ─── Mock helper for notification/ticket API fallback ──────────────────

function getMessages(): H5MessageItem[] {
  const session = getRequiredSession();
  const state = getStateForAccount(session.accountId);
  return [...state.messages].sort((left, right) => right.createdAt.localeCompare(left.createdAt));
}

const mockTicketsStore: Array<{
  id: string;
  category: string;
  priority: string;
  subject: string;
  description: string;
  status: string;
  created_at: string;
  updated_at: string;
  last_reply_at: string | null;
  messages: Array<{ id: string; sender_type: string; sender_name: string; content: string; created_at: string; internal_only: boolean }>;
}> = [];

function getSupportTickets(): unknown[] {
  return [...mockTicketsStore];
}

function getSupportTicketById(id: string): unknown | null {
  return mockTicketsStore.find((t) => t.id === id) ?? null;
}

function addTicketReply(ticketId: string, message: string): boolean {
  const ticket = mockTicketsStore.find((t) => t.id === ticketId);
  if (!ticket) return false;
  ticket.messages.push({
    id: 'msg-' + Date.now(),
    sender_type: 'user',
    sender_name: 'user',
    content: message,
    created_at: new Date().toISOString(),
    internal_only: false,
  });
  ticket.last_reply_at = new Date().toISOString();
  ticket.updated_at = new Date().toISOString();
  return true;
}

// ─── H52-012: Notification + Ticket API functions ──────────────────

export async function getNotificationsApi(params: { page?: number; size?: number }): Promise<{ items: H5MessageItem[]; total: number }> {
  if (apiMode === 'real') {
    const res = await h5Api.get('/api/h5/notifications', { params });
    return res.data;
  }
  const msgs = getMessages();
  const page = params.page ?? 1;
  const size = params.size ?? 20;
  return { items: msgs.slice((page - 1) * size, page * size), total: msgs.length };
}

export async function markNotificationReadApi(id: string): Promise<boolean> {
  if (apiMode === 'real') {
    await h5Api.put('/api/h5/notifications/' + encodeURIComponent(id) + '/read');
    return true;
  }
  return markMessageRead(id) as unknown as boolean;
}

export async function markAllNotificationsReadApi(): Promise<boolean> {
  if (apiMode === 'real') {
    await h5Api.put('/api/h5/notifications/read-all');
    return true;
  }
  return markAllMessagesRead() as unknown as boolean;
}

export async function getTicketsApi(params: { page?: number; size?: number }): Promise<{ items: unknown[]; total: number }> {
  if (apiMode === 'real') {
    const res = await h5Api.get('/api/h5/tickets', { params });
    return res.data;
  }
  const tickets = getSupportTickets();
  const page = params.page ?? 1;
  const size = params.size ?? 20;
  return { items: tickets.slice((page - 1) * size, page * size), total: tickets.length };
}

export async function createTicketApi(data: { category: string; priority: string; subject: string; description: string }): Promise<{ id: string }> {
  if (apiMode === 'real') {
    const res = await h5Api.post('/api/h5/tickets', data);
    return res.data;
  }
  const now = new Date().toISOString();
  const id = 'mock-' + Date.now();
  mockTicketsStore.unshift({
    id,
    category: data.category,
    priority: data.priority,
    subject: data.subject,
    description: data.description,
    status: 'open',
    created_at: now,
    updated_at: now,
    last_reply_at: now,
    messages: [{
      id: id + '-msg-0',
      sender_type: 'user',
      sender_name: 'user',
      content: data.description,
      created_at: now,
      internal_only: false,
    }],
  });
  return { id };
}

export async function getTicketDetailApi(id: string): Promise<unknown | null> {
  if (apiMode === 'real') {
    const res = await h5Api.get('/api/h5/tickets/' + encodeURIComponent(id));
    return res.data;
  }
  return getSupportTicketById(id);
}

export async function replyToTicketApi(ticketId: string, message: string): Promise<boolean> {
  if (apiMode === 'real') {
    await h5Api.post('/api/h5/tickets/' + encodeURIComponent(ticketId) + '/messages', { message });
    return true;
  }
  return addTicketReply(ticketId, message);
}

function getMockLeaderboard(): { rankings: { rank: number; userId: string; score: number }[] } {
  return {
    rankings: [
      { rank: 1, userId: "12864472", score: 5200 },
      { rank: 2, userId: "87342155", score: 4760 },
      { rank: 3, userId: "54021863", score: 3980 },
      { rank: 4, userId: "74190538", score: 3510 },
    ],
  };
}

export async function getLeaderboardApi(): Promise<{ rankings: { rank: number; userId: string; score: number }[] }> {
  if (apiMode === 'real') {
    const res = await h5Api.get('/api/h5/leaderboard');
    return res.data;
  }
  return getMockLeaderboard();
}

export async function getPromotionsApi(): Promise<{ items: unknown[] }> {
  if (apiMode === 'real') {
    const res = await h5Api.get('/api/h5/promotions');
    return res.data;
  }
  return { items: [] };
}

export async function joinPromotionApi(id: string): Promise<{ success: boolean }> {
  if (apiMode === 'real') {
    const res = await h5Api.post(`/api/h5/promotions/${id}/join`);
    return res.data;
  }
  return { success: true };
}

// ─── Mock helpers for commerce API ──────────────────────────────

function getMockOrders(params: { page?: number; size?: number; status?: string }): { items: H5MemberOrder[]; total: number } {
  const session = getRequiredSession();
  const state = getStateForAccount(session.accountId);
  let filtered = state.orders;
  if (params.status && params.status !== 'all') {
    filtered = filtered.filter((o) => o.status === params.status);
  }
  const page = params.page ?? 1;
  const size = params.size ?? 20;
  const sorted = [...filtered].sort((a, b) => b.createdAt.localeCompare(a.createdAt));
  return { items: sorted.slice((page - 1) * size, page * size), total: sorted.length };
}

// ─── H52-013: Commerce API functions ──────────────────────────────

export async function getProductsApi(): Promise<{ id: string; name: string; price: number; image_url: string; }[]> {
  if (apiMode === 'real') {
    const res = await h5Api.get('/api/h5/commerce/products');
    return res.data.items ?? res.data;
  }
  return [];
}

export async function getProductDetailApi(id: string): Promise<unknown | null> {
  if (apiMode === 'real') {
    const res = await h5Api.get(`/api/h5/commerce/products/${id}`);
    return res.data;
  }
  return null;
}

export async function createOrderApi(productId: string, quantity: number): Promise<{ id: string }> {
  if (apiMode === 'real') {
    const res = await h5Api.post('/api/h5/commerce/orders', { product_id: productId, quantity });
    return res.data;
  }
  return { id: `mock-${Date.now()}` };
}

export async function getOrdersApi(params: { page?: number; size?: number; status?: string }): Promise<{ items: unknown[]; total: number }> {
  if (apiMode === 'real') {
    const res = await h5Api.get('/api/h5/commerce/orders', { params });
    return res.data;
  }
  return getMockOrders(params);
}

export async function getOrderDetailApi(id: string): Promise<unknown | null> {
  if (apiMode === 'real') {
    const res = await h5Api.get(`/api/h5/commerce/orders/${id}`);
    return res.data;
  }
  return null;
}

export async function getLogisticsApi(orderId: string): Promise<{ status: string; tracking_number?: string; steps: unknown[] }> {
  if (apiMode === 'real') {
    const res = await h5Api.get(`/api/h5/commerce/orders/${orderId}/logistics`);
    return res.data;
  }
  return { status: 'pending', steps: [] };
}

// ─── H52-014: Fragment + Mailing API functions ──────────────────

function getMockFragments(): { items: unknown[]; overview: unknown } {
  const session = getRequiredSession();
  const state = getStateForAccount(session.accountId);
  const overview = buildFragmentOverview(state);
  return {
    items: overview.inventory,
    overview,
  };
}

export async function getFragmentsApi(): Promise<{ items: unknown[]; overview: unknown }> {
  if (apiMode === 'real') {
    const res = await h5Api.get('/api/h5/fragments');
    return res.data;
  }
  return getMockFragments();
}

export async function getFragmentDetailApi(id: string): Promise<unknown | null> {
  if (apiMode === 'real') {
    const res = await h5Api.get('/api/h5/fragments/' + encodeURIComponent(id));
    return res.data;
  }
  return null;
}

export async function checkInFragmentApi(): Promise<{ success: boolean; fragment: unknown }> {
  if (apiMode === 'real') {
    const res = await h5Api.post('/api/h5/fragments/check-in');
    return res.data;
  }
  return { success: true, fragment: { id: 'mock-' + Date.now() } };
}

export async function exchangeFragmentsApi(data: { item_id: string; address: unknown }): Promise<{ id: string; status: string }> {
  if (apiMode === 'real') {
    const res = await h5Api.post('/api/h5/fragments/exchanges', data);
    return res.data;
  }
  return { id: 'mock-' + Date.now(), status: 'submitted' };
}

export async function getShippingStatusApi(exchangeId: string): Promise<{ status: string; tracking_number?: string }> {
  if (apiMode === 'real') {
    const res = await h5Api.get('/api/h5/rewards/shipping/' + encodeURIComponent(exchangeId));
    return res.data;
  }
  return { status: 'pending' };
}

export async function subscribeMailingApi(email: string): Promise<boolean> {
  if (apiMode === 'real') {
    await h5Api.post('/api/h5/mailing/subscribe', { email });
    return true;
  }
  return true;
}

export async function unsubscribeMailingApi(email: string): Promise<boolean> {
  if (apiMode === 'real') {
    await h5Api.post('/api/h5/mailing/unsubscribe', { email });
    return true;
  }
  return true;
}

export const H5_API_ENDPOINTS = {
  wallet: {
    balance: '/api/h5/wallet',
    transactions: '/api/h5/wallet/transactions',
    recharge: '/api/h5/wallet/recharges',
    rechargeStatus: (id: string) => `/api/h5/wallet/recharge/${id}/status`,
  },
  withdrawals: {
    list: '/api/h5/withdrawals',
    detail: (id: string) => `/api/h5/withdrawals/${id}`,
  },
  tasks: {
    list: '/api/h5/tasks',
    detail: (id: string) => `/api/h5/tasks/${id}`,
    submit: (id: string) => `/api/h5/tasks/${id}/submit`,
    proof: (id: string) => `/api/h5/tasks/${id}/proof`,
  },
  notifications: '/api/h5/notifications',
  notificationsUnreadCount: '/api/h5/notifications?unread=true&count_only=true',
  tickets: {
    list: '/api/h5/tickets',
    detail: (id: string) => `/api/h5/tickets/${id}`,
  },
  verifications: {
    list: '/api/h5/verifications',
    photos: (id: string) => `/api/h5/verifications/${id}/photos`,
  },
  whatsappBindings: '/api/h5/whatsapp-bindings',
  commerce: {
    products: '/api/h5/commerce/products',
    orders: '/api/h5/commerce/orders',
  },
  fragments: '/api/h5/fragments',
  promotions: '/api/h5/promotions',
  leaderboard: '/api/h5/leaderboard',
} as const;

// ─── H52-016: Chat message types ──────────────────────────────

export type H5ChatMessage = {
  id: string;
  content: string;
  type: 'text' | 'image' | 'system';
  image_url?: string;
  direction: 'inbound' | 'outbound';
  status: 'sending' | 'sent' | 'delivered' | 'read';
  timestamp: string;
};

// ─── H52-016: Chat API functions ──────────────────────────────

export async function getMessagesApi(params: { page?: number; size?: number; conversation_id?: string }): Promise<{ items: H5ChatMessage[]; total: number }> {
  if (apiMode === 'real') {
    const res = await h5Api.get('/api/h5/messages', { params });
    return res.data;
  }
  // Mock: return sample messages
  const mockMsgs: H5ChatMessage[] = [
    { id: 'm1', content: getSeedDataText("chatWelcomeInbound"), type: 'text', direction: 'inbound', status: 'read', timestamp: new Date(Date.now() - 3600000).toISOString() },
    { id: 'm2', content: getSeedDataText("chatWelcomeOutbound"), type: 'text', direction: 'outbound', status: 'read', timestamp: new Date(Date.now() - 3500000).toISOString() },
    { id: 'm3', content: getSeedDataText("chatWelcomeReply"), type: 'text', direction: 'inbound', status: 'read', timestamp: new Date(Date.now() - 3400000).toISOString() },
  ];
  const page = params.page ?? 1;
  const size = params.size ?? 20;
  return { items: mockMsgs.slice((page - 1) * size, page * size), total: mockMsgs.length };
}

export async function sendMessageApi(
  conversationId: string,
  content: string,
  type: string = 'text',
  imageUrl?: string,
): Promise<H5ChatMessage> {
  if (apiMode === 'real') {
    const res = await h5Api.post('/api/h5/messages', {
      conversation_id: conversationId,
      content,
      type,
      image_url: imageUrl,
    });
    return res.data;
  }
  return {
    id: `mock-${Date.now()}`,
    content,
    type: type as 'text' | 'image',
    image_url: imageUrl,
    direction: 'outbound',
    status: 'sent',
    timestamp: new Date().toISOString(),
  };
}

// ── Sign-in Types ──

export type H5SignInStatus = {
  consecutiveDays: number;
  todaySignedIn: boolean;
  goalDays: number;
  goalReward: number;
  isCompleted: boolean;
};

// ── Task Instance Types ──

export type H5TaskProductStatus = "pending" | "available" | "running" | "completed" | "failed";

export type H5TaskProduct = {
  id: string;
  productName: string;
  imageUrl: string;
  price: number;
  currency: string;
  status: H5TaskProductStatus;
};

export type H5TaskInstance = {
  id: string;
  title: string;
  description: string;
  type: H5TaskPackageType;
  status: H5TaskPackageStatus;
  rewardRatio: number;
  rewardAmount: number;
  products: H5TaskProduct[];
  completedCount: number;
  totalCount: number;
  systemBalance: number;
  totalCommission?: number;
  currentCommission?: number;
  countdownSeconds?: number;
  completionWindowHours?: number;
};

// ── Invite Types ──

export type H5InviteRecord = {
  id: string;
  userIdMasked: string;
  type: "registration" | "registration_recharge";
  createdAt: string;
  rewardAmount: number;
};

export type H5InviteInfo = {
  inviteLink: string;
  invitedCount: number;
  earnedAmount: number;
  maxInvites: number;
  remainingInvites: number;
};

// ── Mock Sign-In ──

const SIGN_IN_GOAL_DAYS = 7;
const SIGN_IN_GOAL_REWARD = 5;

function getMockSignInStatus(): H5SignInStatus {
  const session = getRequiredSession();
  const state = getStateForAccount(session.accountId);
  const checked = state.checkedInDate === todayKey();
  const consecutiveDays = checked ? 5 : 3;
  return {
    consecutiveDays,
    todaySignedIn: checked,
    goalDays: SIGN_IN_GOAL_DAYS,
    goalReward: SIGN_IN_GOAL_REWARD,
    isCompleted: consecutiveDays >= SIGN_IN_GOAL_DAYS,
  };
}

// ── Mock Task Instance ──

function getMockTaskInstances(): H5TaskInstance[] {
  const session = getRequiredSession();
  const state = getStateForAccount(session.accountId);
  const packages = state.taskPackages.filter(
    p => p.status === "pending_claim" || p.status === "active" || p.status === "completed" || p.status === "expired",
  );
  return packages.map((pkg) => {
    const completedCount = pkg.items.filter(i => i.completed_at).length;
    const totalCount = pkg.items.length;
    const totalCommission = pkg.items.reduce((sum, item) => sum + item.price * pkg.rewardRatio, 0);
    const currentCommission = pkg.items
      .filter((item) => Boolean(item.completed_at))
      .reduce((sum, item) => sum + item.price * pkg.rewardRatio, 0);
    const countdownSeconds = pkg.status === "pending_claim"
      ? pkg.completionWindowHours * 3600
      : pkg.expiresAt
        ? Math.max(0, Math.floor((new Date(pkg.expiresAt).getTime() - Date.now()) / 1000))
        : 0;
    const products: H5TaskProduct[] = pkg.items.map((item, idx) => {
      let status: H5TaskProductStatus = "pending";
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
        status,
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
      completionWindowHours: pkg.completionWindowHours,
    };
  });
}

function getMockTaskInstanceDetail(instanceId: string): H5TaskInstance | null {
  const instances = getMockTaskInstances();
  return instances.find(i => i.id === instanceId) ?? null;
}

// ── Mock Invite ──

function getMockInviteLink(): string {
  const session = getRequiredSession();
  const origin = typeof window !== "undefined" ? window.location.origin : "http://127.0.0.1:5173";
  const url = new URL("/h5/register", origin);
  url.searchParams.set("invite_code", session.inviteCode);
  return url.toString();
}

function getMockInviteInfo(): H5InviteInfo {
  const link = getMockInviteLink();
  return {
    inviteLink: link,
    invitedCount: 8,
    earnedAmount: 31,
    maxInvites: 20,
    remainingInvites: 12,
  };
}

function getMockInviteRecords(): H5InviteRecord[] {
  return [
    { id: "inv1", userIdMasked: "U****91", type: "registration", createdAt: "2026-06-10T09:16:00.000Z", rewardAmount: 2 },
    { id: "inv2", userIdMasked: "U****52", type: "registration_recharge", createdAt: "2026-06-08T10:42:00.000Z", rewardAmount: 5 },
    { id: "inv3", userIdMasked: "U****73", type: "registration", createdAt: "2026-06-05T12:08:00.000Z", rewardAmount: 2 },
    { id: "inv4", userIdMasked: "U****34", type: "registration", createdAt: "2026-06-03T14:30:00.000Z", rewardAmount: 2 },
    { id: "inv5", userIdMasked: "U****25", type: "registration_recharge", createdAt: "2026-06-01T08:00:00.000Z", rewardAmount: 5 },
  ];
}

// ── Exported API Functions ──

export async function getSignInStatusApi(): Promise<H5SignInStatus> {
  if (apiMode === 'real') {
    const res = await h5Api.get('/api/h5/sign-in/status');
    return res.data;
  }
  return getMockSignInStatus();
}

export async function performSignInApi(): Promise<H5SignInStatus> {
  if (apiMode === 'real') {
    const res = await h5Api.post('/api/h5/sign-in');
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
    isCompleted: false,
  };
}

export async function getTaskInstancesApi(): Promise<H5TaskInstance[]> {
  if (apiMode === 'real') {
    const res = await h5Api.get('/api/h5/task-instances', { params: { user_id: 'me' } });
    return res.data;
  }
  return getMockTaskInstances();
}

export async function getTaskInstanceDetailApi(id: string): Promise<H5TaskInstance | null> {
  if (apiMode === 'real') {
    const res = await h5Api.get(`/api/h5/task-instances/${encodeURIComponent(id)}`);
    return res.data;
  }
  return getMockTaskInstanceDetail(id);
}

export async function startProductApi(instanceId: string, productId: string): Promise<{ success: boolean; reason?: string }> {
  if (apiMode === 'real') {
    const res = await h5Api.post(`/api/h5/task-instances/${encodeURIComponent(instanceId)}/start-product`, { product_id: productId });
    return res.data;
  }
  // Mock: deduct balance and mark product as completed
  const session = getRequiredSession();
  updateStateForAccount(session.accountId, (draft) => {
    const pkg = draft.taskPackages.find(p => p.id === instanceId);
    if (!pkg) return draft;
    const item = pkg.items.find(i => i.id === productId);
    if (!item) return draft;
    if (draft.wallet.systemBalance < item.price) {
      throw createServiceError("balanceInsufficient");
    }
    draft.wallet.systemBalance -= item.price;
    item.completed_at = new Date().toISOString();
    return draft;
  });
  return { success: true };
}

export async function retryProductApi(instanceId: string, productId: string): Promise<{ success: boolean; reason?: string }> {
  if (apiMode === 'real') {
    const res = await h5Api.post(`/api/h5/task-instances/${encodeURIComponent(instanceId)}/retry-product`, { product_id: productId });
    return res.data;
  }
  return startProductApi(instanceId, productId);
}

export async function getInviteInfoApi(): Promise<H5InviteInfo> {
  if (apiMode === 'real') {
    const res = await h5Api.get('/api/h5/invites/my-link');
    return res.data;
  }
  return getMockInviteInfo();
}

export async function getInviteRecordsApi(): Promise<H5InviteRecord[]> {
  if (apiMode === 'real') {
    const res = await h5Api.get('/api/h5/invites/my-records');
    return res.data;
  }
  return getMockInviteRecords();
}

// ── Request deduplication utility ──
const requestCache = new Map<string, { promise: Promise<unknown>; timestamp: number }>();
const REQUEST_DEDUP_TTL = 5000; // 5 seconds

async function dedupRequest<T>(key: string, fetcher: () => Promise<T>): Promise<T> {
  const cached = requestCache.get(key);
  if (cached && Date.now() - cached.timestamp < REQUEST_DEDUP_TTL) {
    return cached.promise as Promise<T>;
  }
  const promise = fetcher();
  requestCache.set(key, { promise, timestamp: Date.now() });
  promise.finally(() => {
    // Clean up after TTL
    setTimeout(() => {
      if (requestCache.get(key)?.promise === promise) {
        requestCache.delete(key);
      }
    }, REQUEST_DEDUP_TTL);
  });
  return promise;
}
