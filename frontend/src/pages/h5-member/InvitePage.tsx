import { type JSX } from "react";
import { GiftOutlined, LinkOutlined, UserOutlined, WhatsAppOutlined } from "@ant-design/icons";

import type { H5InviteInfo, H5InviteRecord } from "../../services/h5Member";
import { formatMoney, formatTimestamp } from "./sharedUtils";
import { CompactListRow, DetailGrid, EmptyStateCard, SectionHeader } from "./sharedComponents";
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
  const inviteProgressValue = `${inviteInfo.invitedCount}/${inviteInfo.maxInvites}`;

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
      <article className="h5-card h5-invite-program-card">
        <SectionHeader meta={t("tasks.inviteProgramMeta")} title={t("tasks.inviteProgramTitle")} />

        <div className="h5-invite-program-hero">
          <div className="h5-invite-hero-icon">
            <GiftOutlined />
          </div>
          <div className="h5-invite-program-copy">
            <strong>{t("tasks.inviteTitle")}</strong>
            <p>{t("tasks.inviteProgramDesc")}</p>
          </div>
        </div>

        <div className="h5-member-task-chip-row">
          <span className="h5-member-inline-pill">{t("tasks.inviteReward1", { amount: formatMoney(2) })}</span>
          <span className="h5-member-inline-pill">{t("tasks.inviteReward2", { threshold: formatMoney(30), amount: formatMoney(3) })}</span>
        </div>

        <DetailGrid
          items={[
            { label: t("tasks.inviteStatsInvitedLabel"), value: String(inviteInfo.invitedCount) },
            { label: t("tasks.inviteStatsEarnedLabel"), value: formatMoney(inviteInfo.earnedAmount) },
            { label: t("tasks.inviteProgress"), value: inviteProgressValue },
            { label: t("tasks.inviteCapacity"), value: String(inviteInfo.maxInvites) },
          ]}
        />
      </article>

      <article className="h5-card h5-invite-action-card">
        <SectionHeader meta={t("tasks.inviteActionsMeta")} title={t("tasks.inviteMyLink")} />
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
        <div className="h5-invite-action-foot">
          <span className="h5-member-inline-pill">
            {t("tasks.inviteStatsRemainingLabel")}: {inviteInfo.remainingInvites}
          </span>
          <span className="h5-member-inline-pill">
            {t("tasks.inviteProgress")}: {inviteProgressValue}
          </span>
        </div>
      </article>

      <article className="h5-card">
        <SectionHeader meta={t("tasks.inviteRulesMeta")} title={t("tasks.inviteRulesTitle")} />
        <div className="h5-card-stack">
          <CompactListRow
            meta={t("tasks.inviteRuleRegistrationMeta")}
            title={t("tasks.inviteRuleRegistrationTitle")}
            tone="success"
            value={t("tasks.inviteEarned", { amount: formatMoney(2) })}
          />
          <CompactListRow
            meta={t("tasks.inviteRuleRechargeMeta", { threshold: formatMoney(30) })}
            title={t("tasks.inviteRuleRechargeTitle")}
            tone="active"
            value={t("tasks.inviteEarned", { amount: formatMoney(3) })}
          />
        </div>
      </article>

      <article className="h5-card">
        <SectionHeader meta={`${inviteRecords.length} ${t("common.records")}`} title={t("tasks.inviteRecords")} />
        <div className="h5-card-stack">
          {inviteRecords.length > 0 ? (
            inviteRecords.map((record: H5InviteRecord) => (
              <div className="h5-invite-record-row" key={record.id}>
                <span aria-hidden="true" className="h5-invite-record-icon">
                  <UserOutlined />
                </span>
                <CompactListRow
                  badge={record.type === "registration" ? t("tasks.inviteRecordRegistered") : t("tasks.inviteRecordRecharged")}
                  meta={formatTimestamp(record.createdAt)}
                  title={record.userIdMasked}
                  tone={record.type === "registration" ? "success" : "active"}
                  value={t("tasks.inviteEarned", { amount: formatMoney(record.rewardAmount) })}
                />
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
