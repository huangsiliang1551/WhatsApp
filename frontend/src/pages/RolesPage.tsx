import { useEffect, type JSX } from "react";

function buildWorkbenchRolesLocation(search: string): string {
  const params = new URLSearchParams(search.startsWith("?") ? search.slice(1) : search);
  const nextParams = new URLSearchParams();
  const agencyId = params.get("agencyId");
  const role = params.get("role");

  if (agencyId) {
    nextParams.set("agencyId", agencyId);
  }
  nextParams.set("tab", "roles");
  if (role) {
    nextParams.set("role", role);
  }

  return `/system/agents?${nextParams.toString()}`;
}

export function RolesPage(): JSX.Element {
  useEffect(() => {
    const nextLocation = buildWorkbenchRolesLocation(window.location.search);
    const currentLocation = `${window.location.pathname}${window.location.search}`;
    if (nextLocation !== currentLocation) {
      window.history.replaceState({}, "", nextLocation);
      window.dispatchEvent(new PopStateEvent("popstate"));
    }
  }, []);

  return (
    <section style={{ padding: 24 }}>
      <h1>角色权限兼容入口</h1>
      <p>旧版 /system/roles 已并入代理商管理工作台。</p>
      <p>正在跳转到代理商管理工作台的角色视图...</p>
    </section>
  );
}

export default RolesPage;
