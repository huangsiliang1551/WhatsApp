import { type JSX } from "react";
import { LinkOutlined } from "@ant-design/icons";

import type { H5HomeDashboard } from "../../services/h5Member";
import {
  buildPromotionInvitees, buildPromotionLink, formatTimestamp,
  type PromotionInvitee,
} from "./sharedUtils";
import {
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

  return (
    <section className="h5-card-stack">
      <article className="h5-card h5-member-promotion-hero">
        <SectionHeader meta={t('promotion.exclusiveLink')} title={t('promotion.title')} />
        <p className="muted">{t('promotion.desc')}</p>
        <div className="h5-member-promotion-link-box">
          <span>{promotionLink}</span>
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
        </div>
        <div className="h5-member-promotion-code-row">
          <span className="h5-member-inline-pill">{t('promotion.linkGenerated')}</span>
          <span className="h5-member-inline-pill">{t('promotion.account', { masked: dashboard.member.accountIdMasked })}</span>
        </div>
      </article>

      <article className="h5-card">
        <SectionHeader meta={t('promotion.overview')} title={t('promotion.data')} />
        <DetailGrid
          items={[
            { label: t('promotion.inviteeCount'), value: String(promotionInvitees.length) },
            { label: t('promotion.rechargeCount'), value: String(promotionRechargeCount) },
            { label: t('promotion.noRechargeCount'), value: String(Math.max(0, promotionInvitees.length - promotionRechargeCount)) },
            { label: t('promotion.promoTask'), value: t('promotion.promoTaskValue') },
          ]}
        />
      </article>

      <article className="h5-card">
        <SectionHeader meta={t('promotion.rulesMeta')} title={t('promotion.rulesTitle')} />
        <DetailGrid
          items={[
            { label: t('promotion.rewardBalance'), value: t('promotion.rewardBalanceValue') },
            { label: t('promotion.validityWindow'), value: t('promotion.validityWindowValue') },
            { label: t('promotion.delayNotice'), value: t('promotion.delayNoticeValue') },
          ]}
        />
      </article>

      <article className="h5-card h5-member-promotion-list-card">
        <SectionHeader meta={`${promotionInvitees.length} ${t('common.person')}`} title={t('promotion.inviteeList')} />
        <div className="h5-member-promotion-table" role="table" aria-label={t('promotion.inviteeList')}>
          <div className="h5-member-promotion-table-row h5-member-promotion-table-head" role="row">
            <span role="columnheader">{t('promotion.colSequence')}</span>
            <span role="columnheader">{t('promotion.colUserId')}</span>
            <span role="columnheader">{t('promotion.colRegisteredAt')}</span>
            <span role="columnheader">{t('promotion.colHasRecharged')}</span>
          </div>
          {promotionInvitees.length > 0 ? (
            promotionInvitees.map((item: PromotionInvitee) => (
              <div className="h5-member-promotion-table-row" key={`${item.sequence}-${item.userIdMasked}`} role="row">
                <span className="h5-member-promotion-cell" data-label={t('promotion.colSequence')} role="cell">
                  {item.sequence}
                </span>
                <strong className="h5-member-promotion-cell" data-label={t('promotion.colUserId')} role="cell">
                  {item.userIdMasked}
                </strong>
                <span className="h5-member-promotion-cell" data-label={t('promotion.colRegisteredAt')} role="cell">
                  {formatTimestamp(item.registeredAt)}
                </span>
                <span
                  className={`h5-member-promotion-cell ${item.hasRecharged ? "h5-member-promotion-status-paid" : "h5-member-promotion-status-pending"}`}
                  data-label={t('promotion.colHasRecharged')}
                  role="cell"
                >
                  {item.hasRecharged ? t('promotion.hasRecharged') : t('promotion.notRecharged')}
                </span>
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
