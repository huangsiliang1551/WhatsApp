from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.metrics import task_reviews_total
from app.db.models import H5Site, TaskInstance, TaskReviewDecision, TaskSubmission, utc_now
from app.schemas.task_workflow import (
    ReviewQueueItemResponse,
    TaskReviewDecisionActionRequest,
    TaskReviewDecisionResponse,
)
from app.services.task_submission_service import TaskSubmissionService


class ReviewService:
    def __init__(
        self,
        *,
        session: Session,
        submission_service: TaskSubmissionService,
    ) -> None:
        self._session = session
        self._submission_service = submission_service

    async def list_review_queue(
        self,
        *,
        account_id: str | None = None,
        agency_id: str | None = None,
    ) -> list[ReviewQueueItemResponse]:
        query = (
            select(TaskSubmission)
            .options(joinedload(TaskSubmission.task_instance).joinedload(TaskInstance.template))
            .options(joinedload(TaskSubmission.task_instance).joinedload(TaskInstance.user))
            .options(joinedload(TaskSubmission.task_instance).joinedload(TaskInstance.site))
            .options(joinedload(TaskSubmission.proofs))
            .where(TaskSubmission.status == "under_review")
            .order_by(TaskSubmission.created_at.desc(), TaskSubmission.id.desc())
        )
        if account_id is not None:
            query = query.where(TaskSubmission.account_id == account_id)
        if agency_id is not None:
            agency_account_ids = select(H5Site.account_id).where(H5Site.agency_id == agency_id)
            query = query.where(TaskSubmission.account_id.in_(agency_account_ids))
        submissions = self._session.execute(query).unique().scalars().all()
        items: list[ReviewQueueItemResponse] = []
        for submission in submissions:
            task_instance = submission.task_instance
            latest_decision = self._latest_decision_model(submission.id)
            items.append(
                ReviewQueueItemResponse(
                    task_instance_id=task_instance.id,
                    template_id=task_instance.template_id,
                    template_task_key=task_instance.template.task_key,
                    template_name=task_instance.template.name,
                    template_title=task_instance.template.title,
                    template_description=task_instance.template.description,
                    task_type=task_instance.template.task_type,
                    reward_points=task_instance.template.reward_points,
                    account_id=self._require_submission_account_id(submission),
                    user_id=task_instance.user_id,
                    public_user_id=task_instance.user.public_user_id,
                    site_id=task_instance.site_id,
                    site_key=task_instance.site.site_key if task_instance.site is not None else None,
                    task_status=task_instance.status,
                    review_required=task_instance.review_required,
                    submission=await self._submission_service.get_submission(submission.id),
                    latest_decision=(
                        await self._serialize_decision(
                            latest_decision,
                            fallback_account_id=self._require_submission_account_id(submission),
                        )
                        if latest_decision
                        else None
                    ),
                )
            )
        return items

    async def get_submission_detail(self, submission_id: str) -> ReviewQueueItemResponse:
        submission = self._session.execute(
            select(TaskSubmission)
            .options(joinedload(TaskSubmission.task_instance).joinedload(TaskInstance.template))
            .options(joinedload(TaskSubmission.task_instance).joinedload(TaskInstance.user))
            .options(joinedload(TaskSubmission.task_instance).joinedload(TaskInstance.site))
            .where(TaskSubmission.id == submission_id)
        ).unique().scalars().first()
        if submission is None:
            raise LookupError(f"Task submission '{submission_id}' was not found.")
        task_instance = submission.task_instance
        latest_decision = self._latest_decision_model(submission.id)
        return ReviewQueueItemResponse(
            task_instance_id=task_instance.id,
            template_id=task_instance.template_id,
            template_task_key=task_instance.template.task_key,
            template_name=task_instance.template.name,
            template_title=task_instance.template.title,
            template_description=task_instance.template.description,
            task_type=task_instance.template.task_type,
            reward_points=task_instance.template.reward_points,
            account_id=self._require_submission_account_id(submission),
            user_id=task_instance.user_id,
            public_user_id=task_instance.user.public_user_id,
            site_id=task_instance.site_id,
            site_key=task_instance.site.site_key if task_instance.site is not None else None,
            task_status=task_instance.status,
            review_required=task_instance.review_required,
            submission=await self._submission_service.get_submission(submission.id),
            latest_decision=(
                await self._serialize_decision(
                    latest_decision,
                    fallback_account_id=self._require_submission_account_id(submission),
                )
                if latest_decision
                else None
            ),
        )

    async def approve_submission(
        self,
        *,
        submission_id: str,
        reviewer_actor_id: str,
        payload: TaskReviewDecisionActionRequest,
    ) -> TaskReviewDecisionResponse:
        return await self._finalize_submission(
            submission_id=submission_id,
            reviewer_actor_id=reviewer_actor_id,
            decision="approved",
            payload=payload,
        )

    async def reject_submission(
        self,
        *,
        submission_id: str,
        reviewer_actor_id: str,
        payload: TaskReviewDecisionActionRequest,
    ) -> TaskReviewDecisionResponse:
        if not (payload.reason_code or payload.reason_text):
            raise ValueError("Rejected submissions require reason_code or reason_text.")
        return await self._finalize_submission(
            submission_id=submission_id,
            reviewer_actor_id=reviewer_actor_id,
            decision="rejected",
            payload=payload,
        )

    async def _finalize_submission(
        self,
        *,
        submission_id: str,
        reviewer_actor_id: str,
        decision: str,
        payload: TaskReviewDecisionActionRequest,
    ) -> TaskReviewDecisionResponse:
        submission = self._session.scalars(
            select(TaskSubmission)
            .options(joinedload(TaskSubmission.task_instance))
            .where(TaskSubmission.id == submission_id)
        ).first()
        if submission is None:
            raise LookupError(f"Task submission '{submission_id}' was not found.")
        if submission.status != "under_review":
            raise ValueError(
                f"Task submission '{submission_id}' cannot be reviewed from status '{submission.status}'."
            )

        now = utc_now()
        submission.status = decision
        submission.review_completed_at = now
        task_instance = submission.task_instance
        task_instance.status = decision
        task_instance.reviewed_at = now
        task_instance.completed_at = now if decision == "approved" else None
        review_decision = TaskReviewDecision(
            account_id=self._require_submission_account_id(submission),
            task_instance_id=task_instance.id,
            submission_id=submission.id,
            decision=decision,
            decision_source="manual",
            reviewer_actor_id=reviewer_actor_id,
            reason_code=payload.reason_code,
            reason_text=payload.reason_text,
            evidence_json=payload.evidence_json,
        )
        self._session.add(submission)
        self._session.add(task_instance)
        self._session.add(review_decision)
        self._session.commit()
        self._session.refresh(review_decision)
        task_reviews_total.labels(decision=decision).inc()
        return await self._serialize_decision(review_decision)

    def _latest_decision_model(self, submission_id: str) -> TaskReviewDecision | None:
        return self._session.scalars(
            select(TaskReviewDecision)
            .where(TaskReviewDecision.submission_id == submission_id)
            .order_by(TaskReviewDecision.created_at.desc(), TaskReviewDecision.id.desc())
        ).first()

    @staticmethod
    async def _serialize_decision(
        decision: TaskReviewDecision,
        *,
        fallback_account_id: str | None = None,
    ) -> TaskReviewDecisionResponse:
        return TaskReviewDecisionResponse(
            id=decision.id,
            account_id=decision.account_id or fallback_account_id,
            submission_id=decision.submission_id,
            task_instance_id=decision.task_instance_id,
            decision=decision.decision,
            decision_source=decision.decision_source,
            reviewer_actor_id=decision.reviewer_actor_id,
            reason_code=decision.reason_code,
            reason_text=decision.reason_text,
            evidence_json=decision.evidence_json or {},
            created_at=decision.created_at,
        )

    @staticmethod
    def _resolve_account_id(task_instance: TaskInstance) -> str | None:
        return (
            task_instance.account_id
            or task_instance.template.account_id
            or (task_instance.site.account_id if task_instance.site is not None else None)
            or task_instance.user.account_id
            or (
                task_instance.user.registration_site.account_id
                if task_instance.user.registration_site is not None
                else None
            )
        )

    def _require_submission_account_id(self, submission: TaskSubmission) -> str:
        if submission.account_id is not None:
            return submission.account_id
        account_id = self._resolve_account_id(submission.task_instance)
        if account_id is None:
            raise ValueError(
                f"Task submission '{submission.id}' does not have a resolved account scope."
            )
        return account_id
