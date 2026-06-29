from __future__ import annotations

from app.db.models import H5Site, TaskIssuePlan, TaskSystemConfig
from app.schemas.task_system_config import TaskSystemConfigResponse, TaskSystemConfigUpsertRequest
from sqlalchemy import select
from sqlalchemy.orm import Session


class TaskSystemConfigService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_config(self, *, account_id: str, site_id: str | None) -> TaskSystemConfigResponse:
        self._validate_site(account_id=account_id, site_id=site_id)
        config = self._find_config(account_id=account_id, site_id=site_id)
        if config is None and site_id is not None:
            config = self._find_config(account_id=account_id, site_id=None)
        if config is None:
            return TaskSystemConfigResponse(account_id=account_id, site_id=site_id)
        return self._serialize(config, response_site_id=site_id)

    def upsert_config(self, payload: TaskSystemConfigUpsertRequest) -> TaskSystemConfigResponse:
        self._validate_site(account_id=payload.account_id, site_id=payload.site_id)
        self._validate_plan(account_id=payload.account_id, plan_id=payload.newbie_plan_id)
        self._validate_plan(account_id=payload.account_id, plan_id=payload.official_plan_id)

        config = self._collapse_duplicate_scope(account_id=payload.account_id, site_id=payload.site_id)
        if config is None:
            config = TaskSystemConfig(account_id=payload.account_id, site_id=payload.site_id)
            self.session.add(config)

        config.status = payload.status
        config.whatsapp_binding_reward_enabled = payload.whatsapp_binding_reward_enabled
        config.whatsapp_binding_reward_amount = payload.whatsapp_binding_reward_amount
        config.whatsapp_binding_reward_wallet_type = payload.whatsapp_binding_reward_wallet_type
        config.whatsapp_binding_reward_currency = payload.whatsapp_binding_reward_currency
        config.certified_member_enabled = payload.certified_member_enabled
        config.certified_recharge_threshold = payload.certified_recharge_threshold
        config.certified_recharge_scope = payload.certified_recharge_scope
        config.auto_certify_on_recharge = payload.auto_certify_on_recharge
        config.newbie_task_enabled = payload.newbie_task_enabled
        config.newbie_plan_id = payload.newbie_plan_id
        config.newbie_auto_popup = payload.newbie_auto_popup
        config.official_plan_id = payload.official_plan_id
        config.show_task_balance_transfer_prompt = payload.show_task_balance_transfer_prompt
        config.min_task_balance_transfer_prompt_amount = payload.min_task_balance_transfer_prompt_amount
        config.max_active_batches_per_user = payload.max_active_batches_per_user
        config.max_active_packages_per_user = payload.max_active_packages_per_user
        config.metadata_json = payload.metadata_json
        self.session.flush()
        self.session.commit()
        self.session.refresh(config)
        return self._serialize(config)

    def _find_config(self, *, account_id: str, site_id: str | None) -> TaskSystemConfig | None:
        stmt = select(TaskSystemConfig).where(TaskSystemConfig.account_id == account_id)
        if site_id is None:
            stmt = stmt.where(TaskSystemConfig.site_id.is_(None))
        else:
            stmt = stmt.where(TaskSystemConfig.site_id == site_id)
        stmt = stmt.order_by(
            TaskSystemConfig.updated_at.desc(),
            TaskSystemConfig.created_at.desc(),
            TaskSystemConfig.id.desc(),
        )
        return self.session.scalars(stmt).first()

    def _collapse_duplicate_scope(self, *, account_id: str, site_id: str | None) -> TaskSystemConfig | None:
        stmt = select(TaskSystemConfig).where(TaskSystemConfig.account_id == account_id)
        if site_id is None:
            stmt = stmt.where(TaskSystemConfig.site_id.is_(None))
        else:
            stmt = stmt.where(TaskSystemConfig.site_id == site_id)
        stmt = stmt.order_by(
            TaskSystemConfig.updated_at.desc(),
            TaskSystemConfig.created_at.desc(),
            TaskSystemConfig.id.desc(),
        )
        rows = self.session.scalars(stmt).all()
        if not rows:
            return None
        keeper = rows[0]
        for duplicate in rows[1:]:
            self.session.delete(duplicate)
        self.session.flush()
        return keeper

    def _validate_site(self, *, account_id: str, site_id: str | None) -> None:
        if site_id is None:
            return
        site = self.session.get(H5Site, site_id)
        if site is None:
            raise LookupError(f"Site '{site_id}' was not found.")
        if site.account_id != account_id:
            raise ValueError(f"Site '{site_id}' does not belong to account '{account_id}'.")

    def _validate_plan(self, *, account_id: str, plan_id: str | None) -> None:
        if not plan_id:
            return
        plan = self.session.get(TaskIssuePlan, plan_id)
        if plan is None:
            raise LookupError(f"Task issue plan '{plan_id}' was not found.")
        if plan.account_id != account_id:
            raise ValueError(f"Task issue plan '{plan_id}' does not belong to account '{account_id}'.")

    @staticmethod
    def _serialize(
        config: TaskSystemConfig,
        *,
        response_site_id: str | None = None,
    ) -> TaskSystemConfigResponse:
        return TaskSystemConfigResponse(
            account_id=config.account_id,
            site_id=response_site_id if response_site_id is not None else config.site_id,
            status=config.status,
            whatsapp_binding_reward_enabled=config.whatsapp_binding_reward_enabled,
            whatsapp_binding_reward_amount=config.whatsapp_binding_reward_amount,
            whatsapp_binding_reward_wallet_type=config.whatsapp_binding_reward_wallet_type,
            whatsapp_binding_reward_currency=config.whatsapp_binding_reward_currency,
            certified_member_enabled=config.certified_member_enabled,
            certified_recharge_threshold=config.certified_recharge_threshold,
            certified_recharge_scope=config.certified_recharge_scope,
            auto_certify_on_recharge=config.auto_certify_on_recharge,
            newbie_task_enabled=config.newbie_task_enabled,
            newbie_plan_id=config.newbie_plan_id,
            newbie_auto_popup=config.newbie_auto_popup,
            official_plan_id=config.official_plan_id,
            show_task_balance_transfer_prompt=config.show_task_balance_transfer_prompt,
            min_task_balance_transfer_prompt_amount=config.min_task_balance_transfer_prompt_amount,
            max_active_batches_per_user=config.max_active_batches_per_user,
            max_active_packages_per_user=config.max_active_packages_per_user,
            metadata_json=config.metadata_json,
            created_at=config.created_at,
            updated_at=config.updated_at,
        )
