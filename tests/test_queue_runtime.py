import asyncio

from fastapi.testclient import TestClient

from app.api.deps import get_db_session
from app.core.settings import get_settings
from app.services.queue_service import QueueService
from app.services.runtime_state import RuntimeStateStore
from app.worker import process_reserved_job


def test_mock_inbound_message_queues_ai_job_and_exposes_queue_stats(
    client: TestClient,
) -> None:
    response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "mock-account-queue-1",
            "conversation_id": "conv-queue-1",
            "user_id": "user-queue-1",
            "text": "hello from queue",
            "mode": "ai",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["outbound"]["text"] is None
    assert payload["outbound"]["delivery_mode"] == "ai_async_queued"
    assert payload["queue"]["queue"] == "ai_generation"

    stats_response = client.get("/api/queue/stats")
    assert stats_response.status_code == 200
    stats = stats_response.json()

    assert stats["queues"][0]["queue"] == "ai_generation"
    assert stats["queues"][0]["queued"] == 1
    assert stats["queues"][0]["retried_total"] == 0
    assert stats["recent_failed_jobs"] == []


def test_worker_processes_queued_ai_reply_and_persists_outbound_reply(client: TestClient) -> None:
    response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "mock-account-queue-2",
            "conversation_id": "conv-queue-2",
            "user_id": "user-queue-2",
            "text": "need async reply",
            "mode": "ai",
        },
    )
    payload = response.json()
    job_id = payload["queue"]["job_id"]

    queue_service = QueueService(get_settings())
    job = queue_service.get_job(job_id)
    assert job is not None

    session_generator = client.app.dependency_overrides[get_db_session]()
    session = next(session_generator)
    try:
        processed_job = asyncio.run(
            process_reserved_job(
                "ai_generation",
                queue_service,
                runtime_state=RuntimeStateStore(session),
            )
        )
    finally:
        session_generator.close()

    assert processed_job is not None
    assert processed_job.status == "completed"
    assert processed_job.completed_at is not None
    assert processed_job.attempt_count == 1

    job = queue_service.get_job(job_id)
    assert job is not None
    assert job.status == "completed"
    assert job.result is not None

    stats_response = client.get("/api/queue/stats")
    assert stats_response.status_code == 200
    stats = stats_response.json()
    assert stats["queues"][0]["queued"] == 0
    assert stats["queues"][0]["processing"] == 0
    assert stats["queues"][0]["completed"] == 1
    assert stats["queues"][0]["failed"] == 0
    assert stats["queues"][0]["retried_total"] == 0
    assert stats["recent_failed_jobs"] == []

    messages_response = client.get("/api/conversations/mock-account-queue-2/conv-queue-2/messages")
    assert messages_response.status_code == 200
    messages = messages_response.json()

    assert messages[-1]["direction"] == "outbound"
    assert messages[-1]["ai_generated"] is True
    assert "MockAI" in messages[-1]["original_text"]


def test_worker_retries_failed_ai_job_and_exposes_failure_metadata(
    client: TestClient,
    monkeypatch,
) -> None:
    async def failing_process_ai_generation_job(
        payload: dict[str, object],
        settings,
        runtime_state=None,
    ) -> dict[str, object]:
        del settings, runtime_state
        raise RuntimeError(f"boom:{payload['user_message']}")

    monkeypatch.setattr(
        "app.worker.process_ai_generation_job",
        failing_process_ai_generation_job,
    )

    response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "mock-account-queue-3",
            "conversation_id": "conv-queue-3",
            "user_id": "user-queue-3",
            "text": "please fail",
            "mode": "ai",
        },
    )
    assert response.status_code == 200

    queue_service = QueueService(get_settings())

    for _ in range(get_settings().queue_max_retries + 1):
        session_generator = client.app.dependency_overrides[get_db_session]()
        session = next(session_generator)
        try:
            last_job = asyncio.run(
                process_reserved_job(
                    "ai_generation",
                    queue_service,
                    runtime_state=RuntimeStateStore(session),
                )
            )
        finally:
            session_generator.close()

    assert last_job is not None
    assert last_job.status == "dead_letter"
    assert last_job.retry_count == get_settings().queue_max_retries
    assert last_job.attempt_count == get_settings().queue_max_retries + 1
    assert last_job.error == "boom:please fail"
    assert last_job.failed_at is not None
    assert last_job.error_history == [
        "boom:please fail",
        "boom:please fail",
        "boom:please fail",
        "boom:please fail",
    ]

    stats_response = client.get("/api/queue/stats")
    assert stats_response.status_code == 200
    stats = stats_response.json()
    assert stats["queues"][0]["queued"] == 0
    assert stats["queues"][0]["failed"] == 0
    assert stats["queues"][0]["retried_total"] == get_settings().queue_max_retries
    assert stats["dead_letter_count"] == 1
    assert len(stats["recent_failed_jobs"]) == 0
