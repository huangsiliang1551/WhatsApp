import { type JSX, type FormEvent, useState } from "react";
import {
  CheckCircleFilled,
  ClockCircleFilled,
  CloseCircleFilled,
  ExclamationCircleFilled,
  WalletOutlined,
} from "@ant-design/icons";

import type { H5WalletSummary, H5WithdrawRequest } from "../../services/h5Member";
import {
  formatMoney,
  formatTimestamp,
  getWithdrawStatusLabel,
} from "./sharedUtils";
import { CompactListRow, EmptyStateCard, SectionHeader } from "./sharedComponents";
import { t } from "./i18n";
import { DetailSkeleton } from "./skeletons";

const MIN_WITHDRAW = 10;
const WITHDRAW_FEE_RATE = 0.01;

function validateWithdrawAmount(value: string, max: number): string {
  if (!value.trim()) return t("validation.required");
  const num = Number(value);
  if (Number.isNaN(num) || num <= 0) return t("validation.positiveNumber");
  if (num < MIN_WITHDRAW) return t("validation.minAmount", { min: formatMoney(MIN_WITHDRAW) });
  if (num > max) return t("validation.maxAmount", { max: formatMoney(max) });
  return "";
}

function WithdrawStatusFlow({ status }: { status: H5WithdrawRequest["status"] }): JSX.Element {
  const steps: Array<{ key: string; icon: typeof ClockCircleFilled; label: string }> = [
    { key: "submitted", icon: ClockCircleFilled, label: t("withdraw.statusSubmitted") },
    { key: "reviewing", icon: ExclamationCircleFilled, label: t("withdraw.statusReviewing") },
    { key: "approved", icon: CheckCircleFilled, label: t("withdraw.statusApproved") },
    { key: "paid", icon: CheckCircleFilled, label: t("withdraw.statusPaid") },
  ];

  const statusOrder: H5WithdrawRequest["status"][] = ["submitted", "reviewing", "approved", "paid"];
  const currentIdx = statusOrder.indexOf(status);

  if (status === "rejected") {
    return (
      <div className="h5-withdraw-status-flow-rejected">
        <CloseCircleFilled style={{ color: "var(--h5-color-danger, #ff4d4f)", fontSize: 20 }} />
        <span>{t("withdraw.statusRejected")}</span>
      </div>
    );
  }

  return (
    <div className="h5-withdraw-status-flow">
      {steps.slice(0, currentIdx + 1).map((step, idx) => (
        <span className="h5-withdraw-status-flow-step-group" key={step.key}>
          {idx > 0 ? <span className="h5-withdraw-status-flow-connector" /> : null}
          <span className={`h5-withdraw-status-flow-step ${idx < currentIdx ? "completed" : "current"}`}>
            <step.icon style={{ fontSize: 16 }} />
            <span>{step.label}</span>
          </span>
        </span>
      ))}
    </div>
  );
}

type WithdrawPageProps = {
  effectiveWalletSummary: H5WalletSummary;
  withdrawAmount: string;
  withdrawRequests: H5WithdrawRequest[];
  maxWithdrawAmount: number;
  actionName: string | null;
  loading?: boolean;
  onWithdrawAmountChange: (value: string) => void;
  onWithdraw: (event: FormEvent<HTMLFormElement>) => Promise<void>;
  onShowTransferAllConfirm: () => void;
  onSetMaxWithdraw: () => void;
};

