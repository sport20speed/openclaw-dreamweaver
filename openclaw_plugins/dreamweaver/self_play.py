"""SelfPlayEngine — the dream self-play evolution loop (PRD §6.3).

Five roles iterate on a motif:
  Genius → Critic → Judge → Refiner → (every 10th: Mutator)

Stop conditions: max iterations, convergence, external interrupt.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import re
import time
from dataclasses import dataclass, field
from typing import Any, Optional, Protocol

logger = logging.getLogger(__name__)


@dataclass
class Solution:
    content: str
    round: int = 0
    role: str = "genius"
    score: Optional[float] = None


@dataclass
class JudgeVerdict:
    score_a: float
    score_b: float
    winner: str
    reason: str


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
    judge_model_temperature: float = 0.1
    creative_model_temperature: float = 0.8
    safety_ethics_check: bool = True
    max_tokens_per_call: int = 4096


GENIUS_PROMPT = """你是创新突破专家。针对以下问题，提出一个激进且逻辑自洽的完整解决方案。
忽略现有工程实践，可调用任何已知科学原理。必须包含具体技术路径、关键算法、预期效果和对比现有方案的优势矩阵。
问题：{motif}
之前最佳方案参考（如有）：{best_solution_summary}
请输出完整方案文档。"""

CRITIC_PROMPT = """你是最严厉的审稿人。你的目标是从根本逻辑、实现可行性、效率、隐含假设、伦理风险、资源消耗、意外后果等维度，找出当前方案中的致命缺陷。至少列出 5 个具体漏洞，并说明每个漏洞的严重程度和可能导致的后果。
当前方案：{current_solution}
问题背景：{motif}"""

JUDGE_PROMPT = """你是一位公正的专家评委。阅读问题和两个方案（当前方案 vs 历史最佳），根据正确性、创新性、实用性、鲁棒性和效率进行 0-10 分综合评分，并给出详细的胜负分析。评分必须基于具体证据。
问题：{motif}
当前方案：{solution_A}
历史最佳方案：{solution_B}
输出 JSON: {{"score_A": .., "score_B": .., "winner": "A"/"B", "reason": "..."}}

