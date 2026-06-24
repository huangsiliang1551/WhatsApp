import { useEffect, useRef, useState, type JSX, type ReactNode } from "react";
import { EyeInvisibleOutlined, EyeOutlined, LoadingOutlined } from "@ant-design/icons";

import type { H5MessageItem } from "../../services/h5Member";
import {
  formatTimestamp,
  getMessageCategoryLabel,
  getPurchaseFlowSteps,
  getPurchaseStageMeta,
  type PurchasePhaseState,
  type ToastItem,
} from "./sharedUtils";
import { t } from "./i18n";

export function QuickActionCard({
  title,
  body,
  icon,
  meta,
  onClick,
  compact = false,
}: {
  title: string;
  body: string;
  icon: JSX.Element;
  meta?: string;
  onClick: () => void;
  compact?: boolean;
}): JSX.Element {
  return (
    <button className={`h5-member-quick-action ${compact ? "h5-member-quick-action-compact" : ""}`} onClick={onClick} type="button">
      <div className="h5-member-quick-action-head">
        <span className="h5-member-quick-action-icon">{icon}</span>
        {meta ? <span className="h5-member-quick-action-meta">{meta}</span> : null}
      </div>
      <strong>{title}</strong>
      <span>{body}</span>
    </button>
  );
}

export function SectionHeader({
  title,
  meta,
  action,
}: {
  title: string;
  meta?: string;
  action?: JSX.Element;
}): JSX.Element {
  return (
    <div className="h5-card-header">
      <div className="h5-member-section-heading">
        <strong title={title}>{title}</strong>
        {meta ? <span className="h5-member-section-meta" title={meta}>{meta}</span> : null}
      </div>
      {action}
    </div>
  );
}

export function RetryBar({
  message,
  onRetry,
}: {
  message: string;
  onRetry: () => void;
}): JSX.Element {
  return (
    <div className="h5-retry-bar">
      <span className="h5-retry-message">{message}</span>
      <button className="h5-retry-button" onClick={onRetry} type="button">
        {t("common.retry")}
      </button>
    </div>
  );
}

export function EmptyStateCard({
  icon,
  title,
  description,
  action,
}: {
  icon: JSX.Element;
  title: string;
  description: string;
  action?: JSX.Element;
}): JSX.Element {
  return (
    <div className="h5-empty-state">
      <span aria-hidden="true" className="h5-empty-icon">
        {icon}
      </span>
      <strong className="h5-empty-title">{title}</strong>
      <p className="h5-empty-desc">{description}</p>
      {action ? <div className="h5-button-group">{action}</div> : null}
    </div>
  );
}

export function DetailGrid({
  items,
}: {
  items: Array<{ label: string; value: string }>;
}): JSX.Element {
  return (
    <div className="h5-member-detail-grid">
      {items.map((item) => (
        <article className="h5-member-detail-card" key={`${item.label}:${item.value}`}>
          <span className="h5-member-detail-label">{item.label}</span>
          <strong className="h5-member-detail-value">{item.value}</strong>
        </article>
      ))}
    </div>
  );
}

export function CompactListRow({
  title,
  subtitle,
  meta,
  badge,
  value,
  sideNote,
  tone = "default",
  onClick,
  actionLabel,
}: {
  title: string;
  subtitle?: string;
  meta?: string;
  badge?: string;
  value?: string;
  sideNote?: string;
  tone?: "default" | "active" | "success" | "danger";
  onClick?: () => void;
  actionLabel?: string;
}): JSX.Element {
  const content = (
    <>
      <div className="h5-member-list-row-main">
        <div className="h5-member-list-row-copy">
          <div className="h5-member-list-row-title">
            <strong title={title}>{title}</strong>
            {badge ? <span className={`h5-member-list-row-badge h5-member-list-row-badge-${tone}`}>{badge}</span> : null}
          </div>
          {subtitle || meta ? (
            <span className="h5-member-list-row-subtitle">
              {subtitle}
              {subtitle && meta ? " · " : ""}
              {meta}
            </span>
          ) : null}
        </div>
      </div>
      <div className="h5-member-list-row-side">
        {value ? <strong className={`h5-member-list-row-value h5-member-list-row-value-${tone}`}>{value}</strong> : null}
        {sideNote || actionLabel ? (
          <div className="h5-member-list-row-meta">
            {sideNote ? <span className="h5-member-list-row-note">{sideNote}</span> : null}
            {actionLabel ? <span className="h5-member-list-row-action">{actionLabel}</span> : null}
          </div>
        ) : null}
      </div>
    </>
  );

  if (onClick) {
    return (
      <button className="h5-member-list-row h5-member-list-row-button" onClick={onClick} type="button">
        {content}
      </button>
    );
  }

  return <div className="h5-member-list-row">{content}</div>;
}

