import type { ReactNode } from "react";

import type { ConsoleRouteDefinition } from "../types/console";

type AdminRoutePageShellProps = {
  children: ReactNode;
  onOpenStats: () => void;
  route: ConsoleRouteDefinition;
  compact?: boolean;
};

function getProgressColor(tone: ConsoleRouteDefinition["progress"]["tone"]): string {
  if (tone === "done") return "success";
  if (tone === "in_progress") return "processing";
  return "default";
}

function getDataSourceColor(tone: ConsoleRouteDefinition["dataBadges"][number]["tone"]): string {
  if (tone === "api") return "blue";
  if (tone === "hybrid") return "cyan";
  if (tone === "mock") return "gold";
  return "default";
}

function getDataSourceLabel(tone: ConsoleRouteDefinition["dataBadges"][number]["tone"]): string {
  if (tone === "api") return "API";
  if (tone === "hybrid") return "混合";
  if (tone === "mock") return "模拟";
  return "占位";
}

export function AdminRoutePageShell({
  children,
  onOpenStats,
  route,
  compact = false,
}: AdminRoutePageShellProps) {
  if (compact) {
    return (
      <div
        className="admin-route-page"
        style={{
          display: "flex",
          flexDirection: "column",
          flex: 1,
          minHeight: 0,
          padding: 0,
        }}
      >
        {children}
      </div>
    );
  }

  return (
    <div
      className="admin-route-page"
      style={{
        display: "flex",
        flexDirection: "column",
        flex: 1,
        minHeight: 0,
        padding: "0 24px 24px",
      }}
    >

      <div style={{ flex: 1, minHeight: 0, overflow: "auto" }}>
        {children}
      </div>
    </div>
  );
}
