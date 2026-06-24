export type H5SpaRequest = {
  method: string;
  pathname: string;
};

const STATIC_FILE_PATTERN = /\.[a-z0-9]+$/i;

export function shouldServeH5AppShell(request: H5SpaRequest): boolean {
  const method = request.method.toUpperCase();
  const pathname = request.pathname.trim();

  if (method !== "GET" && method !== "HEAD") {
    return false;
  }

  if (pathname !== "/h5" && !pathname.startsWith("/h5/")) {
    return false;
  }

  if (
    pathname.startsWith("/api/")
    || pathname.startsWith("/@")
    || pathname.startsWith("/src/")
    || pathname.startsWith("/assets/")
    || pathname.startsWith("/node_modules/")
  ) {
    return false;
  }

  return !STATIC_FILE_PATTERN.test(pathname);
}