如果任一方案涉及武器、恶意软件、社会工程攻击或不道德内容，对应的 score 必须为 0，并在 reason 中明确标注"伦理否决"。"""

REFINER_PROMPT = """你是一名高级架构师。在不削弱方案创新性的前提下，解决 Critic 指出的所有致命漏洞，输出改进后的完整方案。
原始方案：{solution}
Critic反馈：{critic_feedback}
问题背景：{motif}"""

MUTATOR_PROMPT = """你需要引入一个完全意想不到的跨领域范式来重构当前方案。例如："现在假设我们只能使用流体力学原理来解决这个软件工程问题。"请给出一个异化但逻辑通顺的新方案原型。
当前方案：{solution}
变异方向：{random_paradigm}"""

MUTATION_PARADIGMS = [
    "流体力学原理", "区块链共识机制", "生物进化论", "量子纠缠", "蜂群智能",
    "热力学第二定律", "分形几何", "博弈论中的囚徒困境", "光合作用能量转换", "蚁群路径优化",
    "板块构造学", "免疫系统记忆机制", "语言学中的乔姆斯基层级", "量子场论中的路径积分",
]


class SelfPlayEngine:
    def __init__(self, llm: LLMProvider, config: Optional[SelfPlayConfig] = None) -> None:
        self._llm = llm
        self._config = config or SelfPlayConfig()

    async def run(self, motif: str, stop_signal: Optional[asyncio.Event] = None,
                  on_checkpoint: Optional[Any] = None) -> DreamResult:
        started = time.time()
        logs: list[IterationLog] = []
        no_improvement_streak: int = 0

        genius_result = await self._genius_generate(motif, best_summary="无（首轮）")
        logs.append(genius_result["log"])

        s_best = Solution(content=genius_result["text"], round=0, role="genius", score=5.0)
        s_current_sol = s_best
        best_score: float = 5.0

        for iteration in range(1, self._config.max_iterations + 1):
            if stop_signal and stop_signal.is_set():
                logger.info("SelfPlay interrupted at round %d", iteration)
                return DreamResult(motif=motif, final_solution=s_best.content,
                                   best_score=s_best.score or 0.0, total_iterations=iteration - 1,
                                   logs=logs, started_at=started, finished_at=time.time(),
                                   convergence_reason="interrupted")

            if no_improvement_streak >= self._config.convergence_rounds:
                logger.info("Converged after %d rounds", iteration - 1)
                return DreamResult(motif=motif, final_solution=s_best.content,
                                   best_score=s_best.score or 0.0, total_iterations=iteration - 1,
                                   logs=logs, started_at=started, finished_at=time.time(),
                                   convergence_reason="convergence")

            critic_result = await self._critic_evaluate(motif, s_current_sol.content)
            logs.append(critic_result["log"])

            verdict = await self._judge_compare(motif, s_current_sol.content, s_best.content)
            logs.append(verdict["log"])
            current_score = verdict["verdict"].score_a
            s_current_sol.score = current_score

            if verdict["verdict"].winner == "A":
                s_best = Solution(content=s_current_sol.content, round=iteration, role="refiner", score=current_score)
            if current_score > best_score:
                best_score = current_score
                no_improvement_streak = 0
            else:
                no_improvement_streak += 1

            refiner_result = await self._refiner_improve(motif, s_current_sol.content, critic_result["text"])
            logs.append(refiner_result["log"])
            s_current_sol = Solution(content=refiner_result["text"], round=iteration, role="refiner")

            if iteration % self._config.mutation_interval == 0:
                mutator_result = await self._mutator_mutate(motif, s_best.content)
                logs.append(mutator_result["log"])
                mut_verdict = await self._judge_compare(motif, mutator_result["text"], s_best.content)
                logs.append(mut_verdict["log"])
                if mut_verdict["verdict"].winner == "A":
                    s_best = Solution(content=mutator_result["text"], round=iteration, role="mutator",
                                      score=mut_verdict["verdict"].score_a)
                    best_score = mut_verdict["verdict"].score_a
                    no_improvement_streak = 0

            if iteration % self._config.checkpoint_interval == 0 and on_checkpoint is not None:
                checkpoint = DreamResult(motif=motif, final_solution=s_best.content, best_score=best_score,
                                         total_iterations=iteration, logs=list(logs),
                                         started_at=started, finished_at=time.time(), convergence_reason="running")
                try:
                    result_cb = on_checkpoint(checkpoint)
                    if asyncio.iscoroutine(result_cb):
                        await result_cb
                except Exception:
                    logger.exception("Checkpoint save failed")

        return DreamResult(motif=motif, final_solution=s_best.content, best_score=best_score,
                           total_iterations=self._config.max_iterations, logs=logs,
                           started_at=started, finished_at=time.time(), convergence_reason="max_iterations")

    async def _genius_generate(self, motif: str, best_summary: str) -> dict[str, Any]:
        prompt = GENIUS_PROMPT.format(motif=motif, best_solution_summary=best_summary)
        response, tokens = await self._llm.generate(system_prompt=prompt, temperature=self._config.creative_model_temperature, max_tokens=self._config.max_tokens_per_call)
        return {"text": response, "log": IterationLog(round=0, role="genius", prompt=prompt, response=response, tokens_used=tokens)}

    async def _critic_evaluate(self, motif: str, solution: str) -> dict[str, Any]:
        prompt = CRITIC_PROMPT.format(motif=motif, current_solution=solution)
        response, tokens = await self._llm.generate(system_prompt=prompt, temperature=self._config.creative_model_temperature, max_tokens=self._config.max_tokens_per_call)
        return {"text": response, "log": IterationLog(round=-1, role="critic", prompt=prompt, response=response, tokens_used=tokens)}

    async def _judge_compare(self, motif: str, solution_a: str, solution_b: str) -> dict[str, Any]:
        prompt = JUDGE_PROMPT.format(motif=motif, solution_A=solution_a, solution_B=solution_b)
        response, tokens = await self._llm.generate(system_prompt=prompt, temperature=self._config.judge_model_temperature, max_tokens=self._config.max_tokens_per_call)
        verdict = self._parse_judge_response(response)
        return {"text": response, "log": IterationLog(round=-1, role="judge", prompt=prompt, response=response, score=verdict.score_a, tokens_used=tokens), "verdict": verdict}

    async def _refiner_improve(self, motif: str, solution: str, critic_feedback: str) -> dict[str, Any]:
        prompt = REFINER_PROMPT.format(motif=motif, solution=solution, critic_feedback=critic_feedback)
        response, tokens = await self._llm.generate(system_prompt=prompt, temperature=self._config.creative_model_temperature, max_tokens=self._config.max_tokens_per_call)
        return {"text": response, "log": IterationLog(round=-1, role="refiner", prompt=prompt, response=response, tokens_used=tokens)}

    async def _mutator_mutate(self, motif: str, solution: str) -> dict[str, Any]:
        paradigm = random.choice(MUTATION_PARADIGMS)
        prompt = MUTATOR_PROMPT.format(motif=motif, solution=solution, random_paradigm=paradigm)
        response, tokens = await self._llm.generate(system_prompt=prompt, temperature=self._config.creative_model_temperature + 0.2, max_tokens=self._config.max_tokens_per_call)
        return {"text": response, "log": IterationLog(round=-1, role="mutator", prompt=prompt, response=response, tokens_used=tokens)}

    @staticmethod
    def _parse_judge_response(response: str) -> JudgeVerdict:
        json_match = re.search(r"\{[\s\S]*?\}", response)
        if json_match:
            try:
                data = json.loads(json_match.group(0))
                return JudgeVerdict(score_a=float(data.get("score_A", 5.0)), score_b=float(data.get("score_B", 5.0)),
                                    winner=str(data.get("winner", "B")), reason=str(data.get("reason", "")))
            except (json.JSONDecodeError, ValueError, TypeError):
                pass
        try:
            data = json.loads(response)
            return JudgeVerdict(score_a=float(data.get("score_A", 5.0)), score_b=float(data.get("score_B", 5.0)),
                                winner=str(data.get("winner", "B")), reason=str(data.get("reason", "")))
        except (json.JSONDecodeError, ValueError, TypeError):
            logger.warning("Failed to parse Judge response, using defaults")
            return JudgeVerdict(score_a=5.0, score_b=5.0, winner="B", reason="解析失败")
