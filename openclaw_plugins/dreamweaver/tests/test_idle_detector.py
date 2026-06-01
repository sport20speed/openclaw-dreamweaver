"""Unit tests for IdleDetector."""

from __future__ import annotations

import asyncio
import time

import pytest

from openclaw_plugins.dreamweaver.config import DreamWeaverConfig
from openclaw_plugins.dreamweaver.idle_detector import (
    ActivityState,
    IdleDetector,
)


@pytest.fixture
def config_fast() -> DreamWeaverConfig:
    return DreamWeaverConfig(idle_timeout_seconds=2)


@pytest.fixture
def detector(config_fast: DreamWeaverConfig) -> IdleDetector:
    return IdleDetector(config_fast)


def test_initial_state_active(detector: IdleDetector) -> None:
    assert detector.state == ActivityState.ACTIVE
    assert not detector.is_idle


@pytest.mark.asyncio
async def test_start_stop(detector: IdleDetector) -> None:
    await detector.start()
    assert detector._running is True
    await detector.stop()
    assert detector._running is False


@pytest.mark.asyncio
async def test_heartbeat_prevents_idle(detector: IdleDetector) -> None:
    await detector.start()
    for _ in range(6):
        await detector.record_heartbeat(time.time())
        await asyncio.sleep(0.5)
    assert detector.state == ActivityState.ACTIVE
    await detector.stop()


@pytest.mark.asyncio
async def test_transition_to_idle(detector: IdleDetector) -> None:
    transitions: list[tuple[ActivityState, ActivityState]] = []

    async def on_change(old: ActivityState, new: ActivityState) -> None:
        transitions.append((old, new))

    detector.on_state_change = on_change
    await detector.start()
    await asyncio.sleep(3.5)
    assert detector.state == ActivityState.IDLE
    assert detector.is_idle
    assert len(transitions) >= 1
    assert transitions[0] == (ActivityState.ACTIVE, ActivityState.IDLE)
    await detector.stop()


@pytest.mark.asyncio
async def test_idle_to_active_on_heartbeat(detector: IdleDetector) -> None:
    await detector.start()
    await asyncio.sleep(3.5)
    assert detector.state == ActivityState.IDLE
    await detector.record_heartbeat(time.time() + 10)
    assert detector.state == ActivityState.ACTIVE
    await detector.stop()


@pytest.mark.asyncio
async def test_task_queue_blocks_idle(detector: IdleDetector) -> None:
    await detector.start()
    for _ in range(6):
        await detector.record_task_activity()
        await asyncio.sleep(0.5)
    assert detector.state == ActivityState.ACTIVE
    await detector.record_task_idle()
    await asyncio.sleep(3.5)
    assert detector.state == ActivityState.IDLE
    await detector.stop()


@pytest.mark.asyncio
async def test_manual_activity(detector: IdleDetector) -> None:
    await detector.start()
    await asyncio.sleep(3.5)
    assert detector.state == ActivityState.IDLE
    await detector.record_manual_activity()
    assert detector.state == ActivityState.ACTIVE
    await detector.stop()


@pytest.mark.asyncio
async def test_idle_seconds_increases(detector: IdleDetector) -> None:
    await detector.start()
    await asyncio.sleep(1.0)
    s = detector.idle_seconds
    assert 1.0 <= s < 2.5
    await detector.stop()


@pytest.mark.asyncio
async def test_debounce_after_wake(detector: IdleDetector) -> None:
    await detector.start()
    await asyncio.sleep(3.5)
    assert detector.state == ActivityState.IDLE
    await detector.record_heartbeat(time.time() + 100)
    assert detector.state == ActivityState.ACTIVE
    await asyncio.sleep(2.5)
    assert detector.state == ActivityState.ACTIVE
    await detector.stop()
