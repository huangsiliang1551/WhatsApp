import { useCallback, useEffect, useState } from "react";
import { adminAuth } from "../services/adminAuth";
import { resolveApiBaseUrl } from "../services/resolveApiBaseUrl";

export interface PermissionsInfo {
  user_type: "super_admin" | "agent" | "agent_member";
  role: string;
  agency_id: string | null;
  agency_name: string | null;
  menus: string[];
  permissions: string[];
}

function deriveEmptyPermissions(): PermissionsInfo {
  const user = adminAuth.getCurrentUser();
  const userType =
    user?.role === "admin"
      ? "super_admin"
      : user?.role === "agent"
        ? "agent"
        : "agent_member";

  return {
    user_type: userType,
    role: user?.role ?? userType,
    agency_id: user?.agency_id ?? null,
    agency_name: null,
    menus: [],
    permissions: [],
  };
}

export function canSeePageWithMenus(menus: string[], pageId: string): boolean {
  return new Set(menus).has(pageId);
}

const API_BASE = resolveApiBaseUrl(
  import.meta.env.VITE_API_BASE_URL as string | undefined,
  import.meta.env.DEV,
);

async function fetchPermissions(): Promise<PermissionsInfo | null> {
  try {
    const token = adminAuth.getAccessToken();
    if (!token) {
      return null;
    }

    const response = await fetch(`${API_BASE}/api/auth/permissions`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.ok) {
      return null;
    }

    return (await response.json()) as PermissionsInfo;
  } catch {
    return null;
  }
}

export function usePermissions() {
  const [perms, setPerms] = useState<PermissionsInfo | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    const apiPerms = await fetchPermissions();
    setPerms(apiPerms ?? deriveEmptyPermissions());
    setLoading(false);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    const onPopState = () => {
      void load();
    };

    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, [load]);

  const can = useCallback(
    (code: string) => perms?.permissions.includes(code) ?? false,
    [perms],
  );

  const canSeePage = useCallback(
    (pageId: string) => {
      if (!perms) {
        return false;
      }
      return canSeePageWithMenus(perms.menus, pageId);
    },
    [perms],
  );

  return { perms, can, canSeePage, loading };
}
