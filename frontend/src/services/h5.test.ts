import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  createSupportTicket,
  getH5Bootstrap,
  getH5TaskDetail,
  listPlatformMemberVerifications,
  listPlatformMemberWhatsAppBindings,
  listH5Tasks,
  listSupportTickets,
  replySupportTicket,
  type SupportTicketCategory,
  type SupportTicketPriority,
  updatePlatformMemberVerificationStatus,
  updatePlatformMemberWhatsAppBindingStatus,
  uploadH5TaskProof,
} from "./h5";

const MEMBER_SESSION_KEY = "frontend.h5.member-session.v1";
const storage = new Map<string, string>();

function installLocalStorageMock(): void {
  Object.defineProperty(window, "localStorage", {
    configurable: true,
    value: {
      getItem(key: string): string | null {
        return storage.get(key) ?? null;
      },
      setItem(key: string, value: string): void {
        storage.set(key, value);
      },
      removeItem(key: string): void {
        storage.delete(key);
      },
      clear(): void {
        storage.clear();
      },
    },
  });
}

function writeMemberSession(): void {
  window.localStorage.setItem(
    MEMBER_SESSION_KEY,
    JSON.stringify({
      accountId: "38271456",
      phone: "13800000000",
      publicUserId: "h5-38271456",
      displayName: "Demo Member",
      inviteCode: "INV38271456",
    }),
  );
}

