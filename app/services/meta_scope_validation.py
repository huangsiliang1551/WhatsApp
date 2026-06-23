from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import WhatsAppBusinessAccount, WhatsAppPhoneNumber


@dataclass(slots=True)
class ResolvedPhoneNumberScope:
    account_id: str
    waba_id: str | None
    phone_number_id: str
    phone_number: WhatsAppPhoneNumber


class MetaScopeValidator:
    def __init__(self, session: Session) -> None:
        self._session = session

    def validate_waba_scope(
        self,
        *,
        account_id: str | None,
        waba_id: str | None,
        allowed_account_ids: set[str] | None,
    ) -> str | None:
        if waba_id is None:
            return None

        owner_account_id = self._session.execute(
            select(WhatsAppBusinessAccount.account_id)
            .where(WhatsAppBusinessAccount.waba_id == waba_id)
            .limit(1)
        ).scalar_one_or_none()
        if owner_account_id is None:
            return None

        if account_id is not None and owner_account_id != account_id:
            raise ValueError(
                f"WABA '{waba_id}' belongs to account '{owner_account_id}', not '{account_id}'."
            )
        if allowed_account_ids is not None and owner_account_id not in allowed_account_ids:
            raise ValueError(f"WABA '{waba_id}' is outside the accessible account scope.")

        return owner_account_id

    def validate_phone_number_scope(
        self,
        *,
        phone_number_id: str | None,
        account_id: str | None,
        waba_id: str | None,
        allowed_account_ids: set[str] | None,
        enforce_waba_match: bool = False,
    ) -> ResolvedPhoneNumberScope | None:
        if phone_number_id is None:
            return None

        query = (
            select(WhatsAppPhoneNumber)
            .options(selectinload(WhatsAppPhoneNumber.waba_account))
            .where(WhatsAppPhoneNumber.phone_number_id == phone_number_id)
        )
        if allowed_account_ids is not None:
            query = query.where(WhatsAppPhoneNumber.account_id.in_(allowed_account_ids))

        phone_number = self._session.scalars(query).first()
        if phone_number is None:
            return None

        resolved_account_id = phone_number.account_id
        if account_id is not None and resolved_account_id != account_id:
            raise ValueError(
                f"Phone-Number-ID '{phone_number_id}' belongs to account '{resolved_account_id}', "
                f"not '{account_id}'."
            )

        resolved_waba_id = self._resolve_phone_waba_id(phone_number)
        if (
            enforce_waba_match
            and waba_id is not None
            and resolved_waba_id is not None
            and resolved_waba_id != waba_id
        ):
            raise ValueError(
                f"Phone-Number-ID '{phone_number_id}' belongs to WABA '{resolved_waba_id}', "
                f"not '{waba_id}'."
            )

        return ResolvedPhoneNumberScope(
            account_id=resolved_account_id,
            waba_id=resolved_waba_id,
            phone_number_id=phone_number.phone_number_id,
            phone_number=phone_number,
        )

    @staticmethod
    def _resolve_phone_waba_id(phone_number: WhatsAppPhoneNumber) -> str | None:
        if phone_number.waba_id:
            return phone_number.waba_id
        waba_account = phone_number.waba_account
        if waba_account is not None and waba_account.waba_id:
            return waba_account.waba_id
        if phone_number.waba_account_id is None:
            return None
        if waba_account is not None:
            return waba_account.waba_id
        return None
