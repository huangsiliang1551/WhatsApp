import { type JSX } from "react";
import {
  AppstoreOutlined,
  BellOutlined,
  TrophyOutlined,
  WalletOutlined,
} from "@ant-design/icons";

import type { H5HomeDashboard, H5MemberSession, H5TaskPackage, H5WalletSummary } from "../../services/h5Member";
import { maskAccountId } from "../../services/h5Member";
import { t } from "./i18n";
import { HomeSkeleton } from "./skeletons";
import {
  formatMoney,
  formatPercentage,
  getHomeFragmentMeta,
  getHomeFragmentSideNote,
  getHomePrimaryAction,
  getTaskPackageStatusLabel,
  getTaskPackageTypeLabel,
  getVerificationStatusLabel,
  type HomePrimaryAction,
} from "./sharedUtils";
import { CompactListRow, EmptyStateCard, MessageFeedItem, QuickActionCard, SectionHeader } from "./sharedComponents";

type FocusTaskPackage = H5TaskPackage & {
  totalCommission: number;
  currentCommission: number;
  completedItems: number;
  totalItems: number;
  countdownSeconds: number;
};

type HomePageProps = {
  dashboard: H5HomeDashboard;
  session: H5MemberSession | null;
  memberPhoneMasked: string;
  focusTaskPackage: FocusTaskPackage | null;
  primaryHomeAction: HomePrimaryAction;
  unreadMessageCount: number;
  siteKey: string;
  actionName: string | null;
  homeWalletBalance: H5WalletSummary | null;
  notificationCount: number;
  loading?: boolean;
  onNavigate: (path: string) => void;
  onOpenClaimDialog: (packageId: string) => void;
  onShowTransferAllConfirm: () => void;
};

function getPrimaryActionPath(action: HomePrimaryAction): string {
  if (action.kind === "withdraw") return "/h5/withdraw";
  if (action.kind === "recharge") return "/h5/wallet";
  return "/h5/tasks";
}

