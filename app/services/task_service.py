from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.db.models import (
    AppUser,
    AudienceRuleSet,
    H5Site,
    TaskInstance,
    TaskSubmission,
    TaskTemplate,
    utc_now,
)
from app.schemas.tasks import (
    TaskInstanceCreateRequest,
    TaskInstanceResponse,
    TaskTemplateCreateRequest,
    TaskTemplateResponse,
)


TASK_INSTANCE_MUTABLE_STATUSES = {"available", "claimed"}


class TaskService:
    def __init__(self, session: Session) -> None:
        self._session = session

    async def list_task_templates(
        self,
        status: str | None = None,
        task_type: str | None = None,
        account_id: str | None = None,
    ) -> list[TaskTemplateResponse]:
        query = select(TaskTemplate).order_by(TaskTemplate.created_at.desc(), TaskTemplate.task_key)
        if status is not None:
            query = query.where(TaskTemplate.status == status)
        if task_type is not None:
            query = query.where(TaskTemplate.task_type == task_type)
        if account_id is not None:
            query = query.where(TaskTemplate.account_id == account_id)
        templates = self._session.scalars(query).all()
        return [self._serialize_task_template(template) for template in templates]

    async def create_task_template(self, payload: TaskTemplateCreateRequest) -> TaskTemplateResponse:
        if self._session.scalars(select(TaskTemplate).where(TaskTemplate.task_key == payload.task_key)).first():
            raise ValueError(f"Task key '{payload.task_key}' already exists.")

        if payload.audience_rule_set_id is not None:
            audience_rule = self._session.get(AudienceRuleSet, payload.audience_rule_set_id)
            if audience_rule is None:
                raise LookupError(f"Audience rule set '{payload.audience_rule_set_id}' was not found.")

        template = TaskTemplate(
            account_id=self.resolve_create_template_account_id(payload),
            task_key=payload.task_key,
            name=payload.name,
            title=payload.title,
            description=payload.description,
            task_type=payload.task_type,
            status=payload.status,
            audience_rule_set_id=payload.audience_rule_set_id,
            reward_amount=payload.reward_amount,
            reward_points=payload.reward_points,
            claim_timeout_seconds=payload.claim_timeout_seconds,
            auto_review_enabled=payload.auto_review_enabled,
            metadata_json=payload.metadata_json,
        )
        self._session.add(template)
        self._session.commit()
        self._session.refresh(template)
        return self._serialize_task_template(template)

    async def list_task_instances(
        self,
        status: str | None = None,
        template_id: str | None = None,
        user_id: str | None = None,
        account_id: str | None = None,
    ) -> list[TaskInstanceResponse]:
        query = (
            select(TaskInstance)
            .options(joinedload(TaskInstance.template))
            .options(joinedload(TaskInstance.user))
            .options(joinedload(TaskInstance.site))
            .options(joinedload(TaskInstance.submissions))
            .options(joinedload(TaskInstance.tickets))
            .order_by(TaskInstance.created_at.desc(), TaskInstance.id)
        )
        if status is not None:
            query = query.where(TaskInstance.status == status)
        if template_id is not None:
            query = query.where(TaskInstance.template_id == template_id)
        if user_id is not None:
            query = query.where(TaskInstance.user_id == user_id)
        if account_id is not None:
            query = query.where(TaskInstance.account_id == account_id)
        instances = self._session.execute(query).unique().scalars().all()
        return [self._serialize_task_instance(instance) for instance in instances]

    async def create_task_instance(self, payload: TaskInstanceCreateRequest) -> TaskInstanceResponse:
        template, user, site, resolved_account_id = self._prepare_create_instance_context(payload)

        instance = TaskInstance(
            account_id=resolved_account_id,
            template_id=template.id,
            user_id=user.id,
            site_id=site.id if site is not None else user.registration_site_id,
            status="available",
            claim_timeout_seconds_snapshot=template.claim_timeout_seconds,
            review_required=payload.review_required,
            available_at=utc_now(),
            metadata_json=payload.metadata_json,
        )
        self._session.add(instance)
        self._session.commit()
        return (await self.list_task_instances(template_id=template.id, user_id=user.id))[0]

    async def resolve_create_instance_account_id(self, payload: TaskInstanceCreateRequest) -> str | None:
        (_template, _user, _site, resolved_account_id) = self._prepare_create_instance_context(payload)
        return resolved_account_id

    async def claim_task_instance(self, task_instance_id: str) -> TaskInstanceResponse:
        instance = self._session.get(TaskInstance, task_instance_id)
        if instance is None:
            raise LookupError(f"Task instance '{task_instance_id}' was not found.")
        if instance.status != "available":
            raise ValueError(
                f"Task instance '{task_instance_id}' cannot be claimed from status '{instance.status}'."
            )

        claimed_at = utc_now()
        instance.status = "claimed"
        instance.claimed_at = claimed_at
        instance.claim_deadline_at = claimed_at + timedelta(seconds=instance.claim_timeout_seconds_snapshot)
        self._session.add(instance)
        self._session.commit()
        return await self.get_task_instance(task_instance_id)

    async def resolve_task_instance_account_id(self, task_instance_id: str) -> str | None:
        instance = self._session.execute(
            select(TaskInstance)
            .options(joinedload(TaskInstance.template))
            .options(joinedload(TaskInstance.user))
            .options(joinedload(TaskInstance.site))
            .where(TaskInstance.id == task_instance_id)
        ).unique().scalars().first()
        if instance is None:
            raise LookupError(f"Task instance '{task_instance_id}' was not found.")
        return self._resolve_task_instance_account_id(
            current_account_id=instance.account_id,
            template=instance.template,
            site=instance.site,
            fallback_user=instance.user,
            fallback_site=instance.user.registration_site,
        )

    async def get_task_instance(self, task_instance_id: str) -> TaskInstanceResponse:
        instance = self._session.execute(
            select(TaskInstance)
            .options(joinedload(TaskInstance.template))
            .options(joinedload(TaskInstance.user))
            .options(joinedload(TaskInstance.site))
            .options(joinedload(TaskInstance.submissions))
            .options(joinedload(TaskInstance.tickets))
            .where(TaskInstance.id == task_instance_id)
        ).unique().scalars().first()
        if instance is None:
            raise LookupError(f"Task instance '{task_instance_id}' was not found.")
        return self._serialize_task_instance(instance)

    def _serialize_task_template(self, template: TaskTemplate) -> TaskTemplateResponse:
        return TaskTemplateResponse.model_validate(
            {
                "id": template.id,
                "account_id": template.account_id,
                "task_key": template.task_key,
                "name": template.name,
                "title": template.title,
                "description": template.description,
                "task_type": template.task_type,
                "status": template.status,
                "audience_rule_set_id": template.audience_rule_set_id,
                "reward_amount": template.reward_amount,
                "reward_points": template.reward_points,
                "claim_timeout_seconds": template.claim_timeout_seconds,
                "auto_review_enabled": template.auto_review_enabled,
                "metadata_json": template.metadata_json,
                "created_at": template.created_at,
                "updated_at": template.updated_at,
            }
        )

    def _serialize_task_instance(self, instance: TaskInstance) -> TaskInstanceResponse:
        latest_submission = None
        if instance.submissions:
            latest_submission = max(instance.submissions, key=lambda item: (item.submission_no, item.created_at))
        active_ticket_count = sum(1 for ticket in instance.tickets if ticket.is_active)
        review_status_summary = latest_submission.status if latest_submission is not None else None
        return TaskInstanceResponse.model_validate(
            {
                "id": instance.id,
                "template_id": instance.template_id,
                "template_task_key": instance.template.task_key,
                "template_name": instance.template.name,
                "template_title": instance.template.title,
                "template_description": instance.template.description,
                "task_type": instance.template.task_type,
                "reward_points": instance.template.reward_points,
                "account_id": self._resolve_task_instance_account_id(
                    current_account_id=instance.account_id,
                    template=instance.template,
                    site=instance.site,
                    fallback_user=instance.user,
                    fallback_site=instance.user.registration_site,
                ),
                "user_id": instance.user_id,
                "public_user_id": instance.user.public_user_id,
                "site_id": instance.site_id,
                "site_key": instance.site.site_key if instance.site else None,
                "status": instance.status,
                "claim_timeout_seconds_snapshot": instance.claim_timeout_seconds_snapshot,
                "review_required": instance.review_required,
                "latest_submission_id": latest_submission.id if latest_submission is not None else None,
                "active_ticket_count": active_ticket_count,
                "review_status_summary": review_status_summary,
                "available_at": instance.available_at,
                "claimed_at": instance.claimed_at,
                "claim_deadline_at": instance.claim_deadline_at,
                "submitted_at": instance.submitted_at,
                "reviewed_at": instance.reviewed_at,
                "completed_at": instance.completed_at,
                "expired_at": instance.expired_at,
                "metadata_json": instance.metadata_json,
                "created_at": instance.created_at,
                "updated_at": instance.updated_at,
            }
        )

    @staticmethod
    def _extract_compat_account_id(metadata_json: dict[str, object] | None) -> str | None:
        if not isinstance(metadata_json, dict):
            return None
        value = metadata_json.get("account_id")
        if isinstance(value, str) and value:
            return value
        return None

    def resolve_create_template_account_id(self, payload: TaskTemplateCreateRequest) -> str | None:
        return payload.account_id or self._extract_compat_account_id(payload.metadata_json)

    def _prepare_create_instance_context(
        self,
        payload: TaskInstanceCreateRequest,
    ) -> tuple[TaskTemplate, AppUser, H5Site | None, str | None]:
        template = self._session.get(TaskTemplate, payload.template_id)
        if template is None:
            raise LookupError(f"Task template '{payload.template_id}' was not found.")

        user = self._session.get(AppUser, payload.user_id)
        if user is None:
            raise LookupError(f"User '{payload.user_id}' was not found.")
        if user.is_anonymous:
            raise ValueError("Anonymous users cannot receive formal task instances.")

        site: H5Site | None = None
        if payload.site_id is not None:
            site = self._session.get(H5Site, payload.site_id)
            if site is None:
                raise LookupError(f"Site '{payload.site_id}' was not found.")

        resolved_account_id = (
            payload.account_id
            or self._resolve_task_instance_account_id(
                current_account_id=None,
                template=template,
                site=site,
                fallback_user=user,
                fallback_site=user.registration_site,
            )
        )
        fallback_site = user.registration_site
        if payload.account_id is not None and template.account_id is not None and payload.account_id != template.account_id:
            raise ValueError("Task instance account_id does not match the task template account_id.")
        if site is not None and site.account_id is not None and resolved_account_id is not None and site.account_id != resolved_account_id:
            raise ValueError("Task instance site account_id does not match the task account scope.")
        if (
            site is None
            and fallback_site is not None
            and fallback_site.account_id is not None
            and resolved_account_id is not None
            and fallback_site.account_id != resolved_account_id
        ):
            raise ValueError("Task instance registration site account_id does not match the task account scope.")
        return template, user, site, resolved_account_id

    @staticmethod
    def _resolve_task_instance_account_id(
        *,
        current_account_id: str | None,
        template: TaskTemplate,
        site: H5Site | None,
        fallback_user: AppUser | None,
        fallback_site: H5Site | None,
    ) -> str | None:
        return (
            current_account_id
            or template.account_id
            or (site.account_id if site is not None else None)
            or (fallback_user.account_id if fallback_user is not None else None)
            or (fallback_site.account_id if fallback_site is not None else None)
        )
