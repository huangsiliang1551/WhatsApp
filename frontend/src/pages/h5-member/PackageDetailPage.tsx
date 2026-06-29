import { useRef, useState, type JSX } from "react";
import { CheckCircleOutlined, CloseCircleOutlined, LoadingOutlined, WarningOutlined } from "@ant-design/icons";

import type { H5TaskInstance, H5TaskProductStatus } from "../../services/h5Member";
import {
  delay,
  formatCountdown,
  formatMoney,
  getPurchaseFailureActions,
  getTaskPackageTypeLabel,
} from "./sharedUtils";
import { DetailGrid, SectionHeader } from "./sharedComponents";
import { t } from "./i18n";

type PackageDetailPageProps = {
  instance: H5TaskInstance;
  actionName: string | null;
  onStartProduct: (productId: string) => Promise<void>;
  onRetryProduct: (productId: string) => Promise<void>;
  onNavigate: (path: string) => void;
  onRefresh: () => Promise<void>;
  onOpenClaimDialog?: (pkg: { id: string; title: string }) => void;
};

export function PackageDetailPage({
  instance,
  actionName,
  onStartProduct,
  onRetryProduct,
  onNavigate,
  onOpenClaimDialog,
}: PackageDetailPageProps): JSX.Element {
  const [showProgress, setShowProgress] = useState(false);
  const [currentProductId, setCurrentProductId] = useState<string | null>(null);
  const [progressStep, setProgressStep] = useState(0);
  const [progressFailed, setProgressFailed] = useState(false);
  const [progressFailureReason, setProgressFailureReason] = useState<string | null>(null);
  const [currentActionKind, setCurrentActionKind] = useState<"start" | "retry" | null>(null);
  const [showBalanceDialog, setShowBalanceDialog] = useState(false);
  const [balanceProduct, setBalanceProduct] = useState<{ price: number; currency: string } | null>(null);
  const stepsCardRef = useRef<HTMLElement | null>(null);

  const allCompleted = instance.products.length > 0 && instance.products.every((product) => product.status === "completed");
  const remainingItems = Math.max(0, instance.totalCount - instance.completedCount);
  const currentCommission = instance.currentCommission ?? 0;
  const totalCommission = instance.totalCommission ?? instance.rewardAmount;
  const countdownSeconds = instance.countdownSeconds ?? 0;
  const progressPercent = instance.totalCount > 0 ? (instance.completedCount / instance.totalCount) * 100 : 0;
  const visibleCurrentProduct = instance.currentProduct ?? null;
  const batchProgressLabel = instance.batchIndex && instance.batchTotal ? `${instance.batchIndex}/${instance.batchTotal}` : null;
  const focusStatusClass =
    instance.status === "pending_claim"
      ? "active"
      : instance.status === "completed"
        ? "completed"
        : instance.status === "expired"
          ? "expired"
          : "active";
  const focusStatusLabel =
    instance.status === "pending_claim"
      ? t("tasks.groupAvailable")
      : instance.status === "completed"
        ? t("tasks.completed")
        : instance.status === "expired"
          ? t("tasks.expired")
          : t("tasks.groupInProgress");
  const nextStepLabel =
    instance.status === "pending_claim"
      ? t("tasks.detailFocusClaim")
      : visibleCurrentProduct?.status === "failed"
        ? t("tasks.retry")
        : visibleCurrentProduct
          ? t("tasks.detailFocusReady")
          : t("tasks.detailWaitingNextTask");
  const progressSteps = [
    { key: "ordering", label: t("tasks.progressOrdering") },
    {
      key: "paying",
      label: t("tasks.progressPaying", {
        amount: formatMoney(balanceProduct?.price ?? 0, balanceProduct?.currency ?? "USD"),
      }),
    },
    { key: "paid", label: t("tasks.progressPaid") },
    { key: "checking", label: t("tasks.progressChecking") },
  ];
  const balanceLabelParts = [
    {
      label: t("tasks.needAmount", { amount: "" }).replace(/[:：]\s*$/, ""),
      value: formatMoney(balanceProduct?.price ?? 0, balanceProduct?.currency ?? "USD"),
    },
    {
      label: t("tasks.currentBalance", { amount: "" }).replace(/[:：]\s*$/, ""),
      value: formatMoney(instance.systemBalance),
    },
  ];

  function getProductStatusLabel(status: H5TaskProductStatus): string {
    switch (status) {
      case "pending":
        return t("tasks.productPending");
      case "available":
        return t("tasks.productAvailable");
      case "running":
        return t("tasks.productRunning");
      case "completed":
        return t("tasks.productCompleted");
      case "failed":
        return t("tasks.productFailed");
    }
  }

  function getProductBtnClass(status: H5TaskProductStatus): string {
    switch (status) {
      case "available":
        return "status-available";
      case "completed":
        return "status-completed";
      case "failed":
        return "status-failed";
      case "running":
        return "status-running";
      default:
        return "";
    }
  }

  function isProductDisabled(status: H5TaskProductStatus): boolean {
    return status !== "available" && status !== "failed";
  }

  function closeProgressModal(): void {
    setShowProgress(false);
    setCurrentProductId(null);
    setProgressStep(0);
    setProgressFailed(false);
    setProgressFailureReason(null);
    setCurrentActionKind(null);
    setBalanceProduct(null);
  }

  async function handleProductAction(productId: string, status: H5TaskProductStatus): Promise<void> {
    if (status === "completed" || status === "running") return;
    const product = instance.products.find((item) => item.id === productId);
    if (!product) return;

    if (product.price > instance.systemBalance) {
      setBalanceProduct(product);
      setShowBalanceDialog(true);
      return;
    }

    setCurrentProductId(productId);
    setCurrentActionKind(status === "failed" ? "retry" : "start");
    setBalanceProduct(product);
    setProgressFailed(false);
    setProgressFailureReason(null);
    setProgressStep(0);
    setShowProgress(true);

    setProgressStep(1);
    await delay(800);
    setProgressStep(2);
    await delay(800);
    setProgressStep(3);
    await delay(800);
    setProgressStep(4);

    try {
      if (status === "failed") {
        await onRetryProduct(productId);
      } else {
        await onStartProduct(productId);
      }
      setProgressStep(5);
      await delay(600);
      closeProgressModal();
    } catch (error) {
      setProgressFailed(true);
      setProgressFailureReason(error instanceof Error ? error.message : t("notification.purchaseFailed"));
    }
  }

  async function handleRetryCurrentAction(): Promise<void> {
    if (!currentProductId || !currentActionKind) return;
    await handleProductAction(currentProductId, currentActionKind === "retry" ? "failed" : "available");
  }

  function handleFailureAction(action: "recharge" | "retry" | "tickets" | "tasks"): void {
    if (action === "retry") {
      void handleRetryCurrentAction();
      return;
    }
    closeProgressModal();
    if (action === "recharge") {
      onNavigate("/h5/wallet");
      return;
    }
    if (action === "tasks") {
      onNavigate("/h5/tasks");
      return;
    }
    onNavigate("/h5/tickets/new");
  }

  function renderProgressModal(): JSX.Element | null {
    if (!showProgress) return null;
    const current = progressStep;
    const progressPct = Math.min(Math.round((current / 5) * 100), 100);

    return (
      <div className="h5-progress-modal-backdrop" role="presentation">
        <article aria-modal="true" className="h5-progress-modal" role="dialog">
          <h3>{t("tasks.startTask")}</h3>
          {progressSteps.map((step, index) => {
            const stepNum = index + 1;
            let cls = "";
            let icon: JSX.Element;
            if (stepNum < current) {
              cls = "done";
              icon = <CheckCircleOutlined />;
            } else if (stepNum === current) {
              cls = "active";
              icon = <LoadingOutlined />;
            } else {
              icon = <span aria-hidden="true" className="h5-progress-step-icon-placeholder">○</span>;
            }
            return (
              <div className={`h5-progress-step ${cls}`} key={step.key}>
                <span className="h5-progress-step-icon">{icon}</span>
                <span>{step.label}</span>
              </div>
            );
          })}
          {current <= 4 ? (
            <div className="h5-progress-step-bar">
              <div className="h5-progress-step-bar-fill" style={{ width: `${progressPct}%` }} />
            </div>
          ) : null}
          {progressFailed ? (
            <>
              <p className="h5-package-progress-status h5-package-progress-status-error">
                <CloseCircleOutlined /> {progressFailureReason ?? t("common.failed")}
              </p>
              <div className="h5-member-card-actions">
                {getPurchaseFailureActions(progressFailureReason ?? undefined).map((action) => (
                  <button
                    className={action === "retry" ? "seed-button" : "seed-button seed-button-secondary"}
                    key={action}
                    onClick={() => handleFailureAction(action)}
                    type="button"
                  >
                    {action === "recharge"
                      ? t("purchase.actionRecharge")
                      : action === "tasks"
                        ? t("purchase.actionBackToTasks")
                        : action === "tickets"
                          ? t("purchase.actionContact")
                          : t("purchase.actionRetry")}
                  </button>
                ))}
              </div>
            </>
          ) : current > 4 ? (
            <p className="h5-package-progress-status h5-package-progress-status-success">
              <CheckCircleOutlined /> {t("common.success")}
            </p>
          ) : null}
        </article>
      </div>
    );
  }

  function renderBalanceDialog(): JSX.Element | null {
    if (!showBalanceDialog || !balanceProduct) return null;
    return (
      <div className="h5-progress-modal-backdrop" role="presentation">
        <article aria-modal="true" className="h5-progress-modal h5-balance-dialog" role="dialog">
          <div className="h5-balance-dialog-icon"><WarningOutlined /></div>
          <h3>{t("tasks.insufficientBalance")}</h3>
          <div className="h5-balance-dialog-amounts">
            {balanceLabelParts.map((item) => (
              <span key={item.label}>
                <span className="amount-value">{item.value}</span>
                <span className="amount-label">{item.label}</span>
              </span>
            ))}
          </div>
          <div className="h5-member-card-actions">
            <button className="seed-button" onClick={() => onNavigate("/h5/wallet")} type="button">
              {t("tasks.goRecharge")}
            </button>
            <button className="seed-button seed-button-secondary" onClick={() => setShowBalanceDialog(false)} type="button">
              {t("common.cancel")}
            </button>
          </div>
        </article>
      </div>
    );
  }

  function renderCelebration(): JSX.Element {
    return (
      <section className="h5-card-stack">
        <article className="h5-card h5-package-celebration">
          <div aria-hidden="true" className="h5-package-celebration-icon">🎉</div>
          <h2>{t("serviceMessages.packageCompletedTitle", { title: instance.title })}</h2>
          <p>{t("serviceMessages.packageCompletedBody")}</p>
          <div className="h5-package-celebration-actions">
            <button className="seed-button" onClick={() => onNavigate("/h5/wallet")} type="button">
              {t("tasks.viewBalance")}
            </button>
            <button className="seed-button seed-button-secondary" onClick={() => onNavigate("/h5/tasks")} type="button">
              {t("tasks.backToTaskList")}
            </button>
          </div>
        </article>
      </section>
    );
  }

  function renderSummaryCard(): JSX.Element {
    const claimOnly = instance.status === "pending_claim";
    const amountBreakdown = [
      { label: t("tasks.plannedAmount"), value: formatMoney(instance.plannedAmount ?? 0) },
      { label: t("tasks.systemAmount"), value: formatMoney(instance.systemGeneratedAmount ?? 0) },
      { label: t("tasks.manualAddAmount"), value: formatMoney(instance.manualAddedAmount ?? 0) },
      { label: t("tasks.effectiveAmount"), value: formatMoney(instance.effectiveAmount ?? 0) },
    ];

    return (
      <article className="h5-card">
        <SectionHeader title={t("tasks.detailRewardSummary")} meta={instance.title} />
        <div className="h5-member-task-chip-row">
          <span className="h5-member-inline-pill">{t("tasks.progress", { done: instance.completedCount, total: instance.totalCount })}</span>
          <span className="h5-member-inline-pill">{`${t("tasks.rewardRatio")} ${Math.round(instance.rewardRatio * 100)}%`}</span>
          <span className="h5-member-inline-pill">{t("tasks.currentCommission", { amount: formatMoney(currentCommission) })}</span>
        </div>
        <DetailGrid
          items={[
            { label: t("tasks.remainingItems"), value: String(remainingItems) },
            { label: t("tasks.expectedCommission"), value: formatMoney(totalCommission) },
            { label: t("tasks.countdown"), value: formatCountdown(countdownSeconds) },
          ]}
        />
        <DetailGrid items={amountBreakdown} />
        <div className="h5-member-progress h5-package-summary-progress">
          <div className="h5-member-progress-fill" style={{ width: `${progressPercent}%` }} />
        </div>
        <div className="h5-package-reward-row">
          <span aria-hidden="true" className="h5-package-reward-icon">💰</span>
          <span>{t("tasks.expectedCommission", { amount: formatMoney(totalCommission) })}</span>
        </div>
        <p className="h5-package-note-copy">{t("tasks.detailRewardArrival")}</p>
        <div className="h5-package-balance-row">
          <span>{t("profile.systemBalance")}</span>
          <strong>{formatMoney(instance.systemBalance)}</strong>
        </div>
        {claimOnly ? (
          <div className="h5-member-card-actions h5-package-inline-actions">
            <button className="seed-button" onClick={() => onOpenClaimDialog?.({ id: instance.id, title: instance.title })} type="button">
              {t("shell.confirmClaimBtn")}
            </button>
          </div>
        ) : null}
      </article>
    );
  }

  function renderFocusCard(): JSX.Element {
    const claimOnly = instance.status === "pending_claim";

    function handleFocusAction(): void {
      if (claimOnly) {
        onOpenClaimDialog?.({ id: instance.id, title: instance.title });
        return;
      }
      stepsCardRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }

    return (
      <article className="h5-card h5-package-focus-card">
        <SectionHeader title={t("tasks.detailFocusTitle")} meta={t("tasks.detailFocusMeta")} />
        <div className="h5-task-focus-panel">
          <div className="h5-task-focus-copy">
            <strong>{instance.title}</strong>
            <p className="muted">{t("tasks.detailRemainingLabel", { done: instance.completedCount, total: instance.totalCount })}</p>
            {batchProgressLabel ? <p className="muted">{batchProgressLabel}</p> : null}
          </div>
          <span className={`h5-task-instance-status-badge ${focusStatusClass}`}>
            {focusStatusLabel}
          </span>
        </div>

        <div className="h5-task-focus-grid">
          <article className="h5-task-focus-pill">
            <span>{t("tasks.detailNextStep")}</span>
            <strong>{nextStepLabel}</strong>
            <small>{claimOnly ? t("tasks.startsOnClaim") : t("tasks.detailStepHint")}</small>
          </article>
          <article className="h5-task-focus-pill">
            <span>{t("tasks.expectedCommission")}</span>
            <strong>{formatMoney(totalCommission)}</strong>
            <small>{t("tasks.countdown")}: {formatCountdown(countdownSeconds)}</small>
          </article>
        </div>

        <div className="h5-member-card-actions">
          <button className="seed-button" onClick={handleFocusAction} type="button">
            {claimOnly ? t("tasks.claim") : t("home.actionContinue")}
          </button>
          <button className="seed-button seed-button-secondary" onClick={() => onNavigate("/h5/tasks")} type="button">
            {t("tasks.backToTasks")}
          </button>
        </div>
      </article>
    );
  }

  function renderProductsCard(): JSX.Element | null {
    if (instance.status === "pending_claim") {
      return (
        <article className="h5-card">
          <SectionHeader title={t("tasks.detailCompletionSteps")} meta={getTaskPackageTypeLabel(instance.type)} />
          <p className="muted">{t("shell.claimHint")}</p>
          <div className="template-detail-grid">
            <span>{t("shell.claimRule1")}</span>
            <span>{t("shell.claimRule2")}</span>
            <span>{t("shell.claimRule3")}</span>
            <span>{t("shell.claimRule4")}</span>
          </div>
        </article>
      );
    }

    return (
        <article className="h5-card" ref={stepsCardRef}>
        <SectionHeader
          title={t("tasks.detailCompletionSteps")}
          meta={t("tasks.items", { count: instance.totalCount })}
        />
        <p className="h5-package-note-copy">{t("tasks.detailStepHint")}</p>
        {!visibleCurrentProduct ? (
          <p className="h5-package-note-copy">{t("tasks.detailWaitingNextTask")}</p>
        ) : null}
        {(visibleCurrentProduct ? [visibleCurrentProduct] : []).map((product) => {
          const isDisabled = isProductDisabled(product.status);
          const isCurrentAction = actionName === `start:${product.id}` || actionName === `retry:${product.id}`;
          return (
            <div className="h5-package-product-item" key={product.id}>
              <img
                alt={product.productName}
                className="h5-package-product-img"
                src={product.imageUrl || "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='52' height='52'%3E%3Crect width='52' height='52' fill='%23f3f4f6'/%3E%3C/svg%3E"}
              />
              <div className="h5-package-product-info">
                <strong>{product.productName}</strong>
                <span className="h5-package-product-price">{formatMoney(product.price, product.currency)}</span>
              </div>
              <button
                className={`h5-package-product-btn ${getProductBtnClass(product.status)}`}
                disabled={isDisabled || isCurrentAction || actionName !== null}
                onClick={() => void handleProductAction(product.id, product.status)}
                title={isCurrentAction ? t("common.loading") : getProductStatusLabel(product.status)}
                type="button"
              >
                {isCurrentAction ? t("common.loading") : getProductStatusLabel(product.status)}
              </button>
            </div>
          );
        })}
      </article>
    );
  }

  function renderSupportCard(): JSX.Element | null {
    if (showProgress || showBalanceDialog) {
      return null;
    }

    return (
      <article className="h5-card">
        <SectionHeader title={t("tasks.detailSupport")} meta={getTaskPackageTypeLabel(instance.type)} />
        <p className="h5-package-note-copy">{t("tasks.detailSupportHint")}</p>
        <div className="template-detail-grid h5-package-note-grid">
          <span>{t("tasks.detailCountdownNotice")}</span>
          <span>{t("tasks.detailBalanceNotice")}</span>
        </div>
        <div className="h5-member-card-actions h5-package-inline-actions">
          <button className="seed-button" onClick={() => onNavigate("/h5/tickets/new")} type="button">
            {t("tasks.contactSupport")}
          </button>
          <button className="seed-button seed-button-secondary" onClick={() => onNavigate("/h5/tasks")} type="button">
            {t("tasks.backToTasks")}
          </button>
        </div>
      </article>
    );
  }

  if (allCompleted && instance.status !== "pending_claim") {
    return renderCelebration();
  }

  return (
    <section className="h5-card-stack">
      {renderFocusCard()}
      {renderSummaryCard()}
      {renderProductsCard()}
      {renderSupportCard()}
      {renderProgressModal()}
      {renderBalanceDialog()}
    </section>
  );
}
