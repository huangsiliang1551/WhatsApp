import re
from dataclasses import dataclass

from app.services.ecommerce_service import EcommerceService
from app.services.knowledge_base import match_support_knowledge
from app.services.support_knowledge_service import SupportKnowledgeService
from app.services.translation_service import TranslationService

ORDER_ID_PATTERN = re.compile(r"\b[A-Z]{2,12}-\d{3,}\b", re.IGNORECASE)
TRACKING_TOKEN_PATTERN = re.compile(r"\b[A-Z0-9-]{8,}\b", re.IGNORECASE)


@dataclass(frozen=True)
class SupportRouteDecision:
    route_name: str
    reply_text: str
    delivered_language: str
    metadata: dict[str, object]


class SupportRouter:
    def __init__(
        self,
        ecommerce_service: EcommerceService,
        translation_service: TranslationService,
        support_knowledge_service: SupportKnowledgeService | None = None,
    ) -> None:
        self._ecommerce_service = ecommerce_service
        self._translation_service = translation_service
        self._support_knowledge_service = support_knowledge_service

    async def resolve(
        self,
        account_id: str,
        customer_language: str,
        user_message: str,
    ) -> SupportRouteDecision | None:
        if self._support_knowledge_service is not None:
            database_match = await self._support_knowledge_service.match_entry(
                account_id=account_id,
                user_message=user_message,
            )
            if database_match is not None:
                delivered_text = await _translate_reply(
                    translation_service=self._translation_service,
                    text=database_match.entry.answer,
                    target_language=customer_language,
                    source_language=database_match.entry.source_language,
                )
                return SupportRouteDecision(
                    route_name=database_match.entry.route_name,
                    reply_text=delivered_text,
                    delivered_language=customer_language,
                    metadata={
                        "article_id": database_match.entry.article_id,
                        "category": database_match.entry.category,
                        "title": database_match.entry.title,
                        "score": database_match.score,
                        "source_type": "database",
                    },
                )

        knowledge_match = match_support_knowledge(user_message)
        if knowledge_match is not None:
            delivered_text = await _translate_reply(
                translation_service=self._translation_service,
                text=knowledge_match.entry.answer,
                target_language=customer_language,
                source_language="en",
            )
            return SupportRouteDecision(
                route_name=knowledge_match.entry.route_name,
                reply_text=delivered_text,
                delivered_language=customer_language,
                metadata={
                    "article_id": knowledge_match.entry.article_id,
                    "category": knowledge_match.entry.category,
                    "title": knowledge_match.entry.title,
                    "score": knowledge_match.score,
                },
            )

        order_id = _extract_order_id(user_message)
        if order_id is not None:
            return await self._resolve_order_lookup(
                account_id=account_id,
                customer_language=customer_language,
                order_id=order_id,
            )

        tracking_number = _extract_tracking_number(user_message)
        if tracking_number is not None:
            return await self._resolve_tracking_lookup(
                account_id=account_id,
                customer_language=customer_language,
                tracking_number=tracking_number,
            )

        return None

    async def _resolve_order_lookup(
        self,
        account_id: str,
        customer_language: str,
        order_id: str,
    ) -> SupportRouteDecision:
        try:
            order = await self._ecommerce_service.get_order(account_id=account_id, order_id=order_id)
            first_shipment = order.shipments[0] if order.shipments else None
            summary = (
                f"Order {order.order_id} is currently {order.fulfillment_status}. "
                f"Payment status: {order.payment_status}. "
                f"Total amount: {order.currency} {order.total_amount:.2f}. "
                f"Shipping address: {order.shipping_address}. "
                f"Tracking number: {first_shipment.tracking_number if first_shipment else 'not assigned yet'}."
            )
            route_name = "order_lookup"
            metadata = {
                "order_id": order.order_id,
                "payment_status": order.payment_status,
                "fulfillment_status": order.fulfillment_status,
                "tracking_number": first_shipment.tracking_number if first_shipment else None,
            }
        except LookupError:
            summary = (
                f"I could not find order {order_id} under the current account. "
                "Please confirm the order number or provide the tracking number."
            )
            route_name = "order_lookup_not_found"
            metadata = {"order_id": order_id}

        delivered_text = await _translate_reply(
            translation_service=self._translation_service,
            text=summary,
            target_language=customer_language,
            source_language="en",
        )
        return SupportRouteDecision(
            route_name=route_name,
            reply_text=delivered_text,
            delivered_language=customer_language,
            metadata=metadata,
        )

    async def _resolve_tracking_lookup(
        self,
        account_id: str,
        customer_language: str,
        tracking_number: str,
    ) -> SupportRouteDecision:
        try:
            shipment = await self._ecommerce_service.get_shipment(
                account_id=account_id,
                tracking_number=tracking_number,
            )
            latest_event = shipment.events[-1] if shipment.events else None
            summary = (
                f"Tracking {shipment.tracking_number} with {shipment.carrier} is currently {shipment.status}. "
                f"Destination: {shipment.destination}. "
                f"Estimated delivery: {shipment.estimated_delivery_at or 'not available yet'}. "
                f"Latest update: "
                f"{latest_event.status if latest_event else 'no event yet'}"
                f"{f' at {latest_event.location}' if latest_event else ''}"
                f"{f' on {latest_event.occurred_at}' if latest_event else ''}."
            )
            route_name = "tracking_lookup"
            metadata = {
                "tracking_number": shipment.tracking_number,
                "carrier": shipment.carrier,
                "status": shipment.status,
                "order_id": shipment.order_id,
            }
        except LookupError:
            summary = (
                f"I could not find tracking number {tracking_number} under the current account. "
                "Please confirm the tracking number or share the related order number."
            )
            route_name = "tracking_lookup_not_found"
            metadata = {"tracking_number": tracking_number}

        delivered_text = await _translate_reply(
            translation_service=self._translation_service,
            text=summary,
            target_language=customer_language,
            source_language="en",
        )
        return SupportRouteDecision(
            route_name=route_name,
            reply_text=delivered_text,
            delivered_language=customer_language,
            metadata=metadata,
        )


async def _translate_reply(
    translation_service: TranslationService,
    text: str,
    target_language: str,
    source_language: str,
) -> str:
    translated_text, translated = await translation_service.translate_outbound_for_customer(
        text=text,
        source_language=source_language,
        target_language=target_language,
    )
    return translated_text if translated else text


def _extract_order_id(user_message: str) -> str | None:
    match = ORDER_ID_PATTERN.search(user_message)
    return match.group(0).upper() if match else None


def _extract_tracking_number(user_message: str) -> str | None:
    for match in TRACKING_TOKEN_PATTERN.finditer(user_message):
        candidate = match.group(0).upper()
        if ORDER_ID_PATTERN.fullmatch(candidate):
            continue
        if any(character.isalpha() for character in candidate) and any(
            character.isdigit() for character in candidate
        ):
            return candidate
    return None
