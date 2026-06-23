import { createElement, type JSX } from "react";
import {
  AppstoreOutlined,
  AuditOutlined,
  BellOutlined,
  GiftOutlined,
  LinkOutlined,
  LockOutlined,
  MessageOutlined,
  ShoppingOutlined,
  TrophyOutlined,
  UserOutlined,
  WalletOutlined,
} from "@ant-design/icons";

import type {
  H5MemberVerificationRequest,
  H5MessageItem,
  H5TaskPackage,
  H5WithdrawRequest,
} from "../../services/h5Member";
import type { SupportTicketCategory, SupportTicketPriority, SupportTicketStatus } from "../../services/h5";
import { getSupportTicketStatusLabel } from "../../services/h5";
import { t } from "./i18n";

// Keep runtime H5 helpers in a plain .ts module so Vite can hot-update utilities without full shell invalidation.
export function formatTimestamp(value: string | null): string {
  if (!value) return t("common.none");
  return new Date(value).toLocaleString(getCurrentLocale());
}

export function formatMoney(value: number, currency = "USD"): string {
  return new Intl.NumberFormat(getCurrentLocale(), {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  }).format(value);
}

export function getCurrentLocale(): string {
  if (typeof window === "undefined") {
    return "zh-CN";
  }

  const saved = window.localStorage?.getItem("h5-lang");
  if (saved) {
    return saved;
  }

  if (typeof document !== "undefined" && document.documentElement.lang) {
    return document.documentElement.lang;
  }

  if (typeof navigator !== "undefined" && navigator.language) {
    return navigator.language;
  }

  return "zh-CN";
}

const RTL_LOCALE_PATTERN = /^(ar|fa|he|ps|ur)(-|$)/i;

export function getLocaleDirection(locale = getCurrentLocale()): "ltr" | "rtl" {
  return RTL_LOCALE_PATTERN.test(locale) ? "rtl" : "ltr";
}

export function syncDocumentLocale(locale = getCurrentLocale()): void {
  if (typeof document === "undefined") {
    return;
  }

  document.documentElement.lang = locale;
  document.documentElement.dir = getLocaleDirection(locale);
}

export function formatPercentage(value: number): string {
  return `${(value * 100).toFixed(0)}%`;
}

export function formatCountdown(seconds: number): string {
  const total = Math.max(0, seconds);
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const secs = total % 60;
  return `${hours.toString().padStart(2, "0")}:${minutes.toString().padStart(2, "0")}:${secs
    .toString()
    .padStart(2, "0")}`;
}

export function getTaskPackageStatusLabel(status: H5TaskPackage["status"]): string {
  if (status === "pending_claim") return t("tasks.statusPendingClaim");
  if (status === "active") return t("tasks.statusActive");
  if (status === "completed") return t("tasks.statusCompleted");
  return t("tasks.statusExpired");
}

export function getTaskPackageTypeLabel(type: H5TaskPackage["type"]): string {
  if (type === "rookie") return t("tasks.typeRookie");
  if (type === "growth") return t("tasks.typeGrowth");
  return t("tasks.typePromotion");
}

export function getMessageCategoryLabel(category: H5MessageItem["category"]): string {
  if (category === "task") return t("messages.categoryTask");
  if (category === "wallet") return t("messages.categoryWallet");
  if (category === "order") return t("messages.categoryOrder");
  if (category === "support") return t("messages.categorySupport");
  if (category === "fragment") return t("messages.categoryFragment");
  return t("messages.categorySystem");
}

export function getWithdrawStatusLabel(status: H5WithdrawRequest["status"]): string {
  if (status === "submitted") return t("withdraw.statusSubmitted");
  if (status === "reviewing") return t("withdraw.statusReviewing");
  if (status === "approved") return t("withdraw.statusApproved");
  if (status === "rejected") return t("withdraw.statusRejected");
  return t("withdraw.statusPaid");
}

export function getShippingStatusLabel(status: string): string {
  if (status === "pending_address") return t("fragments.shippingPendingAddress");
  if (status === "submitted") return t("fragments.shippingSubmitted");
  if (status === "packing") return t("fragments.shippingPacking");
  if (status === "shipped") return t("fragments.shippingShipped");
  if (status === "delivered") return t("fragments.shippingDelivered");
  return t("common.done");
}

