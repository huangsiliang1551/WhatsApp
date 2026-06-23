import { type JSX, type FormEvent } from "react";
import { AuditOutlined } from "@ant-design/icons";

import { t } from "./i18n";
import { ListSkeleton } from "./skeletons";
import type { SupportTicket, SupportTicketCategory, SupportTicketDetail, SupportTicketPriority } from "../../services/h5";
import {
  formatTimestamp,
  getTicketPriorityLabels, getTicketCategoryLabels, getTicketStatusLabel,
  canReplyToTicket,
  TicketDraft,
} from "./sharedUtils";
import { CompactListRow, EmptyStateCard, SectionHeader } from "./sharedComponents";

type TicketsPageProps = {
  page: "list" | "new" | "detail";
  siteKey: string;
  tickets: SupportTicket[];
  ticketDetail: SupportTicketDetail | null;
  ticketDraft: TicketDraft;
  ticketReply: string;
  actionName: string | null;
  loading: boolean;
  error: string | null;
  onNavigate: (path: string) => void;
  onCreateTicket: (event: FormEvent<HTMLFormElement>) => Promise<void>;
  onTicketDraftChange: (draft: TicketDraft) => void;
  onTicketReplyChange: (value: string) => void;
  onReplyToTicket: (event: FormEvent<HTMLFormElement>) => Promise<void>;
  onRetry: () => void;
};

