import {
  listTaskInstances,
  listTaskTemplates,
  type TaskInstance,
  type TaskTemplate
} from "./api";
import { getCurrentMemberSession, H5AuthRequiredError } from "./h5Member";
import { useAppStore } from "../stores/appStore";

export type H5TaskStatus =
  | "available"
  | "claimed"
  | "submitted"
  | "pending_review"
  | "changes_requested"
  | "appealing"
  | "approved"
  | "rejected"
  | "expired"
  | "abandoned"
  | "cancelled"
  | "completed";

export type H5TaskItem = {
  id: string;
  account_id: string;
  public_user_id: string;
  site_key: string | null;
  template_id: string;
  task_key: string;
  template_name: string;
  title: string;
  description: string | null;
  task_type: string;
  reward_points: number;
  claim_timeout_seconds: number;
  review_required: boolean;
  status: H5TaskStatus;
  latest_submission_id: string | null;
  available_at: string;
  claimed_at: string | null;
  claim_deadline_at: string | null;
  submitted_at: string | null;
  reviewed_at: string | null;
  completed_at: string | null;
  submission_note: string | null;
  submission_media_urls: string[];
  submission_proofs: H5TaskProofFile[];
  review_note: string | null;
  reviewer_id: string | null;
  latest_submission: H5LatestSubmission | null;
  latest_review_decision: H5LatestReviewDecision | null;
};

export type H5Context = {
  site_key?: string;
  public_user_id?: string;
};

export type H5Bootstrap = {
  site: {
    id: string;
    site_key: string;
    brand_name: string;
    domain: string;
    default_language: string;
  };
  user: {
    id: string;
    public_user_id: string;
    display_name: string | null;
    language_code: string;
  };
  tasks: H5TaskItem[];
  open_ticket_count: number;
};

export type H5TaskProofFile = {
  id: string;
  task_instance_id: string;
  read_url: string | null;
  original_filename: string;
  mime_type: string;
  size_bytes: number;
  created_at: string;
};

export type H5LatestSubmission = {
  id: string;
  submission_no: number;
  status: string;
  submitted_at: string;
  review_started_at: string | null;
  review_completed_at: string | null;
  payload_json: Record<string, unknown>;
  proofs: H5TaskProofFile[];
};

export type H5LatestReviewDecision = {
  id: string;
  decision: string;
  decision_source: string;
  reviewer_actor_id: string | null;
  reason_code: string | null;
  reason_text: string | null;
  created_at: string;
};

export type ReviewQueueItem = H5TaskItem & {
  submission_id: string;
  queue_status: "pending_review" | "approved" | "rejected";
  wait_minutes: number;
  priority: "high" | "normal";
};

export type ReviewDecisionPayload = {
  decision: "approved" | "rejected";
  note?: string;
  reviewer_id: string;
};

export type PlatformMemberVerificationStatus =
  | "pending"
  | "under_review"
  | "approved"
  | "rejected";

export type PlatformMemberVerificationTransitionStatus =
  | "under_review"
  | "approved"
  | "rejected";

export type PlatformMemberVerificationDocument = {
  id: string;
  fileName: string;
  mimeType: string | null;
  storageKey: string | null;
  metadataJson: Record<string, unknown> | null;
  createdAt: string;
};

export type PlatformMemberVerificationRequest = {
  id: string;
  accountId: string;
  memberProfileId: string;
  userId: string;
  publicUserId: string;
  memberNo: string;
  displayName: string | null;
  requestType: string;
  status: PlatformMemberVerificationStatus;
  notes: string | null;
  reviewNote: string | null;
  reviewerActorId: string | null;
  createdAt: string;
  updatedAt: string;
  reviewedAt: string | null;
  documents: PlatformMemberVerificationDocument[];
};

export type PlatformMemberVerificationStatusUpdatePayload = {
  status: PlatformMemberVerificationTransitionStatus;
  note?: string;
};

export type PlatformMemberWhatsAppBindingStatus = "pending" | "bound" | "failed";

export type PlatformMemberWhatsAppBindingRequest = {
  id: string;
  accountId: string;
  userId: string;
  memberProfileId: string;
  siteId: string | null;
  siteKey: string | null;
  publicUserId: string;
  memberNo: string;
  displayName: string | null;
  status: PlatformMemberWhatsAppBindingStatus;
  requestedPhoneNumber: string | null;
  startCount: number;
  lastError: string | null;
  createdAt: string;
  updatedAt: string;
  lastStartedAt: string | null;
  boundAt: string | null;
};

export type PlatformMemberWhatsAppBindingStatusUpdatePayload = {
  status: PlatformMemberWhatsAppBindingStatus;
  note?: string;
};

export type H5TaskSubmissionPayload = {
  public_user_id?: string;
  site_key?: string;
  note: string;
  media_urls: string[];
  proof_file_ids?: string[];
};

export type SupportTicketCategory = "task_appeal" | "help" | "complaint";
export type SupportTicketStatus =
  | "open"
  | "in_progress"
  | "pending_user"
  | "resolved"
  | "rejected"
  | "closed"
  | "cancelled";
export type SupportTicketPriority = "low" | "normal" | "high" | "urgent";

export type SupportTicketMessage = {
  id: string;
  sender_type: "user" | "agent" | "system";
  sender_name: string;
  content: string;
  created_at: string;
  internal_only: boolean;
};

export type SupportTicket = {
  id: string;
  account_id: string;
  user_id?: string | null;
  public_user_id: string;
  category: SupportTicketCategory;
  status: SupportTicketStatus;
  priority: SupportTicketPriority;
  subject: string;
  content_preview: string;
  linked_task_instance_id: string | null;
  source: "h5" | "console";
  created_at: string;
  updated_at: string;
  last_reply_at: string | null;
};

export type SupportTicketDetail = SupportTicket & {
  description: string;
  messages: SupportTicketMessage[];
};

export type SupportTicketCreatePayload = {
  account_id?: string;
  public_user_id?: string;
  site_key?: string;
  category: SupportTicketCategory;
  priority: SupportTicketPriority;
  subject: string;
  description: string;
  linked_task_instance_id?: string;
  linked_submission_id?: string;
};

export type SupportTicketReplyPayload = {
  sender_type: "user" | "agent" | "system";
  sender_name: string;
  content: string;
  internal_only?: boolean;
  next_status?: SupportTicketStatus;
};

export type SupportTicketStatusPayload = {
  status: SupportTicketStatus;
  actor_name: string;
  note?: string;
};

export function getSupportTicketStatusLabel(status: SupportTicketStatus): string {
  switch (status) {
    case "open":
      return "待处理";
    case "in_progress":
      return "处理中";
    case "pending_user":
      return "待用户补充";
    case "resolved":
      return "已解决";
    case "rejected":
      return "已驳回";
    case "closed":
      return "已关闭";
    case "cancelled":
      return "已取消";
    default:
      return status;
  }
}

const SUPPORT_TICKET_STATUS_TRANSITIONS: Record<SupportTicketStatus, SupportTicketStatus[]> = {
  open: ["in_progress", "pending_user", "resolved", "rejected", "cancelled"],
  in_progress: ["pending_user", "resolved", "rejected", "cancelled"],
  pending_user: ["in_progress", "resolved", "rejected", "cancelled"],
  resolved: ["closed", "in_progress"],
  rejected: ["closed"],
  closed: [],
  cancelled: [],
};

export function isSupportTicketTerminalStatus(status: SupportTicketStatus): boolean {
  return status === "rejected" || status === "closed" || status === "cancelled";
}

export function getSupportTicketAllowedTransitions(
  status: SupportTicketStatus,
): SupportTicketStatus[] {
  return SUPPORT_TICKET_STATUS_TRANSITIONS[status];
}

function canSupportTicketTransition(
  currentStatus: SupportTicketStatus,
  targetStatus: SupportTicketStatus,
): boolean {
  return (
    currentStatus === targetStatus ||
    SUPPORT_TICKET_STATUS_TRANSITIONS[currentStatus].includes(targetStatus)
  );
}

function resolveLocalReplyTicketStatus(
  currentStatus: SupportTicketStatus,
  payload: SupportTicketReplyPayload,
): SupportTicketStatus {
  if (payload.next_status && canSupportTicketTransition(currentStatus, payload.next_status)) {
    return payload.next_status;
  }
  if (payload.sender_type === "user" && currentStatus === "pending_user") {
    return "in_progress";
  }
  return currentStatus;
}

type StoredTaskSubmission = {
  task_id: string;
  public_user_id: string;
  note: string;
  media_urls: string[];
  proof_file_ids?: string[];
  submitted_at: string;
};

type StoredReviewDecision = {
  task_id: string;
  decision: "approved" | "rejected";
  note: string;
  reviewer_id: string;
  reviewed_at: string;
};

type StoredTicketRecord = {
  id: string;
  account_id: string;
  user_id?: string | null;
  public_user_id: string;
  category: SupportTicketCategory;
  status: SupportTicketStatus;
  priority: SupportTicketPriority;
  subject: string;
  description: string;
  linked_task_instance_id: string | null;
  source: "h5" | "console";
  created_at: string;
  updated_at: string;
  last_reply_at: string | null;
  messages: SupportTicketMessage[];
};