export function getVerificationStatusLabel(status: string): string {
  if (status === "pending" || status === "under_review") return t("verification.statusUnderReview");
  if (status === "approved" || status === "verified") return t("verification.statusApproved");
  if (status === "rejected") return t("verification.statusRejected");
  return t("verification.statusNotSubmitted");
}

export function getPurchasePhaseLabel(
  phase: "create_order" | "paying" | "settling" | "success" | "failed",
): string {
  if (phase === "create_order") return t("purchase.phaseCreateOrder");
  if (phase === "paying") return t("purchase.phasePaying");
  if (phase === "settling") return t("purchase.phaseSettling");
  if (phase === "success") return t("purchase.phaseSuccess");
  return t("purchase.phaseFailed");
}

export function getFragmentStageContent({
  canExchangeFragments,
  latestShippingStatus,
}: {
  canExchangeFragments: boolean;
  latestShippingStatus: string | null;
}): { title: string; description: string } {
  if (latestShippingStatus) {
    const statusLabel = getShippingStatusLabel(latestShippingStatus);
    return {
      title:
        latestShippingStatus === "pending_address"
          ? t("fragments.stageAddress")
          : t("fragments.stageShipping"),
      description: t("fragments.stageProgress", { status: statusLabel }),
    };
  }

  if (canExchangeFragments) {
    return {
      title: t("fragments.stageAddress"),
      description: t("fragments.stageReady"),
    };
  }

  return {
    title: t("fragments.stageCollect"),
    description: t("fragments.stageKeepCollecting"),
  };
}

export function getVerificationRequestStatusLabel(status: string): string {
  if (status === "pending" || status === "under_review") return t("verification.statusUnderReview");
  if (status === "approved" || status === "verified") return t("verification.statusApproved");
  if (status === "rejected") return t("verification.statusRejected");
  if (status === "cancelled") return t("verification.statusCancelled");
  if (status === "not_submitted") return t("verification.statusNotSubmitted");
  return t("verification.statusOther");
}

export function getVerificationRequestTone(status: string): "default" | "active" | "success" | "danger" {
  if (status === "pending" || status === "under_review") return "active";
  if (status === "approved" || status === "verified") return "success";
  if (status === "rejected" || status === "cancelled") return "danger";
  return "default";
}

export function getVerificationRequestTypeLabel(requestType: string): string {
  if (requestType === "identity") return t("verification.identity");
  return requestType || t("common.unknown");
}

export function isVerificationRequestActive(request: H5MemberVerificationRequest): boolean {
  return ["pending", "under_review"].includes(request.status);
}

export function getTicketStatusLabel(status: SupportTicketStatus): string {
  return getTicketStatusLabels()[status] ?? status;
}

export function getRouteTitle(route: { page: string }): string {
  const titles: Record<string, string> = {
    home: t("shell.routeHome"),
    tasks: t("shell.routeTasks"),
    "task-package": t("shell.routeTaskPackage"),
    messages: t("shell.routeMessages"),
    profile: t("shell.routeProfile"),
    settings: t("shell.routeSettings"),
    verification: t("shell.routeVerification"),
    recharge: t("shell.tabEarnings"),
    withdraw: t("shell.routeWithdraw"),
    orders: t("shell.routeOrders"),
    tickets: t("shell.routeTickets"),
    "ticket-new": t("shell.routeTicketNew"),
    "ticket-detail": t("shell.routeTicketDetail"),
    fragments: t("shell.routeFragments"),
    leaderboard: t("shell.routeLeaderboard"),
    promotion: t("shell.routePromotion"),
    invite: t("shell.routeInvite"),
    whatsapp: t("shell.routeWhatsapp"),
    register: t("shell.routeRegister"),
    login: t("shell.routeLogin"),
  };
  return titles[route.page] ?? t("auth.login");
}

