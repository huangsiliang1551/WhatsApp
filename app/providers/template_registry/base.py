from abc import ABC, abstractmethod

from app.schemas.template_registry import (
    TemplateRegistrySubmitRequest,
    TemplateRegistrySubmitResult,
    TemplateRegistrySyncResult,
)


class TemplateRegistryProvider(ABC):
    provider_name: str

    @abstractmethod
    async def submit_template(
        self,
        payload: TemplateRegistrySubmitRequest,
    ) -> TemplateRegistrySubmitResult:
        raise NotImplementedError

    @abstractmethod
    async def sync_templates(
        self,
        *,
        account_id: str,
        waba_id: str,
        access_token: str | None,
    ) -> TemplateRegistrySyncResult:
        raise NotImplementedError
