import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { t } from "./i18n";

const storage = new Map<string, string>();

function installLocalStorageMock(): void {
  Object.defineProperty(window, "localStorage", {
    configurable: true,
    value: {
      getItem(key: string): string | null {
        return storage.get(key) ?? null;
      },
      setItem(key: string, value: string): void {
        storage.set(key, value);
      },
      removeItem(key: string): void {
        storage.delete(key);
      },
      clear(): void {
        storage.clear();
      },
    },
  });
}

type TicketsPageProps = React.ComponentProps<typeof import("./TicketsPage").TicketsPage>;

async function renderTicketsPage(
  overrides: Partial<TicketsPageProps> = {},
): Promise<{
  props: TicketsPageProps;
}> {
  const { TicketsPage } = await import("./TicketsPage");
  const props: TicketsPageProps = {
    page: "list",
    siteKey: "mall-us",
    tickets: [],
    ticketDetail: null,
    ticketDraft: {
      category: "help",
      priority: "normal",
      subject: "",
      description: "",
    },
    ticketReply: "",
    actionName: null,
    loading: false,
    error: null,
    onNavigate: vi.fn(),
    onCreateTicket: vi.fn().mockResolvedValue(undefined),
    onTicketDraftChange: vi.fn(),
    onTicketReplyChange: vi.fn(),
    onReplyToTicket: vi.fn().mockResolvedValue(undefined),
    onRetry: vi.fn(),
    ...overrides,
  };

  render(<TicketsPage {...props} />);
  return { props };
}

