from app.services.support_intent_service import SupportIntentService


def test_support_intent_service_detects_human_handover_request() -> None:
    service = SupportIntentService()

    decision = service.classify("I want to talk to a human agent now.")

    assert decision.intent_name == "human_handover_request"
    assert decision.handover_recommended is True
    assert decision.handover_reason == "customer_requested_human_support"


def test_support_intent_service_detects_refund_without_handover() -> None:
    service = SupportIntentService()

    decision = service.classify("Need a refund for this order.")

    assert decision.intent_name == "refund_or_return"
    assert decision.handover_recommended is False
