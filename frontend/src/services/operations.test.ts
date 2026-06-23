import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type {
  PlatformMemberVerificationRequest,
  PlatformMemberWhatsAppBindingRequest,
} from "./h5";
import {
  getCustomerMemberStatusSnapshot,
  listPlatformUserMemberStatusIndex,
  selectCustomerProfileForConversation,
} from "./operations";
import type { CustomerProfileSummary } from "../types/operations";

const {
  listPlatformMemberVerificationsMock,
  listPlatformMemberWhatsAppBindingsMock,
} = vi.hoisted(() => ({
  listPlatformMemberVerificationsMock: vi.fn<
    (params?: {
      account_id?: string;
      status?: string;
    }) => Promise<PlatformMemberVerificationRequest[]>
  >(),
  listPlatformMemberWhatsAppBindingsMock: vi.fn<
    (params?: {
      account_id?: string;
      status?: string;
    }) => Promise<PlatformMemberWhatsAppBindingRequest[]>
  >(),
}));

vi.mock("./h5", async () => {
  const actual = await vi.importActual<typeof import("./h5")>("./h5");
  return {
    ...actual,
    listPlatformMemberVerifications: listPlatformMemberVerificationsMock,
    listPlatformMemberWhatsAppBindings: listPlatformMemberWhatsAppBindingsMock,
  };
});

function createProfile(overrides?: Partial<CustomerProfileSummary>): CustomerProfileSummary {
  return {
    id: "user-1",
    account_id: "acct-h5",
    public_user_id: "public-user-1",
    display_name: "Demo Member",
    registration_site_key: "mall-cn",
    registration_site_domain: "mall-cn.example.com",
    language_code: "zh-CN",
    lifecycle_status: "active",
    is_anonymous: false,
    has_whatsapp: true,
    is_invited_user: false,
    is_new_user: false,
    restrict_task_claim: false,
    last_active_at: "2026-06-12T00:00:00Z",
    registration_ip: null,
    registration_ips: [],
    multi_ip: false,
    tag_keys: [],
    identity_values: [],
    relatedCustomerIds: [],
    conversation_count: 0,
    open_conversation_count: 0,
    ticket_count: 0,
    open_ticket_count: 0,
    ...overrides,
  };
}

function createVerification(
  overrides?: Partial<PlatformMemberVerificationRequest>
): PlatformMemberVerificationRequest {
  return {
    id: "verify-1",
    accountId: "acct-h5",
    memberProfileId: "member-profile-1",
    userId: "user-1",
    publicUserId: "public-user-1",
    memberNo: "12345678",
    displayName: "Demo Member",
    requestType: "identity",
    status: "pending",
    notes: null,
    reviewNote: null,
    reviewerActorId: null,
    createdAt: "2026-06-12T00:00:00Z",
    updatedAt: "2026-06-12T00:00:00Z",
    reviewedAt: null,
    documents: [],
    ...overrides,
  };
}

function createBinding(
  overrides?: Partial<PlatformMemberWhatsAppBindingRequest>
): PlatformMemberWhatsAppBindingRequest {
  return {
    id: "binding-1",
    accountId: "acct-h5",
    userId: "user-1",
    memberProfileId: "member-profile-1",
    siteId: "site-1",
    siteKey: "mall-cn",
    publicUserId: "public-user-1",
    memberNo: "12345678",
    displayName: "Demo Member",
    status: "pending",
    requestedPhoneNumber: "13800000000",
    startCount: 1,
    lastError: null,
    createdAt: "2026-06-12T00:00:00Z",
    updatedAt: "2026-06-12T00:00:00Z",
    lastStartedAt: null,
    boundAt: null,
    ...overrides,
  };
}

