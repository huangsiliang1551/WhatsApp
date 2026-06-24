import type { JSX } from "react";
import {
  CheckCircleOutlined,
  FireOutlined,
  UserOutlined,
} from "@ant-design/icons";

import type { H5HomeDashboard, H5SignInStatus, H5WhatsAppBinding } from "../../services/h5Member";
import {
  formatMoney,
  getCurrentLocale,
  getProfileActionIcon,
  type ProfileQuickAction,
} from "./sharedUtils";
import { CompactListRow, SectionHeader } from "./sharedComponents";
import { t } from "./i18n";
import { ProfileSkeleton } from "./skeletons";

type ProfilePageProps = {
  dashboard: H5HomeDashboard;
  whatsAppBinding: H5WhatsAppBinding | null;
  profileVerificationStatusLabel: string;
  profileQuickActions: ProfileQuickAction[];
  actionName: string | null;
  onNavigate: (path: string) => void;
  onLogout: () => void;
  onShowTransferAllConfirm: () => void;
  loading?: boolean;
  signInStatus?: H5SignInStatus | null;
  onSignIn?: () => Promise<void>;
};

export function ProfilePage({
  dashboard,
  whatsAppBinding,
  profileVerificationStatusLabel,
  profileQuickActions,
  actionName,
  onNavigate,
  onLogout,
  onShowTransferAllConfirm,
  loading = false,
  signInStatus,
  onSignIn,
}: ProfilePageProps): JSX.Element {
  if (loading) return <ProfileSkeleton />;

  const memberSinceLabel = dashboard.member.createdAt
    ? new Intl.DateTimeFormat(getCurrentLocale(), {
        year: "numeric",
        month: "short",
        day: "numeric",
      }).format(new Date(dashboard.member.createdAt))
    : t("common.none");
  const secondaryQuickActions = profileQuickActions.filter((item) => item.key === "promotion" || item.key === "orders");
  const serviceRows: Array<{
    key: string;
    title: string;
    meta: string;
    sideNote: string;
    path: string;
    tone: "default" | "active" | "success" | "danger";
  }> = [
    {
      key: "verification",
      title: t("verification.title"),
      meta: profileVerificationStatusLabel,
      sideNote: "",
      path: "/h5/verification",
      tone: dashboard.verification.currentStatus === "approved" ? "success" : "default",
    },
    {
      key: "whatsapp",
      title: t("whatsapp.title"),
      meta: whatsAppBinding?.isBound ? t("profile.waBound") : t("profile.waUnbound"),
      sideNote: whatsAppBinding?.phoneNumber ?? t("common.none"),
      path: "/h5/whatsapp",
      tone: whatsAppBinding?.isBound ? "success" : "default",
    },
    {
      key: "messages",
      title: t("messages.title"),
      meta: t("home.systemReminders"),
      sideNote: t("home.unread", { count: dashboard.unreadCount }),
      path: "/h5/messages",
      tone: dashboard.unreadCount > 0 ? "active" : "default",
    },
    {
      key: "support",
      title: t("tickets.title"),
      meta: t("tickets.ticketListDesc"),
      sideNote: "",
      path: "/h5/tickets",
      tone: "default",
    },
    {
      key: "settings",
      title: t("settings.title"),
      meta: t("profile.clickToSettings"),
      sideNote: "",
      path: "/h5/me/settings",
      tone: "default",
    },
  ];

  return (
    <section className="h5-card-stack">
      <article className="h5-card h5-member-profile-overview">
        <SectionHeader meta={t("profile.identityMeta")} title={t("profile.accountCenter")} />

        <div className="h5-member-profile-hero">
          <div className="h5-member-profile-hero-main">
            <button className="h5-member-profile-avatar-button" onClick={() => onNavigate("/h5/me/settings")} type="button">
              <div className="h5-member-profile-avatar" aria-hidden="true">
                {dashboard.member.avatarUrl ? (
                  <img alt={t("profile.title")} className="h5-member-profile-avatar-image" src={dashboard.member.avatarUrl} />
                ) : (
                  <UserOutlined />
                )}
              </div>
            </button>

            <div className="h5-member-profile-hero-copy">
              <div className="h5-member-profile-heading-row">
                <strong>{dashboard.member.displayName || dashboard.member.phone}</strong>
                {signInStatus && !signInStatus.isCompleted ? (
                  signInStatus.todaySignedIn ? (
                    <span className="h5-profile-signin-btn h5-profile-signin-btn-done">
                      <CheckCircleOutlined /> {t("tasks.consecutiveDays", { n: signInStatus.consecutiveDays })}
                    </span>
                  ) : (
                    <button
                      className="h5-profile-signin-btn"
                      disabled={actionName === "profile-signin"}
                      onClick={() => void onSignIn?.()}
                      type="button"
                    >
                      <FireOutlined /> {t("tasks.signIn")}
                    </button>
                  )
                ) : null}
              </div>

              <p>{dashboard.member.accountIdMasked || dashboard.member.phone}</p>

              <div className="h5-member-profile-status-row">
                <span
                  aria-label={whatsAppBinding?.isBound ? t("profile.waBound") : t("profile.waUnbound")}
                  className={`h5-member-whatsapp-status-icon ${
                    whatsAppBinding?.isBound ? "h5-member-whatsapp-status-icon-bound" : "h5-member-whatsapp-status-icon-unbound"
                  }`}
                  role="img"
                  title={
                    whatsAppBinding?.isBound
                      ? (whatsAppBinding.phoneNumber ? t("profile.waBoundWithPhone", { phone: whatsAppBinding.phoneNumber }) : t("profile.waBound"))
                      : t("profile.waUnbound")
                  }
                >
                  WA
                </span>
                <button
                  className="h5-member-inline-pill h5-member-profile-status-trigger"
                  onClick={() => onNavigate("/h5/verification")}
                  type="button"
                >
                  {profileVerificationStatusLabel}
                </button>
              </div>
            </div>
          </div>
        </div>

        <div className="h5-member-profile-stat-strip">
          <article className="h5-member-profile-stat-pill">
            <strong>{memberSinceLabel}</strong>
            <span>{t("profile.snapshotMemberSince")}</span>
          </article>
          <article className="h5-member-profile-stat-pill">
            <strong>{dashboard.activeCount}</strong>
            <span>{t("profile.snapshotActiveTasks")}</span>
          </article>
          <article className="h5-member-profile-stat-pill">
            <strong>{dashboard.pendingClaimCount}</strong>
            <span>{t("profile.snapshotPendingClaim")}</span>
          </article>
        </div>

        <div className="h5-member-profile-balance-strip">
          <article className="h5-member-profile-balance-card">
            <div className="h5-member-balance-card-main">
              <span className="h5-member-balance-card-label">{t("profile.systemBalance")}</span>
              <strong className="h5-member-balance-card-value">{formatMoney(dashboard.wallet.systemBalance)}</strong>
            </div>
            <div className="h5-member-balance-card-actions">
              <button className="seed-button seed-button-secondary h5-member-balance-pill-button" onClick={() => onNavigate("/h5/wallet")} type="button">
                {t("profile.recharge")}
              </button>
              <button className="seed-button seed-button-secondary h5-member-balance-pill-button" onClick={() => onNavigate("/h5/withdraw")} type="button">
                {t("profile.withdraw")}
              </button>
            </div>
          </article>

          <article className="h5-member-profile-balance-card">
            <div className="h5-member-balance-card-main">
              <span className="h5-member-balance-card-label">{t("profile.taskBalance")}</span>
              <strong className="h5-member-balance-card-value">{formatMoney(dashboard.wallet.taskBalance)}</strong>
            </div>
            <div className="h5-member-balance-card-actions">
              <button className="seed-button seed-button-secondary h5-member-balance-pill-button" onClick={onShowTransferAllConfirm} type="button">
                {t("profile.transferAll")}
              </button>
            </div>
          </article>
        </div>
      </article>

      <article className="h5-card">
        <SectionHeader meta={t("profile.serviceCenterMeta")} title={t("profile.serviceCenter")} />
        <div className="h5-member-profile-group">
          <div className="h5-member-profile-group-head">
            <strong className="h5-member-profile-group-title">{t("profile.serviceSnapshotTitle")}</strong>
            <span className="h5-member-profile-group-meta">{t("profile.serviceSnapshotMeta")}</span>
          </div>
          <div className="h5-member-profile-service-strip">
            <article className="h5-member-profile-service-pill">
              <strong>{profileVerificationStatusLabel}</strong>
              <span>{t("profile.serviceVerification")}</span>
              <small>{dashboard.verification.hasActiveRequest ? t("verification.currentRequest") : t("verification.verificationStatus")}</small>
            </article>
            <article className="h5-member-profile-service-pill">
              <strong>{t("home.unread", { count: dashboard.unreadCount })}</strong>
              <span>{t("profile.serviceMessages")}</span>
              <small>{t("home.systemReminders")}</small>
            </article>
            <article className="h5-member-profile-service-pill">
              <strong>{whatsAppBinding?.isBound ? t("profile.waBound") : t("profile.waUnbound")}</strong>
              <span>{t("profile.serviceBinding")}</span>
              <small>{whatsAppBinding?.phoneNumber ?? t("common.none")}</small>
            </article>
          </div>
        </div>
        <div className="h5-card-stack h5-member-profile-service-list">
          {serviceRows.map((item) => (
            <CompactListRow
              actionLabel={t("common.enter")}
              key={item.key}
              meta={item.meta}
              onClick={() => onNavigate(item.path)}
              sideNote={item.sideNote}
              title={item.title}
              tone={item.tone}
            />
          ))}
        </div>
      </article>

      {secondaryQuickActions.length > 0 ? (
        <article className="h5-card h5-member-profile-quick-actions">
          <SectionHeader meta={t("profile.activityHubMeta")} title={t("profile.commonEntries")} />
          <div className="h5-member-profile-quick-grid">
            {secondaryQuickActions.map((item) => (
              <button className="h5-member-profile-quick-card" key={`${item.path}:${item.label}`} onClick={() => onNavigate(item.path)} type="button">
                <span className="h5-member-profile-quick-icon">{getProfileActionIcon(item.key)}</span>
                <span className="h5-member-profile-quick-copy">
                  <strong>{item.label}</strong>
                  <span>{item.description}</span>
                </span>
              </button>
            ))}
          </div>
        </article>
      ) : null}

      <article className="h5-card">
        <button className="seed-button seed-button-danger h5-member-profile-logout-button" onClick={onLogout} type="button">
          {actionName === "logout" ? t("profile.loggingOut") : t("profile.logout")}
        </button>
      </article>
    </section>
  );
}
