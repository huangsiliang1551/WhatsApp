import { type JSX, type MouseEvent } from "react";
import { AppstoreOutlined, CheckCircleOutlined, FireOutlined } from "@ant-design/icons";

import type { H5SignInStatus, H5TaskInstance } from "../../services/h5Member";
import {
  formatCountdown,
  formatMoney,
  formatPercentage,
  getTaskPackageTypeLabel,
} from "./sharedUtils";
import { DetailGrid, EmptyStateCard, PullToRefresh, SectionHeader } from "./sharedComponents";
import { t } from "./i18n";
import { ListSkeleton } from "./skeletons";

type TasksPageProps = {
  signInStatus: H5SignInStatus;
  taskInstances: H5TaskInstance[];
  actionName: string | null;
  loading: boolean;
  error: string | null;
  onSignIn: () => Promise<void>;
  onNavigate: (path: string) => void;
  onRefresh: () => Promise<void>;
  onOpenClaimDialog?: (packageId: string) => void;
};

export function TasksPage({
  signInStatus,
  taskInstances,
  actionName,
  loading,
  error,
  onSignIn,
  onNavigate,
  onRefresh,
  onOpenClaimDialog,
}: TasksPageProps): JSX.Element {
  const inProgress = taskInstances.filter((task) => task.status === "active");
  const available = taskInstances.filter((task) => task.status === "pending_claim");
  const completed = taskInstances.filter((task) => task.status === "completed");
  const expired = taskInstances.filter((task) => task.status === "expired");
  const prioritizeInProgress = inProgress.length > 0;

  function renderSignInCard(): JSX.Element {
    const { todaySignedIn, consecutiveDays, goalDays, goalReward, isCompleted } = signInStatus;
    const progress = Math.min((consecutiveDays / goalDays) * 100, 100);

    if (isCompleted) {
      return (
        <article className="h5-card h5-signin-card">
          <div className="h5-signin-header">
            <span className="h5-signin-fire"><CheckCircleOutlined /></span>
            <strong>{t("tasks.signedIn")}</strong>
          </div>
          <p className="h5-signin-goal">{t("tasks.signInGoal", { n: goalDays, amount: goalReward.toFixed(2) })}</p>
          <div className="h5-signin-progress-row">
            <div className="h5-member-progress">
              <div className="h5-member-progress-fill" style={{ width: "100%", background: "#52c41a" }} />
            </div>
            <span className="h5-signin-count">{t("tasks.consecutiveDays", { n: consecutiveDays })}</span>
          </div>
        </article>
      );
    }

    return (
      <article className="h5-card h5-signin-card">
        <div className="h5-signin-header">
          <span className="h5-signin-fire"><FireOutlined /></span>
          <strong>{t("tasks.consecutiveDays", { n: consecutiveDays })}</strong>
        </div>
        <p className="h5-signin-goal">{t("tasks.signInGoal", { n: goalDays, amount: goalReward.toFixed(2) })}</p>
        <div className="h5-signin-progress-row">
          <div className="h5-member-progress">
            <div className="h5-member-progress-fill" style={{ width: `${progress}%` }} />
          </div>
          <span className="h5-signin-count">{`${consecutiveDays}/${goalDays}`}</span>
        </div>
        <button
          className={`h5-signin-btn${todaySignedIn ? " h5-signin-btn-done" : ""}`}
          disabled={todaySignedIn || actionName === "signin-task"}
          onClick={() => void onSignIn()}
          title={todaySignedIn ? t("tasks.signedIn") : actionName === "signin-task" ? t("common.loading") : t("tasks.signIn")}
          type="button"
        >
          {todaySignedIn ? (
            <>
              <CheckCircleOutlined /> {t("tasks.signedIn")}
            </>
          ) : (
            actionName === "signin-task" ? t("common.loading") : t("tasks.signIn")
          )}
        </button>
      </article>
    );
  }

  function renderTaskCard(instance: H5TaskInstance): JSX.Element {
    const progress = instance.totalCount > 0 ? (instance.completedCount / instance.totalCount) * 100 : 0;
    const totalCommission = instance.totalCommission ?? instance.rewardAmount;
    const countdownSeconds = instance.countdownSeconds ?? 0;
    const isAvailable = instance.status === "pending_claim";
    const statusClass =
      instance.status === "completed"
        ? "completed"
        : instance.status === "expired"
          ? "expired"
          : "active";
    const statusLabel =
      instance.status === "pending_claim"
        ? t("tasks.groupAvailable")
        : instance.status === "active"
          ? t("tasks.inProgress")
          : instance.status === "completed"
            ? t("tasks.completed")
            : t("tasks.expired");

    function handleCardClick(): void {
      onNavigate(`/h5/tasks/package/${instance.id}`);
    }

    function handlePrimaryAction(event: MouseEvent<HTMLButtonElement>): void {
      event.stopPropagation();
      if (isAvailable && onOpenClaimDialog) {
        onOpenClaimDialog(instance.id);
        return;
      }
      handleCardClick();
    }

    return (
      <article
        className="h5-card h5-task-instance-card"
        key={instance.id}
        onClick={handleCardClick}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") {
            handleCardClick();
          }
        }}
        role="button"
        tabIndex={0}
      >
        <div className="h5-member-task-summary">
          <div>
            <strong>{instance.title}</strong>
            <p className="muted">
              {isAvailable
                ? t("tasks.startsOnClaim")
                : t("tasks.remaining", { time: formatCountdown(countdownSeconds) })}
            </p>
          </div>
          <span className={`h5-task-instance-status-badge ${statusClass}`}>{statusLabel}</span>
        </div>

        <div className="h5-task-instance-meta h5-member-task-chip-row">
          <span className="h5-member-inline-pill">{getTaskPackageTypeLabel(instance.type)}</span>
          <span className="h5-member-inline-pill">{t("tasks.items", { count: instance.totalCount })}</span>
          <span className="h5-member-inline-pill">{`${t("tasks.rewardRatio")} ${formatPercentage(instance.rewardRatio)}`}</span>
        </div>

        <DetailGrid
          items={[
            { label: t("tasks.remainingTime"), value: formatCountdown(countdownSeconds) },
            {
              label: t("tasks.progress", { done: instance.completedCount, total: instance.totalCount }),
              value: `${Math.round(progress)}%`,
            },
            { label: t("tasks.totalCommission"), value: formatMoney(totalCommission) },
          ]}
        />

        <div className="h5-member-progress" style={{ marginTop: 12 }}>
          <div className="h5-member-progress-fill" style={{ width: `${progress}%` }} />
        </div>

        <div className="h5-member-card-actions" style={{ marginTop: 12 }}>
          <button className="seed-button" onClick={handlePrimaryAction} type="button">
            {isAvailable ? t("tasks.claim") : t("tasks.viewPackage")}
          </button>
        </div>
      </article>
    );
  }

  function renderPartition(title: string, items: H5TaskInstance[]): JSX.Element | null {
    if (items.length === 0) return null;
    return (
      <section className="h5-task-section">
        <h4 className="h5-task-partition-title">{`${title} (${items.length})`}</h4>
        <div className="h5-card-stack">
          {items.map(renderTaskCard)}
        </div>
      </section>
    );
  }

  if (loading && taskInstances.length === 0) {
    return (
      <section className="h5-card-stack">
        <ListSkeleton count={4} />
      </section>
    );
  }

  return (
    <section className="h5-card-stack">
      <PullToRefresh onRefresh={async () => { await onRefresh(); }}>
        {prioritizeInProgress ? renderPartition(t("tasks.groupInProgress"), inProgress) : null}

        {renderSignInCard()}

        <article className="h5-card h5-task-overview-card">
          <SectionHeader meta={t("tasks.overviewMeta")} title={t("tasks.overviewTitle")} />
          <div className="h5-task-overview-grid">
            <article className="h5-member-detail-card">
              <span className="h5-member-detail-label">{t("tasks.groupInProgress")}</span>
              <strong className="h5-member-detail-value">{inProgress.length}</strong>
            </article>
            <article className="h5-member-detail-card">
              <span className="h5-member-detail-label">{t("tasks.groupAvailable")}</span>
              <strong className="h5-member-detail-value">{available.length}</strong>
            </article>
            <article className="h5-member-detail-card">
              <span className="h5-member-detail-label">{t("tasks.groupCompleted")}</span>
              <strong className="h5-member-detail-value">{completed.length}</strong>
            </article>
          </div>
          <div className="h5-member-task-chip-row">
            <span className="h5-member-inline-pill">{t("tasks.overviewActive", { count: inProgress.length })}</span>
            <span className="h5-member-inline-pill">{t("tasks.overviewAvailable", { count: available.length })}</span>
            <span className="h5-member-inline-pill">{t("tasks.overviewCompleted", { count: completed.length })}</span>
          </div>
        </article>

        {error ? (
          <article className="h5-card">
            <p style={{ color: "var(--color-error, #ff4d4f)", fontSize: 14 }}>{error}</p>
          </article>
        ) : null}

        {!prioritizeInProgress ? renderPartition(t("tasks.groupInProgress"), inProgress) : null}
        {renderPartition(t("tasks.groupAvailable"), available)}
        {renderPartition(t("tasks.groupCompleted"), completed)}
        {renderPartition(t("tasks.groupExpired"), expired)}

        {taskInstances.length === 0 && !error ? (
          <article className="h5-card">
            <EmptyStateCard
              description={t("tasks.noPackagesDesc")}
              icon={<AppstoreOutlined />}
              title={t("tasks.noPackages")}
            />
          </article>
        ) : null}
      </PullToRefresh>
    </section>
  );
}