export function getRouteSubtitle(
  route: { page: string },
  options: { tagline?: string | null; brandName?: string | null },
): string {
  if (route.page === "home") {
    const tagline = options.tagline?.trim();
    const normalizedTagline = tagline?.replace(/\s+/g, " ").toLowerCase();
    const deprecatedHomeTaglines = new Set([
      "task packages, wallet, support, and fragments in one place.",
      "任务、钱包、消息与碎片奖励一站式入口",
    ]);

    if (!tagline || (normalizedTagline && deprecatedHomeTaglines.has(normalizedTagline))) {
      return t("shell.subtitleHomeDefault");
    }

    return tagline;
  }

  const subtitles: Record<string, string> = {
    messages: t("shell.subtitleMessages"),
    tasks: t("shell.subtitleTasks"),
    profile: t("shell.subtitleProfile"),
    orders: t("shell.subtitleOrders"),
    tickets: t("shell.subtitleTickets"),
    recharge: t("shell.subtitleEarnings"),
    withdraw: t("shell.subtitleWithdraw"),
    settings: t("shell.subtitleSettings"),
    promotion: t("shell.subtitlePromotion"),
    verification: t("shell.subtitleVerification"),
    fragments: t("shell.subtitleFragments"),
    leaderboard: t("shell.subtitleLeaderboard"),
    whatsapp: t("shell.subtitleWhatsapp"),
    invite: t("shell.subtitleInvite"),
  };

  const brandName = options.brandName?.trim();
  return subtitles[route.page] ?? brandName ?? t("shell.brandName");
}

export function getProfileLinkIcon(label: string): JSX.Element {
  const normalized = label.toLowerCase();
  if (normalized.includes("wallet") || normalized.includes("recharge") || normalized.includes("withdraw")) {
    return createElement(WalletOutlined);
  }
  if (normalized.includes("promotion")) return createElement(LinkOutlined);
  if (normalized.includes("verification") || normalized.includes("ticket")) return createElement(AuditOutlined);
  if (normalized.includes("order")) return createElement(ShoppingOutlined);
  if (normalized.includes("contact")) return createElement(MessageOutlined);
  if (normalized.includes("leaderboard")) return createElement(TrophyOutlined);
  if (normalized.includes("fragment")) return createElement(GiftOutlined);
  if (normalized.includes("whatsapp")) return createElement(LinkOutlined);
  if (normalized.includes("password")) return createElement(LockOutlined);
  return createElement(UserOutlined);
}

export function getProfileLinkGroup(label: string): string {
  const normalized = label.toLowerCase();
  if (normalized.includes("wallet") || normalized.includes("recharge") || normalized.includes("withdraw") || normalized.includes("leaderboard")) return t("shell.groupFinancial");
  if (normalized.includes("promotion")) return t("shell.groupPromotion");
  if (normalized.includes("verification") || normalized.includes("ticket") || normalized.includes("contact")) return t("shell.groupPlatform");
  if (normalized.includes("order") || normalized.includes("fragment")) return t("shell.groupRecords");
  return t("shell.groupPlatform");
}

export function buildH5Path(pathname: string, siteKey: string, extraParams?: Record<string, string>): string {
  const url = new URL(`http://localhost${pathname}`);
  url.searchParams.set("site_key", siteKey);
  if (extraParams) {
    for (const [key, value] of Object.entries(extraParams)) {
      if (value.trim()) {
        url.searchParams.set(key, value);
      }
    }
  }
  return `${url.pathname}${url.search}`;
}

export function canReplyToTicket(status: SupportTicketStatus): boolean {
  return !["resolved", "rejected", "closed", "cancelled"].includes(status);
}

export type PurchasePhaseState = {
  phase: string;
  progress: number;
  tone: "running" | "success" | "failed";
};

export type ToastItem = {
  key: string;
  message: string;
  tone: "notice" | "error";
  duration: number;
};

export function getPurchaseStageMeta(
  state: PurchasePhaseState,
): { tone: "ready" | "running" | "success" | "failed"; title: string; detail: string; badge: string } {
  if (state.progress <= 0) {
    return {
      tone: "ready",
      title: t("purchase.readyTitle"),
      detail: t("purchase.readyDetail"),
      badge: t("purchase.readyBadge"),
    };
  }
  if (state.tone === "success") {
    return {
      tone: "success",
      title: t("purchase.successTitle"),
      detail: t("purchase.successDetail"),
      badge: t("purchase.successBadge"),
    };
  }
  if (state.tone === "failed") {
    return {
      tone: "failed",
      title: t("purchase.failedTitle"),
      detail: state.phase,
      badge: t("purchase.failedBadge"),
    };
  }
  return {
    tone: "running",
    title: state.phase,
    detail: t("purchase.runningDetail", { progress: Math.round(state.progress) }),
    badge: t("purchase.runningBadge"),
  };
}

