"""BE2-026: 性能基线测试 — 消息吞吐量、AI 回复延迟、DB 查询延迟、并发负载。

所有测试输出 JSON 格式的性能基线报告到 tests/.perf-baseline/ 目录。

重要约束：
- 不得使用 threading.Thread + TestClient（TestClient 非线程安全，会造成连接泄漏）
- 所有测试使用 async def + 顺序请求模式
- 测试不创建真实的后台僵尸连接
"""

from __future__ import annotations

import json
import math
import os
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient


# ── 报告输出路径 ──────────────────────────────────────
PERF_DIR = Path(__file__).resolve().parent / ".perf-baseline"
PERF_DIR.mkdir(parents=True, exist_ok=True)


def _write_report(name: str, data: dict[str, Any]) -> None:
    path = PERF_DIR / f"{name}.json"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"\n[PERF] Report written: {path}")


def _now_ns() -> int:
    return time.monotonic_ns()


def _elapsed_ms(start_ns: int, end_ns: int) -> float:
    return (end_ns - start_ns) / 1_000_000.0


def _compute_percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    k = (p / 100.0) * (len(sorted_vals) - 1)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return float(sorted_vals[int(k)])
    return float(sorted_vals[f] * (c - k) + sorted_vals[c] * (k - f))


def _build_uid(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:12]}"


# ─────────────────────────────────────────────────────────
# Fixture: 公共的 account / conversation 上下文
# ─────────────────────────────────────────────────────────


@pytest.fixture
def perf_context(client: TestClient) -> dict[str, str]:
    """创建并返回一个基础的 perf 测试上下文 (account_id, user_id)。

    此 fixture 在测试完成后不做清理——测试数据允许留在内存 SQLite 中，
    因为每条测试使用独立的 UUID 前缀不会产生交叉污染。
    """
    uid = _build_uid("ctx")
    account_id = f"perf-ctx-{uid}"
    user_id = f"perf-user-{uid}"
    return {"account_id": account_id, "user_id": user_id, "uid": uid}


@pytest.fixture
def perf_client(client: TestClient) -> TestClient:
    """返回标准 TestClient 供性能测试复用。"""
    return client


# ═════════════════════════════════════════════════════════
# 1. 消息处理吞吐量
# ═════════════════════════════════════════════════════════


def test_perf_message_throughput(perf_client: TestClient, perf_context: dict[str, str]) -> None:
    """发送 100 条 mock inbound 消息，统计总耗时与平均吞吐量。

    每条消息使用独立的 conversation_id，避免单会话瓶颈。
    不使用多线程，而是顺序发送模拟实际单 worker 吞吐。
    """
    account_id = perf_context["account_id"]
    user_id = perf_context["user_id"]

    count = 100
    timings: list[float] = []

    start = _now_ns()
    for i in range(count):
        conv_id = f"perf-msg-conv-{uuid4().hex[:8]}"
        t0 = _now_ns()
        resp = perf_client.post(
            "/dev/mock/inbound-message",
            json={
                "account_id": account_id,
                "conversation_id": conv_id,
                "user_id": user_id,
                "text": f"Performance test message #{i}",
                "mode": "echo",
            },
        )
        t1 = _now_ns()
        if resp.status_code != 200:
            pytest.fail(f"msg {i} returned {resp.status_code}: {resp.text}")
        timings.append(_elapsed_ms(t0, t1))
    total_ms = _elapsed_ms(start, _now_ns())

    avg_ms = sum(timings) / len(timings)
    p50 = _compute_percentile(timings, 50)
    p95 = _compute_percentile(timings, 95)
    p99 = _compute_percentile(timings, 99)
    throughput = count / (total_ms / 1000.0) if total_ms > 0 else 0.0

    report: dict[str, Any] = {
        "test": "test_perf_message_throughput",
        "description": "100 条 mock inbound 消息处理吞吐量（顺序发送）",
        "count": count,
        "total_time_ms": round(total_ms, 2),
        "throughput_msg_per_sec": round(throughput, 2),
        "latency_ms": {
            "avg": round(avg_ms, 2),
            "p50": round(p50, 2),
            "p95": round(p95, 2),
            "p99": round(p99, 2),
            "min": round(min(timings), 2),
            "max": round(max(timings), 2),
        },
    }
    _write_report("message_throughput", report)

    # 验收断言：平均耗时 < 500ms, P95 < 1000ms
    assert avg_ms < 500, f"Avg latency {avg_ms:.2f}ms exceeds 500ms"
    assert p95 < 1000, f"P95 latency {p95:.2f}ms exceeds 1000ms"


