import string
from typing import Any

import redis.asyncio as aioredis
import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.settings import Settings
from app.db.models import AIPrompt

logger = structlog.get_logger()

PROMPT_CACHE_TTL = 300  # 5 minutes
PROMPT_CACHE_KEY_PREFIX = "prompt_cache"

_FALLBACK_PROMPTS: dict[str, dict[str, str]] = {
    "customer_service_default": {
        "en": (
            "You are a helpful customer service assistant for {company_name}. "
            "Respond politely and professionally to the customer's inquiry. "
            "If you cannot resolve the issue, offer to transfer to a human agent.\n\n"
            "Customer language: {customer_language}\n"
            "Customer message: {user_message}"
        ),
        "zh-CN": (
            "你是一个友好的客服助手，代表{company_name}。请礼貌且专业地回复客户询问。\n"
            "如果无法解决问题，请提供转接人工客服的选项。\n\n"
            "客户语言：{customer_language}\n"
            "客户消息：{user_message}"
        ),
    },
    "customer_service_human_handover": {
        "en": (
            "I'm sorry, but I'm unable to fully resolve your issue. "
            "I will transfer you to a human agent who can provide further assistance. "
            "Please wait while we connect you."
        ),
        "zh-CN": (
            "很抱歉，我无法完全解决您的问题。我将为您转接人工客服，请稍候。"
        ),
    },
    "product_inquiry": {
        "en": (
            "You are a product specialist for {company_name}. "
            "Provide accurate and helpful information about our products. "
            "If you need specific product details, ask the customer for the product name or SKU.\n\n"
            "Customer language: {customer_language}\n"
            "Customer message: {user_message}"
        ),
        "zh-CN": (
            "你是{company_name}的产品专员。请提供准确有用的产品信息。\n"
            "如果需要具体的产品详情，请向客户询问产品名称或SKU。\n\n"
            "客户语言：{customer_language}\n"
            "客户消息：{user_message}"
        ),
    },
    "order_status": {
        "en": (
            "You are an order support assistant for {company_name}. "
            "Help customers check their order status. "
            "Ask for the order ID if not provided.\n\n"
            "Customer language: {customer_language}\n"
            "Customer message: {user_message}"
        ),
        "zh-CN": (
            "你是{company_name}的订单支持助手。帮助客户查询订单状态。\n"
            "如果客户未提供订单号，请询问。\n\n"
            "客户语言：{customer_language}\n"
            "客户消息：{user_message}"
        ),
    },
    "complaint_handling": {
        "en": (
            "You are a complaint handling specialist for {company_name}. "
            "Listen to the customer's complaint empathetically, apologize sincerely, "
            "and offer a reasonable solution. Escalate to a human agent if needed.\n\n"
            "Customer language: {customer_language}\n"
            "Customer complaint: {user_message}"
        ),
        "zh-CN": (
            "你是{company_name}的投诉处理专员。请以同理心倾听客户的投诉，真诚致歉，\n"
            "并提供合理的解决方案。必要时升级给人工客服。\n\n"
            "客户语言：{customer_language}\n"
            "客户投诉：{user_message}"
        ),
    },
}


class PromptManager:
    def __init__(
        self,
        settings: Settings,
        session: Session,
        redis_client: Any | None = None,
    ) -> None:
        self._settings = settings
        self._session = session
        if redis_client is not None:
            self._redis = redis_client
        elif settings.test_mode:
            self._redis = None
        else:
            self._redis = aioredis.from_url(settings.redis_url, decode_responses=True)

    async def get_prompt(
        self,
        template_name: str,
        account_id: str | None = None,
        language: str = "en",
        variables: dict[str, str] | None = None,
    ) -> str:
        cache_key = f"{PROMPT_CACHE_KEY_PREFIX}:{template_name}:{account_id or '__global__'}:{language}"

        cached = await self._get_cached(cache_key)
        if cached is not None:
            return self._substitute_variables(cached, variables or {})

        db_prompt = await self._load_from_db(template_name, account_id, language)
        if db_prompt is not None:
            await self._set_cache(cache_key, db_prompt)
            return self._substitute_variables(db_prompt, variables or {})

        fallback = self._load_fallback(template_name, language)
        if fallback is not None:
            # Only cache fallback for the least specific scope to avoid DB lookups next time
            narrow_key = f"{PROMPT_CACHE_KEY_PREFIX}:{template_name}:__global__:{language}"
            await self._set_cache(narrow_key, fallback)
            return self._substitute_variables(fallback, variables or {})

        raise LookupError(f"No prompt found for template '{template_name}' (account={account_id}, language={language})")

    async def _get_cached(self, cache_key: str) -> str | None:
        if self._redis is None:
            return None
        try:
            value = await self._redis.get(cache_key)
            return str(value) if value is not None else None
        except Exception:
            logger.warning("prompt_cache_read_failed", cache_key=cache_key, exc_info=True)
            return None

    async def _set_cache(self, cache_key: str, value: str) -> None:
        if self._redis is None:
            return
        try:
            await self._redis.setex(cache_key, PROMPT_CACHE_TTL, value)
        except Exception:
            logger.warning("prompt_cache_write_failed", cache_key=cache_key, exc_info=True)

    async def _load_from_db(self, template_name: str, account_id: str | None, language: str) -> str | None:
        try:
            query = (
                select(AIPrompt)
                .where(
                    AIPrompt.name == template_name,
                    AIPrompt.is_active.is_(True),
                )
                .order_by(AIPrompt.version.desc())
            )

            if account_id is not None:
                query = query.where(
                    (AIPrompt.account_id == account_id) | (AIPrompt.account_id.is_(None))
                )
                entry = self._session.scalars(query).first()
                if entry is not None and entry.account_id != account_id:
                    return None
            else:
                query = query.where(AIPrompt.account_id.is_(None))
                entry = self._session.scalars(query).first()

            if entry is None:
                return None

            return str(entry.content)
        except Exception:
            logger.warning("prompt_db_load_failed", template_name=template_name, exc_info=True)
            return None

    def _load_fallback(self, template_name: str, language: str) -> str | None:
        language_map = _FALLBACK_PROMPTS.get(template_name)
        if language_map is None:
            return None
        prompt = language_map.get(language)
        if prompt is None:
            prompt = language_map.get("en")
        return prompt

    @staticmethod
    def _substitute_variables(template: str, variables: dict[str, str]) -> str:
        if not variables:
            return template

        defaults = {
            "company_name": "our store",
            "customer_language": "en",
            "user_message": "",
        }
        defaults.update(variables)

        try:
            return string.Template(template).safe_substitute(defaults)
        except ValueError:
            return template
