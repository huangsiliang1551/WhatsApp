from fastapi.testclient import TestClient


def test_list_mock_ecommerce_orders_by_account(client: TestClient) -> None:
    response = client.get(
        "/api/ecommerce/orders",
        params={"account_id": "demo-account-es"},
    )

    assert response.status_code == 200
    payload = response.json()

    assert len(payload) == 1
    assert payload[0]["account_id"] == "demo-account-es"
    assert payload[0]["order_id"] == "MOCK-1001"
    assert payload[0]["payment_status"] == "paid"
    assert payload[0]["fulfillment_status"] == "shipped"
    assert payload[0]["tracking_number"] == "YTES123456789"


def test_get_mock_ecommerce_order_detail_and_write_audit_log(client: TestClient) -> None:
    response = client.get(
        "/api/ecommerce/orders/MOCK-2001",
        params={"account_id": "demo-account-fr"},
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["account_id"] == "demo-account-fr"
    assert payload["customer_name"] == "Camille Martin"
    assert payload["shipping_address"] == "15 Rue de Rivoli, Paris, FR"
    assert len(payload["items"]) == 2
    assert payload["shipments"][0]["tracking_number"] == "FRPOST987654321"

    audit_response = client.get(
        "/api/runtime/audit-logs",
        params={
            "account_id": "demo-account-fr",
            "action": "ecommerce_order_queried",
        },
    )
    assert audit_response.status_code == 200
    audit_logs = audit_response.json()

    assert len(audit_logs) == 1
    assert audit_logs[0]["target_type"] == "order"
    assert audit_logs[0]["target_id"] == "MOCK-2001"
    assert audit_logs[0]["payload"]["provider"] == "mock"


def test_get_mock_ecommerce_shipment_detail(client: TestClient) -> None:
    response = client.get(
        "/api/ecommerce/shipments/ARAMEX556677889",
        params={"account_id": "demo-account-ar"},
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["account_id"] == "demo-account-ar"
    assert payload["order_id"] == "MOCK-3001"
    assert payload["carrier"] == "Aramex"
    assert payload["status"] == "delivered"
    assert payload["recipient_name"] == "Omar Hassan"
    assert payload["events"][-1]["status"] == "delivered"


def test_ecommerce_lookup_is_scoped_by_account(client: TestClient) -> None:
    order_response = client.get(
        "/api/ecommerce/orders/MOCK-1001",
        params={"account_id": "demo-account-fr"},
    )
    shipment_response = client.get(
        "/api/ecommerce/shipments/YTES123456789",
        params={"account_id": "demo-account-ar"},
    )

    assert order_response.status_code == 404
    assert "demo-account-fr" in order_response.json()["detail"]
    assert shipment_response.status_code == 404
    assert "demo-account-ar" in shipment_response.json()["detail"]
