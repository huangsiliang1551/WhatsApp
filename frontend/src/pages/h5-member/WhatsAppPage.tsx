import { type ChangeEvent, type FormEvent, type JSX, type KeyboardEvent, useCallback, useEffect, useRef, useState } from "react";
import {
  ArrowLeftOutlined,
  CheckOutlined,
  CloseCircleOutlined,
  LoadingOutlined,
  PictureOutlined,
  SendOutlined,
  WhatsAppOutlined,
} from "@ant-design/icons";

import type { H5ChatMessage, H5WhatsAppBinding } from "../../services/h5Member";
import { formatTimestamp, getCurrentLocale } from "./sharedUtils";
import { DetailGrid, SectionHeader } from "./sharedComponents";
import { t } from "./i18n";
import { ImageViewer } from "./ImageViewer";
import { ProfileSkeleton } from "./skeletons";

type WhatsAppPageProps = {
  whatsAppBinding: H5WhatsAppBinding | null;
  actionName: string | null;
  onStartBinding: () => Promise<void>;
  whatsappPhone: string;
  onWhatsappPhoneChange: (value: string) => void;
  onStartWhatsAppBindingApi: () => Promise<void>;
  chatMessages: H5ChatMessage[];
  chatLoading: boolean;
  chatHasMore: boolean;
  onSendMessage: (content: string, type?: string) => Promise<void>;
  onLoadMoreMessages: () => Promise<void>;
  onRefreshMessages: () => Promise<void>;
  onBack?: () => void;
  loading?: boolean;
};

function isPendingBindingStatus(status: string | null | undefined): boolean {
  const normalized = status?.trim().toLowerCase();
  return normalized === "pending"
    || normalized === "requested"
    || normalized === "reviewing"
    || normalized === "processing"
    || normalized === "submitted";
}

function formatChatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString(getCurrentLocale(), {
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "";
  }
}

function ChatStatusIcon({ status }: { status: H5ChatMessage["status"] }): JSX.Element | null {
  if (status === "sending") {
    return <LoadingOutlined style={{ fontSize: 12, color: "#94a3b8" }} />;
  }

  if (status === "sent") {
    return <CheckOutlined style={{ fontSize: 12, color: "#94a3b8" }} />;
  }

  if (status === "delivered") {
    return (
      <span className="h5-chat-status-checks" style={{ color: "#94a3b8" }}>
        <CheckOutlined />
        <CheckOutlined />
      </span>
    );
  }

  if (status === "read") {
    return (
      <span className="h5-chat-status-checks" style={{ color: "#53bdeb" }}>
        <CheckOutlined />
        <CheckOutlined />
      </span>
    );
  }

  return null;
}

