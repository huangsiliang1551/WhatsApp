import React, { useMemo, useState, useEffect, useCallback, type JSX } from "react";

import "../styles.css";
import "../styles/h5-member.css";


import { maskAccountId } from "../services/h5Member";
import type { H5HomeDashboard, H5WalletSummary } from "../services/h5Member";
import type { H5FragmentOverview } from "../services/h5Member";
import type { H5SignInStatus, H5TaskInstance, H5InviteInfo, H5InviteRecord } from "../services/h5Member";
import {
  isH5AuthRequiredError,
  getSignInStatusApi, performSignInApi,
  getTaskInstancesApi, getTaskInstanceDetailApi,
  startProductApi, retryProductApi,
  getInviteInfoApi, getInviteRecordsApi,
} from "../services/h5Member";
import { sessionManager } from "../services/h5SessionManager";
import { ListSkeleton } from "./h5-member/skeletons";
import { useAuthGuard } from "./h5-member/useAuthGuard";
import { buildH5Path } from "./h5-member/sharedUtils";
import { t } from "./h5-member/i18n";
import { H5PageShell, type ParsedRoute, useH5MemberApp } from "./h5-member";
import { ErrorBoundary } from "./h5-member/ErrorBoundary";
import { HomeSkeleton } from "./h5-member/skeletons";

const LoginPage = React.lazy(() => import("./h5-member").then(m => ({ default: m.LoginPage })));
const HomePage = React.lazy(() => import("./h5-member").then(m => ({ default: m.HomePage })));
const ProfilePage = React.lazy(() => import("./h5-member").then(m => ({ default: m.ProfilePage })));
const SettingsPage = React.lazy(() => import("./h5-member").then(m => ({ default: m.SettingsPage })));
const RechargePage = React.lazy(() => import("./h5-member").then(m => ({ default: m.RechargePage })));
const WithdrawPage = React.lazy(() => import("./h5-member").then(m => ({ default: m.WithdrawPage })));
const PromotionPage = React.lazy(() => import("./h5-member").then(m => ({ default: m.PromotionPage })));
const FragmentsPage = React.lazy(() => import("./h5-member").then(m => ({ default: m.FragmentsPage })));
const OrdersPage = React.lazy(() => import("./h5-member").then(m => ({ default: m.OrdersPage })));
const LeaderboardPage = React.lazy(() => import("./h5-member").then(m => ({ default: m.LeaderboardPage })));
const WhatsAppPage = React.lazy(() => import("./h5-member").then(m => ({ default: m.WhatsAppPage })));
const VerificationPage = React.lazy(() => import("./h5-member").then(m => ({ default: m.VerificationPage })));
const TasksPage = React.lazy(() => import("./h5-member").then(m => ({ default: m.TasksPage })));
const PackageDetailPage = React.lazy(() => import("./h5-member").then(m => ({ default: m.PackageDetailPage })));
const InvitePage = React.lazy(() => import("./h5-member").then(m => ({ default: m.InvitePage })));
const MessagesPage = React.lazy(() => import("./h5-member").then(m => ({ default: m.MessagesPage })));
const TicketsPage = React.lazy(() => import("./h5-member").then(m => ({ default: m.TicketsPage })));

type H5AppProps = {
  locationKey: string;
  navigate: (path: string) => void;
};

const DEFAULT_SITE_KEY = "mall-cn";

