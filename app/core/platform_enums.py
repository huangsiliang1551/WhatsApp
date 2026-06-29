from enum import StrEnum


class H5SiteStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


class UserLifecycleStatus(StrEnum):
    ACTIVE = "active"
    FROZEN = "frozen"
    BLACKLISTED = "blacklisted"


class UserIdentityType(StrEnum):
    USERNAME = "username"
    PHONE = "phone"
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    ANONYMOUS = "anonymous"


class InviteCodeStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"
    EXPIRED = "expired"


class UserTagSourceType(StrEnum):
    MANUAL = "manual"
    RULE = "rule"
    SYSTEM = "system"


class AudienceRuleStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


class TaskType(StrEnum):
    SHOPPING = "shopping"
    INVITE = "invite"
    LADDER = "ladder"
    DAILY = "daily"


class TaskTemplateStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    EXPIRED = "expired"
    ARCHIVED = "archived"


class TaskInstanceStatus(StrEnum):
    AVAILABLE = "available"
    CLAIMED = "claimed"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    CHANGES_REQUESTED = "changes_requested"
    APPROVED = "approved"
    REJECTED = "rejected"
    APPEALING = "appealing"
    COMPLETED = "completed"
    EXPIRED = "expired"
    ABANDONED = "abandoned"
    CANCELLED = "cancelled"


class TaskProofFileType(StrEnum):
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"
    LINK = "link"
    TEXT = "text"


class TaskProofFileStatus(StrEnum):
    ACTIVE = "active"
    UPLOADED = "uploaded"
    ATTACHED = "attached"
    INVALID = "invalid"
    REPLACED = "replaced"
    DELETED = "deleted"


class TaskSubmissionType(StrEnum):
    STANDARD = "standard"
    RESUBMISSION = "resubmission"
    APPEAL = "appeal"


class TaskSubmissionStatus(StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    CHANGES_REQUESTED = "changes_requested"
    APPROVED = "approved"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class TaskSubmissionProofRole(StrEnum):
    PRIMARY = "primary"
    EVIDENCE = "evidence"
    SUPPLEMENTAL = "supplemental"
    EXPLANATION = "explanation"


class TaskReviewDecisionType(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CHANGES_REQUESTED = "changes_requested"
    ESCALATED = "escalated"


class TaskReviewDecisionSource(StrEnum):
    MANUAL = "manual"
    PLACEHOLDER_AUTO = "placeholder_auto"


class TicketType(StrEnum):
    SUBMISSION_REVIEW = "submission_review"
    APPEAL = "appeal"
    HELP = "help"
    COMPLAINT = "complaint"
    MANUAL_SERVICE = "manual_service"


class TicketStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    WAITING_USER = "waiting_user"
    PENDING_USER = "pending_user"
    RESOLVED = "resolved"
    REJECTED = "rejected"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class TicketMessageSenderType(StrEnum):
    USER = "user"
    AGENT = "agent"
    OPERATOR = "operator"
    SYSTEM = "system"


class TicketMessageType(StrEnum):
    TEXT = "text"
    IMAGE = "image"
    FILE = "file"
    SYSTEM_NOTE = "system_note"
