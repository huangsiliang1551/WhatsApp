from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Account, H5Site, TaskProductPool, TaskProductPoolItem


def _seed_task_product_pool_api_scope(db_session_factory: sessionmaker[Session]) -> dict[str, str]:
    with db_session_factory() as session:
        account = Account(account_id="acct-task-pool-api", display_name="Task Pool API")
        site = H5Site(
            account_id=account.account_id,
            site_key="task-pool-api",
            domain="task-pool-api.example.com",
            brand_name="Task Pool API",
            default_language="zh-CN",
        )
        session.add_all([account, site])
        session.flush()

        pool = TaskProductPool(
            account_id=account.account_id,
            site_id=site.id,
            name="Existing Pool",
            code="existing-pool",
            pool_type="general",
            status="active",
            currency="USD",
        )
        session.add(pool)
        session.flush()

        session.add(
            TaskProductPoolItem(
                account_id=account.account_id,
                pool_id=pool.id,
                product_id="existing-product-1",
                product_name="Existing Product 1",
                image_url="https://example.com/existing-1.png",
                price=Decimal("12.50"),
                currency="USD",
                status="active",
                sort_order=1,
            )
        )
        session.commit()
        return {
            "account_id": account.account_id,
            "site_id": site.id,
            "pool_id": pool.id,
        }


