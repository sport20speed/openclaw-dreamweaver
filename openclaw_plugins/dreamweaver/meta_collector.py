"""M1: Meta-feature collector — extracts 22 features from each dream episode.

Captures input features (motif side), process features (config side),
environment features, and output labels. Stores in meta_training_data table.
"""

from __future__ import annotations

import logging
import sqlite3
import time
from dataclasses import dataclass
from typing import Any, Optional

from .self_play import DreamResult, SelfPlayConfig

logger = logging.getLogger(__name__)

# ── Feature extraction ────────────────────────────────────────────

@dataclass
class MetaEpisode:
    dream_id: str
    # Input features
    motif_source: str = "manual"
    motif_length: int = 0
    motif_word_count: int = 0
    motif_has_question: bool = False
    motif_has_numbers: bool = False
    domain_tags: str = "[]"
    complexity_score: float = 0.5
    # Process features
    genius_temp: float = 0.85
    critic_temp: float = 0.75
    refiner_temp: float = 0.70
    judge_model: str = "deepseek-v4-flash"
    genius_model: str = "deepseek-v4-flash"
    max_iterations: int = 100
    mutation_interval: int = 10
    # Environment
    hour_of_day: int = 0
    day_of_week: int = 0
    total_tokens: int = 0
    duration_seconds: float = 0.0
    cpu_avg: float = 0.0
    memory_mb: float = 0.0
    api_call_count: int = 0
    # Output labels
    best_score: float = 0.0
    convergence_rounds: int = 0
    convergence_reason: str = "max_iterations"
    score_improvement: float = 0.0
    critic_fatal_count: int = 0
    ethical_blocks: int = 0


