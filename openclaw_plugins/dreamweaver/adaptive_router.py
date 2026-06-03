"""M5: Adaptive model router — routes LLM calls to local/cloud based on context.

Routing rules (PRD §7.2):
  - Mutator / low-score (<4.0) → local Ollama
  - Genius first round → cloud Flash
  - Judge high-score (>7.5) → cloud Pro
  - Default → cloud Flash
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from .llm_providers import DeepSeekProvider, OllamaProvider

logger = logging.getLogger(__name__)

# ── Router ─────────────────────────────────────────────────────────

TIERS = {
    "local": {"label": "Ollama qwen3.5:9b", "provider": "ollama"},
    "cloud_fast": {"label": "DeepSeek V4 Flash", "provider": "deepseek"},
    "cloud_pro": {"label": "DeepSeek V4 Pro", "provider": "deepseek"},
}


class AdaptiveRouter:
    """Selects the optimal LLM provider based on role, iteration, and score."""

    def __init__(
        self,
        local_model: str = "qwen3.5:9b",
        cloud_api_key: Optional[str] = None,
        cloud_model: str = "deepseek-v4-flash",
        judge_model: str = "deepseek-v4-pro",
    ) -> None:
        self._local = OllamaProvider(model=local_model) if local_model else None
        self._cloud_fast = DeepSeekProvider(cloud_api_key or "", model=cloud_model) if cloud_api_key else None
        self._cloud_pro = DeepSeekProvider(cloud_api_key or "", model=judge_model) if cloud_api_key else None
        self._fallback = self._cloud_fast or self._local

        # Stats
        self.call_counts: dict[str, int] = {"local": 0, "cloud_fast": 0, "cloud_pro": 0}
        self.estimated_cost: float = 0.0

    def select(
        self,
        role: str,
        *,
        iteration: int = 0,
        current_score: Optional[float] = None,
        call_type: str = "standard",
    ) -> tuple[Any, str]:
        """Return (provider, tier_label) based on routing rules.

        Args:
            role: "genius" | "critic" | "judge" | "refiner" | "mutator"
            iteration: current round (0-indexed)
            current_score: latest score (for adaptive decisions)
            call_type: "standard" | "mutate" | "low_score"
        """
        score = current_score or 5.0

        # Rule 1: Mutator → always local (cheap exploration)
        if role == "mutator" or call_type == "mutate":
            if self._local:
                self._log("local", role)
                return self._local, "local"

        # Rule 2: Low score (< 4.0) → local (not worth cloud cost)
        if score < 4.0 and self._local:
            self._log("local", role)
            return self._local, "local"

        # Rule 3: Judge + high score (> 7.5) → cloud Pro
        if role == "judge" and score > 7.5 and self._cloud_pro:
            self._log("cloud_pro", role)
            return self._cloud_pro, "cloud_pro"

        # Rule 4: Judge → cloud Pro (always, per PRD §6.3.3)
        if role == "judge" and self._cloud_pro:
            self._log("cloud_pro", role)
            return self._cloud_pro, "cloud_pro"

        # Rule 5: Default → cloud Fast
        if self._cloud_fast:
            self._log("cloud_fast", role)
            return self._cloud_fast, "cloud_fast"

        # Fallback
        self._log("local" if self._local else "cloud_fast", role)
        return self._fallback, "local" if self._local else "cloud_fast"

    def _log(self, tier: str, role: str) -> None:
        self.call_counts[tier] = self.call_counts.get(tier, 0) + 1

    @property
    def stats(self) -> dict[str, Any]:
        return {
            "call_counts": dict(self.call_counts),
            "estimated_cost": round(self.estimated_cost, 4),
            "tiers": TIERS,
        }
