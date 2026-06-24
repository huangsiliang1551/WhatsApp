import { type JSX } from "react";
import { LinkOutlined } from "@ant-design/icons";

import type { H5HomeDashboard } from "../../services/h5Member";
import {
  buildPromotionInvitees, buildPromotionLink, formatTimestamp,
  type PromotionInvitee,
} from "./sharedUtils";
import {
  CompactListRow,
  DetailGrid,
  EmptyStateCard,
  SectionHeader,
} from "./sharedComponents";
import { t } from "./i18n";
import { ProfileSkeleton } from "./skeletons";

type PromotionPageProps = {
  dashboard: H5HomeDashboard;
  siteKey: string;
  onNavigate: (path: string) => void;
  onCopyText: (value: string, successMessage: string, failureMessage: string) => Promise<void>;
  loading: boolean;
  error: string | null;
};

export function PromotionPage({
  dashboard,
  siteKey,
  onNavigate,
  onCopyText,
  loading,
  error,
}: PromotionPageProps): JSX.Element {
  if (loading) {
    return <ProfileSkeleton />;
  }

  if (error) {
    return (
      <section className="h5-card-stack">
        <article className="h5-card h5-member-promotion-hero">
          <SectionHeader meta={t('promotion.exclusiveLink')} title={t('promotion.title')} />
          <p className="muted">{t('promotion.desc')}</p>
        </article>
        <EmptyStateCard
          description={error}
          icon={<LinkOutlined />}
          title={t('common.error')}
        />
      </section>
    );
  }

  const promotionLink = buildPromotionLink(siteKey, dashboard.member.inviteCode);
  const promotionInvitees = buildPromotionInvitees(dashboard.member.inviteCode);
  const promotionRechargeCount = promotionInvitees.filter((item) => item.hasRecharged).length;
  const promotionPendingCount = Math.max(0, promotionInvitees.length - promotionRechargeCount);
  const qualifiedRate =
    promotionInvitees.length > 0
      ? `${Math.round((promotionRechargeCount / promotionInvitees.length) * 100)}%`
      : "0%";

  return (
    <section className="h5-card-stack">
      <article className="h5-card h5-member-promotion-program-card">
        <SectionHeader meta={t('promotion.programMeta')} title={t('promotion.programTitle')} />
        <div className="h5-member-promotion-hero">
          <span aria-hidden="true" className="h5-member-promotion-hero-icon">
            <LinkOutlined />
          </span>
          <div className="h5-member-promotion-copy">
            <strong>{t('promotion.title')}</strong>
            <p>{t('promotion.programDesc')}</p>
          </div>
        </div>
        <div className="h5-member-promotion-code-row">
          <span className="h5-member-inline-pill">{t('promotion.linkGenerated')}</span>
          <span className="h5-member-inline-pill">{t('promotion.account', { masked: dashboard.member.accountIdMasked })}</span>
        </div>
        <DetailGrid
          items={[
            { label: t('promotion.inviteeCount'), value: String(promotionInvitees.length) },
            { label: t('promotion.rechargeCount'), value: String(promotionRechargeCount) },
            { label: t('promotion.qualifiedRate'), value: qualifiedRate },
            { label: t('promotion.promoTask'), value: t('promotion.promoTaskValue') },
          ]}
        />
      </article>

      <article className="h5-card">
        <SectionHeader meta={t('promotion.actionsMeta')} title={t('promotion.actionsTitle')} />
        <div className="h5-member-promotion-link-box">
          <span>{promotionLink}</span>
        </div>
        <div className="h5-member-card-actions">
          <button
            className="seed-button"
            onClick={() =>
              void onCopyText(
                promotionLink,
                t('promotion.copySuccess'),
                t('promotion.copyFailed'),
              )
            }
            type="button"
          >
            {t('promotion.copyLink')}
          </button>
          <button className="seed-button seed-button-secondary" onClick={() => onNavigate("/h5/invite")} type="button">
            {t('promotion.openInviteCenter')}
          </button>
        </div>
        <div className="h5-member-promotion-actions-foot">
          <span className="h5-member-inline-pill">{t('promotion.qualifiedRate')}: {qualifiedRate}</span>
          <span className="h5-member-inline-pill">{t('promotion.noRechargeCount')}: {promotionPendingCount}</span>
        </div>
      </article>

      <article className="h5-card">
        <SectionHeader meta={t('promotion.rulesMeta')} title={t('promotion.rulesTitle')} />
        <div className="h5-card-stack">
          <CompactListRow
            sideNote={t('promotion.rewardFlowTitle')}
            subtitle={t('promotion.rewardBalanceValue')}
            title={t('promotion.rewardBalance')}
            tone="success"
          />
          <CompactListRow
            sideNote={t('promotion.validityTitle')}
            subtitle={t('promotion.validityWindowValue')}
            title={t('promotion.validityWindow')}
            tone="active"
          />
          <CompactListRow
            sideNote={t('promotion.followupTitle')}
            subtitle={t('promotion.delayNoticeValue')}
            title={t('promotion.delayNotice')}
          />
        </div>
      </article>

      <article className="h5-card h5-member-promotion-list-card">
        <SectionHeader
          meta={t('promotion.inviteeListMeta', { count: promotionInvitees.length })}
          title={t('promotion.inviteeList')}
        />
        <div className="h5-card-stack h5-member-promotion-record-list">
          {promotionInvitees.length > 0 ? (
            promotionInvitees.map((item: PromotionInvitee) => (
              <div className="h5-member-promotion-record-row" key={`${item.sequence}-${item.userIdMasked}`}>
                <CompactListRow
                  badge={item.hasRecharged ? t('promotion.hasRecharged') : t('promotion.notRecharged')}
                  sideNote={
                    t('promotion.inviteeSequence', { sequence: item.sequence })
                  }
                  actionLabel={item.hasRecharged ? t('promotion.rewardFlowTitle') : t('promotion.followupTitle')}
                  subtitle={t('promotion.inviteeRegistered', { time: formatTimestamp(item.registeredAt) })}
                  title={item.userIdMasked}
                  tone={item.hasRecharged ? "success" : "default"}
                />
              </div>
            ))
          ) : (
            <div className="h5-card-stack">
              <EmptyStateCard
                description={t('promotion.noInviteesDesc')}
                icon={<LinkOutlined />}
                title={t('promotion.noInvitees')}
              />
            </div>
          )}
        </div>
      </article>
    </section>
  );
}
