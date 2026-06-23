"""Exchange rate and site currency API routes."""
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, require_permission
from app.core.auth import RequestActor
from app.services.exchange_rate_service import ExchangeRateService

router = APIRouter(tags=["exchange-rates"])


class RateUpdateBody(BaseModel):
    rate: float
    source: str = "manual"


class CurrencyUpdateBody(BaseModel):
    currency_code: str
    currency_symbol: str


# ── Rates ──

@router.get("/api/exchange-rates")
def list_rates(
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("exchange_rate.view")),
) -> list[dict]:
    svc = ExchangeRateService(session)
    return svc.get_all_rates()


@router.put("/api/exchange-rates/{from_currency}/{to_currency}")
def update_rate(
    from_currency: str,
    to_currency: str,
    data: RateUpdateBody,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("exchange_rate.edit")),
) -> dict:
    svc = ExchangeRateService(session)
    obj = svc.update_rate(from_currency, to_currency, Decimal(str(data.rate)), data.source)
    return {"from": obj.from_currency, "to": obj.to_currency, "rate": float(obj.rate), "source": obj.source}


# ── Site Currency ──

@router.get("/api/sites/{site_id}/currency")
def get_site_currency(
    site_id: str,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("sites.view")),
) -> dict:
    svc = ExchangeRateService(session)
    result = svc.get_site_currency(site_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Site currency not configured")
    return result


@router.put("/api/sites/{site_id}/currency")
def set_site_currency(
    site_id: str,
    data: CurrencyUpdateBody,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("sites.edit")),
) -> dict:
    svc = ExchangeRateService(session)
    obj = svc.set_site_currency(site_id, data.currency_code, data.currency_symbol)
    return {"site_id": obj.site_id, "currency_code": obj.currency_code, "currency_symbol": obj.currency_symbol}
