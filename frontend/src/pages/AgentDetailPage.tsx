import { useEffect, type JSX } from "react";

type LegacyWorkbenchTab =
  | "overview"
  | "permissions"
  | "roles"
  | "members"
  | "edit"
  | "billing";

function normalizeLegacyTab(rawTab: string | null): LegacyWorkbenchTab {
  if (
    rawTab === "roles" ||
    rawTab === "members" ||
    rawTab === "permissions" ||
    rawTab === "edit" ||
    rawTab === "billing"
  ) {
    return rawTab;
  }
  if (rawTab === "permission-grants") {
    return "permissions";
  }
  return "overview";
}

function buildWorkbenchLocationFromLegacyUrl(): string {
  const detailMatch = window.location.pathname.match(/^\/system\/agents\/([^/]+)$/);
  const agencyId = detailMatch ? decodeURIComponent(detailMatch[1]) : null;
  const params = new URLSearchParams(
    window.location.search.startsWith("?")
      ? window.location.search.slice(1)
      : window.location.search
  );
  const nextParams = new URLSearchParams();
  const tab = normalizeLegacyTab(params.get("tab"));

  if (agencyId) {
    nextParams.set("agencyId", agencyId);
  }
  if (agencyId || tab !== "overview") {
    nextParams.set("tab", tab);
  }
  if (tab === "roles" && params.get("role")) {
    nextParams.set("role", params.get("role") as string);
  }
  if (tab === "members" && params.get("member")) {
    nextParams.set("member", params.get("member") as string);
  }

  return `/system/agents?${nextParams.toString()}`;
}

export function AgentDetailPage(): JSX.Element {
  useEffect(() => {
    const nextLocation = buildWorkbenchLocationFromLegacyUrl();
    const currentLocation = `${window.location.pathname}${window.location.search}`;
    if (nextLocation !== currentLocation) {
      window.history.replaceState({}, "", nextLocation);
      window.dispatchEvent(new PopStateEvent("popstate"));
    }
  }, []);

  return (
    <section style={{ padding: 24 }}>
      <h1>代理详情兼容入口</h1>
      <p>旧版代理详情页已并入代理商管理工作台。</p>
      <p>正在跳转到当前代理商的工作台视图...</p>
    </section>
  );
}

export default AgentDetailPage;
