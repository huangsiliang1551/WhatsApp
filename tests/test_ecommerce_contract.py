from typing import Any

from fastapi.testclient import TestClient


LIST_ORDERS_PATH = "/api/ecommerce/orders"
ORDER_LOOKUP_PATH = "/api/ecommerce/orders/{order_id}"
SHIPMENT_LOOKUP_PATH = "/api/ecommerce/shipments/{tracking_number}"


def _get_operation(client: TestClient, path: str, method: str = "get") -> dict[str, Any]:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    operation = response.json().get("paths", {}).get(path, {}).get(method)
    assert operation is not None
    return operation


def test_ecommerce_list_and_lookup_routes_require_account_scope(client: TestClient) -> None:
    list_operation = _get_operation(client, LIST_ORDERS_PATH)
    order_lookup_operation = _get_operation(client, ORDER_LOOKUP_PATH)
    shipment_lookup_operation = _get_operation(client, SHIPMENT_LOOKUP_PATH)

    list_parameters = {
        (item["name"], item["in"]): item for item in list_operation.get("parameters", [])
    }
    order_lookup_parameters = {
        (item["name"], item["in"]): item
        for item in order_lookup_operation.get("parameters", [])
    }
    shipment_lookup_parameters = {
        (item["name"], item["in"]): item
        for item in shipment_lookup_operation.get("parameters", [])
    }

    assert ("account_id", "query") in list_parameters
    assert list_parameters[("account_id", "query")]["required"] is True

    assert ("order_id", "path") in order_lookup_parameters
    assert order_lookup_parameters[("order_id", "path")]["required"] is True
    assert ("account_id", "query") in order_lookup_parameters
    assert order_lookup_parameters[("account_id", "query")]["required"] is True

    assert ("tracking_number", "path") in shipment_lookup_parameters
    assert shipment_lookup_parameters[("tracking_number", "path")]["required"] is True
    assert ("account_id", "query") in shipment_lookup_parameters
    assert shipment_lookup_parameters[("account_id", "query")]["required"] is True


def test_ecommerce_lookup_rejects_requests_without_account_scope(client: TestClient) -> None:
    assert client.get("/api/ecommerce/orders/MOCK-1001").status_code == 422
    assert client.get("/api/ecommerce/shipments/YTES123456789").status_code == 422


def test_ecommerce_lookup_routes_document_404_and_409_responses(client: TestClient) -> None:
    order_lookup_operation = _get_operation(client, ORDER_LOOKUP_PATH)
    shipment_lookup_operation = _get_operation(client, SHIPMENT_LOOKUP_PATH)

    assert "404" in order_lookup_operation.get("responses", {})
    assert "409" in order_lookup_operation.get("responses", {})
    assert "404" in shipment_lookup_operation.get("responses", {})
    assert "409" in shipment_lookup_operation.get("responses", {})