export function MessageFeedItem({
  item,
  onClick,
  compact = false,
}: {
  item: H5MessageItem;
  onClick: () => void;
  compact?: boolean;
}): JSX.Element {
  return (
    <button
      className={`h5-member-message-feed-item ${compact ? "h5-member-message-feed-item-compact" : ""} ${
        item.isRead ? "" : "h5-member-message-feed-item-unread h5-member-message-card-unread"
      }`}
      onClick={onClick}
      type="button"
    >
      <div className="h5-member-message-feed-head">
        <div className="h5-member-message-feed-title">
          <strong>{item.title}</strong>
          {!item.isRead ? <span className="h5-member-message-unread-dot">{t("messages.unreadDot")}</span> : null}
        </div>
        <span className="badge badge-neutral">{getMessageCategoryLabel(item.category)}</span>
      </div>
      <p>{item.body}</p>
      <div className="h5-member-message-feed-foot">
        <span>{formatTimestamp(item.createdAt)}</span>
        <span>{item.isRead ? t("messages.viewed") : t("messages.clickView")}</span>
      </div>
    </button>
  );
}

export function AmountPresetRow({
  values,
  currentValue,
  onSelect,
}: {
  values: number[];
  currentValue: string;
  onSelect: (value: string) => void;
}): JSX.Element {
  return (
    <div className="h5-member-amount-presets">
      {values.map((value) => (
        <button
          className={`h5-member-amount-chip ${currentValue === String(value) ? "h5-member-amount-chip-active" : ""}`}
          key={value}
          onClick={() => onSelect(String(value))}
          type="button"
        >
          {value}
        </button>
      ))}
    </div>
  );
}

export function PasswordField({
  value,
  placeholder,
  visible,
  onChange,
  onToggle,
  onBlur,
}: {
  value: string;
  placeholder: string;
  visible: boolean;
  onChange: (value: string) => void;
  onToggle: () => void;
  onBlur?: () => void;
}): JSX.Element {
  return (
    <div className="h5-member-password-field">
      <input placeholder={placeholder} type={visible ? "text" : "password"} value={value} onChange={(event) => onChange(event.target.value)} onBlur={onBlur} />
      <button
        aria-label={visible ? t("common.hidePassword") : t("common.showPassword")}
        className="h5-member-password-toggle"
        onClick={onToggle}
        type="button"
      >
        {visible ? <EyeInvisibleOutlined /> : <EyeOutlined />}
      </button>
    </div>
  );
}

export function ToastStack({ items, compact = false }: { items: ToastItem[]; compact?: boolean }): JSX.Element | null {
  if (!items.length) return null;

  return (
    <div className={`h5-member-toast-stack ${compact ? "h5-member-toast-stack-compact" : ""}`.trim()} role="status">
      {items.map((item) => (
        <div className={`h5-member-toast ${compact ? "h5-member-toast-compact" : ""} h5-member-toast-${item.tone}`.trim()} key={item.key}>
          <span>{item.message}</span>
          <span className="h5-member-toast-progress" style={{ animationDuration: `${item.duration}ms` }} />
        </div>
      ))}
    </div>
  );
}
export function PurchaseFlow({ state }: { state: PurchasePhaseState }): JSX.Element {
  const steps = getPurchaseFlowSteps(state);
  return (
    <div className="h5-member-purchase-flow">
      {steps.map((step) => (
        <span className={`h5-member-purchase-step h5-member-purchase-step-${step.status}`} key={step.label}>
          {step.label}
        </span>
      ))}
    </div>
  );
}

