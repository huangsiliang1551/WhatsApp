from dataclasses import dataclass


@dataclass(frozen=True)
class SupportIntentDecision:
    intent_name: str
    confidence: float
    handover_recommended: bool
    handover_reason: str | None


class SupportIntentService:
    def classify(self, user_message: str) -> SupportIntentDecision:
        lowered = user_message.strip().lower()

        if _contains_any(
            lowered,
            (
                "human agent",
                "real person",
                "talk to human",
                "agent please",
                "representative",
                "speak to someone",
                "人工",
                "真人",
                "转人工",
                "客服",
                "quiero hablar con una persona",
                "agente humano",
                "parler a une personne",
                "service client",
                "اريد موظف",
                "التحدث مع شخص",
            ),
        ):
            return SupportIntentDecision(
                intent_name="human_handover_request",
                confidence=0.98,
                handover_recommended=True,
                handover_reason="customer_requested_human_support",
            )

        if _contains_any(
            lowered,
            (
                "angry",
                "terrible",
                "complaint",
                "lawsuit",
                "chargeback",
                "fraud",
                "scam",
                "投诉",
                "骗人",
                "欺诈",
                "差评",
                "queja",
                "estafa",
                "fraude",
                "plainte",
                "arnaque",
                "fraude",
                "شكوى",
                "احتيال",
            ),
        ):
            return SupportIntentDecision(
                intent_name="complaint_or_risk",
                confidence=0.94,
                handover_recommended=True,
                handover_reason="sensitive_or_risk_issue",
            )

        if _contains_any(
            lowered,
            (
                "refund",
                "return",
                "exchange",
                "退款",
                "退货",
                "换货",
                "reembolso",
                "devolucion",
                "remboursement",
                "retour",
                "استرداد",
                "استرجاع",
            ),
        ):
            return SupportIntentDecision(
                intent_name="refund_or_return",
                confidence=0.86,
                handover_recommended=False,
                handover_reason=None,
            )

        if _contains_any(
            lowered,
            (
                "change my order",
                "modify order",
                "change address",
                "update address",
                "修改订单",
                "修改地址",
                "改地址",
                "modificar pedido",
                "cambiar direccion",
                "modifier la commande",
                "changer adresse",
                "تعديل الطلب",
                "تغيير العنوان",
            ),
        ):
            return SupportIntentDecision(
                intent_name="order_change",
                confidence=0.84,
                handover_recommended=False,
                handover_reason=None,
            )

        if _contains_any(
            lowered,
            (
                "track",
                "tracking",
                "where is my package",
                "where is my order",
                "物流",
                "快递",
                "订单状态",
                "pedido",
                "seguimiento",
                "ou est",
                "suivi",
                "اين طلبي",
                "تتبع",
            ),
        ):
            return SupportIntentDecision(
                intent_name="order_or_tracking_status",
                confidence=0.78,
                handover_recommended=False,
                handover_reason=None,
            )

        if _contains_any(
            lowered,
            (
                "business hours",
                "working hours",
                "shipping country",
                "ship to",
                "营业时间",
                "服务时间",
                "发哪些国家",
                "配送国家",
                "horario",
                "livraison",
                "ساعات العمل",
                "الدول المتاحة للشحن",
            ),
        ):
            return SupportIntentDecision(
                intent_name="faq_or_policy",
                confidence=0.72,
                handover_recommended=False,
                handover_reason=None,
            )

        return SupportIntentDecision(
            intent_name="general_support",
            confidence=0.45,
            handover_recommended=False,
            handover_reason=None,
        )


def _contains_any(text: str, patterns: tuple[str, ...]) -> bool:
    return any(pattern in text for pattern in patterns)