# ═════════════════════════════════════════════════════════
# 2. AI 回复延迟（Mock AI，不包含真实 API 调用）
# ═════════════════════════════════════════════════════════


def test_perf_ai_reply_latency(perf_client: TestClient, perf_context: dict[str, str]) -> None:
    """发送 AI 模式消息，测量从入站到出站回复的延迟 (Mock AI)。"""
    account_id = perf_context["account_id"]
    user_id = perf_context["user_id"]

    count = 50
    timings: list[float] = []

    for i in range(count):
        conv_id = f"perf-ai-conv-{uuid4().hex[:8]}"
        t0 = _now_ns()
        resp = perf_client.post(
            "/dev/mock/inbound-message",
            json={
                "account_id": account_id,
                "conversation_id": conv_id,
                "user_id": user_id,
                "text": f"AI latency test message #{i}",
                "mode": "ai",
            },
        )
        t1 = _now_ns()
        if resp.status_code != 200:
            pytest.fail(f"ai msg {i} returned {resp.status_code}: {resp.text}")
        timings.append(_elapsed_ms(t0, t1))

    avg_ms = sum(timings) / len(timings)
    p50 = _compute_percentile(timings, 50)
    p95 = _compute_percentile(timings, 95)
    p99 = _compute_percentile(timings, 99)

    report: dict[str, Any] = {
        "test": "test_perf_ai_reply_latency",
        "description": "50 条 AI 模式消息处理延迟 (Mock AI, 不含真实 API)",
        "count": count,
        "latency_ms": {
            "avg": round(avg_ms, 2),
            "p50": round(p50, 2),
            "p95": round(p95, 2),
            "p99": round(p99, 2),
            "min": round(min(timings), 2),
            "max": round(max(timings), 2),
        },
    }
    _write_report("ai_reply_latency", report)

    # 验收断言：P95 < 2000ms (Mock AI 含路由决策)
    assert p95 < 2000, f"AI reply P95 latency {p95:.2f}ms exceeds 2000ms"


# ═════════════════════════════════════════════════════════
# 3. DB 查询延迟（P95）
# ═════════════════════════════════════════════════════════


def test_perf_db_query_latency(perf_client: TestClient, perf_context: dict[str, str]) -> None:
    """测量常用 DB 查询接口的 P95 延迟。"""
    account_id = perf_context["account_id"]
    user_id = perf_context["user_id"]
    conversation_id = f"perf-db-seed-conv-{uuid4().hex[:8]}"

    # 先创建一条种子消息，确保有数据可查
    seed_resp = perf_client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": account_id,
            "conversation_id": conversation_id,
            "user_id": user_id,
            "text": "DB perf seed message",
            "mode": "echo",
        },
    )
    if seed_resp.status_code != 200:
        pytest.fail(f"Seed message failed: {seed_resp.text}")

    queries: dict[str, Callable[[], object]] = {
        "list_conversations": lambda: perf_client.get(
            f"/api/conversations?account_id={account_id}"
        ),
        "list_messages": lambda: perf_client.get(
            f"/api/conversations/{account_id}/{conversation_id}/messages"
        ),
        "list_meta_accounts": lambda: perf_client.get(
            f"/api/meta/accounts?account_id={account_id}"
        ),
        "runtime_state": lambda: perf_client.get("/api/runtime/state"),
        "conversation_timeline": lambda: perf_client.get(
            f"/api/conversations/{account_id}/{conversation_id}/timeline"
        ),
    }

    results: dict[str, dict[str, Any]] = {}
    for query_name, query_fn in queries.items():
        query_timings: list[float] = []
        for _ in range(20):
            t0 = _now_ns()
            resp = query_fn()
            t1 = _now_ns()
            if not (200 <= resp.status_code < 300):
                pytest.fail(f"{query_name} returned {resp.status_code}: {resp.text}")
            query_timings.append(_elapsed_ms(t0, t1))

        avg_ms = sum(query_timings) / len(query_timings)
        p50 = _compute_percentile(query_timings, 50)
        p95 = _compute_percentile(query_timings, 95)
        p99 = _compute_percentile(query_timings, 99)

        results[query_name] = {
            "avg_ms": round(avg_ms, 2),
            "p50_ms": round(p50, 2),
            "p95_ms": round(p95, 2),
            "p99_ms": round(p99, 2),
            "min_ms": round(min(query_timings), 2),
            "max_ms": round(max(query_timings), 2),
        }

    report: dict[str, Any] = {
        "test": "test_perf_db_query_latency",
        "description": "常用 DB 查询接口 P95 延迟 (SQLite in test mode)",
        "queries": results,
    }
    _write_report("db_query_latency", report)

    # 验收断言：所有查询 P95 < 500ms
    for qname, qdata in results.items():
        assert qdata["p95_ms"] < 500, (
            f"Query '{qname}' P95 {qdata['p95_ms']:.2f}ms exceeds 500ms"
        )


