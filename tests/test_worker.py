import asyncio

import app.worker as worker_module


def test_process_reserved_job_returns_none_when_queue_is_empty(monkeypatch) -> None:
    called = False

    class FakeQueueService:
        def reserve_next_job(self, queue_name: str):
            del queue_name
            return None

    async def fake_process_ai_generation_job(payload, settings):
        del payload, settings
        nonlocal called
        called = True
        return {"status": "completed"}

    monkeypatch.setattr(worker_module, "process_ai_generation_job", fake_process_ai_generation_job)

    result = asyncio.run(worker_module.process_reserved_job("ai_generation", FakeQueueService()))

    assert result is None
    assert called is False


def test_process_reserved_job_completes_ai_generation(monkeypatch) -> None:
    class FakeQueueService:
        def __init__(self) -> None:
            self.completed_result: dict[str, object] | None = None
            self.failed_error: str | None = None

        def reserve_next_job(self, queue_name: str):
            class Job:
                payload = {
                    "account_id": "mock-account-worker",
                    "conversation_id": "conv-worker",
                    "recipient_id": "user-worker",
                    "user_message": "hello",
                    "language_code": "en",
                }

            class Reserved:
                job = Job()

            return Reserved()

        def mark_completed(self, job, result: dict[str, object]) -> None:
            self.completed_result = result

        def mark_failed(self, reserved, error: str) -> None:
            self.failed_error = error

    async def fake_process_ai_generation_job(payload, settings):
        return {"status": "completed", "reply_text": "ok"}

    fake_queue_service = FakeQueueService()
    monkeypatch.setattr(worker_module, "process_ai_generation_job", fake_process_ai_generation_job)

    asyncio.run(worker_module.process_reserved_job("ai_generation", fake_queue_service))

    assert fake_queue_service.completed_result == {"status": "completed", "reply_text": "ok"}
    assert fake_queue_service.failed_error is None


def test_process_reserved_job_passes_job_id_and_runtime_state(monkeypatch) -> None:
    runtime_state = object()
    captured: dict[str, object] = {}

    class FakeQueueService:
        def __init__(self) -> None:
            self.completed_result: dict[str, object] | None = None
            self.failed_error: str | None = None

        def reserve_next_job(self, queue_name: str):
            del queue_name

            class Job:
                job_id = "job-worker-1"
                payload = {
                    "account_id": "mock-account-worker",
                    "conversation_id": "conv-worker",
                    "recipient_id": "user-worker",
                    "user_message": "hello",
                    "language_code": "en",
                }

            class Reserved:
                job = Job()

            return Reserved()

        def mark_completed(self, job, result: dict[str, object]) -> dict[str, object]:
            del job
            self.completed_result = result
            return result

        def mark_failed(self, reserved, error: str) -> None:
            del reserved
            self.failed_error = error

    async def fake_process_ai_generation_job(payload, settings, runtime_state=None):
        del settings
        captured["payload"] = payload
        captured["runtime_state"] = runtime_state
        return {"status": "completed", "reply_text": "ok"}

    fake_queue_service = FakeQueueService()
    monkeypatch.setattr(worker_module, "process_ai_generation_job", fake_process_ai_generation_job)

    result = asyncio.run(
        worker_module.process_reserved_job(
            "ai_generation",
            fake_queue_service,
            runtime_state=runtime_state,
        )
    )

    assert result == {"status": "completed", "reply_text": "ok"}
    assert captured["payload"] == {
        "account_id": "mock-account-worker",
        "conversation_id": "conv-worker",
        "recipient_id": "user-worker",
        "user_message": "hello",
        "language_code": "en",
        "job_id": "job-worker-1",
    }
    assert captured["runtime_state"] is runtime_state
    assert fake_queue_service.completed_result == {"status": "completed", "reply_text": "ok"}
    assert fake_queue_service.failed_error is None


def test_process_reserved_job_marks_failure(monkeypatch) -> None:
    class FakeQueueService:
        def __init__(self) -> None:
            self.completed_result: dict[str, object] | None = None
            self.failed_error: str | None = None

        def reserve_next_job(self, queue_name: str):
            class Job:
                payload = {
                    "account_id": "mock-account-worker",
                    "conversation_id": "conv-worker",
                    "recipient_id": "user-worker",
                    "user_message": "hello",
                    "language_code": "en",
                }

            class Reserved:
                job = Job()

            return Reserved()

        def mark_completed(self, job, result: dict[str, object]) -> None:
            self.completed_result = result

        def mark_failed(self, reserved, error: str) -> None:
            self.failed_error = error

    async def fake_process_ai_generation_job(payload, settings):
        raise RuntimeError("boom")

    fake_queue_service = FakeQueueService()
    monkeypatch.setattr(worker_module, "process_ai_generation_job", fake_process_ai_generation_job)

    asyncio.run(worker_module.process_reserved_job("ai_generation", fake_queue_service))

    assert fake_queue_service.completed_result is None
    assert fake_queue_service.failed_error == "boom"
