import re
from datetime import date, datetime, time
from typing import cast

from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.metrics import (
    business_outbound_messages_total,
    business_template_send_failures_total,
    business_template_sends_total,
    message_processing_failures_total,
)
from app.db.models import (
    Conversation,
    MediaAsset,
    MediaAssetEvent,
    Message,
    MessageTemplate,
    TemplateDailyStat,
    TemplateFailureStat,
    TemplateHourlyStat,
    TemplateSendLog,
    WhatsAppBusinessAccount,
    WhatsAppPhoneNumber,
    utc_now,
)
from app.providers.messaging.base import MessagingProvider
from app.providers.template_registry.base import TemplateRegistryProvider
from app.schemas.template_registry import (
    TemplateRegistryRemoteTemplate,
    TemplateRegistrySubmitRequest,
)
from app.schemas.templates import (
    MessageTemplateView,
    TemplateCategory,
    TemplateDraftRequest,
    TemplateDraftUpdateRequest,
    TemplateSendStatus,
    TemplateStatsDailyRow,
    TemplateStatsDetailResponse,
    TemplateStatsFailureReason,
    TemplateStatsHourlyRow,
    TemplateSendLogView,
    TemplateSendRequest,
    TemplateSendResponse,
    TemplateStatsSummary,
    TemplateSubmitResponse,
    TemplateStatus,
    TemplateSyncRequest,
    TemplateSyncResponse,
    TemplateStatusUpdateRequest,
)
from app.services.messaging_dispatch import build_outbound_dispatch_request
from app.services.meta_scope_validation import MetaScopeValidator
from app.services.media_asset_errors import MediaProviderConfigError, MediaProviderUpstreamError
from app.services.media_asset_sync_service import MediaAssetSyncService, PreparedMediaAssetReference
from app.services.runtime_state import RuntimeStateStore
from app.services.template_stats_aggregator import TemplateStatsAggregator
from app.services.translation_service import TranslationService

PLACEHOLDER_PATTERN = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")


