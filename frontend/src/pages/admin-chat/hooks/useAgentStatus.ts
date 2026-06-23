import { useCallback, useEffect, useRef, useState } from "react";
import { useAppStore, type OperatorStatus } from "../../../stores/appStore";
import { setAgentStatus } from "../../../services/api";

export interface StatusOption {
  value: OperatorStatus;
  label: string;
  color: string;
}

const STATUS_OPTIONS: StatusOption[] = [
  { value: "online", label: "🟢 在线", color: "#52c41a" },
  { value: "busy", label: "🟡 忙碌", color: "#faad14" },
  { value: "away", label: "⚪ 离开", color: "#d9d9d9" },
  { value: "offline", label: "🔴 下线", color: "#ff4d4f" },
];

export function useAgentStatus() {
  const agentId = useAppStore((s) => s.consoleAgentId);
  const storeStatus = useAppStore((s) => s.operatorStatus);
  const setStoreStatus = useAppStore((s) => s.setOperatorStatus);
  const [status, setStatusLocal] = useState<OperatorStatus>(storeStatus);
  const statusRef = useRef(status);
  statusRef.current = status;
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const syncStatus = useCallback(async (newStatus: OperatorStatus) => {
    if (!agentId) return;
    try {
      await setAgentStatus(agentId, newStatus);
      setStoreStatus(newStatus);
    } catch {
      // fail silently
    }
  }, [agentId, setStoreStatus]);

  const setStatus = useCallback((newStatus: OperatorStatus) => {
    setStatusLocal(newStatus);
    syncStatus(newStatus);
  }, [syncStatus]);

  // Sync from store on mount or store change
  useEffect(() => {
    setStatusLocal(storeStatus);
  }, [storeStatus]);

  // Auto-sync every 30 seconds
  useEffect(() => {
    intervalRef.current = setInterval(() => {
      if (agentId) {
        syncStatus(statusRef.current);
      }
    }, 30_000);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [agentId, syncStatus]);

  return { status, setStatus, statusOptions: STATUS_OPTIONS };
}
