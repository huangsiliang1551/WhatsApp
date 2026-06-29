from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.db.models import (
    MemberVerificationRequest,
    MemberTaskBatch,
    MemberTaskDayQuota,
    TaskPackageInstance,
    TaskPackageTemplate,
    TaskSystemConfig,
    WalletAccount,
    WalletLedgerEntry,
)
from app.schemas.h5_task_runtime import H5TaskEntryStateMemberPayload, H5TaskEntryStateResponse
from app.services.h5_member_auth_service import H5MemberContext
from app.services.member_task_quota_service import MemberTaskQuotaService
from app.services.task_product_generation_service import TaskProductGenerationService
from app.schemas.member_task_quota import MemberTaskQuotaPlanIssueRequest


class H5TaskRuntimeService:
    def __init__(self, *, session: Session) -> None:
        self._session = session

    async def get_entry_state(
        self,
        *,
        context: H5MemberContext,
    ) -> H5TaskEntryStateResponse:
        config = self._resolve_task_system_config(context=context)
        wallet = self._load_wallet(context=context)
        packages = self._load_packages(context=context)
        real_recharge_amount = self._load_real_recharge_amount(context=context)
        current_verification_status = self._load_current_verification_status(context=context)

        response = H5TaskEntryStateResponse(
            state="no_task",
            redirect_path="/h5/tasks",
            certification_required_amount=float(config.certified_recharge_threshold),
            current_real_recharge_amount=float(real_recharge_amount),
            remaining_recharge_amount=float(
                max(Decimal("0.00"), Decimal(config.certified_recharge_threshold) - real_recharge_amount)
            ),
            system_balance=float(Decimal(wallet.system_balance)) if wallet is not None else 0,
            task_balance=float(Decimal(wallet.task_balance)) if wallet is not None else 0,
            member=H5TaskEntryStateMemberPayload(
                public_user_id=context.user.public_user_id,
                site_key=context.site.site_key,
            ),
        )

        if not context.user.has_whatsapp:
            response.state = "need_whatsapp_binding"
            response.redirect_path = "/h5/whatsapp"
            return response

        if config.newbie_task_enabled:
            rookie_package = next(
                (
                    package
                    for package in packages
                    if package.template.package_type == "rookie" and package.status in {"pending_claim", "active"}
                ),
                None,
            )
            if rookie_package is not None:
                response.task_package_id = rookie_package.id
                response.redirect_path = f"/h5/tasks/package/{rookie_package.id}"
                response.state = "newbie_task_available" if rookie_package.status == "pending_claim" else "newbie_task_active"
                return response

        if (
            wallet is not None
            and config.show_task_balance_transfer_prompt
            and Decimal(wallet.task_balance) >= Decimal(config.min_task_balance_transfer_prompt_amount)
        ):
            response.state = "task_balance_transfer_prompt"
            response.redirect_path = "/h5/wallet"
            return response

        official_package = next(
            (
                package
                for package in packages
                if package.template.package_type != "rookie" and package.status in {"pending_claim", "active"}
            ),
            None,
        )
        is_certified = self._is_certified(
            config=config,
            current_verification_status=current_verification_status,
            real_recharge_amount=real_recharge_amount,
        )
        waiting_for_batch_slot = False
        if official_package is None and is_certified:
            if self._has_reached_active_package_limit(context=context, config=config):
                waiting_for_batch_slot = True
            elif self._has_reached_active_batch_limit(context=context, config=config):
                waiting_for_batch_slot = True
            else:
                official_package, waiting_for_issue_window = self._ensure_next_official_package(
                    context=context,
                    config=config,
                )
                if waiting_for_issue_window:
                    waiting_for_batch_slot = True
        if official_package is not None and is_certified:
            response.task_package_id = official_package.id
            response.redirect_path = f"/h5/tasks/package/{official_package.id}"
            response.state = (
                "official_batch_available" if official_package.status == "pending_claim" else "official_batch_active"
            )
            return response

        if waiting_for_batch_slot:
            response.state = "waiting_next_batch"
            response.redirect_path = "/h5/tasks"
            return response

        if not is_certified and config.certified_member_enabled:
            response.state = "need_certification"
            response.redirect_path = "/h5/wallet/recharge"
            return response

        if official_package is not None:
            response.task_package_id = official_package.id
            response.redirect_path = f"/h5/tasks/package/{official_package.id}"
            response.state = (
                "official_batch_available" if official_package.status == "pending_claim" else "official_batch_active"
            )
            return response

        response.redirect_path = "/h5/tasks"
        return response

    def _resolve_task_system_config(self, *, context: H5MemberContext) -> TaskSystemConfig:
        site_config = self._session.scalar(
            select(TaskSystemConfig)
            .where(
                TaskSystemConfig.account_id == context.account_id,
                TaskSystemConfig.site_id == context.site.id,
            )
            .order_by(TaskSystemConfig.created_at.desc(), TaskSystemConfig.id.desc())
        )
        if site_config is not None:
            return site_config

        account_config = self._session.scalar(
            select(TaskSystemConfig)
            .where(
                TaskSystemConfig.account_id == context.account_id,
                TaskSystemConfig.site_id.is_(None),
            )
            .order_by(TaskSystemConfig.created_at.desc(), TaskSystemConfig.id.desc())
        )
        if account_config is not None:
            return account_config

        return TaskSystemConfig(account_id=context.account_id, site_id=context.site.id)

    def _load_wallet(self, *, context: H5MemberContext) -> WalletAccount | None:
        return self._session.scalar(
            select(WalletAccount).where(
                WalletAccount.account_id == context.account_id,
                WalletAccount.user_id == context.user.id,
            )
        )

    def _load_packages(self, *, context: H5MemberContext) -> list[TaskPackageInstance]:
        return list(
            self._session.execute(
                select(TaskPackageInstance)
                .options(joinedload(TaskPackageInstance.template))
                .where(
                    TaskPackageInstance.account_id == context.account_id,
                    TaskPackageInstance.user_id == context.user.id,
                    TaskPackageInstance.site_id == context.site.id,
                )
                .order_by(TaskPackageInstance.created_at.asc(), TaskPackageInstance.id.asc())
            ).unique().scalars().all()
        )

    def _load_real_recharge_amount(self, *, context: H5MemberContext) -> Decimal:
        amount = self._session.scalar(
            select(func.coalesce(func.sum(WalletLedgerEntry.amount), 0))
            .where(
                WalletLedgerEntry.account_id == context.account_id,
                WalletLedgerEntry.user_id == context.user.id,
                WalletLedgerEntry.direction == "credit",
                WalletLedgerEntry.status == "paid",
                WalletLedgerEntry.is_real_recharge.is_(True),
            )
        )
        return Decimal(amount or 0)

    def _load_current_verification_status(self, *, context: H5MemberContext) -> str:
        request = self._session.scalar(
            select(MemberVerificationRequest)
            .where(
                MemberVerificationRequest.account_id == context.account_id,
                MemberVerificationRequest.member_profile_id == context.member_profile.id,
            )
            .order_by(MemberVerificationRequest.created_at.desc(), MemberVerificationRequest.id.desc())
            .limit(1)
        )
        return request.status if request is not None else "not_submitted"

    @staticmethod
    def _is_certified(
        *,
        config: TaskSystemConfig,
        current_verification_status: str,
        real_recharge_amount: Decimal,
    ) -> bool:
        if not config.certified_member_enabled:
            return True
        if current_verification_status == "approved":
            return True
        return real_recharge_amount >= Decimal(config.certified_recharge_threshold)

    def _ensure_next_official_package(
        self,
        *,
        context: H5MemberContext,
        config: TaskSystemConfig,
    ) -> tuple[TaskPackageInstance | None, bool]:
        if not config.official_plan_id:
            return None, False

        quota, waiting_for_issue_window = self._find_or_issue_next_quota(
            context=context,
            plan_id=config.official_plan_id,
        )
        if quota is None:
            return None, waiting_for_issue_window

        batch = self._find_or_generate_batch(quota_id=quota.id)
        return (
            self._session.scalar(
            select(TaskPackageInstance)
            .where(
                TaskPackageInstance.account_id == context.account_id,
                TaskPackageInstance.user_id == context.user.id,
                TaskPackageInstance.site_id == context.site.id,
                TaskPackageInstance.batch_id == batch.id,
                TaskPackageInstance.status.in_(["pending_claim", "active"]),
            )
            .order_by(TaskPackageInstance.batch_index.asc(), TaskPackageInstance.id.asc())
            ),
            False,
        )

    def _find_or_issue_next_quota(
        self,
        *,
        context: H5MemberContext,
        plan_id: str,
    ) -> tuple[MemberTaskDayQuota | None, bool]:
        existing_pending = self._session.scalar(
            select(MemberTaskDayQuota)
            .where(
                MemberTaskDayQuota.account_id == context.account_id,
                MemberTaskDayQuota.user_id == context.user.id,
                MemberTaskDayQuota.plan_id == plan_id,
                MemberTaskDayQuota.status.in_(["pending", "locked"]),
            )
            .order_by(MemberTaskDayQuota.day_no.asc(), MemberTaskDayQuota.created_at.asc(), MemberTaskDayQuota.id.asc())
        )
        if existing_pending is not None:
            return existing_pending, False

        next_day_no = (
            self._session.scalar(
                select(func.max(MemberTaskDayQuota.day_no)).where(
                    MemberTaskDayQuota.account_id == context.account_id,
                    MemberTaskDayQuota.user_id == context.user.id,
                    MemberTaskDayQuota.plan_id == plan_id,
                )
            )
            or 0
        ) + 1

        quota_service = MemberTaskQuotaService(self._session)
        try:
            created = quota_service.issue_quota_from_plan(
                MemberTaskQuotaPlanIssueRequest(
                    plan_id=plan_id,
                    user_id=context.user.id,
                    day_no=next_day_no,
                    created_by="h5_task_runtime",
                    metadata_json={
                        "source": "h5_task_runtime",
                        "site_id": context.site.id,
                    },
                )
            )
            return self._session.get(MemberTaskDayQuota, created.id), False
        except ValueError as exc:
            if "schedule window has not been reached" in str(exc):
                return None, True
            if "already exists" not in str(exc):
                raise
            return self._session.scalar(
                select(MemberTaskDayQuota).where(
                    MemberTaskDayQuota.account_id == context.account_id,
                    MemberTaskDayQuota.user_id == context.user.id,
                    MemberTaskDayQuota.plan_id == plan_id,
                    MemberTaskDayQuota.day_no == next_day_no,
                )
            ), False
        except LookupError:
            return None, False

    def _find_or_generate_batch(self, *, quota_id: str) -> MemberTaskBatch:
        existing_batch = self._session.scalar(
            select(MemberTaskBatch)
            .where(MemberTaskBatch.quota_id == quota_id)
            .order_by(MemberTaskBatch.created_at.desc(), MemberTaskBatch.id.desc())
        )
        if existing_batch is not None and existing_batch.products_generated:
            return existing_batch

        generation_service = TaskProductGenerationService(self._session)
        return generation_service.generate_for_quota(
            quota_id=quota_id,
            generated_by="h5_task_runtime",
        )

    def _has_reached_active_package_limit(
        self,
        *,
        context: H5MemberContext,
        config: TaskSystemConfig,
    ) -> bool:
        active_package_count = self._session.scalar(
            select(func.count(TaskPackageInstance.id))
            .join(TaskPackageInstance.template)
            .where(
                TaskPackageInstance.account_id == context.account_id,
                TaskPackageInstance.user_id == context.user.id,
                TaskPackageTemplate.package_type != "rookie",
                TaskPackageInstance.status.in_(["pending_claim", "active"]),
            )
        )
        return int(active_package_count or 0) >= int(config.max_active_packages_per_user)

    def _has_reached_active_batch_limit(
        self,
        *,
        context: H5MemberContext,
        config: TaskSystemConfig,
    ) -> bool:
        unfinished_batch_count = self._session.scalar(
            select(func.count(MemberTaskBatch.id))
            .where(
                MemberTaskBatch.account_id == context.account_id,
                MemberTaskBatch.user_id == context.user.id,
                MemberTaskBatch.status != "completed",
            )
        )
        return int(unfinished_batch_count or 0) >= int(config.max_active_batches_per_user)
