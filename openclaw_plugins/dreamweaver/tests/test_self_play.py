"""Unit tests for SelfPlayEngine."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import pytest

from openclaw_plugins.dreamweaver.self_play import (
    DreamResult,
    JudgeVerdict,
    SelfPlayConfig,
    SelfPlayEngine,
)

logger = logging.getLogger(__name__)


class MockLLM:
    """Returns role-aware responses based on Chinese prompt keywords."""

    def __init__(self, *, genius_text: str = "", critic_text: str = "",
                 judge_score_a: float = 7.0, judge_score_b: float = 6.0, judge_winner: str = "A",
                 refiner_text: str = "", mutator_text: str = "",
                 judge_mutator_score_a: float = 5.0, judge_mutator_winner: str = "B",
                 delay: float = 0.0) -> None:
        self.genius_text = genius_text or "Genius 完整方案：一个基于微内核的重构方案..."
        self.critic_text = critic_text or "Critic 发现 5 个漏洞：1. 复杂度上升 2. 迁移成本高 ..."
        self._judge_json = json.dumps({"score_A": judge_score_a, "score_B": judge_score_b, "winner": judge_winner, "reason": "方案A在创新性上明显优于方案B"})
        self.refiner_text = refiner_text or "Refiner 改进方案：保留微内核架构，增加渐进式迁移路径..."
        self.mutator_text = mutator_text or "Mutator 变异方案：用生物免疫系统类比..."
        self._judge_mutator_json = json.dumps({"score_A": judge_mutator_score_a, "score_B": 6.0, "winner": judge_mutator_winner, "reason": "变异方案未能超越当前最佳"})
        self._delay = delay
        self._next_judge_is_mutator = False
        self.call_count = 0
        self.calls: list[dict[str, Any]] = []

    async def generate(self, system_prompt: str, user_prompt: str = "",
                       *, temperature: float = 0.7, max_tokens: int = 4096) -> tuple[str, int]:
        if self._delay > 0:
            await asyncio.sleep(self._delay)
        self.call_count += 1
        self.calls.append({"system_prompt": system_prompt[:200], "temperature": temperature, "max_tokens": max_tokens})
        tokens = 500
        if "创新突破专家" in system_prompt:
            return self.genius_text, tokens
        if "严厉的审稿人" in system_prompt:
            return self.critic_text, tokens
        if "公正评分" in system_prompt:
            if self._next_judge_is_mutator:
                self._next_judge_is_mutator = False
                return self._judge_mutator_json, tokens
            else:
                return self._judge_json, tokens
        if "高级架构师" in system_prompt:
            return self.refiner_text, tokens
        if "跨领域范式" in system_prompt:
            self._next_judge_is_mutator = True
            return self.mutator_text, tokens
        logger.warning("MockLLM fallback: unmatched prompt prefix=%s", system_prompt[:100])
        return "{}", tokens


@pytest.fixture
def config_short() -> SelfPlayConfig:
    return SelfPlayConfig(max_iterations=3, convergence_rounds=10, mutation_interval=2, checkpoint_interval=5)


@pytest.fixture
def mock_llm() -> MockLLM:
    return MockLLM()


@pytest.fixture
def engine(mock_llm: MockLLM, config_short: SelfPlayConfig) -> SelfPlayEngine:
    return SelfPlayEngine(mock_llm, config_short)


@pytest.mark.asyncio
async def test_full_run_completes(engine: SelfPlayEngine) -> None:
    result = await engine.run("测试母题")
    assert isinstance(result, DreamResult)
    assert result.motif == "测试母题"
    assert result.total_iterations == 3
    assert result.best_score > 0
    assert len(result.logs) > 0


@pytest.mark.asyncio
async def test_result_structure(engine: SelfPlayEngine) -> None:
    result = await engine.run("测试母题")
    assert result.final_solution
    assert result.best_score >= 0
    assert result.convergence_reason == "max_iterations"
    assert result.started_at > 0
    assert result.finished_at >= result.started_at


@pytest.mark.asyncio
async def test_logs_capture_all_roles(engine: SelfPlayEngine) -> None:
    result = await engine.run("测试母题")
    roles_seen = {log.role for log in result.logs}
    assert "genius" in roles_seen
    assert "critic" in roles_seen
    assert "judge" in roles_seen
    assert "refiner" in roles_seen


@pytest.mark.asyncio
async def test_logs_contain_prompts_and_responses(engine: SelfPlayEngine) -> None:
    result = await engine.run("测试母题")
    for log in result.logs:
        assert log.response
        assert log.tokens_used > 0


@pytest.mark.asyncio
async def test_convergence_detection() -> None:
    config = SelfPlayConfig(max_iterations=30, convergence_rounds=3, mutation_interval=999)
    mock = MockLLM(judge_winner="B", judge_score_a=6.0, judge_score_b=7.0)
    engine = SelfPlayEngine(mock, config)
    result = await engine.run("测试母题")
    assert result.convergence_reason == "convergence"
    assert result.total_iterations < 30


@pytest.mark.asyncio
async def test_interrupt_stops_early() -> None:
    config = SelfPlayConfig(max_iterations=20, convergence_rounds=30, mutation_interval=999)
    mock = MockLLM(delay=0.005)
    engine = SelfPlayEngine(mock, config)
    stop = asyncio.Event()

    async def _interrupt() -> None:
        await asyncio.sleep(0.04)
        stop.set()

    asyncio.create_task(_interrupt())
    result = await engine.run("测试母题", stop_signal=stop)
    assert result.convergence_reason == "interrupted"
    assert result.total_iterations < 20


@pytest.mark.asyncio
async def test_mutator_can_win() -> None:
    config = SelfPlayConfig(max_iterations=3, convergence_rounds=20, mutation_interval=2)
    mock = MockLLM(judge_mutator_score_a=9.5, judge_mutator_winner="A")
    engine = SelfPlayEngine(mock, config)
    result = await engine.run("测试母题")
    assert result.best_score == 9.5


@pytest.mark.asyncio
async def test_checkpoint_callback_called() -> None:
    config = SelfPlayConfig(max_iterations=15, convergence_rounds=20, checkpoint_interval=5, mutation_interval=999)
    mock = MockLLM(judge_winner="B", judge_score_a=6.0, judge_score_b=7.0)
    engine = SelfPlayEngine(mock, config)
    checkpoints: list[DreamResult] = []

    async def save(result: DreamResult) -> None:
        checkpoints.append(result)

    await engine.run("测试母题", on_checkpoint=save)
    assert len(checkpoints) >= 2


@pytest.mark.asyncio
async def test_checkpoint_error_does_not_kill_loop() -> None:
    config = SelfPlayConfig(max_iterations=10, convergence_rounds=20, checkpoint_interval=5, mutation_interval=999)
    mock = MockLLM(judge_winner="B")
    engine = SelfPlayEngine(mock, config)

    async def broken_save(_result: DreamResult) -> None:
        raise RuntimeError("disk full")

    result = await engine.run("测试母题", on_checkpoint=broken_save)
    assert result.convergence_reason in ("max_iterations", "convergence")


def test_parse_valid_json() -> None:
    response = '{"score_A": 8.5, "score_B": 7.0, "winner": "A", "reason": "更好"}'
    verdict = SelfPlayEngine._parse_judge_response(response)
    assert verdict.score_a == 8.5
    assert verdict.score_b == 7.0
    assert verdict.winner == "A"


def test_parse_markdown_fenced_json() -> None:
    response = '```json\n{"score_A": 9.0, "score_B": 4.0, "winner": "A", "reason": "显著更优"}\n```'
    verdict = SelfPlayEngine._parse_judge_response(response)
    assert verdict.score_a == 9.0
    assert verdict.winner == "A"


def test_parse_invalid_response_fallback() -> None:
    response = "我无法判断这两个方案..."
    verdict = SelfPlayEngine._parse_judge_response(response)
    assert verdict.score_a == 5.0
    assert verdict.winner == "B"


def test_parse_partial_json_with_text() -> None:
    response = '经过分析，我认为方案A更好。\n{"score_A": 8.0, "score_B": 6.5, "winner": "A", "reason": "创新性更强"}\n综上所述...'
    verdict = SelfPlayEngine._parse_judge_response(response)
    assert verdict.score_a == 8.0
    assert verdict.winner == "A"


@pytest.mark.asyncio
async def test_best_score_improves() -> None:
    mock = MockLLM(judge_score_a=8.0, judge_winner="A")
    config = SelfPlayConfig(max_iterations=3, convergence_rounds=10, mutation_interval=999)
    engine = SelfPlayEngine(mock, config)
    result = await engine.run("测试母题")
    assert result.best_score == 8.0


@pytest.mark.asyncio
async def test_best_score_never_decreases() -> None:
    mock = MockLLM(judge_score_a=5.0, judge_score_b=9.0, judge_winner="B")
    config = SelfPlayConfig(max_iterations=3, convergence_rounds=10, mutation_interval=999)
    engine = SelfPlayEngine(mock, config)
    result = await engine.run("测试母题")
    assert result.best_score >= 5.0
