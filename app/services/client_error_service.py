from __future__ import annotations

from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import ClientError


class ClientErrorService:
    """Record and query frontend JS errors."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_errors(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        error_type: str | None = None,
    ) -> list[ClientError]:
        query = select(ClientError).order_by(ClientError.created_at.desc())
        if error_type:
            query = query.where(ClientError.error_type == error_type)
        return list(self._session.scalars(query.offset(offset).limit(limit)).all())

    def count_errors(self, error_type: str | None = None) -> int:
        query = select(func.count(ClientError.id))
        if error_type:
            query = query.where(ClientError.error_type == error_type)
        result = self._session.scalar(query)
        return result or 0

    def record_error(
        self,
        *,
        site_key: str | None = None,
        error_type: str,
        message: str,
        stack_trace: str | None = None,
        url: str | None = None,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> ClientError:
        error = ClientError(
            id=str(uuid4()),
            site_key=site_key,
            error_type=error_type,
            message=message,
            stack_trace=stack_trace,
            url=url,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        self._session.add(error)
        self._session.commit()
        return error

    def get_error(self, error_id: str) -> ClientError:
        error = self._session.get(ClientError, error_id)
        if not error:
            raise LookupError(f"Client error '{error_id}' not found.")
        return error

    def delete_error(self, error_id: str) -> None:
        error = self._session.get(ClientError, error_id)
        if not error:
            raise LookupError(f"Client error '{error_id}' not found.")
        self._session.delete(error)
        self._session.commit()