function createJsonResponse(payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

function createErrorResponse(status: number, detail: string): Response {
  return new Response(JSON.stringify({ detail }), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function createAuthResponse(): Response {
  return createJsonResponse({
    member: {
      userId: "user-1",
      publicUserId: "h5-38271456",
      accountId: "acct-h5",
      siteId: "site-1",
      siteKey: "mall-cn",
      memberNo: "38271456",
      accountIdMasked: "382***56",
      inviteCode: "INV-ABCD1234",
      phone: "13800000000",
      displayName: "Demo Member",
      languageCode: "zh-CN",
      createdAt: "2026-06-11T00:00:00Z",
      lastLoginAt: "2026-06-11T01:00:00Z",
    },
    site: {
      id: "site-1",
      accountId: "acct-h5",
      siteKey: "mall-cn",
      brandName: "Brand mall-cn",
      domain: "mall-cn.example.com",
      defaultLanguage: "zh-CN",
    },
    session: {
      expiresAt: "2026-06-12T00:00:00Z",
      refreshExpiresAt: "2026-06-18T00:00:00Z",
    },
  });
}

describe("H5 ticket auth contract", () => {
  beforeEach(() => {
    installLocalStorageMock();
    window.localStorage.clear();
    writeMemberSession();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("lists member tickets from the authenticated H5 endpoint without query identity", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(createAuthResponse())
      .mockResolvedValueOnce(createJsonResponse([
        {
          id: "ticket-1",
          account_id: "acct-h5",
          ticket_type: "help",
          status: "open",
          priority: "normal",
          site_id: "site-1",
          site_key: "mall-cn",
          user_id: "user-1",
          public_user_id: "h5-38271456",
          linked_task_instance_id: null,
          linked_submission_id: null,
          review_decision_id: null,
          title: "Need help",
          latest_reply_at: null,
          resolved_at: null,
          closed_at: null,
          is_active: true,
          messages: [],
          created_at: "2026-06-11T00:00:00Z",
          updated_at: "2026-06-11T00:00:00Z",
        },
      ]));
    vi.stubGlobal("fetch", fetchMock);

    await listSupportTickets();

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/h5/auth/me");
    expect(fetchMock.mock.calls[1]?.[0]).toBe("/api/h5/tickets");
    expect(fetchMock.mock.calls[1]?.[1]).toMatchObject({ credentials: "include" });
    expect(String(fetchMock.mock.calls[1]?.[0])).not.toContain("public_user_id");
    expect(String(fetchMock.mock.calls[1]?.[0])).not.toContain("site_key");
  });

  it("creates member tickets without posting client-supplied identity fields", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(createAuthResponse())
      .mockResolvedValueOnce(createJsonResponse({
        id: "ticket-2",
        account_id: "acct-h5",
        ticket_type: "help",
        status: "open",
        priority: "high",
        site_id: "site-1",
        site_key: "mall-cn",
        user_id: "user-1",
        public_user_id: "h5-38271456",
        linked_task_instance_id: null,
        linked_submission_id: null,
        review_decision_id: null,
        title: "Need help",
        latest_reply_at: null,
        resolved_at: null,
        closed_at: null,
        is_active: true,
        messages: [],
        created_at: "2026-06-11T00:00:00Z",
        updated_at: "2026-06-11T00:00:00Z",
      }));
    vi.stubGlobal("fetch", fetchMock);

    await createSupportTicket({
      category: "help" as SupportTicketCategory,
      priority: "high" as SupportTicketPriority,
      subject: "Need help",
      description: "Please check my ticket.",
    } as never);

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/h5/auth/me");
    expect(fetchMock.mock.calls[1]?.[0]).toBe("/api/h5/tickets");
    const request = fetchMock.mock.calls[1]?.[1];
    expect(request).toMatchObject({ credentials: "include" });
    const body = JSON.parse(String(request?.body)) as Record<string, unknown>;
    expect(body.ticket_type).toBe("help");
    expect(body.title).toBe("Need help");
    expect(body.body_text).toBe("Please check my ticket.");
    expect(body).not.toHaveProperty("account_id");
    expect(body).not.toHaveProperty("public_user_id");
    expect(body).not.toHaveProperty("site_key");
  });

  it("replies to tickets through authenticated H5 routes without query identity", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(createAuthResponse())
      .mockResolvedValueOnce(createJsonResponse({ id: "msg-1" }))
      .mockResolvedValueOnce(createAuthResponse())
      .mockResolvedValueOnce(
        createJsonResponse({
          id: "ticket-3",
          account_id: "acct-h5",
          ticket_type: "help",
          status: "in_progress",
          priority: "normal",
          site_id: "site-1",
          site_key: "mall-cn",
          user_id: "user-1",
          public_user_id: "h5-38271456",
          linked_task_instance_id: null,
          linked_submission_id: null,
          review_decision_id: null,
          title: "Need help",
          latest_reply_at: "2026-06-11T00:10:00Z",
          resolved_at: null,
          closed_at: null,
          is_active: true,
          messages: [
            {
              id: "msg-1",
              sender_type: "user",
              sender_id: "h5-38271456",
              body_text: "Please update me.",
              attachments_json: [],
              is_internal: false,
              created_at: "2026-06-11T00:10:00Z",
            },
          ],
          created_at: "2026-06-11T00:00:00Z",
          updated_at: "2026-06-11T00:10:00Z",
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    await replySupportTicket("ticket-3", {
      sender_type: "user",
      sender_name: "h5-38271456",
      content: "Please update me.",
    });

    expect(fetchMock).toHaveBeenCalledTimes(4);
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/h5/auth/me");
    expect(fetchMock.mock.calls[1]?.[0]).toBe("/api/h5/tickets/ticket-3/messages");
    expect(fetchMock.mock.calls[1]?.[1]).toMatchObject({ credentials: "include" });
    expect(String(fetchMock.mock.calls[1]?.[0])).not.toContain("public_user_id");
    expect(String(fetchMock.mock.calls[1]?.[0])).not.toContain("site_key");
    expect(fetchMock.mock.calls[2]?.[0]).toBe("/api/h5/auth/me");
    expect(fetchMock.mock.calls[3]?.[0]).toBe("/api/h5/tickets/ticket-3");
  });

  it("lists H5 tasks from the authenticated member route without query identity", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(createAuthResponse())
      .mockResolvedValueOnce(createJsonResponse([
        {
          id: "task-1",
          account_id: "acct-h5",
          public_user_id: "h5-38271456",
          site_key: "mall-cn",
          template_id: "template-1",
          task_key: "task-key-1",
          template_name: "Task Template",
          title: "Task Title",
          description: "Task Description",
          task_type: "shopping",
          reward_points: 20,
          claim_timeout_seconds: 3600,
          review_required: true,
          status: "available",
          latest_submission_id: null,
          available_at: "2026-06-11T00:00:00Z",
          claimed_at: null,
          claim_deadline_at: null,
          submitted_at: null,
          reviewed_at: null,
          completed_at: null,
          submission_note: null,
          submission_media_urls: [],
          submission_proofs: [],
          review_note: null,
          reviewer_id: null,
          latest_submission: null,
          latest_review_decision: null,
        },
      ]));
    vi.stubGlobal("fetch", fetchMock);

    await listH5Tasks();

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/h5/auth/me");
    expect(fetchMock.mock.calls[1]?.[0]).toBe("/api/h5/tasks");
    expect(fetchMock.mock.calls[1]?.[1]).toMatchObject({ credentials: "include" });
    expect(String(fetchMock.mock.calls[1]?.[0])).not.toContain("public_user_id");
    expect(String(fetchMock.mock.calls[1]?.[0])).not.toContain("site_key");
  });

  it("loads bootstrap from the authenticated member route without query identity", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(createAuthResponse())
      .mockResolvedValueOnce(createJsonResponse({
        site: {
          id: "site-1",
          site_key: "mall-cn",
          brand_name: "Brand mall-cn",
          domain: "mall-cn.example.com",
          default_language: "zh-CN",
        },
        user: {
          id: "user-1",
          public_user_id: "h5-38271456",
          display_name: "Demo Member",
          language_code: "zh-CN",
        },
        tasks: [],
        open_ticket_count: 0,
      }));
    vi.stubGlobal("fetch", fetchMock);

    await getH5Bootstrap();

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/h5/auth/me");
    expect(fetchMock.mock.calls[1]?.[0]).toBe("/api/h5/bootstrap");
    expect(fetchMock.mock.calls[1]?.[1]).toMatchObject({ credentials: "include" });
    expect(String(fetchMock.mock.calls[1]?.[0])).not.toContain("public_user_id");
    expect(String(fetchMock.mock.calls[1]?.[0])).not.toContain("site_key");
  });

  it("loads task detail from the authenticated member route without query identity", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(createAuthResponse())
      .mockResolvedValueOnce(createJsonResponse({
        id: "task-1",
        account_id: "acct-h5",
        public_user_id: "h5-38271456",
        site_key: "mall-cn",
        template_id: "template-1",
        task_key: "task-key-1",
        template_name: "Task Template",
        title: "Task Title",
        description: "Task Description",
        task_type: "shopping",
        reward_points: 20,
        claim_timeout_seconds: 3600,
        review_required: true,
        status: "available",
        latest_submission_id: null,
        available_at: "2026-06-11T00:00:00Z",
        claimed_at: null,
        claim_deadline_at: null,
        submitted_at: null,
        reviewed_at: null,
        completed_at: null,
        submission_note: null,
        submission_media_urls: [],
        submission_proofs: [],
        review_note: null,
        reviewer_id: null,
        latest_submission: null,
        latest_review_decision: null,
      }));
    vi.stubGlobal("fetch", fetchMock);

    await getH5TaskDetail("task-1");

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/h5/auth/me");
    expect(fetchMock.mock.calls[1]?.[0]).toBe("/api/h5/tasks/task-1");
    expect(fetchMock.mock.calls[1]?.[1]).toMatchObject({ credentials: "include" });
    expect(String(fetchMock.mock.calls[1]?.[0])).not.toContain("public_user_id");
    expect(String(fetchMock.mock.calls[1]?.[0])).not.toContain("site_key");
  });

  it("uploads task proofs through the authenticated endpoint without legacy identity form fields", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(createAuthResponse())
      .mockResolvedValueOnce(createJsonResponse({
        id: "proof-1",
        task_instance_id: "task-1",
        read_url: "https://example.com/proofs/proof-1.png",
        original_filename: "proof.png",
        mime_type: "image/png",
        size_bytes: 128,
        created_at: "2026-06-11T00:00:00Z",
      }));
    vi.stubGlobal("fetch", fetchMock);

    await uploadH5TaskProof("task-1", {
      public_user_id: "legacy-user-should-not-be-sent",
      site_key: "legacy-site-should-not-be-sent",
      file: new File(["proof"], "proof.png", { type: "image/png" }),
    });

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/h5/auth/me");
    expect(fetchMock.mock.calls[1]?.[0]).toBe("/api/h5/task-proofs");
    const request = fetchMock.mock.calls[1]?.[1];
    expect(request).toMatchObject({ method: "POST", credentials: "include" });
    expect(request?.body).toBeInstanceOf(FormData);
    const formData = request?.body as FormData;
    expect(formData.get("task_instance_id")).toBe("task-1");
    expect(formData.get("file")).toBeInstanceOf(File);
    expect(formData.has("public_user_id")).toBe(false);
    expect(formData.has("site_key")).toBe(false);
  });

  it("refreshes the H5 auth session after auth/me returns 401 before retrying authenticated proof upload", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(createErrorResponse(401, "Session expired"))
      .mockResolvedValueOnce(createAuthResponse())
      .mockResolvedValueOnce(createAuthResponse())
      .mockResolvedValueOnce(createJsonResponse({
        id: "proof-2",
        task_instance_id: "task-1",
        read_url: "https://example.com/proofs/proof-2.png",
        original_filename: "proof-2.png",
        mime_type: "image/png",
        size_bytes: 256,
        created_at: "2026-06-11T00:05:00Z",
      }));
    vi.stubGlobal("fetch", fetchMock);

    const proof = await uploadH5TaskProof("task-1", {
      file: new File(["proof"], "proof-2.png", { type: "image/png" }),
    });

    expect(proof.id).toBe("proof-2");
    expect(fetchMock).toHaveBeenCalledTimes(4);
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/h5/auth/me");
    expect(fetchMock.mock.calls[1]?.[0]).toBe("/api/h5/auth/refresh");
    expect(fetchMock.mock.calls[2]?.[0]).toBe("/api/h5/auth/me");
    expect(fetchMock.mock.calls[3]?.[0]).toBe("/api/h5/task-proofs");
    expect(fetchMock.mock.calls[1]?.[1]).toMatchObject({
      method: "POST",
      credentials: "include",
    });
    const request = fetchMock.mock.calls[3]?.[1];
    expect(request).toMatchObject({ method: "POST", credentials: "include" });
    expect(request?.body).toBeInstanceOf(FormData);
    const formData = request?.body as FormData;
    expect(formData.get("task_instance_id")).toBe("task-1");
    expect(formData.has("public_user_id")).toBe(false);
    expect(formData.has("site_key")).toBe(false);
  });

  it("bubbles unauthenticated upload failure after refresh fails during proof upload", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(createErrorResponse(401, "Session expired"))
      .mockResolvedValueOnce(createErrorResponse(401, "Refresh expired"))
      .mockResolvedValueOnce(createErrorResponse(401, "Authentication required"))
      .mockResolvedValueOnce(createErrorResponse(401, "Refresh expired"));
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      uploadH5TaskProof("task-1", {
        file: new File(["proof"], "proof-3.png", { type: "image/png" }),
      }),
    ).rejects.toThrow();

    expect(fetchMock).toHaveBeenCalledTimes(4);
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/h5/auth/me");
    expect(fetchMock.mock.calls[1]?.[0]).toBe("/api/h5/auth/refresh");
    expect(fetchMock.mock.calls[2]?.[0]).toBe("/api/h5/task-proofs");
    expect(fetchMock.mock.calls[3]?.[0]).toBe("/api/h5/auth/refresh");
  });

  it("refreshes and retries when the proof upload endpoint itself returns 401", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(createAuthResponse())
      .mockResolvedValueOnce(createErrorResponse(401, "Upload session expired"))
      .mockResolvedValueOnce(createAuthResponse())
      .mockResolvedValueOnce(createJsonResponse({
        id: "proof-4",
        task_instance_id: "task-1",
        read_url: "https://example.com/proofs/proof-4.png",
        original_filename: "proof-4.png",
        mime_type: "image/png",
        size_bytes: 64,
        created_at: "2026-06-11T00:10:00Z",
      }));
    vi.stubGlobal("fetch", fetchMock);

    const proof = await uploadH5TaskProof("task-1", {
      file: new File(["proof"], "proof-4.png", { type: "image/png" }),
    });

    expect(proof.id).toBe("proof-4");
    expect(fetchMock).toHaveBeenCalledTimes(4);
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/h5/auth/me");
    expect(fetchMock.mock.calls[1]?.[0]).toBe("/api/h5/task-proofs");
    expect(fetchMock.mock.calls[2]?.[0]).toBe("/api/h5/auth/refresh");
    expect(fetchMock.mock.calls[3]?.[0]).toBe("/api/h5/task-proofs");
    expect(fetchMock.mock.calls[2]?.[1]).toMatchObject({
      method: "POST",
      credentials: "include",
    });
    expect(fetchMock.mock.calls[3]?.[1]).toMatchObject({
      method: "POST",
      credentials: "include",
    });
  });
});

