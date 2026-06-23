from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

from app.core.settings import Settings
from app.schemas.meta_accounts import MetaWabaAccount
from app.schemas.runtime import (
    AccountRuntimeState,
    LaunchReadinessCheck,
    LaunchReadinessResponse,
    LaunchReadinessSummary,
)
from app.services.meta_account_registry import MetaAccountRegistry, WebhookVerifyTokenConflict
from app.services.runtime_state import RuntimeStateStore


class LaunchReadinessService:
    def __init__(
        self,
        *,
        settings: Settings,
        runtime_state: RuntimeStateStore,
        meta_account_registry: MetaAccountRegistry,
    ) -> None:
        self._settings = settings
        self._runtime_state = runtime_state
        self._meta_account_registry = meta_account_registry

    async def assess(self) -> LaunchReadinessResponse:
        return await self.assess_with_scope()

    async def assess_with_scope(
        self,
        allowed_account_ids: set[str] | None = None,
        account_id: str | None = None,
    ) -> LaunchReadinessResponse:
        checks: list[LaunchReadinessCheck] = []
        runtime_state = await self._runtime_state.list_state()
        all_meta_accounts = await self._meta_account_registry.list_accounts()
        meta_accounts = all_meta_accounts
        if account_id is not None:
            if self._runtime_state.get_account_model(account_id) is None:
                raise LookupError(f"Account '{account_id}' was not found.")
            visible_accounts = [
                account
                for account in runtime_state.accounts
                if account.account_id == account_id
            ]
            meta_accounts = [
                meta_account
                for meta_account in meta_accounts
                if meta_account.account_id == account_id
            ]
            scoped_account_ids = {account_id}
        elif allowed_account_ids is not None:
            visible_accounts = [
                account
                for account in runtime_state.accounts
                if account.account_id in allowed_account_ids
            ]
            meta_accounts = [
                account
                for account in meta_accounts
                if account.account_id in allowed_account_ids
            ]
            scoped_account_ids = allowed_account_ids
        else:
            visible_accounts = list(runtime_state.accounts)
            scoped_account_ids = None
        active_accounts = [account for account in visible_accounts if account.is_active]
        active_account_count = len(active_accounts)
        meta_ready_accounts = [
            account for account in meta_accounts if account.ready_for_meta_activation
        ]
        meta_accounts_by_account_id = self._group_meta_accounts_by_account_id(meta_accounts)
        account_meta_coverage = self._summarize_account_meta_coverage(
            accounts=visible_accounts,
            meta_accounts_by_account_id=meta_accounts_by_account_id,
        )
        live_launch_mode = self._settings.messaging_provider.lower() == "whatsapp"
        pending_status_buffer_counts = await self._runtime_state.count_provider_status_buffer_events(
            replay_state="pending",
            account_id=account_id,
            account_ids=scoped_account_ids,
        )
        replayed_status_buffer_counts = await self._runtime_state.count_provider_status_buffer_events(
            replay_state="replayed",
            account_id=account_id,
            account_ids=scoped_account_ids,
        )
        oldest_pending_status_buffer_events = await self._runtime_state.list_provider_status_buffer_events(
            account_id=account_id,
            account_ids=scoped_account_ids,
            replay_state="pending",
            limit=5,
            oldest_first=True,
        )
        webhook_verify_token_conflicts = await self._meta_account_registry.list_webhook_verify_token_conflicts(
            account_id=account_id,
            allowed_account_ids=scoped_account_ids,
        )
        visible_scope_keys = {
            (account.account_id, account.waba_id)
            for account in meta_accounts
        }
        webhook_root_receive_signature_conflicts = await self._collect_root_receive_signature_conflicts(
            visible_scope_keys=visible_scope_keys,
            all_accounts=all_meta_accounts,
        )
        globally_blocked_scope_keys = self._collect_globally_blocked_waba_scope_keys(
            verify_token_conflicts=webhook_verify_token_conflicts,
            root_receive_signature_conflicts=webhook_root_receive_signature_conflicts,
        )
        meta_ready_accounts = [
            account
            for account in meta_accounts
            if account.ready_for_meta_activation
            and (account.account_id, account.waba_id) not in globally_blocked_scope_keys
        ]
        meta_ready_account_ids = {account.account_id for account in meta_ready_accounts}

        checks.extend(self._assess_runtime())
        checks.extend(self._assess_database())
        checks.extend(self._assess_queue())
        checks.extend(self._assess_ai())
        checks.extend(
            self._assess_messaging(
                meta_accounts,
                formal_ready_account_count=len(meta_ready_accounts),
            )
        )
        checks.extend(
            self._assess_runtime_account_meta_coverage(
                coverage=account_meta_coverage,
                live_launch_mode=live_launch_mode,
            )
        )
        checks.extend(
            self._assess_provider_status_buffer(
                pending_counts_by_account=pending_status_buffer_counts,
                replayed_counts_by_account=replayed_status_buffer_counts,
                oldest_pending_events=oldest_pending_status_buffer_events,
                live_launch_mode=live_launch_mode,
            )
        )
        checks.extend(self._assess_meta_management())
        checks.extend(
            self._assess_meta_accounts(
                meta_accounts,
                globally_blocked_scope_keys=globally_blocked_scope_keys,
                live_launch_mode=live_launch_mode,
            )
        )
        checks.extend(
            self._assess_webhook_verify_token_routing(
                conflicts=webhook_verify_token_conflicts,
                live_launch_mode=live_launch_mode,
            )
        )
        checks.extend(
            self._assess_webhook_root_receive_signature_routing(
                conflicts=webhook_root_receive_signature_conflicts,
                live_launch_mode=live_launch_mode,
            )
        )
        checks.extend(self._assess_monitoring_assets())
        checks.extend(self._assess_operations_assets())

        blocker_count = sum(1 for check in checks if check.status == "blocker")
        warning_count = sum(1 for check in checks if check.status == "warning")
        passed_count = sum(1 for check in checks if check.status == "pass")
        overall_status = (
            "blocked"
            if blocker_count > 0
            else "needs_attention"
            if warning_count > 0
            else "ready"
        )

        return LaunchReadinessResponse(
            summary=LaunchReadinessSummary(
                checked_at=datetime.now(UTC).replace(microsecond=0).isoformat(),
                overall_status=overall_status,
                scope="account" if account_id is not None else "system",
                account_id=account_id,
                blocker_count=blocker_count,
                warning_count=warning_count,
                passed_count=passed_count,
                active_account_count=active_account_count,
                meta_account_count=len(meta_accounts),
                meta_ready_account_count=len(meta_ready_account_ids),
                messaging_provider=self._settings.messaging_provider,
                ai_provider=self._settings.ai_provider,
                queue_backend="memory" if self._settings.test_mode else self._settings.queue_provider,
                metadata={
                    "visible_account_count": len(visible_accounts),
                    "active_account_count": active_account_count,
                    "active_accounts_without_waba_count": len(account_meta_coverage["without_waba"]),
                    "active_accounts_without_ready_waba_count": len(
                        account_meta_coverage["without_ready_waba"]
                    ),
                    "active_accounts_with_ready_waba_count": len(
                        account_meta_coverage["with_ready_waba"]
                    ),
                    "active_accounts_without_waba": account_meta_coverage["without_waba"],
                    "active_accounts_without_ready_waba": account_meta_coverage[
                        "without_ready_waba"
                    ],
                    "active_accounts_with_ready_waba": account_meta_coverage["with_ready_waba"],
                },
            ),
            checks=checks,
        )

    @staticmethod
    def _group_meta_accounts_by_account_id(
        meta_accounts: list[MetaWabaAccount],
    ) -> dict[str, list[MetaWabaAccount]]:
        grouped: dict[str, list[MetaWabaAccount]] = {}
        for meta_account in meta_accounts:
            grouped.setdefault(meta_account.account_id, []).append(meta_account)
        return grouped

    def _summarize_account_meta_coverage(
        self,
        *,
        accounts: list[AccountRuntimeState],
        meta_accounts_by_account_id: dict[str, list[MetaWabaAccount]],
    ) -> dict[str, list[dict[str, object]]]:
        coverage: dict[str, list[dict[str, object]]] = {
            "without_waba": [],
            "without_ready_waba": [],
            "with_ready_waba": [],
        }
        for account in accounts:
            if not account.is_active:
                continue
            linked_meta_accounts = meta_accounts_by_account_id.get(account.account_id, [])
            ready_meta_accounts = [
                meta_account
                for meta_account in linked_meta_accounts
                if meta_account.ready_for_meta_activation
            ]
            snapshot = {
                "account_id": account.account_id,
                "display_name": account.display_name,
                "provider_type": account.provider_type,
                "linked_waba_count": len(linked_meta_accounts),
                "ready_waba_count": len(ready_meta_accounts),
                "linked_waba_ids": [meta_account.waba_id for meta_account in linked_meta_accounts],
                "ready_waba_ids": [meta_account.waba_id for meta_account in ready_meta_accounts],
                "primary_waba_id": (
                    ready_meta_accounts[0].waba_id
                    if ready_meta_accounts
                    else linked_meta_accounts[0].waba_id
                    if linked_meta_accounts
                    else None
                ),
            }
            if not linked_meta_accounts:
                coverage["without_waba"].append(snapshot)
            elif not ready_meta_accounts:
                coverage["without_ready_waba"].append(snapshot)
            else:
                coverage["with_ready_waba"].append(snapshot)
        return coverage

    def _assess_runtime_account_meta_coverage(
        self,
        *,
        coverage: dict[str, list[dict[str, object]]],
        live_launch_mode: bool,
    ) -> list[LaunchReadinessCheck]:
        checks: list[LaunchReadinessCheck] = []
        missing_waba_accounts = coverage["without_waba"]
        missing_ready_waba_accounts = coverage["without_ready_waba"]
        ready_accounts = coverage["with_ready_waba"]

        account_issue_statuses = [
            self._account_meta_issue_status(account=item, live_launch_mode=live_launch_mode)
            for item in [*missing_waba_accounts, *missing_ready_waba_accounts]
        ]
        if account_issue_statuses:
            aggregate_status = (
                "blocker" if "blocker" in account_issue_statuses else "warning"
            )
            checks.append(
                LaunchReadinessCheck(
                    key="meta.account_runtime_coverage",
                    category="meta",
                    status=aggregate_status,
                    title="Active runtime accounts are not uniformly launch-ready",
                    message=(
                        f"{len(missing_waba_accounts)} active account(s) have no linked WABA and "
                        f"{len(missing_ready_waba_accounts)} active account(s) still lack a ready WABA."
                    ),
                    action_hint=(
                        "Link each active WhatsApp account to at least one WABA and finish webhook "
                        "plus outbound readiness before enabling formal launch."
                    ),
                    metadata={
                        "active_accounts_without_waba": missing_waba_accounts,
                        "active_accounts_without_ready_waba": missing_ready_waba_accounts,
                        "active_accounts_with_ready_waba": ready_accounts,
                    },
                )
            )
        else:
            checks.append(
                LaunchReadinessCheck(
                    key="meta.account_runtime_coverage",
                    category="meta",
                    status="pass",
                    title="Active runtime accounts have Meta coverage",
                    message=(
                        "Every active runtime account has at least one linked WABA ready for Meta activation."
                    ),
                    metadata={
                        "active_accounts_with_ready_waba": ready_accounts,
                    },
                )
            )

        for account in missing_waba_accounts:
            checks.append(
                LaunchReadinessCheck(
                    key=f"meta.account.{account['account_id']}.runtime_waba_coverage",
                    category="meta",
                    status=self._account_meta_issue_status(
                        account=account,
                        live_launch_mode=live_launch_mode,
                    ),
                    scope="account",
                    account_id=str(account["account_id"]),
                    title=f"Runtime account coverage for {account['display_name']}",
                    message="This active runtime account has no linked WABA records.",
                    action_hint=(
                        "Create or link a WABA for this account before routing live WhatsApp traffic."
                    ),
                    metadata=account,
                )
            )
        for account in missing_ready_waba_accounts:
            checks.append(
                LaunchReadinessCheck(
                    key=f"meta.account.{account['account_id']}.runtime_waba_readiness",
                    category="meta",
                    status=self._account_meta_issue_status(
                        account=account,
                        live_launch_mode=live_launch_mode,
                    ),
                    scope="account",
                    account_id=str(account["account_id"]),
                    waba_id=self._account_primary_waba_id(account),
                    title=f"Runtime account readiness for {account['display_name']}",
                    message=(
                        f"This active runtime account has {account['linked_waba_count']} linked WABA "
                        "record(s), but none are ready for Meta activation."
                    ),
                    action_hint=(
                        "Finish webhook subscription, verification, app secret, and registered phone "
                        "number setup for at least one linked WABA."
                    ),
                    metadata=account,
                )
            )
        for account in ready_accounts:
            checks.append(
                LaunchReadinessCheck(
                    key=f"meta.account.{account['account_id']}.runtime_waba_readiness",
                    category="meta",
                    status="pass",
                    scope="account",
                    account_id=str(account["account_id"]),
                    waba_id=self._account_primary_waba_id(account),
                    title=f"Runtime account readiness for {account['display_name']}",
                    message=(
                        f"This active runtime account has {account['ready_waba_count']} ready WABA "
                        "record(s)."
                    ),
                    metadata=account,
                )
            )
        return checks

    @staticmethod
    def _account_meta_issue_status(
        *,
        account: dict[str, object],
        live_launch_mode: bool,
    ) -> str:
        provider_type = str(account.get("provider_type") or "").lower()
        if live_launch_mode and provider_type == "whatsapp":
            return "blocker"
        return "warning"

    @staticmethod
    def _account_primary_waba_id(account: dict[str, object]) -> str | None:
        primary_waba_id = account.get("primary_waba_id")
        if isinstance(primary_waba_id, str) and primary_waba_id.strip():
            return primary_waba_id
        return None

    def _assess_runtime(self) -> list[LaunchReadinessCheck]:
        checks: list[LaunchReadinessCheck] = []
        if self._settings.test_mode:
            checks.append(
                LaunchReadinessCheck(
                    key="runtime.test_mode",
                    category="runtime",
                    status="blocker",
                    title="TEST_MODE is enabled",
                    message="The application is still running in test mode and is not ready for a formal launch environment.",
                    action_hint="Set TEST_MODE=false before formal deployment.",
                )
            )
        else:
            checks.append(
                LaunchReadinessCheck(
                    key="runtime.test_mode",
                    category="runtime",
                    status="pass",
                    title="TEST_MODE disabled",
                    message="Runtime is not using test-mode shortcuts.",
                )
            )

        if self._settings.app_env.lower() in {"development", "local"}:
            checks.append(
                LaunchReadinessCheck(
                    key="runtime.app_env",
                    category="runtime",
                    status="warning",
                    title="Application environment is still development",
                    message=f"APP_ENV is '{self._settings.app_env}', which is acceptable for local rollout but not ideal for formal launch tracking.",
                    action_hint="Promote APP_ENV to a deployment-specific value such as staging or production before formal rollout.",
                )
            )
        else:
            checks.append(
                LaunchReadinessCheck(
                    key="runtime.app_env",
                    category="runtime",
                    status="pass",
                    title="Application environment labeled for deployment",
                    message=f"APP_ENV is '{self._settings.app_env}'.",
                )
            )
        return checks

    def _assess_database(self) -> list[LaunchReadinessCheck]:
        checks: list[LaunchReadinessCheck] = []
        checks.append(
            self._check_non_empty(
                key="database.url",
                category="database",
                title="DATABASE_URL configured",
                value=self._settings.database_url,
                message="Primary database connection string is present.",
                blocker_message="DATABASE_URL is missing.",
            )
        )
        checks.append(
            self._check_non_empty(
                key="database.redis_url",
                category="database",
                title="REDIS_URL configured",
                value=self._settings.redis_url,
                message="Primary Redis connection string is present.",
                blocker_message="REDIS_URL is missing.",
            )
        )
        return checks

    def _assess_queue(self) -> list[LaunchReadinessCheck]:
        queue_backend = "memory" if self._settings.test_mode else self._settings.queue_provider
        checks: list[LaunchReadinessCheck] = [
            LaunchReadinessCheck(
                key="queue.backend",
                category="queue",
                status="pass" if queue_backend in {"redis", "memory"} else "blocker",
                title="Queue backend selected",
                message=f"Queue backend is '{queue_backend}'.",
                action_hint=None if queue_backend in {"redis", "memory"} else "Use a supported queue backend.",
            )
        ]
        if queue_backend == "redis":
            checks.append(
                self._check_non_empty(
                    key="queue.redis_url",
                    category="queue",
                    title="QUEUE_REDIS_URL configured",
                    value=self._settings.queue_redis_url,
                    message="Queue Redis connection string is present.",
                    blocker_message="QUEUE_REDIS_URL is missing while QUEUE_PROVIDER=redis.",
                )
            )
        else:
            checks.append(
                LaunchReadinessCheck(
                    key="queue.runtime_mode",
                    category="queue",
                    status="warning" if queue_backend == "memory" else "pass",
                    title="Queue runtime mode",
                    message="Queue is using in-memory mode." if queue_backend == "memory" else "Queue runtime mode is explicit.",
                    action_hint="Use Redis queue backend outside test mode." if queue_backend == "memory" else None,
                )
            )
        return checks

    def _assess_provider_status_buffer(
        self,
        pending_counts_by_account: dict[str, int],
        replayed_counts_by_account: dict[str, int],
        oldest_pending_events: list[object],
        live_launch_mode: bool,
    ) -> list[LaunchReadinessCheck]:
        pending_total = sum(pending_counts_by_account.values())
        replayed_total = sum(replayed_counts_by_account.values())
        pending_accounts_ranked = [
            {"account_id": account_id, "pending_count": pending_count}
            for account_id, pending_count in sorted(
                pending_counts_by_account.items(),
                key=lambda item: (-item[1], item[0]),
            )
        ]
        metadata = {
            "pending_count": pending_total,
            "pending_by_account": dict(sorted(pending_counts_by_account.items())),
            "pending_account_count": len(pending_counts_by_account),
            "pending_accounts_ranked": pending_accounts_ranked,
            "replayed_count": replayed_total,
            "replayed_by_account": dict(sorted(replayed_counts_by_account.items())),
            "oldest_pending_event": self._serialize_oldest_pending_provider_status_buffer_event(
                oldest_pending_events[0] if oldest_pending_events else None
            ),
        }
        if pending_total == 0:
            return [
                LaunchReadinessCheck(
                    key="messaging.provider_status_buffer",
                    category="messaging",
                    status="pass",
                    title="Provider status buffer is clear",
                    message="No unmatched provider status callbacks are pending replay.",
                    metadata=metadata,
                )
            ]

        return [
            LaunchReadinessCheck(
                key="messaging.provider_status_buffer",
                category="messaging",
                status="blocker" if live_launch_mode else "warning",
                title="Provider status callbacks are pending replay",
                message=(
                    f"{pending_total} provider status callback(s) are waiting for "
                    "matching local messages or template send logs."
                ),
                action_hint=(
                    "Investigate pending ProviderStatusEventBuffer rows; confirm outbound sends "
                    "are creating provider message IDs and replay is running."
                ),
                metadata={
                    **metadata,
                },
            )
        ]

    def _serialize_oldest_pending_provider_status_buffer_event(
        self,
        event: object | None,
    ) -> dict[str, object] | None:
        if event is None:
            return None
        resolved_waba_id = getattr(event, "waba_id", None)
        resolved_phone_number_id = getattr(event, "phone_number_id", None)
        if hasattr(event, "provider_message_id"):
            resolved_waba_id, resolved_phone_number_id = (
                self._runtime_state.resolve_provider_status_buffer_scope(event)
            )
        first_seen_at = self._normalize_timestamp(getattr(event, "first_seen_at", None))
        last_seen_at = self._normalize_timestamp(getattr(event, "last_seen_at", None))
        pending_age_seconds = None
        if first_seen_at is not None:
            pending_age_seconds = max(
                int((datetime.now(UTC).replace(tzinfo=None) - first_seen_at).total_seconds()),
                0,
            )
        return {
            "account_id": getattr(event, "account_id", None),
            "provider_name": getattr(event, "provider_name", None),
            "waba_id": resolved_waba_id,
            "phone_number_id": resolved_phone_number_id,
            "provider_message_id": getattr(event, "provider_message_id", None),
            "external_status": getattr(event, "external_status", None),
            "first_seen_at": first_seen_at.isoformat() if isinstance(first_seen_at, datetime) else None,
            "last_seen_at": last_seen_at.isoformat() if isinstance(last_seen_at, datetime) else None,
            "seen_count": getattr(event, "seen_count", None),
            "pending_age_seconds": pending_age_seconds,
        }

    def _normalize_timestamp(self, value: object) -> datetime | None:
        if not isinstance(value, datetime):
            return None
        if value.tzinfo is None:
            return value
        return value.astimezone(UTC).replace(tzinfo=None)

    def _assess_ai(self) -> list[LaunchReadinessCheck]:
        provider = self._settings.ai_provider.lower()
        checks: list[LaunchReadinessCheck] = []
        if provider == "openai":
            checks.append(
                self._check_non_empty(
                    key="ai.openai_key",
                    category="ai",
                    title="OpenAI API key configured",
                    value=self._settings.openai_api_key,
                    message="OpenAI provider is selected and API key is present.",
                    blocker_message="AI_PROVIDER=openai but OPENAI_API_KEY is missing.",
                )
            )
        elif provider == "deepseek":
            checks.append(
                self._check_non_empty(
                    key="ai.deepseek_key",
                    category="ai",
                    title="DeepSeek API key configured",
                    value=self._settings.deepseek_api_key,
                    message="DeepSeek provider is selected and API key is present.",
                    blocker_message="AI_PROVIDER=deepseek but DEEPSEEK_API_KEY is missing.",
                )
            )
        else:
            checks.append(
                LaunchReadinessCheck(
                    key="ai.provider_mode",
                    category="ai",
                    status="warning",
                    title="AI provider is non-standard for launch",
                    message=f"AI provider is '{self._settings.ai_provider}'.",
                    action_hint="Use OpenAI or DeepSeek for the current planned launch path.",
                )
            )

        translation_provider = self._settings.resolve_translation_provider_name()
        if translation_provider == "disabled":
            checks.append(
                LaunchReadinessCheck(
                    key="ai.translation_provider",
                    category="ai",
                    status="pass",
                    title="Translation assist provider",
                    message="Translation assist is disabled by configuration; primary message and AI flows remain unaffected.",
                    action_hint="Enable translation only if operator-side view translation or outbound operator translation is required.",
                )
            )
            return checks
        if translation_provider in {"openai", "deepseek"}:
            has_key = (
                bool(self._settings.openai_api_key)
                if translation_provider == "openai"
                else bool(self._settings.deepseek_api_key)
            )
            checks.append(
                LaunchReadinessCheck(
                    key="ai.translation_provider",
                    category="ai",
                    status="pass" if has_key else "warning",
                    title="Translation assist provider",
                    message=f"Translation provider is '{translation_provider}'.",
                    action_hint=(
                        None
                        if has_key
                        else "Provide the matching provider key or switch TRANSLATION_PROVIDER to fallback."
                    ),
                )
            )
        else:
            checks.append(
                LaunchReadinessCheck(
                    key="ai.translation_provider",
                    category="ai",
                    status="pass",
                    title="Translation assist provider",
                    message=f"Translation provider is '{translation_provider}'.",
                )
            )
        return checks

    def _assess_messaging(
        self,
        meta_accounts: list[MetaWabaAccount],
        *,
        formal_ready_account_count: int,
    ) -> list[LaunchReadinessCheck]:
        provider = self._settings.messaging_provider.lower()
        checks: list[LaunchReadinessCheck] = []
        if provider == "mock":
            checks.append(
                LaunchReadinessCheck(
                    key="messaging.provider_mode",
                    category="messaging",
                    status="warning",
                    title="Messaging provider is still mock",
                    message="Outbound and inbound traffic still run in mock mode, which is fine for local integration but not for formal WhatsApp launch.",
                    action_hint="Switch MESSAGING_PROVIDER to whatsapp after Meta configuration and readiness checks are complete.",
                )
            )
        elif provider == "whatsapp":
            status = "pass" if formal_ready_account_count > 0 else "blocker"
            checks.append(
                LaunchReadinessCheck(
                    key="messaging.provider_mode",
                    category="messaging",
                    status=status,
                    title="WhatsApp provider selected",
                    message="At least one Meta account is ready for formal activation."
                    if status == "pass"
                    else "MESSAGING_PROVIDER=whatsapp but no Meta account is fully ready for formal activation.",
                    action_hint=(
                        None
                        if status == "pass"
                        else "Complete webhook and outbound readiness, then resolve any root webhook routing conflicts for at least one active WABA."
                    ),
                )
            )
        else:
            checks.append(
                LaunchReadinessCheck(
                    key="messaging.provider_mode",
                    category="messaging",
                    status="blocker",
                    title="Messaging provider unsupported",
                    message=f"MESSAGING_PROVIDER is '{self._settings.messaging_provider}'.",
                    action_hint="Use a supported messaging provider.",
                )
            )
        return checks

    def _assess_meta_accounts(
        self,
        meta_accounts: list[MetaWabaAccount],
        *,
        globally_blocked_scope_keys: set[tuple[str, str]],
        live_launch_mode: bool,
    ) -> list[LaunchReadinessCheck]:
        checks: list[LaunchReadinessCheck] = []
        if not meta_accounts:
            checks.append(
                LaunchReadinessCheck(
                    key="meta.accounts_present",
                    category="meta",
                    status="warning" if self._settings.messaging_provider.lower() == "mock" else "blocker",
                    title="No Meta accounts registered",
                    message="There are no WABA records in the system yet.",
                    action_hint="Add at least one WhatsApp Business Account in the Meta admin page.",
                )
            )
            return checks

        checks.append(
            LaunchReadinessCheck(
                key="meta.accounts_present",
                category="meta",
                status="pass",
                title="Meta accounts registered",
                message=f"{len(meta_accounts)} WABA account(s) are present in the system.",
            )
        )
        for account in meta_accounts:
            scope_key = (account.account_id, account.waba_id)
            has_global_root_webhook_conflict = scope_key in globally_blocked_scope_keys
            scope_ready_for_formal_activation = (
                account.ready_for_meta_activation and not has_global_root_webhook_conflict
            )
            missing_parts: list[str] = []
            if not account.ready_for_webhook_delivery:
                missing_parts.append("webhook delivery")
            if not account.ready_for_outbound_messages:
                missing_parts.append("outbound messaging")
            if has_global_root_webhook_conflict:
                missing_parts.append("root webhook routing consistency")
            checks.append(
                LaunchReadinessCheck(
                    key=f"meta.account.{account.account_id}.{account.waba_id}",
                    category="meta",
                    status=(
                        "pass"
                        if scope_ready_for_formal_activation
                        else "blocker"
                        if has_global_root_webhook_conflict and live_launch_mode
                        else "warning"
                    ),
                    scope="account",
                    account_id=account.account_id,
                    waba_id=account.waba_id,
                    title=f"WABA readiness for {account.display_name}",
                    message=(
                        f"WABA {account.waba_id} is ready for formal activation."
                        if scope_ready_for_formal_activation
                        else (
                            f"WABA {account.waba_id} meets local webhook and outbound prerequisites, "
                            "but root webhook routing conflicts still block formal activation."
                        )
                        if has_global_root_webhook_conflict
                        else f"WABA {account.waba_id} still lacks {', '.join(missing_parts)}."
                    ),
                    action_hint=(
                        None
                        if scope_ready_for_formal_activation
                        else (
                            "Resolve root webhook verify-token or app-secret conflicts before formal Meta rollout."
                        )
                        if has_global_root_webhook_conflict
                        else "Use the Meta accounts page to complete webhook subscription, verify token/app secret, and registered phone numbers."
                    ),
                    metadata={
                        "account_is_active": account.account_is_active,
                        "waba_is_active": account.is_active,
                        "onboarding_mode": account.onboarding_mode,
                        "token_source": account.token_source,
                        "has_access_token": account.has_access_token,
                        "has_verify_token": account.has_verify_token,
                        "has_app_secret": account.has_app_secret,
                        "ready_for_webhook_delivery": account.ready_for_webhook_delivery,
                        "ready_for_outbound_messages": account.ready_for_outbound_messages,
                        "ready_for_meta_activation": account.ready_for_meta_activation,
                        "scope_ready_for_formal_activation": scope_ready_for_formal_activation,
                        "has_root_webhook_routing_conflict": has_global_root_webhook_conflict,
                        "registered_phone_number_count": account.registered_phone_number_count,
                        "phone_number_count": account.phone_number_count,
                        "webhook_callback_url": account.webhook_callback_url,
                        "webhook_root_verify_path": account.webhook_root_verify_path,
                        "webhook_verify_path": account.webhook_verify_path,
                        "webhook_receive_path": account.webhook_receive_path,
                        "webhook_root_receive_path": account.webhook_root_receive_path,
                        "webhook_subscribed": account.webhook_subscribed,
                        "webhook_subscription_status": account.webhook_subscription_status,
                        "webhook_verification_status": account.webhook_verification_status,
                        "webhook_runtime_status": account.webhook_runtime_status,
                        "webhook_signature_failure_count": account.webhook_signature_failure_count,
                        "blocking_reasons": list(account.blocking_reasons),
                    },
                )
            )
            checks.extend(
                self._build_webhook_runtime_checks(
                    account=account,
                    live_launch_mode=live_launch_mode,
                )
            )
        return checks

    def _assess_meta_management(self) -> list[LaunchReadinessCheck]:
        provider_name = (
            self._settings.meta_management_provider.lower()
            if self._settings.meta_management_provider
            else self._settings.messaging_provider.lower()
        )
        messaging_provider = self._settings.messaging_provider.lower()
        if messaging_provider == "whatsapp" and provider_name != "whatsapp":
            return [
                LaunchReadinessCheck(
                    key="meta.management_provider",
                    category="meta",
                    status="blocker",
                    title="Meta management provider is not aligned with WhatsApp mode",
                    message=(
                        "MESSAGING_PROVIDER=whatsapp but META_MANAGEMENT_PROVIDER resolves to "
                        f"'{provider_name}'."
                    ),
                    action_hint="Set META_MANAGEMENT_PROVIDER=whatsapp or clear it to follow MESSAGING_PROVIDER.",
                )
            ]
        return [
            LaunchReadinessCheck(
                key="meta.management_provider",
                category="meta",
                status="pass" if provider_name == "whatsapp" else "warning",
                title="Meta management provider selected",
                message=f"Meta management provider is '{provider_name}'.",
                action_hint=(
                    None
                    if provider_name == "whatsapp"
                    else "Switch META_MANAGEMENT_PROVIDER to whatsapp before formal Meta rollout."
                ),
            )
        ]

    def _assess_monitoring_assets(self) -> list[LaunchReadinessCheck]:
        root = Path.cwd()
        files = [
            ("monitoring.prometheus_config", root / "monitoring" / "prometheus" / "prometheus.yml", "Prometheus scrape config"),
            ("monitoring.alert_rules", root / "monitoring" / "prometheus" / "alerts.yml", "Prometheus alert rules"),
            ("monitoring.alertmanager_config", root / "monitoring" / "alertmanager" / "alertmanager.yml", "Alertmanager config"),
            ("monitoring.grafana_dashboard", root / "monitoring" / "grafana" / "dashboards" / "whatsapp-platform-overview.json", "Grafana dashboard"),
        ]
        return [
            LaunchReadinessCheck(
                key=key,
                category="monitoring",
                status="pass" if path.exists() else "warning",
                title=f"{label} present",
                message=f"{path.name} is available." if path.exists() else f"{path.name} is missing from the workspace.",
                action_hint=None if path.exists() else f"Restore or add {path.name}.",
            )
            for key, path, label in files
        ]

    def _assess_operations_assets(self) -> list[LaunchReadinessCheck]:
        root = Path.cwd()
        files = [
            ("operations.deployment_checklist", root / "docs" / "deployment-checklist.md", "Deployment checklist"),
            ("operations.recovery_runbook", root / "docs" / "recovery-runbook.md", "Recovery runbook"),
            ("operations.backup_script", root / "scripts" / "backup-postgres.ps1", "PostgreSQL backup script"),
            ("operations.restore_script", root / "scripts" / "restore-postgres.ps1", "PostgreSQL restore script"),
            ("operations.launch_readiness_script", root / "scripts" / "check-launch-readiness.ps1", "Launch readiness script"),
            ("operations.verify_script", root / "scripts" / "verify-ci.ps1", "Verification script"),
        ]
        return [
            LaunchReadinessCheck(
                key=key,
                category="operations",
                status="pass" if path.exists() else "warning",
                title=f"{label} present",
                message=f"{path.name} is available." if path.exists() else f"{path.name} is missing from the workspace.",
                action_hint=None if path.exists() else f"Restore or add {path.name}.",
            )
            for key, path, label in files
        ]

    def _build_webhook_runtime_checks(
        self,
        *,
        account: MetaWabaAccount,
        live_launch_mode: bool,
    ) -> list[LaunchReadinessCheck]:
        checks: list[LaunchReadinessCheck] = []
        account_scope = {
            "scope": "account",
            "account_id": account.account_id,
            "waba_id": account.waba_id,
        }

        verification_status = account.webhook_verification_status or "pending"
        verification_check_status = self._webhook_check_status(
            current_status=verification_status,
            success_statuses={"verified"},
            live_launch_mode=live_launch_mode,
        )
        checks.append(
            LaunchReadinessCheck(
                key=f"meta.account.{account.account_id}.{account.waba_id}.webhook_verification",
                category="meta",
                status=verification_check_status,
                title=f"Webhook verification for {account.display_name}",
                message=self._build_webhook_verification_message(account),
                action_hint=(
                    None
                    if verification_check_status == "pass"
                    else "Run the Meta webhook verify challenge for this WABA and confirm the verify token matches."
                ),
                metadata={
                    "webhook_verification_status": verification_status,
                    "webhook_last_verified_at": account.webhook_last_verified_at,
                    "webhook_last_verification_error": account.webhook_last_verification_error,
                    "webhook_callback_url": account.webhook_callback_url,
                    "webhook_root_verify_path": account.webhook_root_verify_path,
                    "webhook_verify_path": account.webhook_verify_path,
                    "webhook_root_receive_path": account.webhook_root_receive_path,
                },
                **account_scope,
            )
        )

        runtime_status = account.webhook_runtime_status or "pending"
        runtime_check_status = self._webhook_runtime_check_status(
            account=account,
            live_launch_mode=live_launch_mode,
        )
        checks.append(
            LaunchReadinessCheck(
                key=f"meta.account.{account.account_id}.{account.waba_id}.webhook_runtime",
                category="meta",
                status=runtime_check_status,
                title=f"Webhook runtime health for {account.display_name}",
                message=self._build_webhook_runtime_message(account),
                action_hint=(
                    None
                    if runtime_check_status == "pass"
                    else "Send or receive a signed webhook event for this WABA and clear signature or payload mismatches before formal launch."
                ),
                metadata={
                    "webhook_runtime_status": runtime_status,
                    "webhook_last_event_received_at": account.webhook_last_event_received_at,
                    "webhook_last_message_received_at": account.webhook_last_message_received_at,
                    "webhook_last_status_update_at": account.webhook_last_status_update_at,
                    "webhook_last_management_event_at": account.webhook_last_management_event_at,
                    "webhook_last_signature_failed_at": account.webhook_last_signature_failed_at,
                    "webhook_signature_failure_count": account.webhook_signature_failure_count,
                    "webhook_runtime_error": account.webhook_runtime_error,
                    "webhook_callback_url": account.webhook_callback_url,
                    "webhook_root_verify_path": account.webhook_root_verify_path,
                    "webhook_receive_path": account.webhook_receive_path,
                    "webhook_root_receive_path": account.webhook_root_receive_path,
                },
                **account_scope,
            )
        )
        return checks

    @staticmethod
    def _assess_webhook_verify_token_routing(
        *,
        conflicts: list[WebhookVerifyTokenConflict],
        live_launch_mode: bool,
    ) -> list[LaunchReadinessCheck]:
        if not conflicts:
            return [
                LaunchReadinessCheck(
                    key="meta.webhook_verify_token_routing",
                    category="meta",
                    status="pass",
                    title="Root webhook verify routing is unambiguous",
                    message="Every configured WABA has a unique verify-token mapping for the root webhook verify endpoint.",
                )
            ]

        hidden_scope_count = sum(conflict.hidden_scope_count for conflict in conflicts)
        return [
            LaunchReadinessCheck(
                key="meta.webhook_verify_token_routing",
                category="meta",
                status="blocker" if live_launch_mode else "warning",
                title="Root webhook verify routing is ambiguous",
                message=(
                    f"{len(conflicts)} verify-token collision set(s) would prevent "
                    "GET /webhooks/whatsapp from resolving a single WABA during Meta webhook verification."
                    + (
                        f" {hidden_scope_count} conflicting scope(s) are outside the current account visibility."
                        if hidden_scope_count > 0
                        else ""
                    )
                ),
                action_hint=(
                    "Assign unique verify tokens per WABA or use the scoped verify path for subscription verification."
                ),
                metadata={
                    "conflict_count": len(conflicts),
                    "hidden_scope_count": hidden_scope_count,
                    "conflicts": [
                        {
                            "verify_token_hint": conflict.verify_token_hint,
                            "hidden_scope_count": conflict.hidden_scope_count,
                            "scopes": [
                                {"account_id": account_id, "waba_id": waba_id}
                                for account_id, waba_id in conflict.scopes
                            ],
                        }
                        for conflict in conflicts
                    ],
                },
            )
        ]

    def _assess_webhook_root_receive_signature_routing(
        self,
        *,
        conflicts: list[dict[str, object]],
        live_launch_mode: bool,
    ) -> list[LaunchReadinessCheck]:
        if not conflicts:
            return [
                LaunchReadinessCheck(
                    key="meta.webhook_root_receive_signature_routing",
                    category="meta",
                    status="pass",
                    title="Root webhook receive signature routing is unambiguous",
                    message=(
                        "Every configured root webhook callback target maps to at most one app "
                        "secret, so POST /webhooks/whatsapp can validate signed WABA deliveries "
                        "without cross-scope ambiguity."
                    ),
                )
            ]

        hidden_scope_count = sum(
            int(conflict["hidden_scope_count"])
            for conflict in conflicts
        )
        return [
            LaunchReadinessCheck(
                key="meta.webhook_root_receive_signature_routing",
                category="meta",
                status="blocker" if live_launch_mode else "warning",
                title="Root webhook receive signature routing is ambiguous",
                message=(
                    f"{len(conflicts)} root webhook callback target(s) map visible WABA scope(s) "
                    "to multiple app secrets, so POST /webhooks/whatsapp cannot validate mixed "
                    "WABA deliveries deterministically."
                    + (
                        f" {hidden_scope_count} conflicting scope(s) are outside the current "
                        "account visibility."
                        if hidden_scope_count > 0
                        else ""
                    )
                ),
                action_hint=(
                    "Use one shared app secret for WABAs that share the root callback URL, or "
                    "move those subscriptions to scoped receive paths before formal launch."
                ),
                metadata={
                    "conflict_count": len(conflicts),
                    "hidden_scope_count": hidden_scope_count,
                    "conflicts": conflicts,
                },
            )
        ]

    async def _collect_root_receive_signature_conflicts(
        self,
        *,
        visible_scope_keys: set[tuple[str, str]],
        all_accounts: list[MetaWabaAccount],
    ) -> list[dict[str, object]]:
        grouped_scopes: dict[str, list[dict[str, str]]] = {}
        for account in all_accounts:
            callback_target = self._normalize_root_webhook_callback_target(account)
            if callback_target is None or not account.has_app_secret:
                continue
            auth_context = await self._meta_account_registry.get_webhook_auth_context(
                account.account_id,
                account.waba_id,
            )
            if not auth_context.app_secret:
                continue
            grouped_scopes.setdefault(callback_target, []).append(
                {
                    "account_id": account.account_id,
                    "waba_id": account.waba_id,
                    "app_secret": auth_context.app_secret,
                }
            )

        conflicts: list[dict[str, object]] = []
        for callback_target, scopes in grouped_scopes.items():
            distinct_secrets = {
                scope["app_secret"]
                for scope in scopes
                if scope["app_secret"].strip()
            }
            if len(distinct_secrets) <= 1:
                continue

            visible_scopes = [
                {
                    "account_id": scope["account_id"],
                    "waba_id": scope["waba_id"],
                }
                for scope in scopes
                if (scope["account_id"], scope["waba_id"]) in visible_scope_keys
            ]
            if not visible_scopes:
                continue

            conflicts.append(
                {
                    "callback_target": callback_target,
                    "distinct_app_secret_count": len(distinct_secrets),
                    "hidden_scope_count": len(scopes) - len(visible_scopes),
                    "scopes": visible_scopes,
                }
            )

        return conflicts

    @staticmethod
    def _collect_globally_blocked_waba_scope_keys(
        *,
        verify_token_conflicts: list[WebhookVerifyTokenConflict],
        root_receive_signature_conflicts: list[dict[str, object]],
    ) -> set[tuple[str, str]]:
        blocked_scope_keys: set[tuple[str, str]] = set()
        for conflict in verify_token_conflicts:
            blocked_scope_keys.update(conflict.scopes)
        for conflict in root_receive_signature_conflicts:
            for scope in conflict.get("scopes", []):
                account_id = scope.get("account_id")
                waba_id = scope.get("waba_id")
                if isinstance(account_id, str) and isinstance(waba_id, str):
                    blocked_scope_keys.add((account_id, waba_id))
        return blocked_scope_keys

    @staticmethod
    def _normalize_root_webhook_callback_target(account: MetaWabaAccount) -> str | None:
        if not account.webhook_callback_url:
            return None

        callback_url = account.webhook_callback_url.strip()
        if not callback_url:
            return None

        parsed_callback = urlsplit(callback_url)
        callback_path = LaunchReadinessService._normalize_webhook_path(
            parsed_callback.path or callback_url,
        )
        root_receive_path = LaunchReadinessService._normalize_webhook_path(
            account.webhook_root_receive_path,
        )
        if callback_path != root_receive_path:
            return None

        if parsed_callback.scheme or parsed_callback.netloc:
            return f"{parsed_callback.scheme}://{parsed_callback.netloc}{callback_path}"
        return callback_path

    @staticmethod
    def _normalize_webhook_path(path: str) -> str:
        normalized_path = path.strip()
        if not normalized_path:
            return "/"
        if not normalized_path.startswith("/"):
            normalized_path = f"/{normalized_path}"
        if len(normalized_path) > 1:
            normalized_path = normalized_path.rstrip("/")
        return normalized_path

    @staticmethod
    def _webhook_check_status(
        *,
        current_status: str,
        success_statuses: set[str],
        live_launch_mode: bool,
    ) -> str:
        if current_status in success_statuses:
            return "pass"
        return "blocker" if live_launch_mode else "warning"

    @staticmethod
    def _webhook_runtime_check_status(
        *,
        account: MetaWabaAccount,
        live_launch_mode: bool,
    ) -> str:
        runtime_status = account.webhook_runtime_status or "pending"
        if runtime_status != "healthy":
            return "blocker" if live_launch_mode else "warning"
        if account.webhook_last_event_received_at is None:
            return "blocker" if live_launch_mode else "warning"
        return "pass"

    @staticmethod
    def _build_webhook_verification_message(account: MetaWabaAccount) -> str:
        status = account.webhook_verification_status or "pending"
        if status == "verified":
            return (
                "Webhook verify challenge succeeded"
                if account.webhook_last_verified_at is None
                else f"Webhook verify challenge succeeded at {account.webhook_last_verified_at}."
            )
        if status == "failed":
            return (
                "Webhook verification failed."
                if not account.webhook_last_verification_error
                else f"Webhook verification failed: {account.webhook_last_verification_error}."
            )
        if status == "unavailable":
            return "Webhook verification is unavailable because the verify token is missing."
        return "Webhook verification has not completed yet for this WABA."

    @staticmethod
    def _build_webhook_runtime_message(account: MetaWabaAccount) -> str:
        status = account.webhook_runtime_status or "pending"
        if status == "healthy":
            if (
                account.webhook_last_message_received_at is None
                and account.webhook_last_status_update_at is None
                and account.webhook_last_management_event_at is None
            ):
                return (
                    "A signed webhook event was received, but no in-scope message, status, or management update was accepted yet."
                )
            suffix = (
                ""
                if account.webhook_signature_failure_count <= 0
                else f" Historical signature failures: {account.webhook_signature_failure_count}."
            )
            return (
                "Signed webhook events have been received successfully."
                if account.webhook_last_event_received_at is None
                else f"Signed webhook events were last processed at {account.webhook_last_event_received_at}.{suffix}"
            )
        if status == "signature_failed":
            return (
                "Webhook signature validation failed."
                if not account.webhook_runtime_error
                else f"Webhook signature validation failed: {account.webhook_runtime_error}."
            )
        if status == "signature_unavailable":
            if account.webhook_runtime_error == "missing_app_secret":
                return "Webhook delivery is still blocked because the app secret is missing."
            return "Webhook delivery is still blocked because signature verification is unavailable."
        if status == "payload_invalid":
            return (
                "Webhook payload validation failed."
                if not account.webhook_runtime_error
                else f"Webhook payload validation failed: {account.webhook_runtime_error}."
            )
        if status == "verification_pending":
            runtime_error = (account.webhook_runtime_error or "").strip()
            if runtime_error.startswith("webhook_verification_"):
                suffix = runtime_error.removeprefix("webhook_verification_")
                if not suffix:
                    return "Webhook delivery is still blocked because verification has not completed yet."
                return (
                    "Webhook delivery is still blocked because verification has not completed yet: "
                    f"{suffix}."
                )
            if runtime_error == "missing_webhook_subscription":
                return "Webhook delivery is still blocked because the WABA webhook subscription is missing."
            if runtime_error == "missing_app_secret":
                return "Webhook delivery is still blocked because the app secret is missing."
            if runtime_error == "missing_registered_phone_numbers":
                return "Webhook delivery is still blocked because no registered phone number is linked to this WABA."
            if runtime_error == "missing_phone_numbers":
                return "Webhook delivery is still blocked because no phone number is linked to this WABA."
            if runtime_error == "webhook_not_ready":
                return "Webhook delivery is still blocked because the WABA webhook setup is not fully ready."
            return (
                "Webhook delivery is still blocked by launch prerequisites."
                if not runtime_error
                else f"Webhook delivery is still blocked by launch prerequisites: {runtime_error}."
            )
        return "Webhook runtime health is still pending because no valid signed event has been processed yet."

    @staticmethod
    def _check_non_empty(
        *,
        key: str,
        category: str,
        title: str,
        value: str | None,
        message: str,
        blocker_message: str,
    ) -> LaunchReadinessCheck:
        if value and str(value).strip():
            return LaunchReadinessCheck(
                key=key,
                category=category,
                status="pass",
                title=title,
                message=message,
            )
        return LaunchReadinessCheck(
            key=key,
            category=category,
            status="blocker",
            title=title,
            message=blocker_message,
        )
