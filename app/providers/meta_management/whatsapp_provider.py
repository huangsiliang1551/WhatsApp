from collections.abc import Mapping

import httpx
import structlog

from app.providers.meta_management.base import (
    MetaEmbeddedSignupCompletionCommand,
    MetaEmbeddedSignupCompletionResult,
    MetaManagementProvider,
    MetaManagementProviderError,
    MetaPhoneNumberRecord,
    MetaPhoneNumberSyncCommand,
    MetaPhoneNumberSyncResult,
    MetaWebhookSubscriptionCommand,
    MetaWebhookSubscriptionResult,
)

logger = structlog.get_logger(__name__)


class WhatsAppMetaManagementProvider(MetaManagementProvider):
    provider_name = "whatsapp"

    def __init__(
        self,
        *,
        api_base: str = "https://graph.facebook.com",
        api_version: str = "v20.0",
        app_id: str = "",
        app_secret: str = "",
        subscribed_fields: str = "messages",
        timeout_seconds: int = 30,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_base = api_base.rstrip("/")
        self._api_version = api_version
        self._app_id = app_id
        self._app_secret = app_secret
        self._subscribed_fields = subscribed_fields
        self._timeout_seconds = timeout_seconds
        self._client = client

    async def health_check(
        self,
        waba_id: str,
        access_token: str,
    ) -> dict[str, object]:
        try:
            client = self._client or httpx.AsyncClient(timeout=self._timeout_seconds)
            url = f"{self._api_base}/{self._api_version}/{waba_id}"
            resp = await client.get(url, params={"access_token": access_token, "fields": "id,name,timezone_id"})
            data = resp.json()
            if resp.status_code >= 400:
                return {"ok": False, "error_kind": "meta_api_error", "status_code": resp.status_code, "error": data.get("error", {}), "waba_id": waba_id}
            # owner_business is an edge, query separately
            pid = ""
            try:
                ob_url = f"{self._api_base}/{self._api_version}/{waba_id}/owner_business"
                ob_resp = await client.get(ob_url, params={"access_token": access_token})
                ob_data = ob_resp.json()
                pid = ob_data.get("id", "") if isinstance(ob_data, dict) else ""
            except Exception:
                pass
            return {"ok": True, "waba_id": waba_id, "name": data.get("name", ""), "owner_business": pid}
        except httpx.ConnectError as exc:
            return {"ok": False, "error_kind": "network_unreachable", "error": str(exc), "waba_id": waba_id}
        except httpx.ConnectTimeout as exc:
            return {"ok": False, "error_kind": "network_timeout", "error": str(exc), "waba_id": waba_id}
        except httpx.ReadTimeout as exc:
            return {"ok": False, "error_kind": "network_timeout", "error": str(exc), "waba_id": waba_id}
        except Exception as exc:
            return {"ok": False, "error_kind": "unknown", "error": str(exc), "waba_id": waba_id}

    async def subscribe_webhook(
        self,
        payload: MetaWebhookSubscriptionCommand,
    ) -> MetaWebhookSubscriptionResult:
        logger.info(
            "meta_webhook_subscribe_started",
            account_id=payload.account_id,
            waba_id=payload.waba_id,
        )
        response_json = await self._request_json(
            method="POST",
            endpoint=self._build_endpoint(payload.waba_id, "subscribed_apps"),
            access_token=payload.access_token,
            params={"subscribed_fields": self._subscribed_fields},
            body=None,
        )
        remote_confirmed = self._coerce_success(response_json)
        logger.info(
            "meta_webhook_subscribe_completed",
            account_id=payload.account_id,
            waba_id=payload.waba_id,
            remote_confirmed=remote_confirmed,
        )
        return MetaWebhookSubscriptionResult(
            provider_name=self.provider_name,
            subscription_status="remote_subscribed" if remote_confirmed else "remote_pending",
            remote_confirmed=remote_confirmed,
            raw_response={
                "graph_response": response_json,
                "callback_url": payload.callback_url,
                "verify_token_present": bool(payload.verify_token),
                "app_id": payload.app_id,
            },
            message=(
                "Webhook subscription confirmed by Meta. "
                "Webhook verification and signed delivery still remain pending until the "
                "verify challenge succeeds for the callback URL."
                if remote_confirmed
                else (
                    "Webhook subscription request was accepted but not explicitly confirmed by Meta. "
                    "Webhook verification and signed delivery are still pending."
                )
            ),
        )

    async def sync_phone_numbers(
        self,
        payload: MetaPhoneNumberSyncCommand,
    ) -> MetaPhoneNumberSyncResult:
        logger.info(
            "meta_phone_number_sync_started",
            account_id=payload.account_id,
            waba_id=payload.waba_id,
        )
        response_json = await self._request_json(
            method="GET",
            endpoint=self._build_endpoint(payload.waba_id, "phone_numbers"),
            access_token=payload.access_token,
            params={
                "fields": ",".join(
                    [
                        "id",
                        "display_phone_number",
                        "verified_name",
                        "quality_rating",
                        "code_verification_status",
                        "name_status",
                        "status",
                    ]
                )
            },
            body=None,
        )
        existing_map = {
            item.phone_number_id: item for item in payload.existing_phone_numbers
        }
        phone_numbers = [
            self._deserialize_phone_number(item, existing_map=existing_map)
            for item in response_json.get("data", [])
            if isinstance(item, Mapping)
        ]
        logger.info(
            "meta_phone_number_sync_completed",
            account_id=payload.account_id,
            waba_id=payload.waba_id,
            count=len(phone_numbers),
        )
        return MetaPhoneNumberSyncResult(
            provider_name=self.provider_name,
            sync_mode="remote_fetch",
            status="success",
            phone_numbers=phone_numbers,
            raw_response=response_json,
            message=(
                f"Fetched {len(phone_numbers)} phone number(s) from Meta for WABA '{payload.waba_id}'."
            ),
        )

    async def complete_embedded_signup_session(
        self,
        payload: MetaEmbeddedSignupCompletionCommand,
    ) -> MetaEmbeddedSignupCompletionResult:
        resolved_waba_id = payload.requested_waba_id or self._read_embedded_signup_string(
            payload.raw_payload,
            direct_keys=("waba_id",),
        )
        resolved_portfolio_id = payload.meta_business_portfolio_id or self._read_embedded_signup_string(
            payload.raw_payload,
            direct_keys=("meta_business_portfolio_id", "business_portfolio_id", "business_id"),
        )
        resolved_phone_number_ids = list(payload.phone_number_ids) or self._read_embedded_signup_phone_number_ids(
            payload.raw_payload
        )
        raw_response: dict[str, object] = {
            "session_id": payload.session_id,
            "requested_waba_id": payload.requested_waba_id,
        }
        resolved_authorization_code = payload.authorization_code or self._read_embedded_signup_string(
            payload.raw_payload,
            direct_keys=("authorization_code", "code"),
        )
        resolved_access_token = payload.system_user_access_token or self._read_embedded_signup_string(
            payload.raw_payload,
            direct_keys=("system_user_access_token", "access_token"),
        )
        remote_confirmed = False
        completion_status = "callback_recorded"
        message = (
            "Embedded signup callback recorded locally. "
            "Provide system_user_access_token and waba_id to confirm phone numbers remotely."
        )

        if resolved_access_token is None and resolved_authorization_code:
            app_id = payload.app_id or self._app_id
            app_secret = payload.app_secret or self._app_secret
            if app_id and app_secret:
                resolved_access_token, exchange_snapshot = await self._exchange_authorization_code(
                    authorization_code=resolved_authorization_code,
                    redirect_uri=payload.redirect_uri,
                    app_id=app_id,
                    app_secret=app_secret,
                )
                raw_response["authorization_code_exchange"] = exchange_snapshot
            else:
                raw_response["authorization_code_exchange"] = {
                    "access_token_present": False,
                    "skipped_reason": "missing_meta_app_credentials",
                }
                message = (
                    "Embedded signup callback recorded locally. Configure META_APP_ID "
                    "and META_APP_SECRET to exchange authorization_code remotely."
                )

        if resolved_access_token and resolved_waba_id:
            sync_result = await self.sync_phone_numbers(
                MetaPhoneNumberSyncCommand(
                    account_id=payload.account_id,
                    waba_id=resolved_waba_id,
                    access_token=resolved_access_token,
                    existing_phone_numbers=[],
                )
            )
            remote_confirmed = sync_result.status == "success"
            completion_status = "remote_confirmed" if remote_confirmed else "callback_recorded"
            if sync_result.phone_numbers:
                resolved_phone_number_ids = [
                    item.phone_number_id for item in sync_result.phone_numbers
                ]
            raw_response["phone_number_sync"] = sync_result.raw_response or {}
            message = (
                "Embedded signup callback recorded and Meta phone-number inventory confirmed remotely."
                if remote_confirmed
                else "Embedded signup callback recorded locally; Meta phone-number confirmation is still pending."
            )

        logger.info(
            "meta_embedded_signup_completion_processed",
            account_id=payload.account_id,
            session_id=payload.session_id,
            waba_id=resolved_waba_id,
            remote_confirmed=remote_confirmed,
            phone_number_count=len(resolved_phone_number_ids),
        )
        return MetaEmbeddedSignupCompletionResult(
            provider_name=self.provider_name,
            completion_status=completion_status,
            remote_confirmed=remote_confirmed,
            resolved_waba_id=resolved_waba_id,
            resolved_portfolio_id=resolved_portfolio_id,
            access_token=resolved_access_token,
            phone_number_ids=resolved_phone_number_ids,
            raw_response=raw_response,
            message=message,
        )

    async def send_test_message(
        self,
        waba_id: str,
        access_token: str,
        phone_id: str,
        to: str,
        text: str,
    ) -> dict[str, object]:
        url = f"{self._api_base}/{self._api_version}/{phone_id}/messages"
        body: dict[str, object] = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"preview_url": False, "body": text},
        }
        try:
            result = await self._request_json(
                method="POST",
                endpoint=url,
                access_token=access_token,
                params=None,
                body=body,
            )
            return {
                "ok": True,
                "waba_id": waba_id,
                "to": to,
                "message_id": result.get("messages", [{}])[0].get("id", "") if isinstance(result.get("messages"), list) else "",
                "raw_response": result,
            }
        except MetaManagementProviderError as exc:
            return {
                "ok": False,
                "waba_id": waba_id,
                "to": to,
                "error": str(exc),
                "remote_status_code": exc.remote_status_code,
                "raw_response": exc.raw_response,
            }
        except Exception as exc:
            return {"ok": False, "error": str(exc), "waba_id": waba_id, "to": to}

    async def query_phone_detail(
        self,
        waba_id: str,
        access_token: str,
        phone_id: str,
    ) -> dict[str, object]:
        url = f"{self._api_base}/{self._api_version}/{phone_id}"
        params = {
            "fields": "id,display_phone_number,verified_name,quality_rating,code_verification_status,name_status,status,certificate",
        }
        try:
            result = await self._request_json(
                method="GET",
                endpoint=url,
                access_token=access_token,
                params=params,
                body=None,
            )
            return {"ok": True, "phone_id": phone_id, "raw_response": result}
        except MetaManagementProviderError as exc:
            return {"ok": False, "error": str(exc), "remote_status_code": exc.remote_status_code, "raw_response": exc.raw_response}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    async def query_business_profile(
        self,
        waba_id: str,
        access_token: str,
        phone_id: str,
    ) -> dict[str, object]:
        url = f"{self._api_base}/{self._api_version}/{phone_id}/whatsapp_business_profile"
        params = {"fields": "about,address,description,email,profile_picture_url,websites,vertical"}
        try:
            result = await self._request_json(
                method="GET",
                endpoint=url,
                access_token=access_token,
                params=params,
                body=None,
            )
            return {"ok": True, "phone_id": phone_id, "raw_response": result}
        except MetaManagementProviderError as exc:
            return {"ok": False, "error": str(exc), "remote_status_code": exc.remote_status_code, "raw_response": exc.raw_response}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    async def _exchange_authorization_code(
        self,
        *,
        authorization_code: str,
        redirect_uri: str,
        app_id: str,
        app_secret: str,
    ) -> tuple[str, dict[str, object]]:
        response_json = await self._request_json(
            method="GET",
            endpoint=self._build_version_endpoint("oauth/access_token"),
            access_token=None,
            params={
                "client_id": app_id,
                "client_secret": app_secret,
                "code": authorization_code,
                "redirect_uri": redirect_uri,
            },
            body=None,
            requires_access_token=False,
        )
        access_token = self._read_string(response_json, "access_token")
        if access_token is None:
            raise MetaManagementProviderError(
                "Meta authorization code exchange did not return access_token.",
                raw_response=response_json,
            )
        return access_token, {
            "access_token_present": True,
            "token_type": response_json.get("token_type"),
            "expires_in": response_json.get("expires_in"),
        }

    async def _request_json(
        self,
        *,
        method: str,
        endpoint: str,
        access_token: str | None,
        params: dict[str, str] | None,
        body: dict[str, object] | None,
        requires_access_token: bool = True,
    ) -> dict[str, object]:
        if requires_access_token and not access_token:
            raise MetaManagementProviderError(
                "Meta management request requires access_token.",
                remote_status_code=400,
            )

        headers = {"Authorization": f"Bearer {access_token}"} if access_token else {}
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
            raw_response = self._parse_error_payload(exc.response)
            logger.warning(
                "meta_management_request_http_error",
                method=method,
                endpoint=endpoint,
                status_code=exc.response.status_code,
                error=raw_response,
            )
            raise MetaManagementProviderError(
                self._build_http_error_message(exc.response.status_code, raw_response),
                remote_status_code=exc.response.status_code,
                raw_response=raw_response,
            ) from exc
        except httpx.TimeoutException as exc:
            logger.warning(
                "meta_management_request_timeout",
                method=method,
                endpoint=endpoint,
            )
            raise MetaManagementProviderError(
                "连接 Meta 服务器超时，当前网络可能不稳定，请稍后重试",
                remote_status_code=408,
            ) from exc
        except httpx.ConnectError as exc:
            logger.warning(
                "meta_management_request_connect_error",
                method=method,
                endpoint=endpoint,
                error=str(exc),
            )
            raise MetaManagementProviderError(
                "无法连接 Meta 服务器（graph.facebook.com），当前网络环境可能无法直接访问，建议使用代理或 VPN",
                remote_status_code=0,
            ) from exc
        except httpx.RequestError as exc:
            logger.warning(
                "meta_management_request_failed",
                method=method,
                endpoint=endpoint,
                error=str(exc),
            )
            raise MetaManagementProviderError(
                f"Meta management request failed: {exc}",
            ) from exc

        if not isinstance(payload, dict):
            raise MetaManagementProviderError(
                "Meta management request returned a non-object payload.",
                raw_response={"payload_type": type(payload).__name__},
            )
        return payload

    def _build_endpoint(self, waba_id: str, edge: str) -> str:
        return f"{self._api_base}/{self._api_version}/{waba_id}/{edge}"

    def _build_version_endpoint(self, edge: str) -> str:
        return f"{self._api_base}/{self._api_version}/{edge.lstrip('/')}"

    @staticmethod
    def _coerce_success(payload: Mapping[str, object]) -> bool:
        success = payload.get("success")
        if isinstance(success, bool):
            return success
        return "error" not in payload

    @staticmethod
    def _read_string(
        payload: Mapping[str, object] | None,
        key: str,
    ) -> str | None:
        if payload is None:
            return None
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        return None

    @classmethod
    def _read_embedded_signup_string(
        cls,
        payload: Mapping[str, object] | None,
        *,
        direct_keys: tuple[str, ...],
    ) -> str | None:
        if payload is None:
            return None
        for key in direct_keys:
            value = cls._read_string(payload, key)
            if value is not None:
                return value
        for container in cls._iter_embedded_signup_candidate_mappings(payload):
            for key in direct_keys:
                value = cls._read_string(container, key)
                if value is not None:
                    return value
        return None

    @classmethod
    def _read_embedded_signup_phone_number_ids(
        cls,
        payload: Mapping[str, object] | None,
    ) -> list[str]:
        if payload is None:
            return []

        for candidate in (payload, *cls._iter_embedded_signup_candidate_mappings(payload)):
            phone_number_ids = cls._coerce_phone_number_ids(candidate.get("phone_number_ids"))
            if phone_number_ids:
                return phone_number_ids

            phone_numbers = cls._coerce_phone_number_ids(candidate.get("phone_numbers"))
            if phone_numbers:
                return phone_numbers

            single_phone_number_id = cls._read_string(candidate, "phone_number_id")
            if single_phone_number_id is not None:
                return [single_phone_number_id]

        return []

    @classmethod
    def _iter_embedded_signup_candidate_mappings(
        cls,
        payload: Mapping[str, object],
    ) -> list[Mapping[str, object]]:
        candidates: list[Mapping[str, object]] = []
        for key, value in payload.items():
            if isinstance(value, Mapping):
                if key in {"data", "payload", "result", "session", "embedded_signup", "authorization"}:
                    candidates.append(value)
                candidates.extend(cls._iter_embedded_signup_candidate_mappings(value))
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, Mapping):
                        candidates.extend(cls._iter_embedded_signup_candidate_mappings(item))
        return candidates

    @staticmethod
    def _coerce_phone_number_ids(value: object) -> list[str]:
        if isinstance(value, str) and value.strip():
            return [value.strip()]
        if not isinstance(value, list):
            return []

        phone_number_ids: list[str] = []
        for item in value:
            if isinstance(item, str) and item.strip():
                phone_number_ids.append(item.strip())
                continue
            if isinstance(item, Mapping):
                item_id = item.get("id") or item.get("phone_number_id")
                if isinstance(item_id, str) and item_id.strip():
                    phone_number_ids.append(item_id.strip())
        return phone_number_ids

    @staticmethod
    def _normalize_quality_rating(value: object) -> str:
        normalized = str(value or "").strip().upper()
        if normalized in {"GREEN", "YELLOW", "RED"}:
            return normalized
        return "UNKNOWN"

    @classmethod
    def _deserialize_phone_number(
        cls,
        payload: Mapping[str, object],
        *,
        existing_map: Mapping[str, MetaPhoneNumberRecord],
    ) -> MetaPhoneNumberRecord:
        phone_number_id = str(payload.get("id") or "").strip()
        if not phone_number_id:
            raise MetaManagementProviderError(
                "Meta phone-number payload is missing 'id'.",
                raw_response={"payload": dict(payload)},
            )

        existing = existing_map.get(phone_number_id)
        display_phone_number = str(
            payload.get("display_phone_number")
            or (existing.display_phone_number if existing is not None else phone_number_id)
        ).strip()
        verified_name = (
            str(payload.get("verified_name")).strip()
            if payload.get("verified_name") is not None
            else (existing.verified_name if existing is not None else None)
        )
        quality_rating = cls._normalize_quality_rating(payload.get("quality_rating"))
        is_registered = cls._infer_registration_state(payload, existing=existing)
        return MetaPhoneNumberRecord(
            phone_number_id=phone_number_id,
            display_phone_number=display_phone_number or phone_number_id,
            verified_name=verified_name,
            quality_rating=quality_rating,
            is_registered=is_registered,
        )

    @staticmethod
    def _infer_registration_state(
        payload: Mapping[str, object],
        *,
        existing: MetaPhoneNumberRecord | None,
    ) -> bool:
        code_verification_status = str(
            payload.get("code_verification_status") or ""
        ).strip().upper()
        remote_status = str(payload.get("status") or "").strip().upper()
        if code_verification_status in {"VERIFIED", "CONNECTED"}:
            return True
        if remote_status in {"CONNECTED", "VERIFIED"}:
            return True
        if existing is not None:
            return existing.is_registered
        return False

    @staticmethod
    def _parse_error_payload(response: httpx.Response) -> dict[str, object]:
        try:
            payload = response.json()
        except ValueError:
            return {"text": response.text}
        if isinstance(payload, dict):
            return payload
        return {"payload": payload}

    @staticmethod
    def _build_http_error_message(
        status_code: int,
        payload: Mapping[str, object],
    ) -> str:
        error_payload = payload.get("error")
        if isinstance(error_payload, Mapping):
            message = error_payload.get("message")
            if isinstance(message, str) and message.strip():
                return f"Meta management request failed ({status_code}): {message.strip()}"
        return f"Meta management request failed with status {status_code}."
