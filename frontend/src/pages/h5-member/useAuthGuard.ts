import { useEffect, useState } from "react";
import { sessionManager } from "../../services/h5SessionManager";
import { buildH5Path } from "./sharedUtils";

export type H5MemberInfo = {
  accountId: string;
  phone: string;
  publicUserId: string;
  displayName: string;
  inviteCode: string;
  avatarUrl?: string | null;
  accountIdMasked?: string;
  createdAt?: string;
};

type AuthGuardResult = {
  isAuthenticated: boolean;
  isLoading: boolean;
  user: H5MemberInfo | null;
};

/**
 * 路由守卫 hook
 * @param redirectToLogin 是否在未认证时跳转登录页
 * @param currentPath 当前路径，用于 redirect 参数
 * @param onNavigate 导航回调，用于跳转登录页
 */
export function useAuthGuard(
  redirectToLogin: boolean,
  currentPath: string,
  onNavigate?: (path: string) => void,
): AuthGuardResult {
  const [isLoading, setIsLoading] = useState(true);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [user, setUser] = useState<H5MemberInfo | null>(null);

  useEffect(() => {
    // 从 sessionManager 检查登录态
    const auth = sessionManager.isAuthenticated();
    const userInfo = sessionManager.getUserInfo();

    setIsAuthenticated(auth);
    setUser(userInfo);
    setIsLoading(false);

    if (!auth && redirectToLogin && onNavigate) {
      const currentUrl = new URL(currentPath, "http://localhost");
      const siteKey = currentUrl.searchParams.get("site_key")?.trim();
      if (siteKey) {
        onNavigate(buildH5Path("/h5/login", siteKey, { redirect: currentPath }));
        return;
      }

      const encodedPath = encodeURIComponent(currentPath);
      onNavigate(`/h5/login?redirect=${encodedPath}`);
    }
  }, [redirectToLogin, currentPath, onNavigate]);

  return { isAuthenticated, isLoading, user };
}
