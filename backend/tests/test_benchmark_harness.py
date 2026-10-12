import asyncio

import httpx
import pytest

from scripts.benchmark_harness import BenchmarkHarness


def make_harness(initial_activation, monkeypatch, *, task_fails=False):
    state = {"activated": initial_activation}

    def handle_request(request):
        if request.method == "GET" and request.url.path == "/":
            return httpx.Response(200, json={"agent_activated": state["activated"]})
        if request.method == "POST" and request.url.path == "/activate":
            state["activated"] = True
            return httpx.Response(200, json={"status": "activated"})
        if request.method == "POST" and request.url.path == "/deactivate":
            state["activated"] = False
            return httpx.Response(200, json={"status": "deactivated"})
        return httpx.Response(200, json={"code": "result [1]"})

    harness = BenchmarkHarness()

    async def mock_client():
        return httpx.AsyncClient(
            transport=httpx.MockTransport(handle_request),
            base_url="http://benchmark.test",
        )

    monkeypatch.setattr(harness, "_client", mock_client)

    if task_fails:
        async def fail_task(_task):
            raise RuntimeError("benchmark task failed")

        monkeypatch.setattr(harness, "run_task", fail_task)

    return harness, state


@pytest.mark.parametrize("initial_activation", [False, True])
@pytest.mark.parametrize("task_fails", [False, True])
def test_evaluate_tasks_restores_activation_state(initial_activation, task_fails, monkeypatch):
    harness, state = make_harness(initial_activation, monkeypatch, task_fails=task_fails)
    tasks = [{"name": "sample", "endpoint": "/task", "payload": {}}]

    if task_fails:
        with pytest.raises(RuntimeError, match="benchmark task failed"):
            asyncio.run(harness.evaluate_tasks(tasks))
    else:
        results = asyncio.run(harness.evaluate_tasks(tasks))
        assert results[0]["passed"] is True

    assert state["activated"] is initial_activation