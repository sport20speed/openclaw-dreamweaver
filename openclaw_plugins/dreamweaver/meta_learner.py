"""M2: MetaLearner — RandomForest parameter recommendation from past dreams.

Uses meta_training_data to learn: motif features → optimal execution parameters.
Trains when ≥ 20 episodes collected. Returns defaults with low confidence otherwise.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)

DEFAULTS = {"genius_temp": 0.85, "critic_temp": 0.75, "max_iterations": 100}


@dataclass
class MetaLearnerStats:
    total_episodes: int = 0
    model_ready: bool = False
    last_trained_at: Optional[str] = None
    feature_importance: dict[str, float] = field(default_factory=dict)
    current_recommendation: dict[str, Any] = field(default_factory=lambda: dict(DEFAULTS))
    confidence: float = 0.0


class MetaLearner:
    """Learns from past dreams to recommend better execution parameters."""

    FEATURE_COLS = [
        "motif_length", "motif_word_count", "motif_has_question", "motif_has_numbers",
        "complexity_score", "genius_temp", "critic_temp", "refiner_temp",
        "max_iterations", "mutation_interval", "hour_of_day", "day_of_week",
        "total_tokens", "duration_seconds", "api_call_count",
    ]
    TARGET_COLS = ["best_score", "convergence_rounds", "score_improvement"]
    MIN_SAMPLES = 20

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._model = None
        self._last_trained: float = 0.0
        self._stats = MetaLearnerStats()

    def recommend_params(
        self, motif: str, tags: list[str] | None = None, hour: int | None = None
    ) -> dict[str, Any]:
        """Recommend optimal parameters for a new dream motif."""
        if not self._model:
            # Try training if enough data
            self._maybe_train()
        if not self._model:
            return {**DEFAULTS, "confidence": 0.0}

        # Build feature vector
        features = [
            len(motif),
            len(motif.replace(" ", "")),
            1 if any(c in motif for c in "?？如何怎么") else 0,
            1 if any(c.isdigit() for c in motif) else 0,
            min(1.0, len(motif.replace(" ", "")) / 100.0),
            DEFAULTS["genius_temp"],
            DEFAULTS["critic_temp"],
            0.70,
            DEFAULTS["max_iterations"],
            10,
            hour or time.localtime().tm_hour,
            time.localtime().tm_wday,
            0, 0, 0,  # unknown: tokens, duration, api_calls
        ]

        try:
            pred = self._model.predict([features])[0]
        except Exception:
            logger.exception("M2 predict failed")
            return {**DEFAULTS, "confidence": 0.0}

        # Map prediction to output params
        # pred is a 3-vector: [best_score_pred, convergence_rounds_pred, improvement_pred]
        score_pred = float(pred[0]) if len(pred) > 0 else DEFAULTS["best_score"]
        conv_pred = int(pred[1]) if len(pred) > 1 else 100

        # Heuristic: temp lower for complex motifs, max_iters based on predicted convergence
        complexity = min(1.0, len(motif.replace(" ", "")) / 100.0)
        rec = {
            "genius_temp": round(max(0.5, DEFAULTS["genius_temp"] - complexity * 0.15), 2),
            "critic_temp": round(max(0.4, DEFAULTS["critic_temp"] - complexity * 0.1), 2),
            "max_iterations": max(20, min(200, int(conv_pred * 1.3))),
            "predicted_score": round(score_pred, 1),
            "confidence": round(min(0.7, self._stats.total_episodes / 100), 2),
        }
        return rec

    def _maybe_train(self) -> None:
        """Train model if enough data exists."""
        episodes = self._load_episodes()
        if len(episodes) < self.MIN_SAMPLES:
            return
        self._train(episodes)

    def _load_episodes(self) -> list[dict[str, Any]]:
        try:
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM meta_training_data ORDER BY created_at DESC LIMIT 500"
            ).fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except Exception:
            return []

    def _train(self, episodes: list[dict[str, Any]]) -> None:
        """Train RandomForest on collected episodes."""
        try:
            import numpy as np
            from sklearn.ensemble import RandomForestRegressor
        except ImportError:
            logger.warning("M2: scikit-learn not installed, skipping training")
            return

        X, y = [], []
        for ep in episodes:
            features = [float(ep.get(c, 0) or 0) for c in self.FEATURE_COLS]
            targets = [float(ep.get(c, 0) or 0) for c in self.TARGET_COLS]
            if all(f == 0 for f in features):
                continue
            X.append(features)
            y.append(targets)

        if len(X) < self.MIN_SAMPLES:
            return

        self._model = RandomForestRegressor(n_estimators=50, random_state=42, n_jobs=-1)
        self._model.fit(X, y)
        self._last_trained = time.time()

        # Feature importance
        importances = {}
        for i, col in enumerate(self.FEATURE_COLS):
            if hasattr(self._model, "feature_importances_"):
                importances[col] = round(float(self._model.feature_importances_[i]), 4)

        self._stats = MetaLearnerStats(
            total_episodes=len(episodes),
            model_ready=True,
            last_trained_at=time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(self._last_trained)),
            feature_importance=importances,
            current_recommendation=self.recommend_params("", []),
            confidence=min(0.8, len(episodes) / 100),
        )
        logger.info("M2: trained on %d episodes, top feature: %s", len(episodes),
                      max(importances, key=importances.get) if importances else "none")

    def stats(self) -> dict[str, Any]:
        """Return current learner statistics."""
        s = self._stats
        return {
            "total_episodes": s.total_episodes or self._count(),
            "model_ready": s.model_ready,
            "last_trained_at": s.last_trained_at,
            "feature_importance": s.feature_importance,
            "current_recommendation": s.current_recommendation,
            "confidence": s.confidence,
        }

    def _count(self) -> int:
        try:
            conn = sqlite3.connect(self._db_path)
            row = conn.execute("SELECT COUNT(*) FROM meta_training_data").fetchone()
            conn.close()
            return row[0] if row else 0
        except Exception:
            return 0
