import { zhCN } from "./zh-CN";
import { en } from "./en";

export type Messages = typeof en;

const messagesMap: Record<string, Messages> = {
  "zh-CN": zhCN as Messages,
  en: en as Messages,
  "en-US": en as Messages,
};

function resolveSupportedMessageLanguage(locale: string | null | undefined): keyof typeof messagesMap | null {
  if (!locale) {
    return null;
  }

  if (messagesMap[locale]) {
    return locale as keyof typeof messagesMap;
  }

  const normalized = locale.toLowerCase();
  if (normalized.startsWith("zh")) {
    return "zh-CN";
  }
  if (normalized.startsWith("en")) {
    return "en";
  }

  return "en";
}

function resolveLanguage(): string {
  if (typeof window === "undefined") {
    return "zh-CN";
  }

  const saved = window.localStorage?.getItem("h5-lang");
  const savedLanguage = resolveSupportedMessageLanguage(saved);
  if (savedLanguage) {
    return savedLanguage;
  }

  const docLang = typeof document !== "undefined" ? document.documentElement.lang : "";
  const documentLanguage = resolveSupportedMessageLanguage(docLang);
  if (documentLanguage) {
    return documentLanguage;
  }

  const browserLang = typeof navigator !== "undefined" ? navigator.language : "";
  const browserLanguage = resolveSupportedMessageLanguage(browserLang);
  if (browserLanguage) {
    return browserLanguage;
  }

  return "zh-CN";
}

export function getMessages(): Messages {
  const lang = resolveLanguage();
  return messagesMap[lang] || zhCN;
}

function sanitizeTranslationOutput(value: string): string {
  return value
    .replace(/楼(?=(?:US\$|\$|EUR|GBP|JPY|¥))/g, "")
    .replace(/¥(?=(?:US\$|\$))/g, "")
    .replace(/ [路璺][^A-Za-z0-9{] /g, " · ")
    .replace(/^🎉\s*/g, "")
    .replace(/^✅\s*/g, "")
    .replace(/^❌\s*/g, "")
    .replace(/鈥檚/g, "’s")
    .replace(/Today鈥檚/g, "Today’s")
    .replace(/鈥\?Prev/g, "← Prev")
    .replace(/^‹ Prev$/g, "← Prev")
    .replace(/Next 鈥\?,/g, "Next →")
    .replace(/^Next ›$/g, "Next →")
    .replace(/馃帀\s*/g, "")
    .replace(/鉁\?\s*/g, "")
    .replace(/鉂\?\s*/g, "");
}

export function t(key: string, fallbackOrParams?: string | Record<string, string | number>): string {
  const keys = key.split(".");
  let value: unknown = getMessages();

  for (const k of keys) {
    if (value && typeof value === "object" && k in value) {
      value = (value as Record<string, unknown>)[k];
    } else {
      return typeof fallbackOrParams === "string" ? fallbackOrParams : key;
    }
  }

  if (typeof value === "string") {
    if (fallbackOrParams && typeof fallbackOrParams === "object") {
      return sanitizeTranslationOutput(
        value
          .replace(/\{\{(\w+)\}\}/g, (_, p) => String(fallbackOrParams[p] ?? `{{${p}}}`))
          .replace(/\{(\w+)\}/g, (_, p) => String(fallbackOrParams[p] ?? `{${p}}`)),
      );
    }

    return sanitizeTranslationOutput(value);
  }

  return typeof fallbackOrParams === "string" ? fallbackOrParams : key;
}

export { en };
export { zhCN };
