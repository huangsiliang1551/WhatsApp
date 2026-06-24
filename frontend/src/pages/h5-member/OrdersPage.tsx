import { type JSX, useMemo } from "react";
import { CustomerServiceOutlined, ProfileOutlined, ShoppingOutlined } from "@ant-design/icons";

import type { H5MemberOrder } from "../../services/h5Member";
import { formatMoney, formatTimestamp } from "./sharedUtils";
import { CompactListRow, EmptyStateCard, InfiniteScroll, PullToRefresh, QuickActionCard, SectionHeader } from "./sharedComponents";
import { t } from "./i18n";
import { ListSkeleton } from "./skeletons";

type OrderFilter = "all" | "paid" | "failed" | "processing";

type OrdersPageProps = {
  filteredOrders: H5MemberOrder[];
  orderFilter: OrderFilter;
  siteKey: string;
  onNavigate: (path: string) => void;
  onSetOrderFilter: (filter: OrderFilter) => void;
  ordersLoading: boolean;
  ordersError: string | null;
  ordersPage: number;
  ordersTotal: number;
  onOrderPageChange: (page: number) => void;
  onRetryOrders: () => void;
  loading?: boolean;
};

function getOrderStatusLabel(status: string): string {
  if (status === "paid") return t("orders.badgePaid");
  if (status === "failed") return t("orders.badgeFailed");
  if (status === "processing" || status === "pending") return t("orders.badgeProcessing");
  return status;
}

export function OrdersPage({
  filteredOrders,
  orderFilter,
  siteKey,
  onNavigate,
  onSetOrderFilter,
  ordersLoading,
  ordersError,
  ordersPage,
  ordersTotal,
  onOrderPageChange,
  onRetryOrders,
  loading = false,
}: OrdersPageProps): JSX.Element {
  if (loading) return <ListSkeleton count={4} />;
  const paidCount = useMemo(() => filteredOrders.filter((item) => item.status === "paid").length, [filteredOrders]);
  const failedCount = useMemo(() => filteredOrders.filter((item) => item.status === "failed").length, [filteredOrders]);
  const processingCount = useMemo(
    () => filteredOrders.filter((item) => item.status === "processing" || item.status === "pending").length,
    [filteredOrders],
  );
  const nextStepValue = failedCount > 0
    ? t('orders.overviewNextStepFailed')
    : processingCount > 0
      ? t('orders.overviewNextStepProcessing')
      : t('orders.overviewNextStepClear');

  return (
    <section className="h5-card-stack">
      <article className="h5-card h5-member-orders-overview-card">
        <SectionHeader meta={t('orders.overviewMeta')} title={t('orders.overviewTitle')} />
        <div className="h5-member-orders-overview-grid">
          <div className="h5-member-orders-overview-metric">
            <span>{t('orders.overviewPaidLabel')}</span>
            <strong>{paidCount}</strong>
          </div>
          <div className="h5-member-orders-overview-metric">
            <span>{t('orders.overviewProcessingLabel')}</span>
            <strong>{processingCount}</strong>
          </div>
          <div className="h5-member-orders-overview-metric">
            <span>{t('orders.overviewFailedLabel')}</span>
            <strong>{failedCount}</strong>
          </div>
          <div className="h5-member-orders-overview-metric">
            <span>{t('orders.overviewNextStepLabel')}</span>
            <strong>{nextStepValue}</strong>
          </div>
        </div>
        <div className="h5-member-quick-grid">
          <QuickActionCard
            title={t('orders.overviewTaskShortcutTitle')}
            body={t('orders.overviewTaskShortcutBody')}
            icon={<ProfileOutlined />}
            meta={t('orders.overviewTaskShortcutMeta')}
            onClick={() => onNavigate("/h5/tasks")}
          />
          <QuickActionCard
            title={t('orders.overviewSupportShortcutTitle')}
            body={t('orders.overviewSupportShortcutBody')}
            icon={<CustomerServiceOutlined />}
            meta={t('orders.overviewSupportShortcutMeta')}
            onClick={() => onNavigate("/h5/tickets/new")}
          />
        </div>
      </article>

      <article className="h5-card">
        <SectionHeader meta={t('orders.count', { count: filteredOrders.length })} title={t('orders.title')} />
        <p className="muted">{t('orders.desc')}</p>
      </article>
      <div className="h5-member-segmented h5-member-orders-filters">
        {[
          ["all", t('orders.filterAll')],
          ["paid", t('orders.filterPaid')],
          ["failed", t('orders.filterFailed')],
          ["processing", t('orders.filterProcessing')],
        ].map(([id, label]) => (
          <button
            className={`h5-member-segmented-chip ${orderFilter === id ? "h5-member-segmented-chip-active" : ""}`}
            key={id}
            onClick={() => onSetOrderFilter(id as OrderFilter)}
            type="button"
          >
            {label}
          </button>
        ))}
      </div>

      {ordersLoading ? (
        <article className="h5-card">
          <div className="h5-loading-indicator">{t('orders.loading')}</div>
        </article>
      ) : ordersError ? (
        <article className="h5-card">
          <div className="h5-error-indicator">
            <p>{ordersError}</p>
            <button className="seed-button seed-button-secondary" onClick={onRetryOrders} type="button">
              {t('orders.retry')}
            </button>
          </div>
        </article>
      ) : filteredOrders.length === 0 ? (
        <EmptyStateCard
          action={
            <button className="seed-button seed-button-secondary" onClick={() => onNavigate("/h5/tasks")} type="button">
              {t('orders.backToTasks')}
            </button>
          }
          description={t('orders.noOrdersDesc')}
          icon={<ShoppingOutlined />}
          title={t('orders.noOrders')}
        />
      ) : (
        <>
          <PullToRefresh onRefresh={async () => { onOrderPageChange(1); }}>
          {filteredOrders.map((item) => (
            <article className="h5-card" key={item.id}>
              <CompactListRow
                badge={getOrderStatusLabel(item.status)}
                meta={formatTimestamp(item.createdAt)}
                sideNote={item.orderNo}
                subtitle={`${item.packageTitle} · ${item.sourceLabel}`}
                title={item.productName}
                tone={item.status === "paid" ? "success" : item.status === "failed" ? "danger" : "default"}
                value={formatMoney(item.amount, item.currency)}
              />
            </article>
          ))}
          </PullToRefresh>
          <InfiniteScroll hasMore={ordersPage < Math.ceil(ordersTotal / 20)} loading={ordersLoading} onLoadMore={() => onOrderPageChange(ordersPage + 1)}>
          <div className="h5-member-pagination">
            {Array.from({ length: Math.max(1, Math.ceil(ordersTotal / 20)) }, (_, i) => i + 1).map((page) => (
              <button
                className={`seed-button ${page === ordersPage ? "seed-button-primary" : "seed-button-secondary"}`}
                key={page}
                onClick={() => onOrderPageChange(page)}
                type="button"
              >
                {page}
              </button>
            ))}
          </div>
          </InfiniteScroll>
        </>
      )}
    </section>
  );
}
