"""Tencent Cloud Machine Translation (TMT) provider using TC3-HMAC-SHA256 signing.

Implements TranslationProvider to call the TextTranslate API.
Falls through to the next provider in the chain on failure (configured in factory).
"""

import hashlib
import hmac
import json
import time
import asyncio

import httpx
import structlog

from app.providers.translation.base import TranslationProvider
from app.providers.translation.tencent_tmt_errors import (
    TMT_REGIONS,
    get_tmt_error_prompt,
    get_tmt_error_prompt_with_code,
)

logger = structlog.get_logger()

TMT_ENDPOINT = "tmt.tencentcloudapi.com"
TMT_SERVICE = "tmt"
TMT_VERSION = "2018-03-21"
TMT_ACTION = "TextTranslate"


def _translate_language_code(code: str) -> str:
    """Convert our language codes (e.g. zh-CN, en-US) to Tencent Cloud format (zh, en)."""
    if code.startswith("zh"):
        return "zh"
    return code.split("-")[0] if "-" in code else code


def _sign_tc3(
    secret_key: str,
    date: str,
    string_to_sign: str,
) -> str:
    """TC3-HMAC-SHA256 signing."""
    secret_date = hmac.new(
        f"TC3{secret_key}".encode("utf-8"),
        date.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    secret_service = hmac.new(
        secret_date, TMT_SERVICE.encode("utf-8"), hashlib.sha256
    ).digest()
    secret_signing = hmac.new(
        secret_service, b"tc3_request", hashlib.sha256
    ).digest()
    return hmac.new(
        secret_signing, string_to_sign.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def _build_tc3_auth_header(
    secret_id: str,
    secret_key: str,
    timestamp: int,
    payload_str: str,
) -> dict[str, str]:
    """Build the full Authorization header and required headers for TC3-HMAC-SHA256."""
    algorithm = "TC3-HMAC-SHA256"
    content_type = "application/json"
    date = time.strftime("%Y-%m-%d", time.gmtime(timestamp))

    # 1. Canonical Request
    canonical_uri = "/"
    canonical_querystring = ""
    canonical_headers = f"content-type:{content_type}\nhost:{TMT_ENDPOINT}\n"
    signed_headers = "content-type;host"
    hashed_payload = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()

    canonical_request = (
        f"POST\n{canonical_uri}\n{canonical_querystring}\n"
        f"{canonical_headers}\n{signed_headers}\n{hashed_payload}"
    )

    # 2. String To Sign
    credential_scope = f"{date}/{TMT_SERVICE}/tc3_request"
    hashed_canonical = hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()
    string_to_sign = f"{algorithm}\n{timestamp}\n{credential_scope}\n{hashed_canonical}"

    # 3. Signature
    signature = _sign_tc3(secret_key, date, string_to_sign)

    # 4. Authorization
    authorization = (
        f"{algorithm} Credential={secret_id}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )

    return {
        "Authorization": authorization,
        "Content-Type": content_type,
        "Host": TMT_ENDPOINT,
        "X-TC-Action": TMT_ACTION,
        "X-TC-Timestamp": str(timestamp),
        "X-TC-Version": TMT_VERSION,
    }


class TencentCloudTranslationProvider(TranslationProvider):
    """Translates text via Tencent Cloud Machine Translation (TMT) TextTranslate API.

    Uses TC3-HMAC-SHA256 signing with SecretId/SecretKey for authentication.
    """

    provider_name = "tencent_cloud"

    def __init__(
        self,
        secret_id: str,
        secret_key: str,
        region: str = "ap-guangzhou",
        timeout_seconds: int = 15,
    ) -> None:
        self._secret_id = secret_id
        self._secret_key = secret_key
        self._region = region
        self._timeout_seconds = timeout_seconds

    async def translate_text(
        self,
        text: str,
        source_language: str,
        target_language: str,
    ) -> str:
        if source_language == target_language:
            return text

        source = _translate_language_code(source_language)
        target = _translate_language_code(target_language)

        timestamp = int(time.time())
        payload_dict = {
            "SourceText": text,
            "Source": source,
            "Target": target,
            "ProjectId": 0,
        }
        payload_str = json.dumps(payload_dict, separators=(",", ":"), ensure_ascii=False)

        headers = _build_tc3_auth_header(
            self._secret_id, self._secret_key, timestamp, payload_str
        )
        headers["X-TC-Region"] = self._region

        async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
            response = await client.post(
                f"https://{TMT_ENDPOINT}",
                headers=headers,
                content=payload_str,
            )

            if response.status_code != 200:
                error_detail = _extract_tmt_error(response.text)
                raise RuntimeError(
                    f"Tencent Cloud TMT API error: {response.status_code} {response.text}"
                )

            result = response.json()
            resp = result.get("Response", {})

            # Check for Tencent API-level errors
            if "Error" in resp:
                err = resp["Error"]
                err_code = err.get("Code", "Unknown")
                err_msg = err.get("Message", "")
                friendly = get_tmt_error_prompt_with_code(err_code)
                raise RuntimeError(
                    f"Tencent Cloud TMT error: {err_code} - {err_msg}. {friendly}"
                )

            return resp.get("TargetText", text)

    async def batch_translate_text(
        self,
        texts: list[str],
        source_language: str,
        target_language: str,
    ) -> list[str]:
        if not texts:
            return []
        if source_language == target_language:
            return list(texts)

        # Tencent Cloud TMT has no batch endpoint; call concurrently
        async def _one(text: str) -> str:
            try:
                return await self.translate_text(text, source_language, target_language)
            except Exception:
                return text  # return original on individual failure

        return await asyncio.gather(*[_one(t) for t in texts])

    @staticmethod
    def get_supported_regions() -> list[dict[str, str]]:
        """Return the list of TMT supported regions with labels and endpoints."""
        return list(TMT_REGIONS)


def _extract_tmt_error(response_text: str) -> dict:
    """Try to extract error code from TMT API error response."""
    try:
        data = json.loads(response_text)
        err = data.get("Response", {}).get("Error", {})
        if err:
            return {"code": err.get("Code", "Unknown"), "message": err.get("Message", "")}
    except (json.JSONDecodeError, AttributeError):
        pass
    return {"code": "Unknown", "message": response_text[:200]}
