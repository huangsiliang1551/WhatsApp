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

type WhatsAppPageProps = React.ComponentProps<typeof import("./WhatsAppPage").WhatsAppPage>;

async function renderWhatsAppPage(
  overrides: Partial<WhatsAppPageProps> = {},
): Promise<{
  props: WhatsAppPageProps;
}> {
  const { WhatsAppPage } = await import("./WhatsAppPage");
  const props: WhatsAppPageProps = {
    whatsAppBinding: null,
    actionName: null,
    onStartBinding: vi.fn().mockResolvedValue(undefined),
    whatsappPhone: "",
    onWhatsappPhoneChange: vi.fn(),
    onStartWhatsAppBindingApi: vi.fn().mockResolvedValue(undefined),
    chatMessages: [],
    chatLoading: false,
    chatHasMore: false,
    onSendMessage: vi.fn().mockResolvedValue(undefined),
    onLoadMoreMessages: vi.fn().mockResolvedValue(undefined),
    onRefreshMessages: vi.fn().mockResolvedValue(undefined),
    onBack: vi.fn(),
    loading: false,
    ...overrides,
  };

  render(<WhatsAppPage {...props} />);
  return { props };
}

describe("WhatsAppPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useRealTimers();
    storage.clear();
    installLocalStorageMock();
    storage.set("h5-lang", "en-US");
  });

  afterEach(() => {
    vi.clearAllMocks();
    vi.useRealTimers();
    cleanup();
    storage.clear();
  });

  it("renders a fully localized binding form in english", async () => {
    await renderWhatsAppPage();

    expect(screen.getByText(/Bind WhatsApp/i)).toBeTruthy();
    expect(screen.getByPlaceholderText(/Example:/i)).toBeTruthy();
    expect(screen.getByRole("button", { name: /Submit Binding Request/i })).toBeTruthy();
    expect(screen.queryByText(t("whatsapp.legacyTitle"))).toBeNull();
    expect(screen.queryByText(/Legacy Mode/i)).toBeNull();
    expect(document.body.textContent?.toLowerCase()).not.toContain("prototype");
    expect(document.body.textContent?.toLowerCase()).not.toContain("temporary mode");
  });

  it("shows pending status and hides the resubmission form while a binding request is under review", async () => {
    await renderWhatsAppPage({
      whatsAppBinding: {
        isBound: false,
        bindingStatus: "pending",
        phoneNumber: "8613800138000",
        requestedAt: "2026-06-23T09:00:00.000Z",
        lastUpdatedAt: "2026-06-23T09:00:00.000Z",
      } as never,
    });

    expect(screen.getAllByText(t("whatsapp.pending")).length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: t("whatsapp.bindSubmit") })).toBeNull();
    expect(screen.queryByText(t("whatsapp.bindTitle"))).toBeNull();
  });

  it("validates the phone before submitting a binding request", async () => {
    const onStartWhatsAppBindingApi = vi.fn().mockResolvedValue(undefined);

    await renderWhatsAppPage({
      whatsappPhone: "123",
      onStartWhatsAppBindingApi,
    });

    fireEvent.submit(screen.getByRole("button", { name: t("whatsapp.bindSubmit") }).closest("form")!);

    expect(onStartWhatsAppBindingApi).not.toHaveBeenCalled();
    expect(screen.getByText(t("whatsapp.bindInvalidPhone"))).toBeTruthy();
  });

  it("surfaces a readiness checklist before the binding form for unbound accounts", async () => {
    await renderWhatsAppPage();

    const readinessHeading = screen.getByText(t("whatsapp.readinessTitle"));
    const bindHeading = screen.getByText(t("whatsapp.bindTitle"));

    expect(readinessHeading.compareDocumentPosition(bindHeading)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
    expect(screen.getByText(t("whatsapp.readinessPhoneTitle"))).toBeTruthy();
    expect(screen.getByText(t("whatsapp.readinessReviewTitle"))).toBeTruthy();
    expect(screen.getByText(t("whatsapp.readinessNotifyTitle"))).toBeTruthy();
  });

  it("surfaces binding api errors inline", async () => {
    const onStartWhatsAppBindingApi = vi.fn().mockRejectedValue(new Error("Binding service unavailable"));

    await renderWhatsAppPage({
      whatsappPhone: "8613800138000",
      onStartWhatsAppBindingApi,
    });

    fireEvent.submit(screen.getByRole("button", { name: t("whatsapp.bindSubmit") }).closest("form")!);

    expect(await screen.findByText("Binding service unavailable")).toBeTruthy();
  });

  it("keeps pending follow-up guidance visible while the binding request is under review", async () => {
    await renderWhatsAppPage({
      whatsAppBinding: {
        isBound: false,
        bindingStatus: "pending",
        phoneNumber: "8613800138000",
        requestedAt: "2026-06-23T09:00:00.000Z",
        lastUpdatedAt: "2026-06-23T09:00:00.000Z",
      } as never,
    });

    expect(screen.getByText(t("whatsapp.pendingChecklistTitle"))).toBeTruthy();
    expect(screen.getByText(t("whatsapp.pendingChecklistDesc"))).toBeTruthy();
  });

  it("refreshes chat automatically every five seconds in chat mode", async () => {
    vi.useFakeTimers();
    const onRefreshMessages = vi.fn().mockResolvedValue(undefined);

    await renderWhatsAppPage({
      whatsAppBinding: {
        isBound: true,
        phoneNumber: "8613800138000",
        lastUpdatedAt: "2026-06-23T09:00:00.000Z",
      } as never,
      chatMessages: [
        {
          id: "msg-1",
          content: "Hello",
          type: "text",
          direction: "inbound",
          status: "read",
          timestamp: "2026-06-23T09:00:00.000Z",
        },
      ] as never,
      onRefreshMessages,
    });

    await vi.advanceTimersByTimeAsync(5000);

    expect(onRefreshMessages).toHaveBeenCalledTimes(1);
  });

  it("uses dedicated classes for whatsapp summary state, chat status, and clickable image bubbles", async () => {
    const { WhatsAppPage } = await import("./WhatsAppPage");
    const summaryView = render(
      <WhatsAppPage
        whatsAppBinding={null}
        actionName={null}
        onStartBinding={vi.fn().mockResolvedValue(undefined)}
        whatsappPhone=""
        onWhatsappPhoneChange={vi.fn()}
        onStartWhatsAppBindingApi={vi.fn().mockResolvedValue(undefined)}
        chatMessages={[]}
        chatLoading={false}
        chatHasMore={false}
        onSendMessage={vi.fn().mockResolvedValue(undefined)}
        onLoadMoreMessages={vi.fn().mockResolvedValue(undefined)}
        onRefreshMessages={vi.fn().mockResolvedValue(undefined)}
        onBack={vi.fn()}
        loading={false}
      />,
    );

    const summaryIcon = summaryView.container.querySelector(".h5-member-whatsapp-summary-icon");

    expect(summaryIcon?.className).toContain("h5-member-whatsapp-summary-icon-unbound");
    expect(summaryIcon?.getAttribute("style")).toBeNull();

    summaryView.unmount();

    const chatView = render(
      <WhatsAppPage
        whatsAppBinding={{
          isBound: true,
          bindingStatus: "approved",
          phoneNumber: "8613800138000",
          lastUpdatedAt: "2026-06-23T09:00:00.000Z",
        } as never}
        actionName={null}
        onStartBinding={vi.fn().mockResolvedValue(undefined)}
        whatsappPhone=""
        onWhatsappPhoneChange={vi.fn()}
        onStartWhatsAppBindingApi={vi.fn().mockResolvedValue(undefined)}
        chatMessages={[
          {
            id: "msg-read",
            content: "Image sent",
            type: "image",
            image_url: "https://example.com/test.png",
            direction: "outbound",
            status: "read",
            timestamp: "2026-06-23T09:00:00.000Z",
          },
        ] as never}
        chatLoading={false}
        chatHasMore={false}
        onSendMessage={vi.fn().mockResolvedValue(undefined)}
        onLoadMoreMessages={vi.fn().mockResolvedValue(undefined)}
        onRefreshMessages={vi.fn().mockResolvedValue(undefined)}
        onBack={vi.fn()}
        loading={false}
      />,
    );

    const statusChecks = chatView.container.querySelector(".h5-chat-status-checks");
    const imageBubble = chatView.container.querySelector(".h5-chat-bubble-image");

    expect(statusChecks?.className).toContain("h5-chat-status-checks-read");
    expect(statusChecks?.getAttribute("style")).toBeNull();
    expect(imageBubble?.className).toContain("h5-chat-bubble-image-button");
    expect(imageBubble?.getAttribute("style")).toBeNull();
  });

  it("passes a local preview url when selecting an image in chat mode", async () => {
    const onSendMessage = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(URL, "createObjectURL", {
      configurable: true,
      value: vi.fn(() => "blob:chat-preview-1"),
    });
    const createObjectUrlSpy = vi.mocked(URL.createObjectURL);
    const { WhatsAppPage } = await import("./WhatsAppPage");

    const { container } = render(
      <WhatsAppPage
        whatsAppBinding={{
          isBound: true,
          bindingStatus: "approved",
          phoneNumber: "8613800138000",
          lastUpdatedAt: "2026-06-23T09:00:00.000Z",
        } as never}
        actionName={null}
        onStartBinding={vi.fn().mockResolvedValue(undefined)}
        whatsappPhone=""
        onWhatsappPhoneChange={vi.fn()}
        onStartWhatsAppBindingApi={vi.fn().mockResolvedValue(undefined)}
        chatMessages={[]}
        chatLoading={false}
        chatHasMore={false}
        onSendMessage={onSendMessage}
        onLoadMoreMessages={vi.fn().mockResolvedValue(undefined)}
        onRefreshMessages={vi.fn().mockResolvedValue(undefined)}
        onBack={vi.fn()}
        loading={false}
      />,
    );

    const fileInput = container.querySelector(".h5-chat-file-input") as HTMLInputElement | null;
    expect(fileInput).toBeTruthy();

    fireEvent.change(fileInput!, {
      target: {
        files: [new File(["image"], "chat-photo.png", { type: "image/png" })],
      },
    });

    expect(createObjectUrlSpy).toHaveBeenCalledTimes(1);
    expect(onSendMessage).toHaveBeenCalledWith(t("chat.image"), "image", "blob:chat-preview-1");
  });
});
