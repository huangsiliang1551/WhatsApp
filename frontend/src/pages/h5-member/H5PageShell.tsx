import { useEffect, type JSX, type ReactNode } from "react";
import {
  AppstoreOutlined,
  BellOutlined,
  HomeOutlined,
  LeftOutlined,
  UserOutlined,
  WalletOutlined,
} from "@ant-design/icons";

import { maskAccountId, type H5MemberSession, type H5HomeDashboard, type H5WalletSummary, type H5TaskPackage } from "../../services/h5Member";
import { t } from './i18n';
import { useNetworkStatus } from './useNetworkStatus';
import type { ParsedRoute } from "./useH5MemberApp";
import {
  buildH5Path,
  getCurrentLocale,
  formatMoney,
  getRechargeChannelOptions,
  getRouteTitle,
  getVerificationStatusLabel,
  syncDocumentLocale,
  type ToastItem,
} from "./sharedUtils";
import { SectionHeader, ToastStack } from "./sharedComponents";
import { h5ScrollableViewportStyle, useRootScrollUnlock } from "./useRootScrollUnlock";

export type H5PageShellProps = {
  children: ReactNode;
  route: ParsedRoute;
  navigate: (path: string) => void;
  loading: boolean;
  toastItems: ToastItem[];
  session: H5MemberSession | null;
  memberPhoneMasked: string;
  dashboard: H5HomeDashboard | null;
  actionName: string | null;
  unreadMessageCount: number;
  primaryTabId: string;
  secondaryBackPath: string;
  topbarSubtitle: string;
  effectiveWalletSummary: H5WalletSummary | null;
  rechargeAmount: string;
  transferAllAmount: number;
  claimDialogPackage: H5TaskPackage | null;
  showRechargeChannels: boolean;
  showTransferAllConfirm: boolean;
  onMarkAllMessagesRead: () => void;
  onRecharge: (channelName: string) => void;
  onClaimTaskPackage: (packageId: string) => void;
  onCloseClaimDialog: () => void;
  onTransferAllTaskBalance: () => void;
  onSetShowRechargeChannels: (v: boolean) => void;
  onSetShowTransferAllConfirm: (v: boolean) => void;
};

