import type { JSX } from "react";
import {
  CheckCircleOutlined,
  FireOutlined,
  UserOutlined,
} from "@ant-design/icons";

import type { H5HomeDashboard, H5SignInStatus, H5WhatsAppBinding } from "../../services/h5Member";
import {
  formatMoney,
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
      key: "messages",
      title: t("messages.title"),
      meta: t("home.systemReminders"),
      sideNote: t("home.unread", { count: dashboard.unreadCount }),
      path: "/h5/messages",
      tone: dashboard.unreadCount > 0 ? "active" : "default",
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
        <SectionHeader meta={t("profile.accountCenter")} title={t("profile.title")} />

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

        <div className="h5-member-profile-balance-strip">
          <article className="h5-member-profile-balance-card">
            <div className="h5-member-balance-card-main">
              <span className="h5-member-balance-card-label">{t("profile.systemBalance")}</span>
              <strong className="h5-member-balance-card-value">{formatMoney(dashboard.wallet.systemBalance)}</strong>
            </div>
            <div className="h5-member-balance-card-actions">
              <button className="seed-button seed-button-secondary h5-member-balance-pill-button" onClick={() => onNavigate("/h5/recharge")} type="button">
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
        <SectionHeader meta={t("profile.quickActions")} title={t("profile.accountCenter")} />
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

      <article className="h5-card h5-member-profile-quick-actions">
        <SectionHeader meta={t("profile.quickActions")} title={t("profile.commonEntries")} />
        <div className="h5-member-profile-quick-grid">
          {profileQuickActions.map((item) => (
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

      <article className="h5-card">
        <button className="seed-button seed-button-danger h5-member-profile-logout-button" onClick={onLogout} type="button">
          {actionName === "logout" ? t("profile.loggingOut") : t("profile.logout")}
        </button>
      </article>
    </section>
  );
}
