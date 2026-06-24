import { useCallback, useMemo, useState, type JSX } from "react";
import { BellOutlined, CloseOutlined, CustomerServiceOutlined, ProfileOutlined } from "@ant-design/icons";

import { t } from "./i18n";
import { ListSkeleton } from "./skeletons";
import type { H5MessageItem } from "../../services/h5Member";
import {
  buildMessageGroups,
  getMessageCategoryLabel,
  getCurrentLocale,
  isImportantMessage,
} from "./sharedUtils";
import { EmptyStateCard, InfiniteScroll, MessageFeedItem, PullToRefresh, QuickActionCard, SectionHeader } from "./sharedComponents";

type MessagesPageProps = {
  messages: H5MessageItem[];
  unreadMessageCount: number;
  actionName: string | null;
  siteKey: string;
  loading: boolean;
  error: string | null;
  currentPage: number;
  totalMessages: number;
  onMarkAllRead: () => Promise<void>;
  onOpenMessage: (messageId: string) => Promise<void>;
  onNavigate: (path: string) => void;
  onPageChange: (page: number) => void;
  onRetry: () => void;
};

function formatRelativeTime(value: string | null): string {
  if (!value) return "";
  const now = Date.now();
  const then = new Date(value).getTime();
  const diffMs = now - then;
  if (diffMs < 0) return t("messages.justNow");

  const seconds = Math.floor(diffMs / 1000);
  if (seconds < 60) return t("messages.justNow");

  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return t("messages.minutesAgo", { count: minutes });

  const hours = Math.floor(minutes / 60);
  if (hours < 24) return t("messages.hoursAgo", { count: hours });

  const days = Math.floor(hours / 24);
  if (days < 30) return t("messages.daysAgo", { count: days });

  return new Intl.DateTimeFormat(getCurrentLocale(), {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date(value));
}

function getMessageCategoryToneClass(category: H5MessageItem["category"]): string {
  return `h5-member-msg-detail-category-${category}`;
}

function MessageDetailOverlay({
  item,
  onClose,
}: {
  item: H5MessageItem;
  onClose: () => void;
}): JSX.Element {
  const stopTouchPropagation = (event: React.TouchEvent<HTMLDivElement>): void => {
    event.stopPropagation();
  };

  return (
    <div
      className="h5-member-msg-detail-overlay"
      onClick={onClose}
      onTouchEnd={stopTouchPropagation}
      onTouchMove={stopTouchPropagation}
      onTouchStart={stopTouchPropagation}
    >
      <div
        className="h5-member-msg-detail-panel"
        onClick={(e) => e.stopPropagation()}
        onTouchEnd={stopTouchPropagation}
        onTouchMove={stopTouchPropagation}
        onTouchStart={stopTouchPropagation}
      >
        <div className="h5-member-msg-detail-head">
          <span
            className={`h5-member-msg-detail-category ${getMessageCategoryToneClass(item.category)}`}
          >
            {getMessageCategoryLabel(item.category)}
          </span>
          <button className="h5-member-msg-detail-close" onClick={onClose} type="button">
            <CloseOutlined />
          </button>
        </div>
        <h3 className="h5-member-msg-detail-title">{item.title}</h3>
        <p className="h5-member-msg-detail-body">{item.body}</p>
        <span className="h5-member-msg-detail-time">{formatRelativeTime(item.createdAt)}</span>
      </div>
    </div>
  );
}

export function MessagesPage({
  messages,
  unreadMessageCount,
  loading,
  error,
  currentPage,
  totalMessages,
  onOpenMessage,
  onNavigate,
  onPageChange,
  onRetry,
}: MessagesPageProps): JSX.Element {
  const [detailMessage, setDetailMessage] = useState<H5MessageItem | null>(null);
  const unreadInFeed = useMemo(() => messages.filter((item) => !item.isRead).length, [messages]);
  const importantMessages = useMemo(() => messages.filter((item) => isImportantMessage(item)), [messages]);
  const priorityUnreadCount = useMemo(
    () => importantMessages.filter((item) => !item.isRead).length,
    [importantMessages],
  );
  const readCount = Math.max(0, messages.length - unreadInFeed);
  const nextStepLabel = unreadMessageCount > 0 ? t("messages.overviewNextStepUnread") : t("messages.overviewNextStepClear");

  const messageSections = useMemo(() => {
    const important = importantMessages;
    const other = messages.filter((item) => !isImportantMessage(item));

    return [
      {
        key: "important",
        title: t("messages.importantNotice"),
        description:
          important.length > 0
            ? t("messages.priorityCount", { count: important.filter((item) => !item.isRead).length })
            : t("messages.importantEmpty"),
        emptyTitle: t("messages.noImportantTitle"),
        emptyDescription: t("messages.importantEmpty"),
        emptyAction: (
          <button className="seed-button seed-button-secondary" onClick={() => onNavigate("/h5/tasks")} type="button">
            {t("messages.viewTaskCenter")}
          </button>
        ),
        groups: buildMessageGroups(important),
      },
      {
        key: "other",
        title: t("messages.otherMessages"),
        description: other.length > 0 ? t("messages.otherCount", { count: other.length }) : t("messages.otherEmpty"),
        emptyTitle: t("messages.noOtherTitle"),
        emptyDescription: t("messages.otherEmpty"),
        emptyAction: (
          <button className="seed-button seed-button-secondary" onClick={() => onNavigate("/h5/home")} type="button">
            {t("messages.goHome")}
          </button>
        ),
        groups: buildMessageGroups(other),
      },
    ];
  }, [importantMessages, messages, onNavigate]);

  const handleItemClick = useCallback(
    async (item: H5MessageItem) => {
      setDetailMessage(item);
      if (!item.isRead) {
        await onOpenMessage(item.id);
      }
    },
    [onOpenMessage],
  );

  if (loading && messages.length === 0) {
    return <ListSkeleton count={5} />;
  }

  if (error && messages.length === 0) {
    return (
      <section className="h5-card-stack">
        <article className="h5-card">
          <SectionHeader title={t("messages.messageCenter")} />
          <div className="h5-card-stack h5-member-msg-list">
            <div className="h5-member-msg-empty">
              <BellOutlined />
              <p>{error}</p>
              <button className="seed-button seed-button-secondary" onClick={onRetry} type="button">
                {t("messages.retry")}
              </button>
            </div>
          </div>
        </article>
      </section>
    );
  }

  const totalPages = Math.max(1, Math.ceil(totalMessages / 50));

  return (
    <PullToRefresh onRefresh={async () => onPageChange(1)}>
      <section className="h5-card-stack">
        <article className="h5-card h5-member-message-overview-card">
          <SectionHeader title={t("messages.overviewTitle")} meta={t("messages.overviewMeta")} />

          <div className="h5-member-message-overview-grid">
            <div className="h5-member-message-overview-metric">
              <span>{t("messages.overviewUnreadLabel")}</span>
              <strong>{unreadMessageCount}</strong>
            </div>
            <div className="h5-member-message-overview-metric">
              <span>{t("messages.overviewPriorityLabel")}</span>
              <strong>{priorityUnreadCount}</strong>
            </div>
            <div className="h5-member-message-overview-metric">
              <span>{t("messages.overviewReadLabel")}</span>
              <strong>{readCount}</strong>
            </div>
            <div className="h5-member-message-overview-metric">
              <span>{t("messages.overviewNextStepLabel")}</span>
              <strong>{nextStepLabel}</strong>
            </div>
          </div>

          <div className="h5-member-quick-grid">
            <QuickActionCard
              title={t("messages.taskShortcutTitle")}
              body={t("messages.taskShortcutBody")}
              icon={<ProfileOutlined />}
              meta={t("messages.taskShortcutMeta")}
              onClick={() => onNavigate("/h5/tasks")}
            />
            <QuickActionCard
              title={t("messages.supportShortcutTitle")}
              body={t("messages.supportShortcutBody")}
              icon={<CustomerServiceOutlined />}
              meta={t("messages.supportShortcutMeta")}
              onClick={() => onNavigate("/h5/tickets/new")}
            />
          </div>
        </article>

        <article className="h5-card">
          <SectionHeader
            title={t("messages.messageCenter")}
            meta={t("messages.unread", { count: unreadMessageCount })}
          />

          <div className="h5-card-stack h5-member-msg-list">
            {messageSections.map((section) => (
              <section className="h5-member-msg-section" key={section.key}>
                <SectionHeader title={section.title} meta={section.description} />
                {section.groups.length > 0 ? (
                  <div className="h5-card-stack">
                    {section.groups.map((group) => (
                      <section className="h5-member-msg-group" key={`${section.key}:${group.label}`}>
                        <div className="h5-member-msg-group-head">
                          <strong>{group.label}</strong>
                          <span>
                            {t("messages.groupCount", { count: group.items.length })}
                            {group.unreadCount > 0 ? t("messages.groupUnreadSuffix", { count: group.unreadCount }) : ""}
                          </span>
                        </div>
                        <div className="h5-card-stack h5-member-msg-list">
                          {group.items.map((item) => (
                            <MessageFeedItem key={item.id} item={item} onClick={() => void handleItemClick(item)} />
                          ))}
                        </div>
                      </section>
                    ))}
                  </div>
                ) : (
                  <EmptyStateCard
                    action={section.emptyAction}
                    description={section.emptyDescription}
                    icon={<BellOutlined />}
                    title={section.emptyTitle}
                  />
                )}
              </section>
            ))}
          </div>

          <InfiniteScroll hasMore={currentPage < totalPages} loading={loading} onLoadMore={() => onPageChange(currentPage + 1)}>
            <div />
          </InfiniteScroll>

          {error ? <p className="h5-member-error-note">{error}</p> : null}
        </article>
      </section>

      {detailMessage ? <MessageDetailOverlay item={detailMessage} onClose={() => setDetailMessage(null)} /> : null}
    </PullToRefresh>
  );
}