def test_create_and_list_task_product_pools(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    seeded = _seed_task_product_pool_api_scope(db_session_factory)
    headers = {
        "X-Actor-Id": "operator-task-pool-api",
        "X-Actor-Role": "operator",
        "X-Actor-Account-Ids": seeded["account_id"],
    }

    create_response = client.post(
        "/api/tasks/product-pools",
        headers=headers,
        json={
            "account_id": seeded["account_id"],
            "site_id": seeded["site_id"],
            "name": "Seasonal Pool",
            "code": "seasonal-pool",
            "pool_type": "general",
            "price_mode": "task_price_snapshot",
            "allow_repeat_in_same_batch": False,
            "allow_repeat_in_same_package": False,
            "status": "active",
            "currency": "USD",
            "items": [
                {
                    "product_id": "product-1",
                    "product_name": "Product One",
                    "image_url": "https://example.com/product-1.png",
                    "price": "10.00",
                    "currency": "USD",
                    "product_description": "Product One Description",
                    "status": "active",
                    "sort_order": 1,
                },
                {
                    "product_id": "product-2",
                    "product_name": "Product Two",
                    "image_url": "https://example.com/product-2.png",
                    "price": "20.00",
                    "currency": "USD",
                    "product_description": "Product Two Description",
                    "status": "active",
                    "sort_order": 2,
                },
            ],
        },
    )
    assert create_response.status_code == 200, create_response.text
    created = create_response.json()
    assert created["name"] == "Seasonal Pool"
    assert created["itemCount"] == 2
    assert created["items"][1]["productName"] == "Product Two"

    create_audit_response = client.get(
        "/api/runtime/audit-logs",
        headers=headers,
        params={
            "account_id": seeded["account_id"],
            "target_type": "task_product_pool",
            "target_id": created["id"],
        },
    )
    assert create_audit_response.status_code == 200, create_audit_response.text
    create_logs = create_audit_response.json()
    create_matching = [item for item in create_logs if item["action"] == "task_product_pool_created"]
    assert len(create_matching) == 1
    assert create_matching[0]["payload"]["item_count"] == 2

    list_response = client.get(
        "/api/tasks/product-pools",
        headers=headers,
        params={"account_id": seeded["account_id"]},
    )
    assert list_response.status_code == 200, list_response.text
    listed = list_response.json()
    assert len(listed) == 2
    assert {item["name"] for item in listed} == {"Existing Pool", "Seasonal Pool"}
    seasonal = next(item for item in listed if item["name"] == "Seasonal Pool")
    assert seasonal["itemCount"] == 2


def test_cross_account_task_product_pool_create_is_forbidden(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    seeded = _seed_task_product_pool_api_scope(db_session_factory)
    headers = {
        "X-Actor-Id": "operator-task-pool-forbidden",
        "X-Actor-Role": "operator",
        "X-Actor-Account-Ids": "acct-other-scope",
    }

    create_response = client.post(
        "/api/tasks/product-pools",
        headers=headers,
        json={
            "account_id": seeded["account_id"],
            "site_id": seeded["site_id"],
            "name": "Forbidden Pool",
            "pool_type": "general",
            "status": "active",
            "currency": "USD",
        },
    )
    assert create_response.status_code == 403


def test_task_product_pool_detail_update_add_items_and_import(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    seeded = _seed_task_product_pool_api_scope(db_session_factory)
    headers = {
        "X-Actor-Id": "operator-task-pool-detail",
        "X-Actor-Role": "operator",
        "X-Actor-Account-Ids": seeded["account_id"],
    }

    detail_response = client.get(f"/api/tasks/product-pools/{seeded['pool_id']}", headers=headers)
    assert detail_response.status_code == 200, detail_response.text
    detail = detail_response.json()
    assert detail["id"] == seeded["pool_id"]
    assert detail["itemCount"] == 1

    update_response = client.patch(
        f"/api/tasks/product-pools/{seeded['pool_id']}",
        headers=headers,
        json={
            "name": "Updated Existing Pool",
            "allow_repeat_in_same_batch": True,
            "metadata_json": {"source": "api-update"},
        },
    )
    assert update_response.status_code == 200, update_response.text
    updated = update_response.json()
    assert updated["name"] == "Updated Existing Pool"
    assert updated["allowRepeatInSameBatch"] is True
    assert updated["metadataJson"] == {"source": "api-update"}

    update_audit_response = client.get(
        "/api/runtime/audit-logs",
        headers=headers,
        params={
            "account_id": seeded["account_id"],
            "target_type": "task_product_pool",
            "target_id": seeded["pool_id"],
        },
    )
    assert update_audit_response.status_code == 200, update_audit_response.text
    update_logs = update_audit_response.json()
    update_matching = [item for item in update_logs if item["action"] == "task_product_pool_updated"]
    assert len(update_matching) == 1

    add_items_response = client.post(
        f"/api/tasks/product-pools/{seeded['pool_id']}/items",
        headers=headers,
        json={
            "items": [
                {
                    "product_id": "existing-product-2",
                    "product_name": "Existing Product 2",
                    "image_url": "https://example.com/existing-2.png",
                    "price": "22.00",
                    "currency": "USD",
                    "product_description": "Existing Product 2 Description",
                    "status": "active",
                    "sort_order": 2,
                }
            ]
        },
    )
    assert add_items_response.status_code == 200, add_items_response.text
    added = add_items_response.json()
    assert added["itemCount"] == 2
    assert added["items"][1]["productId"] == "existing-product-2"

    add_audit_response = client.get(
        "/api/runtime/audit-logs",
        headers=headers,
        params={
            "account_id": seeded["account_id"],
            "target_type": "task_product_pool",
            "target_id": seeded["pool_id"],
        },
    )
    assert add_audit_response.status_code == 200, add_audit_response.text
    add_logs = add_audit_response.json()
    add_matching = [item for item in add_logs if item["action"] == "task_product_pool_items_added"]
    assert len(add_matching) == 1
    assert add_matching[0]["payload"]["added_item_count"] == 1

    import_response = client.post(
        f"/api/tasks/product-pools/{seeded['pool_id']}/import",
        headers=headers,
        json={
            "items": [
                {
                    "product_id": "imported-product-1",
                    "product_name": "Imported Product 1",
                    "image_url": "https://example.com/imported-1.png",
                    "price": "30.00",
                    "currency": "USD",
                    "product_description": "Imported Product 1 Description",
                    "status": "active",
                    "sort_order": 1,
                }
            ],
            "replace_existing": True,
        },
    )
    assert import_response.status_code == 200, import_response.text
    imported = import_response.json()
    assert imported["itemCount"] == 1
    assert imported["items"][0]["productId"] == "imported-product-1"

    import_audit_response = client.get(
        "/api/runtime/audit-logs",
        headers=headers,
        params={
            "account_id": seeded["account_id"],
            "target_type": "task_product_pool",
            "target_id": seeded["pool_id"],
        },
    )
    assert import_audit_response.status_code == 200, import_audit_response.text
    import_logs = import_audit_response.json()
    import_matching = [item for item in import_logs if item["action"] == "task_product_pool_items_imported"]
    assert len(import_matching) == 1
    assert import_matching[0]["payload"]["replace_existing"] is True


def test_task_product_pool_item_update_and_delete(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    seeded = _seed_task_product_pool_api_scope(db_session_factory)
    headers = {
        "X-Actor-Id": "operator-task-pool-item",
        "X-Actor-Role": "operator",
        "X-Actor-Account-Ids": seeded["account_id"],
    }

    detail_response = client.get(f"/api/tasks/product-pools/{seeded['pool_id']}", headers=headers)
    assert detail_response.status_code == 200, detail_response.text
    item_id = detail_response.json()["items"][0]["id"]

    update_response = client.patch(
        f"/api/tasks/product-pool-items/{item_id}",
        headers=headers,
        json={
            "product_name": "Existing Product 1 Updated",
            "price": "18.80",
            "status": "inactive",
        },
    )
    assert update_response.status_code == 200, update_response.text
    updated = update_response.json()
    assert updated["productName"] == "Existing Product 1 Updated"
    assert updated["price"] == "18.80"
    assert updated["status"] == "inactive"

    item_audit_response = client.get(
        "/api/runtime/audit-logs",
        headers=headers,
        params={
            "account_id": seeded["account_id"],
            "target_type": "task_product_pool_item",
            "target_id": item_id,
        },
    )
    assert item_audit_response.status_code == 200, item_audit_response.text
    item_logs = item_audit_response.json()
    update_matching = [item for item in item_logs if item["action"] == "task_product_pool_item_updated"]
    assert len(update_matching) == 1

    delete_response = client.delete(
        f"/api/tasks/product-pool-items/{item_id}",
        headers=headers,
    )
    assert delete_response.status_code == 204, delete_response.text

    delete_audit_response = client.get(
        "/api/runtime/audit-logs",
        headers=headers,
        params={
            "account_id": seeded["account_id"],
            "target_type": "task_product_pool_item",
            "target_id": item_id,
        },
    )
    assert delete_audit_response.status_code == 200, delete_audit_response.text
    delete_logs = delete_audit_response.json()
    delete_matching = [item for item in delete_logs if item["action"] == "task_product_pool_item_deleted"]
    assert len(delete_matching) == 1

    final_detail_response = client.get(f"/api/tasks/product-pools/{seeded['pool_id']}", headers=headers)
    assert final_detail_response.status_code == 200, final_detail_response.text
    final_detail = final_detail_response.json()
    assert final_detail["itemCount"] == 0
    assert final_detail["items"] == []
