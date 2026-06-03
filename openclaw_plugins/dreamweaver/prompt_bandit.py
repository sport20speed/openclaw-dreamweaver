"""M3 Lite: Prompt Bandit — learns which prompt style works best per role + context.

Uses epsilon-greedy selection across 3 prompt variants per role.
Records rewards (best_score delta) to gradually shift toward high-value templates.
"""

from __future__ import annotations

import json
import logging
import math
import os
import random
import sqlite3
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# ── Prompt variants per role ───────────────────────────────────────

PROMPT_VARIANTS = {
    "genius": {
        "conservative": {
            "persona": "资深架构师",
            "temperature": 0.65,
            "style": "稳健、工程可行、有具体代码示例",
        },
        "balanced": {
            "persona": "创新突破专家",
            "temperature": 0.85,
            "style": "从第一性原理推导、违反直觉的核心机制",
        },
        "aggressive": {
            "persona": "科幻现实主义设计师",
            "temperature": 1.0,
            "style": "引入跨学科隐喻、挑战领域基础假设、极端激进",
        },
    },
    "critic": {
        "conservative": {
            "persona": "友好审稿人",
            "temperature": 0.6,
            "style": "指出改进方向而非致命攻击，3个漏洞即可",
        },
        "balanced": {
            "persona": "严厉的审稿人",
            "temperature": 0.75,
            "style": "攻击核心假设、找出≥5致命漏洞、不攻击行文",
        },
        "aggressive": {
            "persona": "毁灭性评论家",
            "temperature": 0.9,
            "style": "从根本逻辑推翻方案、论证为何方案不可能成立",
        },
    },
    "refiner": {
        "conservative": {
            "persona": "务实工程师",
            "temperature": 0.6,
            "style": "只修最致命的2个漏洞、保持方案简洁实用",
        },
        "balanced": {
            "persona": "高级架构师",
            "temperature": 0.7,
            "style": "修补漏洞但不牺牲创新、选择性忽略次要问题",
        },
        "aggressive": {
            "persona": "颠覆式改进者",
            "temperature": 0.85,
            "style": "在修复基础上进一步加强激进性、引入新维度",
        },
    },
}


# ── Bandit ─────────────────────────────────────────────────────────

@dataclass
class ArmStats:
    variant: str
    pulls: int = 0
    total_reward: float = 0.0
    avg_reward: float = 0.0

    def update(self, reward: float) -> None:
        self.pulls += 1
        self.total_reward += reward
        self.avg_reward = round(self.total_reward / self.pulls, 3)


@dataclass
class RoleBandit:
    role: str
    arms: dict[str, ArmStats] = field(default_factory=dict)
    epsilon: float = 0.2  # exploration rate (decreases with experience)

    def select(self) -> tuple[str, ArmStats]:
        """Epsilon-greedy arm selection."""
        if not self.arms:
            return "balanced", ArmStats(variant="balanced")

        if random.random() < self.epsilon:
            # Explore: pick random arm
            variant = random.choice(list(self.arms.keys()))
        else:
            # Exploit: pick best arm
            best = max(self.arms.values(), key=lambda a: a.avg_reward)
            variant = best.variant

        return variant, self.arms.get(variant, ArmStats(variant=variant))

    def record(self, variant: str, reward: float) -> None:
        if variant not in self.arms:
            self.arms[variant] = ArmStats(variant=variant)
        self.arms[variant].update(reward)
        # Decay epsilon as we learn
        total_pulls = sum(a.pulls for a in self.arms.values())
        self.epsilon = max(0.05, 0.2 * math.exp(-total_pulls / 50))


class PromptBandit:
    """Manages bandits for all roles and selects prompt variants."""

    CREATE_TABLE = """
    CREATE TABLE IF NOT EXISTS prompt_bandit_state (
        role TEXT NOT NULL,
        variant TEXT NOT NULL,
        pulls INTEGER DEFAULT 0,
        total_reward REAL DEFAULT 0,
        avg_reward REAL DEFAULT 0,
        epsilon REAL DEFAULT 0.2,
        updated_at TEXT DEFAULT (datetime('now')),
        PRIMARY KEY (role, variant)
    );
    """

    def __init__(self, db_path: str | None = None) -> None:
        self._bandits: dict[str, RoleBandit] = {}
        self._db_path = db_path
        if db_path:
            self._load_state()

    def _load_state(self) -> None:
        try:
            conn = sqlite3.connect(self._db_path)
            conn.execute(self.CREATE_TABLE)
            conn.commit()
            rows = conn.execute("SELECT * FROM prompt_bandit_state").fetchall()
            for row in rows:
                role = row[0]
                if role not in self._bandits:
                    self._bandits[role] = RoleBandit(role=role)
                self._bandits[role].arms[row[1]] = ArmStats(
                    variant=row[1], pulls=row[2], total_reward=row[3], avg_reward=row[4],
                )
                self._bandits[role].epsilon = row[5]
            conn.close()
        except Exception:
            pass

    def _save_state(self) -> None:
        if not self._db_path:
            return
        try:
            conn = sqlite3.connect(self._db_path)
            conn.execute(self.CREATE_TABLE)
            for role, bandit in self._bandits.items():
                for variant, arm in bandit.arms.items():
                    conn.execute(
                        """INSERT OR REPLACE INTO prompt_bandit_state
                           (role, variant, pulls, total_reward, avg_reward, epsilon)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (role, variant, arm.pulls, arm.total_reward, arm.avg_reward, bandit.epsilon),
                    )
            conn.commit()
            conn.close()
        except Exception:
            pass

    def select(self, role: str, motif_complexity: float = 0.5) -> tuple[str, dict[str, Any]]:
        """Select the best prompt variant for a role and context.

        Returns (variant_name, prompt_params) for use by the role.
        """
        if role not in self._bandits:
            self._bandits[role] = RoleBandit(role=role)
            # Initialize arms
            for variant in PROMPT_VARIANTS.get(role, {}):
                self._bandits[role].arms[variant] = ArmStats(variant=variant)

        variant, arm = self._bandits[role].select()
        params = PROMPT_VARIANTS.get(role, {}).get(variant, {})
        return variant, {**params, "epsilon": self._bandits[role].epsilon}

    def reward(self, role: str, variant: str, score_delta: float) -> None:
        """Record a reward for the selected variant.

        reward = score delta (positive = improvement, negative = regression).
        """
        if role not in self._bandits:
            self._bandits[role] = RoleBandit(role=role)
        self._bandits[role].record(variant, score_delta)
        self._save_state()

    def stats(self) -> list[dict[str, Any]]:
        """Return all bandit statistics."""
        result = []
        for role, bandit in self._bandits.items():
            for variant, arm in bandit.arms.items():
                result.append({
                    "role": role,
                    "variant": variant,
                    "pulls": arm.pulls,
                    "avg_reward": arm.avg_reward,
                    "params": PROMPT_VARIANTS.get(role, {}).get(variant, {}),
                })
        return sorted(result, key=lambda x: x["avg_reward"], reverse=True)
