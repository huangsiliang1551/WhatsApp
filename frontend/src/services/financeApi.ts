import { api } from "./api";

export interface FinanceRechargeRecord {
  id: string;
  account_id?: string;
  user_id: string;
  public_user_id?: string | null;
  amount: number;
  cash_amount: number;
  bonus_amount: number;
  currency: string;
  status: string;
  source_type?: string | null;
  transaction_type?: string | null;
  fund_type?: string | null;
  is_bonus?: boolean;
  is_real_recharge?: boolean;
  reference_type?: string | null;
  reference_id?: string | null;
  created_at?: string | null;
}

export interface FinanceWithdrawalRecord {
  id: string;
  account_id?: string;
  user_id: string;
  public_user_id?: string | null;
  amount: number;
  cash_amount: number;
  bonus_amount: number;
  actual_payout_amount?: number;
  withdraw_account_type?: string | null;
  account_no_masked?: string | null;
  account_fingerprint?: string | null;
  duplicate_account_count?: number;
  duplicate_member_ids?: string[];
  risk_level?: string | null;
  risk_flags?: string[];
  currency?: string;
  status: string;
  reject_reason?: string | null;
  created_at?: string | null;
  reviewed_at?: string | null;
  paid_at?: string | null;
}

export interface FinanceSummary {
  recharge_amount: number;
  recharge_count: number;
  bonus_amount: number;
  withdrawal_amount: number;
  withdrawal_cash_amount: number;
  withdrawal_bonus_amount: number;
  withdrawal_fee: number;
  withdrawal_count: number;
  net_recharge: number;
}

export interface FinanceAnomalyAlert {
  type: string;
  record_id?: string;
  account_id?: string;
  user_id?: string;
  public_user_id?: string;
  count?: number;
  amount?: number;
  time?: string;
  message: string;
}

export interface FinanceBonusGrant {
  id: string;
  account_id: string;
  grant_no: string;
  user_id: string;
  public_user_id?: string | null;
  amount: number;
  currency: string;
  source_type: string;
  reason: string;
  remark?: string | null;
  status: string;
  operator_id: string;
  approved_by?: string | null;
  approved_at?: string | null;
  credited_at?: string | null;
  rejected_at?: string | null;
  ledger_id?: string | null;
  created_at?: string | null;
}

export interface FinanceRechargeRepair {
  id: string;
  account_id: string;
  repair_no: string;
  user_id: string;
  public_user_id?: string | null;
  amount: number;
  currency: string;
  repair_type: string;
  reason: string;
  remark?: string | null;
  status: string;
  channel_id?: string | null;
  platform_order_no?: string | null;
  channel_order_no?: string | null;
  operator_id: string;
  approved_by?: string | null;
  approved_at?: string | null;
  credited_at?: string | null;
  rejected_at?: string | null;
  recharge_record_id?: string | null;
  ledger_id?: string | null;
  created_at?: string | null;
}

export interface FinanceWalletLedger {
  id: string;
  account_id?: string;
  user_id: string;
  public_user_id?: string | null;
  ledger_type: string;
  transaction_type: string;
  direction: string;
  amount: number;
  currency: string;
  status: string;
  source_type?: string | null;
  fund_type?: string | null;
  cash_amount: number;
  bonus_amount: number;
  task_amount: number;
  balance_after?: number | null;
  cash_balance_after?: number | null;
  bonus_balance_after?: number | null;
  task_balance_after?: number | null;
  display_category?: string | null;
  display_title?: string | null;
  note?: string | null;
  reference_type?: string | null;
  reference_id?: string | null;
  created_at?: string | null;
}

export interface BonusGrantCreatePayload {
  accountId: string;
  userId: string;
  amount: number;
  currency?: string;
  sourceType?: string;
  reason: string;
  remark?: string;
}

export interface RechargeRepairCreatePayload {
  accountId: string;
  userId: string;
  amount: number;
  currency?: string;
  repairType?: string;
  reason: string;
  remark?: string;
  channelId?: string;
  platformOrderNo?: string;
  channelOrderNo?: string;
}

export interface RechargeRecordFilters {
  agencyId?: string;
  siteId?: string;
  status?: string;
  sourceType?: string;
  fundScope?: "cash" | "bonus";
  includeBonus?: boolean;
  sortField?: string;
  sortOrder?: "asc" | "desc";
}

export interface WithdrawalRecordFilters {
  agencyId?: string;
  siteId?: string;
  status?: string;
  fundScope?: "cash" | "bonus";
  includeBonus?: boolean;
  sortField?: string;
  sortOrder?: "asc" | "desc";
}

export interface WalletLedgerFilters {
  agencyId?: string;
  userId?: string;
  status?: string;
  sourceType?: string;
  transactionType?: string;
  fundScope?: "cash" | "bonus";
  sortField?: string;
  sortOrder?: "asc" | "desc";
}

