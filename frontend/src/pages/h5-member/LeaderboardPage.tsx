import { type JSX } from "react";
import { TrophyOutlined } from "@ant-design/icons";

import type { H5LeaderboardEntry } from "../../services/h5Member";
import { formatMoney } from "./sharedUtils";
import { CompactListRow, DetailGrid, EmptyStateCard, SectionHeader } from "./sharedComponents";
import { t } from "./i18n";
import { ListSkeleton } from "./skeletons";

type LeaderboardPageProps = {
  leaderboard: H5LeaderboardEntry[];
  loading: boolean;
  error: string | null;
};

export function LeaderboardPage({ leaderboard, loading, error }: LeaderboardPageProps): JSX.Element {
  const topPerformer = leaderboard[0] ?? null;
  const runnerUp = leaderboard[1] ?? null;
  const spreadValue =
    topPerformer && runnerUp
      ? formatMoney(topPerformer.amount - runnerUp.amount, topPerformer.currency)
      : topPerformer
        ? formatMoney(topPerformer.amount, topPerformer.currency)
        : "--";

  if (loading) {
    return <ListSkeleton count={5} />;
  }

  if (error) {
    return (
      <section className="h5-card-stack">
        <article className="h5-card">
          <SectionHeader meta={t('leaderboard.meta', { count: 0 })} title={t('leaderboard.title')} />
          <p className="muted">{t('leaderboard.desc')}</p>
        </article>
        <section className="h5-card h5-member-leaderboard-list">
          <EmptyStateCard
            description={error}
            icon={<TrophyOutlined />}
            title={t('common.error')}
          />
        </section>
      </section>
    );
  }

  return (
    <section className="h5-card-stack">
      {topPerformer ? (
        <article className="h5-card h5-member-leaderboard-overview-card">
          <SectionHeader meta={t('leaderboard.overviewMeta')} title={t('leaderboard.overviewTitle')} />
          <DetailGrid
            items={[
              { label: t('leaderboard.overviewLeaderLabel'), value: topPerformer.accountIdMasked },
              { label: t('leaderboard.overviewRunnerUpLabel'), value: runnerUp?.accountIdMasked ?? "--" },
              { label: t('leaderboard.overviewSpreadLabel'), value: spreadValue },
              { label: t('leaderboard.overviewPrivacyLabel'), value: t('leaderboard.maskedAccountsOnly') },
            ]}
          />
        </article>
      ) : null}

      {topPerformer ? (
        <article className="h5-card h5-member-leaderboard-hero">
          <SectionHeader meta={t('leaderboard.maskedAccountsOnly')} title={t('leaderboard.topPerformer')} />
          <CompactListRow
            badge={t('leaderboard.rank', { rank: topPerformer.rank })}
            meta={t('leaderboard.topPerformerDesc')}
            title={topPerformer.accountIdMasked}
            tone="active"
            value={formatMoney(topPerformer.amount, topPerformer.currency)}
          />
        </article>
      ) : null}
      <article className="h5-card">
        <SectionHeader meta={t('leaderboard.meta', { count: leaderboard.length })} title={t('leaderboard.title')} />
        <p className="muted">{t('leaderboard.desc')}</p>
      </article>
      <section className="h5-card h5-member-leaderboard-list">
        <div className="h5-card-stack">
          {leaderboard.length > 0 ? (
            leaderboard.map((item) => (
              <CompactListRow
                key={`${item.rank}-${item.accountIdMasked}`}
                meta={t('leaderboard.rank', { rank: item.rank })}
                title={item.accountIdMasked}
                tone="active"
                value={formatMoney(item.amount, item.currency)}
              />
            ))
          ) : (
            <EmptyStateCard
              description={t('leaderboard.noDataDesc')}
              icon={<TrophyOutlined />}
              title={t('leaderboard.noData')}
            />
          )}
        </div>
      </section>
    </section>
  );
}
