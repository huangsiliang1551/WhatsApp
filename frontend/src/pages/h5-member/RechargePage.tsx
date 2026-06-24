import { type JSX, type FormEvent, useMemo, useRef, useState } from "react";
import { WalletOutlined } from "@ant-design/icons";

import type { H5WalletSummary, H5WalletTransaction } from "../../services/h5Member";
import {
  formatMoney,
  formatTimestamp,
} from "./sharedUtils";
import { AmountPresetRow, CompactListRow, EmptyStateCard, SectionHeader } from "./sharedComponents";
import { t } from "./i18n";
import { DetailSkeleton } from "./skeletons";

function validateRechargeAmount(value: string): string {
  if (!value.trim()) return t("validation.required");
  const num = Number(value);
  if (isNaN(num) || num <= 0) return t("validation.positiveNumber");
  if (value.includes(".") && value.split(".")[1]?.length > 2) return t("validation.maxDecimals");
  if (num > 1000000) return t("validation.maxAmount", { max: formatMoney(1000000) });
  return "";
}

function getRechargeStatusLabel(status: string): string {
  switch (status) {
    case "paid":
    case "success":
      return t("recharge.statusPaid");
    case "processing":
      return t("recharge.statusProcessing");
    case "submitted":
    case "pending":
      return t("recharge.statusSubmitted");
    case "failed":
      return t("recharge.statusFailed");
    default:
      return status;
  }
}

type RechargePageProps = {
  effectiveWalletSummary: H5WalletSummary;
  rechargeAmount: string;
  rechargeHistory: H5WalletTransaction[];
  actionName: string | null;
  loading: boolean;
  error: string | null;
  rechargeStatus: string | null;
  onRechargeAmountChange: (value: string) => void;
  onNavigate: (path: string) => void;
  onOpenRechargeChannels: (event: FormEvent<HTMLFormElement>) => void;
};

