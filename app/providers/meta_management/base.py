from abc import ABC, abstractmethod
from dataclasses import dataclass, field


class MetaManagementProviderError(Exception):
    def __init__(
        self,
        message: str,
        *,
        remote_status_code: int | None = None,
        raw_response: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.remote_status_code = remote_status_code
        self.raw_response = raw_response


@dataclass(slots=True)
class MetaPhoneNumberRecord:
    phone_number_id: str
    display_phone_number: str
    verified_name: str | None = None
    quality_rating: str = "UNKNOWN"
    is_registered: bool = False
    is_active: bool = True


@dataclass(slots=True)
class MetaWebhookSubscriptionCommand:
    account_id: str
    waba_id: str
    callback_url: str
    verify_token: str | None = None
    app_id: str | None = None
    access_token: str | None = None
    app_secret: str | None = None


@dataclass(slots=True)
class MetaWebhookSubscriptionResult:
    provider_name: str
    subscription_status: str
    remote_confirmed: bool
    raw_response: dict[str, object] | None = None
    message: str | None = None


@dataclass(slots=True)
class MetaPhoneNumberSyncCommand:
    account_id: str
    waba_id: str
    access_token: str | None = None
    existing_phone_numbers: list[MetaPhoneNumberRecord] = field(default_factory=list)


@dataclass(slots=True)
class MetaPhoneNumberSyncResult:
    provider_name: str
    sync_mode: str
    status: str
    phone_numbers: list[MetaPhoneNumberRecord] = field(default_factory=list)
    raw_response: dict[str, object] | None = None
    message: str | None = None


@dataclass(slots=True)
class MetaEmbeddedSignupCompletionCommand:
    account_id: str
    session_id: str
    redirect_uri: str
    app_id: str | None = None
    app_secret: str | None = None
    requested_waba_id: str | None = None
    meta_business_portfolio_id: str | None = None
    phone_number_ids: list[str] = field(default_factory=list)
    setup_session_id: str | None = None
    authorization_code: str | None = None
    system_user_access_token: str | None = None
    raw_payload: dict[str, object] | None = None


@dataclass(slots=True)
class MetaEmbeddedSignupCompletionResult:
    provider_name: str
    completion_status: str
    remote_confirmed: bool
    resolved_waba_id: str | None = None
    resolved_portfolio_id: str | None = None
    access_token: str | None = None
    phone_number_ids: list[str] = field(default_factory=list)
    raw_response: dict[str, object] | None = None
    message: str | None = None


class MetaManagementProvider(ABC):
    provider_name: str

    @abstractmethod
    async def health_check(
        self,
        waba_id: str,
        access_token: str,
    ) -> dict[str, object]:
        raise NotImplementedError

    @abstractmethod
    async def subscribe_webhook(
        self,
        payload: MetaWebhookSubscriptionCommand,
    ) -> MetaWebhookSubscriptionResult:
        raise NotImplementedError

    @abstractmethod
    async def sync_phone_numbers(
        self,
        payload: MetaPhoneNumberSyncCommand,
    ) -> MetaPhoneNumberSyncResult:
        raise NotImplementedError

    @abstractmethod
    async def complete_embedded_signup_session(
        self,
        payload: MetaEmbeddedSignupCompletionCommand,
    ) -> MetaEmbeddedSignupCompletionResult:
        raise NotImplementedError

    @abstractmethod
    async def send_test_message(
        self,
        waba_id: str,
        access_token: str,
        phone_id: str,
        to: str,
        text: str,
    ) -> dict[str, object]:
        raise NotImplementedError

    @abstractmethod
    async def query_phone_detail(
        self,
        waba_id: str,
        access_token: str,
        phone_id: str,
    ) -> dict[str, object]:
        raise NotImplementedError

    @abstractmethod
    async def query_business_profile(
        self,
        waba_id: str,
        access_token: str,
        phone_id: str,
    ) -> dict[str, object]:
        raise NotImplementedError