export function H5PageShell(props: H5PageShellProps): JSX.Element {
  const rechargeChannelOptions = getRechargeChannelOptions();
  const {
    children,
    route,
    navigate,
    loading,
    toastItems,
    session,
    memberPhoneMasked,
    dashboard,
    actionName,
    unreadMessageCount,
    primaryTabId,
    secondaryBackPath,
    topbarSubtitle,
    effectiveWalletSummary,
    rechargeAmount,
    transferAllAmount,
    claimDialogPackage,
    showRechargeChannels,
    showTransferAllConfirm,
    onMarkAllMessagesRead,
    onRecharge,
    onClaimTaskPackage,
    onCloseClaimDialog,
    onTransferAllTaskBalance,
    onSetShowRechargeChannels,
    onSetShowTransferAllConfirm,
  } = props;

  const { isOnline, isWeakNetwork } = useNetworkStatus();
  const isWhatsAppRoute = route.page === "whatsapp";
  const isHomeRoute = route.page === "home";
  const contentClassName = isWhatsAppRoute ? "h5-member-content h5-member-content-chat" : "h5-member-content";
  const useCompactToast = ["home", "tasks", "profile", "recharge"].includes(route.page);
  const homeTopbarTitle =
    dashboard?.member.displayName?.trim()
    || session?.displayName?.trim()
    || dashboard?.site.brand_name
    || t("shell.brandName");
  const homeAccountHint =
    dashboard?.member.accountIdMasked
    || (session ? maskAccountId(session.accountId) : memberPhoneMasked);
  const homeDateHint = new Intl.DateTimeFormat(getCurrentLocale(), {
    month: "short",
    day: "numeric",
    weekday: "short",
  }).format(new Date());
  const homeTopbarSubtitle = `${homeDateHint} | ${homeAccountHint}`;
  const homeVerificationStatus = dashboard ? getVerificationStatusLabel(dashboard.verification.currentStatus) : null;
  const homeAvatarLabel = homeTopbarTitle.slice(0, 1).toUpperCase();

  useEffect(() => {
    syncDocumentLocale();
  });

  useRootScrollUnlock();

  return (
    <main className="h5-shell h5-member-app-shell" style={h5ScrollableViewportStyle}>
      <ToastStack compact={useCompactToast} items={toastItems} />

      {!isOnline && (
        <div className="h5-network-banner h5-network-banner-offline">
          {t('network.offline')}
        </div>
      )}
      {isOnline && isWeakNetwork && (
        <div className="h5-network-banner h5-network-banner-weak">
          {t('network.weak')}
        </div>
      )}

      <header className={`h5-member-topbar ${isHomeRoute ? "h5-member-topbar-home" : ""}`}>
        <div className="h5-member-topbar-main">
          {isHomeRoute || route.page === "tasks" || route.page === "recharge" || route.page === "profile" ? null : (
            <button className="h5-member-back-button" onClick={() => navigate(secondaryBackPath)} type="button">
              <LeftOutlined />
              <span>{t('common.back')}</span>
            </button>
          )}
          {isHomeRoute ? (
            <div className="h5-member-home-status">
              <button
                aria-label={t("profile.accountCenter")}
                className="h5-member-home-status-avatar"
                onClick={() => navigate(buildH5Path("/h5/me", route.siteKey))}
                type="button"
              >
                <span>{homeAvatarLabel}</span>
              </button>
              <div className="h5-member-home-status-copy">
                <strong title={homeTopbarTitle}>{homeTopbarTitle}</strong>
                <span title={homeTopbarSubtitle}>{homeTopbarSubtitle}</span>
              </div>
            </div>
          ) : (
            <div className="h5-member-topbar-title-group">
              <strong title={getRouteTitle(route)}>
                {getRouteTitle(route)}
              </strong>
              <span title={topbarSubtitle}>{topbarSubtitle}</span>
            </div>
          )}
          {route.page === "messages" ? (
            <button className="h5-member-msg-topbar-btn" onClick={onMarkAllMessagesRead} type="button">
              {actionName === "read-all" ? t('shell.markingAllRead') : t('shell.markAllRead')}
              <span className="h5-member-msg-topbar-count">{unreadMessageCount}</span>
            </button>
          ) : null}
        </div>

        <div className="h5-member-topbar-side">
          {isHomeRoute && dashboard ? (
            <>
              <button className="h5-member-topbar-pill" onClick={() => navigate(buildH5Path("/h5/messages", route.siteKey))} type="button">
                <BellOutlined />
                <span>{dashboard.unreadCount}</span>
              </button>
              <button
                className="h5-member-topbar-pill h5-member-topbar-pill-secondary"
                onClick={() => navigate(buildH5Path("/h5/verification", route.siteKey))}
                type="button"
              >
                <span>{homeVerificationStatus}</span>
              </button>
            </>
          ) : null}

          {route.page === "tickets" ? (
            <button className="seed-button seed-button-secondary" onClick={() => navigate(buildH5Path("/h5/tickets/new", route.siteKey))} type="button">
              {t('tickets.newTicket')}
            </button>
          ) : null}
        </div>
      </header>

      <section className={contentClassName}>
        {loading ? <article className="h5-card h5-empty-card">{t('shell.loading')}</article> : null}

        {!loading ? children : null}

        {showRechargeChannels ? (
          <div className="h5-member-claim-confirm-backdrop" role="presentation">
            <article aria-modal="true" className="h5-card h5-member-claim-confirm" role="dialog">
              <SectionHeader title={t('recharge.selectChannel')} />
              <div className="h5-card-stack">
                <strong>{t('recharge.rechargeAmount', { amount: formatMoney(Number(rechargeAmount || 0), effectiveWalletSummary?.currency ?? "USD") })}</strong>
                <p className="muted">{t('recharge.channelHint')}</p>
                <div className="h5-card-stack">
                  {rechargeChannelOptions.map((channel) => (
                    <button
                      className="h5-member-profile-quick-card"
                      disabled={actionName === "recharge"}
                      key={channel.id}
                      onClick={() => onRecharge(channel.label)}
                      type="button"
                    >
                      <span className="h5-member-profile-quick-icon">
                        <WalletOutlined />
                      </span>
                      <span className="h5-member-profile-quick-copy">
                        <strong>{channel.label}</strong>
                        <span>{channel.description}</span>
                      </span>
                    </button>
                  ))}
                </div>
              </div>
              <div className="h5-member-card-actions">
                <button className="seed-button seed-button-secondary" disabled={actionName === "recharge"} onClick={() => onSetShowRechargeChannels(false)} type="button">
                  {t('common.cancel')}
                </button>
              </div>
            </article>
          </div>
        ) : null}

        {showTransferAllConfirm ? (
          <div className="h5-member-claim-confirm-backdrop" role="presentation">
            <article aria-modal="true" className="h5-card h5-member-claim-confirm" role="dialog">
              <SectionHeader title={t('shell.confirmTransfer')} />
              <div className="h5-card-stack">
                <strong>{t('shell.transferConfirm', { amount: formatMoney(transferAllAmount, effectiveWalletSummary?.currency ?? "USD") })}</strong>
                <p className="muted">{t('shell.transferHint')}</p>
              </div>
              <div className="h5-member-card-actions">
                <button className="seed-button seed-button-secondary" disabled={actionName === "transfer"} onClick={() => onSetShowTransferAllConfirm(false)} type="button">
                  {t('common.cancel')}
                </button>
                <button className="seed-button" disabled={actionName === "transfer" || transferAllAmount <= 0} onClick={onTransferAllTaskBalance} type="button">
                  {actionName === "transfer" ? t('shell.transferProcessing') : t('shell.transferConfirmBtn')}
                </button>
              </div>
            </article>
          </div>
        ) : null}

        {claimDialogPackage ? (
          <div className="h5-member-claim-confirm-backdrop" role="presentation">
            <article aria-modal="true" className="h5-card h5-member-claim-confirm" role="dialog">
              <SectionHeader title={t('shell.confirmClaim')} />
              <div className="h5-card-stack">
                <strong>{claimDialogPackage.title}</strong>
                <p className="muted">{t('shell.claimHint')}</p>
                <div className="template-detail-grid">
                  <span>{t('shell.claimRule1')}</span>
                  <span>{t('shell.claimRule2')}</span>
                  <span>{t('shell.claimRule3')}</span>
                  <span>{t('shell.claimRule4')}</span>
                </div>
              </div>
              <div className="h5-member-card-actions">
                <button className="seed-button seed-button-secondary" disabled={Boolean(actionName?.startsWith("claim:"))} onClick={onCloseClaimDialog} type="button">
                  {t('common.cancel')}
                </button>
                <button
                  className="seed-button"
                  disabled={actionName === `claim:${claimDialogPackage.id}`}
                  onClick={() => onClaimTaskPackage(claimDialogPackage.id)}
                  type="button"
                >
                  {actionName === `claim:${claimDialogPackage.id}` ? t('shell.claiming') : t('shell.confirmClaimBtn')}
                </button>
              </div>
            </article>
          </div>
        ) : null}

        <div className="h5-member-safe-bottom" />
      </section>

      <nav className="h5-member-tabbar">
        {[
          { id: "home", label: t('shell.tabHome'), path: buildH5Path("/h5/home", route.siteKey), icon: <HomeOutlined /> },
          { id: "tasks", label: t('shell.tabTasks'), path: buildH5Path("/h5/tasks", route.siteKey), icon: <AppstoreOutlined /> },
          { id: "earnings", label: t('shell.tabEarnings'), path: buildH5Path("/h5/wallet", route.siteKey), icon: <WalletOutlined /> },
          { id: "profile", label: t('shell.tabProfile'), path: buildH5Path("/h5/me", route.siteKey), icon: <UserOutlined /> },
        ].map((item) => (
          <button className={`h5-member-tabbar-item ${primaryTabId === item.id ? "h5-member-tabbar-item-active" : ""}`} key={item.id} onClick={() => navigate(item.path)} type="button">
            <span className="h5-member-tabbar-icon">
              {item.icon}
              {item.id === "profile" && unreadMessageCount > 0 ? <span className="h5-member-tabbar-badge">{unreadMessageCount > 99 ? "99+" : unreadMessageCount}</span> : null}
            </span>
            <span>{item.label}</span>
          </button>
        ))}
      </nav>
    </main>
  );
}