export function RechargePage({
  effectiveWalletSummary,
  rechargeAmount,
  rechargeHistory,
  actionName,
  loading,
  error,
  rechargeStatus,
  onRechargeAmountChange,
  onNavigate,
  onOpenRechargeChannels,
}: RechargePageProps): JSX.Element {
  if (loading) return <DetailSkeleton />;

  const [amountError, setAmountError] = useState("");
  const actionCardRef = useRef<HTMLElement | null>(null);
  const isProcessing = actionName === "recharge";

  const flowMetrics = useMemo(() => {
    if (rechargeHistory.length === 0) {
      return {
        latestRechargeAt: null,
        todayFlowAmount: 0,
        weeklyFlowAmount: 0,
      };
    }

    const normalized = rechargeHistory
      .map((item) => ({
        ...item,
        createdAtMs: new Date(item.createdAt).getTime(),
      }))
      .filter((item) => Number.isFinite(item.createdAtMs) && item.status !== "failed");

    if (normalized.length === 0) {
      return {
        latestRechargeAt: null,
        todayFlowAmount: 0,
        weeklyFlowAmount: 0,
      };
    }

    const latest = normalized.reduce((max, item) => Math.max(max, item.createdAtMs), Number.NEGATIVE_INFINITY);
    const latestDate = new Date(latest);
    const latestDayKey = latestDate.toDateString();
    const windowStart = latest - 7 * 24 * 60 * 60 * 1000;

    return normalized.reduce(
      (acc, item) => {
        if (item.createdAtMs >= windowStart) {
          acc.weeklyFlowAmount += item.amount;
        }
        if (new Date(item.createdAtMs).toDateString() === latestDayKey) {
          acc.todayFlowAmount += item.amount;
        }
        return acc;
      },
      {
        latestRechargeAt: new Date(latest).toISOString(),
        todayFlowAmount: 0,
        weeklyFlowAmount: 0,
      },
    );
  }, [rechargeHistory]);
  const withdrawableNow = effectiveWalletSummary.canWithdraw ? effectiveWalletSummary.systemBalance : 0;
  const thresholdLabel = t("withdraw.threshold", {
    amount: formatMoney(effectiveWalletSummary.withdrawThreshold, effectiveWalletSummary.currency),
  });
  const readinessHint = effectiveWalletSummary.canWithdraw
    ? t("withdraw.canWithdrawHint")
    : t("withdraw.needTransferHint", {
        amount: formatMoney(effectiveWalletSummary.shortfallAmount, effectiveWalletSummary.currency),
      });

  function handleAmountChange(value: string): void {
    onRechargeAmountChange(value);
    if (value.trim() && !isNaN(Number(value)) && Number(value) > 0) {
      setAmountError("");
      return;
    }
    setAmountError(validateRechargeAmount(value));
  }

  function handleBlur(): void {
    if (rechargeAmount.trim()) {
      setAmountError(validateRechargeAmount(rechargeAmount));
    }
  }

  return (
    <section className="h5-card-stack">
      <article className="h5-card h5-member-wallet-balance-hero">
        <SectionHeader
          meta={t("recharge.snapshotMeta")}
          title={t("recharge.snapshotTitle")}
        />
        <p className="muted">{t("recharge.snapshotDesc")}</p>

        <section className="h5-member-wallet-balance-grid h5-member-earnings-summary-grid">
          <article className="h5-summary-card h5-member-wallet-balance-card h5-member-wallet-balance-card-system">
            <div className="h5-member-balance-card-main">
              <span className="h5-member-balance-card-label">{t("withdraw.systemBalance")}</span>
              <strong className="h5-member-balance-card-value">
                {formatMoney(effectiveWalletSummary.systemBalance, effectiveWalletSummary.currency)}
              </strong>
              <span className="h5-member-balance-card-note">{t("recharge.totalBalanceHint")}</span>
            </div>
          </article>

          <article className="h5-summary-card h5-member-wallet-balance-card h5-member-wallet-balance-card-system">
            <div className="h5-member-balance-card-main">
              <span className="h5-member-balance-card-label">{t("recharge.withdrawableNow")}</span>
              <strong className="h5-member-balance-card-value">
                {formatMoney(withdrawableNow, effectiveWalletSummary.currency)}
              </strong>
              <span className="h5-member-balance-card-note">
                {effectiveWalletSummary.canWithdraw ? t("withdraw.metThreshold") : t("recharge.notReadyToWithdraw")}
              </span>
            </div>
          </article>

          <article className="h5-summary-card h5-member-wallet-balance-card">
            <div className="h5-member-balance-card-main">
              <span className="h5-member-balance-card-label">{t("recharge.todayFlow")}</span>
              <strong className="h5-member-balance-card-value">
                {formatMoney(flowMetrics.todayFlowAmount, effectiveWalletSummary.currency)}
              </strong>
              <span className="h5-member-balance-card-note">{t("recharge.todayFlowHint")}</span>
            </div>
          </article>

          <article className="h5-summary-card h5-member-wallet-balance-card h5-member-wallet-balance-card-task">
            <div className="h5-member-balance-card-main">
              <span className="h5-member-balance-card-label">{t("recharge.recentFlow")}</span>
              <strong className="h5-member-balance-card-value">
                {formatMoney(flowMetrics.weeklyFlowAmount, effectiveWalletSummary.currency)}
              </strong>
              <span className="h5-member-balance-card-note">
                {flowMetrics.latestRechargeAt
                  ? t("recharge.lastActivity", { time: formatTimestamp(flowMetrics.latestRechargeAt) })
                  : t("recharge.history")}
              </span>
            </div>
          </article>
        </section>
      </article>

      <article className="h5-card h5-member-wallet-readiness-card">
        <SectionHeader meta={t("recharge.withdrawalReadinessMeta")} title={t("recharge.withdrawalReadiness")} />
        <div className="h5-member-wallet-threshold-bar">
          <strong>{effectiveWalletSummary.canWithdraw ? t("withdraw.metThreshold") : t("withdraw.needTransfer")}</strong>
          <span>{thresholdLabel}</span>
          <span>{readinessHint}</span>
        </div>

        <div className="h5-member-wallet-readiness-grid">
          <article className="h5-member-wallet-readiness-pill">
            <span>{t("withdraw.taskBalance")}</span>
            <strong>{formatMoney(effectiveWalletSummary.taskBalance, effectiveWalletSummary.currency)}</strong>
            <small>{t("recharge.taskBalanceHint")}</small>
          </article>

          <article className="h5-member-wallet-readiness-pill">
            <span>{t("recharge.nextAction")}</span>
            <strong>{effectiveWalletSummary.canWithdraw ? t("recharge.quickWithdraw") : t("recharge.quickRecharge")}</strong>
            <small>{t("recharge.recentFlowHint")}</small>
          </article>
        </div>

        <div className="h5-member-wallet-hero-actions">
          <button
            className="seed-button seed-button-secondary"
            onClick={() => actionCardRef.current?.scrollIntoView({ behavior: "smooth", block: "start" })}
            type="button"
          >
            {t("recharge.quickRecharge")}
          </button>
          <button className="seed-button seed-button-secondary" onClick={() => onNavigate("/h5/withdraw")} type="button">
            {t("recharge.quickWithdraw")}
          </button>
        </div>
      </article>

      <article className="h5-card h5-member-wallet-action-card h5-member-wallet-action-card-priority" ref={actionCardRef}>
        <SectionHeader title={t("recharge.amount")} />

        {error ? <div className="h5-form-error-banner">{error}</div> : null}

        {rechargeStatus ? (
          <div className="h5-member-recharge-status">
            <span className="h5-spinner" />
            <span>{t("recharge.statusPolling", { status: rechargeStatus })}</span>
          </div>
        ) : null}

        <form className="h5-form" onSubmit={onOpenRechargeChannels}>
          <div className="h5-member-wallet-action-head">
            <strong>{t("recharge.confirm")}</strong>
            <span>{t("recharge.channelHint")}</span>
          </div>

          <label>
            {t("recharge.amount")}
            <input
              className={amountError ? "h5-field-input-error" : ""}
              disabled={isProcessing}
              inputMode="decimal"
              onBlur={handleBlur}
              onChange={(event) => handleAmountChange(event.target.value)}
              value={rechargeAmount}
            />
            {amountError ? <span className="h5-field-error">{amountError}</span> : null}
          </label>

          <AmountPresetRow currentValue={rechargeAmount} onSelect={onRechargeAmountChange} values={[100, 300, 500, 1000]} />

          <div className="h5-member-inline-actions">
            <button className="h5-primary-button" disabled={isProcessing || !!amountError} type="submit">
              {isProcessing ? (
                <><span className="h5-spinner h5-spinner-inline" /> {t("recharge.processing")}</>
              ) : (
                t("recharge.confirm")
              )}
            </button>
          </div>
        </form>
      </article>

      <article className="h5-card">
        <SectionHeader meta={t("orders.count", { count: rechargeHistory.length })} title={t("recharge.history")} />
        <div className="h5-card-stack h5-member-wallet-history-list">
          {rechargeHistory.length > 0 ? (
            rechargeHistory.map((item) => (
              <CompactListRow
                key={item.id}
                meta={formatMoney(item.amount, item.currency)}
                sideNote={formatTimestamp(item.createdAt)}
                title={item.note || t("recharge.historyDefaultNote")}
                tone={item.status === "failed" ? "danger" : item.status === "processing" ? "default" : "success"}
                value={getRechargeStatusLabel(item.status)}
              />
            ))
          ) : (
            <EmptyStateCard
              description={t("recharge.noHistoryDesc")}
              icon={<WalletOutlined />}
              title={t("recharge.noHistory")}
            />
          )}
        </div>
      </article>
    </section>
  );
}