export function HomePage({
  dashboard,
  session,
  memberPhoneMasked,
  focusTaskPackage,
  primaryHomeAction,
  unreadMessageCount,
  siteKey,
  actionName,
  homeWalletBalance,
  notificationCount,
  loading = false,
  onNavigate,
  onOpenClaimDialog,
  onShowTransferAllConfirm,
}: HomePageProps): JSX.Element {
  if (loading) return <HomeSkeleton />;

  const todayEarned = focusTaskPackage?.currentCommission ?? 0;
  const withdrawable = dashboard.wallet.systemBalance;
  const weeklyGoalTarget = 3;
  const weeklyGoalDone = Math.min(
    weeklyGoalTarget,
    dashboard.activeCount + dashboard.pendingClaimCount + (dashboard.wallet.canWithdraw ? 1 : 0),
  );
  const weeklyGoalProgress = weeklyGoalDone / weeklyGoalTarget;
  const headerAction = getHomePrimaryAction(focusTaskPackage, dashboard.wallet);
  const recentNotice = dashboard.recentMessages[0] ?? null;
  const accountHint = session ? maskAccountId(session.accountId) : memberPhoneMasked;
  const displayName = session?.displayName || dashboard.member.displayName || accountHint;
  const statusInitial = displayName.trim().charAt(0).toUpperCase() || accountHint.charAt(0).toUpperCase();
  const statusDate = new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    weekday: "short",
  }).format(new Date());
  const verificationStatus = getVerificationStatusLabel(dashboard.verification.currentStatus);
  const statusAlerts = notificationCount > 0 ? t("home.statusAlerts", { count: notificationCount }) : t("home.statusClear");

  return (
    <section className="h5-card-stack">
      <section className="h5-card h5-member-home-command">
        <div className="h5-member-home-status-panel">
          <div className="h5-member-home-status">
            <button
              aria-label={t("profile.title")}
              className="h5-member-home-status-avatar"
              onClick={() => onNavigate("/h5/profile")}
              type="button"
            >
              {statusInitial}
            </button>
            <div className="h5-member-home-status-copy">
              <strong>{t("home.statusGreeting", { name: displayName })}</strong>
              <span>{t("home.statusContext", { date: statusDate, account: accountHint })}</span>
            </div>
          </div>

          <div className="h5-member-home-status-rail">
            <span className="h5-member-inline-pill">{t("home.statusVerification", { status: verificationStatus })}</span>
            <span className="h5-member-inline-pill">{statusAlerts}</span>
          </div>
        </div>

        <SectionHeader meta={t("home.todayTargetMeta")} title={t("home.todayEarningsTitle")} />

        <div className="h5-member-home-metric-grid">
          <article className="h5-member-home-metric-card">
            <span className="h5-member-home-metric-label">{t("home.todayEarningsMetric")}</span>
            <strong className="h5-member-home-metric-value">{formatMoney(todayEarned, dashboard.wallet.currency)}</strong>
            <span className="h5-member-home-metric-note">{primaryHomeAction.title}</span>
          </article>

          <article className="h5-member-home-metric-card">
            <span className="h5-member-home-metric-label">{t("home.withdrawableBalanceMetric")}</span>
            <strong className="h5-member-home-metric-value">{formatMoney(withdrawable, dashboard.wallet.currency)}</strong>
            <span className="h5-member-home-metric-note">
              {dashboard.wallet.canWithdraw
                ? t("home.canWithdraw")
                : t("home.shortfallHint", { amount: formatMoney(dashboard.wallet.shortfallAmount, dashboard.wallet.currency) })}
            </span>
          </article>

          <article className="h5-member-home-metric-card">
            <span className="h5-member-home-metric-label">{t("home.goalProgressMetric")}</span>
            <strong className="h5-member-home-metric-value">{formatPercentage(weeklyGoalProgress)}</strong>
            <span className="h5-member-home-metric-note">{`${weeklyGoalDone}/${weeklyGoalTarget}`}</span>
          </article>
        </div>

        <div className="h5-member-home-command-panel">
          <div className="h5-member-home-command-copy">
            <strong>{headerAction.title}</strong>
            <p className="muted">{headerAction.description}</p>
          </div>
          <div className="h5-member-home-command-signals">
            <span className="h5-member-inline-pill">{t("home.pendingClaimCount", { count: dashboard.pendingClaimCount })}</span>
            <span className="h5-member-inline-pill">{t("home.activeCount", { count: dashboard.activeCount })}</span>
            <span className="h5-member-inline-pill">{t("home.expiringCount", { count: dashboard.expiringCount })}</span>
            {notificationCount > 0 ? (
              <span className="h5-member-inline-pill">{t("home.unread", { count: notificationCount })}</span>
            ) : null}
          </div>
          <div className="h5-member-card-actions">
            <button
              className="seed-button"
              disabled={actionName === "claim-home" || actionName === "withdraw" || actionName === "recharge"}
              onClick={() => {
                if (primaryHomeAction.kind === "claim" && focusTaskPackage) {
                  onOpenClaimDialog(focusTaskPackage.id);
                  return;
                }
                if (primaryHomeAction.kind === "continue" && focusTaskPackage) {
                  onNavigate(`/h5/tasks/package/${focusTaskPackage.id}`);
                  return;
                }
                onNavigate(getPrimaryActionPath(primaryHomeAction));
              }}
              type="button"
            >
              {primaryHomeAction.buttonLabel}
            </button>
            <button className="seed-button seed-button-secondary" onClick={() => onNavigate("/h5/tasks")} type="button">
              {t("home.taskCenter")}
            </button>
          </div>
        </div>
      </section>

      <section className="h5-card">
        <SectionHeader meta={t("home.taskCenterSectionMeta")} title={t("home.inProgressSection")} />
        <div className="h5-card-stack">
          {focusTaskPackage ? (
            <CompactListRow
              actionLabel={primaryHomeAction.buttonLabel}
              badge={getTaskPackageStatusLabel(focusTaskPackage.status)}
              meta={getTaskPackageTypeLabel(focusTaskPackage.type)}
              onClick={() => {
                if (focusTaskPackage.status === "pending_claim") {
                  onOpenClaimDialog(focusTaskPackage.id);
                  return;
                }
                onNavigate(`/h5/tasks/package/${focusTaskPackage.id}`);
              }}
              sideNote={t("home.progressLabel", {
                done: focusTaskPackage.completedItems,
                total: focusTaskPackage.totalItems,
              })}
              title={focusTaskPackage.title}
              tone={focusTaskPackage.status === "completed" ? "success" : "active"}
              value={formatMoney(focusTaskPackage.totalCommission, dashboard.wallet.currency)}
            />
          ) : (
            <EmptyStateCard
              description={t("tasks.noPackagesDesc")}
              icon={<AppstoreOutlined />}
              title={t("home.currentMainAction")}
            />
          )}
        </div>
      </section>

      <section className="h5-card">
        <SectionHeader meta={t("home.taskRecommendationMeta")} title={t("home.recommendedTasksSection")} />
        <div className="h5-member-home-section-grid">
          <QuickActionCard
            body={t("home.taskCenterDesc")}
            compact
            icon={<AppstoreOutlined />}
            meta={t("home.pendingClaimCount", { count: dashboard.pendingClaimCount + dashboard.activeCount })}
            onClick={() => onNavigate("/h5/tasks")}
            title={t("home.taskCenter")}
          />
          <QuickActionCard
            body={t("home.rechargeWithdrawDesc")}
            compact
            icon={<WalletOutlined />}
            meta={dashboard.wallet.canWithdraw ? t("home.canWithdraw") : t("home.recharge")}
            onClick={() => onNavigate(dashboard.wallet.canWithdraw ? "/h5/withdraw" : "/h5/wallet")}
            title={t("home.rechargeWithdraw")}
          />
        </div>
      </section>

      <section className="h5-card">
        <SectionHeader meta={t("home.growthSectionMeta")} title={t("home.growthSection")} />
        <div className="h5-card-stack">
          <CompactListRow
            actionLabel={t("common.view")}
            meta={dashboard.member.inviteCode}
            onClick={() => onNavigate("/h5/promotion")}
            sideNote={t("home.promotionDesc")}
            title={t("home.promotion")}
            tone="active"
          />
          <CompactListRow
            actionLabel={t("common.view")}
            meta={getHomeFragmentMeta(dashboard.fragments)}
            onClick={() => onNavigate("/h5/fragments")}
            sideNote={getHomeFragmentSideNote(dashboard.fragments)}
            title={t("home.fragments")}
            tone={dashboard.fragments.canExchange ? "success" : "default"}
          />
          <CompactListRow
            actionLabel={t("common.viewAll")}
            meta={t("home.cumulativeRankings")}
            onClick={() => onNavigate("/h5/leaderboard")}
            sideNote={`Top ${dashboard.leaderboard.length}`}
            title={t("home.withdrawLeaderboard")}
            tone="active"
          />
          <CompactListRow
            actionLabel={t("home.transferAll")}
            meta={homeWalletBalance ? formatMoney(homeWalletBalance.taskBalance, homeWalletBalance.currency) : formatMoney(dashboard.wallet.taskBalance, dashboard.wallet.currency)}
            onClick={onShowTransferAllConfirm}
            sideNote={formatMoney(dashboard.wallet.systemBalance, dashboard.wallet.currency)}
            title={t("home.taskBalance")}
            tone="success"
            value={formatMoney(dashboard.wallet.taskBalance, dashboard.wallet.currency)}
          />
        </div>
      </section>

      <section className="h5-card">
        <SectionHeader meta={t("home.supportSectionMeta")} title={t("home.supportSection")} />
        <div className="h5-card-stack">
          {recentNotice ? (
            <MessageFeedItem item={recentNotice} onClick={() => onNavigate("/h5/messages")} />
          ) : (
            <EmptyStateCard
              description={t("home.recentActivityEmpty")}
              icon={<BellOutlined />}
              title={t("home.noRecentActivity")}
            />
          )}

          <CompactListRow
            actionLabel={t("common.view")}
            meta={t("home.systemReminders")}
            onClick={() => onNavigate("/h5/messages")}
            sideNote={t("home.unread", { count: unreadMessageCount })}
            title={t("home.importantNotice")}
            tone={unreadMessageCount > 0 ? "active" : "default"}
          />
          <CompactListRow
            actionLabel={t("common.view")}
            meta={getVerificationStatusLabel(dashboard.verification.currentStatus)}
            onClick={() => onNavigate("/h5/verification")}
            sideNote={accountHint}
            title={t("home.memberVerification")}
            tone={dashboard.verification.currentStatus === "approved" ? "success" : "default"}
          />
          <CompactListRow
            actionLabel={t("common.enter")}
            meta={siteKey}
            onClick={() => onNavigate("/h5/tickets/new")}
            sideNote={memberPhoneMasked}
            title={t("home.ticketComplaint")}
            tone="default"
          />
        </div>
      </section>

      {dashboard.leaderboard.length === 0 ? (
        <section className="h5-card">
          <EmptyStateCard
            description={t("home.noLeaderboardDesc")}
            icon={<TrophyOutlined />}
            title={t("home.noLeaderboard")}
          />
        </section>
      ) : null}
    </section>
  );
}
