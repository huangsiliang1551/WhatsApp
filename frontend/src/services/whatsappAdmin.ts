import { listMetaAccounts, type MetaWabaAccount } from "./api";
import {
  listPlatformMemberWhatsAppBindings,
  updatePlatformMemberWhatsAppBindingStatus,
  type PlatformMemberWhatsAppBindingRequest,
  type PlatformMemberWhatsAppBindingStatus,
} from "./h5";
import type {
  PlatformWhatsAppBindingFilters,
  PlatformWhatsAppBindingRecord,
  PlatformWhatsAppBindingStatusInput,
  WhatsAppAccountOption,
} from "../types/whatsapp";

function mapBindingRecord(
  binding: PlatformMemberWhatsAppBindingRequest,
): PlatformWhatsAppBindingRecord {
  return {
    id: binding.id,
    accountId: binding.accountId,
    userId: binding.userId,
    memberProfileId: binding.memberProfileId,
    siteId: binding.siteId,
    siteKey: binding.siteKey,
    publicUserId: binding.publicUserId,
    memberNo: binding.memberNo,
    displayName: binding.displayName,
    status: binding.status,
    requestedPhoneNumber: binding.requestedPhoneNumber,
    startCount: binding.startCount,
    lastError: binding.lastError,
    createdAt: binding.createdAt,
    updatedAt: binding.updatedAt,
    lastStartedAt: binding.lastStartedAt,
    boundAt: binding.boundAt,
  };
}

function mapAccountOption(account: MetaWabaAccount): WhatsAppAccountOption {
  return {
    accountId: account.account_id,
    wabaId: account.waba_id,
    displayName: account.display_name,
    metaBusinessPortfolioId: account.meta_business_portfolio_id ?? null,
    hasAccessToken: account.has_access_token,
    isActive: account.is_active,
    phoneCount: Array.isArray(account.phone_numbers) ? account.phone_numbers.length : 0,
    tokenSource: account.token_source,
  };
}

export async function listWhatsAppBindingReviews(
  filters?: PlatformWhatsAppBindingFilters,
): Promise<PlatformWhatsAppBindingRecord[]> {
  const bindings = await listPlatformMemberWhatsAppBindings({
    account_id: filters?.accountId,
    status: filters?.status as PlatformMemberWhatsAppBindingStatus | undefined,
  });
  return bindings.map(mapBindingRecord);
}

export async function reviewWhatsAppBinding(
  requestId: string,
  input: PlatformWhatsAppBindingStatusInput,
): Promise<PlatformWhatsAppBindingRecord> {
  const binding = await updatePlatformMemberWhatsAppBindingStatus(requestId, input);
  return mapBindingRecord(binding);
}

export async function listWhatsAppAccountOptions(): Promise<WhatsAppAccountOption[]> {
  const accounts = await listMetaAccounts();
  return accounts.map(mapAccountOption);
}