const TASK_SUBMISSIONS_KEY = "frontend.h5.task-submissions.v1";
const TASK_REVIEWS_KEY = "frontend.h5.task-reviews.v1";
const SUPPORT_TICKETS_KEY = "frontend.h5.support-tickets.v1";
const DEFAULT_SITE_KEY = "mall-cn";
const DEFAULT_USER_ID = "user-demo-01";
function getAdminHeaders(contentType = true): HeadersInit {
  const actor = useAppStore.getState();
  const headers: Record<string, string> = {
    "X-Actor-Id": actor.consoleAgentId,
    "X-Actor-Name": actor.consoleAgentName,
    "X-Actor-Role": actor.actorRole,
    "X-Actor-Account-Ids": actor.actorAccountIds.join(",")
  };
  if (contentType) {
    headers["Content-Type"] = "application/json";
  }
  return headers;
}

function isBrowser(): boolean {
  return typeof window !== "undefined" && typeof window.localStorage !== "undefined";
}

function nowIso(): string {
  return new Date().toISOString();
}

function createId(prefix: string): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return `${prefix}-${crypto.randomUUID()}`;
  }
  return `${prefix}-${Math.random().toString(36).slice(2, 10)}`;
}

function minutesAgo(minutes: number): string {
  return new Date(Date.now() - minutes * 60_000).toISOString();
}

