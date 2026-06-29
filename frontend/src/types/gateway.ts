export type GatewayNodeStatus = "online" | "offline" | "degraded" | "unknown";
export type GatewayJobStatus = "pending" | "running" | "succeeded" | "failed" | "cancelled" | "unknown";

export interface GatewayNodeRecord {
  id: string;
  accountId: string | null;
  name: string;
  host: string;
  region: string | null;
  environment: string | null;
  status: GatewayNodeStatus;
  lastHeartbeatAt: string | null;
  lastDeployAt: string | null;
  activeSiteCount: number;
  updatedAt: string | null;
}

export interface GatewayJobRecord {
  id: string;
  accountId: string | null;
  nodeId: string | null;
  siteId: string | null;
  siteKey: string | null;
  jobType: string;
  status: GatewayJobStatus;
  startedAt: string | null;
  finishedAt: string | null;
  errorMessage: string | null;
}

export interface GatewayHealthSummary {
  totalNodes: number;
  onlineNodes: number;
  degradedNodes: number;
  offlineNodes: number;
  runningJobs: number;
  failedJobs: number;
}
