export function resolveApiBaseUrl(rawBaseUrl: string | undefined, isDev: boolean): string {
  const explicitBaseUrl = rawBaseUrl?.trim();
  if (explicitBaseUrl) {
    return explicitBaseUrl;
  }
  if (isDev) {
    return "";
  }
  return "";
}
