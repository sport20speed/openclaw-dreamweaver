"""SelfPlayEngine — the dream self-play evolution loop (PRD §6.3).

V2: Uses role classes from openclaw_plugins.dreamweaver.roles for clean separation.
Five roles iterate: Genius → Critic → Judge → Refiner → (every 10th: Mutator)
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Optional, Protocol

from .roles.base import DreamContext, RoleOutput
from .roles.genius import GeniusRole
from .roles.critic import CriticRole
from .roles.judge import JudgeRole
from .roles.refiner import RefinerRole
from .roles.mutator import MutatorRole

logger = logging.getLogger(__name__)


# Backward-compat exports (tests rely on these)
@dataclass
class JudgeVerdict:
    score_a: float
    score_b: float
    winner: str
    reason: str


@dataclass
class Solution:
    content: str
    round: int = 0
    role: str = "genius"
    score: Optional[float] = None


@dataclass
class IterationLog:
    round: int
    role: str
    prompt: str
    response: str
    score: Optional[float] = None
    tokens_used: int = 0
    timestamp: float = field(default_factory=time.time)


@dataclass
class DreamResult:
    motif: str
    final_solution: str
    best_score: float
    total_iterations: int
    logs: list[IterationLog]
    started_at: float
    finished_at: float
    convergence_reason: str


class LLMProvider(Protocol):
    async def generate(self, system_prompt: str, user_prompt: str = "",
                       *, temperature: float = 0.7, max_tokens: int = 4096) -> tuple[str, int]: ...


@dataclass
class SelfPlayConfig:
    max_iterations: int = 100
    convergence_rounds: int = 20
    mutation_interval: int = 10
    checkpoint_interval: int = 10
    judge_model_temperature: float = 0.05
    creative_model_temperature: float = 0.8
    safety_ethics_check: bool = True
    max_tokens_per_call: int = 2048


class SelfPlayEngine:
    """Orchestrates role-based self-play with configurable LLMs per role."""

    def __init__(self, llm: LLMProvider, config: Optional[SelfPlayConfig] = None,
                 *, judge_llm: Optional[LLMProvider] = None) -> None:
        self._llm = llm
        self._judge_llm = judge_llm or llm
        self._config = config or SelfPlayConfig()

    async def run(self, motif: str, stop_signal: Optional[asyncio.Event] = None,
                  on_checkpoint: Optional[Any] = None) -> DreamResult:
        """Execute the full self-play loop."""
        started = time.time()

        # Create role instances
        genius = GeniusRole(self._llm)
        critic = CriticRole(self._llm)
        judge = JudgeRole(self._judge_llm)
        refiner = RefinerRole(self._llm)
        mutator = MutatorRole(self._llm)

        logs: list[IterationLog] = []
        no_improvement_streak: int = 0

        # Round 0: Genius generates initial solution
        ctx = DreamContext(motif=motif, current_solution="", best_solution="")
        output = await genius.execute(ctx)
        logs.append(self._to_log(output, round=0))

        s_best = Solution(content=output.content, round=0, role="genius", score=5.0)
        s_current = s_best
        best_score: float = 5.0

        # Main iteration loop
        for iteration in range(1, self._config.max_iterations + 1):
            if stop_signal and stop_signal.is_set():
                return self._finish(motif, s_best, best_score, iteration - 1, logs, started, "interrupted")

            if no_improvement_streak >= self._config.convergence_rounds:
                return self._finish(motif, s_best, best_score, iteration - 1, logs, started, "convergence")

            # Step 1: Critic
            ctx = DreamContext(motif=motif, current_solution=s_current.content,
                               best_solution=s_best.content, current_round=iteration)
            c_out = await critic.execute(ctx)
            logs.append(self._to_log(c_out, round=iteration))

            # Step 2: Judge
            ctx = DreamContext(motif=motif, current_solution=s_current.content,
                               best_solution=s_best.content, current_round=iteration)
            j_out = await judge.execute(ctx)
            logs.append(self._to_log(j_out, round=iteration))
            current_score = j_out.score or 5.0
            s_current.score = current_score

            verdict = j_out.metadata.get("verdict", {}) or {}
            winner = verdict.get("winner") or verdict.get('"winner"', "B")
            if winner == "A" and current_score > best_score:
                s_best = Solution(content=s_current.content, round=iteration, role="refiner", score=current_score)

            if current_score > best_score:
                best_score = current_score
                no_improvement_streak = 0
            else:
                no_improvement_streak += 1

            # Step 3: Refiner
            ctx = DreamContext(motif=motif, current_solution=s_current.content,
                               critic_feedback=c_out.content, current_round=iteration,
                               best_solution=s_best.content)
            r_out = await refiner.execute(ctx)
            logs.append(self._to_log(r_out, round=iteration))
            s_current = Solution(content=r_out.content, round=iteration, role="refiner")

            # Step 4: Mutator (every N rounds)
            if iteration % self._config.mutation_interval == 0:
                m_out = await mutator.execute(DreamContext(
                    motif=motif, current_solution=s_best.content,
                    best_solution=s_best.content, current_round=iteration))
                logs.append(self._to_log(m_out, round=iteration))

                mj_out = await judge.execute(DreamContext(
                    motif=motif, current_solution=m_out.content,
                    best_solution=s_best.content, current_round=iteration))
                logs.append(self._to_log(mj_out, round=iteration))

                mj_verdict = mj_out.metadata.get("verdict", {}) or {}
                if (mj_verdict.get("winner") or mj_verdict.get('"winner"', "B")) == "A":
                    s_best = Solution(content=m_out.content, round=iteration,
                                      role="mutator", score=mj_out.score or 0)
                    best_score = mj_out.score or best_score
                    no_improvement_streak = 0

            # Checkpoint
            if iteration % self._config.checkpoint_interval == 0 and on_checkpoint:
                cp = self._finish(motif, s_best, best_score, iteration, list(logs), started, "running")
                try:
                    result = on_checkpoint(cp)
                    if asyncio.iscoroutine(result):
                        await result
                except Exception:
                    logger.exception("Checkpoint save failed")

        return self._finish(motif, s_best, best_score, self._config.max_iterations, logs, started, "max_iterations")

    @staticmethod
    def _to_log(output: RoleOutput, round: int) -> IterationLog:
        return IterationLog(round=round, role=output.role, prompt=output.prompt or "", response=output.content,
                            score=output.score, tokens_used=output.tokens_used)

    @staticmethod
    def _finish(motif: str, best: Solution, score: float, iterations: int,
                logs: list[IterationLog], started: float, reason: str) -> DreamResult:
        return DreamResult(motif=motif, final_solution=best.content, best_score=score,
                           total_iterations=iterations, logs=logs,
                           started_at=started, finished_at=time.time(), convergence_reason=reason)

    @staticmethod
    def _parse_judge_response(response: str) -> JudgeVerdict:
        """Backward-compat: delegate to JudgeRole parser."""
        data = JudgeRole._parse(response)
        return JudgeVerdict(
            score_a=float(data.get("score_A", 5.0)),
            score_b=float(data.get("score_B", 5.0)),
            winner=str(data.get("winner", "B")),
            reason=str(data.get("reason", "")),
        )