export function getPurchaseFlowSteps(
  state: PurchasePhaseState,
): Array<{ label: string; status: "pending" | "active" | "done" | "failed" }> {
  const labels = [
    t("purchase.stepCreateOrder"),
    t("purchase.stepPaying"),
    t("purchase.stepPaymentResult"),
    t("purchase.stepTaskResult"),
  ] as const;
  const activeIndex = state.progress >= 100 ? 3 : state.progress >= 88 ? 2 : state.progress >= 58 ? 1 : 0;

  return labels.map((label, index) => {
    if (state.tone === "failed" && index === activeIndex) {
      return { label, status: "failed" };
    }
    if (state.tone === "success" && state.progress >= 100) {
      return { label, status: "done" };
    }
    if (index < activeIndex) {
      return { label, status: "done" };
    }
    if (index === activeIndex) {
      return { label, status: "active" };
    }
    return { label, status: "pending" };
  });
}

export type PromotionInvitee = {
  sequence: number;
  userIdMasked: string;
  registeredAt: string;
  hasRecharged: boolean;
};

export function maskPromotionUserId(value: string): string {
  if (value.length <= 5) return value;
  return `${value.slice(0, 3)}***${value.slice(-2)}`;
}

export function buildPromotionLink(siteKey: string, inviteCode: string): string {
  const origin = typeof window !== "undefined" ? window.location.origin : "http://127.0.0.1:5174";
  const url = new URL("/h5/register", origin);
  url.searchParams.set("site_key", siteKey);
  url.searchParams.set("invite_code", inviteCode);
  return url.toString();
}

export function buildPromotionInvitees(inviteCode: string): PromotionInvitee[] {
  const seed = inviteCode.replace(/[^A-Z0-9]/gi, "").slice(-6) || "382714";
  return [
    { sequence: 1, userIdMasked: maskPromotionUserId(`U${seed}91`), registeredAt: "2026-06-12T09:16:00.000Z", hasRecharged: true },
    { sequence: 2, userIdMasked: maskPromotionUserId(`U${seed}52`), registeredAt: "2026-06-12T10:42:00.000Z", hasRecharged: false },
    { sequence: 3, userIdMasked: maskPromotionUserId(`U${seed}73`), registeredAt: "2026-06-12T12:08:00.000Z", hasRecharged: true },
  ];
}

function getMessageDayGroup(value: string): string {
  const target = new Date(value);
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);
  const targetDate = new Date(target.getFullYear(), target.getMonth(), target.getDate());

  if (targetDate.getTime() === today.getTime()) return t("messages.today");
  if (targetDate.getTime() === yesterday.getTime()) return t("messages.yesterday");
  return t("messages.earlier");
}

export function buildMessageGroups(items: H5MessageItem[]): Array<{ label: string; items: H5MessageItem[]; unreadCount: number }> {
  const grouped = new Map<string, H5MessageItem[]>();
  items.forEach((item) => {
    const group = getMessageDayGroup(item.createdAt);
    const current = grouped.get(group) ?? [];
    current.push(item);
    grouped.set(group, current);
  });
  return [t("messages.today"), t("messages.yesterday"), t("messages.earlier")]
    .map((label) => {
      const groupItems = grouped.get(label) ?? [];
      return {
        label,
        items: groupItems,
        unreadCount: groupItems.filter((item) => !item.isRead).length,
      };
    })
    .filter((group) => group.items.length > 0);
}

export function isImportantMessage(item: H5MessageItem): boolean {
  return item.category === "task" || item.category === "wallet" || item.category === "order" || item.category === "support";
}

export type HomePrimaryAction = {
  title: string;
  description: string;
  buttonLabel: string;
  kind: "claim" | "continue" | "recharge" | "withdraw";
  packageId?: string;
};