describe("TicketsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    storage.clear();
    installLocalStorageMock();
    storage.set("h5-lang", "en-US");
  });

  afterEach(() => {
    vi.clearAllMocks();
    cleanup();
    storage.clear();
  });

  it("disables new-ticket submit until subject and description are both filled", async () => {
    await renderTicketsPage({
      page: "new",
      ticketDraft: {
        category: "help",
        priority: "normal",
        subject: "Need help",
        description: "",
      },
    });

    expect((screen.getByRole("button", { name: t("tickets.submitTicket") }) as HTMLButtonElement).disabled).toBe(true);

    cleanup();

    await renderTicketsPage({
      page: "new",
      ticketDraft: {
        category: "help",
        priority: "normal",
        subject: "Need help",
        description: "Withdrawal still pending after review window.",
      },
    });

    expect((screen.getByRole("button", { name: t("tickets.submitTicket") }) as HTMLButtonElement).disabled).toBe(false);
  });

  it("shows the submitting state for new-ticket creation", async () => {
    await renderTicketsPage({
      page: "new",
      ticketDraft: {
        category: "help",
        priority: "normal",
        subject: "Need help",
        description: "Withdrawal still pending after review window.",
      },
      actionName: "ticket-create",
    });

    expect((screen.getByRole("button", { name: t("tickets.submitting") }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("shows localized error UI instead of raw translation keys", async () => {
    await renderTicketsPage({
      page: "list",
      error: "Service temporarily unavailable",
    });

    expect(screen.getByText(/Error:/)).toBeTruthy();
    expect(screen.getByRole("button", { name: t("common.retry") })).toBeTruthy();
  });

  it("keeps a create-ticket action visible from the ticket list header", async () => {
    const onNavigate = vi.fn();

    await renderTicketsPage({
      page: "list",
      tickets: [
        {
          id: "101",
          account_id: "acc-1",
          public_user_id: "u-1",
          subject: "Withdrawal review taking longer than expected",
          status: "open",
          priority: "high",
          category: "help",
          content_preview: "Need help checking the current review queue.",
          source: "h5",
          linked_task_instance_id: null,
          created_at: "2026-06-23T09:00:00.000Z",
          updated_at: "2026-06-23T09:00:00.000Z",
          last_reply_at: "2026-06-23T10:00:00.000Z",
        },
      ] as never,
      onNavigate,
    });

    fireEvent.click(screen.getByRole("button", { name: t("tickets.newTicket") }));

    expect(onNavigate).toHaveBeenCalledWith("/h5/tickets/new");
  });

  it("surfaces a support overview summary before the ticket list", async () => {
    await renderTicketsPage({
      page: "list",
      tickets: [
        {
          id: "101",
          account_id: "acc-1",
          public_user_id: "u-1",
          subject: "Withdrawal review taking longer than expected",
          status: "open",
          priority: "high",
          category: "help",
          content_preview: "Need help checking the current review queue.",
          source: "h5",
          linked_task_instance_id: null,
          created_at: "2026-06-23T09:00:00.000Z",
          updated_at: "2026-06-23T09:00:00.000Z",
          last_reply_at: "2026-06-23T10:00:00.000Z",
        },
        {
          id: "102",
          account_id: "acc-1",
          public_user_id: "u-1",
          subject: "Task appeal waiting on review",
          status: "pending_user",
          priority: "normal",
          category: "task_appeal",
          content_preview: "Need to provide screenshot evidence.",
          source: "h5",
          linked_task_instance_id: null,
          created_at: "2026-06-22T09:00:00.000Z",
          updated_at: "2026-06-22T09:00:00.000Z",
          last_reply_at: "2026-06-22T10:00:00.000Z",
        },
      ] as never,
    });

    const overviewHeading = screen.getByText(t("tickets.overviewTitle"));
    const listHeading = screen.getByText(t("tickets.title"));
    const firstTicket = screen.getByText("Withdrawal review taking longer than expected");

    expect(overviewHeading.compareDocumentPosition(listHeading)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
    expect(listHeading.compareDocumentPosition(firstTicket)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
    expect(screen.getAllByText(t("tickets.openCount")).length).toBeGreaterThan(0);
    expect(screen.getByText(t("tickets.waitingCount"))).toBeTruthy();
    expect(screen.getByText(t("tickets.resolvedCount"))).toBeTruthy();
  });

  it("renders a submission checklist before the new-ticket form", async () => {
    await renderTicketsPage({
      page: "new",
      ticketDraft: {
        category: "help",
        priority: "normal",
        subject: "",
        description: "",
      },
    });

    const prepHeading = screen.getByText(t("tickets.prepTitle"));
    const submitHeading = screen.getAllByText(t("tickets.submitTicket"))[0];

    expect(prepHeading.compareDocumentPosition(submitHeading)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
    expect(screen.getByText(t("tickets.prepSubjectTitle"))).toBeTruthy();
    expect(screen.getByText(t("tickets.prepContextTitle"))).toBeTruthy();
    expect(screen.getByText(t("tickets.prepResponseTitle"))).toBeTruthy();
  });

  it("treats resolved tickets as read-only and hides the reply composer", async () => {
    await renderTicketsPage({
      page: "detail",
      ticketDetail: {
        id: "tk-1",
        account_id: "acc-1",
        public_user_id: "u-1",
        category: "help",
        status: "resolved",
        priority: "normal",
        subject: "Withdrawal review completed",
        content_preview: "Resolved by support",
        source: "h5",
        linked_task_instance_id: null,
        created_at: "2026-06-22T09:00:00.000Z",
        updated_at: "2026-06-23T10:00:00.000Z",
        last_reply_at: "2026-06-23T10:00:00.000Z",
        description: "Support marked this ticket as resolved.",
        messages: [
          {
            id: "msg-1",
            sender_type: "agent",
            sender_name: "Support",
            content: "Issue resolved.",
            created_at: "2026-06-23T10:00:00.000Z",
            internal_only: false,
          },
        ],
      } as never,
    });

    expect(screen.getByText(t("tickets.statusResolved"))).toBeTruthy();
    expect(screen.getByText(t("tickets.closedHint"))).toBeTruthy();
    expect(screen.queryByRole("button", { name: t("tickets.reply") })).toBeNull();
  });

  it("keeps internal-only messages out of the visible ticket thread", async () => {
    await renderTicketsPage({
      page: "detail",
      ticketDetail: {
        id: "tk-2",
        account_id: "acc-1",
        public_user_id: "u-1",
        category: "complaint",
        status: "open",
        priority: "high",
        subject: "Complaint follow-up",
        content_preview: "Customer submitted more detail.",
        source: "h5",
        linked_task_instance_id: null,
        created_at: "2026-06-22T09:00:00.000Z",
        updated_at: "2026-06-23T10:00:00.000Z",
        last_reply_at: "2026-06-23T10:00:00.000Z",
        description: "Visible thread only.",
        messages: [
          {
            id: "msg-visible",
            sender_type: "user",
            sender_name: "Member",
            content: "Visible reply",
            created_at: "2026-06-23T10:00:00.000Z",
            internal_only: false,
          },
          {
            id: "msg-hidden",
            sender_type: "system",
            sender_name: "Internal note",
            content: "Do not show this message",
            created_at: "2026-06-23T10:05:00.000Z",
            internal_only: true,
          },
        ],
      } as never,
    });

    expect(screen.getByText("Visible reply")).toBeTruthy();
    expect(screen.queryByText("Do not show this message")).toBeNull();
    expect(screen.getByText(t("tickets.messageCount", { count: 1 }))).toBeTruthy();
  });

  it("disables reply submission until reply text is filled and shows sending state", async () => {
    await renderTicketsPage({
      page: "detail",
      ticketReply: "",
      ticketDetail: {
        id: "tk-3",
        account_id: "acc-1",
        public_user_id: "u-1",
        category: "help",
        status: "open",
        priority: "normal",
        subject: "Need more info",
        content_preview: "Awaiting user",
        source: "h5",
        linked_task_instance_id: null,
        created_at: "2026-06-22T09:00:00.000Z",
        updated_at: "2026-06-23T10:00:00.000Z",
        last_reply_at: "2026-06-23T10:00:00.000Z",
        description: "Support is waiting for the user.",
        messages: [],
      } as never,
    });

    expect((screen.getByRole("button", { name: t("tickets.reply") }) as HTMLButtonElement).disabled).toBe(true);

    cleanup();

    await renderTicketsPage({
      page: "detail",
      ticketReply: "Here is the missing order number.",
      actionName: "ticket-reply",
      ticketDetail: {
        id: "tk-3",
        account_id: "acc-1",
        public_user_id: "u-1",
        category: "help",
        status: "open",
        priority: "normal",
        subject: "Need more info",
        content_preview: "Awaiting user",
        source: "h5",
        linked_task_instance_id: null,
        created_at: "2026-06-22T09:00:00.000Z",
        updated_at: "2026-06-23T10:00:00.000Z",
        last_reply_at: "2026-06-23T10:00:00.000Z",
        description: "Support is waiting for the user.",
        messages: [],
      } as never,
    });

    expect((screen.getByRole("button", { name: t("tickets.sending") }) as HTMLButtonElement).disabled).toBe(true);
  });
});