describe("customer member status aggregation", () => {
  beforeEach(() => {
    listPlatformMemberVerificationsMock.mockReset();
    listPlatformMemberWhatsAppBindingsMock.mockReset();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("prefers account-scoped member profile and user identifiers over public user id fallback", async () => {
    listPlatformMemberVerificationsMock.mockResolvedValue([
      createVerification({
        id: "verify-public-fallback",
        memberProfileId: "member-profile-other",
        userId: "user-other",
        publicUserId: "public-user-1",
        updatedAt: "2026-06-12T02:00:00Z",
      }),
      createVerification({
        id: "verify-strong-match",
        userId: "user-1",
        publicUserId: "public-user-other",
        updatedAt: "2026-06-12T01:00:00Z",
      }),
    ]);
    listPlatformMemberWhatsAppBindingsMock.mockResolvedValue([
      createBinding({
        id: "binding-public-fallback",
        memberProfileId: "member-profile-other",
        userId: "user-other",
        publicUserId: "public-user-1",
        updatedAt: "2026-06-12T02:30:00Z",
      }),
      createBinding({
        id: "binding-strong-match",
        userId: "user-1",
        publicUserId: "public-user-other",
        updatedAt: "2026-06-12T01:30:00Z",
      }),
    ]);

    const snapshot = await getCustomerMemberStatusSnapshot(createProfile());

    expect(listPlatformMemberVerificationsMock).toHaveBeenCalledWith({
      account_id: "acct-h5",
    });
    expect(listPlatformMemberWhatsAppBindingsMock).toHaveBeenCalledWith({
      account_id: "acct-h5",
    });
    expect(snapshot.verificationRequests.map((item) => item.id)).toEqual(["verify-strong-match"]);
    expect(snapshot.bindingRequests.map((item) => item.id)).toEqual(["binding-strong-match"]);
  });

  it("falls back to public user id matching when no strong member identifiers are available", async () => {
    listPlatformMemberVerificationsMock.mockResolvedValue([
      createVerification({
        id: "verify-fallback-latest",
        accountId: "acct-h5",
        memberProfileId: "member-profile-other",
        userId: "user-other",
        publicUserId: "public-user-2",
        updatedAt: "2026-06-12T03:00:00Z",
      }),
      createVerification({
        id: "verify-fallback-older",
        accountId: "acct-h5",
        memberProfileId: "member-profile-other",
        userId: "user-other-2",
        publicUserId: "public-user-2",
        updatedAt: "2026-06-12T01:00:00Z",
      }),
      createVerification({
        id: "verify-other-account",
        accountId: "acct-other",
        publicUserId: "public-user-2",
      }),
    ]);
    listPlatformMemberWhatsAppBindingsMock.mockResolvedValue([
      createBinding({
        id: "binding-fallback",
        accountId: "acct-h5",
        memberProfileId: "member-profile-other",
        userId: "user-other",
        publicUserId: "public-user-2",
        updatedAt: "2026-06-12T03:30:00Z",
      }),
    ]);

    const snapshot = await getCustomerMemberStatusSnapshot(
      createProfile({
        id: "user-2",
        public_user_id: "public-user-2",
      })
    );

    expect(snapshot.verificationRequests.map((item) => item.id)).toEqual([
      "verify-fallback-latest",
      "verify-fallback-older",
    ]);
    expect(snapshot.bindingRequests.map((item) => item.id)).toEqual(["binding-fallback"]);
  });

  it("builds a platform user member status index with latest statuses and counts", async () => {
    listPlatformMemberVerificationsMock.mockResolvedValue([
      createVerification({
        id: "verify-user-1-approved",
        userId: "user-1",
        status: "approved",
        updatedAt: "2026-06-12T03:00:00Z",
      }),
      createVerification({
        id: "verify-user-1-pending",
        userId: "user-1",
        status: "pending",
        updatedAt: "2026-06-12T01:00:00Z",
      }),
      createVerification({
        id: "verify-user-2-rejected",
        userId: "user-2",
        publicUserId: "public-user-2",
        status: "rejected",
        updatedAt: "2026-06-12T02:00:00Z",
      }),
    ]);
    listPlatformMemberWhatsAppBindingsMock.mockResolvedValue([
      createBinding({
        id: "binding-user-1-bound",
        userId: "user-1",
        status: "bound",
        updatedAt: "2026-06-12T04:00:00Z",
      }),
      createBinding({
        id: "binding-user-2-failed",
        userId: "user-2",
        publicUserId: "public-user-2",
        status: "failed",
        updatedAt: "2026-06-12T05:00:00Z",
      }),
    ]);

    const index = await listPlatformUserMemberStatusIndex(
      [
        createProfile(),
        createProfile({
          id: "user-2",
          public_user_id: "public-user-2",
        }),
      ],
      "acct-h5"
    );

    expect(index["user-1"]).toMatchObject({
      latestVerificationStatus: "approved",
      latestBindingStatus: "bound",
      verificationCount: 2,
      bindingCount: 1,
    });
    expect(index["user-2"]).toMatchObject({
      latestVerificationStatus: "rejected",
      latestBindingStatus: "failed",
      verificationCount: 1,
      bindingCount: 1,
    });
  });

  it("requests the platform user status index without an account filter for mixed-scope users", async () => {
    listPlatformMemberVerificationsMock.mockResolvedValue([]);
    listPlatformMemberWhatsAppBindingsMock.mockResolvedValue([]);

    await listPlatformUserMemberStatusIndex([
      createProfile({
        account_id: null,
      }),
    ]);

    expect(listPlatformMemberVerificationsMock).toHaveBeenCalledWith({
      account_id: undefined,
    });
    expect(listPlatformMemberWhatsAppBindingsMock).toHaveBeenCalledWith({
      account_id: undefined,
    });
  });

  it("prefers an exact public user id match when selecting a customer profile for a conversation", () => {
    const selected = selectCustomerProfileForConversation(
      [
        createProfile({
          id: "user-identity",
          public_user_id: "public-user-other",
          relatedCustomerIds: ["wa-123"],
          identity_values: ["wa-123"],
          last_active_at: "2026-06-12T03:00:00Z",
        }),
        createProfile({
          id: "user-public",
          public_user_id: "wa-123",
          relatedCustomerIds: ["wa-123"],
          identity_values: [],
          last_active_at: "2026-06-12T01:00:00Z",
        }),
      ],
      {
        customer_id: "wa-123",
      } as { customer_id: string }
    );

    expect(selected?.id).toBe("user-public");
  });

  it("falls back to related customer ids and identity values when no public user id matches", () => {
    const selected = selectCustomerProfileForConversation(
      [
        createProfile({
          id: "user-older",
          public_user_id: "public-user-older",
          relatedCustomerIds: ["wa-456"],
          identity_values: [],
          last_active_at: "2026-06-12T01:00:00Z",
        }),
        createProfile({
          id: "user-latest",
          public_user_id: "public-user-latest",
          relatedCustomerIds: [],
          identity_values: ["wa-456"],
          last_active_at: "2026-06-12T05:00:00Z",
        }),
      ],
      {
        customer_id: "wa-456",
      } as { customer_id: string }
    );

    expect(selected?.id).toBe("user-latest");
  });
});