export function PurchaseStagePanel({ state }: { state: PurchasePhaseState }): JSX.Element {
  const meta = getPurchaseStageMeta(state);
  return (
    <div className={`h5-member-task-stage-panel h5-member-task-stage-panel-${meta.tone}`}>
      <div className="h5-member-task-stage-head">
        <div className="h5-member-task-stage-copy">
          <strong>{meta.title}</strong>
          <span>{meta.detail}</span>
        </div>
        <span className={`h5-member-task-stage-badge h5-member-task-stage-badge-${meta.tone}`}>{meta.badge}</span>
      </div>
      <PurchaseFlow state={state} />
      <div className="h5-member-progress">
        <div
          className={`h5-member-progress-fill ${state.tone === "failed" ? "h5-member-progress-fill-failed" : ""}`}
          style={{ width: `${state.progress}%` }}
        />
      </div>
    </div>
  );
}

export function PullToRefresh({ onRefresh, children }: { onRefresh: () => Promise<void>; children: ReactNode }): JSX.Element {
  const [refreshing, setRefreshing] = useState(false);
  const [pullDistance, setPullDistance] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);
  const startY = useRef(0);
  const pulling = useRef(false);

  const getScrollHost = (): HTMLElement | null => {
    const container = containerRef.current;
    if (!container) return null;
    return container.closest(".h5-member-app-shell") as HTMLElement | null ?? container;
  };

  const handleTouchStart = (event: React.TouchEvent): void => {
    const scrollHost = getScrollHost();
    if (scrollHost && scrollHost.scrollTop <= 0) {
      startY.current = event.touches[0].clientY;
      pulling.current = true;
    }
  };

  const handleTouchMove = (event: React.TouchEvent): void => {
    if (!pulling.current || refreshing) return;
    const diff = event.touches[0].clientY - startY.current;
    if (diff > 0) {
      setPullDistance(Math.min(diff * 0.5, 80));
    }
  };

  const handleTouchEnd = async (): Promise<void> => {
    if (pulling.current && pullDistance > 50 && !refreshing) {
      setRefreshing(true);
      setPullDistance(40);
      try {
        await onRefresh();
      } catch {
        // Ignore refresh errors so the shell can recover on the next pull.
      }
      setRefreshing(false);
      setPullDistance(0);
    } else {
      setPullDistance(0);
    }
    pulling.current = false;
  };

  return (
    <div
      className="h5-pull-shell"
      ref={containerRef}
      onTouchEnd={() => void handleTouchEnd()}
      onTouchMove={handleTouchMove}
      onTouchStart={handleTouchStart}
    >
      {pullDistance > 0 ? (
        <div
          className={`h5-pull-indicator ${refreshing ? "h5-pull-indicator-refreshing" : ""}`}
          style={{ height: pullDistance }}
        >
          {refreshing ? (
            <><LoadingOutlined className="h5-pull-indicator-icon" />{t("common.loading")}</>
          ) : pullDistance > 50 ? (
            t("common.releaseToRefresh")
          ) : (
            t("common.pullToRefresh")
          )}
        </div>
      ) : null}
      {children}
    </div>
  );
}

export function InfiniteScroll({
  hasMore,
  loading,
  onLoadMore,
  children,
}: {
  hasMore: boolean;
  loading: boolean;
  onLoadMore: () => void;
  children: ReactNode;
}): JSX.Element {
  const sentinelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!hasMore || loading) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && hasMore && !loading) {
          onLoadMore();
        }
      },
      { threshold: 0.1 },
    );

    const sentinel = sentinelRef.current;
    if (sentinel) {
      observer.observe(sentinel);
    }

    return () => {
      if (sentinel) {
        observer.unobserve(sentinel);
      }
    };
  }, [hasMore, loading, onLoadMore]);

  return (
    <>
      {children}
      <div className="h5-infinite-scroll-sentinel" ref={sentinelRef} />
      {loading ? (
        <div className="h5-infinite-scroll-loading">
          <LoadingOutlined className="h5-infinite-scroll-loading-icon" />{t("common.loading")}
        </div>
      ) : null}
      {!hasMore && !loading ? (
        <div className="h5-infinite-scroll-end muted">
          {t("common.noMore")}
        </div>
      ) : null}
    </>
  );
}
