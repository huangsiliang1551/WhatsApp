from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
import hashlib
import time
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.db.models import (
    AppUser,
    InviteCode,
    MemberNotification,
    MemberOrder,
    MemberProfile,
    PromotionTaskInstance,
    PromotionTaskTemplate,
    TaskPackageInstance,
    TaskPackageInstanceItem,
    TaskPackageTemplate,
    UserReferral,
    WalletAccount,
    WalletLedgerEntry,
    WalletRechargeOrder,
    WalletTransferRequest,
    WithdrawalAuditLog,
    WithdrawalRequest,
    utc_now,
)
from app.schemas.h5_member_commerce import (
    H5LogisticsResponse,
    H5MemberOrderResponse,
    H5TaskPackagePayload,
    H5TaskPackagePurchaseResponse,
    H5TaskPackagePromotionPayload,
    H5WithdrawalAuditLogResponse,
    H5WithdrawalResponse,
    H5WithdrawLeaderboardEntryResponse,
    H5TaskPackageItemPayload,
    H5WalletSummaryResponse,
    H5WalletTransactionResponse,
)
from app.services.h5_member_auth_service import H5MemberContext
from app.services.h5_member_fragment_service import H5MemberFragmentService
from app.services.wallet_ledger_service import WalletLedgerService


@dataclass(slots=True)
class _CacheEntry:
    data: object
    expires_at: float