export function WithdrawPage({
  effectiveWalletSummary,
  withdrawAmount,
  withdrawRequests,
  maxWithdrawAmount,
  actionName,
  loading = false,
  onWithdrawAmountChange,
  onWithdraw,
  onShowTransferAllConfirm,
  onSetMaxWithdraw,
}: WithdrawPageProps): JSX.Element {
  const [amountError, setAmountError] = useState("");

  if (loading) {
    return <DetailSkeleton />;
  }

  const withdrawAmountNum = Number(withdrawAmount);
  const isAmountValid = withdrawAmount.trim().length > 0 && !Number.isNaN(withdrawAmountNum) && withdrawAmountNum > 0;
  const fee = isAmountValid ? Math.min(withdrawAmountNum * WITHDRAW_FEE_RATE, withdrawAmountNum) : 0;
  const estimatedReceive = isAmountValid ? withdrawAmountNum - fee : 0;
  const withdrawableNow = effectiveWalletSummary.canWithdraw ? maxWithdrawAmount : 0;
  const thresholdLabel = t("withdraw.threshold", {
    amount: formatMoney(effectiveWalletSummary.withdrawThreshold, effectiveWalletSummary.currency),
  });
  const readinessHint = effectiveWalletSummary.canWithdraw
    ? t("withdraw.canWithdrawHint")
    : t("withdraw.needTransferHint", {
        amount: formatMoney(effectiveWalletSummary.shortfallAmount, effectiveWalletSummary.currency),
      });
  const nextStepLabel = effectiveWalletSummary.canWithdraw
    ? t("withdraw.nextStepWithdraw")
    : t("withdraw.nextStepTransfer");

  function handleAmountChange(value: string): void {
    onWithdrawAmountChange(value);
    if (value.trim() && !Number.isNaN(Number(value)) && Number(value) > 0) {
      setAmountError("");
      return;
    }
    setAmountError(validateWithdrawAmount(value, maxWithdrawAmount));
  }

  return (
    <section className="h5-card-stack">
      <article className="h5-card h5-member-wallet-balance-hero">
        <SectionHeader meta={t("withdraw.snapshotMeta")} title={t("withdraw.snapshotTitle")} />
        <p className="muted">{t("withdraw.snapshotDesc")}</p>

        <section className="h5-member-balance-strip h5-member-wallet-balance-grid">
          <article className="h5-summary-card h5-member-wallet-balance-card h5-member-wallet-balance-card-system">
            <div className="h5-member-balance-card-main">
              <span className="h5-member-balance-card-label">{t("withdraw.systemBalance")}</span>
              <strong className="h5-member-balance-card-value">
                {formatMoney(effectiveWalletSummary.systemBalance, effectiveWalletSummary.currency)}
              </strong>
              <span className="h5-member-balance-card-note">{t("withdraw.systemBalanceHint")}</span>
            </div>
          </article>

          <article className="h5-summary-card h5-member-wallet-balance-card h5-member-wallet-balance-card-task">
            <div className="h5-member-balance-card-main">
              <span className="h5-member-balance-card-label">{t("withdraw.taskBalance")}</span>
              <strong className="h5-member-balance-card-value">
                {formatMoney(effectiveWalletSummary.taskBalance, effectiveWalletSummary.currency)}
              </strong>
              <span className="h5-member-balance-card-note">{t("withdraw.taskBalanceHint")}</span>
            </div>
            <div className="h5-member-balance-card-actions">
              <button className="h5-secondary-button h5-member-balance-pill-button" onClick={onShowTransferAllConfirm} type="button">
                {t("withdraw.transferAll")}
              </button>
            </div>
          </article>

          <article className="h5-summary-card h5-member-wallet-balance-card h5-member-wallet-balance-card-system">
            <div className="h5-member-balance-card-main">
              <span className="h5-member-balance-card-label">{t("withdraw.availableNow")}</span>
              <strong className="h5-member-balance-card-value">
                {formatMoney(withdrawableNow, effectiveWalletSummary.currency)}
              </strong>
              <span className="h5-member-balance-card-note">
                {effectiveWalletSummary.canWithdraw ? t("withdraw.availableNowHint") : t("withdraw.thresholdNotMet")}
              </span>
            </div>
          </article>
        </section>
      </article>

      <article className="h5-card h5-member-wallet-readiness-card">
        <SectionHeader meta={t("withdraw.readinessMeta")} title={t("withdraw.readinessTitle")} />
        <div className="h5-member-wallet-threshold-bar">
          <strong>{effectiveWalletSummary.canWithdraw ? t("withdraw.metThreshold") : t("withdraw.needTransfer")}</strong>
          <span>{thresholdLabel}</span>
          <span>{readinessHint}</span>
        </div>

        <div className="h5-member-wallet-readiness-grid">
          <article className="h5-member-wallet-readiness-pill">
            <span>{t("withdraw.nextStep")}</span>
            <strong>{nextStepLabel}</strong>
            <small>{effectiveWalletSummary.canWithdraw ? t("withdraw.thresholdMet") : t("withdraw.taskBalanceHint")}</small>
          </article>

          <article className="h5-member-wallet-readiness-pill">
            <span>{t("withdraw.fee")}</span>
            <strong>{t("withdraw.feeRate")}</strong>
            <small>{t("withdraw.feeNote")}</small>
          </article>
        </div>
      </article>

      <article className="h5-card h5-member-wallet-action-card h5-member-wallet-action-card-priority">
        <SectionHeader title={t("withdraw.amount")} />
        <form className="h5-form" onSubmit={(event) => void onWithdraw(event)}>
          <div className="h5-member-wallet-action-head">
            <strong>{t("withdraw.systemWithdraw")}</strong>
            <span>{effectiveWalletSummary.canWithdraw ? t("withdraw.thresholdMet") : t("withdraw.thresholdNotMet")}</span>
          </div>

          <label>
            {t("withdraw.amount")}
            <input
              className={amountError ? "h5-field-input-error" : ""}
              inputMode="decimal"
              onChange={(event) => handleAmountChange(event.target.value)}
              value={withdrawAmount}
            />
            {amountError ? <span className="h5-field-error">{amountError}</span> : null}
          </label>

          {fee > 0 && !amountError ? (
            <div className="h5-withdraw-fee-display">
              <span>{`${t("withdraw.fee")}: ${formatMoney(fee, effectiveWalletSummary.currency)}`}</span>
              {estimatedReceive > 0 ? (
                <span>
                  {t("withdraw.estimatedReceive", {
                    amount: formatMoney(estimatedReceive, effectiveWalletSummary.currency),
                  })}
                </span>
              ) : null}
            </div>
          ) : null}

          <div className="h5-member-inline-actions">
            <button className="h5-secondary-button" onClick={onSetMaxWithdraw} type="button">
              {t("withdraw.withdrawAll")}
            </button>
            <button className="h5-primary-button" disabled={actionName === "withdraw" || loading} type="submit">
              {loading || actionName === "withdraw" ? (
                <>
                  <span className="h5-spinner" /> {t("withdraw.processing")}
                </>
              ) : (
                t("withdraw.withdraw")
              )}
            </button>
          </div>
        </form>
      </article>

      <article className="h5-card">
        <SectionHeader meta={t("orders.count", { count: withdrawRequests.length })} title={t("withdraw.history")} />
        <div className="h5-card-stack">
          {withdrawRequests.length > 0 ? (
            withdrawRequests.map((item) => (
              <div className="h5-withdraw-request-item" key={item.id}>
                <CompactListRow
                  meta={getWithdrawStatusLabel(item.status)}
                  sideNote={formatTimestamp(item.createdAt)}
                  title={formatMoney(item.amount, item.currency)}
                  tone={item.status === "rejected" ? "danger" : item.status === "paid" ? "success" : "active"}
                  value={getWithdrawStatusLabel(item.status)}
                />
                <WithdrawStatusFlow status={item.status} />
              </div>
            ))
          ) : (
            <EmptyStateCard
              action={
                <button className="h5-secondary-button" onClick={onSetMaxWithdraw} type="button">
                  {t("withdraw.withdrawAll")}
                </button>
              }
              description={t("withdraw.noHistoryDesc")}
              icon={<WalletOutlined />}
              title={t("withdraw.noHistory")}
            />
          )}
        </div>
      </article>
    </section>
  );
}
