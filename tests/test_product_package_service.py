"""Tests for product_package_service.py (12 tests)."""
from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.db.models import Account, Product, ProductPackage
from app.schemas.marketing import PackageCreateRequest, PackageUpdateRequest
from app.services.product_package_service import ProductPackageService
from app.services.product_service import ProductService
from app.schemas.marketing import ProductCreateRequest


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add(Account(account_id="acc-1", display_name="Test"))
    session.commit()
    # Create some products
    svc = ProductService(session)
    svc.create_product(ProductCreateRequest(account_id="acc-1", name="A", price=Decimal("10")))
    svc.create_product(ProductCreateRequest(account_id="acc-1", name="B", price=Decimal("20")))
    svc.create_product(ProductCreateRequest(account_id="acc-1", name="C", price=Decimal("30")))
    yield session
    session.close()


def test_list_packages_empty(db_session: Session):
    svc = ProductPackageService(db_session)
    result = svc.list_packages("acc-1")
    assert result["total"] == 0


def test_create_package(db_session: Session):
    svc = ProductPackageService(db_session)
    pkg = svc.create_package(PackageCreateRequest(
        account_id="acc-1", name="Bundle", target_amount=Decimal("30"),
        product_count=2, completion_reward=Decimal("5"),
    ))
    assert pkg.name == "Bundle"
    assert pkg.total_value >= Decimal("0")
    assert pkg.completion_reward == Decimal("5")


def test_create_package_not_enough_products(db_session: Session):
    svc = ProductPackageService(db_session)
    with pytest.raises(ValueError, match="Not enough"):
        svc.create_package(PackageCreateRequest(
            account_id="acc-1", name="Bundle", target_amount=Decimal("100"),
            product_count=10,
        ))


def test_get_package(db_session: Session):
    svc = ProductPackageService(db_session)
    pkg = svc.create_package(PackageCreateRequest(
        account_id="acc-1", name="Bundle", target_amount=Decimal("30"), product_count=2,
    ))
    got = svc.get_package(pkg.id)
    assert got.id == pkg.id


def test_get_package_not_found(db_session: Session):
    svc = ProductPackageService(db_session)
    with pytest.raises(LookupError):
        svc.get_package("nonexistent")


def test_update_package_name(db_session: Session):
    svc = ProductPackageService(db_session)
    pkg = svc.create_package(PackageCreateRequest(
        account_id="acc-1", name="Old", target_amount=Decimal("30"), product_count=2,
    ))
    updated = svc.update_package(pkg.id, PackageUpdateRequest(name="New"))
    assert updated.name == "New"


def test_update_package_reward(db_session: Session):
    svc = ProductPackageService(db_session)
    pkg = svc.create_package(PackageCreateRequest(
        account_id="acc-1", name="Bundle", target_amount=Decimal("30"), product_count=2,
        completion_reward=Decimal("5"),
    ))
    updated = svc.update_package(pkg.id, PackageUpdateRequest(completion_reward=Decimal("10")))
    assert updated.completion_reward == Decimal("10")


def test_delete_package(db_session: Session):
    svc = ProductPackageService(db_session)
    pkg = svc.create_package(PackageCreateRequest(
        account_id="acc-1", name="Bundle", target_amount=Decimal("30"), product_count=2,
    ))
    svc.delete_package(pkg.id)
    with pytest.raises(LookupError):
        svc.get_package(pkg.id)


def test_assemble_preview(db_session: Session):
    svc = ProductPackageService(db_session)
    result = svc.preview_assemble(Decimal("30"), 10, 2, "acc-1")
    assert len(result.items) == 2


def test_assemble_preview_not_enough(db_session: Session):
    svc = ProductPackageService(db_session)
    with pytest.raises(ValueError, match="Not enough"):
        svc.preview_assemble(Decimal("100"), 10, 10, "acc-1")


def test_assemble_package_algorithm(db_session: Session):
    svc = ProductPackageService(db_session)
    products = svc._assemble_package(Decimal("30"), 10, 2, "acc-1")
    assert len(products) == 2
    total = sum(p.price for p in products)
    assert abs(total - Decimal("30")) <= Decimal("3")  # 10% of 30


def test_claim_and_completion_stats(db_session: Session):
    """Test _count_claims and _completion_rate work with no instances."""
    svc = ProductPackageService(db_session)
    pkg = svc.create_package(PackageCreateRequest(
        account_id="acc-1", name="Bundle", target_amount=Decimal("30"), product_count=2,
    ))
    count = svc._count_claims(pkg.id)
    rate = svc._completion_rate(pkg.id)
    assert count == 0
    assert rate == 0.0
