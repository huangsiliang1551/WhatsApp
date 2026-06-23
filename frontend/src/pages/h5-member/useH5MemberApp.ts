import { useEffect, useMemo, useRef, useState, type ChangeEvent, type FormEvent, type JSX } from "react";

import {
  claimTaskPackage,
  completeTaskPackagePurchase,
  createFragmentExchange,
  createRechargeOrder,
  getCurrentMemberSession,
  getWithdrawDetailApi,
  getWithdrawalsApi,
  submitWithdrawApi,
  getFragmentsOverview,
  getFragmentsApi,
  checkInFragmentApi,
  exchangeFragmentsApi,
  getShippingStatusApi,
  subscribeMailingApi,
  unsubscribeMailingApi,
  getMaskedPhone,
  getMemberHomeDashboard,
  getMemberVerificationRequestDetail,
  getMemberVerificationSummary,
  getNotificationsCountApi,
  getTaskPackageDetail,
  getTaskPackageDetailApi,
  getTaskPackagesApi,
  getWalletBalanceApi,
  getWalletTransactionsApi,
  getWhatsAppBinding,
  rechargeApi,
  getRechargeStatusApi,
  getWithdrawLeaderboard,
  isH5AuthRequiredError,
  listMemberMessages,
  listMemberVerificationRequests,
  listMemberOrders,
  listTaskPackages,
  listWalletTransactions,

  getNotificationsApi,
  markNotificationReadApi,
  markAllNotificationsReadApi,
  getTicketsApi,
  createTicketApi,
  getTicketDetailApi,
  replyToTicketApi,

  getOrdersApi,
  getOrderDetailApi,

  getLeaderboardApi,
  getPromotionsApi,

  loginMember,
  logoutMember,
  maskAccountId,
  performDailyCheckIn,
  registerMember,
  createMemberVerificationRequest,
  startWhatsAppBinding,
  transferTaskBalanceToSystem,
  updateProfileApi,
  updateAvatarApi,
  changePasswordApi,
  getVerificationStatusApi,
  submitVerificationApi,
  uploadVerificationPhotosApi,
  getWhatsAppBindingStatusApi,
  startWhatsAppBindingApi,
  getMessagesApi,
  sendMessageApi,
  type H5ChatMessage,
  type H5MemberVerificationRequest,
  type H5MemberVerificationSummary,
  type H5FragmentOverview,
  type H5HomeDashboard,
  type H5LeaderboardEntry,
  type H5MemberOrder,
  type H5MemberSession,
  type H5MessageItem,
  type H5RewardShippingOrder,
  type H5ShippingAddress,
  type H5TaskPackage,
  type H5WalletSummary,
  type H5WalletTransaction,
  type H5WhatsAppBinding,
  type H5WithdrawRequest,
} from "../../services/h5Member";
import {
  type SupportTicket,
  type SupportTicketDetail,
} from "../../services/h5";
import { sessionManager } from "../../services/h5SessionManager";
import {
  buildH5Path,
  buildPromotionInvitees,
  buildPromotionLink,
  createVerificationSummaryFromRequest,
  delay,
  getFragmentStageContent,
  getHomePrimaryAction,
  getPurchasePhaseLabel,
  getRouteSubtitle,
  getProfileQuickActions,
  getVerificationStatusLabel,
  isImportantMessage,
  isVerificationRequestActive,
  mergeVerificationRequests,
  type HomePrimaryAction,
  type PurchasePhaseState,
  type ToastItem,
  type PromotionInvitee,
  type TicketDraft,
  type ShippingFormState,
} from "./sharedUtils";
import { DEFAULT_SHIPPING_FORM } from "./formDefaults";
import { DEFAULT_TICKET_DRAFT } from "./ticketDefaults";
import { t } from "./i18n";

// ─── Route types ─────────────────────────────────────────────────

export type ParsedRoute =
  | { page: "login"; siteKey: string }
  | { page: "register"; siteKey: string }
  | { page: "home"; siteKey: string }
  | { page: "tasks"; siteKey: string; filter: string }
  | { page: "task-package"; siteKey: string; packageId: string }
  | { page: "messages"; siteKey: string }
  | { page: "profile"; siteKey: string }
  | { page: "settings"; siteKey: string }
  | { page: "recharge"; siteKey: string }
  | { page: "withdraw"; siteKey: string }
  | { page: "orders"; siteKey: string }
  | { page: "tickets"; siteKey: string }
  | { page: "ticket-new"; siteKey: string }
  | { page: "ticket-detail"; siteKey: string; ticketId: string }
  | { page: "fragments"; siteKey: string }
  | { page: "leaderboard"; siteKey: string }
  | { page: "promotion"; siteKey: string }
  | { page: "verification"; siteKey: string }
  | { page: "whatsapp"; siteKey: string }
  | { page: "invite"; siteKey: string };

// ─── Local type aliases ──────────────────────────────────────────

type TaskPackageListItem = Awaited<ReturnType<typeof listTaskPackages>>[number];
type TaskPackageDetailView = Awaited<ReturnType<typeof getTaskPackageDetail>>;

type ImportantToastCandidate = {
  key: string;
  message: string;
};

// ─── Hook ─────────────────────────────────────────────────────────

