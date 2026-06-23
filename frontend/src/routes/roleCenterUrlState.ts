export type RoleCenterQuery = {
  agencyId: string | null;
  role: string | null;
};

export function readRoleCenterQuery(search: string = window.location.search): RoleCenterQuery {
  const params = new URLSearchParams(search.startsWith("?") ? search.slice(1) : search);
  return {
    agencyId: params.get("agencyId"),
    role: params.get("role"),
  };
}

export function buildRoleCenterPath(agencyId: string, role?: string | null): string {
  const params = new URLSearchParams();
  params.set("agencyId", agencyId);
  params.set("tab", "roles");
  if (role) {
    params.set("role", role);
  }
  return `/system/agents?${params.toString()}`;
}

export function syncRoleCenterLocation(
  agencyId: string | null,
  role: string | null,
  pathname: string = window.location.pathname,
): void {
  const url = new URL(window.location.href);
  url.pathname = pathname;
  if (agencyId) {
    url.searchParams.set("agencyId", agencyId);
    url.searchParams.set("tab", "roles");
  } else {
    url.searchParams.delete("agencyId");
    url.searchParams.delete("tab");
  }
  if (role) {
    url.searchParams.set("role", role);
  } else {
    url.searchParams.delete("role");
  }
  window.history.replaceState({}, "", `${url.pathname}${url.search}`);
}

export function openRoleCenter(agencyId: string, role?: string | null): void {
  window.history.pushState({}, "", buildRoleCenterPath(agencyId, role));
  window.dispatchEvent(new PopStateEvent("popstate"));
}
