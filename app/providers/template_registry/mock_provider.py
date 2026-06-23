from uuid import uuid4

from app.providers.template_registry.base import TemplateRegistryProvider
from app.schemas.template_registry import (
    TemplateRegistryRemoteTemplate,
    TemplateRegistrySubmitRequest,
    TemplateRegistrySubmitResult,
    TemplateRegistrySyncResult,
)


class MockTemplateRegistryProvider(TemplateRegistryProvider):
    provider_name = "mock"

    async def submit_template(
        self,
        payload: TemplateRegistrySubmitRequest,
    ) -> TemplateRegistrySubmitResult:
        remote_template = TemplateRegistryRemoteTemplate(
            provider_template_id=f"mock-template-{uuid4()}",
            name=payload.name,
            language=payload.language,
            category=payload.category,
            status="PENDING",
            rejected_reason=None,
            components=payload.components,
            raw_payload={
                "account_id": payload.account_id,
                "waba_id": payload.waba_id,
                "name": payload.name,
            },
        )
        return TemplateRegistrySubmitResult(
            provider_name=self.provider_name,
            action="submitted",
            remote_status="PENDING",
            provider_template_id=remote_template.provider_template_id,
            remote_template=remote_template,
            raw_response=remote_template.raw_payload,
        )

    async def sync_templates(
        self,
        *,
        account_id: str,
        waba_id: str,
        access_token: str | None,
    ) -> TemplateRegistrySyncResult:
        del account_id, waba_id, access_token
        return TemplateRegistrySyncResult(
            provider_name=self.provider_name,
            templates=[],
        )
