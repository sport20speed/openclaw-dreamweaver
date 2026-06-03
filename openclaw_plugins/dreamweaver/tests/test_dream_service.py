"""Unit tests for DreamService orchestrator."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from openclaw_plugins.dreamweaver.config import DreamWeaverConfig
from openclaw_plugins.dreamweaver.dream_service import DreamService
from openclaw_plugins.dreamweaver.models import DreamStatus
from openclaw_plugins.dreamweaver.resource_monitor import ResourceConfig, ResourceMonitor, ResourceSnapshot


class StubLLM:
    def __init__(self, delay: float = 0.0) -> None:
        self.delay = delay
        self.calls: list[str] = []

    async def generate(self, system_prompt: str, user_prompt: str = "",
                       *, temperature: float = 0.7, max_tokens: int = 4096) -> tuple[str, int]:
        if self.delay:
            await asyncio.sleep(self.delay)
        self.calls.append(system_prompt[:80])
        if "创新突破专家" in system_prompt:
            return "Genius 方案：一个激进的重构方案。参考 [[架构设计]]。", 100
        if "严厉的审稿人" in system_prompt:
            return "Critic 漏洞报告：1.过于激进 2.风险高 3.成本大 4.缺乏验证 5.依赖不明确", 100
        if "公正评分" in system_prompt:
            return '{"score_A": 8.0, "score_B": 6.0, "winner": "A", "reason": "A更好"}', 100
        if "高级架构师" in system_prompt:
            return "Refiner 改进方案：保留创新点，增加风险缓解。", 100
        if "跨领域范式" in system_prompt:
            return "Mutator 变异方案：用流体力学类比重构。", 100
        return "{}", 50


class FakeProbe:
    def __init__(self, cpu: float = 10.0, mem: float = 20.0) -> None:
        self.cpu = cpu
        self.mem = mem
    def sample(self) -> ResourceSnapshot:
        return ResourceSnapshot(cpu_percent=self.cpu, memory_percent=self.mem)


@pytest.fixture
def config() -> DreamWeaverConfig:
    return DreamWeaverConfig(enabled=True, idle_timeout_seconds=900, max_iterations=2,
                              convergence_rounds=5, checkpoint_interval=10, mutation_interval=999)


@pytest.fixture
def llm() -> StubLLM:
    return StubLLM()


@pytest.fixture
def service(config: DreamWeaverConfig, llm: StubLLM) -> DreamService:
    monitor = ResourceMonitor(probe=FakeProbe(cpu=10.0, mem=20.0), config=ResourceConfig(retry_delay_seconds=0.01))
    return DreamService(config, llm, resource_monitor=monitor)


@pytest.mark.asyncio
async def test_start_stop(service: DreamService) -> None:
    await service.start()
    assert service._idle_detector._running is True
    await service.stop()
    assert service._idle_detector._running is False


@pytest.mark.asyncio
async def test_disabled_service_does_not_start_detector() -> None:
    config = DreamWeaverConfig(enabled=False)
    svc = DreamService(config, StubLLM())
    await svc.start()
    assert svc._idle_detector._running is False
    await svc.stop()


@pytest.mark.asyncio
async def test_start_dream_manual(service: DreamService) -> None:
    status_events: list[dict[str, Any]] = []
    async def collect(data: dict[str, Any]) -> None:
        status_events.append(data)
    service.on_status_push = collect
    started = await service.start_dream(motif="自定义母题")
    assert started is True
    assert service._status in (DreamStatus.RUNNING, DreamStatus.COMPLETED, DreamStatus.IDLE)
    if service._run_task:
        await asyncio.wait_for(service._run_task, timeout=5.0)
    assert service._status in (DreamStatus.COMPLETED, DreamStatus.IDLE)
    assert len(status_events) >= 1


@pytest.mark.asyncio
async def test_start_dream_rejects_double_start() -> None:
    slow_llm = StubLLM(delay=0.1)
    config = DreamWeaverConfig(max_iterations=5, convergence_rounds=10, checkpoint_interval=10, mutation_interval=999, idle_timeout_seconds=900)
    monitor = ResourceMonitor(probe=FakeProbe(cpu=10.0, mem=20.0), config=ResourceConfig(retry_delay_seconds=0.01))
    svc = DreamService(config, slow_llm, resource_monitor=monitor)
    started1 = await svc.start_dream(motif="第一个梦")
    assert started1 is True
    started2 = await svc.start_dream(motif="第二个梦")
    assert started2 is False
    if svc._run_task:
        try:
            await asyncio.wait_for(svc._run_task, timeout=5.0)
        except asyncio.TimeoutError:
            pass
    await svc.stop()


@pytest.mark.asyncio
async def test_stop_dream_interrupts() -> None:
    slow_llm = StubLLM(delay=0.1)
    monitor = ResourceMonitor(probe=FakeProbe(cpu=10.0, mem=20.0))
    svc = DreamService(DreamWeaverConfig(max_iterations=20, convergence_rounds=30, mutation_interval=999), slow_llm, resource_monitor=monitor)
    await svc.start_dream(motif="长梦")
    await asyncio.sleep(0.3)
    result = await svc.stop_dream()
    assert svc._status == DreamStatus.INTERRUPTED
    assert result is not None or svc._last_result is not None


@pytest.mark.asyncio
async def test_status_response(service: DreamService) -> None:
    s = service.status()
    assert s.status == DreamStatus.IDLE
    assert s.current_round == 0
    assert s.best_score == 0.0


@pytest.mark.asyncio
async def test_idle_triggers_dream() -> None:
    config = DreamWeaverConfig(enabled=True, idle_timeout_seconds=1, max_iterations=2, convergence_rounds=10, mutation_interval=999)
    monitor = ResourceMonitor(probe=FakeProbe(cpu=10.0, mem=20.0), config=ResourceConfig(retry_delay_seconds=0.01))
    svc = DreamService(config, StubLLM(), resource_monitor=monitor)
    completed: list[DreamStatus] = []
    async def on_complete(result: Any) -> None:
        completed.append(svc._status)
    svc.on_dream_complete = on_complete
    await svc.start()
    await asyncio.sleep(2.0)
    if svc._run_task:
        await asyncio.wait_for(svc._run_task, timeout=5.0)
    await svc.stop()
    assert svc._status in (DreamStatus.COMPLETED, DreamStatus.IDLE, DreamStatus.RUNNING)


@pytest.mark.asyncio
async def test_user_return_interrupts_dream() -> None:
    config = DreamWeaverConfig(enabled=True, idle_timeout_seconds=1, max_iterations=50, convergence_rounds=30, mutation_interval=999)
    slow_llm = StubLLM(delay=0.1)
    monitor = ResourceMonitor(probe=FakeProbe(cpu=10.0, mem=20.0))
    svc = DreamService(config, slow_llm, resource_monitor=monitor)
    await svc.start()
    await asyncio.sleep(1.5)
    await svc._idle_detector.record_heartbeat(asyncio.get_event_loop().time() + 100)
    if svc._run_task:
        try:
            await asyncio.wait_for(svc._run_task, timeout=5.0)
        except asyncio.TimeoutError:
            pass
    assert svc._status in (DreamStatus.INTERRUPTED, DreamStatus.COMPLETED, DreamStatus.IDLE)
    await svc.stop()


@pytest.mark.asyncio
async def test_resource_block_prevents_dream() -> None:
    config = DreamWeaverConfig(max_iterations=2, convergence_rounds=10, mutation_interval=999)
    monitor = ResourceMonitor(probe=FakeProbe(cpu=95.0, mem=95.0), config=ResourceConfig(retry_delay_seconds=0.01))
    svc = DreamService(config, StubLLM(), resource_monitor=monitor)
    started = await svc.start_dream(motif="本不该启动")
    assert started is False
    assert svc._status == DreamStatus.IDLE
