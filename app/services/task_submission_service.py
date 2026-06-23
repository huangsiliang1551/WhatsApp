from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.core.metrics import task_reviews_total, task_submissions_total
from app.core.platform_enums import (
    TaskInstanceStatus,
    TaskReviewDecisionSource,
    TaskReviewDecisionType,
    TaskSubmissionStatus,
)
from app.db.models import (
    AppUser,
    H5Site,
    TaskInstance,
    TaskReviewDecision,
    TaskSubmission,
    TaskSubmissionProof,
    utc_now,
)
from app.schemas.task_workflow import TaskSubmissionCreateRequest, TaskSubmissionResponse
from app.services.task_proof_storage_service import TaskProofStorageService


class TaskSubmissionService:
    def __init__(
        self,
        *,
        session: Session,
        proof_storage_service: TaskProofStorageService,
    ) -> None:
        self._session = session
        self._proof_storage_service = proof_storage_service

    async def create_submission(
        self,
        *,
        task_instance_id: str,
        payload: TaskSubmissionCreateRequest,
    ) -> TaskSubmissionResponse:
        instance = self._require_task_instance(task_instance_id)
        user = self._require_submitter(instance, payload.public_user_id)
        self._ensure_site_matches(instance=instance, site_id=payload.site_id, site_key=payload.site_key)
        self._ensure_submittable(instance)

        proofs = self._proof_storage_service.require_proofs(
            task_instance=instance,
            user=user,
            proof_file_ids=payload.proof_file_ids,
        )
        submission_no = self._next_submission_no(instance.id)
        now = utc_now()
        payload_json = dict(payload.payload_json)
        if payload.notes is not None:
            payload_json["notes"] = payload.notes
        submission = TaskSubmission(
            account_id=self._require_account_scope(instance),
            task_instance_id=instance.id,
            submitted_by_user_id=user.id,
            site_id=instance.site_id,
            submission_no=submission_no,
            status=TaskSubmissionStatus.SUBMITTED.value,
            source_channel="h5",
            submitted_at=now,
            review_started_at=None,
            review_completed_at=None,
            review_required_snapshot=instance.review_required,
            payload_json=payload_json,
        )
        self._session.add(submission)
        self._session.flush()

        for index, proof in enumerate(proofs):
            proof.status = "attached"
            self._session.add(
                TaskSubmissionProof(
                    account_id=submission.account_id,
                    task_instance_id=submission.task_instance_id,
                    submission_id=submission.id,
                    proof_file_id=proof.id,
                    proof_role="evidence",
                    sort_order=index,
                )
            )

        instance.status = TaskInstanceStatus.SUBMITTED.value
        instance.submitted_at = now
        instance.completed_at = None
        self._session.add(instance)

        self._initialize_review(submission=submission, task_instance=instance, started_at=now)

        self._session.commit()
        task_submissions_total.labels(status=submission.status).inc()
        return await self.get_submission(submission.id)

    async def get_submission(self, submission_id: str) -> TaskSubmissionResponse:
        submission = self._session.execute(
            select(TaskSubmission)
            .options(joinedload(TaskSubmission.task_instance).joinedload(TaskInstance.user))
            .options(joinedload(TaskSubmission.task_instance).joinedload(TaskInstance.site))
            .options(joinedload(TaskSubmission.proofs).joinedload(TaskSubmissionProof.proof_file))
            .where(TaskSubmission.id == submission_id)
        ).unique().scalars().first()
        if submission is None:
            raise LookupError(f"Task submission '{submission_id}' was not found.")
        return await self._serialize_submission(submission)

    async def get_latest_submission_for_task(self, task_instance_id: str) -> TaskSubmissionResponse:
        submission = self._session.execute(
            select(TaskSubmission)
            .options(joinedload(TaskSubmission.task_instance).joinedload(TaskInstance.user))
            .options(joinedload(TaskSubmission.task_instance).joinedload(TaskInstance.site))
            .options(joinedload(TaskSubmission.proofs).joinedload(TaskSubmissionProof.proof_file))
            .where(TaskSubmission.task_instance_id == task_instance_id)
            .order_by(TaskSubmission.submission_no.desc(), TaskSubmission.created_at.desc())
        ).unique().scalars().first()
        if submission is None:
            raise LookupError(f"Task instance '{task_instance_id}' has no submission yet.")
        return await self._serialize_submission(submission)

    def resolve_task_instance_account_id(self, task_instance_id: str) -> str:
        instance = self._require_task_instance(task_instance_id)
        return self._require_account_scope(instance)

    def _initialize_review(
        self,
        *,
        submission: TaskSubmission,
        task_instance: TaskInstance,
        started_at: datetime,
    ) -> None:
        submission.status = TaskSubmissionStatus.UNDER_REVIEW.value
        submission.review_started_at = started_at
        task_instance.status = TaskInstanceStatus.UNDER_REVIEW.value
        self._session.add(submission)
        self._session.add(task_instance)

        if task_instance.template.auto_review_enabled:
            self._session.add(
                TaskReviewDecision(
                    account_id=submission.account_id,
                    task_instance_id=task_instance.id,
                    submission_id=submission.id,
                    decision=TaskReviewDecisionType.PENDING.value,
                    decision_source=TaskReviewDecisionSource.PLACEHOLDER_AUTO.value,
                    reviewer_actor_id=None,
                    reason_code="auto_review_placeholder",
                    reason_text="Auto review placeholder created.",
                    evidence_json={},
                )
            )
            task_reviews_total.labels(decision=TaskReviewDecisionType.PENDING.value).inc()

    async def _serialize_submission(self, submission: TaskSubmission) -> TaskSubmissionResponse:
        task_instance = submission.task_instance
        user = task_instance.user
        site = task_instance.site
        proofs = []
        for link in sorted(submission.proofs, key=lambda item: item.sort_order):
            proofs.append(await self._proof_storage_service.serialize_proof(link.proof_file))
        return TaskSubmissionResponse(
            id=submission.id,
            account_id=self._require_submission_account_id(submission),
            task_instance_id=submission.task_instance_id,
            submission_no=submission.submission_no,
            status=submission.status,
            submitted_by_user_id=submission.submitted_by_user_id,
            public_user_id=user.public_user_id,
            site_id=submission.site_id,
            site_key=site.site_key if site is not None else None,
            source_channel=submission.source_channel,
            submitted_at=submission.submitted_at,
            review_started_at=submission.review_started_at,
            review_completed_at=submission.review_completed_at,
            review_required_snapshot=submission.review_required_snapshot,
            payload_json=submission.payload_json,
            proofs=proofs,
            created_at=submission.created_at,
            updated_at=submission.updated_at,
        )

    @staticmethod
    def _resolve_account_id(instance: TaskInstance) -> str | None:
        return (
            instance.account_id
            or instance.template.account_id
            or (instance.site.account_id if instance.site is not None else None)
            or instance.user.account_id
            or (
                instance.user.registration_site.account_id
                if instance.user.registration_site is not None
                else None
            )
        )

    def _require_account_scope(self, instance: TaskInstance) -> str:
        account_id = self._resolve_account_id(instance)
        if account_id is None:
            raise ValueError(f"Task instance '{instance.id}' does not have a resolved account scope.")
        return account_id

    def _require_submission_account_id(self, submission: TaskSubmission) -> str:
        if submission.account_id is not None:
            return submission.account_id
        return self._require_account_scope(submission.task_instance)

    def _require_task_instance(self, task_instance_id: str) -> TaskInstance:
        instance = self._session.scalars(
            select(TaskInstance)
            .options(joinedload(TaskInstance.template))
            .options(joinedload(TaskInstance.user))
            .options(joinedload(TaskInstance.site))
            .where(TaskInstance.id == task_instance_id)
        ).first()
        if instance is None:
            raise LookupError(f"Task instance '{task_instance_id}' was not found.")
        return instance

    @staticmethod
    def _require_submitter(instance: TaskInstance, public_user_id: str) -> AppUser:
        user = instance.user
        if user.public_user_id != public_user_id:
            raise PermissionError(
                f"Task instance '{instance.id}' does not belong to public user '{public_user_id}'."
            )
        return user

    @staticmethod
    def _ensure_site_matches(
        *,
        instance: TaskInstance,
        site_id: str | None,
        site_key: str | None,
    ) -> None:
        if site_id is not None and instance.site_id != site_id:
            raise PermissionError(f"Task instance '{instance.id}' does not belong to site '{site_id}'.")
        if site_key is not None:
            resolved_site_key = instance.site.site_key if instance.site is not None else None
            if resolved_site_key != site_key:
                raise PermissionError(f"Task instance '{instance.id}' does not belong to site '{site_key}'.")

    def _ensure_submittable(self, instance: TaskInstance) -> None:
        if instance.user.is_anonymous:
            raise ValueError("Anonymous users cannot submit formal task instances.")
        if instance.status == TaskInstanceStatus.REJECTED.value:
            raise ValueError(
                f"Task instance '{instance.id}' cannot be submitted from status 'rejected'. "
                "Rejected tasks must continue through an appeal or help ticket instead of direct resubmission."
            )
        if instance.status == TaskInstanceStatus.CHANGES_REQUESTED.value:
            raise ValueError(
                f"Task instance '{instance.id}' cannot be submitted from status 'changes_requested'. "
                "Legacy changes-requested tasks must continue through a help ticket or review follow-up "
                "instead of direct resubmission."
            )
        if instance.status == TaskInstanceStatus.APPEALING.value:
            raise ValueError(
                f"Task instance '{instance.id}' cannot be submitted from status 'appealing'. "
                "An active appeal must be resolved before any further task action."
            )
        if instance.status in {"approved", "rejected", "expired", "abandoned", "completed"}:
            raise ValueError(f"Task instance '{instance.id}' cannot be submitted from status '{instance.status}'.")
        existing = self._session.scalars(
            select(TaskSubmission).where(TaskSubmission.task_instance_id == instance.id)
        ).first()
        if existing is not None:
            raise ValueError(f"Duplicate submission: task instance '{instance.id}' already has a submission.")

    def _next_submission_no(self, task_instance_id: str) -> int:
        current = self._session.scalar(
            select(func.max(TaskSubmission.submission_no)).where(TaskSubmission.task_instance_id == task_instance_id)
        )
        return int(current or 0) + 1