function parseRoute(locationKey: string): ParsedRoute {
  const url = new URL(locationKey, "http://localhost");
  const siteKey = url.searchParams.get("site_key") ?? DEFAULT_SITE_KEY;
  const filter = url.searchParams.get("filter") ?? "active";
  const rawParts = url.pathname.split("/").filter(Boolean);
  // 统一转为小写，使路由匹配大小写不敏感
  const parts = rawParts.map(p => p.toLowerCase());

  if (parts[0] !== "h5") return { page: "home", siteKey };
  if (parts[1] === "login") return { page: "login", siteKey };
  if (parts[1] === "register") return { page: "register", siteKey };
  if (parts[1] === "tasks" && parts[2] === "package" && parts[3]) return { page: "task-package", siteKey, packageId: parts[3] };
  if (parts[1] === "tasks") return { page: "tasks", siteKey, filter };
  if (parts[1] === "invite") return { page: "invite", siteKey };
  if (parts[1] === "messages") return { page: "messages", siteKey };
  if (parts[1] === "me" && parts[2] === "settings") return { page: "settings", siteKey };
  if (parts[1] === "me") return { page: "profile", siteKey };
  if (parts[1] === "wallet" || parts[1] === "recharge") return { page: "recharge", siteKey };
  if (parts[1] === "withdraw") return { page: "withdraw", siteKey };
  if (parts[1] === "orders") return { page: "orders", siteKey };
  if (parts[1] === "tickets" && parts[2] === "new") return { page: "ticket-new", siteKey };
  if (parts[1] === "tickets" && parts[2]) return { page: "ticket-detail", siteKey, ticketId: parts[2] };
  if (parts[1] === "tickets") return { page: "tickets", siteKey };
  if (parts[1] === "fragments") return { page: "fragments", siteKey };
  if (parts[1] === "leaderboard") return { page: "leaderboard", siteKey };
  if (parts[1] === "promotion") return { page: "promotion", siteKey };
  if (parts[1] === "verification") return { page: "verification", siteKey };
  if (parts[1] === "whatsapp") return { page: "whatsapp", siteKey };
  return { page: "home", siteKey };
}

// ── Wrapper components for self-contained pages ──

function TasksPageShell({
  siteKey,
  navigate,
  actionName,
  onOpenClaimDialog,
}: {
  siteKey: string;
  navigate: (path: string) => void;
  actionName: string | null;
  onOpenClaimDialog: (packageId: string) => void;
}): JSX.Element | null {
  const [signInStatus, setSignInStatus] = useState<H5SignInStatus | null>(null);
  const [taskInstances, setTaskInstances] = useState<H5TaskInstance[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [status, instances] = await Promise.all([
        getSignInStatusApi(),
        getTaskInstancesApi(),
      ]);
      setSignInStatus(status);
      setTaskInstances(instances);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void loadData(); }, [loadData]);

  const handleSignIn = useCallback(async () => {
    if (!signInStatus || signInStatus.todaySignedIn) return;
    try {
      const result = await performSignInApi();
      setSignInStatus(result);
    } catch {
      // Error handled by parent toast
    }
  }, [signInStatus]);

  if (!signInStatus && loading) {
    return <ListSkeleton count={4} />;
  }

  return (
    <TasksPage
      signInStatus={signInStatus ?? { consecutiveDays: 0, todaySignedIn: false, goalDays: 7, goalReward: 5, isCompleted: false }}
      taskInstances={taskInstances}
      actionName={actionName}
      loading={loading}
      error={error}
      onSignIn={handleSignIn}
      onNavigate={(path) => navigate(buildH5Path(path, siteKey))}
      onRefresh={loadData}
      onOpenClaimDialog={onOpenClaimDialog}
    />
  );
}

