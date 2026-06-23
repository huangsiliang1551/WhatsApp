import { type JSX } from "react";
import { GiftOutlined, LinkOutlined, UserOutlined, WhatsAppOutlined } from "@ant-design/icons";

import type { H5InviteInfo, H5InviteRecord } from "../../services/h5Member";
import { formatMoney, formatTimestamp } from "./sharedUtils";
import { EmptyStateCard, SectionHeader } from "./sharedComponents";
import { t } from "./i18n";
import { DetailSkeleton } from "./skeletons";

type InvitePageProps = {
  inviteInfo: H5InviteInfo;
  inviteRecords: H5InviteRecord[];
  loading: boolean;
  error: string | null;
  onCopyText: (value: string, successMessage: string, failureMessage: string) => Promise<void>;
  onRetry: () => Promise<void>;
};

export function InvitePage({
  inviteInfo,
  inviteRecords,
  loading,
  error,
  onCopyText,
  onRetry,
}: InvitePageProps): JSX.Element {
  function handleWhatsAppShare(): void {
    const shareUrl = `https://wa.me/?text=${encodeURIComponent(`${t("tasks.inviteShareText")}\n${inviteInfo.inviteLink}`)}`;
    window.open(shareUrl, "_blank", "noopener,noreferrer");
  }

  function handleCopyLink(): void {
    void onCopyText(
      inviteInfo.inviteLink,
      t("notification.copySuccess", { value: t("tasks.inviteMyLink") }),
      t("notification.copyFailed"),
    );
  }

  if (loading) {
    return <DetailSkeleton />;
  }

  if (error) {
    return (
      <section className="h5-card-stack">
        <article className="h5-card">
          <p className="error-text">{error}</p>
          <button className="seed-button" onClick={() => void onRetry()} type="button">
            {t("common.retry")}
          </button>
        </article>
      </section>
    );
  }

  return (
    <section className="h5-card-stack">
      <article className="h5-card h5-invite-hero">
        <div className="h5-invite-hero-icon">
          <GiftOutlined />
        </div>
        <h2>{t("tasks.inviteTitle")}</h2>
        <p>{t("tasks.inviteReward1", { amount: formatMoney(2) })}</p>
        <p>{t("tasks.inviteReward2", { threshold: formatMoney(30), amount: formatMoney(3) })}</p>
      </article>

      <article className="h5-card">
        <SectionHeader title={t("tasks.inviteMyLink")} />
        <div className="h5-invite-link-box">
          <span>{inviteInfo.inviteLink}</span>
          <button className="seed-button seed-button-secondary" onClick={handleCopyLink} type="button">
            <LinkOutlined /> {t("tasks.inviteCopyLink")}
          </button>
        </div>
        <div className="h5-invite-actions">
          <button className="seed-button" onClick={handleWhatsAppShare} type="button">
            <WhatsAppOutlined /> {t("tasks.inviteWhatsAppShare")}
          </button>
        </div>
      </article>

      <article className="h5-card">
        <SectionHeader title={t("tasks.inviteStatsTitle")} />
        <div className="h5-invite-stats-grid">
          <div className="h5-invite-stat-card">
            <strong>{inviteInfo.invitedCount}</strong>
            <span>{t("tasks.inviteStatsInvitedLabel")}</span>
          </div>
          <div className="h5-invite-stat-card">
            <strong>{formatMoney(inviteInfo.earnedAmount)}</strong>
            <span>{t("tasks.inviteStatsEarnedLabel")}</span>
          </div>
          <div className="h5-invite-stat-card">
            <strong>{inviteInfo.remainingInvites}</strong>
            <span>{t("tasks.inviteStatsRemainingLabel")}</span>
          </div>
        </div>
      </article>

      <article className="h5-card">
        <SectionHeader meta={`${inviteRecords.length} ${t("common.records")}`} title={t("tasks.inviteRecords")} />
        <div className="h5-card-stack">
          {inviteRecords.length > 0 ? (
            inviteRecords.map((record) => (
              <div className="h5-invite-record-item" key={record.id}>
                <span aria-hidden="true" className="h5-invite-record-icon">
                  <UserOutlined />
                </span>
                <div className="h5-invite-record-info">
                  <strong>{record.userIdMasked}</strong>
                  <span>
                    {record.type === "registration" ? t("tasks.inviteRegistered") : t("tasks.inviteRecharged")}
                    {" · "}
                    {formatTimestamp(record.createdAt)}
                  </span>
                </div>
                <span className="h5-invite-record-reward">
                  {t("tasks.inviteEarned", { amount: record.rewardAmount.toFixed(2) })}
                </span>
              </div>
            ))
          ) : (
            <EmptyStateCard
              description={t("tasks.inviteNoRecordsDesc")}
              icon={<GiftOutlined />}
              title={t("tasks.inviteNoRecords")}
            />
          )}
        </div>
      </article>
    </section>
  );
}
