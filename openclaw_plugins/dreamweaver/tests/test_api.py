"""Unit tests for DreamWeaver FastAPI routes."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI

from openclaw_plugins.dreamweaver.api import create_router
from openclaw_plugins.dreamweaver.config import DreamWeaverConfig
from openclaw_plugins.dreamweaver.database import DreamRepository
from openclaw_plugins.dreamweaver.dream_service import DreamService
from openclaw_plugins.dreamweaver.resource_monitor import ResourceConfig, ResourceSnapshot

import tempfile
from pathlib import Path


# ── Stub LLM ───────────────────────────────────────────────────────

class StubLLM:
    async def generate(self, system_prompt: str, user_prompt: str = "",
                       *, temperature: float = 0.7, max_tokens: int = 4096
                       ) -> tuple[str, int]:
        if "创新突破专家" in system_prompt:
            return "方案内容", 100
        if "严厉的审稿人" in system_prompt:
            return "漏洞1-5", 100
        if "公正的专家评委" in system_prompt:
            return '{"score_A": 8.0, "score_B": 6.0, "winner": "A", "reason": "ok"}', 100
        if "高级架构师" in system_prompt:
            return "改进方案", 100
        if "跨领域范式" in system_prompt:
            return "变异方案", 100
        return "{}", 50


class StubLLMDelayed:
    def __init__(self, delay: float = 0.1) -> None:
        self._delay = delay

    async def generate(self, system_prompt: str, user_prompt: str = "",
                       *, temperature: float = 0.7, max_tokens: int = 4096
                       ) -> tuple[str, int]:
        import asyncio
        await asyncio.sleep(self._delay)
        if "创新突破专家" in system_prompt:
            return "方案内容", 100
        if "严厉的审稿人" in system_prompt:
            return "漏洞1-5", 100
        if "公正的专家评委" in system_prompt:
            return '{"score_A": 8.0, "score_B": 6.0, "winner": "A", "reason": "ok"}', 100
        if "高级架构师" in system_prompt:
            return "改进方案", 100
        if "跨领域范式" in system_prompt:
            return "变异方案", 100
        return "{}", 50


# ── Fake probe ─────────────────────────────────────────────────────

class FakeProbe:
    def sample(self) -> ResourceSnapshot:
        return ResourceSnapshot(cpu_percent=10.0, memory_percent=20.0)


# ── Fixtures ───────────────────────────────────────────────────────

@pytest.fixture
def app_client() -> TestClient:
    config = DreamWeaverConfig(
        enabled=True,
        idle_timeout_seconds=900,
        max_iterations=2,
        convergence_rounds=10,
        mutation_interval=999,
    )
    monitor = __import__(
        "openclaw_plugins.dreamweaver.resource_monitor", fromlist=["ResourceMonitor"]
    ).ResourceMonitor(probe=FakeProbe(), config=ResourceConfig(retry_delay_seconds=0.01))

    svc = DreamService(config, StubLLM(), resource_monitor=monitor)

    import tempfile
    import os
    td = tempfile.mkdtemp()
    repo = DreamRepository(os.path.join(td, "test.db"))

    # We can't await async init in a sync fixture, so we use a workaround
    import sqlite3
    repo._conn = sqlite3.connect(repo.path, check_same_thread=False)
    repo._conn.row_factory = sqlite3.Row
    repo._conn.executescript(
        __import__("openclaw_plugins.dreamweaver.database", fromlist=["CREATE_TABLES_SQL"])
        .CREATE_TABLES_SQL
    )
    repo._conn.commit()

    router = create_router(svc, repo)
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


# ── Tests ──────────────────────────────────────────────────────────

def test_get_status_idle(app_client: TestClient) -> None:
    resp = app_client.get("/dream/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "idle"
    assert data["current_round"] == 0


def test_start_dream(app_client: TestClient) -> None:
    resp = app_client.post("/dream/start", json={"motif": "测试API母题"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True


def test_start_double_rejected() -> None:
    import asyncio
    config = DreamWeaverConfig(enabled=True, idle_timeout_seconds=900, max_iterations=5,
                               convergence_rounds=10, mutation_interval=999)
    slow_llm = StubLLMDelayed(delay=0.1)
    monitor = __import__("openclaw_plugins.dreamweaver.resource_monitor", fromlist=["ResourceMonitor"]
                        ).ResourceMonitor(probe=FakeProbe(), config=ResourceConfig(retry_delay_seconds=0.01))
    svc = DreamService(config, slow_llm, resource_monitor=monitor)
    import tempfile, os, sqlite3
    td = tempfile.mkdtemp()
    repo = DreamRepository(os.path.join(td, "test.db"))
    repo._conn = sqlite3.connect(repo.path, check_same_thread=False)
    repo._conn.row_factory = sqlite3.Row
    from openclaw_plugins.dreamweaver.database import CREATE_TABLES_SQL
    repo._conn.executescript(CREATE_TABLES_SQL)
    repo._conn.commit()
    router = create_router(svc, repo)
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    client.post("/dream/start", json={"motif": "first"})
    resp = client.post("/dream/start", json={"motif": "second"})
    assert resp.status_code == 409


def test_stop_when_idle_returns_404(app_client: TestClient) -> None:
    resp = app_client.post("/dream/stop")
    assert resp.status_code == 404


def test_history_empty(app_client: TestClient) -> None:
    resp = app_client.get("/dream/history")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []


def test_get_nonexistent_dream(app_client: TestClient) -> None:
    resp = app_client.get("/dream/nonexistent")
    assert resp.status_code == 404


def test_history_pagination(app_client: TestClient) -> None:
    resp = app_client.get("/dream/history?limit=5&offset=0&sort_by=best_score")
    assert resp.status_code == 200
