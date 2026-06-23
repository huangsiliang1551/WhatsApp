import { type JSX, type FormEvent } from "react";
import { GiftOutlined } from "@ant-design/icons";

import type { H5FragmentOverview, H5ShippingAddress } from "../../services/h5Member";
import {
  formatTimestamp,
  getShippingStatusLabel, ShippingFormState,
} from "./sharedUtils";
import { CompactListRow, EmptyStateCard, SectionHeader } from "./sharedComponents";
import { t } from "./i18n";
import { DetailSkeleton } from "./skeletons";

type FragmentsPageProps = {
  fragmentOverview: H5FragmentOverview;
  fragmentCompletion: { completed: number; total: number; missing: number; progress: number };
  canExchangeFragments: boolean;
  latestShippingOrder: H5FragmentOverview["shippingOrders"][number] | null;
  fragmentStageTitle: string;
  fragmentStageDescription: string;
  shippingForm: ShippingFormState;
  actionName: string | null;
  fragmentsLoading: boolean;
  fragmentsError: string | null;
  onCheckIn: () => Promise<void>;
  onExchange: (event: FormEvent<HTMLFormElement>) => Promise<void>;
  onShippingFormChange: (field: keyof ShippingFormState, value: string) => void;
  onRetry: () => Promise<void>;
  loading?: boolean;
};

export function FragmentsPage({
  fragmentOverview,
  fragmentCompletion,
  canExchangeFragments,
  latestShippingOrder,
  fragmentStageTitle,
  fragmentStageDescription,
  shippingForm,
  actionName,
  fragmentsLoading,
  fragmentsError,
  onCheckIn,
  onExchange,
  onShippingFormChange,
  onRetry,
}: FragmentsPageProps): JSX.Element {
  if (fragmentsLoading) {
    return <DetailSkeleton />;
  }

  if (fragmentsError) {
    return (
      <section className="h5-card-stack">
        <article className="h5-card">
          <p className="error-text">{fragmentsError}</p>
          <button className="seed-button" onClick={() => void onRetry()} type="button">
            {t("common.retry")}
          </button>
        </article>
      </section>
    );
  }

  return (
    <section className="h5-card-stack">
      <article className="h5-card h5-member-fragment-hero">
        <SectionHeader
          action={
            <button className="seed-button seed-button-secondary" onClick={() => void onCheckIn()} type="button">
              {actionName === "checkin" ? t('fragments.checkingIn') : t('fragments.checkin')}
            </button>
          }
          title={t('fragments.title')}
        />
        <div className="h5-member-fragment-progress">
          <div className="h5-member-task-summary">
            <strong>{t('fragments.completed', { done: fragmentCompletion.completed, total: fragmentCompletion.total })}</strong>
            <span>{fragmentCompletion.missing > 0 ? t('fragments.missing', { count: fragmentCompletion.missing }) : t('fragments.canExchange')}</span>
          </div>
          <div className="h5-member-progress">
            <div className="h5-member-progress-fill" style={{ width: `${fragmentCompletion.progress}%` }} />
          </div>
        </div>
        <div className="h5-member-fragment-steps">
          {[t('fragments.stepCheckin'), t('fragments.stepTasks'), t('fragments.stepCollect'), t('fragments.stepAddress'), t('fragments.stepShipping')].map((label, index) => (
            <span
              className={`h5-member-fragment-step ${index < 2 || (index === 2 && canExchangeFragments) || (index > 2 && fragmentOverview.shippingOrders.length > 0) ? "h5-member-fragment-step-active" : ""}`}
              key={label}
            >
              {label}
            </span>
          ))}
        </div>
        <div className="h5-member-fragment-grid">
          {fragmentOverview.inventory.map((item) => (
            <article className="h5-member-fragment-card h5-member-fragment-inventory-card" key={item.id}>
              <strong>{item.name}</strong>
              <span>{`${item.owned}/${item.required}`}</span>
              <small>{item.rarity}</small>
            </article>
          ))}
        </div>
      </article>

      <article className="h5-card">
        <SectionHeader title={fragmentStageTitle} />
        <p className="muted">{fragmentStageDescription}</p>
        <form className="h5-form" onSubmit={(event) => void onExchange(event)}>
          <label>
            {t('fragments.receiver')}
            <input value={shippingForm.receiver} onChange={(event) => onShippingFormChange("receiver", event.target.value)} />
          </label>
          <label>
            {t('fragments.phone')}
            <input value={shippingForm.phone} onChange={(event) => onShippingFormChange("phone", event.target.value)} />
          </label>
          <label>
            {t('fragments.province')}
            <input value={shippingForm.province} onChange={(event) => onShippingFormChange("province", event.target.value)} />
          </label>
          <label>
            {t('fragments.city')}
            <input value={shippingForm.city} onChange={(event) => onShippingFormChange("city", event.target.value)} />
          </label>
          <label>
            {t('fragments.address')}
            <textarea rows={4} value={shippingForm.addressLine} onChange={(event) => onShippingFormChange("addressLine", event.target.value)} />
          </label>
          <button className="seed-button" disabled={!canExchangeFragments || actionName === "fragment-exchange"} type="submit">
            {actionName === "fragment-exchange" ? t('fragments.submitting') : canExchangeFragments ? t('fragments.exchangeSubmit') : t('fragments.notCollected')}
          </button>
        </form>
      </article>

      <article className="h5-card">
        <SectionHeader meta={t('orders.count', { count: fragmentOverview.dropLogs.length })} title={t('fragments.dropLogs')} />
        <div className="h5-card-stack">
          {fragmentOverview.dropLogs.length > 0 ? (
            fragmentOverview.dropLogs.map((item) => (
              <CompactListRow
                key={item.id}
                meta={formatTimestamp(item.createdAt)}
                sideNote={item.source === "checkin" ? t('fragments.fromCheckin') : t('fragments.fromTask')}
                title={item.fragmentName}
              />
            ))
          ) : (
            <EmptyStateCard
              description={t('fragments.noDropsDesc')}
              icon={<GiftOutlined />}
              title={t('fragments.noDrops')}
            />
          )}
        </div>
      </article>

      <article className="h5-card">
        <SectionHeader meta={t('orders.count', { count: fragmentOverview.shippingOrders.length })} title={t('fragments.shippingStatus')} />
        <div className="h5-card-stack h5-member-fragment-shipping-list">
          {fragmentOverview.shippingOrders.length > 0 ? (
            fragmentOverview.shippingOrders.map((item) => (
              <CompactListRow
                key={item.id}
                badge={getShippingStatusLabel(item.status)}
                meta={formatTimestamp(item.createdAt)}
                title={item.rewardName}
                tone={item.status === "completed" || item.status === "delivered" ? "success" : "active"}
                value={item.address ? item.address.city : t('fragments.pendingAddress')}
              />
            ))
          ) : (
            <EmptyStateCard
              description={t('fragments.noShippingDesc')}
              icon={<GiftOutlined />}
              title={t('fragments.noShipping')}
            />
          )}
        </div>
      </article>
    </section>
  );
}