class TemplateService:
    def __init__(
        self,
        session: Session,
        runtime_state: RuntimeStateStore,
        translation_service: TranslationService,
        messaging_provider: MessagingProvider,
        template_registry_provider: TemplateRegistryProvider,
    ) -> None:
        self._session = session
        self._runtime_state = runtime_state
        self._translation_service = translation_service
        self._messaging_provider = messaging_provider
        self._template_registry_provider = template_registry_provider
        self._media_asset_sync_service = MediaAssetSyncService(
            session=session,
            runtime_state=runtime_state,
            messaging_provider=messaging_provider,
        )
        self._meta_scope_validator = MetaScopeValidator(session)
        self._template_stats_aggregator = TemplateStatsAggregator(session=session)

    async def list_templates(
        self,
        account_id: str | None = None,
        waba_id: str | None = None,
        status: TemplateStatus | None = None,
        language: str | None = None,
        agency_id: str | None = None,
    ) -> list[MessageTemplateView]:
        query = (
            select(MessageTemplate)
            .options(selectinload(MessageTemplate.waba_account))
            .order_by(MessageTemplate.created_at.desc(), MessageTemplate.name.asc())
        )
        if account_id is not None:
            query = query.where(MessageTemplate.account_id == account_id)
        if waba_id is not None:
            query = query.where(self._template_waba_match_clause(waba_id))
        if status is not None:
            query = query.where(MessageTemplate.status == status)
        if language is not None:
            query = query.where(MessageTemplate.language == language)
        if agency_id is not None:
            query = query.where(
                (MessageTemplate.agency_id == agency_id) | (MessageTemplate.agency_id.is_(None))
            )

        templates = self._session.scalars(query).all()
        return [self._serialize_template(template) for template in templates]

    async def create_template_draft(
        self,
        payload: TemplateDraftRequest,
        actor_type: str = "system",
        actor_id: str | None = None,
    ) -> MessageTemplateView:
        if self._runtime_state.get_account_model(payload.account_id) is None:
            raise LookupError(f"Account '{payload.account_id}' was not found.")
        waba_account = self._require_waba_for_account(
            account_id=payload.account_id,
            waba_id=payload.waba_id,
        )
        components, header_media_asset = self._build_template_components_for_draft(
            account_id=payload.account_id,
            waba_id=payload.waba_id,
            body_text=payload.body_text,
            header_text=payload.header_text,
            header_media_asset_id=payload.header_media_asset_id,
            header_media_handle=payload.header_media_handle,
            footer_text=payload.footer_text,
            sample_variables=payload.sample_variables,
        )
        template = MessageTemplate(
            account_id=payload.account_id,
            waba_account_id=waba_account.id if waba_account is not None else None,
            waba_id=waba_account.waba_id if waba_account is not None else None,
            name=payload.name,
            language=payload.language,
            category=payload.category,
            status="DRAFT",
            components=components,
        )
        self._session.add(template)
        self._runtime_state.add_audit_log(
            account_id=payload.account_id,
            actor_type=actor_type,
            actor_id=actor_id,
            action="template_draft_created",
            target_type="message_template",
            target_id=payload.name,
            payload={
                "waba_id": payload.waba_id,
                "language": payload.language,
                "category": payload.category,
                "header_media_asset_id": (
                    header_media_asset.id if header_media_asset is not None else None
                ),
                "header_media_asset_type": (
                    header_media_asset.asset_type if header_media_asset is not None else None
                ),
            },
        )
        self._session.commit()
        self._session.refresh(template)
        return self._serialize_template(template)

    async def update_template_draft(
        self,
        template_id: str,
        payload: TemplateDraftUpdateRequest,
        allowed_account_ids: set[str] | None = None,
        actor_type: str = "system",
        actor_id: str | None = None,
    ) -> MessageTemplateView:
        template = self._require_template(template_id)
        self._ensure_template_account_allowed(
            template=template,
            allowed_account_ids=allowed_account_ids,
        )
        if template.status != "DRAFT":
            raise ValueError(
                f"Template '{template.id}' is in status '{template.status}' and can no longer be edited as a draft."
            )

        components = template.components or {}
        next_waba_id = (
            payload.waba_id
            if "waba_id" in payload.model_fields_set
            else self._resolve_template_waba_id(template)
        )
        next_name = payload.name if "name" in payload.model_fields_set else template.name
        next_language = (
            payload.language if "language" in payload.model_fields_set else template.language
        )
        next_category = (
            payload.category if "category" in payload.model_fields_set else template.category
        )
        next_body_text = (
            payload.body_text
            if "body_text" in payload.model_fields_set
            else str(components.get("body_text") or "")
        )
        next_header_text = (
            payload.header_text
            if "header_text" in payload.model_fields_set
            else str(components.get("header_text"))
            if components.get("header_text") is not None
            else None
        )
        next_header_media_asset_id = (
            payload.header_media_asset_id
            if "header_media_asset_id" in payload.model_fields_set
            else str(components.get("header_media_asset_id"))
            if components.get("header_media_asset_id") is not None
            else None
        )
        next_header_media_handle = (
            payload.header_media_handle
            if "header_media_handle" in payload.model_fields_set
            else str(components.get("header_media_handle"))
            if components.get("header_media_handle") is not None
            else None
        )
        next_footer_text = (
            payload.footer_text
            if "footer_text" in payload.model_fields_set
            else str(components.get("footer_text"))
            if components.get("footer_text") is not None
            else None
        )
        next_sample_variables = (
            payload.sample_variables
            if "sample_variables" in payload.model_fields_set
            else self._extract_sample_variables(template)
        )
        waba_account = self._require_waba_for_account(
            account_id=template.account_id,
            waba_id=next_waba_id,
        )
        next_components, header_media_asset = self._build_template_components_for_draft(
            account_id=template.account_id,
            waba_id=next_waba_id,
            body_text=next_body_text,
            header_text=next_header_text,
            header_media_asset_id=next_header_media_asset_id,
            header_media_handle=next_header_media_handle,
            footer_text=next_footer_text,
            sample_variables=next_sample_variables,
        )
        template.waba_account_id = waba_account.id if waba_account is not None else None
        template.waba_account = waba_account
        template.waba_id = waba_account.waba_id if waba_account is not None else None
        template.name = next_name
        template.language = next_language
        template.category = next_category
        template.components = next_components
        self._session.add(template)
        self._runtime_state.add_audit_log(
            account_id=template.account_id,
            actor_type=actor_type,
            actor_id=actor_id,
            action="template_draft_updated",
            target_type="message_template",
            target_id=template.id,
            payload={
                "waba_id": next_waba_id,
                "name": next_name,
                "language": next_language,
                "category": next_category,
                "header_media_asset_id": (
                    header_media_asset.id if header_media_asset is not None else None
                ),
                "header_media_asset_type": (
                    header_media_asset.asset_type if header_media_asset is not None else None
                ),
                "updated_fields": sorted(payload.model_fields_set),
            },
        )
        self._session.commit()
        self._session.refresh(template)
        return self._serialize_template(template)

    async def update_template_status(
        self,
        template_id: str,
        payload: TemplateStatusUpdateRequest,
        allowed_account_ids: set[str] | None = None,
        actor_type: str = "system",
        actor_id: str | None = None,
    ) -> MessageTemplateView:
        template = self._require_template(template_id)
        self._ensure_template_account_allowed(template=template, allowed_account_ids=allowed_account_ids)
        template.status = payload.status
        template.rejected_reason = payload.rejected_reason
        if payload.meta_template_id:
            template.meta_template_id = payload.meta_template_id
        self._session.add(template)
        self._runtime_state.add_audit_log(
            account_id=template.account_id,
            actor_type=actor_type,
            actor_id=actor_id,
            action="template_status_updated",
            target_type="message_template",
            target_id=template.id,
            payload={
                "status": payload.status,
                "rejected_reason": payload.rejected_reason,
                "meta_template_id": payload.meta_template_id,
            },
        )
        self._session.commit()
        self._session.refresh(template)
        return self._serialize_template(template)

    async def apply_template_webhook_update(
        self,
        *,
        account_id: str,
        waba_id: str,
        meta_template_id: str | None,
        name: str | None,
        language: str | None,
        status: str | None,
        rejected_reason: str | None,
        quality_score: str | None,
        event_type: str,
        raw_payload: dict[str, object],
    ) -> MessageTemplateView | None:
        template = self._find_template_for_webhook(
            account_id=account_id,
            waba_id=waba_id,
            meta_template_id=meta_template_id,
            name=name,
            language=language,
        )
        if template is None:
            return None

        normalized_status = self._normalize_template_webhook_status(status)
        if normalized_status is not None:
            template.status = normalized_status
            template.rejected_reason = rejected_reason
        elif rejected_reason is not None:
            template.rejected_reason = rejected_reason
        if meta_template_id and not template.meta_template_id:
            template.meta_template_id = meta_template_id
        template.waba_id = waba_id

        provider_payload = dict(template.provider_template_payload or {})
        provider_payload["last_webhook_update"] = {
            "event_type": event_type,
            "status": normalized_status,
            "quality_score": quality_score,
            "raw_payload": raw_payload,
            "received_at": utc_now().isoformat(),
        }
        if quality_score is not None:
            provider_payload["quality_score"] = quality_score
        template.provider_template_payload = provider_payload
        template.last_synced_at = utc_now()

        self._session.add(template)
        self._runtime_state.add_audit_log(
            account_id=template.account_id,
            actor_type="system",
            actor_id=None,
            action=(
                "template_webhook_quality_updated"
                if event_type == "message_template_quality_update"
                else "template_webhook_status_updated"
            ),
            target_type="message_template",
            target_id=template.id,
            payload={
                "waba_id": waba_id,
                "meta_template_id": meta_template_id,
                "name": name,
                "language": language,
                "status": normalized_status,
                "rejected_reason": rejected_reason,
                "quality_score": quality_score,
                "event_type": event_type,
            },
        )
        self._session.commit()
        self._session.refresh(template)
        return self._serialize_template(template)

    async def list_send_logs(
        self,
        account_id: str | None = None,
        waba_id: str | None = None,
        conversation_id: str | None = None,
        external_conversation_id: str | None = None,
        internal_conversation_id: str | None = None,
        template_id: str | None = None,
        phone_number_id: str | None = None,
        status: TemplateSendStatus | None = None,
        error_code: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int = 100,
        allowed_account_ids: set[str] | None = None,
    ) -> list[TemplateSendLogView]:
        if (
            conversation_id is not None
            and external_conversation_id is not None
            and conversation_id != external_conversation_id
        ):
            raise ValueError(
                "conversation_id and external_conversation_id refer to the same external "
                "conversation filter and must match when both are provided."
        )
        resolved_external_conversation_id = external_conversation_id or conversation_id
        start_date, end_date = self._normalize_date_window(date_from=date_from, date_to=date_to)
        self._validate_scope_filters(
            account_id=account_id,
            waba_id=waba_id,
            phone_number_id=phone_number_id,
            allowed_account_ids=allowed_account_ids,
        )
        if template_id is not None:
            template = self._require_template(template_id)
            self._ensure_template_account_allowed(
                template=template,
                allowed_account_ids=allowed_account_ids,
            )
            self._validate_template_route_scope_filters(
                template=template,
                account_id=account_id,
                waba_id=waba_id,
                phone_number_id=phone_number_id,
                allowed_account_ids=allowed_account_ids,
            )
        occurred_at = func.coalesce(TemplateSendLog.sent_at, TemplateSendLog.created_at)
        query = (
            select(TemplateSendLog)
            .options(
                selectinload(TemplateSendLog.template),
                selectinload(TemplateSendLog.conversation),
                selectinload(TemplateSendLog.phone_number),
            )
            .order_by(occurred_at.desc(), TemplateSendLog.id.desc())
        )
        if account_id is not None:
            query = query.where(TemplateSendLog.account_id == account_id)
        elif allowed_account_ids is not None:
            query = query.where(TemplateSendLog.account_id.in_(allowed_account_ids))
        if resolved_external_conversation_id is not None:
            query = query.where(
                TemplateSendLog.conversation.has(
                    external_conversation_id=resolved_external_conversation_id
                )
            )
        if internal_conversation_id is not None:
            query = query.where(TemplateSendLog.conversation_id == internal_conversation_id)
        if template_id is not None:
            query = query.where(TemplateSendLog.template_id == template_id)
        apply_scope_filter_after_load = phone_number_id is not None or waba_id is not None
        if status is not None:
            query = query.where(TemplateSendLog.status == status)
        if error_code is not None:
            query = query.where(TemplateSendLog.error_code == error_code)
        if start_date is not None:
            query = query.where(
                occurred_at >= datetime.combine(start_date, time.min)
            )
        if end_date is not None:
            query = query.where(
                occurred_at <= datetime.combine(end_date, time.max)
            )
        if not apply_scope_filter_after_load:
            query = query.limit(limit)
        logs = self._session.scalars(query).all()
        message_scopes = self._load_send_log_message_scopes(logs)
        if apply_scope_filter_after_load:
            logs = [
                item
                for item in logs
                if self._matches_send_log_scope_filters(
                    log=item,
                    waba_id=waba_id,
                    phone_number_id=phone_number_id,
                    conversation=item.conversation,
                    message_scope=message_scopes.get(item.id),
                )
            ][:limit]
        return [
            self._serialize_send_log(item, message_scope=message_scopes.get(item.id))
            for item in logs
        ]

    def _load_template_daily_rows(
        self,
        *,
        template: MessageTemplate,
        waba_id: str | None,
        phone_number_id: str | None,
        start_date: date | None,
        end_date: date | None,
        allowed_account_ids: set[str] | None,
    ) -> list[TemplateStatsDailyRow]:
        query = select(TemplateDailyStat).where(TemplateDailyStat.template_id == template.id).order_by(
            TemplateDailyStat.date.desc(),
            TemplateDailyStat.template_name.asc(),
        )
        if allowed_account_ids is not None:
            query = query.where(TemplateDailyStat.account_id.in_(allowed_account_ids))
        if waba_id is not None:
            query = query.where(TemplateDailyStat.waba_id == waba_id)
        if phone_number_id is not None:
            query = query.where(TemplateDailyStat.phone_number_id == phone_number_id)
        if start_date is not None:
            query = query.where(TemplateDailyStat.date >= start_date)
        if end_date is not None:
            query = query.where(TemplateDailyStat.date <= end_date)
        return [self._serialize_daily_stat(item) for item in self._session.scalars(query).all()]

    def _validate_scope_filters(
        self,
        *,
        account_id: str | None,
        waba_id: str | None,
        phone_number_id: str | None,
        allowed_account_ids: set[str] | None,
    ) -> None:
        self._validate_account_waba_scope(
            account_id=account_id,
            waba_id=waba_id,
            allowed_account_ids=allowed_account_ids,
        )
        resolved_scope = self._meta_scope_validator.validate_phone_number_scope(
            phone_number_id=phone_number_id,
            account_id=account_id,
            waba_id=waba_id,
            allowed_account_ids=allowed_account_ids,
            enforce_waba_match=False,
        )
        if (
            resolved_scope is None
            or waba_id is None
            or resolved_scope.waba_id is None
            or resolved_scope.waba_id == waba_id
        ):
            return
        if self._has_historical_phone_scope(
            account_id=account_id or resolved_scope.account_id,
            waba_id=waba_id,
            phone_number_id=phone_number_id,
        ):
            return
        raise ValueError(
            f"Phone-Number-ID '{phone_number_id}' belongs to WABA '{resolved_scope.waba_id}', "
            f"not '{waba_id}'."
        )

    def _validate_account_waba_scope(
        self,
        *,
        account_id: str | None,
        waba_id: str | None,
        allowed_account_ids: set[str] | None,
    ) -> None:
        if account_id is None or waba_id is None:
            return

        current_waba = self._session.scalars(
            select(WhatsAppBusinessAccount).where(
                WhatsAppBusinessAccount.account_id == account_id,
                WhatsAppBusinessAccount.waba_id == waba_id,
            )
        ).first()
        if current_waba is not None:
            return

        if self._has_historical_waba_scope(account_id=account_id, waba_id=waba_id):
            return

        owner_query = select(WhatsAppBusinessAccount.account_id).where(
            WhatsAppBusinessAccount.waba_id == waba_id
        )
        if allowed_account_ids is not None:
            owner_query = owner_query.where(
                WhatsAppBusinessAccount.account_id.in_(allowed_account_ids)
            )
        owner_account_id = self._session.execute(owner_query.limit(1)).scalar_one_or_none()
        if owner_account_id is not None and owner_account_id != account_id:
            raise ValueError(
                f"WABA '{waba_id}' belongs to account '{owner_account_id}', not '{account_id}'."
            )

    def _validate_template_route_scope_filters(
        self,
        *,
        template: MessageTemplate,
        account_id: str | None,
        waba_id: str | None,
        phone_number_id: str | None,
        allowed_account_ids: set[str] | None,
    ) -> None:
        if account_id is not None and template.account_id != account_id:
            raise ValueError(
                f"Template '{template.id}' belongs to account '{template.account_id}', not '{account_id}'."
            )

        template_waba_id = self._resolve_template_waba_id(template)
        if waba_id is not None and template_waba_id is not None and template_waba_id != waba_id:
            if not self._has_historical_template_scope(
                template=template,
                waba_id=waba_id,
                phone_number_id=phone_number_id,
            ):
                raise ValueError(
                    f"Template '{template.id}' is bound to WABA '{template_waba_id}', not '{waba_id}'."
                )

        resolved_scope = self._meta_scope_validator.validate_phone_number_scope(
            phone_number_id=phone_number_id,
            account_id=account_id,
            waba_id=waba_id,
            allowed_account_ids=allowed_account_ids,
            enforce_waba_match=False,
        )
        effective_waba_id = waba_id or template_waba_id
        if (
            resolved_scope is None
            or effective_waba_id is None
            or resolved_scope.waba_id is None
            or resolved_scope.waba_id == effective_waba_id
        ):
            return
        if self._has_historical_template_scope(
            template=template,
            waba_id=effective_waba_id,
            phone_number_id=phone_number_id,
        ):
            return
        raise ValueError(
            f"Phone-Number-ID '{phone_number_id}' belongs to WABA '{resolved_scope.waba_id}', "
            f"not '{effective_waba_id}'."
        )

    def _has_historical_template_scope(
        self,
        *,
        template: MessageTemplate,
        waba_id: str | None,
        phone_number_id: str | None,
    ) -> bool:
        if self._session.scalars(
            select(TemplateDailyStat)
            .where(
                TemplateDailyStat.account_id == template.account_id,
                TemplateDailyStat.template_id == template.id,
            )
            .limit(1)
        ).first() is not None and self._has_historical_template_stat_scope(
            model=TemplateDailyStat,
            template=template,
            waba_id=waba_id,
            phone_number_id=phone_number_id,
        ):
            return True
        if self._session.scalars(
            select(TemplateHourlyStat)
            .where(
                TemplateHourlyStat.account_id == template.account_id,
                TemplateHourlyStat.template_id == template.id,
            )
            .limit(1)
        ).first() is not None and self._has_historical_template_stat_scope(
            model=TemplateHourlyStat,
            template=template,
            waba_id=waba_id,
            phone_number_id=phone_number_id,
        ):
            return True
        if self._session.scalars(
            select(TemplateFailureStat)
            .where(
                TemplateFailureStat.account_id == template.account_id,
                TemplateFailureStat.template_id == template.id,
            )
            .limit(1)
        ).first() is not None and self._has_historical_template_stat_scope(
            model=TemplateFailureStat,
            template=template,
            waba_id=waba_id,
            phone_number_id=phone_number_id,
        ):
            return True

        send_logs = self._session.scalars(
            select(TemplateSendLog)
            .options(
                selectinload(TemplateSendLog.phone_number),
                selectinload(TemplateSendLog.conversation)
                .selectinload(Conversation.phone_number)
                .selectinload(WhatsAppPhoneNumber.waba_account),
            )
            .where(
                TemplateSendLog.account_id == template.account_id,
                TemplateSendLog.template_id == template.id,
            )
        ).all()
        if not send_logs:
            return False
        message_scopes = self._load_send_log_message_scopes(send_logs)
        return any(
            self._matches_send_log_scope_filters(
                log=log,
                waba_id=waba_id,
                phone_number_id=phone_number_id,
                conversation=log.conversation,
                message_scope=message_scopes.get(log.id),
            )
            for log in send_logs
        )

    def _has_historical_template_stat_scope(
        self,
        *,
        model: type[TemplateDailyStat] | type[TemplateHourlyStat] | type[TemplateFailureStat],
        template: MessageTemplate,
        waba_id: str | None,
        phone_number_id: str | None,
    ) -> bool:
        query = select(model).where(
            model.account_id == template.account_id,
            model.template_id == template.id,
        )
        if waba_id is not None:
            query = query.where(model.waba_id == waba_id)
        if phone_number_id is not None:
            query = query.where(model.phone_number_id == phone_number_id)
        return self._session.scalars(query.limit(1)).first() is not None

    def _has_historical_phone_scope(
        self,
        *,
        account_id: str,
        waba_id: str,
        phone_number_id: str,
    ) -> bool:
        if self._session.scalars(
            select(TemplateDailyStat)
            .where(
                TemplateDailyStat.account_id == account_id,
                TemplateDailyStat.waba_id == waba_id,
                TemplateDailyStat.phone_number_id == phone_number_id,
            )
            .limit(1)
        ).first() is not None:
            return True
        if self._session.scalars(
            select(TemplateHourlyStat)
            .where(
                TemplateHourlyStat.account_id == account_id,
                TemplateHourlyStat.waba_id == waba_id,
                TemplateHourlyStat.phone_number_id == phone_number_id,
            )
            .limit(1)
        ).first() is not None:
            return True
        if self._session.scalars(
            select(TemplateFailureStat)
            .where(
                TemplateFailureStat.account_id == account_id,
                TemplateFailureStat.waba_id == waba_id,
                TemplateFailureStat.phone_number_id == phone_number_id,
            )
            .limit(1)
        ).first() is not None:
            return True
        send_logs = self._session.scalars(
            select(TemplateSendLog)
            .options(
                selectinload(TemplateSendLog.phone_number),
                selectinload(TemplateSendLog.conversation)
                .selectinload(Conversation.phone_number)
                .selectinload(WhatsAppPhoneNumber.waba_account),
            )
            .where(
                TemplateSendLog.account_id == account_id,
            )
        ).all()
        if not send_logs:
            return False
        message_scopes = self._load_send_log_message_scopes(send_logs)
        return any(
            self._matches_send_log_scope_filters(
                log=log,
                waba_id=waba_id,
                phone_number_id=phone_number_id,
                conversation=log.conversation,
                message_scope=message_scopes.get(log.id),
            )
            for log in send_logs
        )

    def _has_historical_waba_scope(
        self,
        *,
        account_id: str,
        waba_id: str,
    ) -> bool:
        if self._session.scalars(
            select(TemplateDailyStat)
            .where(
                TemplateDailyStat.account_id == account_id,
                TemplateDailyStat.waba_id == waba_id,
            )
            .limit(1)
        ).first() is not None:
            return True
        if self._session.scalars(
            select(TemplateHourlyStat)
            .where(
                TemplateHourlyStat.account_id == account_id,
                TemplateHourlyStat.waba_id == waba_id,
            )
            .limit(1)
        ).first() is not None:
            return True
        if self._session.scalars(
            select(TemplateFailureStat)
            .where(
                TemplateFailureStat.account_id == account_id,
                TemplateFailureStat.waba_id == waba_id,
            )
            .limit(1)
        ).first() is not None:
            return True
        send_logs = self._fetch_send_logs_for_analytics(
            account_id=account_id,
            waba_id=waba_id,
            phone_number_id=None,
            allowed_account_ids=None,
            start_date=None,
            end_date=None,
        )
        return len(send_logs) > 0

    async def get_stats_summary(
        self,
        *,
        account_id: str | None,
        waba_id: str | None = None,
        phone_number_id: str | None,
        category: TemplateCategory | None,
        language: str | None,
        date_from: str | None,
        date_to: str | None,
        allowed_account_ids: set[str] | None,
    ) -> TemplateStatsSummary:
        rows = await self.list_daily_stats(
            account_id=account_id,
            waba_id=waba_id,
            phone_number_id=phone_number_id,
            category=category,
            language=language,
            date_from=date_from,
            date_to=date_to,
            allowed_account_ids=allowed_account_ids,
        )
        return self._build_summary(
            send_count=sum(item.send_count for item in rows),
            delivered_count=sum(item.delivered_count for item in rows),
            read_count=sum(item.read_count for item in rows),
            failed_count=sum(item.failed_count for item in rows),
            billable_count=sum(item.billable_count for item in rows),
            estimated_cost=sum(item.estimated_cost for item in rows),
        )

    async def list_daily_stats(
        self,
        *,
        account_id: str | None,
        waba_id: str | None = None,
        phone_number_id: str | None,
        category: TemplateCategory | None,
        language: str | None,
        date_from: str | None,
        date_to: str | None,
        allowed_account_ids: set[str] | None,
    ) -> list[TemplateStatsDailyRow]:
        self._validate_scope_filters(
            account_id=account_id,
            waba_id=waba_id,
            phone_number_id=phone_number_id,
            allowed_account_ids=allowed_account_ids,
        )
        start_date, end_date = self._normalize_date_window(date_from=date_from, date_to=date_to)
        query = select(TemplateDailyStat).order_by(
            TemplateDailyStat.date.desc(),
            TemplateDailyStat.template_name.asc(),
        )
        if account_id is not None:
            query = query.where(TemplateDailyStat.account_id == account_id)
        elif allowed_account_ids is not None:
            query = query.where(TemplateDailyStat.account_id.in_(allowed_account_ids))
        if waba_id is not None:
            query = query.where(TemplateDailyStat.waba_id == waba_id)
        if phone_number_id is not None:
            query = query.where(TemplateDailyStat.phone_number_id == phone_number_id)
        if category is not None:
            query = query.where(TemplateDailyStat.template_category == category)
        if language is not None:
            query = query.where(TemplateDailyStat.template_language == language)
        if start_date is not None:
            query = query.where(TemplateDailyStat.date >= start_date)
        if end_date is not None:
            query = query.where(TemplateDailyStat.date <= end_date)
        rows = self._session.scalars(query).all()
        return [self._serialize_daily_stat(item) for item in rows]

    async def rebuild_daily_stats(
        self,
        *,
        account_id: str | None,
        waba_id: str | None,
        phone_number_id: str | None,
        date_from: str | None,
        date_to: str | None,
        allowed_account_ids: set[str] | None,
    ) -> datetime:
        self._validate_scope_filters(
            account_id=account_id,
            waba_id=waba_id,
            phone_number_id=phone_number_id,
            allowed_account_ids=allowed_account_ids,
        )
        start_date, end_date = self._normalize_date_window(date_from=date_from, date_to=date_to)
        return await self._refresh_daily_stats(
            account_id=account_id,
            waba_id=waba_id,
            phone_number_id=phone_number_id,
            allowed_account_ids=allowed_account_ids,
            start_date=start_date,
            end_date=end_date,
        )

    async def get_template_analytics(
        self,
        *,
        template_id: str,
        waba_id: str | None = None,
        phone_number_id: str | None,
        date_from: str | None,
        date_to: str | None,
        allowed_account_ids: set[str] | None,
    ) -> TemplateStatsDetailResponse:
        template = self._require_template(template_id)
        self._ensure_template_account_allowed(
            template=template,
            allowed_account_ids=allowed_account_ids,
        )
        self._validate_scope_filters(
            account_id=template.account_id,
            waba_id=waba_id,
            phone_number_id=phone_number_id,
            allowed_account_ids=allowed_account_ids,
        )
        self._validate_template_route_scope_filters(
            template=template,
            account_id=template.account_id,
            waba_id=waba_id,
            phone_number_id=phone_number_id,
            allowed_account_ids=allowed_account_ids,
        )
        start_date, end_date = self._normalize_date_window(date_from=date_from, date_to=date_to)
        daily_rows = self._load_template_daily_rows(
            template=template,
            waba_id=waba_id,
            phone_number_id=phone_number_id,
            start_date=start_date,
            end_date=end_date,
            allowed_account_ids=allowed_account_ids,
        )
        summary = self._build_summary(
            send_count=sum(item.send_count for item in daily_rows),
            delivered_count=sum(item.delivered_count for item in daily_rows),
            read_count=sum(item.read_count for item in daily_rows),
            failed_count=sum(item.failed_count for item in daily_rows),
            billable_count=sum(item.billable_count for item in daily_rows),
            estimated_cost=sum(item.estimated_cost for item in daily_rows),
        )
        hourly_rows = self._load_template_hourly_rows(
            template=template,
            waba_id=waba_id,
            phone_number_id=phone_number_id,
            start_date=start_date,
            end_date=end_date,
            allowed_account_ids=allowed_account_ids,
        )
        failure_rows = self._load_template_failure_rows(
            template=template,
            waba_id=waba_id,
            phone_number_id=phone_number_id,
            start_date=start_date,
            end_date=end_date,
            allowed_account_ids=allowed_account_ids,
        )
        return TemplateStatsDetailResponse(
            template_id=template.id,
            template_name=template.name,
            account_id=template.account_id,
            template_language=template.language,
            template_category=template.category,
            summary=summary,
            daily_rows=daily_rows,
            hourly_rows=hourly_rows,
            failure_reasons=failure_rows,
        )

    async def send_template(
        self,
        template_id: str,
        payload: TemplateSendRequest,
        allowed_account_ids: set[str] | None = None,
        actor_type: str | None = None,
        actor_id: str | None = None,
    ) -> TemplateSendResponse:
        template = self._require_template(template_id)
        self._ensure_template_account_allowed(template=template, allowed_account_ids=allowed_account_ids)
        if template.account_id != payload.account_id:
            raise ValueError(
                f"Template '{template_id}' does not belong to account '{payload.account_id}'."
            )
        if template.status != "APPROVED":
            raise ValueError(
                f"Template '{template_id}' in status '{template.status}' cannot be sent."
            )

        conversation = await self._runtime_state.get_conversation_model(
            account_id=payload.account_id,
            conversation_id=payload.conversation_id,
        )
        self._runtime_state.ensure_conversation_messaging_available(conversation)
        conversation_phone_number_id = self._resolve_conversation_provider_phone_number_id(
            conversation
        )
        conversation_identity_payload = self._build_conversation_identity_payload(
            conversation=conversation,
            fallback_external_conversation_id=payload.conversation_id,
        )
        if payload.phone_number_id is not None:
            if conversation_phone_number_id is None:
                raise ValueError(
                    f"Conversation '{payload.conversation_id}' is not bound to a Phone-Number-ID."
                )
            if payload.phone_number_id != conversation_phone_number_id:
                raise ValueError(
                    "Template send Phone-Number-ID "
                    f"'{payload.phone_number_id}' does not match conversation Phone-Number-ID "
                    f"'{conversation_phone_number_id}'."
                )
        self._ensure_agent_can_send_template(
            conversation=conversation,
            agent_id=payload.agent_id,
        )
        sent_by_agent_id = self._runtime_state.resolve_agent_storage_id(
            account_id=payload.account_id,
            agent_id=payload.agent_id,
        )
        rendered_text = self._render_template(
            body_text=str((template.components or {}).get("body_text") or ""),
            variables=payload.variables,
            sample_variables=self._extract_sample_variables(template),
        )
        header_media_asset = self._resolve_header_media_asset_for_send(
            template=template,
            conversation=conversation,
        )
        existing_send_log = self._find_send_log_by_idempotency_key(
            account_id=payload.account_id,
            template_id=template.id,
            conversation_id=payload.conversation_id,
            idempotency_key=payload.idempotency_key,
        )
        if existing_send_log is not None:
            existing_conversation_id = (
                existing_send_log.conversation.external_conversation_id
                if existing_send_log.conversation is not None
                else None
            )
            if (
                existing_send_log.template_id != template.id
                or existing_conversation_id != payload.conversation_id
            ):
                raise ValueError(
                    "Template idempotency key has already been used for another "
                    "template send in this account."
                )
            await self._runtime_state.replay_unmatched_provider_status_events(
                account_id=payload.account_id,
                provider_message_id=existing_send_log.message_id,
            )
            self._session.refresh(existing_send_log)
            return TemplateSendResponse(
                template_id=template.id,
                account_id=payload.account_id,
                conversation_id=payload.conversation_id,
                external_conversation_id=conversation.external_conversation_id,
                internal_conversation_id=conversation.id,
                phone_number_id=conversation_phone_number_id,
                status=existing_send_log.status,
                delivered_text=rendered_text,
                template_language=template.language,
                header_media_asset_id=existing_send_log.header_media_asset_id,
                header_media_asset_name=existing_send_log.header_media_asset_name,
                header_media_asset_type=existing_send_log.header_media_asset_type,
                header_media_provider_media_id=(
                    existing_send_log.header_media_provider_media_id
                    or existing_send_log.header_media_meta_media_id
                ),
                header_media_meta_media_id=existing_send_log.header_media_meta_media_id,
                header_media_sync_status=existing_send_log.header_media_sync_status,
                message_id=existing_send_log.message_id,
                send_log_id=existing_send_log.id,
                provider=self._messaging_provider.provider_name,
            )
        try:
            self._ensure_template_route_matches_conversation(
                template=template,
                conversation=conversation,
            )
        except ValueError as exc:
            self._record_failed_send_attempt(
                template=template,
                conversation=conversation,
                payload=payload,
                rendered_text=rendered_text,
                header_media_asset=None,
                error_code="template_route_mismatch",
                failure_reason=str(exc),
                actor_type=actor_type,
                actor_id=actor_id,
            )
            raise
        resolved_route_waba_id = self._resolve_template_send_waba_id(
            template=template,
            conversation=conversation,
        )
        prepared_header_reference = None
        if header_media_asset is not None:
            try:
                prepared_header_reference = await self._media_asset_sync_service.ensure_provider_reference(
                    asset=header_media_asset,
                    account_id=payload.account_id,
                    target_phone_number_id=conversation_phone_number_id,
                    actor_type=actor_type or ("agent" if payload.agent_id else "system"),
                    actor_id=actor_id or payload.agent_id,
                    usage_context="template_header_send",
                    context_payload={
                        **conversation_identity_payload,
                        "template_id": template.id,
                        "waba_id": resolved_route_waba_id,
                        "phone_number_id": conversation_phone_number_id,
                    },
                )
            except MediaProviderConfigError as exc:
                self._record_failed_send_attempt(
                    template=template,
                    conversation=conversation,
                    payload=payload,
                    rendered_text=rendered_text,
                    header_media_asset=header_media_asset,
                    error_code="header_media_sync_failed",
                    failure_reason=str(exc),
                    actor_type=actor_type,
                    actor_id=actor_id,
                )
                raise MediaProviderConfigError(f"Template send failed: {exc}") from exc
            except MediaProviderUpstreamError as exc:
                self._record_failed_send_attempt(
                    template=template,
                    conversation=conversation,
                    payload=payload,
                    rendered_text=rendered_text,
                    header_media_asset=header_media_asset,
                    error_code="header_media_sync_failed",
                    failure_reason=str(exc),
                    actor_type=actor_type,
                    actor_id=actor_id,
                )
                raise MediaProviderUpstreamError(f"Template send failed: {exc}") from exc
            except ValueError as exc:
                self._record_failed_send_attempt(
                    template=template,
                    conversation=conversation,
                    payload=payload,
                    rendered_text=rendered_text,
                    header_media_asset=header_media_asset,
                    error_code="header_media_sync_failed",
                    failure_reason=str(exc),
                    actor_type=actor_type,
                    actor_id=actor_id,
                )
                raise ValueError(f"Template send failed: {exc}") from exc
        header_provider_media_id = (
            prepared_header_reference.provider_media_id
            if prepared_header_reference is not None
            else None
        )
        header_meta_media_id = (
            prepared_header_reference.meta_media_id
            if prepared_header_reference is not None
            else None
        )
        dispatch_request = build_outbound_dispatch_request(
            provider=self._messaging_provider,
            conversation=conversation,
            account_id=payload.account_id,
            conversation_id=payload.conversation_id,
            recipient_id=conversation.customer_id,
            text=rendered_text,
            message_type="template",
            template_name=template.name,
            template_language=template.language,
            template_variables=payload.variables,
            template_header_media_type=(
                header_media_asset.asset_type if header_media_asset is not None else None
            ),
            media_asset_id=(
                header_provider_media_id
            ),
            media_url=None,
            file_name=(
                header_media_asset.name
                if header_media_asset is not None and header_media_asset.asset_type == "document"
                else None
            ),
            metadata={
                "template_id": template.id,
            },
        )
        try:
            dispatch_result = await self._messaging_provider.send_outbound(dispatch_request)
        except Exception as exc:
            business_outbound_messages_total.labels(
                provider=self._messaging_provider.provider_name,
                delivery_mode="template_send",
                outcome="failed",
            ).inc()
            message_processing_failures_total.labels(
                provider=self._messaging_provider.provider_name,
                stage="template_send",
            ).inc()
            self._record_failed_send_attempt(
                template=template,
                conversation=conversation,
                payload=payload,
                rendered_text=rendered_text,
                header_media_asset=header_media_asset,
                prepared_header_reference=prepared_header_reference,
                error_code="dispatch_exception",
                failure_reason=str(exc),
                actor_type=actor_type,
                actor_id=actor_id,
            )
            detail = f"Template send failed: {exc}"
            if isinstance(exc, RuntimeError):
                raise MediaProviderUpstreamError(detail) from exc
            if isinstance(exc, ValueError) and "access_token" in str(exc) and "requires" in str(exc):
                raise MediaProviderConfigError(detail) from exc
            raise ValueError(detail) from exc
        business_outbound_messages_total.labels(
            provider=dispatch_result.provider_name,
            delivery_mode="template_send",
            outcome="accepted",
        ).inc()
        business_template_sends_total.labels(
            provider=dispatch_result.provider_name,
            status="SENT",
        ).inc()
        message_payload: dict[str, object | None] = {
            "template_id": template.id,
            "template_name": template.name,
            "template_language": template.language,
            "variables": payload.variables,
            "header_media_asset_id": header_media_asset.id if header_media_asset is not None else None,
            "header_media_asset_name": (
                header_media_asset.name if header_media_asset is not None else None
            ),
            "header_media_asset_type": (
                header_media_asset.asset_type if header_media_asset is not None else None
            ),
            "header_media_storage_url": (
                header_media_asset.storage_url if header_media_asset is not None else None
            ),
            "header_media_provider_media_id": header_provider_media_id,
            "header_media_meta_media_id": header_meta_media_id,
            "agent_id": payload.agent_id,
            "provider": dispatch_result.provider_name,
            "provider_message_id": dispatch_result.provider_message_id,
            "provider_accepted": dispatch_result.accepted,
            "mock_send": self._messaging_provider.provider_name == "mock",
        }
        if resolved_route_waba_id is not None:
            message_payload["waba_id"] = resolved_route_waba_id
        if conversation_phone_number_id is not None:
            message_payload["phone_number_id"] = conversation_phone_number_id
        message = await self._runtime_state.record_outbound_message(
            account_id=payload.account_id,
            conversation_id=payload.conversation_id,
            recipient_id=conversation.customer_id,
            text=rendered_text,
            language_code=template.language,
            translated_text=None,
            translated_language_code=None,
            delivery_mode="template_send",
            ai_generated=False,
            payload=message_payload,
            message_type="template",
            sent_by_agent_id=sent_by_agent_id,
            provider_message_id=dispatch_result.provider_message_id,
        )
        send_log = TemplateSendLog(
            account_id=payload.account_id,
            template_id=template.id,
            conversation_id=conversation.id,
            phone_number_id=conversation_phone_number_id,
            waba_id=resolved_route_waba_id,
            template_name=template.name,
            template_language=template.language,
            template_category=template.category,
            template_code=template.meta_template_id,
            header_media_asset_id=header_media_asset.id if header_media_asset is not None else None,
            header_media_asset_name=header_media_asset.name if header_media_asset is not None else None,
            header_media_asset_type=header_media_asset.asset_type if header_media_asset is not None else None,
            header_media_provider_media_id=header_provider_media_id,
            header_media_meta_media_id=header_meta_media_id,
            header_media_sync_status=(
                prepared_header_reference.provider_sync.sync_status
                if prepared_header_reference is not None
                else None
            ),
            wa_id=conversation.customer_id,
            message_id=dispatch_result.provider_message_id or message.id,
            idempotency_key=payload.idempotency_key,
            status="SENT",
            sent_at=utc_now(),
            last_status_at=utc_now(),
        )
        self._session.add(send_log)
        self._session.flush()
        self._template_stats_aggregator.record_send_log_created(send_log)
        if header_media_asset is not None:
            self._session.add(
                MediaAssetEvent(
                    account_id=payload.account_id,
                    asset_id=header_media_asset.id,
                    waba_id=resolved_route_waba_id,
                    phone_number_id=conversation_phone_number_id,
                    event_type="media_asset_template_sent",
                    provider_media_id=header_provider_media_id,
                    meta_media_id=(
                        prepared_header_reference.meta_media_id
                        if prepared_header_reference is not None
                        else None
                    ),
                    created_by=actor_id or payload.agent_id,
                    payload={
                        **conversation_identity_payload,
                        "template_id": template.id,
                        "message_id": message.id,
                        "send_log_id": send_log.id,
                        "provider": dispatch_result.provider_name,
                        "provider_message_id": dispatch_result.provider_message_id,
                        "provider_media_id": header_provider_media_id,
                        "meta_media_id": header_meta_media_id,
                        "waba_id": resolved_route_waba_id,
                        "phone_number_id": conversation_phone_number_id,
                        "sync_status": (
                            prepared_header_reference.provider_sync.sync_status
                            if prepared_header_reference is not None
                            else None
                        ),
                    },
                )
            )
        self._runtime_state.add_audit_log(
            account_id=payload.account_id,
            actor_type=actor_type or ("agent" if payload.agent_id else "system"),
            actor_id=actor_id or payload.agent_id,
            action="template_sent",
            target_type="message_template",
            target_id=template.id,
            payload={
                **conversation_identity_payload,
                "message_id": message.id,
                "provider": dispatch_result.provider_name,
                "provider_message_id": dispatch_result.provider_message_id,
                "send_log_id": send_log.id,
                "waba_id": resolved_route_waba_id,
                "phone_number_id": conversation_phone_number_id,
                "idempotency_key": payload.idempotency_key,
                "wa_id": conversation.customer_id,
                "status": "SENT",
                "delivered_text": rendered_text,
                "variables": payload.variables,
                "header_media_asset_id": header_media_asset.id if header_media_asset is not None else None,
                "header_media_asset_type": (
                    header_media_asset.asset_type if header_media_asset is not None else None
                ),
                "header_media_provider_media_id": header_provider_media_id,
                "header_media_meta_media_id": header_meta_media_id,
                "header_media_sync_status": (
                    prepared_header_reference.provider_sync.sync_status
                    if prepared_header_reference is not None
                    else None
                ),
            },
        )
        self._session.commit()
        await self._runtime_state.replay_unmatched_provider_status_events(
            account_id=payload.account_id,
            provider_message_id=dispatch_result.provider_message_id,
        )
        self._session.refresh(send_log)
        return TemplateSendResponse(
            template_id=template.id,
            account_id=payload.account_id,
            conversation_id=conversation_identity_payload["conversation_id"] or payload.conversation_id,
            external_conversation_id=(
                conversation_identity_payload["external_conversation_id"] or payload.conversation_id
            ),
            internal_conversation_id=conversation.id,
            phone_number_id=conversation_phone_number_id,
            status="SENT",
            delivered_text=rendered_text,
            template_language=template.language,
            header_media_asset_id=header_media_asset.id if header_media_asset is not None else None,
            header_media_asset_name=header_media_asset.name if header_media_asset is not None else None,
            header_media_asset_type=header_media_asset.asset_type if header_media_asset is not None else None,
            header_media_provider_media_id=header_provider_media_id,
            header_media_meta_media_id=header_meta_media_id,
            header_media_sync_status=(
                prepared_header_reference.provider_sync.sync_status
                if prepared_header_reference is not None
                else None
            ),
            message_id=dispatch_result.provider_message_id or message.id,
            send_log_id=send_log.id,
            provider=dispatch_result.provider_name,
        )

    async def submit_template(
        self,
        template_id: str,
        allowed_account_ids: set[str] | None = None,
        actor_type: str = "system",
        actor_id: str | None = None,
    ) -> TemplateSubmitResponse:
        template = self._require_template(template_id)
        self._ensure_template_account_allowed(template=template, allowed_account_ids=allowed_account_ids)
        if template.status != "DRAFT":
            raise ValueError(
                f"Template '{template.id}' is in status '{template.status}' and cannot be submitted again."
            )
        waba_account = self._require_template_waba(template)
        submit_time = utc_now()
        result = await self._template_registry_provider.submit_template(
            TemplateRegistrySubmitRequest(
                account_id=template.account_id,
                waba_id=waba_account.waba_id,
                access_token=waba_account.access_token,
                name=template.name,
                language=template.language,
                category=template.category,
                components=template.components or {},
            )
        )
        template.meta_template_id = result.provider_template_id or template.meta_template_id
        template.status = result.remote_status
        template.rejected_reason = (
            result.remote_template.rejected_reason
            if result.remote_template is not None
            else template.rejected_reason
        )
        template.submitted_at = submit_time
        template.last_synced_at = submit_time
        template.provider_template_payload = result.raw_response
        self._session.add(template)
        self._runtime_state.add_audit_log(
            account_id=template.account_id,
            actor_type=actor_type,
            actor_id=actor_id,
            action="template_submitted",
            target_type="message_template",
            target_id=template.id,
            payload={
                "provider": result.provider_name,
                "waba_id": waba_account.waba_id,
                "meta_template_id": template.meta_template_id,
                "remote_status": result.remote_status,
                "action": result.action,
            },
        )
        self._session.commit()
        self._session.refresh(template)
        return TemplateSubmitResponse(
            provider=result.provider_name,
            action=result.action,
            remote_status=result.remote_status,
            template=self._serialize_template(template),
        )

    async def sync_templates(
        self,
        payload: TemplateSyncRequest,
        actor_type: str = "system",
        actor_id: str | None = None,
    ) -> TemplateSyncResponse:
        waba_account = self._require_waba_for_account(
            account_id=payload.account_id,
            waba_id=payload.waba_id,
        )
        result = await self._template_registry_provider.sync_templates(
            account_id=payload.account_id,
            waba_id=payload.waba_id,
            access_token=waba_account.access_token,
        )
        sync_time = utc_now()
        created_count = 0
        updated_count = 0
        skipped_count = 0
        synced_templates: list[MessageTemplateView] = []

        for remote_template in result.templates:
            template = self._find_template_for_remote(
                account_id=payload.account_id,
                waba_id=payload.waba_id,
                remote_template=remote_template,
            )
            if template is None and not payload.import_missing:
                skipped_count += 1
                continue
            if template is None:
                template = MessageTemplate(
                    account_id=payload.account_id,
                    waba_account_id=waba_account.id,
                    waba_id=payload.waba_id,
                    name=remote_template.name,
                    language=remote_template.language,
                    category=remote_template.category,
                    status=remote_template.status,
                    meta_template_id=remote_template.provider_template_id,
                    rejected_reason=remote_template.rejected_reason,
                    components=remote_template.components,
                    last_synced_at=sync_time,
                    provider_template_payload=remote_template.raw_payload,
                )
                template.waba_account = waba_account
                self._session.add(template)
                self._session.flush()
                created_count += 1
            else:
                template.waba_account_id = waba_account.id
                template.waba_account = waba_account
                template.waba_id = payload.waba_id
                template.name = remote_template.name
                template.language = remote_template.language
                template.category = remote_template.category
                template.status = remote_template.status
                template.meta_template_id = remote_template.provider_template_id or template.meta_template_id
                template.rejected_reason = remote_template.rejected_reason
                template.components = remote_template.components
                template.last_synced_at = sync_time
                template.provider_template_payload = remote_template.raw_payload
                self._session.add(template)
                updated_count += 1
            synced_templates.append(self._serialize_template(template))

        self._runtime_state.add_audit_log(
            account_id=payload.account_id,
            actor_type=actor_type,
            actor_id=actor_id,
            action="template_sync_completed",
            target_type="waba_account",
            target_id=payload.waba_id,
            payload={
                "provider": result.provider_name,
                "created_count": created_count,
                "updated_count": updated_count,
                "skipped_count": skipped_count,
                "import_missing": payload.import_missing,
            },
        )
        self._session.commit()
        return TemplateSyncResponse(
            account_id=payload.account_id,
            waba_id=payload.waba_id,
            provider=result.provider_name,
            created_count=created_count,
            updated_count=updated_count,
            skipped_count=skipped_count,
            templates=synced_templates,
        )

    async def _refresh_daily_stats(
        self,
        *,
        account_id: str | None,
        waba_id: str | None,
        phone_number_id: str | None,
        allowed_account_ids: set[str] | None,
        start_date: date | None,
        end_date: date | None,
    ) -> datetime:
        rebuilt_at = utc_now()
        send_logs = self._fetch_send_logs_for_analytics(
            account_id=account_id,
            waba_id=waba_id,
            phone_number_id=phone_number_id,
            allowed_account_ids=allowed_account_ids,
            start_date=start_date,
            end_date=end_date,
        )
        self._delete_template_stat_rows(
            model=TemplateDailyStat,
            account_id=account_id,
            waba_id=waba_id,
            phone_number_id=phone_number_id,
            allowed_account_ids=allowed_account_ids,
            start_date=start_date,
            end_date=end_date,
        )
        self._delete_template_stat_rows(
            model=TemplateHourlyStat,
            account_id=account_id,
            waba_id=waba_id,
            phone_number_id=phone_number_id,
            allowed_account_ids=allowed_account_ids,
            start_date=start_date,
            end_date=end_date,
        )
        self._delete_template_stat_rows(
            model=TemplateFailureStat,
            account_id=account_id,
            waba_id=waba_id,
            phone_number_id=phone_number_id,
            allowed_account_ids=allowed_account_ids,
            start_date=start_date,
            end_date=end_date,
        )
        if waba_id is not None or phone_number_id is not None:
            self._delete_scoped_rebuild_dirty_rows(send_logs)

        for log in send_logs:
            self._template_stats_aggregator.record_send_log_created(log)
        self._session.commit()
        return rebuilt_at

    def _delete_template_stat_rows(
        self,
        *,
        model: type[TemplateDailyStat] | type[TemplateHourlyStat] | type[TemplateFailureStat],
        account_id: str | None,
        waba_id: str | None,
        phone_number_id: str | None,
        allowed_account_ids: set[str] | None,
        start_date: date | None,
        end_date: date | None,
    ) -> None:
        delete_stmt = delete(model)
        if account_id is not None:
            delete_stmt = delete_stmt.where(model.account_id == account_id)
        elif allowed_account_ids is not None:
            delete_stmt = delete_stmt.where(model.account_id.in_(allowed_account_ids))
        if waba_id is not None:
            delete_stmt = delete_stmt.where(model.waba_id == waba_id)
        if phone_number_id is not None:
            delete_stmt = delete_stmt.where(model.phone_number_id == phone_number_id)
        if start_date is not None:
            delete_stmt = delete_stmt.where(model.date >= start_date)
        if end_date is not None:
            delete_stmt = delete_stmt.where(model.date <= end_date)
        self._session.execute(delete_stmt)

    def _delete_scoped_rebuild_dirty_rows(
        self,
        send_logs: list[TemplateSendLog],
    ) -> None:
        if not send_logs:
            return
        message_scopes = self._load_send_log_message_scopes(send_logs)
        daily_keys: set[tuple[str, date, str | None, str | None, str | None, str, str]] = set()
        hourly_keys: set[tuple[str, date, int, str | None, str | None, str | None, str, str]] = set()
        failure_keys: set[
            tuple[str, date, str | None, str | None, str | None, str, str, str]
        ] = set()

        for log in send_logs:
            if (
                log.template_name is None
                or log.template_language is None
                or log.template_category is None
            ):
                continue
            occurred_at = self._template_stats_aggregator._resolve_occurred_at(log)
            for variant_waba_id, variant_phone_number_id in self._build_rebuild_scope_variants(
                log=log,
                message_scope=message_scopes.get(log.id),
            ):
                daily_keys.add(
                    (
                        log.account_id,
                        occurred_at.date(),
                        log.template_id,
                        variant_waba_id,
                        variant_phone_number_id,
                        log.template_name,
                        log.template_language,
                    )
                )
                hourly_keys.add(
                    (
                        log.account_id,
                        occurred_at.date(),
                        occurred_at.hour,
                        log.template_id,
                        variant_waba_id,
                        variant_phone_number_id,
                        log.template_name,
                        log.template_language,
                    )
                )
                if log.failed_at is not None or log.status == "FAILED":
                    failure_keys.add(
                        (
                            log.account_id,
                            occurred_at.date(),
                            log.template_id,
                            variant_waba_id,
                            variant_phone_number_id,
                            log.template_name,
                            log.template_language,
                            log.error_code or "unknown",
                        )
                    )

        self._delete_template_daily_rows_by_keys(daily_keys)
        self._delete_template_hourly_rows_by_keys(hourly_keys)
        self._delete_template_failure_rows_by_keys(failure_keys)

    def _build_rebuild_scope_variants(
        self,
        *,
        log: TemplateSendLog,
        message_scope: dict[str, str | None] | None,
    ) -> set[tuple[str | None, str | None]]:
        conversation = log.conversation
        variants: set[tuple[str | None, str | None]] = {
            (
                self._resolve_send_log_waba_id(
                    log,
                    conversation=conversation,
                    message_scope=message_scope,
                ),
                self._resolve_send_log_provider_phone_number_id(
                    log,
                    conversation=conversation,
                    message_scope=message_scope,
                ),
            ),
            (log.waba_id, log.phone_number_id),
        }
        if isinstance(log.phone_number_id, str) and log.phone_number_id:
            phone_number = self._resolve_phone_number_by_local_or_provider_id(
                account_id=log.account_id,
                phone_number_id=log.phone_number_id,
            )
            if phone_number is not None:
                variants.add(
                    (
                        phone_number.waba_id
                        or (
                            phone_number.waba_account.waba_id
                            if phone_number.waba_account is not None
                            else None
                        ),
                        phone_number.phone_number_id,
                    )
                )
                variants.add(
                    (
                        log.waba_id
                        or phone_number.waba_id
                        or (
                            phone_number.waba_account.waba_id
                            if phone_number.waba_account is not None
                            else None
                        ),
                        phone_number.id,
                    )
                )
        return variants

    def _delete_template_daily_rows_by_keys(
        self,
        keys: set[tuple[str, date, str | None, str | None, str | None, str, str]],
    ) -> None:
        if not keys:
            return
        clauses = [
            and_(
                TemplateDailyStat.account_id == account_id,
                TemplateDailyStat.date == stat_date,
                TemplateDailyStat.template_id == template_id,
                TemplateDailyStat.waba_id == row_waba_id,
                TemplateDailyStat.phone_number_id == row_phone_number_id,
                TemplateDailyStat.template_name == template_name,
                TemplateDailyStat.template_language == template_language,
            )
            for (
                account_id,
                stat_date,
                template_id,
                row_waba_id,
                row_phone_number_id,
                template_name,
                template_language,
            ) in keys
        ]
        self._session.execute(delete(TemplateDailyStat).where(or_(*clauses)))

    def _delete_template_hourly_rows_by_keys(
        self,
        keys: set[tuple[str, date, int, str | None, str | None, str | None, str, str]],
    ) -> None:
        if not keys:
            return
        clauses = [
            and_(
                TemplateHourlyStat.account_id == account_id,
                TemplateHourlyStat.date == stat_date,
                TemplateHourlyStat.hour_bucket == hour_bucket,
                TemplateHourlyStat.template_id == template_id,
                TemplateHourlyStat.waba_id == row_waba_id,
                TemplateHourlyStat.phone_number_id == row_phone_number_id,
                TemplateHourlyStat.template_name == template_name,
                TemplateHourlyStat.template_language == template_language,
            )
            for (
                account_id,
                stat_date,
                hour_bucket,
                template_id,
                row_waba_id,
                row_phone_number_id,
                template_name,
                template_language,
            ) in keys
        ]
        self._session.execute(delete(TemplateHourlyStat).where(or_(*clauses)))

    def _delete_template_failure_rows_by_keys(
        self,
        keys: set[tuple[str, date, str | None, str | None, str | None, str, str, str]],
    ) -> None:
        if not keys:
            return
        clauses = [
            and_(
                TemplateFailureStat.account_id == account_id,
                TemplateFailureStat.date == stat_date,
                TemplateFailureStat.template_id == template_id,
                TemplateFailureStat.waba_id == row_waba_id,
                TemplateFailureStat.phone_number_id == row_phone_number_id,
                TemplateFailureStat.template_name == template_name,
                TemplateFailureStat.template_language == template_language,
                TemplateFailureStat.error_code == error_code,
            )
            for (
                account_id,
                stat_date,
                template_id,
                row_waba_id,
                row_phone_number_id,
                template_name,
                template_language,
                error_code,
            ) in keys
        ]
        self._session.execute(delete(TemplateFailureStat).where(or_(*clauses)))

    def _fetch_send_logs_for_analytics(
        self,
        *,
        account_id: str | None,
        waba_id: str | None,
        phone_number_id: str | None,
        allowed_account_ids: set[str] | None,
        start_date: date | None,
        end_date: date | None,
    ) -> list[TemplateSendLog]:
        query = (
            select(TemplateSendLog)
            .options(
                selectinload(TemplateSendLog.template).selectinload(MessageTemplate.waba_account),
                selectinload(TemplateSendLog.phone_number).selectinload(WhatsAppPhoneNumber.waba_account),
                selectinload(TemplateSendLog.conversation)
                .selectinload(Conversation.phone_number)
                .selectinload(WhatsAppPhoneNumber.waba_account),
            )
            .order_by(TemplateSendLog.created_at.desc(), TemplateSendLog.id.desc())
        )
        if account_id is not None:
            query = query.where(TemplateSendLog.account_id == account_id)
        elif allowed_account_ids is not None:
            query = query.where(TemplateSendLog.account_id.in_(allowed_account_ids))
        occurred_at = func.coalesce(TemplateSendLog.sent_at, TemplateSendLog.created_at)
        if start_date is not None:
            query = query.where(occurred_at >= datetime.combine(start_date, time.min))
        if end_date is not None:
            query = query.where(occurred_at <= datetime.combine(end_date, time.max))
        send_logs = self._session.scalars(query).all()
        message_scopes = self._load_send_log_message_scopes(send_logs)
        filtered_logs: list[TemplateSendLog] = []
        for item in send_logs:
            if not self._matches_send_log_scope_filters(
                log=item,
                waba_id=waba_id,
                phone_number_id=phone_number_id,
                conversation=item.conversation,
                message_scope=message_scopes.get(item.id),
            ):
                continue
            occurred_at = item.sent_at or item.created_at
            occurred_date = occurred_at.date()
            if start_date is not None and occurred_date < start_date:
                continue
            if end_date is not None and occurred_date > end_date:
                continue
            filtered_logs.append(item)
        return filtered_logs

    def _load_template_hourly_rows(
        self,
        *,
        template: MessageTemplate,
        waba_id: str | None,
        phone_number_id: str | None,
        start_date: date | None,
        end_date: date | None,
        allowed_account_ids: set[str] | None,
    ) -> list[TemplateStatsHourlyRow]:
        query = select(TemplateHourlyStat).where(TemplateHourlyStat.template_id == template.id).order_by(
            TemplateHourlyStat.hour_bucket.asc(),
            TemplateHourlyStat.date.asc(),
        )
        if allowed_account_ids is not None:
            query = query.where(TemplateHourlyStat.account_id.in_(allowed_account_ids))
        if waba_id is not None:
            query = query.where(TemplateHourlyStat.waba_id == waba_id)
        if phone_number_id is not None:
            query = query.where(TemplateHourlyStat.phone_number_id == phone_number_id)
        if start_date is not None:
            query = query.where(TemplateHourlyStat.date >= start_date)
        if end_date is not None:
            query = query.where(TemplateHourlyStat.date <= end_date)

        counters: dict[int, dict[str, int]] = {}
        for row in self._session.scalars(query).all():
            current = counters.setdefault(
                row.hour_bucket,
                {
                    "send_count": 0,
                    "delivered_count": 0,
                    "read_count": 0,
                    "failed_count": 0,
                },
            )
            current["send_count"] += row.send_count
            current["delivered_count"] += row.delivered_count
            current["read_count"] += row.read_count
            current["failed_count"] += row.failed_count

        return [
            TemplateStatsHourlyRow(
                hour_bucket=hour_bucket,
                send_count=counts["send_count"],
                delivered_count=counts["delivered_count"],
                read_count=counts["read_count"],
                failed_count=counts["failed_count"],
            )
            for hour_bucket, counts in sorted(counters.items())
        ]

    def _load_template_failure_rows(
        self,
        *,
        template: MessageTemplate,
        waba_id: str | None,
        phone_number_id: str | None,
        start_date: date | None,
        end_date: date | None,
        allowed_account_ids: set[str] | None,
    ) -> list[TemplateStatsFailureReason]:
        query = select(TemplateFailureStat).where(
            TemplateFailureStat.template_id == template.id
        ).order_by(
            TemplateFailureStat.error_code.asc(),
            TemplateFailureStat.date.asc(),
        )
        if allowed_account_ids is not None:
            query = query.where(TemplateFailureStat.account_id.in_(allowed_account_ids))
        if waba_id is not None:
            query = query.where(TemplateFailureStat.waba_id == waba_id)
        if phone_number_id is not None:
            query = query.where(TemplateFailureStat.phone_number_id == phone_number_id)
        if start_date is not None:
            query = query.where(TemplateFailureStat.date >= start_date)
        if end_date is not None:
            query = query.where(TemplateFailureStat.date <= end_date)

        counters: dict[str, int] = {}
        for row in self._session.scalars(query).all():
            counters[row.error_code] = counters.get(row.error_code, 0) + row.failed_count

        return [
            TemplateStatsFailureReason(error_code=error_code, failed_count=failed_count)
            for error_code, failed_count in sorted(
                counters.items(),
                key=lambda item: (-item[1], item[0]),
            )
        ]

    @staticmethod
    def _normalize_date_window(
        *,
        date_from: str | None,
        date_to: str | None,
    ) -> tuple[date | None, date | None]:
        start_date = datetime.fromisoformat(date_from).date() if date_from else None
        end_date = datetime.fromisoformat(date_to).date() if date_to else None
        if start_date is not None and end_date is not None and start_date > end_date:
            raise ValueError("date_from must be less than or equal to date_to.")
        return start_date, end_date

    def _serialize_daily_stat(self, item: TemplateDailyStat) -> TemplateStatsDailyRow:
        summary = self._build_summary(
            send_count=item.send_count,
            delivered_count=item.delivered_count,
            read_count=item.read_count,
            failed_count=item.failed_count,
            billable_count=item.billable_count,
            estimated_cost=float(item.estimated_cost or 0),
        )
        return TemplateStatsDailyRow(
            date=item.date.isoformat(),
            account_id=item.account_id,
            template_id=item.template_id,
            waba_id=item.waba_id,
            phone_number_id=item.phone_number_id,
            template_name=item.template_name,
            template_code=item.template_code,
            template_category=item.template_category,
            template_language=item.template_language,
            send_count=item.send_count,
            delivered_count=item.delivered_count,
            delivery_rate=summary.delivery_rate,
            read_count=item.read_count,
            read_rate=summary.read_rate,
            read_rate_by_send=summary.read_rate_by_send,
            failed_count=item.failed_count,
            billable_count=item.billable_count,
            estimated_cost=float(item.estimated_cost or 0),
            estimated_cost_status=summary.estimated_cost_status,
            estimated_cost_note=summary.estimated_cost_note,
        )

    @staticmethod
    def _build_summary(
        *,
        send_count: int,
        delivered_count: int,
        read_count: int,
        failed_count: int,
        billable_count: int,
        estimated_cost: float,
    ) -> TemplateStatsSummary:
        delivery_rate = (delivered_count / send_count) if send_count else 0
        read_rate = (read_count / delivered_count) if delivered_count else 0
        read_rate_by_send = (read_count / send_count) if send_count else 0
        estimated_cost_status, estimated_cost_note = TemplateService._describe_estimated_cost(
            billable_count=billable_count,
            estimated_cost=estimated_cost,
        )
        return TemplateStatsSummary(
            send_count=send_count,
            delivered_count=delivered_count,
            delivery_rate=delivery_rate,
            read_count=read_count,
            read_rate=read_rate,
            read_rate_by_send=read_rate_by_send,
            failed_count=failed_count,
            billable_count=billable_count,
            estimated_cost=estimated_cost,
            estimated_cost_status=estimated_cost_status,
            estimated_cost_note=estimated_cost_note,
        )

    @staticmethod
    def _describe_estimated_cost(*, billable_count: int, estimated_cost: float) -> tuple[str, str | None]:
        if billable_count <= 0:
            return (
                "not_applicable",
                "当前筛选范围内没有 billable 模板发送，预估成本不适用。",
            )
        if estimated_cost <= 0:
            return (
                "missing_provider_cost",
                "存在 billable 模板发送，但 provider 没有返回 estimated_cost；当前 0 仅表示缺少费用回执。",
            )
        return (
            "provider_estimated",
            "当前仅累计 provider 明确返回的 estimated_cost，不代表最终结算账单。",
        )

    def _record_failed_send_attempt(
        self,
        *,
        template: MessageTemplate,
        conversation: object,
        payload: TemplateSendRequest,
        rendered_text: str,
        header_media_asset: MediaAsset | None,
        prepared_header_reference: PreparedMediaAssetReference | None = None,
        error_code: str,
        failure_reason: str,
        actor_type: str | None = None,
        actor_id: str | None = None,
    ) -> None:
        resolved_route_waba_id = self._resolve_template_send_waba_id(
            template=template,
            conversation=conversation,
        )
        conversation_phone_number_id = self._resolve_conversation_provider_phone_number_id(
            conversation
        )
        conversation_identity_payload = self._build_conversation_identity_payload(
            conversation=conversation,
            fallback_external_conversation_id=payload.conversation_id,
        )
        header_provider_media_id = (
            prepared_header_reference.provider_media_id
            if prepared_header_reference is not None
            else None
        )
        header_meta_media_id = (
            prepared_header_reference.meta_media_id
            if prepared_header_reference is not None
            else None
        )
        send_log = TemplateSendLog(
            account_id=payload.account_id,
            template_id=template.id,
            conversation_id=getattr(conversation, "id"),
            phone_number_id=conversation_phone_number_id,
            waba_id=resolved_route_waba_id,
            template_name=template.name,
            template_language=template.language,
            template_category=template.category,
            template_code=template.meta_template_id,
            header_media_asset_id=header_media_asset.id if header_media_asset is not None else None,
            header_media_asset_name=header_media_asset.name if header_media_asset is not None else None,
            header_media_asset_type=header_media_asset.asset_type if header_media_asset is not None else None,
            header_media_provider_media_id=header_provider_media_id,
            header_media_meta_media_id=header_meta_media_id,
            header_media_sync_status=(
                prepared_header_reference.provider_sync.sync_status
                if prepared_header_reference is not None
                else None
            ),
            wa_id=getattr(conversation, "customer_id"),
            message_id=None,
            idempotency_key=payload.idempotency_key,
            status="FAILED",
            error_code=error_code,
            sent_at=None,
            failed_at=utc_now(),
            last_status_at=utc_now(),
        )
        self._session.add(send_log)
        self._session.flush()
        self._template_stats_aggregator.record_send_log_created(send_log)
        if header_media_asset is not None:
            self._session.add(
                MediaAssetEvent(
                    account_id=payload.account_id,
                    asset_id=header_media_asset.id,
                    waba_id=resolved_route_waba_id,
                    phone_number_id=conversation_phone_number_id,
                    event_type="media_asset_template_send_failed",
                    provider_media_id=header_provider_media_id,
                    meta_media_id=header_meta_media_id,
                    created_by=actor_id or payload.agent_id,
                    payload={
                        **conversation_identity_payload,
                        "template_id": template.id,
                        "send_log_id": send_log.id,
                        "error_code": error_code,
                        "failure_reason": failure_reason,
                        "provider": self._messaging_provider.provider_name,
                        "waba_id": resolved_route_waba_id,
                        "phone_number_id": (
                            prepared_header_reference.phone_number_id
                            if prepared_header_reference is not None
                            else conversation_phone_number_id
                        ),
                        "provider_media_id": header_provider_media_id,
                        "meta_media_id": header_meta_media_id,
                        "sync_status": (
                            prepared_header_reference.provider_sync.sync_status
                            if prepared_header_reference is not None
                            else None
                        ),
                    },
                )
            )
        self._runtime_state.add_audit_log(
            account_id=payload.account_id,
            actor_type=actor_type or ("agent" if payload.agent_id else "system"),
            actor_id=actor_id or payload.agent_id,
            action="template_send_failed",
            target_type="message_template",
            target_id=template.id,
            payload={
                **conversation_identity_payload,
                "send_log_id": send_log.id,
                "waba_id": resolved_route_waba_id,
                "phone_number_id": conversation_phone_number_id,
                "idempotency_key": payload.idempotency_key,
                "wa_id": getattr(conversation, "customer_id"),
                "status": "FAILED",
                "error_code": error_code,
                "failure_reason": failure_reason,
                "provider": self._messaging_provider.provider_name,
                "delivered_text": rendered_text,
                "variables": payload.variables,
                "header_media_asset_id": header_media_asset.id if header_media_asset is not None else None,
                "header_media_asset_type": (
                    header_media_asset.asset_type if header_media_asset is not None else None
                ),
                "header_media_provider_media_id": header_provider_media_id,
                "header_media_meta_media_id": header_meta_media_id,
            },
        )
        business_template_sends_total.labels(
            provider=self._messaging_provider.provider_name,
            status="FAILED",
        ).inc()
        business_template_send_failures_total.labels(
            provider=self._messaging_provider.provider_name,
            reason=error_code,
        ).inc()
        self._session.commit()

    def _ensure_agent_can_send_template(
        self,
        conversation: object,
        agent_id: str | None,
    ) -> None:
        if agent_id is None:
            return
        management_mode = str(getattr(conversation, "management_mode"))
        assigned_agent = getattr(conversation, "assigned_agent", None)
        assigned_agent_id = self._runtime_state.get_public_agent_id(
            assigned_agent,
            fallback=getattr(conversation, "assigned_agent_id"),
        )
        if management_mode not in {"human_managed", "paused"}:
            raise PermissionError(
                "Operator template sends require the conversation to be in human_managed or paused mode."
            )
        if assigned_agent_id != agent_id:
            raise PermissionError(
                f"Agent '{agent_id}' cannot send a template for this conversation; it is assigned to '{assigned_agent_id}'."
            )

    def _require_template(self, template_id: str) -> MessageTemplate:
        template = self._session.scalars(
            select(MessageTemplate)
            .options(selectinload(MessageTemplate.waba_account))
            .where(MessageTemplate.id == template_id)
        ).first()
        if template is None:
            raise LookupError(f"Template '{template_id}' was not found.")
        return template

    def _ensure_template_account_allowed(
        self,
        *,
        template: MessageTemplate,
        allowed_account_ids: set[str] | None,
    ) -> None:
        if allowed_account_ids is None:
            return
        if template.account_id in allowed_account_ids:
            return
        raise PermissionError(
            f"Template '{template.id}' does not belong to an accessible account scope."
        )

    def _require_template_waba(self, template: MessageTemplate) -> WhatsAppBusinessAccount:
        resolved_waba_id = self._resolve_template_waba_id(template)
        if resolved_waba_id is not None:
            waba_account = self._require_waba_for_account(
                account_id=template.account_id,
                waba_id=resolved_waba_id,
            )
            template.waba_account = waba_account
            template.waba_account_id = waba_account.id
            template.waba_id = waba_account.waba_id
            return waba_account
        if template.waba_account is not None:
            return template.waba_account
        if template.waba_account_id is None:
            raise ValueError(f"Template '{template.id}' is not bound to a WABA.")
        waba_account = self._session.get(WhatsAppBusinessAccount, template.waba_account_id)
        if waba_account is None:
            raise ValueError(f"Template '{template.id}' has an invalid WABA binding.")
        return waba_account

    def _ensure_template_route_matches_conversation(
        self,
        *,
        template: MessageTemplate,
        conversation: object,
    ) -> None:
        conversation_phone = getattr(conversation, "phone_number", None)
        if conversation_phone is None:
            if self._messaging_provider.provider_name == "whatsapp":
                raise ValueError(
                    "WhatsApp template sends require the conversation to be bound to a Phone-Number-ID."
                )
            return
        conversation_waba_id = self._resolve_phone_waba_id(conversation_phone)
        if conversation_waba_id is None:
            raise ValueError(
                "Conversation phone route is missing its WABA binding and cannot be used for template sends."
            )
        template_waba = self._require_template_waba(template)
        if conversation_waba_id != template_waba.waba_id:
            raise ValueError(
                f"Template '{template.id}' is bound to WABA '{template_waba.waba_id}', "
                f"but conversation '{getattr(conversation, 'external_conversation_id', 'unknown')}' routes "
                f"through WABA '{conversation_waba_id}'."
            )

    def _require_waba_for_account(
        self,
        account_id: str,
        waba_id: str | None,
    ) -> WhatsAppBusinessAccount | None:
        if waba_id is None:
            return None
        waba_account = self._session.scalars(
            select(WhatsAppBusinessAccount).where(
                WhatsAppBusinessAccount.account_id == account_id,
                WhatsAppBusinessAccount.waba_id == waba_id,
            )
        ).first()
        if waba_account is None:
            raise ValueError(f"WABA '{waba_id}' for account '{account_id}' was not found.")
        return waba_account

    def _extract_sample_variables(self, template: MessageTemplate) -> dict[str, str]:
        components = template.components or {}
        sample_variables = components.get("sample_variables")
        if isinstance(sample_variables, dict):
            return {
                str(key): str(value)
                for key, value in sample_variables.items()
            }
        return {}

    def _resolve_header_media_asset_for_draft(
        self,
        *,
        account_id: str,
        waba_id: str | None,
        header_media_asset_id: str | None,
    ) -> MediaAsset | None:
        if not header_media_asset_id:
            return None
        asset = self._require_media_asset(asset_id=header_media_asset_id)
        self._validate_header_media_asset(
            asset=asset,
            account_id=account_id,
            waba_id=waba_id,
            phone_number_id=None,
        )
        return asset

    def _build_template_components_for_draft(
        self,
        *,
        account_id: str,
        waba_id: str | None,
        body_text: str,
        header_text: str | None,
        header_media_asset_id: str | None,
        header_media_handle: str | None,
        footer_text: str | None,
        sample_variables: dict[str, str] | None,
    ) -> tuple[dict[str, object], MediaAsset | None]:
        if header_text and header_media_asset_id:
            raise ValueError("Template header_text and header_media_asset_id cannot both be set.")
        if header_media_handle and not header_media_asset_id:
            raise ValueError("Template header_media_handle requires header_media_asset_id.")
        header_media_asset = self._resolve_header_media_asset_for_draft(
            account_id=account_id,
            waba_id=waba_id,
            header_media_asset_id=header_media_asset_id,
        )
        return (
            {
                "body_text": body_text,
                "header_text": header_text,
                "header_media_asset_id": (
                    header_media_asset.id if header_media_asset is not None else None
                ),
                "header_media_asset_name": (
                    header_media_asset.name if header_media_asset is not None else None
                ),
                "header_media_asset_type": (
                    header_media_asset.asset_type if header_media_asset is not None else None
                ),
                "header_media_handle": header_media_handle,
                "footer_text": footer_text,
                "sample_variables": sample_variables or {},
            },
            header_media_asset,
        )

    def _resolve_header_media_asset_for_send(
        self,
        *,
        template: MessageTemplate,
        conversation: object,
    ) -> MediaAsset | None:
        components = template.components or {}
        raw_asset_id = components.get("header_media_asset_id")
        if not isinstance(raw_asset_id, str) or not raw_asset_id:
            return None
        asset = self._require_media_asset(asset_id=raw_asset_id)
        self._validate_header_media_asset(
            asset=asset,
            account_id=template.account_id,
            waba_id=self._resolve_template_send_waba_id(
                template=template,
                conversation=conversation,
            ),
            phone_number_id=(
                conversation.phone_number.phone_number_id
                if getattr(conversation, "phone_number", None) is not None
                else None
            ),
        )
        return asset

    def _require_media_asset(self, *, asset_id: str) -> MediaAsset:
        asset = self._session.scalars(
            select(MediaAsset)
            .options(selectinload(MediaAsset.phone_number))
            .where(MediaAsset.id == asset_id)
        ).first()
        if asset is None:
            raise ValueError(f"Media asset '{asset_id}' was not found.")
        return asset

    @staticmethod
    def _validate_header_media_asset(
        *,
        asset: MediaAsset,
        account_id: str,
        waba_id: str | None,
        phone_number_id: str | None,
    ) -> None:
        if asset.account_id != account_id:
            raise ValueError(
                f"Media asset '{asset.id}' does not belong to account '{account_id}'."
            )
        if asset.asset_type not in {"image", "video", "document"}:
            raise ValueError(
                f"Media asset '{asset.id}' with type '{asset.asset_type}' cannot be used as template header media."
            )
        if not asset.is_active:
            raise ValueError(f"Media asset '{asset.id}' is inactive.")
        if waba_id and asset.waba_id and asset.waba_id != waba_id:
            raise ValueError(
                f"Media asset '{asset.id}' is bound to WABA '{asset.waba_id}', not '{waba_id}'."
            )
        asset_phone_number_id = (
            asset.phone_number.phone_number_id
            if asset.phone_number is not None
            else None
        )
        if phone_number_id and asset_phone_number_id and asset_phone_number_id != phone_number_id:
            raise ValueError(
                f"Media asset '{asset.id}' is bound to Phone-Number-ID '{asset_phone_number_id}', not '{phone_number_id}'."
            )

    def _render_template(
        self,
        body_text: str,
        variables: dict[str, str],
        sample_variables: dict[str, str],
    ) -> str:
        merged_variables = {**sample_variables, **variables}

        def replace(match: re.Match[str]) -> str:
            key = match.group(1)
            return merged_variables.get(key, match.group(0))

        return PLACEHOLDER_PATTERN.sub(replace, body_text)

    def _find_send_log_by_idempotency_key(
        self,
        *,
        account_id: str,
        template_id: str,
        conversation_id: str,
        idempotency_key: str | None,
    ) -> TemplateSendLog | None:
        if not idempotency_key:
            return None
        return self._session.scalars(
            select(TemplateSendLog)
            .options(selectinload(TemplateSendLog.conversation))
            .where(
                TemplateSendLog.account_id == account_id,
                TemplateSendLog.idempotency_key == idempotency_key,
            )
        ).first()

    def _find_template_for_remote(
        self,
        *,
        account_id: str,
        waba_id: str,
        remote_template: TemplateRegistryRemoteTemplate,
    ) -> MessageTemplate | None:
        if remote_template.provider_template_id:
            template = self._session.scalars(
                select(MessageTemplate)
                .options(selectinload(MessageTemplate.waba_account))
                .where(
                    MessageTemplate.account_id == account_id,
                    self._template_waba_match_clause(waba_id),
                    MessageTemplate.meta_template_id == remote_template.provider_template_id,
                )
            ).first()
            if template is not None:
                return template
        return self._session.scalars(
            select(MessageTemplate)
            .options(selectinload(MessageTemplate.waba_account))
            .where(
                MessageTemplate.account_id == account_id,
                self._template_waba_match_clause(waba_id),
                MessageTemplate.name == remote_template.name,
                MessageTemplate.language == remote_template.language,
            )
        ).first()

    def _find_template_for_webhook(
        self,
        *,
        account_id: str,
        waba_id: str,
        meta_template_id: str | None,
        name: str | None,
        language: str | None,
    ) -> MessageTemplate | None:
        if meta_template_id:
            template = self._session.scalars(
                select(MessageTemplate)
                .options(selectinload(MessageTemplate.waba_account))
                .where(
                    MessageTemplate.account_id == account_id,
                    self._template_waba_match_clause(waba_id),
                    MessageTemplate.meta_template_id == meta_template_id,
                )
            ).first()
            if template is not None:
                return template
        if not name or not language:
            return None
        return self._session.scalars(
            select(MessageTemplate)
            .options(selectinload(MessageTemplate.waba_account))
            .where(
                MessageTemplate.account_id == account_id,
                self._template_waba_match_clause(waba_id),
                MessageTemplate.name == name,
                MessageTemplate.language == language,
            )
        ).first()

    @staticmethod
    def _normalize_template_webhook_status(status: str | None) -> TemplateStatus | None:
        if status is None:
            return None
        normalized = status.strip().upper()
        if normalized in {"PENDING", "APPROVED", "REJECTED", "DRAFT", "DISABLED", "PAUSED"}:
            return cast(TemplateStatus, normalized)
        return None

    def _resolve_template_send_waba_id(
        self,
        *,
        template: MessageTemplate,
        conversation: object,
    ) -> str | None:
        conversation_waba_id = self._resolve_conversation_waba_id(conversation)
        if conversation_waba_id is not None:
            return conversation_waba_id
        return self._resolve_template_waba_id(template)

    @staticmethod
    def _resolve_conversation_waba_id(conversation: object) -> str | None:
        return TemplateService._resolve_phone_waba_id(getattr(conversation, "phone_number", None))

    @staticmethod
    def _resolve_conversation_provider_phone_number_id(conversation: object) -> str | None:
        phone_number = getattr(conversation, "phone_number", None)
        provider_phone_number_id = getattr(phone_number, "phone_number_id", None)
        if isinstance(provider_phone_number_id, str) and provider_phone_number_id:
            return provider_phone_number_id
        return None

    @classmethod
    def _build_conversation_identity_payload(
        cls,
        *,
        conversation: object,
        fallback_external_conversation_id: str | None = None,
    ) -> dict[str, str | None]:
        external_conversation_id = cls._resolve_external_conversation_id(
            conversation,
            fallback_external_conversation_id=fallback_external_conversation_id,
        )
        internal_conversation_id = getattr(conversation, "id", None)
        return {
            "conversation_id": external_conversation_id,
            "external_conversation_id": external_conversation_id,
            "internal_conversation_id": (
                internal_conversation_id if isinstance(internal_conversation_id, str) else None
            ),
        }

    @staticmethod
    def _resolve_external_conversation_id(
        conversation: object,
        *,
        fallback_external_conversation_id: str | None = None,
    ) -> str | None:
        external_conversation_id = getattr(conversation, "external_conversation_id", None)
        if isinstance(external_conversation_id, str) and external_conversation_id:
            return external_conversation_id
        return fallback_external_conversation_id

    def _resolve_template_waba_id(self, template: MessageTemplate) -> str | None:
        if template.waba_id:
            return template.waba_id
        if template.waba_account is not None and template.waba_account.waba_id:
            return template.waba_account.waba_id
        if template.waba_account_id is None:
            return None
        waba_account = self._session.get(WhatsAppBusinessAccount, template.waba_account_id)
        if waba_account is None or not waba_account.waba_id:
            return None
        return waba_account.waba_id

    @staticmethod
    def _resolve_phone_waba_id(phone_number: WhatsAppPhoneNumber | None) -> str | None:
        if phone_number is None:
            return None
        if phone_number.waba_id:
            return phone_number.waba_id
        if phone_number.waba_account is not None and phone_number.waba_account.waba_id:
            return phone_number.waba_account.waba_id
        return None

    def _serialize_template(self, template: MessageTemplate) -> MessageTemplateView:
        components = template.components or {}
        sample_variables = components.get("sample_variables")
        return MessageTemplateView(
            template_id=template.id,
            account_id=template.account_id,
            waba_id=self._resolve_template_waba_id(template),
            name=template.name,
            language=template.language,
            category=template.category,
            status=template.status,
            meta_template_id=template.meta_template_id,
            rejected_reason=template.rejected_reason,
            body_text=str(components.get("body_text") or ""),
            header_text=(
                str(components.get("header_text"))
                if components.get("header_text") is not None
                else None
            ),
            header_media_asset_id=(
                str(components.get("header_media_asset_id"))
                if components.get("header_media_asset_id") is not None
                else None
            ),
            header_media_asset_name=(
                str(components.get("header_media_asset_name"))
                if components.get("header_media_asset_name") is not None
                else None
            ),
            header_media_asset_type=(
                str(
                    components.get("header_media_asset_type")
                    or components.get("header_media_type")
                )
                if (
                    components.get("header_media_asset_type") is not None
                    or components.get("header_media_type") is not None
                )
                else None
            ),
            header_media_handle=(
                str(components.get("header_media_handle"))
                if components.get("header_media_handle") is not None
                else None
            ),
            footer_text=(
                str(components.get("footer_text"))
                if components.get("footer_text") is not None
                else None
            ),
            sample_variables=(
                {str(key): str(value) for key, value in sample_variables.items()}
                if isinstance(sample_variables, dict)
                else {}
            ),
            submitted_at=template.submitted_at.isoformat() if template.submitted_at is not None else None,
            last_synced_at=(
                template.last_synced_at.isoformat() if template.last_synced_at is not None else None
            ),
            created_at=template.created_at.isoformat(),
            updated_at=template.updated_at.isoformat(),
        )

    def _template_waba_match_clause(self, waba_id: str) -> object:
        return or_(
            MessageTemplate.waba_id == waba_id,
            (
                MessageTemplate.waba_id.is_(None)
                & MessageTemplate.waba_account.has(WhatsAppBusinessAccount.waba_id == waba_id)
            ),
        )

    def _serialize_send_log(
        self,
        log: TemplateSendLog,
        *,
        message_scope: dict[str, str | None] | None = None,
    ) -> TemplateSendLogView:
        conversation = log.conversation
        template = log.template
        external_conversation_id = (
            conversation.external_conversation_id if conversation is not None else None
        )
        return TemplateSendLogView(
            id=log.id,
            account_id=log.account_id,
            template_id=log.template_id,
            waba_id=self._resolve_send_log_waba_id(
                log,
                conversation=conversation,
                message_scope=message_scope,
            ),
            template_name=log.template_name or (template.name if template is not None else None),
            template_language=log.template_language or (template.language if template is not None else None),
            template_category=log.template_category or (template.category if template is not None else None),
            template_code=log.template_code or (template.meta_template_id if template is not None else None),
            header_media_asset_id=log.header_media_asset_id,
            header_media_asset_name=log.header_media_asset_name,
            header_media_asset_type=log.header_media_asset_type,
            header_media_provider_media_id=(
                log.header_media_provider_media_id or log.header_media_meta_media_id
            ),
            header_media_meta_media_id=log.header_media_meta_media_id,
            header_media_sync_status=log.header_media_sync_status,
            conversation_id=external_conversation_id,
            external_conversation_id=external_conversation_id,
            internal_conversation_id=log.conversation_id,
            phone_number_id=self._resolve_send_log_provider_phone_number_id(
                log,
                conversation=conversation,
                message_scope=message_scope,
            ),
            wa_id=log.wa_id,
            message_id=log.message_id,
            idempotency_key=log.idempotency_key,
            status=log.status,
            error_code=log.error_code,
            conversation_origin_type=log.conversation_origin_type,
            conversation_category=log.conversation_category,
            pricing_model=log.pricing_model,
            billable=log.billable,
            estimated_cost=float(log.estimated_cost or 0),
            sent_at=log.sent_at.isoformat() if log.sent_at is not None else None,
            delivered_at=log.delivered_at.isoformat() if log.delivered_at is not None else None,
            read_at=log.read_at.isoformat() if log.read_at is not None else None,
            failed_at=log.failed_at.isoformat() if log.failed_at is not None else None,
            last_status_at=log.last_status_at.isoformat() if log.last_status_at is not None else None,
            created_at=log.created_at.isoformat(),
        )

    def _resolve_send_log_provider_phone_number_id(
        self,
        log: TemplateSendLog,
        *,
        conversation: Conversation | None = None,
        message_scope: dict[str, str | None] | None = None,
    ) -> str | None:
        snapshot_phone_number_id = self._pick_send_log_message_scope_value(
            message_scope=message_scope,
            key="phone_number_id",
        )
        if snapshot_phone_number_id is not None:
            return snapshot_phone_number_id
        if log.phone_number is not None:
            return log.phone_number.phone_number_id
        resolved_conversation = conversation or log.conversation
        if resolved_conversation is not None and resolved_conversation.phone_number is not None:
            return resolved_conversation.phone_number.phone_number_id
        if log.phone_number_id is None:
            return None
        phone_number = self._resolve_phone_number_by_local_or_provider_id(
            account_id=log.account_id,
            phone_number_id=log.phone_number_id,
        )
        if phone_number is not None:
            return phone_number.phone_number_id
        return log.phone_number_id

    def _resolve_send_log_waba_id(
        self,
        log: TemplateSendLog,
        *,
        conversation: Conversation | None = None,
        message_scope: dict[str, str | None] | None = None,
    ) -> str | None:
        snapshot_waba_id = self._pick_send_log_message_scope_value(
            message_scope=message_scope,
            key="waba_id",
        )
        if snapshot_waba_id is not None:
            return snapshot_waba_id
        if log.waba_id is not None:
            return log.waba_id
        if log.phone_number is not None and log.phone_number.waba_id:
            return log.phone_number.waba_id
        if log.phone_number is not None and log.phone_number.waba_account is not None:
            return log.phone_number.waba_account.waba_id
        resolved_conversation = conversation or log.conversation
        if resolved_conversation is not None and resolved_conversation.phone_number is not None:
            conversation_phone_number = resolved_conversation.phone_number
            if conversation_phone_number.waba_id:
                return conversation_phone_number.waba_id
            if conversation_phone_number.waba_account is not None:
                return conversation_phone_number.waba_account.waba_id
        if log.phone_number_id is None:
            return None
        phone_number = self._resolve_phone_number_by_local_or_provider_id(
            account_id=log.account_id,
            phone_number_id=log.phone_number_id,
        )
        if phone_number is not None and phone_number.waba_id:
            return phone_number.waba_id
        if phone_number is not None and phone_number.waba_account is not None:
            return phone_number.waba_account.waba_id
        return None

    def _resolve_send_log_phone_number_id_for_scope_filter(
        self,
        log: TemplateSendLog,
        *,
        message_scope: dict[str, str | None] | None = None,
    ) -> str | None:
        snapshot_phone_number_id = self._pick_send_log_message_scope_value(
            message_scope=message_scope,
            key="phone_number_id",
        )
        if snapshot_phone_number_id is not None:
            return snapshot_phone_number_id
        if log.phone_number_id is None:
            return None
        phone_number = self._session.get(WhatsAppPhoneNumber, log.phone_number_id)
        if phone_number is not None and phone_number.id == log.phone_number_id:
            return None
        return log.phone_number_id

    def _resolve_phone_number_by_local_or_provider_id(
        self,
        *,
        account_id: str,
        phone_number_id: str,
    ) -> WhatsAppPhoneNumber | None:
        phone_number = self._session.get(WhatsAppPhoneNumber, phone_number_id)
        if phone_number is not None:
            return phone_number
        return self._session.scalars(
            select(WhatsAppPhoneNumber).where(
                WhatsAppPhoneNumber.account_id == account_id,
                WhatsAppPhoneNumber.phone_number_id == phone_number_id,
            )
        ).first()

    def _load_send_log_message_scopes(
        self,
        logs: list[TemplateSendLog],
    ) -> dict[str, dict[str, str | None]]:
        message_ids = {log.message_id for log in logs if isinstance(log.message_id, str) and log.message_id}
        if not message_ids:
            return {}
        account_ids = {log.account_id for log in logs}
        rows = self._session.execute(
            select(Message.id, Message.provider_message_id, Message.payload).where(
                Message.account_id.in_(account_ids),
                or_(
                    Message.id.in_(message_ids),
                    Message.provider_message_id.in_(message_ids),
                ),
            )
        ).all()
        scope_by_message_key: dict[str, dict[str, str | None]] = {}
        for message_id, provider_message_id, payload in rows:
            if not isinstance(payload, dict):
                continue
            scope = {
                "waba_id": self._pick_nested_payload_string(payload, "waba_id"),
                "phone_number_id": self._pick_nested_payload_string(payload, "phone_number_id"),
            }
            if message_id:
                scope_by_message_key[message_id] = scope
            if provider_message_id:
                scope_by_message_key[provider_message_id] = scope
        return {
            log.id: scope_by_message_key[log.message_id]
            for log in logs
            if isinstance(log.message_id, str) and log.message_id in scope_by_message_key
        }

    def _matches_send_log_scope_filters(
        self,
        *,
        log: TemplateSendLog,
        waba_id: str | None,
        phone_number_id: str | None,
        conversation: Conversation | None,
        message_scope: dict[str, str | None] | None,
    ) -> bool:
        resolved_waba_id = self._resolve_send_log_waba_id(
            log,
            conversation=conversation,
            message_scope=message_scope,
        )
        if waba_id is not None and resolved_waba_id != waba_id:
            return False
        resolved_phone_number_id = self._resolve_send_log_phone_number_id_for_scope_filter(
            log,
            message_scope=message_scope,
        )
        if phone_number_id is not None and resolved_phone_number_id != phone_number_id:
            return False
        return True

    @staticmethod
    def _pick_send_log_message_scope_value(
        *,
        message_scope: dict[str, str | None] | None,
        key: str,
    ) -> str | None:
        if not isinstance(message_scope, dict):
            return None
        value = message_scope.get(key)
        if isinstance(value, str) and value:
            return value
        return None

    @staticmethod
    def _pick_payload_string(
        payload: dict[str, object] | None,
        key: str,
    ) -> str | None:
        if not isinstance(payload, dict):
            return None
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
        return None

    @classmethod
    def _pick_nested_payload_string(
        cls,
        payload: dict[str, object] | None,
        key: str,
    ) -> str | None:
        if not isinstance(payload, dict):
            return None
        direct_value = cls._pick_payload_string(payload, key)
        if direct_value is not None:
            return direct_value
        metadata = payload.get("metadata")
        if isinstance(metadata, dict):
            metadata_value = cls._pick_payload_string(metadata, key)
            if metadata_value is not None:
                return metadata_value
        for candidate_key in ("provider_payload", "raw_payload"):
            candidate = payload.get(candidate_key)
            if not isinstance(candidate, dict):
                continue
            nested_value = cls._pick_nested_payload_string(candidate, key)
            if nested_value is not None:
                return nested_value
        return None
