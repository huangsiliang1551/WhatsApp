"""Tests for product_service.py (10 tests)."""
from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.db.models import Account, Product, ProductPackage
from app.schemas.marketing import ProductCreateRequest, ProductUpdateRequest
from app.services.product_service import ProductService


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add(Account(account_id="acc-1", display_name="Test"))
    session.commit()
    yield session
    session.close()


def test_create_product(db_session: Session):
    svc = ProductService(db_session)
    p = svc.create_product(ProductCreateRequest(account_id="acc-1", name="Widget", price=Decimal("19.99")))
    assert p.name == "Widget"
    assert p.price == Decimal("19.99")


def test_list_products(db_session: Session):
    svc = ProductService(db_session)
    svc.create_product(ProductCreateRequest(account_id="acc-1", name="A", price=Decimal("10")))
    svc.create_product(ProductCreateRequest(account_id="acc-1", name="B", price=Decimal("20")))
    result = svc.list_products("acc-1")
    assert result["total"] == 2


def test_list_products_paginated(db_session: Session):
    svc = ProductService(db_session)
    for i in range(5):
        svc.create_product(ProductCreateRequest(account_id="acc-1", name=f"P{i}", price=Decimal("10")))
    result = svc.list_products("acc-1", page=1, size=2)
    assert len(result["items"]) == 2
    assert result["total"] == 5


def test_list_products_search(db_session: Session):
    svc = ProductService(db_session)
    svc.create_product(ProductCreateRequest(account_id="acc-1", name="Widget", price=Decimal("10")))
    svc.create_product(ProductCreateRequest(account_id="acc-1", name="Gadget", price=Decimal("10")))
    result = svc.list_products("acc-1", search="Widget")
    assert result["total"] == 1


def test_get_product(db_session: Session):
    svc = ProductService(db_session)
    p = svc.create_product(ProductCreateRequest(account_id="acc-1", name="X", price=Decimal("5")))
    got = svc.get_product(p.id)
    assert got.id == p.id


def test_get_product_not_found(db_session: Session):
    svc = ProductService(db_session)
    with pytest.raises(LookupError):
        svc.get_product("nonexistent")


def test_update_product(db_session: Session):
    svc = ProductService(db_session)
    p = svc.create_product(ProductCreateRequest(account_id="acc-1", name="X", price=Decimal("5")))
    updated = svc.update_product(p.id, ProductUpdateRequest(name="Y", price=Decimal("10")))
    assert updated.name == "Y"
    assert updated.price == Decimal("10")


def test_delete_product(db_session: Session):
    svc = ProductService(db_session)
    p = svc.create_product(ProductCreateRequest(account_id="acc-1", name="X", price=Decimal("5")))
    svc.delete_product(p.id)
    with pytest.raises(LookupError):
        svc.get_product(p.id)


def test_delete_product_referenced(db_session: Session):
    svc = ProductService(db_session)
    p = svc.create_product(ProductCreateRequest(account_id="acc-1", name="X", price=Decimal("5")))
    db_session.add(ProductPackage(account_id="acc-1", name="Pkg", target_amount=Decimal("10"),
                                   product_count=1, product_ids=[p.id], total_value=Decimal("5")))
    db_session.commit()
    with pytest.raises(ValueError, match="referenced"):
        svc.delete_product(p.id)


def test_csv_import_export(db_session: Session):
    svc = ProductService(db_session)
    csv_content = "name,price,tags\nWidget,19.99,hot\nGadget,9.99,new\n"
    count = svc.import_csv("acc-1", csv_content)
    assert count == 2

    exported = svc.export_csv("acc-1")
    assert "Widget" in exported
    assert "Gadget" in exported
