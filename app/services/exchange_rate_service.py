"""Exchange rate and site currency management service."""
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ExchangeRate, SiteCurrency


class ExchangeRateService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_rate(self, from_currency: str, to_currency: str) -> Decimal | None:
        if from_currency == to_currency:
            return Decimal("1.0")
        rate = self._session.execute(
            select(ExchangeRate).where(
                ExchangeRate.from_currency == from_currency.upper(),
                ExchangeRate.to_currency == to_currency.upper(),
            )
        ).scalar_one_or_none()
        return Decimal(str(rate.rate)) if rate else None

    def convert(self, amount: Decimal, from_currency: str, to_currency: str) -> Decimal:
        if from_currency == to_currency:
            return amount
        rate = self.get_rate(from_currency, to_currency)
        if rate is None:
            raise ValueError(f"No exchange rate found for {from_currency} -> {to_currency}")
        return (amount * rate).quantize(Decimal("0.01"))

    def update_rate(
        self, from_currency: str, to_currency: str, rate: Decimal, source: str = "manual"
    ) -> ExchangeRate:
        from_currency = from_currency.upper()
        to_currency = to_currency.upper()
        existing = self._session.execute(
            select(ExchangeRate).where(
                ExchangeRate.from_currency == from_currency,
                ExchangeRate.to_currency == to_currency,
            )
        ).scalar_one_or_none()
        if existing:
            existing.rate = rate
            existing.source = source
            existing.updated_at = datetime.now(timezone.utc)
            return existing
        obj = ExchangeRate(
            id=str(uuid4()),
            from_currency=from_currency,
            to_currency=to_currency,
            rate=rate,
            source=source,
        )
        self._session.add(obj)
        self._session.flush()
        return obj

    def get_all_rates(self) -> list[dict]:
        rows = self._session.execute(select(ExchangeRate)).scalars().all()
        return [
            {"id": r.id, "from": r.from_currency, "to": r.to_currency, "rate": float(r.rate), "source": r.source}
            for r in rows
        ]

    def get_site_currency(self, site_id: str) -> dict | None:
        sc = self._session.execute(
            select(SiteCurrency).where(SiteCurrency.site_id == site_id)
        ).scalar_one_or_none()
        if sc is None:
            return None
        return {"site_id": sc.site_id, "currency_code": sc.currency_code, "currency_symbol": sc.currency_symbol}

    def set_site_currency(self, site_id: str, currency_code: str, currency_symbol: str) -> SiteCurrency:
        existing = self._session.execute(
            select(SiteCurrency).where(SiteCurrency.site_id == site_id)
        ).scalar_one_or_none()
        if existing:
            existing.currency_code = currency_code
            existing.currency_symbol = currency_symbol
            return existing
        sc = SiteCurrency(
            id=str(uuid4()), site_id=site_id, currency_code=currency_code, currency_symbol=currency_symbol
        )
        self._session.add(sc)
        self._session.flush()
        return sc
