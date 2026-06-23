import zhCN from "./zh-CN.json";
import enUS from "./en-US.json";
import jaJP from "./ja-JP.json";

const locales: Record<string, Record<string, string>> = {
  "zh-CN": zhCN,
  "en-US": enUS,
  "ja-JP": jaJP,
};

let currentLang = localStorage.getItem("agent_language") || "zh-CN";

export function setLanguage(lang: string): void {
  currentLang = lang;
  localStorage.setItem("agent_language", lang);
}

export function getCurrentLanguage(): string {
  return currentLang;
}

export function t(key: string, params?: Record<string, string | number>): string {
  const locale = locales[currentLang] || locales["zh-CN"];
  let text = locale[key] || key;
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      text = text.replace(`{${k}}`, String(v));
    }
  }
  return text;
}

export function getAvailableLanguages(): Array<{ code: string; label: string }> {
  return [
    { code: "zh-CN", label: "简体中文" },
    { code: "en-US", label: "English" },
    { code: "ja-JP", label: "日本語" },
  ];
}
