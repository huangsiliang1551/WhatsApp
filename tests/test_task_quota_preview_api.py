from fastapi.testclient import TestClient


def _headers() -> dict[str, str]:
    return {
        "X-Actor-Id": "operator-task-preview-api",
        "X-Actor-Role": "operator",
        "X-Actor-Account-Ids": "acct-preview",
    }


def test_preview_task_quota_average_allocation(client: TestClient) -> None:
    response = client.post(
        "/api/tasks/quotas/preview",
        headers=_headers(),
        json={
            "package_count": 3,
            "day_total_amount": "300.00",
            "amount_allocation_mode": "average",
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["packageAmounts"] == ["100.00", "100.00", "100.00"]
    assert payload["computedTotalAmount"] == "300.00"


def test_preview_task_quota_incremental_allocation(client: TestClient) -> None:
    response = client.post(
        "/api/tasks/quotas/preview",
        headers=_headers(),
        json={
            "package_count": 3,
            "day_total_amount": "300.00",
            "amount_allocation_mode": "incremental",
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["packageAmounts"] == ["50.00", "100.00", "150.00"]


def test_preview_task_quota_manual_allocation_requires_exact_total(client: TestClient) -> None:
    response = client.post(
        "/api/tasks/quotas/preview",
        headers=_headers(),
        json={
            "package_count": 3,
            "day_total_amount": "300.00",
            "amount_allocation_mode": "manual",
            "package_amounts": ["100.00", "100.00", "50.00"],
        },
    )
    assert response.status_code == 409