export function getHomePrimaryAction(
  focusTaskPackage: { status: string; id: string; totalItems: number; totalCommission: number; title: string } | null,
  wallet: { canWithdraw: boolean; systemBalance: number; taskBalance: number } | null,
): HomePrimaryAction {
  if (focusTaskPackage?.status === "active") {
    return {
      title: t("home.actionContinueTask"),
      description: t("home.actionContinueTaskDesc"),
      buttonLabel: t("home.actionContinue"),
      kind: "continue",
      packageId: focusTaskPackage.id,
    };
  }

  if (focusTaskPackage?.status === "pending_claim") {
    return {
      title: t("home.actionNewPackage"),
      description: t("home.actionNewPackageDesc"),
      buttonLabel: t("home.actionClaim"),
      kind: "claim",
      packageId: focusTaskPackage.id,
    };
  }

  if (wallet?.canWithdraw) {
    return {
      title: t("home.actionCanWithdraw"),
      description: t("home.actionCanWithdrawDesc"),
      buttonLabel: t("home.actionGoWithdraw"),
      kind: "withdraw",
    };
  }

  return {
    title: t("home.actionLowBalance"),
    description: t("home.actionLowBalanceDesc"),
    buttonLabel: t("home.actionGoRecharge"),
    kind: "recharge",
  };
}

export function getHomeVerificationMeta(summary: { currentStatus: string }): string {
  if (summary.currentStatus === "pending" || summary.currentStatus === "under_review") {
    return t("home.verificationSubmitted");
  }
  if (summary.currentStatus === "approved" || summary.currentStatus === "verified") {
    return t("home.verificationApproved");
  }
  if (summary.currentStatus === "rejected") {
    return t("home.verificationRejected");
  }
  return t("home.verificationNotSubmitted");
}

export function getHomeFragmentMeta(summary: {
  shippingOrderCount: number;
  latestShippingStatus?: string | null;
  canExchange: boolean;
  rewardName?: string | null;
  totalCount: number;
  missingCount: number;
}): string {
  if (summary.shippingOrderCount > 0 && summary.latestShippingStatus) {
    return t("home.fragmentShipping", { status: getShippingStatusLabel(summary.latestShippingStatus) });
  }
  if (summary.canExchange) {
    return summary.rewardName ? t("home.fragmentCanExchange", { reward: summary.rewardName }) : t("home.fragmentCanExchangeGeneric");
  }
  if (summary.totalCount > 0) {
    return t("home.fragmentMissing", { count: summary.missingCount });
  }
  return t("home.fragmentDefault");
}

export function getHomeFragmentSideNote(summary: { totalCount: number; completedCount: number }): string {
  if (summary.totalCount > 0) {
    return `${summary.completedCount}/${summary.totalCount}`;
  }
  return "0/0";
}

export function getProfilePageLinks(siteKey: string): Array<{ label: string; description: string; path: string }> {
  return [
    { label: t("profileLinks.promotion"), description: t("profileLinks.promotionDesc"), path: buildH5Path("/h5/promotion", siteKey) },
    { label: t("profileLinks.orders"), description: t("profileLinks.ordersDesc"), path: buildH5Path("/h5/orders", siteKey) },
    { label: t("profileLinks.tickets"), description: t("profileLinks.ticketsDesc"), path: buildH5Path("/h5/tickets", siteKey) },
    { label: t("profileLinks.contact"), description: t("profileLinks.contactDesc"), path: buildH5Path("/h5/tickets/new", siteKey) },
  ];
}

export function mergeVerificationRequests(
  priorityRequest: H5MemberVerificationRequest,
  requests: H5MemberVerificationRequest[],
): H5MemberVerificationRequest[] {
  return [priorityRequest, ...requests.filter((item) => item.id !== priorityRequest.id)];
}

export function createVerificationSummaryFromRequest(
  request: H5MemberVerificationRequest,
  history: H5MemberVerificationRequest[],
): {
  currentStatus: string;
  hasActiveRequest: boolean;
  activeRequest: H5MemberVerificationRequest | null;
  history: H5MemberVerificationRequest[];
} {
  const hasActiveRequest = isVerificationRequestActive(request);
  return {
    currentStatus: request.status,
    hasActiveRequest,
    activeRequest: hasActiveRequest ? request : null,
    history,
  };
}