export function WhatsAppPage({
  whatsAppBinding,
  actionName,
  whatsappPhone,
  onWhatsappPhoneChange,
  onStartWhatsAppBindingApi,
  chatMessages,
  chatLoading,
  chatHasMore,
  onSendMessage,
  onLoadMoreMessages,
  onRefreshMessages,
  onBack,
  loading = false,
}: WhatsAppPageProps): JSX.Element {
  const [phoneError, setPhoneError] = useState<string | null>(null);
  const [apiError, setApiError] = useState<string | null>(null);
  const [apiLoading, setApiLoading] = useState(false);
  const [inputValue, setInputValue] = useState("");
  const [sending, setSending] = useState(false);
  const [imageViewerUrl, setImageViewerUrl] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const isBound = whatsAppBinding?.isBound ?? false;
  const isPendingBinding = !isBound && isPendingBindingStatus(whatsAppBinding?.bindingStatus);
  const isApiAction = actionName === "whatsapp-api";
  const bindingStatusLabel = isBound
    ? t("whatsapp.boundStatus")
    : isPendingBinding
      ? t("whatsapp.pending")
      : t("whatsapp.notBound");

  const scrollToBottom = useCallback((smooth = true) => {
    if (messagesEndRef.current && typeof messagesEndRef.current.scrollIntoView === "function") {
      messagesEndRef.current.scrollIntoView({ behavior: smooth ? "smooth" : "auto" });
    }
  }, []);

  useEffect(() => {
    if (chatMessages.length > 0) {
      scrollToBottom(true);
    }
  }, [chatMessages.length, scrollToBottom]);

  useEffect(() => {
    const isChatMode = isBound || chatMessages.length > 0;
    if (!isChatMode) {
      return;
    }

    const timer = window.setInterval(() => {
      void onRefreshMessages();
    }, 5000);

    return () => window.clearInterval(timer);
  }, [chatMessages.length, isBound, onRefreshMessages]);

  const handleScroll = useCallback(() => {
    const container = messagesContainerRef.current;
    if (!container || chatLoading || !chatHasMore) {
      return;
    }

    if (container.scrollTop < 50) {
      const previousHeight = container.scrollHeight;
      void onLoadMoreMessages().then(() => {
        requestAnimationFrame(() => {
          if (messagesContainerRef.current) {
            messagesContainerRef.current.scrollTop = messagesContainerRef.current.scrollHeight - previousHeight;
          }
        });
      });
    }
  }, [chatHasMore, chatLoading, onLoadMoreMessages]);

  const handleSend = useCallback(async () => {
    const text = inputValue.trim();
    if (!text || sending) {
      return;
    }

    setSending(true);
    setInputValue("");
    try {
      await onSendMessage(text);
    } finally {
      setSending(false);
      if (inputRef.current) {
        inputRef.current.style.height = "auto";
      }
    }
  }, [inputValue, onSendMessage, sending]);

  const handleKeyDown = useCallback(
    (event: KeyboardEvent<HTMLTextAreaElement>) => {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        void handleSend();
      }
    },
    [handleSend],
  );

  const handleInputChange = useCallback((event: ChangeEvent<HTMLTextAreaElement>) => {
    setInputValue(event.target.value);
    const target = event.target;
    target.style.height = "auto";
    target.style.height = `${Math.min(target.scrollHeight, 120)}px`;
  }, []);

  const handleImageSelect = useCallback(
    async (event: ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0];
      if (!file || !file.type.startsWith("image/")) {
        return;
      }

      setSending(true);
      try {
        await onSendMessage(t("chat.image"), "image");
      } finally {
        setSending(false);
        if (fileInputRef.current) {
          fileInputRef.current.value = "";
        }
      }
    },
    [onSendMessage],
  );

  const validatePhone = useCallback((value: string): boolean => {
    const digitsOnly = value.replace(/\D/g, "");
    if (digitsOnly.length < 7) {
      setPhoneError(t("whatsapp.bindInvalidPhone"));
      return false;
    }
    setPhoneError(null);
    return true;
  }, []);

  const handlePhoneChange = useCallback(
    (value: string) => {
      onWhatsappPhoneChange(value);
      if (value) {
        validatePhone(value);
      } else {
        setPhoneError(null);
      }
      setApiError(null);
    },
    [onWhatsappPhoneChange, validatePhone],
  );

  const handleSubmit = useCallback(
    async (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      if (!validatePhone(whatsappPhone)) {
        return;
      }

      setApiError(null);
      setApiLoading(true);
      try {
        await onStartWhatsAppBindingApi();
      } catch (error) {
        setApiError(error instanceof Error ? error.message : t("common.failed"));
      } finally {
        setApiLoading(false);
      }
    },
    [onStartWhatsAppBindingApi, validatePhone, whatsappPhone],
  );

  const renderMessage = useCallback((message: H5ChatMessage) => {
    const isInbound = message.direction === "inbound";
    const isSystem = message.type === "system";
    const isImage = message.type === "image";

    if (isSystem) {
      return (
        <div className="h5-chat-bubble-system" key={message.id}>
          <span>{message.content}</span>
          <span className="h5-chat-bubble-time">{formatChatTime(message.timestamp)}</span>
        </div>
      );
    }

    return (
      <div className={`h5-chat-bubble ${isInbound ? "h5-chat-bubble-inbound" : "h5-chat-bubble-outbound"}`} key={message.id}>
        {isImage && message.image_url ? (
          <div
            className="h5-chat-bubble-image"
            onClick={() => setImageViewerUrl(message.image_url ?? null)}
            style={{ cursor: "pointer" }}
          >
            <img alt={t("chat.image")} src={message.image_url} />
          </div>
        ) : (
          <div className="h5-chat-bubble-text">{message.content}</div>
        )}
        <div className="h5-chat-bubble-footer">
          <span className="h5-chat-bubble-time">{formatChatTime(message.timestamp)}</span>
          {!isInbound ? (
            <span className="h5-chat-status">
              <ChatStatusIcon status={message.status} />
            </span>
          ) : null}
        </div>
      </div>
    );
  }, []);

  if (loading) {
    return <ProfileSkeleton />;
  }

  if (isBound || chatMessages.length > 0) {
    return (
      <div className="h5-chat-container">
        <div className="h5-chat-header">
          <button className="h5-subpage-back" onClick={onBack} type="button">
            <ArrowLeftOutlined />
          </button>
          <div className="h5-chat-header-info">
            <strong>{t("chat.title")}</strong>
            <span>
              <WhatsAppOutlined style={{ color: "#25D366", marginRight: 4 }} />
              {whatsAppBinding?.phoneNumber ?? ""}
            </span>
          </div>
        </div>

        <div className="h5-chat-messages" onScroll={handleScroll} ref={messagesContainerRef}>
          {chatLoading && chatMessages.length === 0 ? (
            <div className="h5-chat-loading">
              <LoadingOutlined style={{ marginRight: 6 }} />
              {t("chat.loading")}
            </div>
          ) : null}
          {chatLoading && chatMessages.length > 0 ? (
            <div className="h5-chat-loading">
              <LoadingOutlined />
            </div>
          ) : null}
          {!chatLoading && chatMessages.length === 0 ? <div className="h5-chat-empty">{t("chat.noMessages")}</div> : null}
          {chatMessages.map(renderMessage)}
          <div ref={messagesEndRef} />
        </div>

        <div className="h5-chat-input-area">
          <button
            className="h5-chat-image-btn"
            disabled={sending}
            onClick={() => fileInputRef.current?.click()}
            type="button"
          >
            <PictureOutlined />
          </button>
          <input accept="image/*" onChange={handleImageSelect} ref={fileInputRef} style={{ display: "none" }} type="file" />
          <textarea
            className="h5-chat-input"
            disabled={sending}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            placeholder={t("chat.inputPlaceholder")}
            ref={inputRef}
            rows={1}
            value={inputValue}
          />
          <button className="h5-chat-send-btn" disabled={!inputValue.trim() || sending} onClick={() => void handleSend()} type="button">
            {sending ? <LoadingOutlined /> : <SendOutlined />}
          </button>
        </div>

        {imageViewerUrl ? <ImageViewer images={[imageViewerUrl]} onClose={() => setImageViewerUrl(null)} /> : null}
      </div>
    );
  }

  return (
    <section className="h5-card-stack">
      <article className="h5-card h5-member-whatsapp-summary-card">
        <div className="h5-member-whatsapp-summary-icon" style={{ color: isBound ? "#25D366" : "#94a3b8" }}>
          <WhatsAppOutlined />
        </div>
        <SectionHeader meta={bindingStatusLabel} title={t("whatsapp.title")} />
        <DetailGrid
          items={[
            {
              label: t("whatsapp.currentStatus"),
              value: bindingStatusLabel,
            },
            {
              label: t("whatsapp.phoneNumber"),
              value: whatsAppBinding?.phoneNumber || t("whatsapp.noPhone"),
            },
            {
              label: t("whatsapp.updatedAt"),
              value: formatTimestamp(whatsAppBinding?.lastUpdatedAt ?? null),
            },
          ]}
        />
      </article>

      {isPendingBinding ? (
        <article className="h5-card h5-member-whatsapp-bind-card">
          <SectionHeader meta={t("whatsapp.pending")} title={t("whatsapp.pendingTitle")} />
          <p className="muted h5-member-whatsapp-bind-copy">{t("whatsapp.pendingDesc")}</p>
        </article>
      ) : null}

      {!isBound && !isPendingBinding ? (
        <article className="h5-card h5-member-whatsapp-bind-card">
          <SectionHeader title={t("whatsapp.bindTitle")} />
          <p className="muted h5-member-whatsapp-bind-copy">{t("whatsapp.bindDesc")}</p>
          <form className="h5-form" onSubmit={(event) => void handleSubmit(event)}>
            <label>
              {t("whatsapp.bindPhoneLabel")}
              <input
                disabled={isApiAction || apiLoading}
                inputMode="numeric"
                onChange={(event) => handlePhoneChange(event.target.value)}
                placeholder={t("whatsapp.bindPhonePlaceholder")}
                type="tel"
                value={whatsappPhone}
              />
              {phoneError ? <span className="h5-field-error">{phoneError}</span> : null}
            </label>
            {apiError ? (
              <div className="h5-member-whatsapp-error">
                <CloseCircleOutlined style={{ marginRight: 4 }} />
                {apiError}
              </div>
            ) : null}
            <div className="h5-member-card-actions">
              <button className="h5-primary-button" disabled={isApiAction || apiLoading || !whatsappPhone.trim()} type="submit">
                {isApiAction || apiLoading ? (
                  <>
                    <LoadingOutlined style={{ marginRight: 6 }} />
                    {t("whatsapp.processing")}
                  </>
                ) : (
                  t("whatsapp.bindSubmit")
                )}
              </button>
            </div>
          </form>
        </article>
      ) : null}

    </section>
  );
}