class H5MemberCommerceService:
    SUPPORTED_PROMOTION_METRICS = {"invited_registrations", "recharged_invitees"}
    ORDER_CACHE_TTL: int = 300
    LOGISTICS_CACHE_TTL: int = 600

    def __init__(self, *, session: Session) -> None:
        self._session = session
        self._cache: dict[str, _CacheEntry] = {}
        self._wallet_ledger_service = WalletLedgerService(session=session)

    async def list_task_packages(self, *, context: H5MemberContext) -> list[H5TaskPackagePayload]:
        packages = self._session.execute(
            select(TaskPackageInstance)
            .options(joinedload(TaskPackageInstance.items))
            .options(joinedload(TaskPackageInstance.template))
            .where(
                TaskPackageInstance.account_id == context.account_id,
                TaskPackageInstance.user_id == context.user.id,
                TaskPackageInstance.site_id == context.site.id,
            )
            .order_by(TaskPackageInstance.created_at.desc(), TaskPackageInstance.id.desc())
        ).unique().scalars().all()
        changed = False
        payloads: list[H5TaskPackagePayload] = []
        for package in packages:
            changed = self._expire_if_needed(package) or changed
            payload, promotion_changed = self._serialize_task_package(package=package, context=context)
            changed = promotion_changed or changed
            payloads.append(payload)
        if changed:
            self._session.commit()
        return payloads

    async def get_task_package(
        self,
        *,
        context: H5MemberContext,
        package_id: str,
    ) -> H5TaskPackagePayload:
        package = self._require_package(context=context, package_id=package_id)
        changed = self._expire_if_needed(package)
        payload, promotion_changed = self._serialize_task_package(package=package, context=context)
        changed = promotion_changed or changed
        if changed:
            self._session.add(package)
            self._session.commit()
            self._session.refresh(package)
            payload, _ = self._serialize_task_package(package=package, context=context)
        return payload

    async def claim_task_package(
        self,
        *,
        context: H5MemberContext,
        package_id: str,
    ) -> H5TaskPackagePayload:
        package = self._require_package(context=context, package_id=package_id)
        if self._expire_if_needed(package):
            self._session.add(package)
            self._session.commit()
            self._session.refresh(package)
            payload, changed = self._serialize_task_package(package=package, context=context)
            if changed:
                self._session.commit()
                self._session.refresh(package)
                payload, _ = self._serialize_task_package(package=package, context=context)
            return payload
        payload = self._serialize_task_package_with_refresh(package=package, context=context)
        if package.status == "pending_claim" and package.template.package_type == "promotion":
            self._ensure_promotion_claim_ready(payload.promotion)
        if package.status == "pending_claim":
            now = utc_now()
            package.claimed_at = now
            if package.template.package_type == "promotion":
                wallet = self._require_wallet(context=context, create_if_missing=True)
                package.status = "completed"
                package.completed_at = now
                package.expires_at = now
                self._settle_task_package_reward(
                    context=context,
                    package=package,
                    wallet=wallet,
                    rewarded_at=now,
                )
                promotion_instance = self._session.scalars(
                    select(PromotionTaskInstance).where(
                        PromotionTaskInstance.account_id == context.account_id,
                        PromotionTaskInstance.task_package_instance_id == package.id,
                    )
                ).first()
                if promotion_instance is not None and promotion_instance.rewarded_at is None:
                    promotion_instance.rewarded_at = now
                    promotion_instance.status = "completed"
                    self._session.add(promotion_instance)
            else:
                package.status = "active"
                package.expires_at = now + timedelta(hours=package.completion_window_hours_snapshot)
            self._session.add(package)
            try:
                self._session.commit()
            except IntegrityError:
                self._session.rollback()
                reloaded_package = self._require_package(context=context, package_id=package_id)
                return self._serialize_task_package_with_refresh(package=reloaded_package, context=context)
            self._session.refresh(package)
        return self._serialize_task_package_with_refresh(package=package, context=context)

    async def purchase_task_package_item(
        self,
        *,
        context: H5MemberContext,
        package_id: str,
        item_id: str,
    ) -> H5TaskPackagePurchaseResponse:
        package = self._require_package(context=context, package_id=package_id)
        item = self._require_package_item(package=package, item_id=item_id)
        wallet = self._require_wallet(context=context, create_if_missing=True)

        if package.template.package_type == "promotion":
            return H5TaskPackagePurchaseResponse(
                success=False,
                task_package=self._serialize_task_package_with_refresh(package=package, context=context),
                wallet=self._serialize_wallet_summary(wallet),
                reason="Promotion task packages do not support item purchase.",
            )

        if self._expire_if_needed(package):
            self._session.add(package)
            self._session.commit()
            return H5TaskPackagePurchaseResponse(
                success=False,
                task_package=self._serialize_task_package(package=package, context=context)[0],
                wallet=self._serialize_wallet_summary(wallet),
                reason="Task package has expired.",
            )

        if package.status != "active":
            return H5TaskPackagePurchaseResponse(
                success=False,
                task_package=self._serialize_task_package(package=package, context=context)[0],
                wallet=self._serialize_wallet_summary(wallet),
                reason="Task package is not available for purchase.",
            )

        if item.completed_at is not None:
            return H5TaskPackagePurchaseResponse(
                success=True,
                task_package=self._serialize_task_package(package=package, context=context)[0],
                wallet=self._serialize_wallet_summary(wallet),
                reason="Task package item is already completed.",
            )

        item_price = Decimal(item.price)
        if Decimal(wallet.system_balance) < item_price:
            return H5TaskPackagePurchaseResponse(
                success=False,
                task_package=self._serialize_task_package(package=package, context=context)[0],
                wallet=self._serialize_wallet_summary(wallet),
                reason="System balance is insufficient.",
            )

        now = utc_now()
        fragment_drop = None
        order = MemberOrder(
            account_id=context.account_id,
            user_id=context.user.id,
            package_instance_id=package.id,
            order_no=f"ORD-{uuid4().hex[:10].upper()}",
            package_title=package.template.title,
            product_name=item.product_name,
            amount=item_price,
            currency=item.currency,
            status="paid",
            source_label=package.template.title,
            ordered_at=now,
        )
        self._session.add(order)
        self._session.flush()

        item.order_id = order.id
        item.completed_at = now
        self._session.add(item)
        self._invalidate_cache(f"orders:{context.account_id}:{context.user.id}")
        self._wallet_ledger_service.debit_system_balance(
            wallet=wallet,
            account_id=context.account_id,
            user_id=context.user.id,
            amount=item_price,
            currency=item.currency,
            transaction_type="purchase",
            source_type="purchase",
            note=f"{package.template.title} / {item.product_name}",
            reference_type="member_order",
            reference_id=order.id,
        )

        if all(entry.completed_at is not None for entry in package.items):
            package.status = "completed"
            package.completed_at = now
            self._settle_task_package_reward(
                context=context,
                package=package,
                wallet=wallet,
                rewarded_at=now,
            )
            fragment_service = H5MemberFragmentService(session=self._session)
            fragment_drop = fragment_service.award_fragment_drop(
                context=context,
                source="task",
                source_id=package.id,
                auto_commit=False,
            )

        self._session.commit()
        refreshed_package = self._require_package(context=context, package_id=package.id)
        refreshed_wallet = self._require_wallet(context=context, create_if_missing=True)
        serialized_package, changed = self._serialize_task_package(package=refreshed_package, context=context)
        if changed:
            self._session.commit()
            refreshed_package = self._require_package(context=context, package_id=package.id)
            serialized_package, _ = self._serialize_task_package(package=refreshed_package, context=context)
        return H5TaskPackagePurchaseResponse(
            success=True,
            order=self._serialize_order(order),
            task_package=serialized_package,
            wallet=self._serialize_wallet_summary(refreshed_wallet),
            fragment_drop=fragment_drop,
        )

    async def list_orders(self, *, context: H5MemberContext) -> list[H5MemberOrderResponse]:
        cache_key = f"orders:{context.account_id}:{context.user.id}"
        cached = self._get_cache(cache_key)
        if cached is not None:
            return cached  # type: ignore[return-value]
        orders = self._session.scalars(
            select(MemberOrder)
            .where(
                MemberOrder.account_id == context.account_id,
                MemberOrder.user_id == context.user.id,
            )
            .order_by(MemberOrder.ordered_at.desc(), MemberOrder.id.desc())
        ).all()
        result = [self._serialize_order(item) for item in orders]
        self._set_cache(cache_key, result, ttl=self.ORDER_CACHE_TTL)
        return result

    async def get_wallet_summary(
        self,
        *,
        context: H5MemberContext,
        create_if_missing: bool = True,
    ) -> H5WalletSummaryResponse | None:
        wallet = self._require_wallet(context=context, create_if_missing=create_if_missing)
        if wallet is None:
            return None
        return self._serialize_wallet_summary(wallet)

    async def list_wallet_transactions(
        self,
        *,
        context: H5MemberContext,
    ) -> list[H5WalletTransactionResponse]:
        wallet = self._require_wallet(context=context, create_if_missing=True)
        ledger_entries = self._session.scalars(
            select(WalletLedgerEntry)
            .where(WalletLedgerEntry.wallet_account_id == wallet.id)
            .order_by(WalletLedgerEntry.created_at.desc(), WalletLedgerEntry.id.desc())
        ).all()
        return [self._serialize_wallet_transaction(item) for item in ledger_entries]

    async def create_recharge(
        self,
        *,
        context: H5MemberContext,
        amount: Decimal,
    ) -> H5WalletSummaryResponse:
        wallet = self._require_wallet(context=context, create_if_missing=True)
        now = utc_now()
        sanitized_amount = self._quantize(amount)
        recharge = WalletRechargeOrder(
            account_id=context.account_id,
            wallet_account_id=wallet.id,
            user_id=context.user.id,
            amount=sanitized_amount,
            currency=wallet.currency,
            status="paid",
            credited_at=now,
        )
        self._session.add(recharge)
        self._session.flush()
        self._mark_referral_recharge(
            context=context,
            recharge_order_id=recharge.id,
            recharged_at=now,
        )
        self._wallet_ledger_service.credit_system_balance(
            wallet=wallet,
            account_id=context.account_id,
            user_id=context.user.id,
            amount=sanitized_amount,
            currency=wallet.currency,
            transaction_type="recharge",
            source_type="user_recharge",
            note="Recharge credited",
            reference_type="wallet_recharge_order",
            reference_id=recharge.id,
            fund_type="cash",
            is_real_recharge=True,
        )
        self._create_member_notification(
            context=context,
            category="wallet",
            title="Recharge credited",
            body_text=(
                f"Your recharge of {sanitized_amount:.2f} {wallet.currency} was credited "
                f"to system balance."
            ),
            reference_type="wallet_recharge_order",
            reference_id=recharge.id,
            metadata_json={
                "amount": float(sanitized_amount),
                "currency": wallet.currency,
                "transaction_type": "recharge",
            },
        )
        self._session.commit()
        return self._serialize_wallet_summary(wallet)

    async def transfer_task_balance(
        self,
        *,
        context: H5MemberContext,
        amount: Decimal,
    ) -> H5WalletSummaryResponse:
        wallet = self._require_wallet(context=context, create_if_missing=True)
        sanitized_amount = self._quantize(amount)
        if sanitized_amount <= Decimal("0"):
            raise ValueError("Transfer amount must be greater than zero.")
        if Decimal(wallet.task_balance) < sanitized_amount:
            raise ValueError("Task balance is insufficient.")
        transfer = WalletTransferRequest(
            account_id=context.account_id,
            wallet_account_id=wallet.id,
            user_id=context.user.id,
            amount=sanitized_amount,
            currency=wallet.currency,
            status="paid",
        )
        self._session.add(transfer)
        self._session.flush()
        self._wallet_ledger_service.transfer_task_to_system_bonus(
            wallet=wallet,
            account_id=context.account_id,
            user_id=context.user.id,
            amount=sanitized_amount,
            currency=wallet.currency,
            note_out="Transfer out from task balance",
            note_in="Transfer in from task balance",
            reference_type="wallet_transfer_request",
            reference_id=transfer.id,
        )
        self._create_member_notification(
            context=context,
            category="wallet",
            title="Task balance transferred",
            body_text=(
                f"You transferred {sanitized_amount:.2f} {wallet.currency} "
                f"from task balance to system balance."
            ),
            reference_type="wallet_transfer_request",
            reference_id=transfer.id,
            metadata_json={
                "amount": float(sanitized_amount),
                "currency": wallet.currency,
                "transaction_type": "task_to_system_transfer",
            },
        )
        self._session.commit()
        return self._serialize_wallet_summary(wallet)

    async def create_withdrawal(
        self,
        *,
        context: H5MemberContext,
        amount: Decimal,
        withdraw_account_type: str | None = None,
        bank_name: str | None = None,
        account_no: str | None = None,
    ) -> H5WithdrawalResponse:
        # TODO: BE2-023 — Add duplicate submission prevention. A user should not be able to
        # submit a new withdrawal request while there is an active pending withdrawal
        # (status in {"submitted", "reviewing", "approved"}) for the same user / account.
        wallet = self._require_wallet(context=context, create_if_missing=True)
        wallet = self._require_wallet_row_for_update(wallet_id=wallet.id)
        sanitized_amount = self._quantize(amount)
        if sanitized_amount <= Decimal("0"):
            raise ValueError("Withdrawal amount must be greater than zero.")

        system_balance = self._quantize(Decimal(wallet.system_balance))
        withdraw_threshold = self._quantize(Decimal(wallet.withdraw_threshold))
        if system_balance < withdraw_threshold:
            raise ValueError("System balance has not reached the withdraw threshold.")
        if system_balance < sanitized_amount:
            raise ValueError("System balance is insufficient.")

        now = utc_now()
        account_meta = self._build_withdraw_account_metadata(
            withdraw_account_type=withdraw_account_type,
            bank_name=bank_name,
            account_no=account_no,
        )
        withdrawal = WithdrawalRequest(
            account_id=context.account_id,
            wallet_account_id=wallet.id,
            user_id=context.user.id,
            member_profile_id=context.member_profile.id,
            request_no=f"WDR-{uuid4().hex[:12].upper()}",
            amount=sanitized_amount,
            withdraw_account_type=account_meta["withdraw_account_type"],
            bank_name=account_meta["bank_name"],
            account_no_masked=account_meta["account_no_masked"],
            account_fingerprint=account_meta["account_fingerprint"],
            account_snapshot_json=account_meta["account_snapshot_json"],
            currency=wallet.currency,
            status="submitted",
        )
        self._session.add(withdrawal)
        self._session.flush()
        self._apply_duplicate_account_risk(withdrawal=withdrawal)

        audit_log = WithdrawalAuditLog(
            account_id=context.account_id,
            withdrawal_request_id=withdrawal.id,
            status="submitted",
            note="Withdrawal request submitted",
            actor_type="member",
            actor_id=context.user.id,
        )
        ledger_entry = self._wallet_ledger_service.submit_withdrawal(
            wallet=wallet,
            withdrawal=withdrawal,
            note="Withdrawal request submitted",
        )
        self._session.add(audit_log)
        self._create_member_notification(
            context=context,
            category="wallet",
            title="Withdrawal submitted",
            body_text=(
                f"Your withdrawal request for {sanitized_amount:.2f} {wallet.currency} "
                f"was submitted successfully."
            ),
            reference_type="withdrawal_request",
            reference_id=withdrawal.id,
            metadata_json={
                "amount": float(sanitized_amount),
                "currency": wallet.currency,
                "transaction_type": "withdraw_request",
                "request_no": withdrawal.request_no,
            },
        )
        self._session.commit()
        return self._serialize_withdrawal(withdrawal, history=[audit_log])

    async def list_withdrawals(
        self,
        *,
        context: H5MemberContext,
    ) -> list[H5WithdrawalResponse]:
        withdrawals = self._session.scalars(
            select(WithdrawalRequest)
            .where(
                WithdrawalRequest.account_id == context.account_id,
                WithdrawalRequest.user_id == context.user.id,
            )
            .order_by(WithdrawalRequest.created_at.desc(), WithdrawalRequest.id.desc())
        ).all()
        return self._serialize_withdrawals(withdrawals)

    async def get_withdraw_leaderboard(
        self,
        *,
        context: H5MemberContext,
    ) -> list[H5WithdrawLeaderboardEntryResponse]:
        rows = self._session.execute(
            select(
                WithdrawalRequest.member_profile_id,
                MemberProfile.member_no,
                WithdrawalRequest.currency,
                func.sum(WithdrawalRequest.amount).label("total_amount"),
            )
            .join(MemberProfile, MemberProfile.id == WithdrawalRequest.member_profile_id)
            .where(
                WithdrawalRequest.account_id == context.account_id,
                WithdrawalRequest.status == "paid",
                WithdrawalRequest.member_profile_id.is_not(None),
            )
            .group_by(
                WithdrawalRequest.member_profile_id,
                MemberProfile.member_no,
                WithdrawalRequest.currency,
            )
            .order_by(func.sum(WithdrawalRequest.amount).desc(), MemberProfile.member_no.asc())
        ).all()
        entries: list[H5WithdrawLeaderboardEntryResponse] = []
        for index, row in enumerate(rows, start=1):
            total_amount = self._quantize(Decimal(row.total_amount))
            entries.append(
                H5WithdrawLeaderboardEntryResponse(
                    rank=index,
                    account_id_masked=self._mask_member_no(row.member_no),
                    amount=float(total_amount),
                    currency=row.currency,
                )
            )
        return entries

    async def get_logistics(
        self,
        *,
        context: H5MemberContext,
        order_no: str,
    ) -> H5LogisticsResponse:
        cache_key = f"logistics:{context.account_id}:{order_no}"
        cached = self._get_cache(cache_key)
        if cached is not None:
            return cached  # type: ignore[return-value]
        # Query order to verify ownership
        order = self._session.scalars(
            select(MemberOrder).where(
                MemberOrder.account_id == context.account_id,
                MemberOrder.user_id == context.user.id,
                MemberOrder.order_no == order_no,
            )
        ).first()
        if order is None:
            raise LookupError(f"Order '{order_no}' was not found.")
        # Stub logistics data — real implementation would call ecommerce provider
        result = H5LogisticsResponse(
            order_no=order_no,
            carrier="Standard Carrier",
            tracking_number=f"TRACK-{order_no[-8:].upper()}",
            current_status="in_transit",
            entries=[
                H5LogisticsEntryResponse(
                    status="shipped",
                    description="Package has been shipped",
                    timestamp=order.ordered_at,
                ),
                H5LogisticsEntryResponse(
                    status="in_transit",
                    description="Package is in transit",
                    timestamp=order.ordered_at,
                ),
            ],
        )
        self._set_cache(cache_key, result, ttl=self.LOGISTICS_CACHE_TTL)
        return result

    @staticmethod
    def _standard_error(message: str, *, code: str = "error") -> dict[str, object]:
        return {"error": True, "code": code, "message": message}

    def _get_cache(self, key: str) -> object | None:
        entry = self._cache.get(key)
        if entry is None:
            return None
        if time.time() >= entry.expires_at:
            self._cache.pop(key, None)
            return None
        return entry.data

    def _set_cache(self, key: str, data: object, *, ttl: int) -> None:
        self._cache[key] = _CacheEntry(data=data, expires_at=time.time() + ttl)

    def _invalidate_cache(self, key: str) -> None:
        self._cache.pop(key, None)

    def _require_package(self, *, context: H5MemberContext, package_id: str) -> TaskPackageInstance:
        package = self._session.execute(
            select(TaskPackageInstance)
            .options(joinedload(TaskPackageInstance.items))
            .options(joinedload(TaskPackageInstance.template))
            .where(
                TaskPackageInstance.id == package_id,
                TaskPackageInstance.account_id == context.account_id,
                TaskPackageInstance.user_id == context.user.id,
                TaskPackageInstance.site_id == context.site.id,
            )
        ).unique().scalars().first()
        if package is None:
            raise LookupError(f"Task package '{package_id}' was not found.")
        return package

    @staticmethod
    def _require_package_item(
        *,
        package: TaskPackageInstance,
        item_id: str,
    ) -> TaskPackageInstanceItem:
        for item in package.items:
            if item.id == item_id:
                return item
        raise LookupError(f"Task package item '{item_id}' was not found.")

    def _require_wallet(
        self,
        *,
        context: H5MemberContext,
        create_if_missing: bool,
    ) -> WalletAccount | None:
        wallet = self._session.scalars(
            select(WalletAccount).where(
                WalletAccount.account_id == context.account_id,
                WalletAccount.user_id == context.user.id,
            )
        ).first()
        if wallet is not None or not create_if_missing:
            return wallet
        wallet = WalletAccount(
            account_id=context.account_id,
            user_id=context.user.id,
            system_balance=Decimal("0"),
            task_balance=Decimal("0"),
            currency="USD",
            withdraw_threshold=Decimal("100"),
        )
        self._session.add(wallet)
        try:
            self._session.commit()
        except IntegrityError:
            self._session.rollback()
            wallet = self._session.scalars(
                select(WalletAccount).where(
                    WalletAccount.account_id == context.account_id,
                    WalletAccount.user_id == context.user.id,
                )
            ).first()
            return wallet
        self._session.refresh(wallet)
        return wallet

    def _require_wallet_row_for_update(
        self,
        *,
        wallet_id: str,
    ) -> WalletAccount:
        wallet = self._session.scalars(
            select(WalletAccount)
            .where(WalletAccount.id == wallet_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        ).first()
        if wallet is None:
            raise LookupError(f"Wallet '{wallet_id}' was not found.")
        return wallet

    @staticmethod
    def _expire_if_needed(package: TaskPackageInstance) -> bool:
        if package.status != "active" or package.expires_at is None:
            return False
        if package.expires_at > utc_now():
            return False
        package.status = "expired"
        return True

    def _serialize_task_package(
        self,
        *,
        package: TaskPackageInstance,
        context: H5MemberContext,
    ) -> tuple[H5TaskPackagePayload, bool]:
        total_amount = sum((Decimal(item.price) for item in package.items), start=Decimal("0"))
        completed_amount = sum(
            (Decimal(item.price) for item in package.items if item.completed_at is not None),
            start=Decimal("0"),
        )
        completed_items = sum(1 for item in package.items if item.completed_at is not None)
        total_items = len(package.items)
        total_commission = self._quantize(total_amount * Decimal(package.reward_ratio_snapshot))
        current_commission = self._quantize(completed_amount * Decimal(package.reward_ratio_snapshot))
        countdown_seconds = self._build_countdown_seconds(package=package)
        promotion_payload = None
        changed = False
        if package.template.promotion_metric is not None:
            promotion_payload, changed = self._build_promotion_payload(package=package, context=context)
        return H5TaskPackagePayload(
            id=package.id,
            title=package.template.title,
            description=package.template.description,
            type=package.template.package_type,
            status=package.status,
            reward_ratio=float(package.reward_ratio_snapshot),
            claimed_at=package.claimed_at,
            expires_at=package.expires_at,
            completed_at=package.completed_at,
            dispatched_at=package.dispatched_at,
            completion_window_hours=package.completion_window_hours_snapshot,
            items=[
                H5TaskPackageItemPayload(
                    id=item.id,
                    product_name=item.product_name,
                    image_url=item.image_url,
                    price=float(item.price),
                    currency=item.currency,
                    completed_at=item.completed_at,
                    order_id=item.order_id,
                )
                for item in sorted(package.items, key=lambda entry: entry.sort_order)
            ],
            promotion=promotion_payload,
            task_balance_awarded_at=package.task_balance_awarded_at,
            total_commission=float(total_commission),
            current_commission=float(current_commission),
            completed_items=completed_items,
            total_items=total_items,
            countdown_seconds=countdown_seconds,
        ), changed

    def _build_promotion_payload(
        self,
        *,
        package: TaskPackageInstance,
        context: H5MemberContext,
    ) -> tuple[H5TaskPackagePromotionPayload, bool]:
        changed = False
        metric = self._normalize_promotion_metric(package.template.promotion_metric)
        target_value = package.template.promotion_target_value or 0

        promotion_template, template_created = self._get_or_create_promotion_template(
            context=context,
            package=package,
            metric=metric,
            target_value=target_value,
        )
        changed = template_created or changed

        promotion_instance = self._find_promotion_instance(context=context, package_id=package.id)
        invite_code_snapshot = promotion_instance.invite_code_snapshot if promotion_instance is not None else None

        invite_code, invite_code_created = self._get_or_create_promotion_invite_code(
            context=context,
            invite_code_snapshot=invite_code_snapshot,
        )
        changed = invite_code_created or changed

        promotion_instance, instance_created = self._get_or_create_promotion_instance(
            context=context,
            package=package,
            promotion_template=promotion_template,
            metric=metric,
            target_value=target_value,
            invite_code_snapshot=invite_code.code,
        )
        changed = instance_created or changed

        current_value = self._session.scalar(
            select(func.count(UserReferral.id)).where(
                UserReferral.account_id == context.account_id,
                UserReferral.referrer_user_id == context.user.id,
                UserReferral.site_id == context.site.id,
                UserReferral.invite_code == invite_code.code,
                UserReferral.registered_at.is_not(None)
                if metric == "invited_registrations"
                else UserReferral.first_recharged_at.is_not(None),
            )
        )
        normalized_current = int(current_value or 0)

        if (
            promotion_instance.metric != metric
            or promotion_instance.target_value != target_value
            or promotion_instance.invite_code_snapshot != invite_code.code
            or promotion_instance.current_value != normalized_current
        ):
            promotion_instance.metric = metric
            promotion_instance.target_value = target_value
            promotion_instance.invite_code_snapshot = invite_code.code
            promotion_instance.current_value = normalized_current
            changed = True

        if normalized_current >= target_value > 0 and promotion_instance.achieved_at is None:
            promotion_instance.achieved_at = utc_now()
            changed = True
        if normalized_current < target_value and promotion_instance.achieved_at is not None:
            promotion_instance.achieved_at = None
            changed = True

        if changed:
            self._session.add(promotion_instance)
            self._session.add(promotion_template)
            self._session.add(invite_code)

        return (
            H5TaskPackagePromotionPayload(
                metric=metric,
                current=normalized_current,
                target=target_value,
                invite_code=invite_code.code,
            ),
            changed,
        )

    def _find_promotion_template(
        self,
        *,
        context: H5MemberContext,
        template_id: str,
    ) -> PromotionTaskTemplate | None:
        return self._session.scalars(
            select(PromotionTaskTemplate).where(
                PromotionTaskTemplate.account_id == context.account_id,
                PromotionTaskTemplate.task_package_template_id == template_id,
            )
        ).first()

    def _get_or_create_promotion_template(
        self,
        *,
        context: H5MemberContext,
        package: TaskPackageInstance,
        metric: str,
        target_value: int,
    ) -> tuple[PromotionTaskTemplate, bool]:
        promotion_template = self._find_promotion_template(context=context, template_id=package.template_id)
        if promotion_template is not None:
            return promotion_template, False

        promotion_template = PromotionTaskTemplate(
            account_id=context.account_id,
            task_package_template_id=package.template_id,
            metric=metric,
            target_value=target_value,
            status="active",
        )
        savepoint = self._session.begin_nested()
        try:
            self._session.add(promotion_template)
            self._session.flush()
            savepoint.commit()
            return promotion_template, True
        except IntegrityError:
            savepoint.rollback()
            promotion_template = self._find_promotion_template(context=context, template_id=package.template_id)
            if promotion_template is None:
                raise
            return promotion_template, False

    def _find_promotion_invite_code(
        self,
        *,
        context: H5MemberContext,
        invite_code_snapshot: str | None,
    ) -> InviteCode | None:
        if invite_code_snapshot:
            invite_code = self._session.scalars(
                select(InviteCode).where(
                    InviteCode.site_id == context.site.id,
                    InviteCode.inviter_user_id == context.user.id,
                    InviteCode.code == invite_code_snapshot,
                    InviteCode.status == "active",
                )
            ).first()
            if invite_code is not None:
                return invite_code
        return self._session.scalars(
            select(InviteCode)
            .where(
                InviteCode.site_id == context.site.id,
                InviteCode.inviter_user_id == context.user.id,
                InviteCode.status == "active",
                InviteCode.code.like("PROMO-%"),
            )
            .order_by(InviteCode.created_at.asc(), InviteCode.id.asc())
        ).first()

    def _get_or_create_promotion_invite_code(
        self,
        *,
        context: H5MemberContext,
        invite_code_snapshot: str | None,
    ) -> tuple[InviteCode, bool]:
        invite_code = self._find_promotion_invite_code(
            context=context,
            invite_code_snapshot=invite_code_snapshot,
        )
        if invite_code is not None:
            return invite_code, False

        for _ in range(5):
            invite_code = InviteCode(
                code=self._generate_promotion_invite_code(),
                site_id=context.site.id,
                inviter_user_id=context.user.id,
                status="active",
            )
            savepoint = self._session.begin_nested()
            try:
                self._session.add(invite_code)
                self._session.flush()
                savepoint.commit()
                return invite_code, True
            except IntegrityError:
                savepoint.rollback()
                invite_code = self._find_promotion_invite_code(context=context, invite_code_snapshot=None)
                if invite_code is not None:
                    return invite_code, False
        raise RuntimeError("Unable to create a unique promotion invite code.")

    def _find_promotion_instance(
        self,
        *,
        context: H5MemberContext,
        package_id: str,
    ) -> PromotionTaskInstance | None:
        return self._session.scalars(
            select(PromotionTaskInstance).where(
                PromotionTaskInstance.account_id == context.account_id,
                PromotionTaskInstance.task_package_instance_id == package_id,
            )
        ).first()

    def _get_or_create_promotion_instance(
        self,
        *,
        context: H5MemberContext,
        package: TaskPackageInstance,
        promotion_template: PromotionTaskTemplate,
        metric: str,
        target_value: int,
        invite_code_snapshot: str,
    ) -> tuple[PromotionTaskInstance, bool]:
        promotion_instance = self._find_promotion_instance(context=context, package_id=package.id)
        if promotion_instance is not None:
            return promotion_instance, False

        promotion_instance = PromotionTaskInstance(
            account_id=context.account_id,
            promotion_task_template_id=promotion_template.id,
            task_package_instance_id=package.id,
            user_id=context.user.id,
            member_profile_id=context.member_profile.id,
            metric=metric,
            target_value=target_value,
            invite_code_snapshot=invite_code_snapshot,
            current_value=0,
            status="active",
        )
        savepoint = self._session.begin_nested()
        try:
            self._session.add(promotion_instance)
            self._session.flush()
            savepoint.commit()
            return promotion_instance, True
        except IntegrityError:
            savepoint.rollback()
            promotion_instance = self._find_promotion_instance(context=context, package_id=package.id)
            if promotion_instance is None:
                raise
            return promotion_instance, False

    def _mark_referral_recharge(
        self,
        *,
        context: H5MemberContext,
        recharge_order_id: str,
        recharged_at: datetime,
    ) -> None:
        query = select(UserReferral).where(
            UserReferral.account_id == context.account_id,
            UserReferral.referred_user_id == context.user.id,
        )
        if context.user.registration_invite_code:
            query = query.where(UserReferral.invite_code == context.user.registration_invite_code)
        referral = self._session.scalars(
            query.order_by(UserReferral.created_at.asc(), UserReferral.id.asc())
        ).first()
        if referral is None or referral.first_recharged_at is not None:
            return
        referral.first_recharged_at = recharged_at
        referral.first_recharge_order_id = recharge_order_id
        referral.status = "recharged"
        self._session.add(referral)

    @staticmethod
    def _build_countdown_seconds(*, package: TaskPackageInstance) -> int:
        if package.status in {"completed", "expired"}:
            return 0
        if package.expires_at is None:
            return package.completion_window_hours_snapshot * 3600
        seconds = int((package.expires_at - utc_now()).total_seconds())
        return max(0, seconds)

    @staticmethod
    def _serialize_order(order: MemberOrder) -> H5MemberOrderResponse:
        return H5MemberOrderResponse(
            id=order.id,
            order_no=order.order_no,
            package_id=order.package_instance_id,
            package_title=order.package_title,
            product_name=order.product_name,
            amount=float(order.amount),
            currency=order.currency,
            status=order.status,
            created_at=order.ordered_at,
            source_label=order.source_label,
        )

    @classmethod
    def _serialize_wallet_summary(cls, wallet: WalletAccount) -> H5WalletSummaryResponse:
        system_balance = cls._quantize(Decimal(wallet.system_balance))
        task_balance = cls._quantize(Decimal(wallet.task_balance))
        withdraw_threshold = cls._quantize(Decimal(wallet.withdraw_threshold))
        shortfall = cls._quantize(max(Decimal("0"), withdraw_threshold - system_balance))
        return H5WalletSummaryResponse(
            system_balance=float(system_balance),
            task_balance=float(task_balance),
            currency=wallet.currency,
            withdraw_threshold=float(withdraw_threshold),
            can_withdraw=shortfall == Decimal("0"),
            shortfall_amount=float(shortfall),
        )

    @staticmethod
    def _serialize_wallet_transaction(entry: WalletLedgerEntry) -> H5WalletTransactionResponse:
        return H5WalletTransactionResponse(
            id=entry.id,
            ledger_type=entry.ledger_type,
            transaction_type=entry.transaction_type,
            direction=entry.direction,
            amount=float(entry.amount),
            currency=entry.currency,
            status=entry.status,
            note=entry.note,
            display_category=entry.display_category,
            display_title=entry.display_title or entry.note,
            created_at=entry.created_at,
        )

    def _serialize_withdrawals(
        self,
        withdrawals: list[WithdrawalRequest],
    ) -> list[H5WithdrawalResponse]:
        if not withdrawals:
            return []
        histories = self._load_withdrawal_histories([item.id for item in withdrawals])
        return [
            self._serialize_withdrawal(item, history=histories.get(item.id, []))
            for item in withdrawals
        ]

    def _load_withdrawal_histories(
        self,
        withdrawal_ids: list[str],
    ) -> dict[str, list[WithdrawalAuditLog]]:
        if not withdrawal_ids:
            return {}
        logs = self._session.scalars(
            select(WithdrawalAuditLog)
            .where(WithdrawalAuditLog.withdrawal_request_id.in_(withdrawal_ids))
            .order_by(WithdrawalAuditLog.created_at.asc(), WithdrawalAuditLog.id.asc())
        ).all()
        histories: dict[str, list[WithdrawalAuditLog]] = {withdrawal_id: [] for withdrawal_id in withdrawal_ids}
        for log in logs:
            histories.setdefault(log.withdrawal_request_id, []).append(log)
        return histories

    def _serialize_withdrawal(
        self,
        withdrawal: WithdrawalRequest,
        *,
        history: list[WithdrawalAuditLog],
    ) -> H5WithdrawalResponse:
        duplicate_member_ids = self._get_duplicate_member_ids(withdrawal=withdrawal)
        return H5WithdrawalResponse(
            id=withdrawal.id,
            request_no=withdrawal.request_no,
            amount=float(withdrawal.amount),
            cash_amount=float(withdrawal.cash_amount),
            bonus_amount=float(withdrawal.bonus_amount),
            actual_payout_amount=(
                float(withdrawal.actual_payout_amount) if withdrawal.actual_payout_amount is not None else None
            ),
            withdraw_account_type=withdrawal.withdraw_account_type,
            account_no_masked=withdrawal.account_no_masked,
            account_fingerprint=withdrawal.account_fingerprint,
            duplicate_account_count=withdrawal.duplicate_account_count or 0,
            duplicate_member_ids=duplicate_member_ids,
            risk_level=withdrawal.risk_level,
            risk_flags=list(withdrawal.risk_flags or []),
            currency=withdrawal.currency,
            status=withdrawal.status,
            rejection_reason=withdrawal.rejection_reason,
            created_at=withdrawal.created_at,
            reviewed_at=withdrawal.reviewed_at,
            paid_at=withdrawal.paid_at,
            history=[
                H5WithdrawalAuditLogResponse(
                    id=entry.id,
                    status=entry.status,
                    note=entry.note,
                    actor_type=entry.actor_type,
                    actor_id=entry.actor_id,
                    created_at=entry.created_at,
                )
                for entry in history
            ],
        )

    @staticmethod
    def _normalize_withdraw_account_type(withdraw_account_type: str | None) -> str | None:
        value = (withdraw_account_type or "").strip().lower()
        return value or None

    @classmethod
    def _build_withdraw_account_metadata(
        cls,
        *,
        withdraw_account_type: str | None,
        bank_name: str | None,
        account_no: str | None,
    ) -> dict[str, Any]:
        account_type = cls._normalize_withdraw_account_type(withdraw_account_type)
        normalized_account = (account_no or "").strip()
        normalized_bank_name = (bank_name or "").strip() or None
        if not normalized_account:
            return {
                "withdraw_account_type": account_type,
                "bank_name": normalized_bank_name,
                "account_no_masked": None,
                "account_fingerprint": None,
                "account_snapshot_json": None,
            }

        account_digits = "".join(ch for ch in normalized_account if ch.isalnum())
        account_tail = account_digits[-4:] if account_digits else normalized_account[-4:]
        masked_account = f"{'*' * max(len(account_digits) - 4, 0)}{account_tail}" if account_digits else "****"
        if account_type == "bank":
            fingerprint_raw = f"bank::{(normalized_bank_name or '').upper()}::{account_digits}"
        elif account_type == "crypto":
            fingerprint_raw = f"crypto::{normalized_account.lower()}"
        elif account_type == "ewallet":
            fingerprint_raw = f"ewallet::{normalized_account.lower()}"
        else:
            fingerprint_raw = f"other::{normalized_account.lower()}"

        return {
            "withdraw_account_type": account_type or "other",
            "bank_name": normalized_bank_name,
            "account_no_masked": masked_account,
            "account_fingerprint": hashlib.sha256(fingerprint_raw.encode("utf-8")).hexdigest(),
            "account_snapshot_json": {
                "withdraw_account_type": account_type or "other",
                "bank_name": normalized_bank_name,
                "account_no_masked": masked_account,
            },
        }

    def _apply_duplicate_account_risk(
        self,
        *,
        withdrawal: WithdrawalRequest,
    ) -> None:
        duplicate_member_ids = self._get_duplicate_member_ids(withdrawal=withdrawal)
        duplicate_count = len(duplicate_member_ids)
        withdrawal.duplicate_account_count = duplicate_count
        withdrawal.risk_level = self._derive_risk_level(duplicate_count)
        withdrawal.risk_flags = ["duplicate_withdraw_account"] if duplicate_count > 0 else []
        self._session.add(withdrawal)

    def _get_duplicate_member_ids(
        self,
        *,
        withdrawal: WithdrawalRequest,
    ) -> list[str]:
        if not withdrawal.account_fingerprint:
            return []
        rows = self._session.execute(
            select(AppUser.public_user_id)
            .select_from(WithdrawalRequest)
            .join(AppUser, AppUser.id == WithdrawalRequest.user_id)
            .where(
                WithdrawalRequest.account_id == withdrawal.account_id,
                WithdrawalRequest.account_fingerprint == withdrawal.account_fingerprint,
                WithdrawalRequest.user_id != withdrawal.user_id,
            )
            .distinct()
            .order_by(AppUser.public_user_id.asc())
        ).all()
        return [row[0] for row in rows if row[0]]

    @staticmethod
    def _derive_risk_level(duplicate_count: int) -> str | None:
        if duplicate_count >= 5:
            return "high"
        if duplicate_count >= 2:
            return "medium"
        if duplicate_count >= 1:
            return "low"
        return None

    @staticmethod
    def _mask_member_no(member_no: str) -> str:
        if len(member_no) <= 5:
            return member_no
        return f"{member_no[:3]}***{member_no[-2:]}"

    def _generate_promotion_invite_code(self) -> str:
        for _ in range(50):
            candidate = f"PROMO-{uuid4().hex[:8].upper()}"
            exists = self._session.scalars(
                select(InviteCode.id).where(InviteCode.code == candidate)
            ).first()
            if exists is None:
                return candidate
        raise RuntimeError("Unable to generate a unique promotion invite code.")

    @staticmethod
    def _quantize(value: Decimal) -> Decimal:
        return value.quantize(Decimal("0.01"))

    def _serialize_task_package_with_refresh(
        self,
        *,
        package: TaskPackageInstance,
        context: H5MemberContext,
    ) -> H5TaskPackagePayload:
        payload, changed = self._serialize_task_package(package=package, context=context)
        if changed:
            self._session.commit()
            self._session.refresh(package)
            payload, _ = self._serialize_task_package(package=package, context=context)
        return payload

    @staticmethod
    def _ensure_promotion_claim_ready(promotion: H5TaskPackagePromotionPayload | None) -> None:
        if promotion is None:
            raise ValueError("Promotion task configuration is incomplete.")
        if promotion.target > 0 and promotion.current < promotion.target:
            raise ValueError("Promotion task target has not been reached yet.")

    @classmethod
    def _calculate_task_package_reward(cls, *, package: TaskPackageInstance) -> Decimal:
        total_amount = sum((Decimal(entry.price) for entry in package.items), start=Decimal("0"))
        return cls._quantize(total_amount * Decimal(package.reward_ratio_snapshot))

    def _settle_task_package_reward(
        self,
        *,
        context: H5MemberContext,
        package: TaskPackageInstance,
        wallet: WalletAccount,
        rewarded_at: datetime,
    ) -> None:
        reward_amount = self._calculate_task_package_reward(package=package)
        existing_entry = self._find_task_reward_entry(
            context=context,
            package=package,
            wallet=wallet,
        )
        if existing_entry is not None:
            if package.task_balance_awarded_at is None:
                package.task_balance_awarded_at = rewarded_at
                self._session.add(package)
            return
        if package.task_balance_awarded_at is not None:
            return
        package.task_balance_awarded_at = rewarded_at
        self._session.add(package)
        if reward_amount <= Decimal("0"):
            return
        wallet.task_balance = self._quantize(Decimal(wallet.task_balance) + reward_amount)
        self._session.add(wallet)
        self._session.add(
            WalletLedgerEntry(
                account_id=context.account_id,
                wallet_account_id=wallet.id,
                user_id=context.user.id,
                ledger_type="task",
                transaction_type="task_reward",
                direction="credit",
                amount=reward_amount,
                currency=wallet.currency,
                status="paid",
                note=f"{package.template.title} completed",
                reference_type="task_package_instance",
                reference_id=package.id,
            )
        )
        self._create_member_notification(
            context=context,
            category="task",
            title="Task reward credited",
            body_text=(
                f"Your task reward of {reward_amount:.2f} {wallet.currency} "
                f"was credited after completing {package.template.title}."
            ),
            reference_type="task_package_instance",
            reference_id=package.id,
            metadata_json={
                "amount": float(reward_amount),
                "currency": wallet.currency,
                "transaction_type": "task_reward",
                "package_title": package.template.title,
            },
        )

    def _find_task_reward_entry(
        self,
        *,
        context: H5MemberContext,
        package: TaskPackageInstance,
        wallet: WalletAccount,
    ) -> WalletLedgerEntry | None:
        return self._session.scalars(
            select(WalletLedgerEntry).where(
                WalletLedgerEntry.account_id == context.account_id,
                WalletLedgerEntry.wallet_account_id == wallet.id,
                WalletLedgerEntry.user_id == context.user.id,
                WalletLedgerEntry.ledger_type == "task",
                WalletLedgerEntry.transaction_type == "task_reward",
                WalletLedgerEntry.direction == "credit",
                WalletLedgerEntry.reference_type == "task_package_instance",
                WalletLedgerEntry.reference_id == package.id,
            )
        ).first()

    def _create_member_notification(
        self,
        *,
        context: H5MemberContext,
        category: str,
        title: str,
        body_text: str,
        reference_type: str | None,
        reference_id: str | None,
        metadata_json: dict[str, object] | None = None,
    ) -> None:
        self._session.add(
            MemberNotification(
                account_id=context.account_id,
                user_id=context.user.id,
                member_profile_id=context.member_profile.id,
                site_id=context.site.id,
                category=category,
                title=title,
                body_text=body_text,
                is_read=False,
                reference_type=reference_type,
                reference_id=reference_id,
                metadata_json=metadata_json,
            )
        )

    @classmethod
    def _normalize_promotion_metric(cls, metric: str | None) -> str:
        normalized = (metric or "invited_registrations").strip()
        if normalized not in cls.SUPPORTED_PROMOTION_METRICS:
            raise ValueError(f"Unsupported promotion metric '{normalized}'.")
        return normalized