function readStorage<T>(key: string, fallback: T): T {
  if (!isBrowser()) {
    return fallback;
  }
  const raw = window.localStorage.getItem(key);
  if (!raw) {
    return fallback;
  }
  try {
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

function writeStorage<T>(key: string, value: T): void {
  if (!isBrowser()) {
    return;
  }
  window.localStorage.setItem(key, JSON.stringify(value));
}

function seedTaskTemplates(): TaskTemplate[] {
  const createdAt = minutesAgo(60 * 24 * 7);
  return [
    {
      id: "tpl-proof-order",
      account_id: "acct-cn-main",
      task_key: "proof-order",
      name: "订单截图任务",
      title: "上传订单完成截图",
      description: "提交订单详情页和支付成功页截图，系统会先走自动审核，再进入人工复核。",
      task_type: "shopping",
      status: "active",
      audience_rule_set_id: null,
      reward_amount: null,
      reward_points: 80,
      claim_timeout_seconds: 86400,
      auto_review_enabled: true,
      metadata_json: { account_id: "acct-cn-main" },
      created_at: createdAt,
      updated_at: createdAt
    },
    {
      id: "tpl-invite-share",
      account_id: "acct-cn-main",
      task_key: "invite-share",
      name: "邀请分享任务",
      title: "提交邀请结果",
      description: "分享邀请码后，填写邀请对象和截图，审核通过后发放奖励。",
      task_type: "invite",
      status: "active",
      audience_rule_set_id: null,
      reward_amount: null,
      reward_points: 120,
      claim_timeout_seconds: 172800,
      auto_review_enabled: false,
      metadata_json: { account_id: "acct-cn-main" },
      created_at: createdAt,
      updated_at: createdAt
    },
    {
      id: "tpl-checkin",
      account_id: "acct-global-growth",
      task_key: "daily-checkin",
      name: "每日签到任务",
      title: "完成今日签到",
      description: "进入 H5 活动页完成签到，部分实例不需要人工审核。",
      task_type: "daily",
      status: "active",
      audience_rule_set_id: null,
      reward_amount: null,
      reward_points: 10,
      claim_timeout_seconds: 43200,
      auto_review_enabled: true,
      metadata_json: { account_id: "acct-global-growth" },
      created_at: createdAt,
      updated_at: createdAt
    }
  ];
}

function seedTaskInstances(): TaskInstance[] {
  const createdAt = minutesAgo(60 * 24 * 2);
  return [
    {
      id: "task-1001",
      account_id: "acct-cn-main",
      template_id: "tpl-proof-order",
      template_task_key: "proof-order",
      template_name: "订单截图任务",
      user_id: "user-001",
      public_user_id: "user-demo-01",
      site_id: "site-01",
      site_key: "mall-cn",
      status: "available",
      claim_timeout_seconds_snapshot: 86400,
      review_required: true,
      available_at: minutesAgo(60 * 12),
      claimed_at: null,
      claim_deadline_at: null,
      submitted_at: null,
      reviewed_at: null,
      completed_at: null,
      expired_at: null,
      metadata_json: { account_id: "acct-cn-main" },
      created_at: createdAt,
      updated_at: createdAt
    },
    {
      id: "task-1002",
      account_id: "acct-cn-main",
      template_id: "tpl-invite-share",
      template_task_key: "invite-share",
      template_name: "邀请分享任务",
      user_id: "user-002",
      public_user_id: "user-demo-01",
      site_id: "site-01",
      site_key: "mall-cn",
      status: "claimed",
      claim_timeout_seconds_snapshot: 172800,
      review_required: true,
      available_at: minutesAgo(60 * 26),
      claimed_at: minutesAgo(60 * 4),
      claim_deadline_at: minutesAgo(-60 * 20),
      submitted_at: null,
      reviewed_at: null,
      completed_at: null,
      expired_at: null,
      metadata_json: { account_id: "acct-cn-main" },
      created_at: createdAt,
      updated_at: minutesAgo(60 * 4)
    },
    {
      id: "task-1003",
      account_id: "acct-global-growth",
      template_id: "tpl-proof-order",
      template_task_key: "proof-order",
      template_name: "订单截图任务",
      user_id: "user-003",
      public_user_id: "user-demo-02",
      site_id: "site-02",
      site_key: "flash-sale",
      status: "submitted",
      claim_timeout_seconds_snapshot: 86400,
      review_required: true,
      available_at: minutesAgo(60 * 30),
      claimed_at: minutesAgo(60 * 18),
      claim_deadline_at: minutesAgo(-60 * 6),
      submitted_at: minutesAgo(95),
      reviewed_at: null,
      completed_at: null,
      expired_at: null,
      metadata_json: { account_id: "acct-global-growth" },
      created_at: createdAt,
      updated_at: minutesAgo(95)
    },
    {
      id: "task-1004",
      account_id: "acct-global-growth",
      template_id: "tpl-checkin",
      template_task_key: "daily-checkin",
      template_name: "每日签到任务",
      user_id: "user-004",
      public_user_id: "user-demo-01",
      site_id: "site-03",
      site_key: "daily-cn",
      status: "completed",
      claim_timeout_seconds_snapshot: 43200,
      review_required: false,
      available_at: minutesAgo(60 * 20),
      claimed_at: minutesAgo(60 * 6),
      claim_deadline_at: minutesAgo(-60 * 6),
      submitted_at: minutesAgo(60 * 5),
      reviewed_at: minutesAgo(60 * 5),
      completed_at: minutesAgo(60 * 5),
      expired_at: null,
      metadata_json: { account_id: "acct-global-growth" },
      created_at: createdAt,
      updated_at: minutesAgo(60 * 5)
    }
  ];
}

function seedTicketRecords(): StoredTicketRecord[] {
  return [
    {
      id: "ticket-2001",
      account_id: "acct-cn-main",
      public_user_id: "user-demo-01",
      category: "help",
      status: "open",
      priority: "high",
      subject: "任务截图提交状态咨询",
      description: "我已经在昨晚上传证明材料，页面还没有显示审核结果，想确认是否已经进入审核队列。",
      linked_task_instance_id: "task-1002",
      source: "h5",
      created_at: minutesAgo(180),
      updated_at: minutesAgo(180),
      last_reply_at: minutesAgo(165),
      messages: [
        {
          id: "ticket-2001-msg-1",
          sender_type: "user",
          sender_name: "user-demo-01",
          content: "我已经在昨晚上传证明材料，页面还没有显示审核结果，想确认是否已经进入审核队列。",
          created_at: minutesAgo(180),
          internal_only: false
        },
        {
          id: "ticket-2001-msg-2",
          sender_type: "agent",
          sender_name: "审核坐席 A",
          content: "已收到，先帮你核对任务实例和提交流水，处理完会在这里回复。",
          created_at: minutesAgo(165),
          internal_only: false
        }
      ]
    },
    {
      id: "ticket-2002",
      account_id: "acct-global-growth",
      public_user_id: "user-demo-02",
      category: "complaint",
      status: "pending_user",
      priority: "normal",
      subject: "奖励到账时间确认",
      description: "审核通过后多久发奖励？页面上没有看到明确时效。",
      linked_task_instance_id: "task-1003",
      source: "h5",
      created_at: minutesAgo(320),
      updated_at: minutesAgo(240),
      last_reply_at: minutesAgo(240),
      messages: [
        {
          id: "ticket-2002-msg-1",
          sender_type: "user",
          sender_name: "user-demo-02",
          content: "审核通过后多久发奖励？页面上没有看到明确时效。",
          created_at: minutesAgo(320),
          internal_only: false
        },
        {
          id: "ticket-2002-msg-2",
          sender_type: "agent",
          sender_name: "客服 Luna",
          content: "通常是通过后 10 分钟内到账。若超时，可以继续补充工单。",
          created_at: minutesAgo(240),
          internal_only: false
        }
      ]
    }
  ];
}

function readTaskSubmissions(): StoredTaskSubmission[] {
  return readStorage<StoredTaskSubmission[]>(TASK_SUBMISSIONS_KEY, []);
}

function writeTaskSubmissions(entries: StoredTaskSubmission[]): void {
  writeStorage(TASK_SUBMISSIONS_KEY, entries);
}

function readReviewDecisions(): StoredReviewDecision[] {
  return readStorage<StoredReviewDecision[]>(TASK_REVIEWS_KEY, []);
}

function writeReviewDecisions(entries: StoredReviewDecision[]): void {
  writeStorage(TASK_REVIEWS_KEY, entries);
}

function readTicketRecords(): StoredTicketRecord[] {
  const seeded = seedTicketRecords();
  const stored = readStorage<StoredTicketRecord[]>(SUPPORT_TICKETS_KEY, seeded);
  if (!isBrowser()) {
    return stored;
  }
  if (!window.localStorage.getItem(SUPPORT_TICKETS_KEY)) {
    writeStorage(SUPPORT_TICKETS_KEY, stored);
  }
  return stored;
}

function writeTicketRecords(entries: StoredTicketRecord[]): void {
  writeStorage(SUPPORT_TICKETS_KEY, entries);
}

async function loadBaseTaskData(): Promise<{ templates: TaskTemplate[]; instances: TaskInstance[] }> {
  const [templatesResult, instancesResult] = await Promise.allSettled([
    listTaskTemplates(),
    listTaskInstances()
  ]);

  const templates =
    templatesResult.status === "fulfilled" && templatesResult.value.length > 0
      ? templatesResult.value
      : seedTaskTemplates();
  const instances =
    instancesResult.status === "fulfilled" && instancesResult.value.length > 0
      ? instancesResult.value
      : seedTaskInstances();

  return { templates, instances };
}

function mapTaskStatus(
  instance: TaskInstance,
  submission: StoredTaskSubmission | undefined,
  review: StoredReviewDecision | undefined
): H5TaskStatus {
  const normalizedInstanceStatus = normalizeH5TaskStatus(instance.status, instance.review_required);
  if (review?.decision === "approved") {
    return "approved";
  }
  if (review?.decision === "rejected") {
    return "rejected";
  }
  if (instance.completed_at || normalizedInstanceStatus === "completed") {
    return "completed";
  }
  if (
    normalizedInstanceStatus === "approved" ||
    normalizedInstanceStatus === "rejected" ||
    normalizedInstanceStatus === "changes_requested" ||
    normalizedInstanceStatus === "appealing" ||
    normalizedInstanceStatus === "expired" ||
    normalizedInstanceStatus === "abandoned" ||
    normalizedInstanceStatus === "cancelled"
  ) {
    return normalizedInstanceStatus;
  }
  if (submission || instance.submitted_at || normalizedInstanceStatus === "pending_review") {
    return instance.review_required ? "pending_review" : "submitted";
  }
  if (instance.claimed_at || normalizedInstanceStatus === "claimed") {
    return "claimed";
  }
  return "available";
}

function mapTaskItem(
  instance: TaskInstance,
  templatesById: Map<string, TaskTemplate>,
  submissionsByTask: Map<string, StoredTaskSubmission>,
  reviewsByTask: Map<string, StoredReviewDecision>
): H5TaskItem {
  const template = templatesById.get(instance.template_id);
  const submission = submissionsByTask.get(instance.id);
  const review = reviewsByTask.get(instance.id);
  const proofFiles = (submission?.media_urls ?? []).map((url, index) => ({
    id: `${instance.id}-proof-${index}`,
    task_instance_id: instance.id,
    read_url: url,
    original_filename: `proof-${index + 1}`,
    mime_type: "text/uri-list",
    size_bytes: 0,
    created_at: submission?.submitted_at ?? instance.submitted_at ?? nowIso()
  }));
  const latestSubmissionId = submission ? `${instance.id}-submission` : null;
  const metadataAccountId =
    instance.metadata_json && typeof instance.metadata_json.account_id === "string"
      ? instance.metadata_json.account_id
      : template?.metadata_json && typeof template.metadata_json.account_id === "string"
        ? template.metadata_json.account_id
        : "acct-unscoped";

  return {
    id: instance.id,
    account_id: metadataAccountId,
    public_user_id: instance.public_user_id,
    site_key: instance.site_key,
    template_id: instance.template_id,
    task_key: instance.template_task_key,
    template_name: instance.template_name,
    title: template?.title ?? instance.template_name,
    description: template?.description ?? null,
    task_type: template?.task_type ?? "generic",
    reward_points: template?.reward_points ?? 0,
    claim_timeout_seconds: instance.claim_timeout_seconds_snapshot,
    review_required: instance.review_required,
    status: mapTaskStatus(instance, submission, review),
    latest_submission_id: latestSubmissionId,
    available_at: instance.available_at,
    claimed_at: instance.claimed_at,
    claim_deadline_at: instance.claim_deadline_at,
    submitted_at: submission?.submitted_at ?? instance.submitted_at,
    reviewed_at: review?.reviewed_at ?? instance.reviewed_at,
    completed_at: instance.completed_at,
    submission_note: submission?.note ?? null,
    submission_media_urls: submission?.media_urls ?? [],
    submission_proofs: proofFiles,
    review_note: review?.note ?? null,
    reviewer_id: review?.reviewer_id ?? null,
    latest_submission: submission
      ? {
          id: latestSubmissionId ?? `${instance.id}-submission`,
          submission_no: 1,
          status: review?.decision ?? (instance.review_required ? "under_review" : "submitted"),
          submitted_at: submission.submitted_at,
          review_started_at: submission.submitted_at,
          review_completed_at: review?.reviewed_at ?? null,
          payload_json: {
            notes: submission.note,
            media_urls: submission.media_urls
          },
          proofs: proofFiles
        }
      : null,
    latest_review_decision: review
      ? {
          id: `${instance.id}-review`,
          decision: review.decision,
          decision_source: "manual",
          reviewer_actor_id: review.reviewer_id,
          reason_code: null,
          reason_text: review.note,
          created_at: review.reviewed_at
        }
      : null
  };
}

async function loadTaskCatalog(): Promise<H5TaskItem[]> {
  const { templates, instances } = await loadBaseTaskData();
  const templatesById = new Map(templates.map((template) => [template.id, template]));
  const submissionsByTask = new Map(readTaskSubmissions().map((item) => [item.task_id, item]));
  const reviewsByTask = new Map(readReviewDecisions().map((item) => [item.task_id, item]));

  return instances
    .map((instance) => mapTaskItem(instance, templatesById, submissionsByTask, reviewsByTask))
    .sort((left, right) => right.available_at.localeCompare(left.available_at));
}

function mapTicketSummary(record: StoredTicketRecord): SupportTicket {
  return {
    id: record.id,
    account_id: record.account_id,
    user_id: record.user_id ?? null,
    public_user_id: record.public_user_id,
    category: record.category,
    status: normalizeSupportTicketStatus(record.status),
    priority: record.priority,
    subject: record.subject,
    content_preview: record.description,
    linked_task_instance_id: record.linked_task_instance_id,
    source: record.source,
    created_at: record.created_at,
    updated_at: record.updated_at,
    last_reply_at: record.last_reply_at
  };
}

function mapTicketDetail(record: StoredTicketRecord): SupportTicketDetail {
  return {
    ...mapTicketSummary(record),
    description: record.description,
    messages: [...record.messages].sort((left, right) => left.created_at.localeCompare(right.created_at))
  };
}

class ApiRequestError extends Error {
  status: number;

  constructor(status: number, detail: string) {
    super(detail || `请求失败：${status}`);
    this.name = "ApiRequestError";
    this.status = status;
  }
}

async function readErrorDetail(response: Response): Promise<string> {
  const raw = await response.text();
  if (!raw) {
    return "";
  }
  try {
    const payload = JSON.parse(raw) as { detail?: unknown };
    if (typeof payload.detail === "string" && payload.detail.trim()) {
      return payload.detail;
    }
  } catch {
    // Fall back to raw text when the backend did not return JSON.
  }
  return raw;
}

const H5_MEMBER_SESSION_KEY = "frontend.h5.member-session.v1";

function clearH5MemberSessionCache(): void {
  if (typeof window === "undefined" || typeof window.localStorage === "undefined") {
    return;
  }
  window.localStorage.removeItem(H5_MEMBER_SESSION_KEY);
}

type H5MemberRequestOptions = {
  allowRefresh?: boolean;
  requireMemberAuth?: boolean;
};

async function performCredentialedFetch(input: string, init?: RequestInit): Promise<Response> {
  return fetch(input, {
    credentials: "include",
    ...init,
  });
}

async function refreshH5MemberSession(): Promise<boolean> {
  const response = await performCredentialedFetch("/api/h5/auth/refresh", {
    method: "POST",
  });
  if (response.status === 401) {
    clearH5MemberSessionCache();
    return false;
  }
  if (!response.ok) {
    const detail = await readErrorDetail(response);
    throw new ApiRequestError(response.status, detail);
  }
  return true;
}

async function fetchWithH5MemberAuth(
  input: string,
  init?: RequestInit,
  options?: H5MemberRequestOptions,
): Promise<Response> {
  let response = await performCredentialedFetch(input, init);
  if (response.status === 401 && options?.allowRefresh) {
    const refreshed = await refreshH5MemberSession();
    if (refreshed) {
      response = await performCredentialedFetch(input, init);
    }
  }
  if (response.status === 401 && options?.requireMemberAuth) {
    throw new H5AuthRequiredError();
  }
  return response;
}

async function requestJson<T>(
  input: string,
  init?: RequestInit,
  options?: H5MemberRequestOptions,
): Promise<T> {
  const response = await fetchWithH5MemberAuth(input, init, options);
  if (!response.ok) {
    const detail = await readErrorDetail(response);
    throw new ApiRequestError(response.status, detail);
  }
  return (await response.json()) as T;
}

function getAuthenticatedMemberRequestOptions(
  scope: H5TicketScope | null | undefined,
): H5MemberRequestOptions | undefined {
  if (scope?.mode !== "authenticated") {
    return undefined;
  }
  return {
    allowRefresh: true,
    requireMemberAuth: true,
  };
}

async function tryBackend<T>(request: () => Promise<T>): Promise<T | null> {
  try {
    return await request();
  } catch (error) {
    if (error instanceof TypeError || error instanceof SyntaxError) {
      return null;
    }
    if (error instanceof ApiRequestError && error.status === 404) {
      return null;
    }
    throw error;
  }
}

function resolveH5Context(context?: H5Context): { siteKey: string; publicUserId: string } {
  return {
    siteKey: context?.site_key?.trim() || DEFAULT_SITE_KEY,
    publicUserId: context?.public_user_id?.trim() || DEFAULT_USER_ID
  };
}

type H5TicketScope = {
  mode: "authenticated" | "legacy";
  publicUserId: string;
  siteKey?: string;
};

async function resolveH5TicketScope(context?: H5Context): Promise<H5TicketScope | null> {
  const session = await getCurrentMemberSession();
  if (session) {
    return {
      mode: "authenticated",
      publicUserId: session.publicUserId
    };
  }

  const publicUserId = context?.public_user_id?.trim();
  if (!publicUserId) {
    return null;
  }

  return {
    mode: "legacy",
    publicUserId,
    siteKey: context?.site_key?.trim() || DEFAULT_SITE_KEY
  };
}

function buildH5TicketQuery(scope: H5TicketScope, params?: { status?: SupportTicketStatus }): string {
  const query = new URLSearchParams();
  if (params?.status) {
    query.set("status", params.status);
  }
  if (scope.mode === "legacy") {
    query.set("public_user_id", scope.publicUserId);
    query.set("site_key", scope.siteKey || DEFAULT_SITE_KEY);
  }
  const raw = query.toString();
  return raw ? `?${raw}` : "";
}

async function resolveTicketFallbackIdentity(payload?: {
  account_id?: string;
  public_user_id?: string;
}): Promise<{ accountId: string; publicUserId: string }> {
  const session = await getCurrentMemberSession();
  if (session) {
    return {
      accountId: session.accountId,
      publicUserId: session.publicUserId
    };
  }
  if (payload?.account_id?.trim() && payload.public_user_id?.trim()) {
    return {
      accountId: payload.account_id.trim(),
      publicUserId: payload.public_user_id.trim()
    };
  }
  throw new Error("请先登录会员账号。");
}

function normalizeH5TaskStatus(status: string, reviewRequired: boolean): H5TaskStatus {
  if (status === "under_review" || (status === "submitted" && reviewRequired)) {
    return "pending_review";
  }
  if (
    status === "available" ||
    status === "claimed" ||
    status === "submitted" ||
    status === "pending_review" ||
    status === "changes_requested" ||
    status === "appealing" ||
    status === "approved" ||
    status === "rejected" ||
    status === "expired" ||
    status === "abandoned" ||
    status === "cancelled" ||
    status === "completed"
  ) {
    return status;
  }
  return "cancelled";
}

function normalizeSupportTicketStatus(status: unknown): SupportTicketStatus {
  // Keep backward compatibility with legacy payloads while hiding the old alias from the UI.
  if (status === "waiting_user") {
    return "pending_user";
  }
  if (
    status === "open" ||
    status === "in_progress" ||
    status === "pending_user" ||
    status === "resolved" ||
    status === "rejected" ||
    status === "closed" ||
    status === "cancelled"
  ) {
    return status;
  }
  return "open";
}

function normalizeSupportTicketCategory(category: unknown): SupportTicketCategory {
  if (category === "appeal") {
    return "task_appeal";
  }
  if (category === "task_appeal" || category === "help" || category === "complaint") {
    return category;
  }
  return "help";
}

function mapTaskProofFile(proof: Record<string, unknown>): H5TaskProofFile | null {
  if (typeof proof.id !== "string" || typeof proof.task_instance_id !== "string") {
    return null;
  }
  return {
    id: proof.id,
    task_instance_id: proof.task_instance_id,
    read_url: typeof proof.read_url === "string" ? proof.read_url : null,
    original_filename:
      typeof proof.original_filename === "string" ? proof.original_filename : proof.id,
    mime_type: typeof proof.mime_type === "string" ? proof.mime_type : "application/octet-stream",
    size_bytes: typeof proof.size_bytes === "number" ? proof.size_bytes : 0,
    created_at: typeof proof.created_at === "string" ? proof.created_at : nowIso()
  };
}

function mapBackendLatestSubmission(submission: Record<string, unknown> | undefined): H5LatestSubmission | null {
  if (!submission || typeof submission.id !== "string") {
    return null;
  }
  const proofs = Array.isArray(submission.proofs)
    ? submission.proofs
        .map((proof) => mapTaskProofFile(proof as Record<string, unknown>))
        .filter((proof): proof is H5TaskProofFile => proof !== null)
    : [];
  return {
    id: submission.id,
    submission_no: typeof submission.submission_no === "number" ? submission.submission_no : 1,
    status: typeof submission.status === "string" ? submission.status : "under_review",
    submitted_at: typeof submission.submitted_at === "string" ? submission.submitted_at : nowIso(),
    review_started_at: typeof submission.review_started_at === "string" ? submission.review_started_at : null,
    review_completed_at: typeof submission.review_completed_at === "string" ? submission.review_completed_at : null,
    payload_json:
      submission.payload_json && typeof submission.payload_json === "object"
        ? (submission.payload_json as Record<string, unknown>)
        : {},
    proofs
  };
}

function mapBackendLatestReviewDecision(
  decision: Record<string, unknown> | undefined
): H5LatestReviewDecision | null {
  if (!decision || typeof decision.id !== "string") {
    return null;
  }
  return {
    id: decision.id,
    decision: typeof decision.decision === "string" ? decision.decision : "pending",
    decision_source:
      typeof decision.decision_source === "string" ? decision.decision_source : "manual",
    reviewer_actor_id:
      typeof decision.reviewer_actor_id === "string" ? decision.reviewer_actor_id : null,
    reason_code: typeof decision.reason_code === "string" ? decision.reason_code : null,
    reason_text: typeof decision.reason_text === "string" ? decision.reason_text : null,
    created_at: typeof decision.created_at === "string" ? decision.created_at : nowIso()
  };
}

function mapBackendTask(
  task: Record<string, unknown>,
  enrich?: { note: string | null; media_urls: string[]; proofs: H5TaskProofFile[] } | null
): H5TaskItem {
  const statusValue = typeof task.status === "string" ? task.status : "available";
  const reviewRequired = Boolean(task.review_required);
  const reviewStatusSummary =
    typeof task.review_status_summary === "string" ? task.review_status_summary : null;
  const metadataJson =
    task.metadata_json && typeof task.metadata_json === "object"
      ? (task.metadata_json as Record<string, unknown>)
      : null;
  const latestSubmission = mapBackendLatestSubmission(
    task.latest_submission && typeof task.latest_submission === "object"
      ? (task.latest_submission as Record<string, unknown>)
      : undefined
  );
  const latestReviewDecision = mapBackendLatestReviewDecision(
    task.latest_review_decision && typeof task.latest_review_decision === "object"
      ? (task.latest_review_decision as Record<string, unknown>)
      : undefined
  );
  const latestSubmissionPayload = latestSubmission?.payload_json ?? {};
  const latestSubmissionProofs = latestSubmission?.proofs ?? enrich?.proofs ?? [];
  const latestSubmissionMediaUrls = latestSubmissionProofs
    .map((proof) => proof.read_url)
    .filter((value): value is string => typeof value === "string" && value.length > 0);
  return {
    id: String(task.id),
    account_id:
      typeof task.account_id === "string"
        ? task.account_id
        : typeof metadataJson?.account_id === "string"
          ? metadataJson.account_id
          : "unscoped",
    public_user_id: String(task.public_user_id),
    site_key: typeof task.site_key === "string" ? task.site_key : null,
    template_id: String(task.template_id),
    task_key: String(task.template_task_key),
    template_name: String(task.template_name),
    title:
      typeof task.template_title === "string"
        ? task.template_title
        : typeof task.template_name === "string"
          ? task.template_name
          : String(task.id),
    description: typeof task.template_description === "string" ? task.template_description : null,
    task_type: typeof task.task_type === "string" ? task.task_type : "shopping",
    reward_points: typeof task.reward_points === "number" ? task.reward_points : 0,
    claim_timeout_seconds:
      typeof task.claim_timeout_seconds_snapshot === "number" ? task.claim_timeout_seconds_snapshot : 0,
    review_required: reviewRequired,
    latest_submission_id:
      latestSubmission?.id ??
      (typeof task.latest_submission_id === "string" ? task.latest_submission_id : null),
    status: normalizeH5TaskStatus(statusValue, reviewRequired),
    available_at: String(task.available_at),
    claimed_at: typeof task.claimed_at === "string" ? task.claimed_at : null,
    claim_deadline_at: typeof task.claim_deadline_at === "string" ? task.claim_deadline_at : null,
    submitted_at: latestSubmission?.submitted_at ?? (typeof task.submitted_at === "string" ? task.submitted_at : null),
    reviewed_at:
      latestReviewDecision?.created_at ?? (typeof task.reviewed_at === "string" ? task.reviewed_at : null),
    completed_at: typeof task.completed_at === "string" ? task.completed_at : null,
    submission_note:
      (typeof latestSubmissionPayload.notes === "string" ? latestSubmissionPayload.notes : null) ??
      enrich?.note ??
      null,
    submission_media_urls:
      latestSubmissionMediaUrls.length > 0 ? latestSubmissionMediaUrls : (enrich?.media_urls ?? []),
    submission_proofs: latestSubmissionProofs,
    review_note: latestReviewDecision?.reason_text ?? reviewStatusSummary,
    reviewer_id: latestReviewDecision?.reviewer_actor_id ?? null,
    latest_submission: latestSubmission,
    latest_review_decision: latestReviewDecision
  };
}

function mapBackendReviewItem(item: Record<string, unknown>): ReviewQueueItem {
  const submission = item.submission as Record<string, unknown> | undefined;
  const latestDecision = item.latest_decision as Record<string, unknown> | undefined;
  const mappedSubmission = mapBackendLatestSubmission(submission);
  const mappedDecision = mapBackendLatestReviewDecision(latestDecision);
  const submittedAt =
    submission && typeof submission.submitted_at === "string" ? submission.submitted_at : null;
  const waitMinutes = submittedAt
    ? Math.max(0, Math.round((Date.now() - new Date(submittedAt).getTime()) / 60_000))
    : 0;
  const taskStatus = typeof item.task_status === "string" ? item.task_status : "under_review";
  const reviewRequired = Boolean(item.review_required);
  const queueStatus: ReviewQueueItem["queue_status"] =
    taskStatus === "approved"
      ? "approved"
      : taskStatus === "rejected"
        ? "rejected"
        : "pending_review";
  return {
    id: String(item.task_instance_id),
    submission_id: mappedSubmission?.id ?? "",
    account_id: typeof item.account_id === "string" ? item.account_id : "unscoped",
    public_user_id: String(item.public_user_id),
    site_key: typeof item.site_key === "string" ? item.site_key : null,
    template_id: String(item.template_id),
    task_key: String(item.template_task_key),
    template_name: String(item.template_name),
    title:
      typeof item.template_title === "string"
        ? item.template_title
        : typeof item.template_name === "string"
          ? item.template_name
          : String(item.task_instance_id),
    description: typeof item.template_description === "string" ? item.template_description : null,
    task_type: typeof item.task_type === "string" ? item.task_type : "shopping",
    reward_points: typeof item.reward_points === "number" ? item.reward_points : 0,
    claim_timeout_seconds: 0,
    review_required: reviewRequired,
    latest_submission_id: mappedSubmission?.id ?? null,
    status: normalizeH5TaskStatus(taskStatus, reviewRequired),
    available_at: "",
    claimed_at: null,
    claim_deadline_at: null,
    submitted_at: submittedAt,
    reviewed_at:
      latestDecision && typeof latestDecision.created_at === "string" ? latestDecision.created_at : null,
    completed_at: null,
    submission_note:
      mappedSubmission?.payload_json && typeof mappedSubmission.payload_json.notes === "string"
        ? mappedSubmission.payload_json.notes
        : null,
    submission_media_urls: (mappedSubmission?.proofs ?? [])
      .map((proof) => proof.read_url)
      .filter((value): value is string => Boolean(value)),
    submission_proofs: mappedSubmission?.proofs ?? [],
    review_note: mappedDecision?.reason_text ?? null,
    reviewer_id: mappedDecision?.reviewer_actor_id ?? null,
    latest_submission: mappedSubmission,
    latest_review_decision: mappedDecision,
    queue_status: queueStatus,
    wait_minutes: waitMinutes,
    priority: waitMinutes >= 120 ? "high" : "normal"
  };
}

function mapBackendTicketSummary(ticket: Record<string, unknown>): SupportTicket {
  const accountId =
    typeof ticket.account_id === "string"
      ? ticket.account_id
      : typeof ticket.account_scope_id === "string"
        ? ticket.account_scope_id
        : "unscoped";
  const contentPreview =
    typeof ticket.content_preview === "string"
      ? ticket.content_preview
      : typeof ticket.body_text === "string"
        ? ticket.body_text
        : "";
  return {
    id: String(ticket.id),
    account_id: accountId,
    user_id: typeof ticket.user_id === "string" ? ticket.user_id : null,
    public_user_id: String(ticket.public_user_id),
    category: normalizeSupportTicketCategory(ticket.ticket_type),
    status: normalizeSupportTicketStatus(ticket.status),
    priority: (typeof ticket.priority === "string" ? ticket.priority : "normal") as SupportTicketPriority,
    subject: String(ticket.title),
    content_preview: contentPreview,
    linked_task_instance_id:
      typeof ticket.linked_task_instance_id === "string" ? ticket.linked_task_instance_id : null,
    source: "h5",
    created_at: String(ticket.created_at),
    updated_at: String(ticket.updated_at),
    last_reply_at: typeof ticket.latest_reply_at === "string" ? ticket.latest_reply_at : null
  };
}

function mapBackendTicketDetail(ticket: Record<string, unknown>): SupportTicketDetail {
  const summary = mapBackendTicketSummary(ticket);
  const messages = Array.isArray(ticket.messages)
    ? (ticket.messages as Array<Record<string, unknown>>).map((message) => ({
        id: String(message.id),
        sender_type:
          (message.sender_type === "operator" ? "agent" : message.sender_type) as "user" | "agent" | "system",
        sender_name:
          typeof message.sender_id === "string" && message.sender_id.length > 0
            ? message.sender_id
            : String(message.sender_type),
        content: typeof message.body_text === "string" ? message.body_text : "",
        created_at: String(message.created_at),
        internal_only: Boolean(message.is_internal)
      }))
    : [];
  const firstUserMessage = messages.find((message) => !message.internal_only)?.content ?? "";
  return {
    ...summary,
    content_preview: firstUserMessage,
    description: firstUserMessage,
    messages
  };
}

export async function listH5Tasks(params?: {
  public_user_id?: string;
  account_id?: string;
  site_key?: string;
}): Promise<H5TaskItem[]> {
  const taskScope = await resolveH5TicketScope(params);
  const memberRequestOptions = getAuthenticatedMemberRequestOptions(taskScope);
  if (taskScope) {
    const backendTasks = await tryBackend<Record<string, unknown>[]>(() =>
      requestJson(`/api/h5/tasks${buildH5TicketQuery(taskScope)}`, undefined, memberRequestOptions)
    );
    if (backendTasks) {
      return backendTasks.map((task) => mapBackendTask(task));
    }
  }
  const fallbackPublicUserId = taskScope?.publicUserId ?? params?.public_user_id;
  const tasks = await loadTaskCatalog();
  return tasks.filter((task) => {
    if (fallbackPublicUserId && task.public_user_id !== fallbackPublicUserId) {
      return false;
    }
    if (params?.account_id && task.account_id !== params.account_id) {
      return false;
    }
    return true;
  });
}

export async function getH5Bootstrap(context?: H5Context): Promise<H5Bootstrap> {
  const taskScope = await resolveH5TicketScope(context);
  const memberRequestOptions = getAuthenticatedMemberRequestOptions(taskScope);
  const { siteKey, publicUserId } = resolveH5Context(context);
  const bootstrap = await tryBackend<Record<string, unknown>>(() =>
    requestJson(
      `/api/h5/bootstrap${taskScope ? buildH5TicketQuery(taskScope) : ""}`,
      undefined,
      memberRequestOptions,
    )
  );
  if (bootstrap) {
    const tasks = Array.isArray(bootstrap.tasks)
      ? bootstrap.tasks.map((task) => mapBackendTask(task as Record<string, unknown>))
      : [];
    return {
      site: {
        id: String((bootstrap.site as Record<string, unknown>).id),
        site_key: String((bootstrap.site as Record<string, unknown>).site_key),
        brand_name: String((bootstrap.site as Record<string, unknown>).brand_name),
        domain: String((bootstrap.site as Record<string, unknown>).domain),
        default_language: String((bootstrap.site as Record<string, unknown>).default_language)
      },
      user: {
        id: String((bootstrap.user as Record<string, unknown>).id),
        public_user_id: String((bootstrap.user as Record<string, unknown>).public_user_id),
        display_name:
          typeof (bootstrap.user as Record<string, unknown>).display_name === "string"
            ? String((bootstrap.user as Record<string, unknown>).display_name)
            : null,
        language_code: String((bootstrap.user as Record<string, unknown>).language_code)
      },
      tasks,
      open_ticket_count:
        typeof bootstrap.open_ticket_count === "number" ? bootstrap.open_ticket_count : 0
    };
  }

  const [tasks, tickets] = await Promise.all([
    listH5Tasks(
      taskScope?.mode === "legacy"
        ? { site_key: taskScope.siteKey, public_user_id: taskScope.publicUserId }
        : undefined
    ),
    listSupportTickets(
      taskScope?.mode === "legacy"
        ? { site_key: taskScope.siteKey, public_user_id: taskScope.publicUserId }
        : undefined
    )
  ]);
  const fallbackPublicUserId = taskScope?.publicUserId ?? publicUserId;
  return {
    site: {
      id: siteKey,
      site_key: siteKey,
      brand_name: siteKey,
      domain: `${siteKey}.local`,
      default_language: "zh-CN"
    },
    user: {
      id: fallbackPublicUserId,
      public_user_id: fallbackPublicUserId,
      display_name: fallbackPublicUserId,
      language_code: "zh-CN"
    },
    tasks,
    open_ticket_count: tickets.filter((ticket) =>
      ["open", "in_progress", "pending_user"].includes(ticket.status)
    ).length
  };
}

export async function getH5TaskDetail(taskId: string, context?: H5Context): Promise<H5TaskItem> {
  const taskScope = await resolveH5TicketScope(context);
  const memberRequestOptions = getAuthenticatedMemberRequestOptions(taskScope);
  const { publicUserId } = resolveH5Context(context);
  const backendTask = await tryBackend<Record<string, unknown>>(() =>
    requestJson(
      `/api/h5/tasks/${encodeURIComponent(taskId)}${taskScope ? buildH5TicketQuery(taskScope) : ""}`,
      undefined,
      memberRequestOptions,
    )
  );
  if (backendTask) {
    return mapBackendTask(backendTask);
  }
  const fallbackPublicUserId = taskScope?.publicUserId ?? publicUserId;
  const tasks = await loadTaskCatalog();
  const matched = tasks.find((task) => task.id === taskId && task.public_user_id === fallbackPublicUserId);
  if (!matched) {
    throw new Error("未找到任务。");
  }
  return matched;
}

export async function uploadH5TaskProof(
  taskId: string,
  payload: {
    public_user_id?: string;
    site_key?: string;
    file: File;
  }
): Promise<H5TaskProofFile> {
  const taskScope = await resolveH5TicketScope({
    site_key: payload.site_key,
    public_user_id: payload.public_user_id
  });
  const memberRequestOptions = getAuthenticatedMemberRequestOptions(taskScope);
  const formData = new FormData();
  formData.set("task_instance_id", taskId);
  if (taskScope?.mode === "legacy") {
    formData.set("public_user_id", taskScope.publicUserId);
    formData.set("site_key", taskScope.siteKey ?? DEFAULT_SITE_KEY);
  }
  formData.set("file", payload.file);

  const response = await fetchWithH5MemberAuth("/api/h5/task-proofs", {
    method: "POST",
    body: formData
  }, memberRequestOptions);
  if (!response.ok) {
    const detail = await readErrorDetail(response);
    throw new Error(detail || `证明文件上传失败：${response.status}`);
  }
  const proof = (await response.json()) as Record<string, unknown>;
  const mapped = mapTaskProofFile(proof);
  if (!mapped) {
    throw new Error("证明文件上传响应无效。");
  }
  return mapped;
}

export async function submitH5Task(
  taskId: string,
  payload: H5TaskSubmissionPayload
): Promise<H5TaskItem> {
  const taskScope = await resolveH5TicketScope({
    site_key: payload.site_key,
    public_user_id: payload.public_user_id
  });
  const memberRequestOptions = getAuthenticatedMemberRequestOptions(taskScope);
  let backendTask: Record<string, unknown> | null = null;
  try {
    backendTask = await requestJson<Record<string, unknown>>(`/api/h5/tasks/${encodeURIComponent(taskId)}/submit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ...(taskScope?.mode === "legacy"
          ? {
              public_user_id: taskScope.publicUserId,
              site_key: taskScope.siteKey ?? DEFAULT_SITE_KEY
            }
          : {}),
        proof_file_ids: payload.proof_file_ids ?? [],
        notes: payload.note,
        payload_json: {
          notes: payload.note,
          ...(payload.proof_file_ids && payload.proof_file_ids.length > 0
            ? {}
            : { media_urls: payload.media_urls })
        }
      })
    }, memberRequestOptions);
  } catch (error) {
    if (!(error instanceof TypeError)) {
      throw error;
    }
  }
  if (backendTask) {
    const taskDetail = await tryBackend<Record<string, unknown>>(() =>
      requestJson(
        `/api/h5/tasks/${encodeURIComponent(taskId)}${taskScope ? buildH5TicketQuery(taskScope) : ""}`,
        undefined,
        memberRequestOptions,
      )
    );
    if (taskDetail) {
      return mapBackendTask(taskDetail);
    }
  }
  const fallbackPublicUserId =
    taskScope?.publicUserId ??
    payload.public_user_id ??
    (await resolveTicketFallbackIdentity({ public_user_id: payload.public_user_id })).publicUserId;
  const currentTask = await getH5TaskDetail(taskId, {
    ...(taskScope?.mode === "legacy"
      ? { site_key: taskScope.siteKey, public_user_id: taskScope.publicUserId }
      : { public_user_id: fallbackPublicUserId })
  });
  if (currentTask.status !== "available" && currentTask.status !== "claimed") {
    if (currentTask.status === "rejected") {
      // 只有已驳回且存在最近一次提交流水的任务，才能发起任务申诉；否则只能先发起帮助工单。
      throw new Error(
        currentTask.latest_submission_id
          ? "任务已被驳回，请根据审核备注发起任务申诉或帮助工单，当前任务不能直接重新提交。"
          : "当前任务已驳回，但缺少最近一次提交流水。请先发起帮助工单，由客服协助核对。"
      );
    }
    if (currentTask.status === "changes_requested") {
      throw new Error("当前任务处于待补充处理状态，不能直接重新提交。请发起帮助工单继续处理。");
    }
    if (currentTask.status === "appealing") {
      throw new Error("当前任务正在申诉处理中，不能回到直接提交流程。请在任务申诉或帮助工单中继续处理。");
    }
    throw new Error("当前任务状态不可提交。");
  }
  const submissions = readTaskSubmissions();
  const nextSubmission: StoredTaskSubmission = {
    task_id: taskId,
    public_user_id: fallbackPublicUserId,
    note: payload.note.trim(),
    media_urls: payload.media_urls.filter((item) => item.length > 0),
    proof_file_ids: payload.proof_file_ids ?? [],
    submitted_at: nowIso()
  };
  const nextEntries = submissions.filter((item) => item.task_id !== taskId);
  nextEntries.push(nextSubmission);
  writeTaskSubmissions(nextEntries);
  return getH5TaskDetail(
    taskId,
    taskScope?.mode === "legacy"
      ? { site_key: taskScope.siteKey, public_user_id: taskScope.publicUserId }
      : { public_user_id: fallbackPublicUserId }
  );
}

export async function listReviewQueue(accountId?: string): Promise<ReviewQueueItem[]> {
  const backendQueue = await tryBackend<Record<string, unknown>[]>(() =>
    requestJson(
      `/api/reviews/queue${accountId ? `?account_id=${encodeURIComponent(accountId)}` : ""}`,
      { headers: getAdminHeaders(false) }
    )
  );
  if (backendQueue) {
    return backendQueue.map((item) => mapBackendReviewItem(item));
  }
  const tasks = await loadTaskCatalog();
  return tasks
    .filter(
      (task) =>
        task.review_required &&
        task.submitted_at &&
        (task.status === "pending_review" || task.status === "submitted")
    )
    .filter((task) => (accountId ? task.account_id === accountId : true))
    .map((task) => {
      const submittedAt = task.submitted_at ?? nowIso();
      const waitMinutes = Math.max(
        0,
        Math.round((Date.now() - new Date(submittedAt).getTime()) / 60_000)
      );
      const queueStatus: ReviewQueueItem["queue_status"] =
        task.status === "approved"
          ? "approved"
          : task.status === "rejected"
            ? "rejected"
            : "pending_review";
      const priority: ReviewQueueItem["priority"] = waitMinutes >= 120 ? "high" : "normal";
      return {
        ...task,
        submission_id: task.latest_submission_id ?? "",
        queue_status: queueStatus,
        wait_minutes: waitMinutes,
        priority
      };
    })
    .sort((left, right) => {
      if (left.queue_status !== right.queue_status) {
        return left.queue_status.localeCompare(right.queue_status);
      }
      return right.wait_minutes - left.wait_minutes;
    });
}

export async function submitReviewDecision(
  taskId: string,
  payload: ReviewDecisionPayload
): Promise<ReviewQueueItem> {
  const backendQueue = await tryBackend<Record<string, unknown>[]>(() =>
    requestJson("/api/reviews/queue", { headers: getAdminHeaders(false) })
  );
  const matchedSubmissionId = backendQueue
    ?.map((item) => mapBackendReviewItem(item))
    .find((item) => item.id === taskId)
    ?.submission_id;
  if (matchedSubmissionId) {
    const endpoint = payload.decision === "approved" ? "approve" : "reject";
    const decision = await tryBackend<Record<string, unknown>>(() =>
      requestJson(`/api/reviews/submissions/${encodeURIComponent(matchedSubmissionId)}/${endpoint}`, {
        method: "POST",
        headers: getAdminHeaders(),
        body: JSON.stringify({
          reason_text: payload.note ?? "",
          evidence_json: { reviewer_id: payload.reviewer_id }
        })
      })
    );
    if (decision) {
      const refreshedQueue = await listReviewQueue();
      const matched = refreshedQueue.find((item) => item.id === taskId);
      if (matched) {
        return matched;
      }
    }
  }
  const currentTask = await getH5TaskDetail(taskId);
  if (currentTask.status === "rejected") {
    throw new Error("该提交已驳回；后续应转任务申诉或帮助工单，不应再次直接审核。");
  }
  if (currentTask.status === "changes_requested") {
    throw new Error("该任务当前处于待补充处理状态，不应再次直接审核；后续请在帮助工单或人工复核链路继续处理。");
  }
  if (currentTask.status === "appealing") {
    throw new Error("该任务已进入任务申诉链路，请在任务申诉或帮助工单中继续处理。");
  }
  const reviews = readReviewDecisions();
  const nextReview: StoredReviewDecision = {
    task_id: taskId,
    decision: payload.decision,
    note: payload.note?.trim() ?? "",
    reviewer_id: payload.reviewer_id,
    reviewed_at: nowIso()
  };
  const nextEntries = reviews.filter((item) => item.task_id !== taskId);
  nextEntries.push(nextReview);
  writeReviewDecisions(nextEntries);
  const updatedTask = await getH5TaskDetail(taskId);
  const submittedAt = updatedTask.submitted_at ?? nowIso();
  const waitMinutes = Math.max(0, Math.round((Date.now() - new Date(submittedAt).getTime()) / 60_000));
  return {
    ...updatedTask,
    submission_id: updatedTask.latest_submission_id ?? "",
    queue_status: payload.decision,
    wait_minutes: waitMinutes,
    priority: waitMinutes >= 120 ? "high" : "normal"
  };
}

function mapPlatformMemberVerificationDocument(
  item: Record<string, unknown>
): PlatformMemberVerificationDocument {
  return {
    id: String(item.id),
    fileName: String(item.fileName),
    mimeType: typeof item.mimeType === "string" ? item.mimeType : null,
    storageKey: typeof item.storageKey === "string" ? item.storageKey : null,
    metadataJson:
      item.metadataJson && typeof item.metadataJson === "object"
        ? (item.metadataJson as Record<string, unknown>)
        : null,
    createdAt: String(item.createdAt)
  };
}

function mapPlatformMemberVerificationRequest(
  item: Record<string, unknown>
): PlatformMemberVerificationRequest {
  return {
    id: String(item.id),
    accountId: String(item.accountId),
    memberProfileId: String(item.memberProfileId),
    userId: String(item.userId),
    publicUserId: String(item.publicUserId),
    memberNo: String(item.memberNo),
    displayName: typeof item.displayName === "string" ? item.displayName : null,
    requestType: String(item.requestType),
    status: String(item.status) as PlatformMemberVerificationStatus,
    notes: typeof item.notes === "string" ? item.notes : null,
    reviewNote: typeof item.reviewNote === "string" ? item.reviewNote : null,
    reviewerActorId: typeof item.reviewerActorId === "string" ? item.reviewerActorId : null,
    createdAt: String(item.createdAt),
    updatedAt: String(item.updatedAt),
    reviewedAt: typeof item.reviewedAt === "string" ? item.reviewedAt : null,
    documents: Array.isArray(item.documents)
      ? item.documents.map((document) =>
          mapPlatformMemberVerificationDocument(document as Record<string, unknown>)
        )
      : []
  };
}

function mapPlatformMemberWhatsAppBindingRequest(
  item: Record<string, unknown>
): PlatformMemberWhatsAppBindingRequest {
  return {
    id: String(item.id),
    accountId: String(item.accountId),
    userId: String(item.userId),
    memberProfileId: String(item.memberProfileId),
    siteId: typeof item.siteId === "string" ? item.siteId : null,
    siteKey: typeof item.siteKey === "string" ? item.siteKey : null,
    publicUserId: String(item.publicUserId),
    memberNo: String(item.memberNo),
    displayName: typeof item.displayName === "string" ? item.displayName : null,
    status: String(item.status) as PlatformMemberWhatsAppBindingStatus,
    requestedPhoneNumber:
      typeof item.requestedPhoneNumber === "string" ? item.requestedPhoneNumber : null,
    startCount: typeof item.startCount === "number" ? item.startCount : 0,
    lastError: typeof item.lastError === "string" ? item.lastError : null,
    createdAt: String(item.createdAt),
    updatedAt: String(item.updatedAt),
    lastStartedAt: typeof item.lastStartedAt === "string" ? item.lastStartedAt : null,
    boundAt: typeof item.boundAt === "string" ? item.boundAt : null
  };
}

function buildPlatformQuery(params?: Record<string, string | undefined>): string {
  const query = new URLSearchParams();
  Object.entries(params ?? {}).forEach(([key, value]) => {
    if (typeof value === "string" && value.length > 0) {
      query.set(key, value);
    }
  });
  const raw = query.toString();
  return raw ? `?${raw}` : "";
}

export async function listPlatformMemberVerifications(params?: {
  account_id?: string;
  status?: PlatformMemberVerificationStatus;
}): Promise<PlatformMemberVerificationRequest[]> {
  const items = await requestJson<Record<string, unknown>[]>(
    `/api/platform/member-verifications${buildPlatformQuery({
      account_id: params?.account_id,
      status: params?.status
    })}`,
    { headers: getAdminHeaders(false) }
  );
  return items.map((item) => mapPlatformMemberVerificationRequest(item));
}

export async function updatePlatformMemberVerificationStatus(
  requestId: string,
  payload: PlatformMemberVerificationStatusUpdatePayload
): Promise<PlatformMemberVerificationRequest> {
  const response = await requestJson<Record<string, unknown>>(
    `/api/platform/member-verifications/${encodeURIComponent(requestId)}/status`,
    {
      method: "POST",
      headers: getAdminHeaders(),
      body: JSON.stringify({
        status: payload.status,
        ...(payload.note?.trim() ? { note: payload.note.trim() } : {})
      })
    }
  );
  return mapPlatformMemberVerificationRequest(response);
}

export async function listPlatformMemberWhatsAppBindings(params?: {
  account_id?: string;
  status?: PlatformMemberWhatsAppBindingStatus;
}): Promise<PlatformMemberWhatsAppBindingRequest[]> {
  const items = await requestJson<Record<string, unknown>[]>(
    `/api/platform/member-whatsapp-bindings${buildPlatformQuery({
      account_id: params?.account_id,
      status: params?.status
    })}`,
    { headers: getAdminHeaders(false) }
  );
  return items.map((item) => mapPlatformMemberWhatsAppBindingRequest(item));
}

export async function updatePlatformMemberWhatsAppBindingStatus(
  requestId: string,
  payload: PlatformMemberWhatsAppBindingStatusUpdatePayload
): Promise<PlatformMemberWhatsAppBindingRequest> {
  const response = await requestJson<Record<string, unknown>>(
    `/api/platform/member-whatsapp-bindings/${encodeURIComponent(requestId)}/status`,
    {
      method: "POST",
      headers: getAdminHeaders(),
      body: JSON.stringify({
        status: payload.status,
        ...(payload.note?.trim() ? { note: payload.note.trim() } : {})
      })
    }
  );
  return mapPlatformMemberWhatsAppBindingRequest(response);
}

export async function listSupportTickets(params?: {
  account_id?: string;
  public_user_id?: string;
  site_key?: string;
  status?: SupportTicketStatus;
  category?: SupportTicketCategory;
}): Promise<SupportTicket[]> {
  const ticketScope = await resolveH5TicketScope(params);
  const memberRequestOptions = getAuthenticatedMemberRequestOptions(ticketScope);
  if (ticketScope && !params?.account_id && !params?.category) {
    const h5Tickets = await tryBackend<Record<string, unknown>[]>(() =>
      requestJson(
        `/api/h5/tickets${buildH5TicketQuery(ticketScope, { status: params?.status })}`,
        undefined,
        memberRequestOptions,
      )
    );
    if (h5Tickets) {
      return h5Tickets.map((ticket) => mapBackendTicketSummary(ticket));
    }
  }
  const backendTickets = await tryBackend<Record<string, unknown>[]>(() =>
    requestJson(
      `/api/tickets${buildTicketQuery(params)}`,
      { headers: getAdminHeaders(false) }
    )
  );
  if (backendTickets) {
    return backendTickets.map((ticket) => mapBackendTicketSummary(ticket));
  }
  const fallbackPublicUserId = ticketScope?.publicUserId ?? params?.public_user_id;
  const records = readTicketRecords();
  return records
    .filter((record) => (params?.account_id ? record.account_id === params.account_id : true))
    .filter((record) => (fallbackPublicUserId ? record.public_user_id === fallbackPublicUserId : true))
    .filter((record) => (params?.status ? record.status === params.status : true))
    .filter((record) => (params?.category ? record.category === params.category : true))
    .map(mapTicketSummary)
    .sort((left, right) => (right.last_reply_at ?? right.updated_at).localeCompare(left.last_reply_at ?? left.updated_at));
}

export async function getSupportTicketDetail(
  ticketId: string,
  context?: H5Context
): Promise<SupportTicketDetail> {
  const ticketScope = await resolveH5TicketScope(context);
  const memberRequestOptions = getAuthenticatedMemberRequestOptions(ticketScope);
  if (ticketScope) {
    const h5Ticket = await tryBackend<Record<string, unknown>>(() =>
      requestJson(
        `/api/h5/tickets/${encodeURIComponent(ticketId)}${buildH5TicketQuery(ticketScope)}`,
        undefined,
        memberRequestOptions,
      )
    );
    if (h5Ticket) {
      return mapBackendTicketDetail(h5Ticket);
    }
  }
  const backendTicket = await tryBackend<Record<string, unknown>>(() =>
    requestJson(`/api/tickets/${encodeURIComponent(ticketId)}`, { headers: getAdminHeaders(false) })
  );
  if (backendTicket) {
    return mapBackendTicketDetail(backendTicket);
  }
  const records = readTicketRecords();
  const matched = records.find((record) => record.id === ticketId);
  if (!matched) {
    throw new Error("未找到工单。");
  }
  if (ticketScope && matched.public_user_id !== ticketScope.publicUserId) {
    throw new Error("工单不在当前会员范围内。");
  }
  return mapTicketDetail(matched);
}

export async function createSupportTicket(
  payload: SupportTicketCreatePayload
): Promise<SupportTicketDetail> {
  const ticketScope = await resolveH5TicketScope({
    site_key: payload.site_key,
    public_user_id: payload.public_user_id
  });
  const memberRequestOptions = getAuthenticatedMemberRequestOptions(ticketScope);
  const backendTicket = await tryBackend<Record<string, unknown>>(() =>
    requestJson("/api/h5/tickets", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ...(ticketScope?.mode === "legacy"
          ? {
              account_id: payload.account_id,
              public_user_id: ticketScope.publicUserId,
              site_key: ticketScope.siteKey ?? DEFAULT_SITE_KEY
            }
          : {}),
        ticket_type: payload.category === "task_appeal" ? "appeal" : payload.category,
        title: payload.subject,
        body_text: payload.description,
        linked_task_instance_id: payload.linked_task_instance_id ?? null,
        linked_submission_id: payload.linked_submission_id ?? null,
        priority: payload.priority,
        attachments_json: []
      })
    }, memberRequestOptions)
  );
  if (backendTicket) {
    return mapBackendTicketDetail(backendTicket);
  }
  const fallbackIdentity = await resolveTicketFallbackIdentity(payload);
  const now = nowIso();
  const id = createId("ticket");
  const record: StoredTicketRecord = {
    id,
    account_id: fallbackIdentity.accountId,
    public_user_id: fallbackIdentity.publicUserId,
    category: payload.category,
    status: "open",
    priority: payload.priority,
    subject: payload.subject.trim(),
    description: payload.description.trim(),
    linked_task_instance_id: payload.linked_task_instance_id ?? null,
    source: "h5",
    created_at: now,
    updated_at: now,
    last_reply_at: now,
    messages: [
      {
        id: createId(`${id}-msg`),
        sender_type: "user",
        sender_name: fallbackIdentity.publicUserId,
        content: payload.description.trim(),
        created_at: now,
        internal_only: false
      }
    ]
  };
  const nextRecords = [record, ...readTicketRecords()];
  writeTicketRecords(nextRecords);
  return mapTicketDetail(record);
}

export async function replySupportTicket(
  ticketId: string,
  payload: SupportTicketReplyPayload,
  context?: H5Context
): Promise<SupportTicketDetail> {
  const ticketScope = await resolveH5TicketScope(context);
  const memberRequestOptions = getAuthenticatedMemberRequestOptions(ticketScope);
  if (ticketScope) {
    const formData = new FormData();
    formData.set("body_text", payload.content);
    const h5Message = await tryBackend<Record<string, unknown>>(() =>
      requestJson(`/api/h5/tickets/${encodeURIComponent(ticketId)}/messages${buildH5TicketQuery(ticketScope)}`, {
        method: "POST",
        body: formData
      }, memberRequestOptions)
    );
    if (h5Message) {
      return getSupportTicketDetail(
        ticketId,
        ticketScope.mode === "legacy"
          ? { site_key: ticketScope.siteKey, public_user_id: ticketScope.publicUserId }
          : undefined
      );
    }
  }
  const backendTicket = await tryBackend<Record<string, unknown>>(() =>
    requestJson(`/api/tickets/${encodeURIComponent(ticketId)}/messages`, {
      method: "POST",
      headers: getAdminHeaders(),
      body: JSON.stringify({
        sender_type: payload.sender_type === "agent" ? "operator" : payload.sender_type,
        sender_id: payload.sender_name,
        body_text: payload.content,
        attachments_json: [],
        is_internal: payload.internal_only ?? false
      })
    })
  );
  if (backendTicket) {
    const refreshed = await getSupportTicketDetail(ticketId);
    return refreshed;
  }
  const records = readTicketRecords();
  const currentRecord = records.find((record) => record.id === ticketId);
  if (!currentRecord) {
    throw new Error("未找到工单。");
  }
  const currentStatus = normalizeSupportTicketStatus(currentRecord.status);
  if (isSupportTicketTerminalStatus(currentStatus)) {
    throw new Error("当前工单已结束，不能继续补充。");
  }
  const nextRecords = records.map((record) => {
    if (record.id !== ticketId) {
      return record;
    }
    const message: SupportTicketMessage = {
      id: createId(`${ticketId}-msg`),
      sender_type: payload.sender_type,
      sender_name: payload.sender_name,
      content: payload.content.trim(),
      created_at: nowIso(),
      internal_only: payload.internal_only ?? false
    };
    return {
      ...record,
      status: resolveLocalReplyTicketStatus(currentStatus, payload),
      updated_at: message.created_at,
      last_reply_at: message.created_at,
      messages: [...record.messages, message]
    };
  });
  writeTicketRecords(nextRecords);
  return getSupportTicketDetail(ticketId);
}

export async function updateSupportTicketStatus(
  ticketId: string,
  payload: SupportTicketStatusPayload
): Promise<SupportTicketDetail> {
  const backendTicket = await tryBackend<Record<string, unknown>>(() =>
    requestJson(`/api/tickets/${encodeURIComponent(ticketId)}/status`, {
      method: "POST",
      headers: getAdminHeaders(),
      body: JSON.stringify({
        status: payload.status
      })
    })
  );
  if (backendTicket) {
    if (payload.note?.trim()) {
      await tryBackend<Record<string, unknown>>(() =>
        requestJson(`/api/tickets/${encodeURIComponent(ticketId)}/messages`, {
          method: "POST",
          headers: getAdminHeaders(),
          body: JSON.stringify({
            sender_type: "system",
            sender_id: payload.actor_name,
            body_text: payload.note,
            attachments_json: [],
            is_internal: true
          })
        })
      );
    }
    return getSupportTicketDetail(ticketId);
  }
  const records = readTicketRecords();
  const currentRecord = records.find((record) => record.id === ticketId);
  if (!currentRecord) {
    throw new Error("未找到工单。");
  }
  const currentStatus = normalizeSupportTicketStatus(currentRecord.status);
  const targetStatus = normalizeSupportTicketStatus(payload.status);
  if (!canSupportTicketTransition(currentStatus, targetStatus)) {
    throw new Error(`工单状态不能从 ${currentStatus} 变更为 ${targetStatus}。`);
  }
  const nextRecords = records.map((record) => {
    if (record.id !== ticketId) {
      return record;
    }
    const changedAt = nowIso();
    const nextMessages = [...record.messages];
    if (payload.note?.trim()) {
      nextMessages.push({
        id: createId(`${ticketId}-status`),
        sender_type: "system",
        sender_name: payload.actor_name,
        content: payload.note.trim(),
        created_at: changedAt,
        internal_only: true
      });
    }
    return {
      ...record,
      status: targetStatus,
      updated_at: changedAt,
      last_reply_at: record.last_reply_at,
      messages: nextMessages
    };
  });
  writeTicketRecords(nextRecords);
  return getSupportTicketDetail(ticketId);
}

function buildTicketQuery(params?: {
  account_id?: string;
  public_user_id?: string;
  status?: SupportTicketStatus;
  category?: SupportTicketCategory;
}): string {
  const query = new URLSearchParams();
  if (params?.account_id) {
    query.set("account_id", params.account_id);
  }
  if (params?.public_user_id) {
    query.set("public_user_id", params.public_user_id);
  }
  if (params?.status) {
    query.set("status", params.status);
  }
  if (params?.category) {
    query.set("ticket_type", params.category === "task_appeal" ? "appeal" : params.category);
  }
  const raw = query.toString();
  return raw ? `?${raw}` : "";
}