export function getPurchaseFailureActions(reason: string | undefined): Array<"recharge" | "retry" | "tickets" | "tasks"> {
  if (!reason) {
    return ["retry", "tickets"];
  }

  const normalizedReason = reason.toLowerCase();
  if (
    normalizedReason.includes("balance") ||
    normalizedReason.includes("insufficient") ||
    reason.includes("余额") ||
    reason.includes("浣欓")
  ) {
    return ["recharge"];
  }
  if (
    normalizedReason.includes("timed out") ||
    normalizedReason.includes("timeout") ||
    normalizedReason.includes("expired") ||
    normalizedReason.includes("unavailable") ||
    normalizedReason.includes("cannot purchase") ||
    reason.includes("超时") ||
    reason.includes("不可购买") ||
    reason.includes("瓒呮椂") ||
    reason.includes("涓嶅彲璐拱")
  ) {
    return ["tasks"];
  }
  return ["retry", "tickets"];
}

export function getTicketStatusLabels(): Record<SupportTicketStatus, string> {
  return {
    open: t("tickets.statusOpen"),
    in_progress: t("tickets.statusInProgress"),
    pending_user: t("tickets.statusPendingUser"),
    resolved: t("tickets.statusResolved"),
    rejected: t("tickets.statusRejected"),
    closed: t("tickets.statusClosed"),
    cancelled: t("tickets.statusCancelled"),
  };
}

export function getTicketPriorityLabels(): Record<SupportTicketPriority, string> {
  return {
    low: t("tickets.priorityLow"),
    normal: t("tickets.priorityNormal"),
    high: t("tickets.priorityHigh"),
    urgent: t("tickets.priorityUrgent"),
  };
}

export function getTicketCategoryLabels(): Record<SupportTicketCategory, string> {
  return {
    help: t("tickets.helpTicket"),
    task_appeal: t("tickets.taskAppeal"),
    complaint: t("tickets.complaint"),
  };
}

export type TicketDraft = {
  category: SupportTicketCategory;
  priority: SupportTicketPriority;
  subject: string;
  description: string;
};

export type ShippingFormState = {
  receiver: string;
  phone: string;
  country: string;
  province: string;
  city: string;
  addressLine: string;
};

export function getRechargeChannelOptions(): Array<{ id: "usdt" | "bank" | "card"; label: string; description: string }> {
  return [
    { id: "usdt", label: t("recharge.channelUsdt"), description: t("recharge.channelUsdtDesc") },
    { id: "bank", label: t("recharge.channelBank"), description: t("recharge.channelBankDesc") },
    { id: "card", label: t("recharge.channelCard"), description: t("recharge.channelCardDesc") },
  ];
}

export function delay(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

export type ProfileQuickAction = {
  key: "promotion" | "orders" | "tickets" | "contact";
  label: string;
  description: string;
  path: string;
};

export function getProfileActionIcon(key: ProfileQuickAction["key"]): JSX.Element {
  if (key === "promotion") return createElement(LinkOutlined);
  if (key === "orders") return createElement(ShoppingOutlined);
  if (key === "tickets") return createElement(AuditOutlined);
  if (key === "contact") return createElement(MessageOutlined);
  return createElement(UserOutlined);
}

export function getProfileQuickActions(siteKey: string): ProfileQuickAction[] {
  return [
    { key: "promotion", label: t("profileLinks.promotion"), description: t("profileLinks.promotionDesc"), path: buildH5Path("/h5/promotion", siteKey) },
    { key: "orders", label: t("profileLinks.orders"), description: t("profileLinks.ordersDesc"), path: buildH5Path("/h5/orders", siteKey) },
    { key: "tickets", label: t("profileLinks.tickets"), description: t("profileLinks.ticketsDesc"), path: buildH5Path("/h5/tickets", siteKey) },
    { key: "contact", label: t("profileLinks.contact"), description: t("profileLinks.contactDesc"), path: buildH5Path("/h5/tickets/new", siteKey) },
  ];
}

export const profileOverviewIcons = {
  wallet: createElement(WalletOutlined),
  messages: createElement(BellOutlined),
  tasks: createElement(AppstoreOutlined),
};
