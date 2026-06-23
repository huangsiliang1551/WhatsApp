"""AI 聊天配置 API — Task 5.

Endpoints:
  GET    /api/ai-chat-config/system             — 获取系统默认配置
  PUT    /api/ai-chat-config/system             — 更新系统默认配置
  GET    /api/ai-chat-config/agency/{id}        — 获取代理商有效配置
  PUT    /api/ai-chat-config/agency/{id}        — 更新代理商配置
  DELETE /api/ai-chat-config/agency/{id}        — 恢复代理商到系统默认
  POST   /api/ai-chat-config/test               — 测试聊天
  GET    /api/ai-chat-config/preview-prompt     — 预览最终 system_prompt
  GET    /api/ai-chat-config/tools              — 获取可用工具列表及说明
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, get_request_actor, require_permission
from app.core.auth import RequestActor
from app.core.settings import Settings, get_settings
from app.providers.ai.base import AIModelParams, AIReplyRequest, AIConversationTurn
from app.providers.factory import get_ai_provider
from app.services.ai_chat_config_service import AiChatConfigService, AVAILABLE_TOOLS, DEFAULT_ALLOWED_TOOLS
from app.services.ai_tool_executor import AIToolExecutor

logger = structlog.get_logger()
router = APIRouter(prefix="/api/ai-chat-config", tags=["ai_chat_config"])


# ─── Schemas ────────────────────────────────────────────────────────────────


class SystemConfigResponse(BaseModel):
    id: str
    agency_id: str | None = None
    # ── 1. 系统提示词 ──
    system_prompt: str | None = None
    prompt_append_context: bool | None = None
    prompt_variables: dict | None = None
    # ── 2. 模型参数 ──
    temperature: float | None = None
    max_tokens: int | None = None
    top_p: float | None = None
    frequency_penalty: float | None = None
    presence_penalty: float | None = None
    stop_sequences: list[str] | None = None
    # ── 3. 会话行为 ──
    context_window_messages: int | None = None
    context_window_tokens: int | None = None
    conversation_memory: bool | None = None
    greeting_message: str | None = None
    off_hours_message: str | None = None
    off_hours_start: str | None = None
    off_hours_end: str | None = None
    off_hours_timezone: str | None = None
    # ── 4. 自动回复 ──
    auto_reply_enabled: bool | None = None
    auto_reply_delay_seconds: int | None = None
    auto_reply_keywords: dict | None = None
    auto_reply_fallback: str | None = None
    duplicate_message_filter: bool | None = None
    # ── 5. 转人工 ──
    auto_escalation_enabled: bool | None = None
    escalation_keywords: list[str] | None = None
    escalation_max_failures: int | None = None
    escalation_sentiment_threshold: float | None = None
    escalation_max_rounds: int | None = None
    escalation_message: str | None = None
    # ── 6. 安全 ──
    blocked_topics: list[str] | None = None
    content_filter_enabled: bool | None = None
    pii_protection: bool | None = None
    max_response_length: int | None = None
    language_lock: bool | None = None
    # ── 7. 高级 ──
    response_format: str | None = None
    inject_brand_info: bool | None = None
    inject_knowledge_base: bool | None = None
    debug_mode: bool | None = None
    # ── 8. AI 工具调用 ──
    tools_enabled: bool | None = None
    enabled_tools: list[str] | None = None
    max_tool_calls_per_session: int | None = None
    identity_verify_method: str | None = None
    identity_auto_verify: bool | None = None
    tool_call_timeout_seconds: int | None = None
    created_by: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class UpdateConfigRequest(BaseModel):
    # ── 1. 系统提示词 ──
    system_prompt: str | None = None
    prompt_append_context: bool | None = None
    prompt_variables: dict | None = None
    # ── 2. 模型参数 ──
    temperature: float | None = None
    max_tokens: int | None = None
    top_p: float | None = None
    frequency_penalty: float | None = None
    presence_penalty: float | None = None
    stop_sequences: list[str] | None = None
    # ── 3. 会话行为 ──
    context_window_messages: int | None = None
    context_window_tokens: int | None = None
    conversation_memory: bool | None = None
    greeting_message: str | None = None
    off_hours_message: str | None = None
    off_hours_start: str | None = None
    off_hours_end: str | None = None
    off_hours_timezone: str | None = None
    # ── 4. 自动回复 ──
    auto_reply_enabled: bool | None = None
    auto_reply_delay_seconds: int | None = None
    auto_reply_keywords: dict | None = None
    auto_reply_fallback: str | None = None
    duplicate_message_filter: bool | None = None
    # ── 5. 转人工 ──
    auto_escalation_enabled: bool | None = None
    escalation_keywords: list[str] | None = None
    escalation_max_failures: int | None = None
    escalation_sentiment_threshold: float | None = None
    escalation_max_rounds: int | None = None
    escalation_message: str | None = None
    # ── 6. 安全 ──
    blocked_topics: list[str] | None = None
    content_filter_enabled: bool | None = None
    pii_protection: bool | None = None
    max_response_length: int | None = None
    language_lock: bool | None = None
    # ── 7. 高级 ──
    response_format: str | None = None
    inject_brand_info: bool | None = None
    inject_knowledge_base: bool | None = None
    debug_mode: bool | None = None
    # ── 8. AI 工具调用 ──
    tools_enabled: bool | None = None
    enabled_tools: list[str] | None = None
    max_tool_calls_per_session: int | None = None
    identity_verify_method: str | None = None
    identity_auto_verify: bool | None = None
    tool_call_timeout_seconds: int | None = None


class TestChatRequest(BaseModel):
    agency_id: str | None = None
    user_message: str
    customer_language: str = "zh-CN"
    conversation_history: list[dict[str, str]] = []


class PreviewPromptRequest(BaseModel):
    agency_id: str | None = None
    extra_vars: dict[str, str] = {}


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _config_to_response(config: Any) -> dict[str, Any]:
    return {
        "id": config.id,
        "agency_id": config.agency_id,
        # 1
        "system_prompt": config.system_prompt,
        "prompt_append_context": config.prompt_append_context,
        "prompt_variables": config.prompt_variables if isinstance(config.prompt_variables, dict) else {},
        # 2
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
        "top_p": config.top_p,
        "frequency_penalty": config.frequency_penalty,
        "presence_penalty": config.presence_penalty,
        "stop_sequences": config.stop_sequences if isinstance(config.stop_sequences, list) else [],
        # 3
        "context_window_messages": config.context_window_messages,
        "context_window_tokens": config.context_window_tokens,
        "conversation_memory": config.conversation_memory,
        "greeting_message": config.greeting_message,
        "off_hours_message": config.off_hours_message,
        "off_hours_start": config.off_hours_start,
        "off_hours_end": config.off_hours_end,
        "off_hours_timezone": config.off_hours_timezone,
        # 4
        "auto_reply_enabled": config.auto_reply_enabled,
        "auto_reply_delay_seconds": config.auto_reply_delay_seconds,
        "auto_reply_keywords": config.auto_reply_keywords if isinstance(config.auto_reply_keywords, dict) else {},
        "auto_reply_fallback": config.auto_reply_fallback,
        "duplicate_message_filter": config.duplicate_message_filter,
        # 5
        "auto_escalation_enabled": config.auto_escalation_enabled,
        "escalation_keywords": config.escalation_keywords if isinstance(config.escalation_keywords, list) else [],
        "escalation_max_failures": config.escalation_max_failures,
        "escalation_sentiment_threshold": config.escalation_sentiment_threshold,
        "escalation_max_rounds": config.escalation_max_rounds,
        "escalation_message": config.escalation_message,
        # 6
        "blocked_topics": config.blocked_topics if isinstance(config.blocked_topics, list) else [],
        "content_filter_enabled": config.content_filter_enabled,
        "pii_protection": config.pii_protection,
        "max_response_length": config.max_response_length,
        "language_lock": config.language_lock,
        # 7
        "response_format": config.response_format,
        "inject_brand_info": config.inject_brand_info,
        "inject_knowledge_base": config.inject_knowledge_base,
        "debug_mode": config.debug_mode,
        # 8
        "tools_enabled": config.tools_enabled,
        "enabled_tools": config.enabled_tools if isinstance(config.enabled_tools, list) else [],
        "max_tool_calls_per_session": config.max_tool_calls_per_session,
        "identity_verify_method": config.identity_verify_method,
        "identity_auto_verify": config.identity_auto_verify,
        "tool_call_timeout_seconds": config.tool_call_timeout_seconds,
        # meta
        "created_by": config.created_by,
        "created_at": config.created_at.isoformat() if config.created_at else None,
        "updated_at": config.updated_at.isoformat() if config.updated_at else None,
    }


# ─── Endpoints ──────────────────────────────────────────────────────────────


@router.get("/system", summary="获取系统默认配置")
def get_system_config(
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("ai_chat_config.view_system")),
):
    svc = AiChatConfigService(session)
    config = svc.get_effective_config(agency_id=None)
    return _config_to_response(config)


@router.put("/system", summary="更新系统默认配置")
def update_system_config(
    body: UpdateConfigRequest,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("ai_chat_config.edit_system")),
):
    svc = AiChatConfigService(session)
    updates = {k: v for k, v in body.model_dump(exclude_none=True).items()}
    if not updates:
        raise HTTPException(status_code=400, detail="未提供需要更新的字段")
    config = svc.upsert_system_default(updates)
    session.commit()
    return _config_to_response(config)


@router.get("/agency/{agency_id}", summary="获取代理商有效配置")
def get_agency_config(
    agency_id: str,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("ai_chat_config.view_agency")),
):
    svc = AiChatConfigService(session)
    config = svc.get_effective_config(agency_id=agency_id)
    return _config_to_response(config)


@router.put("/agency/{agency_id}", summary="更新代理商配置")
def update_agency_config(
    agency_id: str,
    body: UpdateConfigRequest,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("ai_chat_config.edit_agency")),
):
    svc = AiChatConfigService(session)
    updates = {k: v for k, v in body.model_dump(exclude_none=True).items()}
    if not updates:
        raise HTTPException(status_code=400, detail="未提供需要更新的字段")
    config = svc.upsert_agency_config(agency_id, updates)
    session.commit()
    return _config_to_response(config)


@router.delete("/agency/{agency_id}", summary="恢复代理商到系统默认")
def reset_agency_config(
    agency_id: str,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("ai_chat_config.reset_agency")),
):
    svc = AiChatConfigService(session)
    deleted = svc.reset_agency_config(agency_id)
    session.commit()
    if not deleted:
        raise HTTPException(status_code=404, detail="未找到该代理商的配置")
    return {"success": True, "message": f"代理商 {agency_id} 的 AI 聊天配置已重置为系统默认"}


@router.post("/test", summary="测试聊天配置")
async def test_chat(
    body: TestChatRequest,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("ai_chat_config.test")),
    settings: Settings = Depends(get_settings),
):
    """使用真实数据测试 AI 聊天配置，验证工具调用是否正常工作。"""
    svc = AiChatConfigService(session)
    config = svc.get_effective_config(agency_id=body.agency_id)

    # 构建模型参数
    model_params = AIModelParams(
        temperature=config.temperature or 0.3,
        max_tokens=config.max_tokens or 300,
        top_p=config.top_p or 1.0,
        frequency_penalty=config.frequency_penalty or 0.0,
        presence_penalty=config.presence_penalty or 0.0,
    )

    # 构建 system_prompt
    system_prompt = svc.build_system_prompt(
        config,
        extra_vars={"customer_language": body.customer_language},
    )

    # 获取可用工具
    available_tools = svc.get_available_tools(config)

    # 构建对话历史
    history = [
        AIConversationTurn(
            role=turn.get("role", "user"),
            text=turn.get("text", ""),
        )
        for turn in body.conversation_history
        if turn.get("text", "").strip()
    ]

    request = AIReplyRequest(
        account_id="test",
        conversation_id="test",
        customer_language=body.customer_language,
        user_message=body.user_message,
        conversation_history=history,
        system_prompt=system_prompt,
        model_params=model_params,
        available_tools=available_tools,
    )

    ai_provider = get_ai_provider(settings)

    # 支持 tool_call 循环
    from app.services.ai_tool_executor import AIToolExecutor

    tool_executor = AIToolExecutor(
        session=session,
        settings=settings,
        conversation_id="test",
        account_id="test",
        agency_id=body.agency_id,
    )

    reply_text = await _test_generate_with_tool_loop(ai_provider, request, tool_executor, config)

    # 截断
    if config and config.max_response_length:
        max_len = int(config.max_response_length)
        if max_len > 0 and len(reply_text) > max_len:
            reply_text = reply_text[:max_len].strip() + "..."

    return {
        "reply_text": reply_text,
        "system_prompt": system_prompt,
        "model_params": {
            "temperature": model_params.temperature,
            "max_tokens": model_params.max_tokens,
            "top_p": model_params.top_p,
        },
        "tools_enabled": len(available_tools) > 0,
        "tool_count": len(available_tools),
        "config_agency_id": config.agency_id,
    }


@router.get("/preview-prompt", summary="预览最终 system_prompt")
def preview_prompt(
    agency_id: str | None = None,
    customer_language: str = "auto",
    brand_name: str | None = None,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("ai_chat_config.view_system")),
):
    """预览最终生成的 system_prompt。支持覆盖变量。"""
    svc = AiChatConfigService(session)
    config = svc.get_effective_config(agency_id=agency_id)
    extra_vars: dict[str, str] = {"customer_language": customer_language}
    if brand_name:
        extra_vars["brand_name"] = brand_name
    prompt = svc.build_system_prompt(config, extra_vars=extra_vars)
    return {
        "prompt": prompt,
        "variables": dict(config.prompt_variables or {}),
    }


@router.get("/tools", summary="获取可用工具列表及说明")
def list_tools(
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("ai_chat_config.view_tools")),
):
    """返回所有可用的工具定义（OpenAI Function Calling 格式）。"""
    return {
        "tools": AVAILABLE_TOOLS,
        "default_allowed_tools": DEFAULT_ALLOWED_TOOLS,
        "tool_count": len(AVAILABLE_TOOLS),
    }


# ─── Test helper ────────────────────────────────────────────────────────────


async def _test_generate_with_tool_loop(
    ai_provider: Any,
    request: AIReplyRequest,
    tool_executor: AIToolExecutor,
    config: Any | None,
) -> str:
    """测试环境的 tool_call 循环（与队列处理器中的逻辑保持一致）。"""
    import json as _json

    max_rounds = 3
    current_request = request

    for _ in range(max_rounds):
        reply = await ai_provider.generate_reply(current_request)
        if not reply.startswith('{"__tool_calls__'):
            return reply

        try:
            data = _json.loads(reply)
            tool_calls = data.get("__tool_calls__", [])
        except (_json.JSONDecodeError, TypeError):
            return reply

        if not tool_calls:
            continue

        results_text = ""
        for tc in tool_calls:
            func_name = tc.get("function", {}).get("name", "")
            func_args_raw = tc.get("function", {}).get("arguments", "{}")
            try:
                func_args = _json.loads(func_args_raw) if isinstance(func_args_raw, str) else func_args_raw
            except _json.JSONDecodeError:
                func_args = {}
            max_calls = (config.max_tool_calls_per_session or 10) if config else 10
            timeout = (config.tool_call_timeout_seconds or 5) if config else 5
            result = await tool_executor.execute_tool(
                tool_name=func_name,
                arguments=func_args,
                verified_user_id=None,
                max_calls=max_calls,
                timeout_seconds=timeout,
            )
            results_text += f"\n[{func_name}]：{_json.dumps(result, ensure_ascii=False)}"

        new_history = list(current_request.conversation_history)
        new_history.append(AIConversationTurn(role="assistant", text=f"[工具调用结果]\n{results_text.strip()}"))
        current_request = AIReplyRequest(
            account_id=current_request.account_id,
            conversation_id=current_request.conversation_id,
            customer_language=current_request.customer_language,
            user_message="请根据以上工具调用结果的最终输出，用自然语言回复客户。",
            conversation_history=new_history,
            system_prompt=current_request.system_prompt,
            model_params=current_request.model_params,
            available_tools=[],
            verified_user_id=current_request.verified_user_id,
            agency_id=current_request.agency_id,
        )

    return await ai_provider.generate_reply(current_request)
