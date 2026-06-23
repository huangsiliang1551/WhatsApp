"""API tests for marketing endpoints (12 tests)."""  # noqa: INP001
from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Account, AppUser, Product, ProductPackage, TaskRule, WalletAccount


def seed_data(db_factory: sessionmaker[Session]) -> None:
    """Seed initial data for API tests."""
    session = db_factory()
    session.add(Account(account_id="acc-1", display_name="Test"))
    session.add(AppUser(id="user-1", account_id="acc-1", public_user_id="u1"))
    session.add(WalletAccount(id="wallet-1", account_id="acc-1", user_id="user-1",
                               system_balance=Decimal("100"), task_balance=Decimal("0")))
    # Seed products
    session.add(Product(account_id="acc-1", name="Product A", price=Decimal("10.00")))
    session.add(Product(account_id="acc-1", name="Product B", price=Decimal("20.00")))
    session.add(Product(account_id="acc-1", name="Product C", price=Decimal("30.00")))
    session.commit()
    session.close()


class TestProductsAPI:
    """Products API endpoints."""

    def test_create_product(self, client: TestClient, db_session_factory):
        seed_data(db_session_factory)
        resp = client.post("/api/products", json={
            "account_id": "acc-1",
            "name": "New Product",
            "price": "15.99",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "New Product"
        assert data["price"] == "15.99"

    def test_list_products(self, client: TestClient, db_session_factory):
        seed_data(db_session_factory)
        resp = client.get("/api/products", params={"account_id": "acc-1"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 3
        assert len(data["items"]) >= 3

    def test_delete_product_referenced(self, client: TestClient, db_session_factory):
        seed_data(db_session_factory)
        # Create a product and a package that references it
        session = db_session_factory()
        product = Product(account_id="acc-1", name="X", price=Decimal("5"))
        session.add(product)
        session.commit()
        product_id = product.id
        session.add(ProductPackage(account_id="acc-1", name="Pkg",
                                    target_amount=Decimal("10"), product_count=1,
                                    product_ids=[product_id], total_value=Decimal("5")))
        session.commit()
        session.close()

        resp = client.delete(f"/api/products/{product_id}")
        assert resp.status_code == 409


class TestPackagesAPI:
    """Product packages API endpoints."""

    def test_create_package(self, client: TestClient, db_session_factory):
        seed_data(db_session_factory)
        resp = client.post("/api/product-packages", json={
            "account_id": "acc-1",
            "name": "Test Bundle",
            "target_amount": "30.00",
            "product_count": 2,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Test Bundle"
        assert data["product_count"] == 2

    def test_assemble_preview(self, client: TestClient, db_session_factory):
        seed_data(db_session_factory)
        resp = client.post("/api/product-packages/assemble-preview",
                           params={"account_id": "acc-1"},
                           json={
            "target_amount": "30.00",
            "tolerance_pct": 10,
            "product_count": 2,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 2


class TestTaskRulesAPI:
    """Task rules API endpoints."""

    def test_create_task_rule(self, client: TestClient, db_session_factory):
        seed_data(db_session_factory)
        resp = client.post("/api/task-rules", json={
            "account_id": "acc-1",
            "name": "Welcome Task",
            "rule_type": "package_push",
            "trigger_type": "register",
            "trigger_config": {"delay_minutes": 30},
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Welcome Task"
        assert data["is_enabled"] is True

    def test_toggle_task_rule(self, client: TestClient, db_session_factory):
        seed_data(db_session_factory)
        # Create a rule first
        session = db_session_factory()
        rule = TaskRule(account_id="acc-1", name="Rule", rule_type="package_push",
                         trigger_type="manual", trigger_config={}, is_enabled=True)
        session.add(rule)
        session.commit()
        rule_id = rule.id
        session.close()

        resp = client.patch(f"/api/task-rules/{rule_id}/toggle", json={"is_enabled": False})
        assert resp.status_code == 200
        assert resp.json()["is_enabled"] is False


class TestTaskInstancesAPI:
    """Task instances API endpoints."""

    def test_manual_push(self, client: TestClient, db_session_factory):
        seed_data(db_session_factory)
        # Create a rule
        session = db_session_factory()
        rule = TaskRule(account_id="acc-1", name="Manual Rule", rule_type="package_push",
                         trigger_type="manual", trigger_config={}, is_enabled=True)
        session.add(rule)
        session.commit()
        rule_id = rule.id
        session.close()

        resp = client.post("/api/task-instances/manual-push", json={
            "rule_id": rule_id,
            "user_ids": ["user-1"],
            "account_id": "acc-1",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["pushed_count"] == 1
        assert len(data["task_instance_ids"]) == 1


class TestSignInAPI:
    """Sign-in API endpoints."""

    def test_sign_in_config(self, client: TestClient, db_session_factory):
        seed_data(db_session_factory)
        resp = client.get("/api/sign-in/config")
        assert resp.status_code == 200
        data = resp.json()
        assert data["consecutive_days"] == 7


class TestInvitesAPI:
    """Invite API endpoints."""

    def test_my_link(self, client: TestClient, db_session_factory):
        seed_data(db_session_factory)
        resp = client.get("/api/invites/my-link", params={
            "user_id": "user-1",
            "account_id": "acc-1",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == "user-1"
        assert "invite_code" in data

    def test_invite_config(self, client: TestClient, db_session_factory):
        seed_data(db_session_factory)
        resp = client.get("/api/invites/config")
        assert resp.status_code == 200
        data = resp.json()
        assert data["register_reward"] == "2.00"


class TestMarketingStatsAPI:
    """Marketing stats API endpoints."""

    def test_overview(self, client: TestClient, db_session_factory):
        seed_data(db_session_factory)
        resp = client.get("/api/marketing/stats/overview", params={
            "account_id": "acc-1",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "today_sign_ins" in data
        assert "today_invites" in data