describe("Platform member review contracts", () => {
  beforeEach(() => {
    installLocalStorageMock();
    window.localStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("lists platform member verifications with account and status filters", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(createJsonResponse([
      {
        id: "verify-1",
        accountId: "acct-h5",
        memberProfileId: "member-profile-1",
        userId: "user-1",
        publicUserId: "h5-38271456",
        memberNo: "38271456",
        displayName: "Demo Member",
        requestType: "identity",
        status: "pending",
        notes: "passport review",
        reviewNote: null,
        reviewerActorId: null,
        createdAt: "2026-06-12T00:00:00Z",
        updatedAt: "2026-06-12T00:00:00Z",
        reviewedAt: null,
        documents: [
          {
            id: "doc-1",
            fileName: "passport-front.png",
            mimeType: "image/png",
            storageKey: "member-verification/passport-front.png",
            metadataJson: { side: "front" },
            createdAt: "2026-06-12T00:00:00Z",
          },
        ],
      },
    ]));
    vi.stubGlobal("fetch", fetchMock);

    const requests = await listPlatformMemberVerifications({
      account_id: "acct-h5",
      status: "pending",
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      "/api/platform/member-verifications?account_id=acct-h5&status=pending",
    );
    expect(fetchMock.mock.calls[0]?.[1]).toMatchObject({
      headers: expect.objectContaining({
        "X-Actor-Role": "super_admin",
      }),
    });
    expect(requests[0]).toMatchObject({
      id: "verify-1",
      accountId: "acct-h5",
      memberNo: "38271456",
      status: "pending",
      documents: [
        expect.objectContaining({
          id: "doc-1",
          fileName: "passport-front.png",
        }),
      ],
    });
  });

  it("updates platform member verification review status with note payload", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(createJsonResponse({
      id: "verify-2",
      accountId: "acct-h5",
      memberProfileId: "member-profile-2",
      userId: "user-2",
      publicUserId: "h5-99887766",
      memberNo: "99887766",
      displayName: "Reviewed Member",
      requestType: "identity",
      status: "approved",
      notes: "passport review",
      reviewNote: "资料一致",
      reviewerActorId: "agent-cn-console",
      createdAt: "2026-06-12T00:00:00Z",
      updatedAt: "2026-06-12T01:00:00Z",
      reviewedAt: "2026-06-12T01:00:00Z",
      documents: [],
    }));
    vi.stubGlobal("fetch", fetchMock);

    const response = await updatePlatformMemberVerificationStatus("verify-2", {
      status: "approved",
      note: "资料一致",
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/platform/member-verifications/verify-2/status");
    expect(fetchMock.mock.calls[0]?.[1]).toMatchObject({
      method: "POST",
      headers: expect.objectContaining({
        "Content-Type": "application/json",
      }),
      body: JSON.stringify({
        status: "approved",
        note: "资料一致",
      }),
    });
    expect(response).toMatchObject({
      id: "verify-2",
      status: "approved",
      reviewNote: "资料一致",
    });
  });

  it("lists platform member WhatsApp bindings with account and status filters", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(createJsonResponse([
      {
        id: "binding-1",
        accountId: "acct-h5",
        userId: "user-1",
        memberProfileId: "member-profile-1",
        siteId: "site-1",
        siteKey: "mall-cn",
        publicUserId: "h5-38271456",
        memberNo: "38271456",
        displayName: "Demo Member",
        status: "pending",
        requestedPhoneNumber: "13800000000",
        startCount: 2,
        lastError: null,
        createdAt: "2026-06-12T00:00:00Z",
        updatedAt: "2026-06-12T00:10:00Z",
        lastStartedAt: "2026-06-12T00:10:00Z",
        boundAt: null,
      },
    ]));
    vi.stubGlobal("fetch", fetchMock);

    const requests = await listPlatformMemberWhatsAppBindings({
      account_id: "acct-h5",
      status: "pending",
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      "/api/platform/member-whatsapp-bindings?account_id=acct-h5&status=pending",
    );
    expect(requests[0]).toMatchObject({
      id: "binding-1",
      memberNo: "38271456",
      requestedPhoneNumber: "13800000000",
      startCount: 2,
      status: "pending",
    });
  });

  it("updates platform member WhatsApp binding status with failure note", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(createJsonResponse({
      id: "binding-2",
      accountId: "acct-h5",
      userId: "user-2",
      memberProfileId: "member-profile-2",
      siteId: "site-1",
      siteKey: "mall-cn",
      publicUserId: "h5-99887766",
      memberNo: "99887766",
      displayName: "Binding Member",
      status: "failed",
      requestedPhoneNumber: "13900000000",
      startCount: 1,
      lastError: "号码未匹配",
      createdAt: "2026-06-12T00:00:00Z",
      updatedAt: "2026-06-12T01:00:00Z",
      lastStartedAt: "2026-06-12T00:05:00Z",
      boundAt: null,
    }));
    vi.stubGlobal("fetch", fetchMock);

    const response = await updatePlatformMemberWhatsAppBindingStatus("binding-2", {
      status: "failed",
      note: "号码未匹配",
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/platform/member-whatsapp-bindings/binding-2/status");
    expect(fetchMock.mock.calls[0]?.[1]).toMatchObject({
      method: "POST",
      headers: expect.objectContaining({
        "Content-Type": "application/json",
      }),
      body: JSON.stringify({
        status: "failed",
        note: "号码未匹配",
      }),
    });
    expect(response).toMatchObject({
      id: "binding-2",
      status: "failed",
      lastError: "号码未匹配",
    });
  });
});
