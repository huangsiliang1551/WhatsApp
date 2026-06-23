"""AI 工具执行引擎 — Task 4.5.

提供 10 个安全工具调用（Function Calling）的执行器，
包含身份验证、余额查询、交易记录、签到状态、任务进度、
提现状态、知识库搜索、商品列表、充值指引、认证指引。

安全边界：
- 所有工具只读，绝不修改数据
- 需要身份验证的工具先检查 conversation.verified_user_id
- 调用次数限制（max_tool_calls_per_session）
- 带超时执行
"""

from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.settings import Settings

logger = structlog.get_logger()

# ── 工具白名单 ────────────────────────────────────────────────────────────────
TOOL_WHITELIST: set[str] = {
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
}

# ── 需要身份验证的工具 ─────────────────────────────────────────────────────────
TOOLS_REQUIRING_AUTH: set[str] = {
    "get_balance",
    "get_transactions",
    "get_sign_in_status",
    "get_task_progress",
    "get_withdrawal_status",
}


class AIToolExecutor:
    """AI 工具调用执行引擎。

    执行流程：
    1. 安全检查：工具在白名单中
    2. 安全检查：需要身份验证的工具检查 verified_user_id
    3. 调用次数限制检查
    4. 带超时执行
    5. 记录到会话 metadata_json
    """

    def __init__(
        self,
        session: Session,
        settings: Settings,
        conversation_id: str,
        account_id: str,
        agency_id: str | None = None,
    ) -> None:
        self._session = session
        self._settings = settings
        self._conversation_id = conversation_id
        self._account_id = account_id
        self._agency_id = agency_id
        self._tool_call_count: int = 0

    @property
    def tool_call_count(self) -> int:
        return self._tool_call_count

    async def execute_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        verified_user_id: str | None = None,
        max_calls: int = 10,
        timeout_seconds: int = 15,
    ) -> dict[str, Any]:
        """执行单个工具调用。

        Args:
            tool_name: 工具名称
            arguments: 工具参数 dict
            verified_user_id: 已认证的用户 ID（如果已验证）
            max_calls: 本次会话最大工具调用次数
            timeout_seconds: 单次工具调用超时秒数

        Returns:
            {"success": bool, "result": Any, "error": str | None}
        """
        # ── 安全检查 1: 白名单 ──
        if tool_name not in TOOL_WHITELIST:
            logger.warning(
                "tool_not_in_whitelist",
                tool=tool_name,
                conversation_id=self._conversation_id,
            )
            return {"success": False, "result": None, "error": f"工具 '{tool_name}' 不在白名单中"}

        # ── 安全检查 2: 调用次数限制 ──
        self._tool_call_count += 1
        if self._tool_call_count > max_calls:
            logger.warning(
                "tool_call_limit_exceeded",
                tool=tool_name,
                count=self._tool_call_count,
                max_calls=max_calls,
                conversation_id=self._conversation_id,
            )
            return {"success": False, "result": None, "error": f"工具调用次数超过限制 ({max_calls})"}

        # ── 安全检查 3: 需要身份验证的工具 ──
        if tool_name in TOOLS_REQUIRING_AUTH and not verified_user_id:
            return {
                "success": False,
                "result": None,
                "error": f"工具 '{tool_name}' 需要客户先完成身份验证",
            }

        # ── 执行工具（async timeout） ──
        start_time = time.time()
        try:
            result = await asyncio.wait_for(
                self._dispatch(tool_name, arguments, verified_user_id),
                timeout=timeout_seconds,
            )
            elapsed = time.time() - start_time
            if elapsed > timeout_seconds:
                logger.warning(
                    "tool_slow_execution",
                    tool=tool_name,
                    elapsed_seconds=round(elapsed, 2),
                    timeout_seconds=timeout_seconds,
                    conversation_id=self._conversation_id,
                )
            # 记录工具调用到会话 metadata_json
            self._record_tool_call(tool_name, arguments, result, elapsed)
            return {"success": True, "result": result, "error": None}
        except asyncio.TimeoutError:
            elapsed = time.time() - start_time
            logger.warning(
                "tool_timeout",
                tool=tool_name,
                timeout_seconds=timeout_seconds,
                conversation_id=self._conversation_id,
            )
            result = {"error": "timeout"}
            self._record_tool_call(tool_name, arguments, result, elapsed)
            return {"success": False, "result": None, "error": f"工具 '{tool_name}' 执行超时 ({timeout_seconds}s)"}
        except Exception as exc:
            elapsed = time.time() - start_time
            logger.warning(
                "tool_execution_failed",
                tool=tool_name,
                error=str(exc),
                elapsed_seconds=round(elapsed, 2),
                conversation_id=self._conversation_id,
            )
            result = {"error": str(exc)}
            self._record_tool_call(tool_name, arguments, result, elapsed)
            return {"success": False, "result": None, "error": str(exc)}

    async def _dispatch(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        verified_user_id: str | None,
    ) -> Any:
        """派发到具体的工具实现。"""
        handler = self._get_handler(tool_name)
        return await handler(arguments, verified_user_id)

    def _get_handler(self, tool_name: str):
        handlers = {
            "verify_identity": self._verify_identity,
            "get_balance": self._get_balance,
            "get_transactions": self._get_transactions,
            "get_sign_in_status": self._get_sign_in_status,
            "get_task_progress": self._get_task_progress,
            "get_withdrawal_status": self._get_withdrawal_status,
            "search_knowledge_base": self._search_knowledge_base,
            "list_products": self._list_products,
            "guide_recharge": self._guide_recharge,
            "guide_verification": self._guide_verification,
        }
        handler = handlers.get(tool_name)
        if handler is None:
            raise ValueError(f"未知工具: {tool_name}")
        return handler

    def _record_tool_call(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        result: Any,
        elapsed_seconds: float,
    ) -> None:
        """记录工具调用到会话 metadata_json（不写审计日志）。"""
        try:
            from app.db.models import Conversation
            stmt = select(Conversation).where(Conversation.id == self._conversation_id)
            conv = self._session.execute(stmt).scalar_one_or_none()
            if conv is None:
                return
            metadata = dict(getattr(conv, "metadata_json", {}) or {})
            tool_log = metadata.setdefault("tool_call_log", [])
            tool_log.append({
                "tool": tool_name,
                "arguments": arguments,
                "result": result if isinstance(result, dict) else {"value": str(result)},
                "elapsed_seconds": round(elapsed_seconds, 3),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            # 只保留最近 50 条
            if len(tool_log) > 50:
                metadata["tool_call_log"] = tool_log[-50:]
            conv.metadata_json = metadata
            self._session.flush()
        except Exception:
            logger.warning("failed_to_record_tool_call", tool=tool_name, conversation_id=self._conversation_id)

    # ═══════════════════════════════════════════════════════════════════════════
    # 工具具体实现（全部只读）
    # ═══════════════════════════════════════════════════════════════════════════

    async def _verify_identity(
        self,
        arguments: dict[str, Any],
        _verified_user_id: str | None,
    ) -> dict[str, Any]:
        """通过 WABA 获取会话关联 WhatsApp 号码 → 匹配 app_users。

        实际执行时会查询 conversation 的 phone_number_id，
        然后从 app_users 表中匹配号码。
        """
        customer_phone = arguments.get("customer_phone", "")
        if not customer_phone:
            return {"matched": False, "message": "请提供客户手机号"}

        # 查询 app_users 表匹配号码
        from app.db.models import AppUser

        stmt = select(AppUser).where(AppUser.phone == customer_phone)
        if self._agency_id:
            stmt = stmt.where(AppUser.agency_id == self._agency_id)
        user = self._session.execute(stmt).scalar_one_or_none()

        if user is None:
            return {"matched": False, "message": "未找到匹配的注册用户"}

        return {
            "matched": True,
            "customer_id": user.id,
            "customer_name": getattr(user, "name", "") or "",
            "phone": customer_phone,
        }

    async def _get_balance(
        self,
        arguments: dict[str, Any],
        verified_user_id: str | None,
    ) -> dict[str, Any]:
        """查询 wallet_accounts → 返回 system_balance + task_balance。"""
        from app.db.models import WalletAccount

        customer_id = arguments.get("customer_id", verified_user_id)
        stmt = select(WalletAccount).where(WalletAccount.user_id == customer_id)
        account = self._session.execute(stmt).scalar_one_or_none()

        if account is None:
            return {
                "system_balance": "0.00",
                "task_balance": "0.00",
                "message": "未找到钱包账户",
            }

        return {
            "system_balance": str(getattr(account, "system_balance", "0.00")),
            "task_balance": str(getattr(account, "task_balance", "0.00")),
            "total_balance": str(
                float(getattr(account, "system_balance", 0) or 0)
                + float(getattr(account, "task_balance", 0) or 0)
            ),
        }

    async def _get_transactions(
        self,
        arguments: dict[str, Any],
        verified_user_id: str | None,
    ) -> list[dict[str, Any]]:
        """查询 wallet_ledger_entries 最近 N 条。"""
        from app.db.models import WalletLedgerEntry

        customer_id = arguments.get("customer_id", verified_user_id)
        limit = int(arguments.get("limit", 10))

        stmt = (
            select(WalletLedgerEntry)
            .where(WalletLedgerEntry.user_id == customer_id)
            .order_by(WalletLedgerEntry.created_at.desc())
            .limit(limit)
        )
        entries = self._session.execute(stmt).scalars().all()

        return [
            {
                "id": e.id,
                "amount": str(getattr(e, "amount", "0")),
                "type": str(getattr(e, "entry_type", "") or ""),
                "description": str(getattr(e, "description", "") or ""),
                "created_at": str(getattr(e, "created_at", "") or ""),
            }
            for e in entries
        ]

    async def _get_sign_in_status(
        self,
        arguments: dict[str, Any],
        verified_user_id: str | None,
    ) -> dict[str, Any]:
        """查询 sign_in_records → 连续天数/今日是否签到。"""
        from app.db.models import SignInRecord

        customer_id = arguments.get("customer_id", verified_user_id)
        today = datetime.now(timezone.utc).date()

        stmt = (
            select(SignInRecord)
            .where(SignInRecord.user_id == customer_id)
            .order_by(SignInRecord.sign_in_date.desc())
        )
        records = self._session.execute(stmt).scalars().all()

        streak = 0
        signed_in_today = False
        if records:
            # 计算连续签到
            from datetime import timedelta

            check_date = today
            for record in records:
                record_date = getattr(record, "sign_in_date", None)
                if record_date == check_date:
                    streak += 1
                    if record_date == today:
                        signed_in_today = True
                    check_date = record_date - timedelta(days=1)
                else:
                    break

        return {
            "signed_in_today": signed_in_today,
            "streak_days": streak,
            "total_days": len(records),
        }

    async def _get_task_progress(
        self,
        arguments: dict[str, Any],
        verified_user_id: str | None,
    ) -> list[dict[str, Any]]:
        """查询 mkt_task_instances → 任务名/进度/状态。"""
        from app.db.models import MktTaskInstance

        customer_id = arguments.get("customer_id", verified_user_id)

        stmt = (
            select(MktTaskInstance)
            .where(MktTaskInstance.user_id == customer_id)
            .order_by(MktTaskInstance.updated_at.desc())
            .limit(20)
        )
        instances = self._session.execute(stmt).scalars().all()

        return [
            {
                "task_name": str(getattr(i, "task_name", "") or ""),
                "progress": str(getattr(i, "progress", "0") or "0"),
                "status": str(getattr(i, "status", "") or ""),
                "reward": str(getattr(i, "reward_amount", "0") or "0"),
                "updated_at": str(getattr(i, "updated_at", "") or ""),
            }
            for i in instances
        ]

    async def _get_withdrawal_status(
        self,
        arguments: dict[str, Any],
        verified_user_id: str | None,
    ) -> list[dict[str, Any]]:
        """查询提现记录 → 审核/打款状态。"""
        from app.db.models import Withdrawal

        customer_id = arguments.get("customer_id", verified_user_id)
        from app.db.models import PlatformWithdrawal

        results: list[dict[str, Any]] = []

        # 查询平台提现
        stmt = (
            select(PlatformWithdrawal)
            .where(PlatformWithdrawal.user_id == customer_id)
            .order_by(PlatformWithdrawal.created_at.desc())
            .limit(10)
        )
        withdrawals = self._session.execute(stmt).scalars().all()
        for w in withdrawals:
            results.append(
                {
                    "type": "platform",
                    "amount": str(getattr(w, "amount", "0") or "0"),
                    "status": str(getattr(w, "status", "") or ""),
                    "review_status": str(getattr(w, "review_status", "") or ""),
                    "created_at": str(getattr(w, "created_at", "") or ""),
                }
            )

        # 也查 withdrawal 表
        w_stmt = (
            select(Withdrawal)
            .where(Withdrawal.user_id == customer_id)
            .order_by(Withdrawal.created_at.desc())
            .limit(10)
        )
        try:
            withdrawals2 = self._session.execute(w_stmt).scalars().all()
            for w in withdrawals2:
                results.append(
                    {
                        "type": "withdrawal",
                        "amount": str(getattr(w, "amount", "0") or "0"),
                        "status": str(getattr(w, "status", "") or ""),
                        "created_at": str(getattr(w, "created_at", "") or ""),
                    }
                )
        except Exception:
            pass

        return results[:10]

    async def _search_knowledge_base(
        self,
        arguments: dict[str, Any],
        _verified_user_id: str | None,
    ) -> list[dict[str, Any]]:
        """调用 KnowledgeBaseService.search()。"""
        from app.services.knowledge_base_service import KnowledgeBaseService

        query_text = arguments.get("query", "")
        if not query_text:
            return []

        kb_service = KnowledgeBaseService(self._session)
        results = kb_service.search(
            query=query_text,
            agency_id=self._agency_id,
        )
        return [
            {
                "id": r.id,
                "title": r.title,
                "content": _truncate_text(getattr(r, "content", ""), 300),
                "score": getattr(r, "score", 1.0),
            }
            for r in results
        ]

    async def _list_products(
        self,
        arguments: dict[str, Any],
        _verified_user_id: str | None,
    ) -> list[dict[str, Any]]:
        """查询 products 表。"""
        from app.db.models import Product

        category = arguments.get("category", "")
        limit = int(arguments.get("limit", 10))

        stmt = select(Product)
        if category:
            # 尝试匹配 category 字段
            if hasattr(Product, "category"):
                stmt = stmt.where(Product.category.ilike(f"%{category}%"))
        if self._agency_id and hasattr(Product, "agency_id"):
            stmt = stmt.where(Product.agency_id == self._agency_id)
        stmt = stmt.limit(limit)

        products = self._session.execute(stmt).scalars().all()
        return [
            {
                "id": p.id,
                "name": getattr(p, "name", "") or "",
                "price": str(getattr(p, "price", "0") or "0"),
                "description": _truncate_text(getattr(p, "description", "") or "", 200),
            }
            for p in products
        ]

    async def _guide_recharge(
        self,
        _arguments: dict[str, Any],
        _verified_user_id: str | None,
    ) -> dict[str, Any]:
        """返回静态充值指引。"""
        return {
            "title": "充值操作指引",
            "steps": [
                "1. 登录您的账户",
                "2. 进入「我的钱包」页面",
                "3. 点击「充值」按钮",
                "4. 选择充值金额和支付方式",
                "5. 完成支付后金额将自动到账",
            ],
            "note": "如遇充值问题，请联系人工客服处理。",
        }

    async def _guide_verification(
        self,
        _arguments: dict[str, Any],
        _verified_user_id: str | None,
    ) -> dict[str, Any]:
        """返回静态认证指引。"""
        return {
            "title": "身份认证操作指引",
            "steps": [
                "1. 登录您的账户",
                "2. 进入「账户设置」页面",
                "3. 点击「身份认证」",
                "4. 按要求上传身份证照片",
                "5. 等待系统审核（通常 1-2 个工作日）",
            ],
            "note": "完成认证后可以享受更多服务和功能。",
        }


def _truncate_text(text: str, max_length: int) -> str:
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."