export async function listRechargeRecords(filters: RechargeRecordFilters = {}): Promise<FinanceRechargeRecord[]> {
  const response = await api.get<FinanceRechargeRecord[]>("/api/finance/recharge-records", {
    params: {
      agency_id: filters.agencyId,
      site_id: filters.siteId,
      status: filters.status,
      source_type: filters.sourceType,
      fund_scope: filters.fundScope,
      include_bonus: filters.includeBonus,
      sort_field: filters.sortField,
      sort_order: filters.sortOrder,
    },
  });
  return response.data;
}

export async function listWithdrawalRecords(filters: WithdrawalRecordFilters = {}): Promise<FinanceWithdrawalRecord[]> {
  const response = await api.get<FinanceWithdrawalRecord[]>("/api/finance/withdrawal-records", {
    params: {
      agency_id: filters.agencyId,
      site_id: filters.siteId,
      status: filters.status,
      fund_scope: filters.fundScope,
      include_bonus: filters.includeBonus,
      sort_field: filters.sortField,
      sort_order: filters.sortOrder,
    },
  });
  return response.data;
}

export async function getFinanceSummary(params: { agencyId?: string; includeBonus?: boolean } = {}): Promise<FinanceSummary> {
  const response = await api.get<FinanceSummary>("/api/finance/report/summary", {
    params: {
      agency_id: params.agencyId,
      include_bonus: params.includeBonus,
    },
  });
  return response.data;
}

export async function listAnomalyAlerts(): Promise<FinanceAnomalyAlert[]> {
  const response = await api.get<FinanceAnomalyAlert[]>("/api/finance/anomaly-alerts");
  return response.data;
}

export async function listBonusGrants(accountId?: string): Promise<FinanceBonusGrant[]> {
  const response = await api.get<FinanceBonusGrant[]>("/api/finance/bonus-grants", {
    params: {
      account_id: accountId,
    },
  });
  return response.data;
}

export async function listRechargeRepairs(accountId?: string): Promise<FinanceRechargeRepair[]> {
  const response = await api.get<FinanceRechargeRepair[]>("/api/finance/recharge-repairs", {
    params: {
      account_id: accountId,
    },
  });
  return response.data;
}

export async function listWalletLedgers(filters: WalletLedgerFilters = {}): Promise<FinanceWalletLedger[]> {
  const response = await api.get<FinanceWalletLedger[]>("/api/finance/wallet-ledgers", {
    params: {
      agency_id: filters.agencyId,
      user_id: filters.userId,
      status: filters.status,
      source_type: filters.sourceType,
      transaction_type: filters.transactionType,
      fund_scope: filters.fundScope,
      sort_field: filters.sortField,
      sort_order: filters.sortOrder,
    },
  });
  return response.data;
}

export async function createBonusGrant(payload: BonusGrantCreatePayload): Promise<FinanceBonusGrant> {
  const response = await api.post<FinanceBonusGrant>("/api/finance/bonus-grants", {
    account_id: payload.accountId,
    user_id: payload.userId,
    amount: payload.amount,
    currency: payload.currency ?? "USD",
    source_type: payload.sourceType ?? "admin_bonus",
    reason: payload.reason,
    remark: payload.remark,
  });
  return response.data;
}

export async function approveBonusGrant(grantId: string): Promise<FinanceBonusGrant> {
  const response = await api.post<FinanceBonusGrant>(`/api/finance/bonus-grants/${grantId}/approve`);
  return response.data;
}

export async function rejectBonusGrant(grantId: string, payload: { reason?: string }): Promise<FinanceBonusGrant> {
  const response = await api.post<FinanceBonusGrant>(`/api/finance/bonus-grants/${grantId}/reject`, payload);
  return response.data;
}

export async function createRechargeRepair(payload: RechargeRepairCreatePayload): Promise<FinanceRechargeRepair> {
  const response = await api.post<FinanceRechargeRepair>("/api/finance/recharge-repairs", {
    account_id: payload.accountId,
    user_id: payload.userId,
    amount: payload.amount,
    currency: payload.currency ?? "USD",
    repair_type: payload.repairType ?? "manual_real_recharge",
    reason: payload.reason,
    remark: payload.remark,
    channel_id: payload.channelId,
    platform_order_no: payload.platformOrderNo,
    channel_order_no: payload.channelOrderNo,
  });
  return response.data;
}

export async function approveRechargeRepair(repairId: string): Promise<FinanceRechargeRepair> {
  const response = await api.post<FinanceRechargeRepair>(`/api/finance/recharge-repairs/${repairId}/approve`);
  return response.data;
}

export async function rejectRechargeRepair(
  repairId: string,
  payload: { reason?: string },
): Promise<FinanceRechargeRepair> {
  const response = await api.post<FinanceRechargeRepair>(`/api/finance/recharge-repairs/${repairId}/reject`, payload);
  return response.data;
}
