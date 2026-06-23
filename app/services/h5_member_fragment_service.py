from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    FragmentDefinition,
    FragmentDropLog,
    FragmentExchangeRequest,
    FragmentInventory,
    FragmentLedgerEntry,
    MailingRequest,
    utc_now,
)
from app.schemas.h5_member_fragments import (
    H5FragmentDropLogResponse,
    H5FragmentInventoryItemResponse,
    H5FragmentOverviewResponse,
    H5RewardShippingAddressResponse,
    H5RewardShippingOrderResponse,
    H5ShippingAddressRequest,
)
from app.services.h5_member_auth_service import H5MemberContext


DEFAULT_FRAGMENT_DEFINITIONS: tuple[dict[str, str], ...] = (
    {
        "fragment_key": "fragment-sun",
        "name": "Star Core Fragment",
        "rarity": "common",
        "color": "#f59e0b",
    },
    {
        "fragment_key": "fragment-moon",
        "name": "Moon Glow Fragment",
        "rarity": "rare",
        "color": "#6366f1",
    },
    {
        "fragment_key": "fragment-star",
        "name": "Star Ray Fragment",
        "rarity": "epic",
        "color": "#ef4444",
    },
)
DEFAULT_REWARD_NAME = "Star Ring Gift Box"


class H5MemberFragmentService:
    def __init__(self, *, session: Session) -> None:
        self._session = session

    async def get_overview(
        self,
        *,
        context: H5MemberContext,
    ) -> H5FragmentOverviewResponse:
        definitions = self._ensure_definitions(account_id=context.account_id)
        self._session.commit()
        return self._build_overview(context=context, definitions=definitions)

    async def perform_checkin(
        self,
        *,
        context: H5MemberContext,
    ) -> H5FragmentOverviewResponse:
        today_start = utc_now().replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow_start = today_start + timedelta(days=1)
        existing_log = self._session.scalars(
            select(FragmentDropLog).where(
                FragmentDropLog.account_id == context.account_id,
                FragmentDropLog.user_id == context.user.id,
                FragmentDropLog.source == "checkin",
                FragmentDropLog.created_at >= today_start,
                FragmentDropLog.created_at < tomorrow_start,
            )
        ).first()
        if existing_log is not None:
            raise ValueError("Member has already checked in today.")

        self.award_fragment_drop(
            context=context,
            source="checkin",
            source_id=None,
            auto_commit=False,
        )
        self._session.commit()
        definitions = self._load_definitions(account_id=context.account_id)
        return self._build_overview(context=context, definitions=definitions)

    async def create_exchange(
        self,
        *,
        context: H5MemberContext,
        payload: H5ShippingAddressRequest,
    ) -> H5FragmentOverviewResponse:
        definitions = self._ensure_definitions(account_id=context.account_id)
        inventories = self._load_inventory_map(context=context)
        missing = [
            definition.name
            for definition in definitions
            if inventories.get(definition.id) is None
            or inventories[definition.id].owned_count < definition.required_count
        ]
        if missing:
            raise ValueError("Fragments are incomplete and cannot be exchanged yet.")

        now = utc_now()
        exchange = FragmentExchangeRequest(
            account_id=context.account_id,
            user_id=context.user.id,
            member_profile_id=context.member_profile.id,
            reward_name=definitions[0].reward_name if definitions else DEFAULT_REWARD_NAME,
            status="submitted",
        )
        self._session.add(exchange)
        self._session.flush()

        for definition in definitions:
            inventory = inventories[definition.id]
            inventory.owned_count -= definition.required_count
            self._session.add(inventory)
            self._session.add(
                FragmentLedgerEntry(
                    account_id=context.account_id,
                    user_id=context.user.id,
                    member_profile_id=context.member_profile.id,
                    fragment_definition_id=definition.id,
                    entry_type="exchange",
                    direction="debit",
                    quantity=definition.required_count,
                    source_type="exchange",
                    source_id=exchange.id,
                    note=f"Exchange applied for {exchange.reward_name}",
                )
            )

        mailing_request = MailingRequest(
            account_id=context.account_id,
            user_id=context.user.id,
            member_profile_id=context.member_profile.id,
            fragment_exchange_request_id=exchange.id,
            reward_name=exchange.reward_name,
            status="submitted",
            receiver=payload.receiver,
            phone=payload.phone,
            country=payload.country,
            province=payload.province,
            city=payload.city,
            address_line=payload.address_line,
            submitted_at=now,
        )
        self._session.add(mailing_request)
        self._session.flush()
        exchange.mailing_request_id = mailing_request.id
        self._session.add(exchange)
        self._session.commit()
        return self._build_overview(context=context, definitions=definitions)

    async def list_shipping_orders(
        self,
        *,
        context: H5MemberContext,
    ) -> list[H5RewardShippingOrderResponse]:
        shipping_orders = self._session.scalars(
            select(MailingRequest)
            .where(
                MailingRequest.account_id == context.account_id,
                MailingRequest.user_id == context.user.id,
            )
            .order_by(MailingRequest.created_at.desc(), MailingRequest.id.desc())
        ).all()
        return [self._serialize_shipping_order(item) for item in shipping_orders]

    def award_fragment_drop(
        self,
        *,
        context: H5MemberContext,
        source: str,
        source_id: str | None,
        auto_commit: bool,
    ) -> H5FragmentDropLogResponse:
        definitions = self._ensure_definitions(account_id=context.account_id)
        existing_drop_count = self._session.scalars(
            select(FragmentDropLog.id).where(
                FragmentDropLog.account_id == context.account_id,
                FragmentDropLog.user_id == context.user.id,
            )
        ).all()
        awarded_definition = definitions[len(existing_drop_count) % len(definitions)]

        inventory = self._session.scalars(
            select(FragmentInventory).where(
                FragmentInventory.account_id == context.account_id,
                FragmentInventory.user_id == context.user.id,
                FragmentInventory.fragment_definition_id == awarded_definition.id,
            )
        ).first()
        if inventory is None:
            inventory = FragmentInventory(
                account_id=context.account_id,
                user_id=context.user.id,
                member_profile_id=context.member_profile.id,
                fragment_definition_id=awarded_definition.id,
                owned_count=0,
            )
        inventory.owned_count += 1
        self._session.add(inventory)
        self._session.flush()

        ledger_entry = FragmentLedgerEntry(
            account_id=context.account_id,
            user_id=context.user.id,
            member_profile_id=context.member_profile.id,
            fragment_definition_id=awarded_definition.id,
            entry_type="drop",
            direction="credit",
            quantity=1,
            source_type=source,
            source_id=source_id,
            note=f"Fragment drop from {source}",
        )
        self._session.add(ledger_entry)
        self._session.flush()

        drop_log = FragmentDropLog(
            account_id=context.account_id,
            user_id=context.user.id,
            member_profile_id=context.member_profile.id,
            fragment_definition_id=awarded_definition.id,
            source=source,
            fragment_ledger_entry_id=ledger_entry.id,
            source_id=source_id,
        )
        self._session.add(drop_log)
        self._session.flush()

        if auto_commit:
            self._session.commit()

        return self._serialize_drop_log(drop_log=drop_log, definition=awarded_definition)

    def _ensure_definitions(self, *, account_id: str) -> list[FragmentDefinition]:
        definitions = self._load_definitions(account_id=account_id)
        existing_keys = {item.fragment_key for item in definitions}
        for item in DEFAULT_FRAGMENT_DEFINITIONS:
            if item["fragment_key"] in existing_keys:
                continue
            self._session.add(
                FragmentDefinition(
                    account_id=account_id,
                    fragment_key=item["fragment_key"],
                    name=item["name"],
                    rarity=item["rarity"],
                    color=item["color"],
                    required_count=1,
                    reward_name=DEFAULT_REWARD_NAME,
                    status="active",
                )
            )
        self._session.flush()
        return self._load_definitions(account_id=account_id)

    def _load_definitions(self, *, account_id: str) -> list[FragmentDefinition]:
        return self._session.scalars(
            select(FragmentDefinition)
            .where(
                FragmentDefinition.account_id == account_id,
                FragmentDefinition.status == "active",
            )
            .order_by(FragmentDefinition.created_at.asc(), FragmentDefinition.id.asc())
        ).all()

    def _load_inventory_map(self, *, context: H5MemberContext) -> dict[str, FragmentInventory]:
        inventories = self._session.scalars(
            select(FragmentInventory).where(
                FragmentInventory.account_id == context.account_id,
                FragmentInventory.user_id == context.user.id,
            )
        ).all()
        return {item.fragment_definition_id: item for item in inventories}

    def _build_overview(
        self,
        *,
        context: H5MemberContext,
        definitions: list[FragmentDefinition],
    ) -> H5FragmentOverviewResponse:
        inventories = self._load_inventory_map(context=context)
        drop_logs = self._session.scalars(
            select(FragmentDropLog)
            .where(
                FragmentDropLog.account_id == context.account_id,
                FragmentDropLog.user_id == context.user.id,
            )
            .order_by(FragmentDropLog.created_at.desc(), FragmentDropLog.id.desc())
        ).all()
        definition_map = {item.id: item for item in definitions}
        shipping_orders = self._session.scalars(
            select(MailingRequest)
            .where(
                MailingRequest.account_id == context.account_id,
                MailingRequest.user_id == context.user.id,
            )
            .order_by(MailingRequest.created_at.desc(), MailingRequest.id.desc())
        ).all()
        reward_name = definitions[0].reward_name if definitions else DEFAULT_REWARD_NAME
        return H5FragmentOverviewResponse(
            inventory=[
                H5FragmentInventoryItemResponse(
                    id=definition.id,
                    fragment_key=definition.fragment_key,
                    name=definition.name,
                    rarity=definition.rarity,
                    color=definition.color,
                    owned=inventories.get(definition.id).owned_count if definition.id in inventories else 0,
                    required=definition.required_count,
                )
                for definition in definitions
            ],
            drop_logs=[
                self._serialize_drop_log(
                    drop_log=drop_log,
                    definition=definition_map[drop_log.fragment_definition_id],
                )
                for drop_log in drop_logs
                if drop_log.fragment_definition_id in definition_map
            ],
            reward_name=reward_name,
            shipping_orders=[self._serialize_shipping_order(item) for item in shipping_orders],
        )

    @staticmethod
    def _serialize_drop_log(
        *,
        drop_log: FragmentDropLog,
        definition: FragmentDefinition,
    ) -> H5FragmentDropLogResponse:
        return H5FragmentDropLogResponse(
            id=drop_log.id,
            fragment_id=definition.id,
            fragment_key=definition.fragment_key,
            fragment_name=definition.name,
            source=drop_log.source,
            created_at=drop_log.created_at,
        )

    @staticmethod
    def _serialize_shipping_order(order: MailingRequest) -> H5RewardShippingOrderResponse:
        return H5RewardShippingOrderResponse(
            id=order.id,
            reward_name=order.reward_name,
            status=order.status,
            created_at=order.created_at,
            address=H5RewardShippingAddressResponse(
                receiver=order.receiver,
                phone=order.phone,
                country=order.country,
                province=order.province,
                city=order.city,
                address_line=order.address_line,
            ),
        )
