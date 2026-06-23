from collections.abc import Mapping
import re

import httpx
import structlog

from app.providers.template_registry.base import TemplateRegistryProvider
from app.schemas.template_registry import (
    TemplateRegistryRemoteTemplate,
    TemplateRegistrySubmitRequest,
    TemplateRegistrySubmitResult,
    TemplateRegistrySyncResult,
)

logger = structlog.get_logger(__name__)


class WhatsAppTemplateRegistryProvider(TemplateRegistryProvider):
    provider_name = "whatsapp"
    _placeholder_pattern = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")

    def __init__(
        self,
        *,
        api_base: str = "https://graph.facebook.com",
        api_version: str = "v20.0",
        timeout_seconds: int = 30,
        max_sync_pages: int = 10,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_base = api_base.rstrip("/")
        self._api_version = api_version
        self._timeout_seconds = timeout_seconds
        self._max_sync_pages = max_sync_pages
        self._client = client

    async def submit_template(
        self,
        payload: TemplateRegistrySubmitRequest,
    ) -> TemplateRegistrySubmitResult:
        if not payload.access_token:
            raise ValueError("WhatsApp template submit requires access_token.")
        endpoint = f"{self._api_base}/{self._api_version}/{payload.waba_id}/message_templates"
        response_json = await self._request_json(
            method="POST",
            endpoint=endpoint,
            access_token=payload.access_token,
            params=None,
            body={
                "name": payload.name,
                "language": payload.language,
                "category": payload.category,
                "components": self._serialize_components(payload.components),
            },
        )
        provider_template_id = self._extract_template_id(response_json)
        remote_status = self._extract_status(response_json, fallback="PENDING")
        remote_template = TemplateRegistryRemoteTemplate(
            provider_template_id=provider_template_id,
            name=payload.name,
            language=payload.language,
            category=payload.category,
            status=remote_status,
            rejected_reason=self._extract_rejected_reason(response_json),
            components=payload.components,
            raw_payload=response_json,
        )
        return TemplateRegistrySubmitResult(
            provider_name=self.provider_name,
            action="submitted",
            remote_status=remote_status,
            provider_template_id=provider_template_id,
            remote_template=remote_template,
            raw_response=response_json,
        )

    async def sync_templates(
        self,
        *,
        account_id: str,
        waba_id: str,
        access_token: str | None,
    ) -> TemplateRegistrySyncResult:
        if not access_token:
            raise ValueError("WhatsApp template sync requires access_token.")
        endpoint = f"{self._api_base}/{self._api_version}/{waba_id}/message_templates"
        remote_templates: list[TemplateRegistryRemoteTemplate] = []
        params: dict[str, str] | None = {"limit": "200"}
        page_count = 0
        while endpoint and page_count < self._max_sync_pages:
            response_json = await self._request_json(
                method="GET",
                endpoint=endpoint,
                access_token=access_token,
                params=params,
                body=None,
            )
            items = response_json.get("data")
            if isinstance(items, list):
                remote_templates.extend(
                    self._deserialize_remote_template(item)
                    for item in items
                    if isinstance(item, Mapping)
                )
            page_count += 1
            endpoint = self._extract_next_page_url(response_json) or ""
            params = None
        if endpoint:
            logger.warning(
                "whatsapp_template_registry_sync_page_limit_reached",
                account_id=account_id,
                waba_id=waba_id,
                max_sync_pages=self._max_sync_pages,
            )
        return TemplateRegistrySyncResult(
            provider_name=self.provider_name,
            templates=remote_templates,
        )

    async def _request_json(
        self,
        *,
        method: str,
        endpoint: str,
        access_token: str,
        params: dict[str, str] | None,
        body: dict[str, object] | None,
    ) -> dict[str, object]:
        headers = {"Authorization": f"Bearer {access_token}"}
        try:
            if self._client is not None:
                response = await self._client.request(
                    method,
                    endpoint,
                    headers=headers,
                    params=params,
                    json=body,
                )
            else:
                async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                    response = await client.request(
                        method,
                        endpoint,
                        headers=headers,
                        params=params,
                        json=body,
                    )
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "whatsapp_template_registry_request_http_error",
                method=method,
                endpoint=endpoint,
                status_code=exc.response.status_code,
            )
            raise RuntimeError(
                f"WhatsApp template registry request failed with status {exc.response.status_code}."
            ) from exc
        except httpx.RequestError as exc:
            logger.warning(
                "whatsapp_template_registry_request_failed",
                method=method,
                endpoint=endpoint,
                error=str(exc),
            )
            raise RuntimeError("WhatsApp template registry request failed.") from exc

        if not isinstance(payload, dict):
            raise RuntimeError("WhatsApp template registry request returned a non-object payload.")
        return payload

    @staticmethod
    def _serialize_components(components: dict[str, object]) -> list[dict[str, object]]:
        body_text = components.get("body_text")
        header_text = components.get("header_text")
        header_media_type = components.get("header_media_asset_type") or components.get(
            "header_media_type"
        )
        header_media_handle = components.get("header_media_handle")
        footer_text = components.get("footer_text")
        sample_variables = (
            components.get("sample_variables")
            if isinstance(components.get("sample_variables"), Mapping)
            else {}
        )
        serialized: list[dict[str, object]] = []
        if header_text:
            transformed_header_text, header_examples = (
                WhatsAppTemplateRegistryProvider._transform_template_text_for_meta(
                    text=str(header_text),
                    sample_variables=sample_variables,
                )
            )
            header_component: dict[str, object] = {
                "type": "HEADER",
                "format": "TEXT",
                "text": transformed_header_text,
            }
            if header_examples:
                header_component["example"] = {
                    "header_text": [header_examples[0]],
                }
            serialized.append(header_component)
        elif header_media_type:
            header_component: dict[str, object] = {
                "type": "HEADER",
                "format": str(header_media_type).upper(),
            }
            if header_media_handle:
                header_component["example"] = {
                    "header_handle": [str(header_media_handle)],
                }
            serialized.append(header_component)
        transformed_body_text, body_examples = (
            WhatsAppTemplateRegistryProvider._transform_template_text_for_meta(
                text=str(body_text or ""),
                sample_variables=sample_variables,
            )
        )
        body_component: dict[str, object] = {"type": "BODY", "text": transformed_body_text}
        if body_examples:
            body_component["example"] = {"body_text": [body_examples]}
        serialized.append(body_component)
        if footer_text:
            serialized.append({"type": "FOOTER", "text": str(footer_text)})
        return serialized

    @classmethod
    def _transform_template_text_for_meta(
        cls,
        *,
        text: str,
        sample_variables: Mapping[object, object],
    ) -> tuple[str, list[str]]:
        if not text:
            return text, []

        placeholder_order: list[str] = []
        placeholder_indexes: dict[str, int] = {}

        def replace(match: re.Match[str]) -> str:
            placeholder_name = match.group(1)
            if placeholder_name.isdigit():
                if placeholder_name not in placeholder_indexes:
                    placeholder_indexes[placeholder_name] = len(placeholder_order) + 1
                    placeholder_order.append(placeholder_name)
                return f"{{{{{placeholder_name}}}}}"
            if placeholder_name not in placeholder_indexes:
                placeholder_indexes[placeholder_name] = len(placeholder_order) + 1
                placeholder_order.append(placeholder_name)
            return f"{{{{{placeholder_indexes[placeholder_name]}}}}}"

        transformed_text = cls._placeholder_pattern.sub(replace, text)
        if not placeholder_order:
            return transformed_text, []

        examples = [
            str(sample_variables.get(name) or name)
            for name in placeholder_order
        ]
        return transformed_text, examples

    @staticmethod
    def _deserialize_remote_template(item: Mapping[str, object]) -> TemplateRegistryRemoteTemplate:
        components_raw = item.get("components")
        components = {}
        if isinstance(components_raw, list):
            for component in components_raw:
                if not isinstance(component, Mapping):
                    continue
                component_type = str(component.get("type", "")).upper()
                if component_type == "BODY":
                    components["body_text"] = str(component.get("text") or "")
                elif component_type == "HEADER":
                    format_value = str(component.get("format") or "TEXT").upper()
                    if format_value == "TEXT":
                        components["header_text"] = str(component.get("text") or "")
                    elif format_value in {"IMAGE", "VIDEO", "DOCUMENT"}:
                        components["header_media_type"] = format_value.lower()
                        example = component.get("example")
                        if isinstance(example, Mapping):
                            header_handle = example.get("header_handle")
                            if isinstance(header_handle, list) and header_handle:
                                components["header_media_handle"] = str(header_handle[0])
                elif component_type == "FOOTER":
                    components["footer_text"] = str(component.get("text") or "")
        language = item.get("language")
        if isinstance(language, Mapping):
            language = language.get("code")
        return TemplateRegistryRemoteTemplate(
            provider_template_id=(
                str(item.get("id")) if item.get("id") is not None else None
            ),
            name=str(item.get("name") or ""),
            language=str(language or ""),
            category=str(item.get("category") or "UTILITY"),
            status=WhatsAppTemplateRegistryProvider._extract_status(item, fallback="PENDING"),
            rejected_reason=WhatsAppTemplateRegistryProvider._extract_rejected_reason(item),
            components=components,
            raw_payload=dict(item),
        )

    @staticmethod
    def _extract_template_id(payload: Mapping[str, object]) -> str | None:
        template_id = payload.get("id")
        return str(template_id) if template_id is not None else None

    @staticmethod
    def _extract_status(payload: Mapping[str, object], fallback: str) -> str:
        status = payload.get("status")
        if status is None:
            return fallback
        normalized = str(status).upper()
        if normalized in {"PENDING", "APPROVED", "REJECTED", "DRAFT", "DISABLED", "PAUSED"}:
            return normalized
        return fallback

    @staticmethod
    def _extract_next_page_url(payload: Mapping[str, object]) -> str | None:
        paging = payload.get("paging")
        if not isinstance(paging, Mapping):
            return None
        next_page = paging.get("next")
        if isinstance(next_page, str) and next_page.strip():
            return next_page.strip()
        return None

    @staticmethod
    def _extract_rejected_reason(payload: Mapping[str, object]) -> str | None:
        reason = payload.get("rejected_reason")
        if reason is None:
            return None
        return str(reason)
