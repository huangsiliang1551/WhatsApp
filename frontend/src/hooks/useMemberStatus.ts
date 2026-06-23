import { useRef, useState } from "react";

import {
  getPlatformUserMemberStatusSnapshot,
  type PlatformUserMemberStatusSnapshot,
} from "../services/operations";
import type {
  PlatformMemberVerificationRequest,
  PlatformMemberWhatsAppBindingRequest,
} from "../services/h5";

/**
 * 会员状态查询的最小输入契约，兼容 CustomerProfileSummary / SupportTicketDetail / PlatformUser
 */
export type UseMemberStatusProfile = {
  id: string;
  account_id: string | null;
  public_user_id: string;
} | null;

export type UseMemberStatusReturn = {
  /** 原始会员状态快照 */
  memberStatus: PlatformUserMemberStatusSnapshot | null;
  /** 加载中 */
  memberStatusLoading: boolean;
  /** 加载错误 */
  memberStatusError: string | null;
  /** 最近一条认证请求 */
  latestVerification: PlatformMemberVerificationRequest | null;
  /** 最近一条绑定请求 */
  latestBinding: PlatformMemberWhatsAppBindingRequest | null;
  /** 认证请求总数 */
  verificationCount: number;
  /** 绑定请求总数 */
  bindingCount: number;
  /**
   * 手动触发加载。
   * 适用于 ChatPage / AssignmentsPage 等需先 resolve 出 profile 再加载状态的情境。
   */
  loadMemberStatus: (profile: Exclude<UseMemberStatusProfile, null>) => Promise<void>;
  /** 重置为初始值 */
  resetMemberStatus: () => void;
};

/**
 * 共享 hook —— 封装会员认证 / WhatsApp 绑定状态的加载逻辑。
 *
 * 使用方式（TicketsPage / CustomersPage 风格）：
 * ```ts
 * const { memberStatus, memberStatusLoading, loadMemberStatus } = useMemberStatus();
 * useEffect(() => { if (selected) loadMemberStatus(selected); }, [selected]);
 * ```
 *
 * 使用方式（ChatPage / AssignmentsPage 风格）：
 * ```ts
 * const { loadMemberStatus, resetMemberStatus } = useMemberStatus();
 * async function loadCustomerContext(): Promise<void> {
 *   const profile = await resolveProfile();
 *   if (profile) await loadMemberStatus(profile);
 * }
 * ```
 */
export function useMemberStatus(): UseMemberStatusReturn {
  const requestIdRef = useRef(0);
  const [memberStatus, setMemberStatus] = useState<PlatformUserMemberStatusSnapshot | null>(null);
  const [memberStatusLoading, setMemberStatusLoading] = useState(false);
  const [memberStatusError, setMemberStatusError] = useState<string | null>(null);

  async function loadMemberStatus(
    profile: Exclude<UseMemberStatusProfile, null>
  ): Promise<void> {
    const requestId = ++requestIdRef.current;
    setMemberStatusLoading(true);
    setMemberStatusError(null);
    try {
      const snapshot = await getPlatformUserMemberStatusSnapshot(profile);
      if (requestId !== requestIdRef.current) {
        return;
      }
      setMemberStatus(snapshot);
    } catch (loadError) {
      if (requestId !== requestIdRef.current) {
        return;
      }
      setMemberStatus(null);
      setMemberStatusError(
        loadError instanceof Error ? loadError.message : "会员状态加载失败"
      );
    } finally {
      if (requestId === requestIdRef.current) {
        setMemberStatusLoading(false);
      }
    }
  }

  function resetMemberStatus(): void {
    setMemberStatus(null);
    setMemberStatusLoading(false);
    setMemberStatusError(null);
  }

  const latestVerification = memberStatus?.verificationRequests[0] ?? null;
  const latestBinding = memberStatus?.bindingRequests[0] ?? null;

  return {
    memberStatus,
    memberStatusLoading,
    memberStatusError,
    latestVerification,
    latestBinding,
    verificationCount: memberStatus?.verificationRequests.length ?? 0,
    bindingCount: memberStatus?.bindingRequests.length ?? 0,
    loadMemberStatus,
    resetMemberStatus,
  };
}
