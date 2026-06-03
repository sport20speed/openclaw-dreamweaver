"""Quality stability metrics for dream self-play (Dev Diary §6-7).

Computes three post-hoc metrics from iteration logs:
  1. Diversity Score — how different is this dream from recent history?
  2. Critic Depth — is the Critic still finding novel attack angles?
  3. Convergence Health — is the score stable, or oscillating?
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Optional

from .self_play import DreamResult, IterationLog


@dataclass
class QualityReport:
    diversity_score: float = 1.0       # 0-1: higher = more diverse (good)
    critic_depth: float = 1.0          # 0-1: higher = deeper attacks (good)
    convergence_health: float = 0.5    # 0-1: 0=too early, 0.5=healthy, 1=unstable
    overall_health: float = 0.5        # Compound score 0-1
    warnings: list[str] = field(default_factory=list)


class QualityAnalyzer:
    """Computes quality metrics from dream iteration logs."""

    def __init__(self, history_window: int = 10) -> None:
        self._history_window = history_window

    def analyze(self, result: DreamResult, past_solutions: list[str] | None = None) -> QualityReport:
        """Run all three metrics on a completed dream."""
        warnings: list[str] = []

        div = self._diversity_score(result, past_solutions or [])
        if div < 0.3:
            warnings.append("方案多样性过低：与历史梦境高度重复，建议调整Genius温度")

        depth = self._critic_depth(result.logs)
        if depth < 0.3:
            warnings.append("Critic攻击深度下降：攻击角度趋于重复，建议调整Critic提示词")

        conv = self._convergence_health(result.logs)
        if conv < 0.2:
            warnings.append("过早收敛：评分连续停滞，建议放宽收敛判据或增加变异频率")
        elif conv > 0.8:
            warnings.append("对弈不稳定：评分波动过大，建议降低Judge温度或增加收敛敏感度")

        # Compound health: weighted average
        overall = div * 0.3 + depth * 0.35 + conv * 0.35

        return QualityReport(
            diversity_score=div,
            critic_depth=depth,
            convergence_health=conv,
            overall_health=overall,
            warnings=warnings,
        )

    # ── 1. Diversity Score ───────────────────────────────────────

    def _diversity_score(self, result: DreamResult, past_solutions: list[str]) -> float:
        """Cosine similarity of current solution vs past week's solutions. Higher = more diverse."""
        if not past_solutions:
            return 1.0  # No history → maximally diverse

        curr_tokens = _tokenize(result.final_solution)
        max_sim = 0.0
        for past in past_solutions:
            past_tokens = _tokenize(past)
            sim = _cosine_similarity(curr_tokens, past_tokens)
            if sim > max_sim:
                max_sim = sim

        return 1.0 - max_sim  # Invert: high similarity = low diversity

    # ── 2. Critic Depth ─────────────────────────────────────────

    def _critic_depth(self, logs: list[IterationLog]) -> float:
        """Ratio of new attack angles vs total attack angles across rounds."""
        critic_logs = [log for log in logs if log.role == "critic"]
        if len(critic_logs) < 2:
            return 1.0  # Not enough data to judge

        all_angles: set[str] = set()
        new_per_round: list[float] = []

        for log in critic_logs:
            angles = _extract_critic_angles(log.response)
            new_count = len(angles - all_angles)
            total_count = len(angles)
            all_angles.update(angles)
            if total_count > 0:
                new_per_round.append(new_count / total_count)

        if not new_per_round:
            return 0.5
        return sum(new_per_round) / len(new_per_round)

    # ── 3. Convergence Health ───────────────────────────────────

    def _convergence_health(self, logs: list[IterationLog]) -> float:
        """Score variance over last N scored rounds. 0=dead flat, 1=chaotic."""
        scores = [log.score for log in logs if log.score is not None]
        recent = scores[-self._history_window:] if len(scores) >= self._history_window else scores
        if len(recent) < 3:
            return 0.5  # Neutral

        mean = sum(recent) / len(recent)
        variance = sum((s - mean) ** 2 for s in recent) / len(recent)
        # Normalize: variance of 0 → health=0 (too flat), variance > 2 → health=1 (too chaotic)
        # Ideal variance is around 0.5-1.5
        if variance < 0.1:
            return 0.05  # Very flat → convergence issue
        if variance > 3.0:
            return 1.0   # Very chaotic
        # Map 0.1-3.0 to 0.05-0.95 with optimum at 1.0 (health=0.5)
        return min(1.0, max(0.05, variance / 3.0))


# ── Helpers ────────────────────────────────────────────────────────

def _tokenize(text: str) -> Counter:
    """Simple word tokenizer for cosine similarity."""
    words = re.findall(r"[\w一-鿿]+", text.lower())
    return Counter(words)


def _cosine_similarity(a: Counter, b: Counter) -> float:
    """Cosine similarity between two token counters."""
    all_keys = set(a.keys()) | set(b.keys())
    dot = sum(a.get(k, 0) * b.get(k, 0) for k in all_keys)
    norm_a = math.sqrt(sum(v ** 2 for v in a.values())) or 1.0
    norm_b = math.sqrt(sum(v ** 2 for v in b.values())) or 1.0
    return dot / (norm_a * norm_b)


def _extract_critic_angles(response: str) -> set[str]:
    """Extract unique attack angle signatures from Critic response.

    Each line starting with a number + period (e.g., '1. 成本过高') is an angle.
    """
    lines = response.split("\n")
    angles: set[str] = set()
    for line in lines:
        line = line.strip()
        match = re.match(r"^\d+[\.\)、]\s*(.+)", line)
        if match:
            # Extract key phrase (first 3 words as signature)
            phrase = match.group(1).strip()[:40].lower()
            angles.add(phrase)
    return angles
