"""Unit tests for DreamRepository (SQLite)."""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import pytest

from openclaw_plugins.dreamweaver.database import DreamRepository
from openclaw_plugins.dreamweaver.self_play import IterationLog


@pytest.fixture
def repo() -> DreamRepository:
    with tempfile.TemporaryDirectory() as td:
        r = DreamRepository(str(Path(td) / "test.db"))
        r._conn = sqlite3.connect(r.path, check_same_thread=False)
        r._conn.row_factory = sqlite3.Row
        r._conn.executescript(
            __import__("openclaw_plugins.dreamweaver.database", fromlist=["CREATE_TABLES_SQL"])
            .CREATE_TABLES_SQL
        )
        r._conn.commit()
        yield r
        r._conn.close()


# ── Schema ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tables_exist(repo: DreamRepository) -> None:
    conn = repo._get_conn()
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    names = [r[0] for r in tables]
    assert "dreams" in names
    assert "dream_iterations" in names


# ── Insert + read ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_insert_and_get_dream(repo: DreamRepository) -> None:
    await repo.insert_dream("20260601-001", "测试母题", tags="test,unit")
    row = await repo.get_dream("20260601-001")
    assert row is not None
    assert row["motif"] == "测试母题"
    assert row["tags"] == "test,unit"


@pytest.mark.asyncio
async def test_update_dream(repo: DreamRepository) -> None:
    await repo.insert_dream("20260601-002", "测试")
    await repo.update_dream("20260601-002", status="completed", best_score=8.5)
    row = await repo.get_dream("20260601-002")
    assert row["status"] == "completed"
    assert row["best_score"] == 8.5


@pytest.mark.asyncio
async def test_list_dreams(repo: DreamRepository) -> None:
    for i in range(5):
        await repo.insert_dream(f"d-{i}", f"motif-{i}")
    items = await repo.list_dreams(limit=3, offset=1)
    assert len(items) == 3


@pytest.mark.asyncio
async def test_count_dreams(repo: DreamRepository) -> None:
    assert await repo.count_dreams() == 0
    await repo.insert_dream("d-1", "m")
    await repo.insert_dream("d-2", "m")
    assert await repo.count_dreams() == 2


@pytest.mark.asyncio
async def test_delete_dream(repo: DreamRepository) -> None:
    await repo.insert_dream("d-del", "to delete")
    await repo.delete_dream("d-del")
    assert await repo.get_dream("d-del") is None


# ── Iterations ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_insert_iterations(repo: DreamRepository) -> None:
    await repo.insert_dream("d-iter", "motif")
    logs = [
        IterationLog(round=0, role="genius", prompt="p", response="r", tokens_used=100),
        IterationLog(round=1, role="critic", prompt="p2", response="r2", score=7.0),
    ]
    await repo.insert_iterations("d-iter", logs)
    rows = await repo.get_iterations("d-iter")
    assert len(rows) == 2
    assert rows[0]["role"] == "genius"
    assert rows[1]["role"] == "critic"


@pytest.mark.asyncio
async def test_delete_cascades_iterations(repo: DreamRepository) -> None:
    await repo.insert_dream("d-cascade", "motif")
    await repo.insert_iterations(
        "d-cascade",
        [IterationLog(round=0, role="genius", prompt="p", response="r")],
    )
    await repo.delete_dream("d-cascade")
    rows = await repo.get_iterations("d-cascade")
    assert len(rows) == 0