export function TicketsPage({
  page,
  siteKey,
  tickets,
  ticketDetail,
  ticketDraft,
  ticketReply,
  actionName,
  loading,
  error,
  onNavigate,
  onCreateTicket,
  onTicketDraftChange,
  onTicketReplyChange,
  onReplyToTicket,
  onRetry,
}: TicketsPageProps): JSX.Element {
  const ticketPriorityLabels = getTicketPriorityLabels();
  const ticketCategoryLabels = getTicketCategoryLabels();
  const canSubmitNewTicket = ticketDraft.subject.trim().length > 0 && ticketDraft.description.trim().length > 0;
  const canSubmitReply = ticketReply.trim().length > 0;

  if (page === "new") {
    return (
      <section className="h5-card-stack">
        <article className="h5-card h5-member-ticket-summary-card">
          <SectionHeader meta={t("tickets.ticketType")} title={t("tickets.newTicket")} />
          <p className="h5-member-ticket-summary-copy">{t("tickets.ticketListDesc")}</p>
          <div className="h5-member-ticket-meta-row">
            <span className="h5-member-inline-pill">{t("tickets.helpTicket")}</span>
            <span className="h5-member-inline-pill">{t("tickets.complaint")}</span>
            <span className="h5-member-inline-pill">{t("tickets.taskAppeal")}</span>
          </div>
        </article>

        <form className="h5-card h5-form h5-member-ticket-reply-card" onSubmit={(event) => void onCreateTicket(event)}>
          <SectionHeader title={t("tickets.submitTicket")} />
          <label>
            {t("tickets.ticketType")}
            <select value={ticketDraft.category} onChange={(event) => onTicketDraftChange({ ...ticketDraft, category: event.target.value as SupportTicketCategory })}>
              <option value="help">{t("tickets.helpTicket")}</option>
              <option value="task_appeal">{t("tickets.taskAppeal")}</option>
              <option value="complaint">{t("tickets.complaint")}</option>
            </select>
          </label>
          <label>
            {t("tickets.priority")}
            <select value={ticketDraft.priority} onChange={(event) => onTicketDraftChange({ ...ticketDraft, priority: event.target.value as SupportTicketPriority })}>
              <option value="low">{t("tickets.priorityLow")}</option>
              <option value="normal">{t("tickets.priorityNormal")}</option>
              <option value="high">{t("tickets.priorityHigh")}</option>
              <option value="urgent">{t("tickets.priorityUrgent")}</option>
            </select>
          </label>
          <label>
            {t("tickets.subject")}
            <input value={ticketDraft.subject} onChange={(event) => onTicketDraftChange({ ...ticketDraft, subject: event.target.value })} placeholder={t("tickets.subjectPlaceholder")} />
          </label>
          <label>
            {t("tickets.description")}
            <textarea
              rows={5}
              value={ticketDraft.description}
              onChange={(event) => onTicketDraftChange({ ...ticketDraft, description: event.target.value })}
              placeholder={t("tickets.descriptionPlaceholder")}
            />
          </label>
          <button className="h5-primary-button" disabled={actionName === "ticket-create" || !canSubmitNewTicket} type="submit">
            {actionName === "ticket-create" ? t("tickets.submitting") : t("tickets.submitTicket")}
          </button>
        </form>
      </section>
    );
  }

  if (page === "detail" && ticketDetail) {
    // Track ticket status for display
    const statusLabel = getTicketStatusLabel(ticketDetail.status);
    const isClosed = ticketDetail.status === "closed" || ticketDetail.status === "resolved" || ticketDetail.status === "rejected";

    return (
      <section className="h5-card-stack">
        <article className="h5-card h5-member-ticket-summary-card">
          <div className="h5-card-header">
            <strong>{ticketDetail.subject}</strong>
            <span className={`badge ${isClosed ? "badge-success" : "badge-mode"}`}>{statusLabel}</span>
          </div>
          <p className="h5-member-ticket-summary-copy">{ticketDetail.description}</p>
          <div className="h5-member-ticket-meta-row">
            <span className="h5-member-inline-pill">{t("tickets.ticketId", { id: ticketDetail.id })}</span>
            <span className="h5-member-inline-pill">{ticketCategoryLabels[ticketDetail.category]}</span>
            <span className="h5-member-inline-pill">{ticketPriorityLabels[ticketDetail.priority]}</span>
            <span className="h5-member-inline-pill">{formatTimestamp(ticketDetail.created_at)}</span>
          </div>
        </article>

        <article className="h5-card">
          <SectionHeader meta={t("tickets.messageCount", { count: ticketDetail.messages.filter((message) => !message.internal_only).length })} title={t("tickets.ticketMessages")} />
          <div className="ticket-thread h5-member-ticket-thread">
            {ticketDetail.messages.filter((message) => !message.internal_only).map((message) => (
              <article className={`ticket-thread-message ${message.sender_type === "user" ? "h5-member-ticket-message-user" : message.sender_type === "agent" ? "h5-member-ticket-message-agent" : "h5-member-ticket-message-system"}`} key={message.id}>
                <div className="ticket-thread-header">
                  <strong>{message.sender_name}</strong>
                  <span className="badge badge-neutral">{message.sender_type === "user" ? t("tickets.user") : message.sender_type === "agent" ? t("tickets.agent") : t("tickets.system")}</span>
                </div>
                <p>{message.content}</p>
                <p className="muted h5-member-ticket-message-time">{formatTimestamp(message.created_at)}</p>
              </article>
            ))}
          </div>
        </article>

        {canReplyToTicket(ticketDetail.status) ? (
          <form className="h5-card h5-form h5-member-ticket-reply-card" onSubmit={(event) => void onReplyToTicket(event)}>
            <label>
              {t("tickets.replyLabel")}
              <textarea rows={4} value={ticketReply} onChange={(event) => onTicketReplyChange(event.target.value)} placeholder={t("tickets.replyPlaceholder")} />
            </label>
            <button className="h5-primary-button" disabled={actionName === "ticket-reply" || !canSubmitReply} type="submit">
              {actionName === "ticket-reply" ? t("tickets.sending") : t("tickets.reply")}
            </button>
          </form>
        ) : (
          <article className="h5-card">
            <p className="muted">{t("tickets.closedHint")}</p>
          </article>
        )}
      </section>
    );
  }

  if (loading && tickets.length === 0) {
    return <ListSkeleton count={4} />;
  }

  if (error && tickets.length === 0) {
    return (
      <section className="h5-card-stack">
        <article className="h5-card">
          <SectionHeader meta={t("tickets.messageCount", { count: 0 })} title={t("tickets.title")} />
          <p className="muted">{t("common.errorTitle")}: {error}</p>
          <div className="h5-card-stack h5-member-ticket-retry">
            <button className="h5-secondary-button" onClick={onRetry} type="button">
              {t("common.retry")}
            </button>
          </div>
        </article>
      </section>
    );
  }

  return (
    <section className="h5-card-stack">
      <article className="h5-card">
        <SectionHeader
          meta={t("tickets.messageCount", { count: tickets.length })}
          title={t("tickets.title")}
          action={
            <button className="seed-button seed-button-secondary" onClick={() => onNavigate("/h5/tickets/new")} type="button">
              {t("tickets.newTicket")}
            </button>
          }
        />
        <p className="muted">{t("tickets.ticketListDesc")}</p>
      </article>
      {tickets.length > 0 ? (
        tickets.map((ticket) => {
          const isResolvedClosed = ticket.status === "resolved" || ticket.status === "closed";
          return (
            <article className="h5-card" key={ticket.id}>
              <CompactListRow
                actionLabel={t("tickets.viewDetail")}
                badge={getTicketStatusLabel(ticket.status)}
                meta={formatTimestamp(ticket.last_reply_at ?? ticket.updated_at)}
                onClick={() => onNavigate(`/h5/tickets/${ticket.id}`)}
                sideNote={ticketPriorityLabels[ticket.priority]}
                subtitle={ticket.content_preview || ticketCategoryLabels[ticket.category]}
                title={ticket.subject}
                tone={isResolvedClosed ? "success" : ticket.status === "rejected" ? "danger" : "active"}
                value={ticketCategoryLabels[ticket.category]}
              />
            </article>
          );
        })
      ) : (
        <EmptyStateCard
          action={
            <button className="h5-secondary-button" onClick={() => onNavigate("/h5/tickets/new")} type="button">
              {t("tickets.newTicket")}
            </button>
          }
          description={t("tickets.noTicketsDesc")}
          icon={<AuditOutlined />}
          title={t("tickets.noTickets")}
        />
      )}
    </section>
  );
}
