export type WhatsAppBindingReviewStatus = "pending" | "bound" | "failed";

export interface PlatformWhatsAppBindingRecord {
  id: string;
  accountId: string;
  userId: string;
  memberProfileId: string;
  siteId: string | null;
  siteKey: string | null;
  publicUserId: string;
  memberNo: string;
  displayName: string | null;
  status: WhatsAppBindingReviewStatus;
  requestedPhoneNumber: string | null;
  startCount: number;
  lastError: string | null;
  createdAt: string;
  updatedAt: string;
  lastStartedAt: string | null;
  boundAt: string | null;
}

export interface PlatformWhatsAppBindingFilters {
  accountId?: string;
  status?: WhatsAppBindingReviewStatus;
}

export interface PlatformWhatsAppBindingStatusInput {
  status: WhatsAppBindingReviewStatus;
  note?: string;
}

export interface WhatsAppAccountOption {
  accountId: string;
  wabaId: string;
  displayName: string;
  metaBusinessPortfolioId: string | null;
  hasAccessToken: boolean;
  isActive: boolean;
  phoneCount: number;
  tokenSource: string;
}
