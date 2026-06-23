"""AI 聊天配置服务 — Task 2.

提供系统默认/代理商配置的查询、更新、重置功能，
以及构建 system_prompt、转人工条件检查、可用工具列表。
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AiChatConfig


# ── 默认系统配置 ──────────────────────────────────────────────────────────────
DEFAULT_SYSTEM_PROMPT_TEMPLATE = (
    "你是一个专业的 WhatsApp 客服助手。\n"
    "\n"
    "## 核心规则\n"
    "1. 用客户的语言回复（客户语言: {{customer_language}}）\n"
    "2. 回复简洁、行动导向，每条消息不超过 100 字\n"
    "3. 不编造订单或政策信息，不确定时主动询问\n"
    "4. 保持礼貌和专业\n"
    "5. 品牌名称: {{brand_name}}\n"
    "\n"
    "## 回复风格\n"
    "- 语气: 友好专业\n"
    "- 禁止: 讨论竞争对手、发表政治言论、提供医疗/法律建议\n"
    "- 当客户情绪激动时: 先共情，再解决问题\n"
    "\n"
    "## 知识库\n"
    "当知识库中有相关答案时，优先使用知识库内容回复。"
)

DEFAULT_MODEL_PARAMS: dict[str, Any] = {
    "temperature": 0.3,
    "max_tokens": 300,
    "top_p": 1.0,
    "frequency_penalty": 0.0,
    "presence_penalty": 0.0,
    "stop_sequences": [],
}

DEFAULT_CONTEXT_PARAMS: dict[str, Any] = {
    "context_window_messages": 10,
    "context_window_tokens": 2000,
}

DEFAULT_ALLOWED_TOOLS: list[str] = [
    "verify_identity",
    "get_balance",
    "get_transactions",
    "get_sign_in_status",
    "get_task_progress",
    "get_withdrawal_status",
    "search_knowledge_base",
    "list_products",
    "guide_recharge",
    "guide_verification",
]


# ── 可用工具定义（OpenAI Function Calling 格式）─ ────────────────────────────
AVAILABLE_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "verify_identity",
            "description": "验证客户身份：通过 WhatsApp 号码匹配系统中的注册用户",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_phone": {
                        "type": "string",
                        "description": "客户的 WhatsApp 号码",
                    },
                },
                "required": ["customer_phone"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_balance",
            "description": "查询客户账户余额（系统余额 + 任务余额）",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {
                        "type": "string",
                        "description": "已认证的客户 ID",
                    },
                },
                "required": ["customer_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_transactions",
            "description": "查询客户最近交易记录",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {
                        "type": "string",
                        "description": "已认证的客户 ID",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回条数，默认 10",
                    },
                },
                "required": ["customer_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_sign_in_status",
            "description": "查询客户的签到情况（连续天数、今日是否已签到）",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {
                        "type": "string",
                        "description": "已认证的客户 ID",
                    },
                },
                "required": ["customer_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_task_progress",
            "description": "查询客户参与的任务进度",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {
                        "type": "string",
                        "description": "已认证的客户 ID",
                    },
                },
                "required": ["customer_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_withdrawal_status",
            "description": "查询客户提现申请的审核和打款状态",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {
                        "type": "string",
                        "description": "已认证的客户 ID",
                    },
                },
                "required": ["customer_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_knowledge_base",
            "description": "在知识库中搜索常见问题答案",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_products",
            "description": "查询可用的商品列表",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "商品分类筛选（可选）",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回条数，默认 10",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "guide_recharge",
            "description": "返回充值操作指引",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "guide_verification",
            "description": "返回身份认证操作指引",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
]

# ── 工具启用时所需身份验证 ────────────────────────────────────────────────────
TOOLS_REQUIRING_AUTH: set[str] = {
    "get_balance",
    "get_transactions",
    "get_sign_in_status",
    "get_task_progress",
    "get_withdrawal_status",
}


class AiChatConfigService:
    """AI 聊天配置读写服务。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    # ── 查询 ──────────────────────────────────────────────────────────────────

    def get_effective_config(self, agency_id: str | None = None) -> AiChatConfig:
        """获取有效配置：代理商配置 → 系统默认。

        如果 agency_id 有值，优先返回代理商配置（没有则返回系统默认）。
        如果 agency_id=None，返回系统默认配置。
        """
        if agency_id:
            agency_config = self._get_agency_config(agency_id)
            if agency_config is not None:
                return agency_config
        return self._get_or_create_system_default()

    def _get_agency_config(self, agency_id: str) -> AiChatConfig | None:
        stmt = select(AiChatConfig).where(AiChatConfig.agency_id == agency_id)
        return self._session.execute(stmt).scalar_one_or_none()

    def _get_or_create_system_default(self) -> AiChatConfig:
        stmt = select(AiChatConfig).where(AiChatConfig.agency_id.is_(None))
        config = self._session.execute(stmt).scalar_one_or_none()
        if config is not None:
            return config
        config = AiChatConfig(
            agency_id=None,
            system_prompt=DEFAULT_SYSTEM_PROMPT_TEMPLATE,
            temperature=DEFAULT_MODEL_PARAMS["temperature"],
            max_tokens=DEFAULT_MODEL_PARAMS["max_tokens"],
            top_p=DEFAULT_MODEL_PARAMS["top_p"],
            frequency_penalty=DEFAULT_MODEL_PARAMS["frequency_penalty"],
            presence_penalty=DEFAULT_MODEL_PARAMS["presence_penalty"],
            context_window_messages=DEFAULT_CONTEXT_PARAMS["context_window_messages"],
            context_window_tokens=DEFAULT_CONTEXT_PARAMS["context_window_tokens"],
            enabled_tools=DEFAULT_ALLOWED_TOOLS,
        )
        self._session.add(config)
        self._session.flush()
        return config

    # ── 增/改 ─────────────────────────────────────────────────────────────────

    def upsert_system_default(self, updates: dict[str, Any]) -> AiChatConfig:
        """更新或创建系统默认配置。"""
        config = self._get_or_create_system_default()
        return self._apply_updates(config, updates)

    def upsert_agency_config(self, agency_id: str, updates: dict[str, Any]) -> AiChatConfig:
        """创建或更新某个代理商的配置。"""
        config = self._get_agency_config(agency_id)
        if config is None:
            # 克隆系统默认 + 应用更新
            defaults = self._get_or_create_system_default()
            config = AiChatConfig(agency_id=agency_id)
            self._copy_config(defaults, config)
            self._session.add(config)
            self._session.flush()
        return self._apply_updates(config, updates)

    # ── 重置 ──────────────────────────────────────────────────────────────────

    def reset_agency_config(self, agency_id: str) -> bool:
        """删除代理商配置，恢复为系统默认。返回是否找到并删除。"""
        config = self._get_agency_config(agency_id)
        if config is None:
            return False
        self._session.delete(config)
        self._session.flush()
        return True

    # ── 构建系统提示词 ────────────────────────────────────────────────────────

    def build_system_prompt(self, config: AiChatConfig, extra_vars: dict[str, str] | None = None) -> str:
        """根据配置和变量替换，构建最终的 system_prompt。

        从 config.system_prompt 读取模板，从 config.prompt_variables 读取默认变量，
        再合并 extra_vars 做格式化替换。
        """
        template = config.system_prompt or DEFAULT_SYSTEM_PROMPT_TEMPLATE
        vars_dict: dict[str, str] = dict(config.prompt_variables or {})
        if extra_vars:
            vars_dict.update(extra_vars)
        return template.format(**vars_dict)

    # ── 转人工条件检查 ─────────────────────────────────────────────────────────

    def check_escalation(
        self,
        config: AiChatConfig,
        user_message: str,
        intent_name: str | None = None,
        unknown_count: int = 0,
    ) -> tuple[bool, str | None]:
        """检查是否满足转人工条件。

        Returns:
            (should_escalate, reason)
        """
        # 关键词触发
        keywords = config.escalation_keywords or []
        if isinstance(keywords, list):
            for kw in keywords:
                if isinstance(kw, str) and kw.lower() in user_message.lower():
                    return True, f"触发转人工关键词: {kw}"

        # 连续未知触发
        threshold = config.escalation_max_failures or 3
        if unknown_count >= threshold:
            return True, f"连续 {unknown_count} 次未识别"

        return False, None

    # ── 可用工具列表 ──────────────────────────────────────────────────────────

    def get_available_tools(self, config: AiChatConfig) -> list[dict[str, Any]]:
        """返回 OpenAI function calling 格式的工具列表，按 enabled_tools 过滤。"""
        if not config.tools_enabled:
            return []
        allowed = config.enabled_tools or DEFAULT_ALLOWED_TOOLS
        if isinstance(allowed, list):
            allowed_set = set(allowed)
        else:
            allowed_set = set(DEFAULT_ALLOWED_TOOLS)
        return [t for t in AVAILABLE_TOOLS if t["function"]["name"] in allowed_set]

    # ── 内部辅助 ──────────────────────────────────────────────────────────────

    def _apply_updates(self, config: AiChatConfig, updates: dict[str, Any]) -> AiChatConfig:
        """将 updates dict 中的非 None 值应用到 config 对象。"""
        for key, value in updates.items():
            if hasattr(config, key):
                setattr(config, key, value)
        self._session.flush()
        return config

    @staticmethod
    def _copy_config(source: AiChatConfig, target: AiChatConfig) -> None:
        """将 source 的可配置字段复制到 target（跳过 id/agency_id/created_at/updated_at）。"""
        skip_fields = {"id", "agency_id", "created_at", "updated_at"}
        for column in source.__table__.columns:
            key = column.name
            if key in skip_fields:
                continue
            setattr(target, key, getattr(source, key))
