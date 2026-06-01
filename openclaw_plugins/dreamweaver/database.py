"""DreamWeaver SQLite database layer (PRD §7.1).

Manages two tables::

    dreams           — one row per dream session
    dream_iterations — one row per agent call (Genius/Critic/Judge/Refiner/Mutator)
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from .models import AgentRole, DreamStatus
from .self_play import DreamResult, IterationLog


# ── DDL ────────────────────────────────────────────────────────────

CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS dreams (
    id TEXT PRIMARY KEY,
    motif TEXT NOT NULL,
    status TEXT DEFAULT 'idle',
    start_time TEXT,
    end_time TEXT,
    iterations INTEGER DEFAULT 0,
    best_score REAL,
    outcome_path TEXT,
    tags TEXT DEFAULT '',
    model_used TEXT DEFAULT '',
    convergence_reason TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS dream_iterations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dream_id TEXT NOT NULL,
    round INTEGER NOT NULL,
    role TEXT NOT NULL,
    prompt TEXT NOT NULL,
    response TEXT NOT NULL,
    score REAL,
    tokens_used INTEGER DEFAULT 0,
    timestamp TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (dream_id) REFERENCES dreams(id)
);

CREATE INDEX IF NOT EXISTS idx_dreams_status ON dreams(status);
CREATE INDEX IF NOT EXISTS idx_dreams_created ON dreams(created_at);
CREATE INDEX IF NOT EXISTS idx_iterations_dream ON dream_iterations(dream_id);
CREATE INDEX IF NOT EXISTS idx_iterations_role ON dream_iterations(role);
"""


# ── Repository ─────────────────────────────────────────────────────

@dataclass
class DreamRepository:
    """Async-friendly SQLite repository for dream data.

    Usage::

        repo = DreamRepository("openclaw_data/dreamweaver.db")
        await repo.init()
        await repo.insert_dream(dream_id, motif, ...)
        history = await repo.list_dreams(limit=20)
    """

    path: str

    def __post_init__(self) -> None:
        self._conn: Optional[sqlite3.Connection] = None

    # ── Lifecycle ──────────────────────────────────────────────

    async def init(self) -> None:
        """Create tables and indexes if they don't exist."""
        conn = self._get_conn()
        conn.executescript(CREATE_TABLES_SQL)
        conn.commit()

    async def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    # ── Dreams CRUD ────────────────────────────────────────────

    async def insert_dream(
        self,
        dream_id: str,
        motif: str,
        *,
        status: str = "running",
        tags: str = "",
        model_used: str = "",
    ) -> None:
        conn = self._get_conn()
        conn.execute(
            """INSERT OR REPLACE INTO dreams
               (id, motif, status, start_time, tags, model_used)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (dream_id, motif, status, _now_iso(), tags, model_used),
        )
        conn.commit()

    async def update_dream(
        self,
        dream_id: str,
        *,
        status: Optional[str] = None,
        end_time: Optional[str] = None,
        iterations: Optional[int] = None,
        best_score: Optional[float] = None,
        outcome_path: Optional[str] = None,
        convergence_reason: Optional[str] = None,
    ) -> None:
        fields: list[str] = []
        params: list[Any] = []
        for name, val in [
            ("status", status),
            ("end_time", end_time),
            ("iterations", iterations),
            ("best_score", best_score),
            ("outcome_path", outcome_path),
            ("convergence_reason", convergence_reason),
        ]:
            if val is not None:
                fields.append(f"{name}=?")
                params.append(val)
        if not fields:
            return
        params.append(dream_id)
        conn = self._get_conn()
        conn.execute(f"UPDATE dreams SET {', '.join(fields)} WHERE id=?", params)
        conn.commit()

    async def get_dream(self, dream_id: str) -> Optional[dict[str, Any]]:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM dreams WHERE id=?", (dream_id,)
        ).fetchone()
        if row is None:
            return None
        return dict(row)

    async def list_dreams(
        self,
        *,
        limit: int = 20,
        offset: int = 0,
        sort_by: str = "created_at",
    ) -> list[dict[str, Any]]:
        valid_sorts = {"created_at", "best_score", "iterations"}
        if sort_by not in valid_sorts:
            sort_by = "created_at"
        conn = self._get_conn()
        rows = conn.execute(
            f"SELECT * FROM dreams ORDER BY {sort_by} DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [dict(r) for r in rows]

    async def delete_dream(self, dream_id: str) -> None:
        conn = self._get_conn()
        conn.execute("DELETE FROM dream_iterations WHERE dream_id=?", (dream_id,))
        conn.execute("DELETE FROM dreams WHERE id=?", (dream_id,))
        conn.commit()

    async def count_dreams(self) -> int:
        conn = self._get_conn()
        row = conn.execute("SELECT COUNT(*) FROM dreams").fetchone()
        return int(row[0]) if row else 0

    # ── Iterations ─────────────────────────────────────────────

    async def insert_iterations(
        self, dream_id: str, logs: list[IterationLog]
    ) -> None:
        conn = self._get_conn()
        rows = [
            (
                dream_id,
                log.round,
                log.role,
                log.prompt,
                log.response,
                log.score,
                log.tokens_used,
                _ts_iso(log.timestamp),
            )
            for log in logs
        ]
        conn.executemany(
            """INSERT INTO dream_iterations
               (dream_id, round, role, prompt, response, score, tokens_used, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )
        conn.commit()

    async def get_iterations(self, dream_id: str) -> list[dict[str, Any]]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM dream_iterations WHERE dream_id=? ORDER BY id",
            (dream_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    # ── Persist full DreamResult ───────────────────────────────

    async def save_result(self, dream_id: str, result: DreamResult) -> None:
        """One-shot: update dream row + insert all iteration logs."""
        await self.update_dream(
            dream_id,
            status=result.convergence_reason,
            end_time=_ts_iso(result.finished_at),
            iterations=result.total_iterations,
            best_score=result.best_score,
            convergence_reason=result.convergence_reason,
        )
        if result.logs:
            await self.insert_iterations(dream_id, result.logs)

    # ── Internal ───────────────────────────────────────────────

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
        return self._conn


# ── Helpers ────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _ts_iso(ts: float) -> str:
    return datetime.fromtimestamp(ts).isoformat(timespec="seconds")
