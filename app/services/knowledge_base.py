import re
from dataclasses import dataclass


@dataclass(frozen=True)
class SupportKnowledgeEntry:
    article_id: str
    route_name: str
    category: str
    title: str
    answer: str
    keywords: tuple[str, ...]
    source_language: str = "en"
    minimum_score: int = 1


@dataclass(frozen=True)
class SupportKnowledgeMatch:
    entry: SupportKnowledgeEntry
    score: int


SUPPORT_KNOWLEDGE_ENTRIES: tuple[SupportKnowledgeEntry, ...] = (
    SupportKnowledgeEntry(
        article_id="faq-refund-policy",
        route_name="faq_refund_policy",
        category="faq",
        title="Refund and return policy",
        answer=(
            "Refund and return requests should be submitted within 7 days after delivery. "
            "Please share your order ID, the reason for the request, and photos if the item is damaged."
        ),
        keywords=(
            "refund",
            "return policy",
            "return",
            "exchange",
            "reembolso",
            "devolucion",
            "devolver",
            "remboursement",
            "retour",
            "退款",
            "退货",
            "换货",
            "استرداد",
            "استرجاع",
        ),
    ),
    SupportKnowledgeEntry(
        article_id="faq-business-hours",
        route_name="faq_business_hours",
        category="faq",
        title="Support business hours",
        answer=(
            "Our support team reviews conversations every day from 09:00 to 18:00 China Standard Time. "
            "Urgent issues can still be submitted at any time and will queue for the next available agent."
        ),
        keywords=(
            "business hours",
            "working hours",
            "support hours",
            "horario",
            "horas de atencion",
            "heures de service",
            "营业时间",
            "服务时间",
            "工作时间",
            "ساعات العمل",
            "اوقات العمل",
        ),
    ),
    SupportKnowledgeEntry(
        article_id="kb-order-change-window",
        route_name="knowledge_order_change",
        category="knowledge_base",
        title="Order modification window",
        answer=(
            "Orders can usually be changed before the warehouse starts packing. "
            "Please send the order ID together with the exact change needed, such as address, color, or quantity."
        ),
        keywords=(
            "change my order",
            "modify order",
            "change address",
            "update address",
            "modificar pedido",
            "cambiar direccion",
            "modifier la commande",
            "changer adresse",
            "修改订单",
            "修改地址",
            "改地址",
            "تعديل الطلب",
            "تغيير العنوان",
        ),
    ),
    SupportKnowledgeEntry(
        article_id="kb-shipping-regions",
        route_name="knowledge_shipping_regions",
        category="knowledge_base",
        title="Shipping regions",
        answer=(
            "We currently support shipping to most regions in Europe, North America, the Middle East, and parts of Asia. "
            "If you share the destination country, we can confirm availability before payment."
        ),
        keywords=(
            "ship to",
            "shipping country",
            "international shipping",
            "envio internacional",
            "pais de envio",
            "livraison internationale",
            "expedier dans",
            "国际配送",
            "配送国家",
            "发哪些国家",
            "شحن دولي",
            "الدول المتاحة للشحن",
        ),
    ),
)

# Compiled keyword matchers for word-boundary-aware matching
_KEYWORD_PATTERNS: dict[str, re.Pattern] = {}


def _get_keyword_pattern(keyword: str) -> re.Pattern:
    """Build or retrieve a cached word-boundary pattern for a keyword."""
    pattern = _KEYWORD_PATTERNS.get(keyword)
    if pattern is None:
        escaped = re.escape(keyword)
        pattern = re.compile(rf"\b{escaped}\b", re.IGNORECASE)
        _KEYWORD_PATTERNS[keyword] = pattern
    return pattern


def list_support_knowledge(category: str | None = None) -> list[SupportKnowledgeEntry]:
    if category is None:
        return list(SUPPORT_KNOWLEDGE_ENTRIES)
    return [entry for entry in SUPPORT_KNOWLEDGE_ENTRIES if entry.category == category]


def match_support_knowledge(user_message: str) -> SupportKnowledgeMatch | None:
    normalized_text = _normalize_text(user_message)
    return match_support_knowledge_entries(
        entries=SUPPORT_KNOWLEDGE_ENTRIES,
        normalized_text=normalized_text,
    )


def match_support_knowledge_entries(
    entries: list[SupportKnowledgeEntry] | tuple[SupportKnowledgeEntry, ...],
    normalized_text: str,
) -> SupportKnowledgeMatch | None:
    best_match: SupportKnowledgeMatch | None = None

    for entry in entries:
        keyword_count = len(entry.keywords)
        matched_keywords = 0
        max_word_count = 0

        for keyword in entry.keywords:
            if keyword_count > 0 and _keyword_matches(keyword, normalized_text):
                matched_keywords += 1
                word_count = len(keyword.split())
                if word_count > max_word_count:
                    max_word_count = word_count

        if matched_keywords < entry.minimum_score:
            continue

        # Density score: matched keywords / total keywords
        density = matched_keywords / keyword_count if keyword_count > 0 else 0.0
        # Specificity bonus for multi-word keyword matches
        specificity_bonus = max_word_count * 0.05
        raw_score = density + specificity_bonus
        score = int(round(raw_score * 100))

        if best_match is None:
            best_match = SupportKnowledgeMatch(entry=entry, score=score)
        else:
            if score > best_match.score:
                best_match = SupportKnowledgeMatch(entry=entry, score=score)
            elif score == best_match.score and entry.priority < best_match.entry.priority:
                best_match = SupportKnowledgeMatch(entry=entry, score=score)

    return best_match


def _keyword_matches(keyword: str, normalized_text: str) -> bool:
    """Check if a keyword matches the normalized text.

    Uses word-boundary regex for Latin scripts and substring match
    for CJK / Arabic scripts where \\b does not work reliably.
    """
    if _is_word_boundary_safe(keyword):
        pattern = _get_keyword_pattern(keyword)
        return pattern.search(normalized_text) is not None
    normalized_keyword = _normalize_text(keyword)
    return normalized_keyword in normalized_text


def _is_word_boundary_safe(text: str) -> bool:
    """Check if text primarily uses scripts where \\b works correctly."""
    for char in text:
        cp = ord(char)
        if 0x0600 <= cp <= 0x06FF:   # Arabic
            return False
        if 0x4E00 <= cp <= 0x9FFF:   # CJK unified
            return False
        if 0xAC00 <= cp <= 0xD7AF:   # Korean
            return False
        if 0x3040 <= cp <= 0x309F:   # Hiragana
            return False
        if 0x30A0 <= cp <= 0x30FF:   # Katakana
            return False
    return True


def _normalize_text(value: str) -> str:
    compact = re.sub(r"\s+", " ", value.strip().lower())
    return compact


def normalize_support_knowledge_text(value: str) -> str:
    return _normalize_text(value)
