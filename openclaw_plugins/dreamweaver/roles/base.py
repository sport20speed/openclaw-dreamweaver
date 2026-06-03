"""Base classes for DreamWeaver self-play roles.

Each role follows the unified interface:
    async def execute(self, context: DreamContext) -> RoleOutput

This allows the SelfPlayEngine to orchestrate roles without coupling to their internals.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Protocol


# ── Unified data types ─────────────────────────────────────────────

@dataclass
class DreamContext:
    """Immutable context passed to every role.execute() call."""
    motif: str                                # The dream's core question
    current_solution: str                     # Latest solution (for Critic/Judge/Refiner)
    best_solution: str                        # Historical best (for Judge comparison)
    best_solution_summary: str = "无（首轮）"   # Summary for Genius
    best_score: float = 0.0
    current_round: int = 0                    # 0-indexed iteration
    max_rounds: int = 100
    critic_feedback: str = ""                 # Latest Critic output (for Refiner)
    mutation_paradigm: str = ""               # Cross-domain paradigm (for Mutator)


@dataclass
class RoleOutput:
    """Standardized output from any role."""
    role: str                                 # "genius" | "critic" | "judge" | "refiner" | "mutator"
    content: str                              # Main text output
    prompt: str = ""                          # System prompt sent to LLM (P0 fix)
    model: str = ""                           # Model used (P0 fix)
    score: Optional[float] = None             # Score if applicable (Judge)
    tokens_used: int = 0
    temperature: float = 0.0                 # Temperature used (P0 fix)
    metadata: dict = field(default_factory=dict)  # Extra data (verdict JSON, etc.)


# ── Provider interface (same as self_play.LLMProvider) ────────────

class LLMProvider(Protocol):
    async def generate(self, system_prompt: str, user_prompt: str = "",
                       *, temperature: float = 0.7, max_tokens: int = 4096
                       ) -> tuple[str, int]: ...


# ── Base Role ──────────────────────────────────────────────────────

class BaseRole:
    """Every role extends this. Provides prompt building + LLM call."""

    role_name: str = "base"
    temperature: float = 0.7
    max_tokens: int = 4096

    def __init__(self, llm: LLMProvider):
        self._llm = llm

    async def execute(self, context: DreamContext) -> RoleOutput:
        """Subclass must override to build prompt and call LLM."""
        raise NotImplementedError

    async def _call(self, prompt: str, temp: Optional[float] = None) -> tuple[str, int]:
        return await self._llm.generate(
            system_prompt=prompt,
            temperature=temp if temp is not None else self.temperature,
            max_tokens=self.max_tokens,
        )