export function useH5MemberApp(
  route: ParsedRoute,
  navigate: (path: string) => void,
) {
  const taskRouteFilter = route.page === "tasks" ? route.filter : "all";

  // ── State ──────────────────────────────────────────────────────

  const [session, setSession] = useState<H5MemberSession | null>(null);
  const [memberPhoneMasked, setMemberPhoneMasked] = useState("");
  const [dashboard, setDashboard] = useState<H5HomeDashboard | null>(null);
  const [taskPackages, setTaskPackages] = useState<TaskPackageListItem[]>([]);
  const [taskPackageDetail, setTaskPackageDetail] = useState<TaskPackageDetailView | null>(null);
  const [messages, setMessages] = useState<H5MessageItem[]>([]);
  const [walletSummary, setWalletSummary] = useState<H5WalletSummary | null>(null);
  const [walletTransactions, setWalletTransactions] = useState<H5WalletTransaction[]>([]);
  const [withdrawRequests, setWithdrawRequests] = useState<H5WithdrawRequest[]>([]);
  const [orders, setOrders] = useState<H5MemberOrder[]>([]);
  const [leaderboard, setLeaderboard] = useState<H5LeaderboardEntry[]>([]);
  const [fragmentOverview, setFragmentOverview] = useState<H5FragmentOverview | null>(null);
  const [whatsAppBinding, setWhatsAppBinding] = useState<H5WhatsAppBinding | null>(null);
  const [verificationSummary, setVerificationSummary] = useState<H5MemberVerificationSummary | null>(null);
  const [verificationRequests, setVerificationRequests] = useState<H5MemberVerificationRequest[]>([]);
  const [verificationRequestDetail, setVerificationRequestDetail] = useState<H5MemberVerificationRequest | null>(null);
  const [verificationNotes, setVerificationNotes] = useState("");
  const [tickets, setTickets] = useState<SupportTicket[]>([]);
  const [ticketDetail, setTicketDetail] = useState<SupportTicketDetail | null>(null);

  const [taskFilter, setTaskFilter] = useState(taskRouteFilter);
  const [orderFilter, setOrderFilter] = useState<"all" | "paid" | "failed" | "processing">("all");
  const [ticketDraft, setTicketDraft] = useState<TicketDraft>(DEFAULT_TICKET_DRAFT);
  const [ticketReply, setTicketReply] = useState("");
  const [loginPhone, setLoginPhone] = useState("");
  const [loginPassword, setLoginPassword] = useState("");
  const [loginPasswordVisible, setLoginPasswordVisible] = useState(false);
  const [rememberMe, setRememberMe] = useState(true);
  const [registerPhone, setRegisterPhone] = useState("");
  const [registerPassword, setRegisterPassword] = useState("");
  const [registerPasswordVisible, setRegisterPasswordVisible] = useState(false);
  const [registerConfirmPassword, setRegisterConfirmPassword] = useState("");
  const [registerConfirmPasswordVisible, setRegisterConfirmPasswordVisible] = useState(false);
  const [settingsPhone, setSettingsPhone] = useState("");
  const [settingsAvatarUrl, setSettingsAvatarUrl] = useState<string | null>(null);
  const [settingsCurrentPassword, setSettingsCurrentPassword] = useState("");
  const [settingsCurrentPasswordVisible, setSettingsCurrentPasswordVisible] = useState(false);
  const [settingsNextPassword, setSettingsNextPassword] = useState("");
  const [settingsNextPasswordVisible, setSettingsNextPasswordVisible] = useState(false);
  const [settingsConfirmPassword, setSettingsConfirmPassword] = useState("");
  const [settingsConfirmPasswordVisible, setSettingsConfirmPasswordVisible] = useState(false);
  const [rechargeAmount, setRechargeAmount] = useState("100");
  const [transferAmount, setTransferAmount] = useState("50");
  const [withdrawAmount, setWithdrawAmount] = useState("100");
  const [shippingForm, setShippingForm] = useState<ShippingFormState>(DEFAULT_SHIPPING_FORM);
  const [purchaseStates, setPurchaseStates] = useState<Record<string, PurchasePhaseState>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [importantToast, setImportantToast] = useState<ToastItem | null>(null);
  const [actionName, setActionName] = useState<string | null>(null);
  const [claimingPackageId, setClaimingPackageId] = useState<string | null>(null);
  const [showRechargeChannels, setShowRechargeChannels] = useState(false);
  const [showTransferAllConfirm, setShowTransferAllConfirm] = useState(false);
  const [verificationActionId, setVerificationActionId] = useState<string | null>(null);
  const [promotions, setPromotions] = useState<unknown[]>([]);
  const [promotionsLoading, setPromotionsLoading] = useState(false);
  const [promotionsError, setPromotionsError] = useState<string | null>(null);
  const [homeWalletBalance, setHomeWalletBalance] = useState<H5WalletSummary | null>(null);
  const [notificationCount, setNotificationCount] = useState<number>(0);
  const [rechargeStatus, setRechargeStatus] = useState<string | null>(null);
  const [taskPage, setTaskPage] = useState(1);
  const [hasMoreTasks, setHasMoreTasks] = useState(false);

  // ── H52-012: Message pagination & ticket state ────────────────
  const [messagePage, setMessagePage] = useState(1);
  const [messageTotalMessages, setMessageTotalMessages] = useState(0);
  const [messagesLoading, setMessagesLoading] = useState(false);
  const [messagesError, setMessagesError] = useState<string | null>(null);
  const [ticketsLoading, setTicketsLoading] = useState(false);
  const [ticketsError, setTicketsError] = useState<string | null>(null);

  // ── H52-014: Fragment loading/error state ──────────────────
  const [fragmentsLoading, setFragmentsLoading] = useState(false);
  const [fragmentsError, setFragmentsError] = useState<string | null>(null);

  // ── H52-013: Orders pagination state ──────────────────────────
  const [ordersPage, setOrdersPage] = useState(1);
  const [ordersTotal, setOrdersTotal] = useState(0);
  const [ordersLoading, setOrdersLoading] = useState(false);
  const [ordersError, setOrdersError] = useState<string | null>(null);
  const [ordersRealCount, setOrdersRealCount] = useState(0);

  // ── Verification form state (new API) ──────────────────────
  const [verificationName, setVerificationName] = useState("");
  const [verificationIdNumber, setVerificationIdNumber] = useState("");
  const [verificationPhotoFiles, setVerificationPhotoFiles] = useState<File[]>([]);

  // ── WhatsApp form state (new API) ──────────────────────────
  const [whatsappPhone, setWhatsappPhone] = useState("");

  // ── H52-016: Chat state ──────────────────────────────────────
  const [chatMessages, setChatMessages] = useState<H5ChatMessage[]>([]);
  const [chatLoading, setChatLoading] = useState(false);
  const [chatPage, setChatPage] = useState(1);
  const [chatTotal, setChatTotal] = useState(0);
  const [chatHasMore, setChatHasMore] = useState(false);

  const requestIdRef = useRef(0);
  const shownImportantToastKeysRef = useRef<Set<string>>(new Set());

  // ── Effects ────────────────────────────────────────────────────

  useEffect(() => {
    setTaskFilter(taskRouteFilter);
  }, [taskRouteFilter]);

  useEffect(() => {
    if (route.page !== "orders") {
      setOrderFilter("all");
    }
  }, [route.page]);

  useEffect(() => {
    if (!dashboard) return;
    setSettingsPhone(dashboard.member.phone);
    setSettingsAvatarUrl(dashboard.member.avatarUrl ?? null);
  }, [dashboard]);

  useEffect(() => {
    if (!notice) return;
    const timer = window.setTimeout(() => setNotice(null), 2600);
    return () => window.clearTimeout(timer);
  }, [notice]);

  useEffect(() => {
    if (!error) return;
    const timer = window.setTimeout(() => setError(null), 3600);
    return () => window.clearTimeout(timer);
  }, [error]);

  useEffect(() => {
    if (!importantToast) return;
    const timer = window.setTimeout(() => {
      setImportantToast((current) => (current?.key === importantToast.key ? null : current));
    }, importantToast.duration);
    return () => window.clearTimeout(timer);
  }, [importantToast]);

  useEffect(() => {
    shownImportantToastKeysRef.current.clear();
    setImportantToast(null);
  }, [route.siteKey, session?.accountId]);

  useEffect(() => {
    void loadRouteData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [route.page, route.siteKey, "packageId" in route ? route.packageId : "", "ticketId" in route ? route.ticketId : ""]);

  // ── Helper functions ───────────────────────────────────────────

  function handleAuthRequiredActionError(error: unknown): boolean {
    if (!isH5AuthRequiredError(error)) {
      return false;
    }
    setSession(null);
    setDashboard(null);
    setTicketDetail(null);
    navigate(buildH5Path("/h5/login", route.siteKey));
    return true;
  }

  async function loadVerificationData(
    activeRequestId: number,
    options: { preserveStateOnError?: boolean; suppressErrorNotice?: boolean } = {},
  ): Promise<void> {
    try {
      const [summary, requests] = await Promise.all([getMemberVerificationSummary(), listMemberVerificationRequests()]);
      if (requestIdRef.current !== activeRequestId) {
        return;
      }

      setVerificationSummary(summary);
      setVerificationRequests(requests);

      const focusRequest =
        summary.activeRequest ??
        requests.find((item) => isVerificationRequestActive(item)) ??
        requests[0] ??
        null;
      if (focusRequest) {
        try {
          const detail = await getMemberVerificationRequestDetail(focusRequest.id);
          if (requestIdRef.current !== activeRequestId) {
            return;
          }
          setVerificationRequestDetail(detail);
          return;
        } catch (detailError) {
          if (handleAuthRequiredActionError(detailError)) {
            return;
          }
          if (requestIdRef.current !== activeRequestId) {
            return;
          }
          setVerificationRequestDetail(focusRequest);
          return;
        }
      }

      setVerificationRequestDetail(null);
    } catch (loadError) {
      if (handleAuthRequiredActionError(loadError)) {
        return;
      }
      if (!options.preserveStateOnError) {
        setVerificationSummary(null);
        setVerificationRequests([]);
        setVerificationRequestDetail(null);
      }
      if (!options.suppressErrorNotice) {
        if (route.page === "verification") {
          setError(loadError instanceof Error ? loadError.message : t("notification.verificationLoadFailed"));
        } else {
          setNotice(loadError instanceof Error ? loadError.message : t("notification.verificationUnavailable"));
        }
      }
    }
  }

  async function loadRouteData(): Promise<void> {
    const requestId = requestIdRef.current + 1;
    requestIdRef.current = requestId;
    setLoading(true);
    setError(null);

    try {
      const activeSession = await getCurrentMemberSession();
      if (requestId !== requestIdRef.current) return;
      setSession(activeSession);

      // 两套 localStorage session 同步检查：
      // - sessionManager (h5_access_token) 有有效期
      // - MEMBER_SESSION_KEY (readSession) 永不过期
      // 必须两者都通过才算有效登录态，防止过期 token 导致 login ↔ home 死循环
      const isSessionManagerAuth = sessionManager.isAuthenticated();
      if (activeSession && !isSessionManagerAuth) {
        // 令牌已过期但 MEMBER_SESSION_KEY 残留 → 清除残留避免死循环
        try { localStorage.removeItem("frontend.h5.member-session.v1"); } catch { /* storage unavailable */ }
      }
      const isEffectivelyAuth = !!(activeSession && isSessionManagerAuth);

      if (!isEffectivelyAuth && route.page !== "login" && route.page !== "register") {
        navigate(buildH5Path("/h5/login", route.siteKey));
        return;
      }
      if (isEffectivelyAuth && (route.page === "login" || route.page === "register")) {
        navigate(buildH5Path("/h5/home", route.siteKey));
        return;
      }
      if (!isEffectivelyAuth) return;

      const [nextDashboard, maskedPhone] = await Promise.all([
        getMemberHomeDashboard(route.siteKey),
        getMaskedPhone(),
      ]);
      if (requestId !== requestIdRef.current) return;

      setDashboard(nextDashboard);
      setMemberPhoneMasked(maskedPhone);

      if (route.page === "home") {
        const [packages, walletBal, notifCount] = await Promise.all([
          listTaskPackages(),
          getWalletBalanceApi(),
          getNotificationsCountApi(),
        ]);
        if (requestId !== requestIdRef.current) return;
        setTaskPackages(packages);
        setHomeWalletBalance(walletBal);
        setNotificationCount(notifCount.unreadCount);
      } else if (route.page === "tasks") {
        setTaskPage(1);
        const taskResult = await getTaskPackagesApi({ status: taskFilter === "all" ? undefined : taskFilter, page: 1, size: 20 });
        setTaskPackages(taskResult);
        setHasMoreTasks(taskResult.length >= 20);
        setTaskPackageDetail(null);
        setTickets([]);
        setTicketDetail(null);
      } else if (route.page === "task-package") {
        const detail = await getTaskPackageDetailApi(route.packageId);
        setTaskPackageDetail(detail);
      } else if (route.page === "messages") {
        setMessagePage(1);
        setMessagesLoading(true);
        setMessagesError(null);
        try {
          const msgResult = await getNotificationsApi({ page: 1, size: 50 });
          setMessages(msgResult.items as H5MessageItem[]);
          setMessageTotalMessages(msgResult.total);
        } catch (msgError) {
          if (requestId !== requestIdRef.current) return;
          setMessagesError(msgError instanceof Error ? msgError.message : t("notification.messageLoadFailed"));
        } finally {
          if (requestId === requestIdRef.current) {
            setMessagesLoading(false);
          }
        }
      } else if (route.page === "recharge" || route.page === "withdraw") {
        const [summary, txResult, withdraws] = await Promise.all([
          getWalletBalanceApi(),
          getWalletTransactionsApi({ page: 1, size: 50 }),
          getWithdrawalsApi({ page: 1, size: 50 }),
        ]);
        if (requestId !== requestIdRef.current) return;
        setWalletSummary(summary);
        setWalletTransactions(txResult.items);
        setWithdrawRequests(withdraws.items);
      } else if (route.page === "orders") {
        setOrdersPage(1);
        setOrdersLoading(true);
        setOrdersError(null);
        try {
          const ordersResult = await getOrdersApi({ page: 1, size: 20 });
          setOrders(ordersResult.items as H5MemberOrder[]);
          setOrdersTotal(ordersResult.total);
          setOrdersRealCount(ordersResult.total);
        } catch (ordersErr) {
          if (requestId !== requestIdRef.current) return;
          setOrdersError(ordersErr instanceof Error ? ordersErr.message : t("notification.orderLoadFailed"));
        } finally {
          if (requestId === requestIdRef.current) {
            setOrdersLoading(false);
          }
        }
      } else if (route.page === "tickets") {
        setTicketsLoading(true);
        setTicketsError(null);
        try {
          const ticketResult = await getTicketsApi({ page: 1, size: 50 });
          setTickets(ticketResult.items as SupportTicket[]);
        } catch (ticketErr) {
          if (requestId !== requestIdRef.current) return;
          setTicketsError(ticketErr instanceof Error ? ticketErr.message : t("notification.ticketLoadFailed"));
        } finally {
          if (requestId === requestIdRef.current) {
            setTicketsLoading(false);
          }
        }
        setTicketDetail(null);
      } else if (route.page === "ticket-detail") {
        const detail = await getTicketDetailApi(route.ticketId);
        setTicketDetail(detail as SupportTicketDetail | null);
      } else if (route.page === "fragments") {
        setFragmentOverview(await getFragmentsOverview());
      } else if (route.page === "leaderboard") {
        const lbResult = await getLeaderboardApi();
        setLeaderboard(lbResult.rankings.map((item) => ({
          rank: item.rank,
          accountIdMasked: maskAccountId(item.userId),
          amount: item.score,
          currency: "USD",
        })));
      } else if (route.page === "promotion") {
        setPromotionsLoading(true);
        setPromotionsError(null);
        try {
          const promoResult = await getPromotionsApi();
          setPromotions(promoResult.items);
        } catch (promoError) {
          if (requestId !== requestIdRef.current) return;
          setPromotionsError(promoError instanceof Error ? promoError.message : t("notification.promotionLoadFailed"));
        } finally {
          if (requestId === requestIdRef.current) {
            setPromotionsLoading(false);
          }
        }
      } else if (route.page === "whatsapp") {
        setWhatsAppBinding(await getWhatsAppBinding());
        // Load chat messages
        const [binding] = await Promise.all([getWhatsAppBinding()]);
        setWhatsAppBinding(binding);
        if (binding?.isBound) {
          setChatPage(1);
          setChatLoading(true);
          try {
            // Try to load initial messages; on error just show empty chat
            try {
              const msgResult = await getMessagesApi({ page: 1, size: 30 });
              setChatMessages(msgResult.items);
              setChatTotal(msgResult.total);
              setChatHasMore(msgResult.items.length >= 30);
            } catch {
              setChatMessages([]);
              setChatTotal(0);
              setChatHasMore(false);
            }
          } finally {
            setChatLoading(false);
          }
        }
      } else if (route.page === "profile") {
        setWhatsAppBinding(await getWhatsAppBinding());
      } else if (route.page === "settings") {
        setWhatsAppBinding(await getWhatsAppBinding());
      } else if (route.page === "verification") {
        await loadVerificationData(requestId);
      }
    } catch (loadError) {
      if (requestId !== requestIdRef.current) return;
      if (handleAuthRequiredActionError(loadError)) {
        return;
      }
      setError(loadError instanceof Error ? loadError.message : t("notification.pageLoadFailed"));
    } finally {
      if (requestId === requestIdRef.current) {
        setLoading(false);
      }
    }
  }

  async function refreshDashboard(): Promise<void> {
    if (!session) return;
    try {
      const [nextDashboard, maskedPhone] = await Promise.all([
        getMemberHomeDashboard(route.siteKey),
        getMaskedPhone(),
      ]);
      setDashboard(nextDashboard);
      setMemberPhoneMasked(maskedPhone);
    } catch (refreshError) {
      if (handleAuthRequiredActionError(refreshError)) {
        return;
      }
      throw refreshError;
    }
  }

  // ── Event Handlers ─────────────────────────────────────────────

  async function handleLogin(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setActionName("login");
    setError(null);
    try {
      const profile = await loginMember({
        siteKey: route.siteKey,
        phone: loginPhone,
        password: loginPassword,
      });
      // Store session tokens
      sessionManager.setSession(
        "mock_access_" + profile.accountId,
        "mock_refresh_" + profile.accountId,
        604800, // 7 days
        rememberMe,
      );
      sessionManager.setUserInfo({
        accountId: profile.accountId,
        phone: profile.phone,
        publicUserId: profile.publicUserId,
        displayName: profile.displayName,
        inviteCode: profile.inviteCode,
        avatarUrl: profile.avatarUrl ?? null,
      });
      setNotice(t("notification.welcomeBack", { accountId: maskAccountId(profile.accountId) }));
      // Handle redirect parameter
      const redirect = new URLSearchParams(window.location.search).get("redirect");
      if (redirect) {
        navigate(decodeURIComponent(redirect));
      } else {
        navigate(buildH5Path("/h5/home", route.siteKey));
      }
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : t("notification.loginFailed"));
    } finally {
      setActionName(null);
    }
  }

  async function handleRegister(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (registerPassword.trim() !== registerConfirmPassword.trim()) {
      setError(t("notification.passwordMismatch"));
      return;
    }
    setActionName("register");
    setError(null);
    try {
      const profile = await registerMember({
        siteKey: route.siteKey,
        phone: registerPhone,
        password: registerPassword,
        confirmPassword: registerConfirmPassword,
      });
      // Store session tokens
      sessionManager.setSession(
        "mock_access_" + profile.accountId,
        "mock_refresh_" + profile.accountId,
        604800, // 7 days
      );
      sessionManager.setUserInfo({
        accountId: profile.accountId,
        phone: profile.phone,
        publicUserId: profile.publicUserId,
        displayName: profile.displayName,
        inviteCode: profile.inviteCode,
        avatarUrl: profile.avatarUrl ?? null,
      });
      setNotice(t("notification.registerSuccess", { accountId: maskAccountId(profile.accountId) }));
      // Handle redirect parameter
      const redirect = new URLSearchParams(window.location.search).get("redirect");
      if (redirect) {
        navigate(decodeURIComponent(redirect));
      } else {
        navigate(buildH5Path("/h5/home", route.siteKey));
      }
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : t("notification.registerFailed"));
    } finally {
      setActionName(null);
    }
  }

  async function handleLogout(): Promise<void> {
    setActionName("logout");
    try {
      await logoutMember();
      setSession(null);
      setDashboard(null);
      setNotice(t("notification.logoutSuccess"));
      navigate(buildH5Path("/h5/login", route.siteKey));
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : t("notification.logoutFailed"));
    } finally {
      setActionName(null);
    }
  }

  async function handleSettingsAvatarChange(event: ChangeEvent<HTMLInputElement>): Promise<void> {
    const file = event.target.files?.[0];
    if (!file) return;
    if (!file.type.startsWith("image/")) {
      setError(t("notification.avatarFormatError"));
      event.target.value = "";
      return;
    }
    if (file.size > 2 * 1024 * 1024) {
      setError(t("notification.avatarSizeError"));
      event.target.value = "";
      return;
    }
    try {
      setActionName("settings-avatar");
      const result = await updateAvatarApi(file);
      setSettingsAvatarUrl(result.avatarUrl);
      // Update session with new avatar
      const nextSession = await getCurrentMemberSession();
      if (nextSession) setSession(nextSession);
      await refreshDashboard();
      setNotice(t("notification.avatarPreviewUpdated"));
    } catch (avatarError) {
      if (handleAuthRequiredActionError(avatarError)) return;
      setError(avatarError instanceof Error ? avatarError.message : t("notification.profileUpdateFailed"));
    } finally {
      setActionName(null);
      event.target.value = "";
    }
  }

  async function handleSaveProfileSettings(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setActionName("settings-profile");
    setError(null);
    try {
      await updateProfileApi({
        phone: settingsPhone,
        avatarUrl: settingsAvatarUrl,
      });
      const nextSession = await getCurrentMemberSession();
      setSession(nextSession);
      await refreshDashboard();
      setNotice(t("notification.profileUpdated"));
    } catch (actionError) {
      if (handleAuthRequiredActionError(actionError)) return;
      const msg = actionError instanceof Error ? actionError.message : t("notification.profileUpdateFailed");
      setError(msg);
      throw actionError;
    } finally {
      setActionName(null);
    }
  }

  async function handleChangePassword(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setActionName("settings-password");
    setError(null);
    try {
      await changePasswordApi({
        currentPassword: settingsCurrentPassword,
        nextPassword: settingsNextPassword,
        confirmPassword: settingsConfirmPassword,
      });
      setSettingsCurrentPassword("");
      setSettingsNextPassword("");
      setSettingsConfirmPassword("");
      setNotice(t("notification.passwordChanged"));
    } catch (actionError) {
      if (handleAuthRequiredActionError(actionError)) return;
      const msg = actionError instanceof Error ? actionError.message : t("notification.passwordChangeFailed");
      setError(msg);
      throw actionError;
    } finally {
      setActionName(null);
    }
  }

  async function handleOpenVerificationRequest(requestId: string): Promise<void> {
    setVerificationActionId(`detail:${requestId}`);
    setError(null);
    try {
      const detail = await getMemberVerificationRequestDetail(requestId);
      setVerificationRequestDetail(detail);
    } catch (actionError) {
      if (handleAuthRequiredActionError(actionError)) return;
      setError(actionError instanceof Error ? actionError.message : t("notification.verificationDetailFailed"));
    } finally {
      setVerificationActionId(null);
    }
  }

  async function handleSubmitVerificationRequest(): Promise<void> {
    setVerificationActionId("submit");
    setError(null);
    try {
      const createdRequest = await createMemberVerificationRequest({
        requestType: "identity",
        notes: verificationNotes,
        documents: [],
      });
      const optimisticRequests = mergeVerificationRequests(createdRequest, verificationRequests);
      setVerificationSummary(createVerificationSummaryFromRequest(createdRequest, optimisticRequests));
      setVerificationRequests(optimisticRequests);
      setVerificationRequestDetail(createdRequest);
      setDashboard((current) =>
        current ? {
          ...current,
          verification: { currentStatus: createdRequest.status, hasActiveRequest: isVerificationRequestActive(createdRequest) },
        } : current,
      );
      setVerificationNotes("");
      await refreshDashboard();
      await loadVerificationData(requestIdRef.current, { preserveStateOnError: true, suppressErrorNotice: true });
      setNotice(t("notification.verificationSubmitted"));
    } catch (actionError) {
      if (handleAuthRequiredActionError(actionError)) return;
      setError(actionError instanceof Error ? actionError.message : t("notification.verificationSubmitFailed"));
    } finally {
      setVerificationActionId(null);
    }
  }

  function openClaimDialog(packageId: string): void {
    setClaimingPackageId(packageId);
  }

  function closeClaimDialog(): void {
    if (actionName?.startsWith("claim:")) return;
    setClaimingPackageId(null);
  }

  async function handleClaimTaskPackage(packageId: string): Promise<void> {
    setActionName(`claim:${packageId}`);
    setError(null);
    try {
      const updated = await claimTaskPackage(packageId);
      setNotice(t("notification.packageClaimed", { title: updated.title }));
      setTaskPackageDetail(updated);
      setTaskPackages(await listTaskPackages());
      await refreshDashboard();
      setClaimingPackageId(null);
    } catch (actionError) {
      if (handleAuthRequiredActionError(actionError)) return;
      setError(actionError instanceof Error ? actionError.message : t("notification.packageClaimFailed"));
    } finally {
      setActionName(null);
    }
  }

  async function handlePurchase(packageId: string, itemId: string): Promise<void> {
    const purchaseKey = `${packageId}:${itemId}`;
    setPurchaseStates((current) => ({
      ...current,
      [purchaseKey]: { phase: getPurchasePhaseLabel("create_order"), progress: 18, tone: "running" },
    }));
    setError(null);
    try {
      await delay(900);
      setPurchaseStates((current) => ({
        ...current,
        [purchaseKey]: { phase: getPurchasePhaseLabel("paying"), progress: 58, tone: "running" },
      }));
      await delay(1000);
      setPurchaseStates((current) => ({
        ...current,
        [purchaseKey]: { phase: getPurchasePhaseLabel("settling"), progress: 88, tone: "running" },
      }));
      await delay(900);
      const result = await completeTaskPackagePurchase(packageId, itemId);
      if (result.success) {
        setPurchaseStates((current) => ({
          ...current,
          [purchaseKey]: { phase: getPurchasePhaseLabel("success"), progress: 100, tone: "success" },
        }));
        setNotice(
          result.fragmentDrop
            ? t("notification.purchaseSuccessWithFragment", { fragment: result.fragmentDrop.fragmentName })
            : t("notification.purchaseSuccess"),
        );
      } else {
        setPurchaseStates((current) => ({
          ...current,
          [purchaseKey]: { phase: result.reason ?? getPurchasePhaseLabel("failed"), progress: 100, tone: "failed" },
        }));
        setError(result.reason ?? t("notification.purchaseFailed"));
      }
      setTaskPackageDetail(await getTaskPackageDetail(packageId));
      setTaskPackages(await listTaskPackages());
      await refreshDashboard();
    } catch (actionError) {
      if (handleAuthRequiredActionError(actionError)) return;
      setPurchaseStates((current) => ({
        ...current,
        [purchaseKey]: { phase: getPurchasePhaseLabel("failed"), progress: 100, tone: "failed" },
      }));
      setError(actionError instanceof Error ? actionError.message : t("notification.purchaseFlowFailed"));
    }
  }

  async function handleMarkAllMessagesRead(): Promise<void> {
    setActionName("read-all");
    try {
      await markAllNotificationsReadApi();
      const msgResult = await getNotificationsApi({ page: 1, size: 50 });
      setMessages(msgResult.items as H5MessageItem[]);
      await refreshDashboard();
      setNotice(t("notification.messagesMarkedRead"));
    } catch (actionError) {
      if (handleAuthRequiredActionError(actionError)) return;
      setError(actionError instanceof Error ? actionError.message : t("notification.markReadFailed"));
    } finally {
      setActionName(null);
    }
  }

  async function handleOpenMessage(messageId: string): Promise<void> {
    try {
      await markNotificationReadApi(messageId);
      const msgResult = await getNotificationsApi({ page: 1, size: 50 });
      setMessages(msgResult.items as H5MessageItem[]);
      await refreshDashboard();
    } catch (actionError) {
      if (handleAuthRequiredActionError(actionError)) return;
      setError(actionError instanceof Error ? actionError.message : t("notification.openMessageFailed"));
    }
  }

  function handleOpenRechargeChannels(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    setError(null);
    setShowRechargeChannels(true);
  }

  async function handleRecharge(channelName: string): Promise<void> {
    setActionName("recharge");
    setError(null);
    try {
      const result = await rechargeApi(Number(rechargeAmount), channelName);
      // Poll for status if not immediately completed
      if (result.status !== 'completed' && result.status !== 'failed') {
        setRechargeStatus(result.status);
        for (let i = 0; i < 30; i++) {
          await delay(1000);
          const status = await getRechargeStatusApi(result.id);
          setRechargeStatus(status);
          if (status === 'completed' || status === 'failed') break;
        }
      }
      setRechargeStatus(null);
      const [summary, txResult] = await Promise.all([
        getWalletBalanceApi(),
        getWalletTransactionsApi({ page: 1, size: 50 }),
      ]);
      setWalletSummary(summary);
      setWalletTransactions(txResult.items);
      await refreshDashboard();
      setShowRechargeChannels(false);
      setNotice(t("notification.rechargeSuccess", { channel: channelName }));
    } catch (actionError) {
      if (handleAuthRequiredActionError(actionError)) return;
      setRechargeStatus(null);
      setError(actionError instanceof Error ? actionError.message : t("notification.rechargeFailed"));
    } finally {
      setActionName(null);
    }
  }

  async function handleTransferAmount(amount: number): Promise<void> {
    setActionName("transfer");
    setError(null);
    try {
      setWalletSummary(await transferTaskBalanceToSystem(amount));
      setWalletTransactions(await listWalletTransactions());
      await refreshDashboard();
      setShowTransferAllConfirm(false);
      setNotice(t("notification.transferSuccess"));
    } catch (actionError) {
      if (handleAuthRequiredActionError(actionError)) return;
      setError(actionError instanceof Error ? actionError.message : t("notification.transferFailed"));
    } finally {
      setActionName(null);
    }
  }

  async function handleTransfer(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    await handleTransferAmount(Number(transferAmount));
  }

  async function handleTransferAllTaskBalance(): Promise<void> {
    const amount = walletSummary?.taskBalance ?? dashboard?.wallet.taskBalance ?? 0;
    await handleTransferAmount(amount);
  }

  async function handleWithdraw(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setActionName("withdraw");
    setError(null);
    try {
      const result = await submitWithdrawApi(Number(withdrawAmount));
      const [summary, txResult, withdrawResult] = await Promise.all([
        getWalletBalanceApi(),
        getWalletTransactionsApi({ page: 1, size: 50 }),
        getWithdrawalsApi({ page: 1, size: 50 }),
      ]);
      setWalletSummary(summary);
      setWalletTransactions(txResult.items);
      setWithdrawRequests(withdrawResult.items);
      await refreshDashboard();
      setNotice(t("notification.withdrawSubmitted"));
    } catch (actionError) {
      if (handleAuthRequiredActionError(actionError)) return;
      setError(actionError instanceof Error ? actionError.message : t("notification.withdrawFailed"));
    } finally {
      setActionName(null);
    }
  }

  async function handleCheckIn(): Promise<void> {
    setActionName("checkin");
    setError(null);
    try {
      setFragmentOverview(await performDailyCheckIn());
      await refreshDashboard();
      setNotice(t("notification.checkinSuccess"));
    } catch (actionError) {
      if (handleAuthRequiredActionError(actionError)) return;
      setError(actionError instanceof Error ? actionError.message : t("notification.checkinFailed"));
    } finally {
      setActionName(null);
    }
  }

  async function handleFragmentExchange(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setActionName("fragment-exchange");
    setError(null);
    try {
      setFragmentOverview(await createFragmentExchange(shippingForm));
      setNotice(t("notification.exchangeSubmitted"));
    } catch (actionError) {
      if (handleAuthRequiredActionError(actionError)) return;
      setError(actionError instanceof Error ? actionError.message : t("notification.exchangeFailed"));
    } finally {
      setActionName(null);
    }
  }

  async function handleStartWhatsAppBinding(): Promise<void> {
    setActionName("whatsapp");
    setError(null);
    try {
      setWhatsAppBinding(await startWhatsAppBinding());
      setNotice(t("notification.whatsappOpened"));
    } catch (actionError) {
      if (handleAuthRequiredActionError(actionError)) return;
      setError(actionError instanceof Error ? actionError.message : t("notification.whatsappFailed"));
    } finally {
      setActionName(null);
    }
  }

  /** 使用新 API 提交认证（姓名 + 身份证号 + 照片） */
  async function handleSubmitVerificationApi(): Promise<void> {
    setActionName("verification-api-submit");
    setError(null);
    try {
      const result = await submitVerificationApi({
        name: verificationName,
        idNumber: verificationIdNumber || undefined,
      });
      if (result.status === 'pending') {
        const submittedAt = new Date().toISOString();
        const optimisticRequest: H5MemberVerificationRequest = {
          id: result.id,
          requestType: "identity",
          status: "pending",
          notes: verificationNotes.trim() || null,
          reviewNote: null,
          reviewerActorId: null,
          reviewedAt: null,
          createdAt: submittedAt,
          updatedAt: submittedAt,
          documents: verificationPhotoFiles.map((file, index) => ({
            id: `${result.id}:upload:${index}`,
            fileName: file.name,
            mimeType: file.type || null,
            storageKey: null,
            metadataJson: null,
            createdAt: submittedAt,
          })),
        };
        const optimisticHistory = mergeVerificationRequests(optimisticRequest, verificationRequests);
        const optimisticSummary = createVerificationSummaryFromRequest(optimisticRequest, optimisticHistory);
        setVerificationSummary(optimisticSummary);
        setVerificationRequests(optimisticHistory);
        setVerificationRequestDetail(optimisticRequest);
        setDashboard((current) => (
          current
            ? {
                ...current,
                verification: {
                  currentStatus: "pending",
                  hasActiveRequest: true,
                },
              }
            : current
        ));
        // 上传照片
        if (verificationPhotoFiles.length > 0) {
          await uploadVerificationPhotosApi(result.id, verificationPhotoFiles);
        }
        setNotice(t("notification.verificationSubmitted"));
        // 清除表单
        setVerificationName("");
        setVerificationIdNumber("");
        setVerificationPhotoFiles([]);
        // 刷新认证数据
        await loadVerificationData(requestIdRef.current, { preserveStateOnError: true, suppressErrorNotice: true });
      } else {
        setError(t("notification.verificationSubmitFailed"));
      }
    } catch (actionError) {
      if (handleAuthRequiredActionError(actionError)) return;
      setError(actionError instanceof Error ? actionError.message : t("notification.verificationSubmitFailed"));
    } finally {
      setActionName(null);
    }
  }

  /** 使用新 API 发起 WhatsApp 绑定 */
  async function handleStartWhatsAppBindingApi(): Promise<void> {
    setActionName("whatsapp-api");
    setError(null);
    try {
      const result = await startWhatsAppBindingApi(whatsappPhone);
      if (result.status === 'pending') {
        setNotice(t("notification.whatsappRequestSubmitted"));
        // 刷新绑定状态
        setWhatsAppBinding(await getWhatsAppBinding());
      }
    } catch (actionError) {
      if (handleAuthRequiredActionError(actionError)) return;
      setError(actionError instanceof Error ? actionError.message : t("notification.whatsappRequestFailed"));
    } finally {
      setActionName(null);
    }
  }

  // ── H52-016: Chat handlers ────────────────────────────────────

  async function handleSendMessage(content: string, type: string = 'text'): Promise<void> {
    try {
      const sent = await sendMessageApi('default', content, type);
      setChatMessages((prev) => [...prev, sent]);
      setChatTotal((prev) => prev + 1);
    } catch (actionError) {
      if (handleAuthRequiredActionError(actionError)) return;
      setError(actionError instanceof Error ? actionError.message : t("notification.sendMessageFailed"));
      throw actionError;
    }
  }

  async function handleLoadMoreMessages(): Promise<void> {
    if (chatLoading || !chatHasMore) return;
    const nextPage = chatPage + 1;
    setChatPage(nextPage);
    setChatLoading(true);
    try {
      const msgResult = await getMessagesApi({ page: nextPage, size: 30 });
      setChatMessages((prev) => [...msgResult.items, ...prev]);
      setChatTotal(msgResult.total);
      setChatHasMore(msgResult.items.length >= 30);
    } catch {
      setChatPage((prev) => prev - 1);
    } finally {
      setChatLoading(false);
    }
  }

  async function handleRefreshMessages(): Promise<void> {
    try {
      const msgResult = await getMessagesApi({ page: 1, size: 30 });
      setChatMessages((prev) => {
        const existingIds = new Set(prev.map((m) => m.id));
        const newMsgs = msgResult.items.filter((m) => !existingIds.has(m.id));
        return [...prev, ...newMsgs];
      });
      setChatTotal(msgResult.total);
    } catch {
      // Silently ignore polling errors
    }
  }

  async function handleCopyText(value: string, successMessage: string, failureMessage: string): Promise<void> {
    try {
      await navigator.clipboard.writeText(value);
      setNotice(successMessage);
    } catch {
      setError(failureMessage);
    }
  }

  // ── H52-012: Message pagination & ticket retry handlers ─────────

  async function handleMessagePageChange(page: number): Promise<void> {
    if (page < 1 || loading) return;
    setMessagePage(page);
    setMessagesLoading(true);
    setMessagesError(null);
    try {
      const msgResult = await getNotificationsApi({ page, size: 50 });
      if (page !== messagePage) {
        // Another page change happened while loading
        return;
      }
      setMessages(msgResult.items as H5MessageItem[]);
      setMessageTotalMessages(msgResult.total);
    } catch (msgError) {
      setMessagesError(msgError instanceof Error ? msgError.message : t("notification.messageLoadFailed"));
    } finally {
      setMessagesLoading(false);
    }
  }

  async function handleRetryMessages(): Promise<void> {
    setMessagePage(1);
    setMessagesLoading(true);
    setMessagesError(null);
    try {
      const msgResult = await getNotificationsApi({ page: 1, size: 50 });
      setMessages(msgResult.items as H5MessageItem[]);
      setMessageTotalMessages(msgResult.total);
    } catch (msgError) {
      setMessagesError(msgError instanceof Error ? msgError.message : t("notification.messageLoadFailed"));
    } finally {
      setMessagesLoading(false);
    }
  }

  async function handleRetryTickets(): Promise<void> {
    setTicketsLoading(true);
    setTicketsError(null);
    try {
      const ticketResult = await getTicketsApi({ page: 1, size: 50 });
      setTickets(ticketResult.items as SupportTicket[]);
    } catch (ticketErr) {
      setTicketsError(ticketErr instanceof Error ? ticketErr.message : t("notification.ticketLoadFailed"));
    } finally {
      setTicketsLoading(false);
    }
  }

  async function handleCreateTicket(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!session) return;
    setActionName("ticket-create");
    setError(null);
    try {
      const created = await createTicketApi({
        category: ticketDraft.category,
        priority: ticketDraft.priority,
        subject: ticketDraft.subject,
        description: ticketDraft.description,
      });
      setTicketDraft(DEFAULT_TICKET_DRAFT);
      setNotice(t("notification.ticketCreated"));
      navigate(buildH5Path(`/h5/tickets/${created.id}`, route.siteKey));
    } catch (actionError) {
      if (handleAuthRequiredActionError(actionError)) return;
      setError(actionError instanceof Error ? actionError.message : t("notification.ticketCreateFailed"));
    } finally {
      setActionName(null);
    }
  }

  async function handleTicketReply(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!session || !ticketDetail) return;
    setActionName("ticket-reply");
    setError(null);
    try {
      await replyToTicketApi(ticketDetail.id, ticketReply.trim());
      const nextDetail = await getTicketDetailApi(ticketDetail.id);
      setTicketDetail(nextDetail as SupportTicketDetail);
      setTicketReply("");
      setNotice(t("notification.ticketReplied"));
    } catch (actionError) {
      if (handleAuthRequiredActionError(actionError)) return;
      setError(actionError instanceof Error ? actionError.message : t("notification.ticketReplyFailed"));
    } finally {
      setActionName(null);
    }
  }

  async function handleLoadMoreTasks(): Promise<void> {
    if (loading || !hasMoreTasks) return;
    const nextPage = taskPage + 1;
    setTaskPage(nextPage);
    setLoading(true);
    try {
      const moreTasks = await getTaskPackagesApi({
        status: taskFilter === "all" ? undefined : taskFilter,
        page: nextPage,
        size: 20,
      });
      setTaskPackages((prev) => [...prev, ...moreTasks]);
      setHasMoreTasks(moreTasks.length >= 20);
    } catch (loadError) {
      if (handleAuthRequiredActionError(loadError)) return;
      setError(loadError instanceof Error ? loadError.message : t("notification.taskLoadMoreFailed"));
    } finally {
      setLoading(false);
    }
  }

  // ── H52-013: Orders page change handler ─────────────────────────

  async function handleOrderPageChange(page: number): Promise<void> {
    if (page < 1 || ordersLoading) return;
    setOrdersPage(page);
    setOrdersLoading(true);
    setOrdersError(null);
    try {
      const ordersResult = await getOrdersApi({ page, size: 20, status: orderFilter === 'all' ? undefined : orderFilter });
      setOrders(ordersResult.items as H5MemberOrder[]);
      setOrdersTotal(ordersResult.total);
    } catch (ordersErr) {
      setOrdersError(ordersErr instanceof Error ? ordersErr.message : t("notification.orderLoadFailed"));
    } finally {
      setOrdersLoading(false);
    }
  }

  async function handleRetryOrders(): Promise<void> {
    setOrdersPage(1);
    setOrdersLoading(true);
    setOrdersError(null);
    try {
      const ordersResult = await getOrdersApi({ page: 1, size: 20, status: orderFilter === 'all' ? undefined : orderFilter });
      setOrders(ordersResult.items as H5MemberOrder[]);
      setOrdersTotal(ordersResult.total);
    } catch (ordersErr) {
      setOrdersError(ordersErr instanceof Error ? ordersErr.message : t("notification.orderLoadFailed"));
    } finally {
      setOrdersLoading(false);
    }
  }

  // ── H52-014: Mailing subscription handlers ──────────────────────

  async function handleSubscribeMailing(email: string): Promise<void> {
    setActionName("mailing-subscribe");
    setError(null);
    try {
      const ok = await subscribeMailingApi(email);
      if (ok) {
        setNotice(t("notification.mailingSubscribeSuccess"));
      } else {
        setError(t("notification.mailingSubscribeFailed"));
      }
    } catch (actionError) {
      if (handleAuthRequiredActionError(actionError)) return;
      setError(actionError instanceof Error ? actionError.message : t("notification.mailingSubscribeFailed"));
    } finally {
      setActionName(null);
    }
  }

  async function handleUnsubscribeMailing(email: string): Promise<void> {
    setActionName("mailing-unsubscribe");
    setError(null);
    try {
      const ok = await unsubscribeMailingApi(email);
      if (ok) {
        setNotice(t("notification.mailingUnsubscribeSuccess"));
      } else {
        setError(t("notification.mailingUnsubscribeFailed"));
      }
    } catch (actionError) {
      if (handleAuthRequiredActionError(actionError)) return;
      setError(actionError instanceof Error ? actionError.message : t("notification.mailingUnsubscribeFailed"));
    } finally {
      setActionName(null);
    }
  }

  // ── H52-014: Fragment retry handler ──────────────────────────────

  async function handleRetryFragments(): Promise<void> {
    setFragmentsLoading(true);
    setFragmentsError(null);
    try {
      const fragmentResult = await getFragmentsApi();
      setFragmentOverview(fragmentResult.overview as H5FragmentOverview);
    } catch (fragmentErr) {
      setFragmentsError(fragmentErr instanceof Error ? fragmentErr.message : t("notification.fragmentLoadFailed"));
    } finally {
      setFragmentsLoading(false);
    }
  }

  // ── Memoized computed values ───────────────────────────────────

  const filteredTaskPackages = useMemo(() => {
    if (taskFilter === "active") return taskPackages.filter((item) => item.status === "active");
    if (taskFilter === "pending_claim") return taskPackages.filter((item) => item.status === "pending_claim");
    if (taskFilter === "completed") return taskPackages.filter((item) => item.status === "completed");
    if (taskFilter === "expired") return taskPackages.filter((item) => item.status === "expired");
    if (taskFilter === "all") return taskPackages;
    return taskPackages.filter((item) => item.type === taskFilter);
  }, [taskFilter, taskPackages]);

  const filteredOrders = useMemo(() => {
    if (orderFilter === "all") return orders;
    if (orderFilter === "processing") {
      return orders.filter((item) => item.status === "processing" || item.status === "pending");
    }
    return orders.filter((item) => item.status === orderFilter);
  }, [orderFilter, orders]);

  const profileLinks = useMemo(() => getProfileQuickActions(route.siteKey), [route.siteKey]);
  const profileQuickActions = useMemo(() => profileLinks, [profileLinks]);
  const canExchangeFragments = fragmentOverview?.inventory.every((item) => item.owned >= item.required) ?? false;
  const unreadMessageCount = useMemo(
    () => messages.filter((item) => !item.isRead).length || dashboard?.unreadCount || 0,
    [dashboard?.unreadCount, messages],
  );

  const effectiveVerificationSummary = useMemo<H5MemberVerificationSummary>(
    () => verificationSummary ?? {
      currentStatus: dashboard?.verification.currentStatus ?? "not_submitted",
      hasActiveRequest: dashboard?.verification.hasActiveRequest ?? false,
      activeRequest: null,
      history: verificationRequests,
    },
    [dashboard?.verification.currentStatus, dashboard?.verification.hasActiveRequest, verificationRequests, verificationSummary],
  );

  const profileVerificationStatusLabel = useMemo(() => {
    return getVerificationStatusLabel(effectiveVerificationSummary.currentStatus);
  }, [effectiveVerificationSummary.currentStatus]);

  const verificationHistory = useMemo(
    () => (effectiveVerificationSummary.history.length > 0 ? effectiveVerificationSummary.history : verificationRequests),
    [effectiveVerificationSummary.history, verificationRequests],
  );

  const focusedVerificationRequest = useMemo(
    () => verificationRequestDetail ?? effectiveVerificationSummary.activeRequest ?? verificationHistory[0] ?? null,
    [effectiveVerificationSummary.activeRequest, verificationHistory, verificationRequestDetail],
  );

  const canSubmitVerificationRequest = !effectiveVerificationSummary.hasActiveRequest;

  const focusTaskPackage = useMemo(() => {
    const active = taskPackages.find((item) => item.status === "active");
    if (active) return active;
    return taskPackages.find((item) => item.status === "pending_claim") ?? null;
  }, [taskPackages]);

  const primaryHomeAction = useMemo(
    () => getHomePrimaryAction(focusTaskPackage, dashboard?.wallet ?? null),
    [dashboard?.wallet, focusTaskPackage],
  );

  const canShowImportantToast = route.page === "messages";

  const importantToastCandidate = useMemo<ImportantToastCandidate | null>(() => {
    if (!canShowImportantToast) {
      return null;
    }
    const source = route.page === "messages" ? messages : dashboard?.recentMessages ?? [];
    const item = source.find((entry) => !entry.isRead && isImportantMessage(entry));
    if (!item) return null;
    return { key: `important:${item.id}`, message: item.title };
  }, [canShowImportantToast, dashboard?.recentMessages, messages, route.page]);

  useEffect(() => {
    if (!importantToastCandidate) return;
    if (shownImportantToastKeysRef.current.has(importantToastCandidate.key)) return;
    shownImportantToastKeysRef.current.add(importantToastCandidate.key);
    setImportantToast({
      key: importantToastCandidate.key,
      message: importantToastCandidate.message,
      tone: "notice",
      duration: 2800,
    });
  }, [importantToastCandidate]);

  useEffect(() => {
    if (canShowImportantToast) return;
    setImportantToast(null);
  }, [canShowImportantToast]);

  const claimDialogPackage = useMemo(() => {
    if (!claimingPackageId) return null;
    if (taskPackageDetail?.id === claimingPackageId) return taskPackageDetail;
    return taskPackages.find((item) => item.id === claimingPackageId) ?? null;
  }, [claimingPackageId, taskPackageDetail, taskPackages]);

  const fragmentCompletion = useMemo(() => {
    if (!fragmentOverview) return { completed: 0, total: 0, missing: 0, progress: 0 };
    const total = fragmentOverview.inventory.length;
    const completed = fragmentOverview.inventory.filter((item) => item.owned >= item.required).length;
    const missing = fragmentOverview.inventory.reduce((sum, item) => sum + Math.max(0, item.required - item.owned), 0);
    return { completed, total, missing, progress: total > 0 ? (completed / total) * 100 : 0 };
  }, [fragmentOverview]);

  const latestShippingOrder = fragmentOverview?.shippingOrders[0] ?? null;

  const promotionLink = useMemo(
    () => (dashboard ? buildPromotionLink(route.siteKey, dashboard.member.inviteCode) : ""),
    [dashboard, route.siteKey],
  );

  const promotionInvitees = useMemo(
    () => (dashboard ? buildPromotionInvitees(dashboard.member.inviteCode) : [] as PromotionInvitee[]),
    [dashboard],
  );

  const promotionRechargeCount = useMemo(
    () => promotionInvitees.filter((item) => item.hasRecharged).length,
    [promotionInvitees],
  );

  const effectiveWalletSummary = walletSummary ?? dashboard?.wallet ?? null;
  const rechargeHistory = useMemo(
    () => walletTransactions.filter((item) => item.transactionType === "recharge"),
    [walletTransactions],
  );

  const maxWithdrawAmount = useMemo(
    () => Number((effectiveWalletSummary?.systemBalance ?? 0).toFixed(2)),
    [effectiveWalletSummary],
  );

  const transferAllAmount = useMemo(
    () => Number((effectiveWalletSummary?.taskBalance ?? 0).toFixed(2)),
    [effectiveWalletSummary],
  );

  const fragmentStageTitle = useMemo(() => {
    return getFragmentStageContent({
      canExchangeFragments,
      latestShippingStatus: latestShippingOrder?.status ?? null,
    }).title;
  }, [canExchangeFragments, latestShippingOrder]);

  const fragmentStageDescription = useMemo(() => {
    return getFragmentStageContent({
      canExchangeFragments,
      latestShippingStatus: latestShippingOrder?.status ?? null,
    }).description;
  }, [canExchangeFragments, latestShippingOrder]);

  const primaryTabId = useMemo(() => {
    if (route.page === "home") return "home";
    if (route.page === "tasks" || route.page === "task-package") return "tasks";
    if (route.page === "recharge" || route.page === "withdraw") return "earnings";
    return "profile";
  }, [route.page]);

  const secondaryBackPath = useMemo(() => {
    if (route.page === "task-package") return buildH5Path("/h5/tasks", route.siteKey);
    if (route.page === "ticket-new" || route.page === "ticket-detail") return buildH5Path("/h5/tickets", route.siteKey);
    if (route.page === "recharge" || route.page === "withdraw" || route.page === "promotion" ||
        route.page === "verification" || route.page === "settings") {
      return buildH5Path("/h5/me", route.siteKey);
    }
    return buildH5Path("/h5/me", route.siteKey);
  }, [route.page, route.siteKey]);

  const topbarSubtitle = useMemo(() => {
    return getRouteSubtitle(route, {
      tagline: dashboard?.site.tagline ?? null,
      brandName: dashboard?.site.brand_name ?? null,
    });
  }, [dashboard?.site.brand_name, dashboard?.site.tagline, route]);

  const toastItems = useMemo<ToastItem[]>(() => {
    const items: ToastItem[] = [];
    if (error) items.push({ key: "error", message: error, tone: "error", duration: 3600 });
    if (importantToast) items.push(importantToast);
    if (notice) items.push({ key: "notice", message: notice, tone: "notice", duration: 2600 });
    return items;
  }, [error, importantToast, notice]);

  // ── Return ─────────────────────────────────────────────────────

  return {
    // Core
    route, navigate,
    session, dashboard, memberPhoneMasked, loading, error, notice, actionName,
    // Page data
    messages, taskPackages, taskPackageDetail, walletSummary, walletTransactions,
    homeWalletBalance, notificationCount, rechargeStatus,
    withdrawRequests, orders, leaderboard, fragmentOverview, whatsAppBinding,
    verificationSummary, verificationRequests, verificationRequestDetail, verificationNotes,
    tickets, ticketDetail,
    // Form states
    taskFilter, orderFilter, ticketDraft, ticketReply,
    loginPhone, loginPassword, loginPasswordVisible,
    rememberMe, setRememberMe,
    registerPhone, registerPassword, registerPasswordVisible, registerConfirmPassword, registerConfirmPasswordVisible,
    settingsPhone, settingsAvatarUrl, settingsCurrentPassword, settingsCurrentPasswordVisible,
    settingsNextPassword, settingsNextPasswordVisible, settingsConfirmPassword, settingsConfirmPasswordVisible,
    rechargeAmount, transferAmount, withdrawAmount, shippingForm,
    // UI states
    purchaseStates, claimingPackageId, showRechargeChannels, showTransferAllConfirm, verificationActionId,
    // Computed
    filteredTaskPackages, filteredOrders, profileLinks, profileQuickActions, canExchangeFragments,
    unreadMessageCount, effectiveVerificationSummary, profileVerificationStatusLabel,
    verificationHistory, focusedVerificationRequest, canSubmitVerificationRequest,
    focusTaskPackage, primaryHomeAction, claimDialogPackage, fragmentCompletion, latestShippingOrder,
    promotionLink, promotionInvitees, promotionRechargeCount, effectiveWalletSummary, rechargeHistory,
    maxWithdrawAmount, transferAllAmount, fragmentStageTitle, fragmentStageDescription,
    primaryTabId, secondaryBackPath, topbarSubtitle, toastItems,
    taskPage, hasMoreTasks,
    messagePage, messageTotalMessages, messagesLoading, messagesError,
    ticketsLoading, ticketsError,
    // H52-013: Orders state
    ordersPage, ordersTotal, ordersLoading, ordersError, ordersRealCount,
    // H52-015: Promotions state
    promotions, promotionsLoading, promotionsError,
    fragmentsLoading, fragmentsError,
    // Setters
    setTaskFilter, setOrderFilter, setTicketDraft, setTicketReply,
    setLoginPhone, setLoginPassword, setLoginPasswordVisible,
    setRegisterPhone, setRegisterPassword, setRegisterPasswordVisible,
    setRegisterConfirmPassword, setRegisterConfirmPasswordVisible,
    setSettingsPhone, setSettingsAvatarUrl, setSettingsCurrentPassword, setSettingsCurrentPasswordVisible,
    setSettingsNextPassword, setSettingsNextPasswordVisible, setSettingsConfirmPassword, setSettingsConfirmPasswordVisible,
    setRechargeAmount, setTransferAmount, setWithdrawAmount, setShippingForm,
    setVerificationNotes, setShowRechargeChannels, setShowTransferAllConfirm,
    // Handlers
    handleLogin, handleRegister, handleLogout,
    handleSettingsAvatarChange, handleSaveProfileSettings, handleChangePassword,
    handleOpenVerificationRequest, handleSubmitVerificationRequest,
    handleClaimTaskPackage, handlePurchase,
    handleMarkAllMessagesRead, handleOpenMessage, handleOpenRechargeChannels, handleRecharge,
    handleTransfer, handleTransferAllTaskBalance, handleTransferAmount, handleWithdraw,
    handleCheckIn, handleFragmentExchange, handleStartWhatsAppBinding, handleStartWhatsAppBindingApi, handleCopyText,
    handleCreateTicket, handleTicketReply, handleLoadMoreTasks,
    // H52-012: New handlers
    handleMessagePageChange, handleRetryMessages, handleRetryTickets,
    // H52-013: Orders handlers
    handleOrderPageChange, handleRetryOrders,
    // H52-014: Fragment & mailing handlers
    handleRetryFragments, handleSubscribeMailing, handleUnsubscribeMailing,
    // Dialog
    openClaimDialog, closeClaimDialog,
    // New API handlers & state
    handleSubmitVerificationApi,
    verificationName, setVerificationName,
    verificationIdNumber, setVerificationIdNumber,
    verificationPhotoFiles, setVerificationPhotoFiles,
    whatsappPhone, setWhatsappPhone,
    // H52-016: Chat state & handlers
    chatMessages, chatLoading, chatHasMore,
    handleSendMessage, handleLoadMoreMessages, handleRefreshMessages,
  };
}

