import { useEffect, useState } from "react";
import { getCurrentMemberSession } from "../../services/h5Member";
import { buildH5LoginRedirectPath } from "./sharedUtils";

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

export function useAuthGuard(
  redirectToLogin: boolean,
  currentPath: string,
  onNavigate?: (path: string) => void,
): AuthGuardResult {
  const [isLoading, setIsLoading] = useState(true);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [user, setUser] = useState<H5MemberInfo | null>(null);

  useEffect(() => {
    let cancelled = false;

    void (async () => {
      const session = await getCurrentMemberSession();
      if (cancelled) {
        return;
      }

      const auth = !!session;
      setIsAuthenticated(auth);
      setUser(
        session
          ? {
              accountId: session.accountId,
              phone: session.phone ?? session.username ?? "",
              publicUserId: session.publicUserId,
              displayName: session.displayName,
              inviteCode: session.inviteCode,
              avatarUrl: session.avatarUrl ?? null,
            }
          : null,
      );
      setIsLoading(false);

      if (!auth && redirectToLogin && onNavigate) {
        const currentUrl = new URL(currentPath, "http://localhost");
        const siteKey = currentUrl.searchParams.get("site_key")?.trim();
        onNavigate(buildH5LoginRedirectPath(currentPath, siteKey));
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [redirectToLogin, currentPath, onNavigate]);

  return { isAuthenticated, isLoading, user };
}