class MetaCollector:
    """Collects meta-episodes from completed dreams and stores to SQLite."""

    CREATE_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS meta_training_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        dream_id TEXT NOT NULL,
        -- Input features
        motif_source TEXT NOT NULL DEFAULT 'manual',
        motif_length INTEGER DEFAULT 0,
        motif_word_count INTEGER DEFAULT 0,
        motif_has_question INTEGER DEFAULT 0,
        motif_has_numbers INTEGER DEFAULT 0,
        domain_tags TEXT DEFAULT '[]',
        complexity_score REAL DEFAULT 0.5,
        -- Process features
        genius_temp REAL DEFAULT 0.85,
        critic_temp REAL DEFAULT 0.75,
        refiner_temp REAL DEFAULT 0.70,
        judge_model TEXT DEFAULT 'deepseek-v4-flash',
        genius_model TEXT DEFAULT 'deepseek-v4-flash',
        max_iterations INTEGER DEFAULT 100,
        mutation_interval INTEGER DEFAULT 10,
        -- Environment
        hour_of_day INTEGER DEFAULT 0,
        day_of_week INTEGER DEFAULT 0,
        total_tokens INTEGER DEFAULT 0,
        duration_seconds REAL DEFAULT 0,
        cpu_avg REAL DEFAULT 0,
        memory_mb REAL DEFAULT 0,
        api_call_count INTEGER DEFAULT 0,
        -- Output labels
        best_score REAL DEFAULT 0,
        convergence_rounds INTEGER DEFAULT 0,
        convergence_reason TEXT DEFAULT 'max_iterations',
        score_improvement REAL DEFAULT 0,
        critic_fatal_count INTEGER DEFAULT 0,
        ethical_blocks INTEGER DEFAULT 0,
        -- Metadata
        created_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (dream_id) REFERENCES dreams(id) ON DELETE CASCADE
    );
    CREATE INDEX IF NOT EXISTS idx_meta_source ON meta_training_data(motif_source);
    CREATE INDEX IF NOT EXISTS idx_meta_score ON meta_training_data(best_score);
    CREATE INDEX IF NOT EXISTS idx_meta_created ON meta_training_data(created_at);
    """

    def __init__(self, db_conn: sqlite3.Connection) -> None:
        self._conn = db_conn
        self._init_table()

    def _init_table(self) -> None:
        try:
            self._conn.executescript(self.CREATE_TABLE_SQL)
            self._conn.commit()
        except Exception:
            logger.exception("Failed to create meta_training_data table")

    def collect(
        self,
        dream_id: str,
        result: DreamResult,
        config: SelfPlayConfig,
        *,
        motif_source: str = "manual",
        domain_tags: list[str] | None = None,
    ) -> Optional[MetaEpisode]:
        """Extract features and insert into meta_training_data."""
        try:
            ep = self._extract(dream_id, result, config, motif_source, domain_tags or [])
            self._insert(ep)
            logger.info("M1: collected episode %s (score=%.1f)", dream_id, ep.best_score)
            return ep
        except Exception:
            logger.exception("M1: failed to collect episode %s", dream_id)
            return None

    def count(self) -> int:
        """Return total episodes collected."""
        try:
            row = self._conn.execute("SELECT COUNT(*) FROM meta_training_data").fetchone()
            return row[0] if row else 0
        except Exception:
            return 0

    # ── Internal ───────────────────────────────────────────────────

    def _extract(
        self,
        dream_id: str,
        result: DreamResult,
        config: SelfPlayConfig,
        motif_source: str,
        domain_tags: list[str],
    ) -> MetaEpisode:
        t = time.localtime(result.started_at)
        motif = result.motif

        # Input features
        motif_len = len(motif)
        motif_words = len(motif.replace(" ", ""))
        has_question = "?" in motif or "？" in motif or "如何" in motif or "怎么" in motif
        has_numbers = any(c.isdigit() for c in motif)

        # Process features
        genius_temp = config.creative_model_temperature
        critic_temp = 0.75
        refiner_temp = 0.70
        judge_temp = config.judge_model_temperature

        # Token stats from logs
        total_tokens = sum(log.tokens_used for log in result.logs)
        api_calls = len(result.logs)

        # Score improvement
        scores = [log.score for log in result.logs if log.score is not None]
        first_score = scores[0] if scores else result.best_score
        improvement = result.best_score - first_score

        # Critic fatal count
        critic_logs = [log for log in result.logs if log.role == "critic"]
        fatal_count = sum(1 for log in critic_logs if "致命" in (log.response or ""))

        # Environment
        duration = result.finished_at - result.started_at

        return MetaEpisode(
            dream_id=dream_id,
            motif_source=motif_source,
            motif_length=motif_len,
            motif_word_count=motif_words,
            motif_has_question=has_question,
            motif_has_numbers=has_numbers,
            domain_tags=str(domain_tags),
            complexity_score=min(1.0, motif_words / 100.0),
            genius_temp=genius_temp,
            critic_temp=critic_temp,
            refiner_temp=refiner_temp,
            judge_model=config.judge_model_temperature,
            genius_model=config.judge_model_temperature,
            max_iterations=config.max_iterations,
            mutation_interval=config.mutation_interval,
            hour_of_day=t.tm_hour,
            day_of_week=t.tm_wday,
            total_tokens=total_tokens,
            duration_seconds=duration,
            api_call_count=api_calls,
            best_score=result.best_score,
            convergence_rounds=result.total_iterations,
            convergence_reason=result.convergence_reason,
            score_improvement=round(improvement, 2),
            critic_fatal_count=fatal_count,
            ethical_blocks=0,
        )

    def _insert(self, ep: MetaEpisode) -> None:
        fields = [
            "dream_id", "motif_source", "motif_length", "motif_word_count",
            "motif_has_question", "motif_has_numbers", "domain_tags", "complexity_score",
            "genius_temp", "critic_temp", "refiner_temp", "judge_model", "genius_model",
            "max_iterations", "mutation_interval", "hour_of_day", "day_of_week",
            "total_tokens", "duration_seconds", "cpu_avg", "memory_mb", "api_call_count",
            "best_score", "convergence_rounds", "convergence_reason",
            "score_improvement", "critic_fatal_count", "ethical_blocks",
        ]
        values = tuple(getattr(ep, f) for f in fields if hasattr(ep, f))
        placeholders = ",".join(["?"] * len(values))
        cols = ",".join(fields)
        self._conn.execute(
            f"INSERT INTO meta_training_data ({cols}) VALUES ({placeholders})",
            values,
        )
        self._conn.commit()