function PackageDetailPageShell({
  siteKey,
  navigate,
  actionName,
  packageId,
  onOpenClaimDialog,
}: {
  siteKey: string;
  navigate: (path: string) => void;
  actionName: string | null;
  packageId: string;
  onOpenClaimDialog: (packageId: string) => void;
}): JSX.Element | null {
  const [instance, setInstance] = useState<H5TaskInstance | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const handleAuthRequiredActionError = useCallback((actionError: unknown): boolean => {
    if (!isH5AuthRequiredError(actionError)) {
      return false;
    }
    sessionManager.clearSession();
    navigate(buildH5Path("/h5/login", siteKey));
    return true;
  }, [navigate, siteKey]);

  const loadData = useCallback(async () => {
    if (!packageId) return;
    setLoading(true);
    setError(null);
    try {
      const result = await getTaskInstanceDetailApi(packageId);
      setInstance(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [packageId]);

  useEffect(() => { void loadData(); }, [loadData]);

  const handleStartProduct = useCallback(async (productId: string) => {
    if (!instance) return;
    try {
      await startProductApi(instance.id, productId);
      await loadData();
    } catch (actionError) {
      if (handleAuthRequiredActionError(actionError)) {
        throw actionError;
      }
      throw actionError;
    }
  }, [handleAuthRequiredActionError, instance, loadData]);

  const handleRetryProduct = useCallback(async (productId: string) => {
    if (!instance) return;
    try {
      await retryProductApi(instance.id, productId);
      await loadData();
    } catch (actionError) {
      if (handleAuthRequiredActionError(actionError)) {
        throw actionError;
      }
      throw actionError;
    }
  }, [handleAuthRequiredActionError, instance, loadData]);

  if (loading && !instance) {
    return <ListSkeleton count={4} />;
  }

  if (error && !instance) {
    return (
      <section className="h5-card-stack">
        <article className="h5-card">
          <p style={{ color: "var(--color-error, #ff4d4f)", fontSize: 14 }}>{error}</p>
          <button className="seed-button" onClick={() => void loadData()} type="button">{t("common.retry")}</button>
        </article>
      </section>
    );
  }

  if (!instance) return null;

  return (
    <PackageDetailPage
      instance={instance}
      actionName={actionName}
      onStartProduct={handleStartProduct}
      onRetryProduct={handleRetryProduct}
      onNavigate={(path) => navigate(buildH5Path(path, siteKey))}
      onRefresh={loadData}
      onOpenClaimDialog={onOpenClaimDialog}
    />
  );
}

function InvitePageShell({ siteKey, navigate, onCopyText }: { siteKey: string; navigate: (path: string) => void; onCopyText: (value: string, successMsg: string, failMsg: string) => Promise<void> }): JSX.Element | null {
  const [inviteInfo, setInviteInfo] = useState<H5InviteInfo | null>(null);
  const [inviteRecords, setInviteRecords] = useState<H5InviteRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [info, records] = await Promise.all([
        getInviteInfoApi(),
        getInviteRecordsApi(),
      ]);
      setInviteInfo(info);
      setInviteRecords(records);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void loadData(); }, [loadData]);

  if (loading && !inviteInfo) return <ListSkeleton count={4} />;

  if (error && !inviteInfo) {
    return (
      <section className="h5-card-stack">
        <article className="h5-card">
          <p style={{ color: "var(--color-error, #ff4d4f)", fontSize: 14 }}>{error}</p>
          <button className="seed-button" onClick={() => void loadData()} type="button">{t("common.retry")}</button>
        </article>
      </section>
    );
  }

  if (!inviteInfo) return null;

  return (
    <InvitePage
      inviteInfo={inviteInfo}
      inviteRecords={inviteRecords}
      loading={loading}
      error={error}
      onCopyText={onCopyText}
      onRetry={loadData}
    />
  );
}

export function H5App({ locationKey, navigate }: H5AppProps): JSX.Element {
  const route = useMemo(() => parseRoute(locationKey), [locationKey]);
  const s = useH5MemberApp(route, navigate);
  const { isAuthenticated, isLoading: authLoading } = useAuthGuard(
    route.page !== "login" && route.page !== "register",
    locationKey,
    navigate,
  );
  const effectiveLoading = s.loading || authLoading;

  return (
    <ErrorBoundary>
      <React.Suspense fallback={<HomeSkeleton />}>
        {route.page === "login" || route.page === "register" ? (
          <ErrorBoundary>
            <LoginPage
              page={route.page}
              siteKey={route.siteKey}
              loginPhone={s.loginPhone}
              loginPassword={s.loginPassword}
              loginPasswordVisible={s.loginPasswordVisible}
              registerPhone={s.registerPhone}
              registerPassword={s.registerPassword}
              registerPasswordVisible={s.registerPasswordVisible}
              registerConfirmPassword={s.registerConfirmPassword}
              registerConfirmPasswordVisible={s.registerConfirmPasswordVisible}
              actionName={s.actionName}
              loginError={s.error}
              rememberMe={s.rememberMe}
              onRememberMeChange={s.setRememberMe}
              onLoginPhoneChange={s.setLoginPhone}
              onLoginPasswordChange={s.setLoginPassword}
              onLoginPasswordToggle={() => s.setLoginPasswordVisible((c: boolean) => !c)}
              onRegisterPhoneChange={s.setRegisterPhone}
              onRegisterPasswordChange={s.setRegisterPassword}
              onRegisterPasswordToggle={() => s.setRegisterPasswordVisible((c: boolean) => !c)}
              onRegisterConfirmPasswordChange={s.setRegisterConfirmPassword}
              onRegisterConfirmPasswordToggle={() => s.setRegisterConfirmPasswordVisible((c: boolean) => !c)}
              onLogin={(event) => s.handleLogin(event)}
              onRegister={(event) => s.handleRegister(event)}
              onNavigate={(path) => navigate(buildH5Path(path, route.siteKey))}
            />
          </ErrorBoundary>
        ) : (

          <H5PageShell
            route={route}
            navigate={navigate}
            loading={effectiveLoading}
            toastItems={s.toastItems}
            session={s.session}
            memberPhoneMasked={s.memberPhoneMasked}
            dashboard={s.dashboard}
            actionName={s.actionName}
            unreadMessageCount={s.unreadMessageCount}
            primaryTabId={s.primaryTabId}
            secondaryBackPath={s.secondaryBackPath}
            topbarSubtitle={s.topbarSubtitle}
            effectiveWalletSummary={s.effectiveWalletSummary}
            rechargeAmount={s.rechargeAmount}
            transferAllAmount={s.transferAllAmount}
            claimDialogPackage={s.claimDialogPackage}
            showRechargeChannels={s.showRechargeChannels}
            showTransferAllConfirm={s.showTransferAllConfirm}
            onMarkAllMessagesRead={() => s.handleMarkAllMessagesRead()}
            onRecharge={(channel) => s.handleRecharge(channel)}
            onClaimTaskPackage={(id) => s.handleClaimTaskPackage(id)}
            onCloseClaimDialog={s.closeClaimDialog}
            onTransferAllTaskBalance={() => s.handleTransferAllTaskBalance()}
            onSetShowRechargeChannels={s.setShowRechargeChannels}
            onSetShowTransferAllConfirm={s.setShowTransferAllConfirm}
          >
            <React.Suspense fallback={<HomeSkeleton />}>
        {isAuthenticated && route.page === "home" && (s.dashboard || effectiveLoading) ? (
            <HomePage
              dashboard={s.dashboard as H5HomeDashboard}
              homeWalletBalance={s.homeWalletBalance}
              notificationCount={s.notificationCount}
              session={s.session}
              memberPhoneMasked={s.memberPhoneMasked}
              focusTaskPackage={s.focusTaskPackage}
              primaryHomeAction={s.primaryHomeAction}
              unreadMessageCount={s.unreadMessageCount}
              siteKey={route.siteKey}
              actionName={s.actionName}
              onNavigate={(path) => navigate(buildH5Path(path, route.siteKey))}
              onOpenClaimDialog={(id) => s.openClaimDialog(id)}
              onShowTransferAllConfirm={() => s.setShowTransferAllConfirm(true)}
              loading={effectiveLoading}
            />
        ) : null}

        {isAuthenticated && route.page === "tasks" ? (
            <TasksPageShell
              siteKey={route.siteKey}
              navigate={navigate}
              actionName={s.actionName}
              onOpenClaimDialog={s.openClaimDialog}
            />
        ) : null}

        {isAuthenticated && route.page === "task-package" ? (
            <PackageDetailPageShell
              siteKey={route.siteKey}
              navigate={navigate}
              actionName={s.actionName}
              packageId={route.packageId ?? ""}
              onOpenClaimDialog={s.openClaimDialog}
            />
        ) : null}

        {isAuthenticated && route.page === "invite" ? (
            <InvitePageShell
              siteKey={route.siteKey}
              navigate={navigate}
              onCopyText={(value, successMsg, failMsg) => s.handleCopyText(value, successMsg, failMsg)}
            />
        ) : null}

        {isAuthenticated && route.page === "messages" ? (
            <MessagesPage
              messages={s.messages}
              unreadMessageCount={s.unreadMessageCount}
              actionName={s.actionName}
              siteKey={route.siteKey}
              loading={s.messagesLoading}
              error={s.messagesError}
              currentPage={s.messagePage}
              totalMessages={s.messageTotalMessages}
              onMarkAllRead={() => s.handleMarkAllMessagesRead()}
              onOpenMessage={(id) => s.handleOpenMessage(id)}
              onNavigate={(path) => navigate(buildH5Path(path, route.siteKey))}
              onPageChange={(page) => s.handleMessagePageChange(page)}
              onRetry={() => s.handleRetryMessages()}
            />
        ) : null}

        {isAuthenticated && route.page === "profile" && (s.dashboard || effectiveLoading) ? (
            <ProfilePage
              dashboard={s.dashboard as H5HomeDashboard}
              whatsAppBinding={s.whatsAppBinding}
              profileVerificationStatusLabel={s.profileVerificationStatusLabel}
              profileQuickActions={s.profileQuickActions}
              actionName={s.actionName}
              onNavigate={(path) => navigate(buildH5Path(path, route.siteKey))}
              onLogout={() => s.handleLogout()}
              onShowTransferAllConfirm={() => s.setShowTransferAllConfirm(true)}
            />
        ) : null}

        {isAuthenticated && route.page === "settings" && (s.dashboard || effectiveLoading) ? (
          <SettingsPage
              dashboard={s.dashboard as H5HomeDashboard}
              settingsPhone={s.settingsPhone}
              settingsAvatarUrl={s.settingsAvatarUrl}
              settingsCurrentPassword={s.settingsCurrentPassword}
              settingsNextPassword={s.settingsNextPassword}
              settingsConfirmPassword={s.settingsConfirmPassword}
              settingsCurrentPasswordVisible={s.settingsCurrentPasswordVisible}
              settingsNextPasswordVisible={s.settingsNextPasswordVisible}
              settingsConfirmPasswordVisible={s.settingsConfirmPasswordVisible}
              actionName={s.actionName}
              onPhoneChange={s.setSettingsPhone}
              onAvatarChange={(event) => s.handleSettingsAvatarChange(event)}
              onSaveProfile={(event) => s.handleSaveProfileSettings(event)}
              onCurrentPasswordChange={s.setSettingsCurrentPassword}
              onCurrentPasswordToggle={() => s.setSettingsCurrentPasswordVisible((c: boolean) => !c)}
              onNextPasswordChange={s.setSettingsNextPassword}
              onNextPasswordToggle={() => s.setSettingsNextPasswordVisible((c: boolean) => !c)}
              onConfirmPasswordChange={s.setSettingsConfirmPassword}
              onConfirmPasswordToggle={() => s.setSettingsConfirmPasswordVisible((c: boolean) => !c)}
              onChangePassword={(event) => s.handleChangePassword(event)}
              loading={effectiveLoading}
            />
        ) : null}

        {isAuthenticated && route.page === "promotion" && (s.dashboard || effectiveLoading) ? (
            <PromotionPage
              dashboard={s.dashboard as H5HomeDashboard}
              siteKey={route.siteKey}
              onNavigate={(path) => navigate(buildH5Path(path, route.siteKey))}
              onCopyText={(value, successMessage, failureMessage) => s.handleCopyText(value, successMessage, failureMessage)}
              loading={s.promotionsLoading}
              error={s.promotionsError}
            />
        ) : null}

        {isAuthenticated && route.page === "verification" && (s.dashboard || effectiveLoading) ? (
          <VerificationPage
              effectiveVerificationSummary={s.effectiveVerificationSummary}
              verificationRequests={s.verificationRequests}
              verificationRequestDetail={s.verificationRequestDetail}
              verificationHistory={s.verificationHistory}
              verificationNotes={s.verificationNotes}
              focusedVerificationRequest={s.focusedVerificationRequest}
              canSubmitVerificationRequest={s.canSubmitVerificationRequest}
              verificationActionId={s.verificationActionId}
              siteKey={route.siteKey}
              onNavigate={(path) => navigate(buildH5Path(path, route.siteKey))}
              onSubmitVerification={() => s.handleSubmitVerificationRequest()}
              onOpenVerificationRequest={(id) => s.handleOpenVerificationRequest(id)}
              onVerificationNotesChange={s.setVerificationNotes}
              verificationName={s.verificationName}
              verificationIdNumber={s.verificationIdNumber}
              actionName={s.actionName}
              onSubmitVerificationApi={() => s.handleSubmitVerificationApi()}
              onVerificationNameChange={s.setVerificationName}
              onVerificationIdNumberChange={s.setVerificationIdNumber}
              onVerificationPhotoFilesChange={s.setVerificationPhotoFiles}
            />
        ) : null}

        {isAuthenticated && route.page === "recharge" && (s.effectiveWalletSummary || effectiveLoading) ? (
          <RechargePage
              effectiveWalletSummary={s.effectiveWalletSummary as H5WalletSummary}
              rechargeAmount={s.rechargeAmount}
              rechargeHistory={s.rechargeHistory}
              actionName={s.actionName}
              loading={effectiveLoading}
              error={s.error}
              rechargeStatus={s.rechargeStatus}
              onRechargeAmountChange={s.setRechargeAmount}
              onNavigate={(path) => navigate(buildH5Path(path, route.siteKey))}
              onOpenRechargeChannels={s.handleOpenRechargeChannels}
            />
        ) : null}

        {isAuthenticated && route.page === "withdraw" && (s.effectiveWalletSummary || effectiveLoading) ? (
          <WithdrawPage
              effectiveWalletSummary={s.effectiveWalletSummary as H5WalletSummary}
              withdrawAmount={s.withdrawAmount}
              withdrawRequests={s.withdrawRequests}
              maxWithdrawAmount={s.maxWithdrawAmount}
              actionName={s.actionName}
              onWithdrawAmountChange={s.setWithdrawAmount}
              onWithdraw={(event) => s.handleWithdraw(event)}
              onShowTransferAllConfirm={() => s.setShowTransferAllConfirm(true)}
              onSetMaxWithdraw={() => s.setWithdrawAmount(String(s.maxWithdrawAmount))}
            />
        ) : null}

        {isAuthenticated && route.page === "orders" ? (
          <OrdersPage
              filteredOrders={s.filteredOrders}
              orderFilter={s.orderFilter}
              siteKey={route.siteKey}
              onNavigate={(path) => navigate(buildH5Path(path, route.siteKey))}
              onSetOrderFilter={s.setOrderFilter}
              ordersLoading={s.ordersLoading}
              ordersError={s.ordersError}
              ordersPage={s.ordersPage}
              ordersTotal={s.ordersTotal}
              onOrderPageChange={s.handleOrderPageChange}
              onRetryOrders={s.handleRetryOrders}
            />
        ) : null}

        {isAuthenticated && route.page === "tickets" ? (
          <TicketsPage
              page="list"
              siteKey={route.siteKey}
              tickets={s.tickets}
              ticketDetail={s.ticketDetail}
              ticketDraft={s.ticketDraft}
              ticketReply={s.ticketReply}
              actionName={s.actionName}
              loading={s.ticketsLoading}
              error={s.ticketsError}
              onNavigate={(path) => navigate(buildH5Path(path, route.siteKey))}
              onCreateTicket={(event) => s.handleCreateTicket(event)}
              onTicketDraftChange={s.setTicketDraft}
              onTicketReplyChange={s.setTicketReply}
              onReplyToTicket={(event) => s.handleTicketReply(event)}
              onRetry={() => s.handleRetryTickets()}
            />
        ) : null}

        {isAuthenticated && route.page === "ticket-new" ? (
          <TicketsPage
              page="new"
              siteKey={route.siteKey}
              tickets={s.tickets}
              ticketDetail={s.ticketDetail}
              ticketDraft={s.ticketDraft}
              ticketReply={s.ticketReply}
              actionName={s.actionName}
              loading={s.ticketsLoading}
              error={s.ticketsError}
              onNavigate={(path) => navigate(buildH5Path(path, route.siteKey))}
              onCreateTicket={(event) => s.handleCreateTicket(event)}
              onTicketDraftChange={s.setTicketDraft}
              onTicketReplyChange={s.setTicketReply}
              onReplyToTicket={(event) => s.handleTicketReply(event)}
              onRetry={() => s.handleRetryTickets()}
            />
        ) : null}

        {isAuthenticated && route.page === "ticket-detail" && (s.ticketDetail || effectiveLoading) ? (
          <TicketsPage
              page="detail"
              siteKey={route.siteKey}
              tickets={s.tickets}
              ticketDetail={s.ticketDetail}
              ticketDraft={s.ticketDraft}
              ticketReply={s.ticketReply}
              actionName={s.actionName}
              loading={s.ticketsLoading}
              error={s.ticketsError}
              onNavigate={(path) => navigate(buildH5Path(path, route.siteKey))}
              onCreateTicket={(event) => s.handleCreateTicket(event)}
              onTicketDraftChange={s.setTicketDraft}
              onTicketReplyChange={s.setTicketReply}
              onReplyToTicket={(event) => s.handleTicketReply(event)}
              onRetry={() => s.handleRetryTickets()}
            />
        ) : null}

        {isAuthenticated && route.page === "fragments" && (s.fragmentOverview || effectiveLoading) ? (
          <FragmentsPage
              fragmentOverview={s.fragmentOverview as H5FragmentOverview}
              fragmentCompletion={s.fragmentCompletion}
              canExchangeFragments={s.canExchangeFragments}
              latestShippingOrder={s.latestShippingOrder}
              fragmentStageTitle={s.fragmentStageTitle}
              fragmentStageDescription={s.fragmentStageDescription}
              shippingForm={s.shippingForm}
              actionName={s.actionName}
              fragmentsLoading={s.fragmentsLoading}
              fragmentsError={s.fragmentsError}
              onCheckIn={() => s.handleCheckIn()}
              onExchange={(event) => s.handleFragmentExchange(event)}
              onShippingFormChange={(field, value) => s.setShippingForm((current) => ({ ...current, [field]: value }))}
              onRetry={() => s.handleRetryFragments()}
            />
        ) : null}

        {isAuthenticated && route.page === "leaderboard" ? (
          <LeaderboardPage leaderboard={s.leaderboard} loading={effectiveLoading} error={null} />
        ) : null}

        {isAuthenticated && route.page === "whatsapp" ? (
          <WhatsAppPage
              whatsAppBinding={s.whatsAppBinding}
              actionName={s.actionName}
              onStartBinding={() => s.handleStartWhatsAppBinding()}
              whatsappPhone={s.whatsappPhone}
              onWhatsappPhoneChange={s.setWhatsappPhone}
              onStartWhatsAppBindingApi={() => s.handleStartWhatsAppBindingApi()}
              chatMessages={s.chatMessages}
              chatLoading={s.chatLoading}
              chatHasMore={s.chatHasMore}
              onSendMessage={(content, type) => s.handleSendMessage(content, type)}
              onLoadMoreMessages={() => s.handleLoadMoreMessages()}
              onRefreshMessages={() => s.handleRefreshMessages()}
              onBack={() => s.navigate(s.secondaryBackPath)}
            />
        ) : null}
            </React.Suspense>
          </H5PageShell>
        )}
      </React.Suspense>
    </ErrorBoundary>
  );
}