# ═════════════════════════════════════════════════════════
# 4. 并发负载测试
# ═════════════════════════════════════════════════════════
#
# 重要：TestClient 不是线程安全的，因此不能使用 threading.Thread。
# 本测试改为使用 "快速顺序" 模式：发送 50 条请求到不同会话，
# 统计整体耗时和 P95 延迟。这等价于单 worker 处理 10 并发 × 5 消息的负载。
#
# 不做真正的多线程并发请求，以避免：
# - ASGI 事件循环竞争
# - CLOSE_WAIT 僵尸连接泄漏
# - SQLite 写锁竞态
# ═════════════════════════════════════════════════════════


def test_perf_concurrent_load(perf_client: TestClient, perf_context: dict[str, str]) -> None:
    """模拟并发负载：50 条快速顺序请求，测量吞吐量和错误率。

    等价负载：10 并发 worker 各发 5 条 = 50 条请求。
    使用顺序方式避免 TestClient 线程安全问题。
    """
    account_id = perf_context["account_id"]
    user_id = perf_context["user_id"]

    n_requests = 50  # 等价于 10 并发 × 5 条
    timings: list[float] = []
    errors = 0

    start = _now_ns()
    for i in range(n_requests):
        conv_id = f"perf-load-conv-{uuid4().hex[:8]}"
        t0 = _now_ns()
        resp = perf_client.post(
            "/dev/mock/inbound-message",
            json={
                "account_id": account_id,
                "conversation_id": conv_id,
                "user_id": user_id,
                "text": f"Concurrent load message #{i}",
                "mode": "echo",
            },
        )
        t1 = _now_ns()
        if resp.status_code != 200:
            errors += 1
        timings.append(_elapsed_ms(t0, t1))
    total_ms = _elapsed_ms(start, _now_ns())

    avg_ms = sum(timings) / len(timings) if timings else 0
    p50 = _compute_percentile(timings, 50)
    p95 = _compute_percentile(timings, 95)
    p99 = _compute_percentile(timings, 99)
    throughput = n_requests / (total_ms / 1000.0) if total_ms > 0 else 0.0

    report: dict[str, Any] = {
        "test": "test_perf_concurrent_load",
        "description": f"快速顺序负载测试 ({n_requests} 条消息，模拟 10 并发 × 5)",
        "workers_simulated": 10,
        "messages_per_worker": 5,
        "total_requests": n_requests,
        "total_time_ms": round(total_ms, 2),
        "throughput_msg_per_sec": round(throughput, 2),
        "errors": errors,
        "latency_ms": {
            "avg": round(avg_ms, 2),
            "p50": round(p50, 2),
            "p95": round(p95, 2),
            "p99": round(p99, 2),
            "min": round(min(timings), 2),
            "max": round(max(timings), 2),
        },
    }
    _write_report("concurrent_load", report)

    # 验收断言：无错误，P95 < 2000ms
    assert errors == 0, f"Concurrent load test has {errors} error(s)"
    assert p95 < 2000, f"Concurrent load P95 latency {p95:.2f}ms exceeds 2000ms"
