"""Unit tests for ResourceMonitor."""

from __future__ import annotations

import pytest

from openclaw_plugins.dreamweaver.resource_monitor import (
    PsutilProbe,
    ResourceConfig,
    ResourceMonitor,
    ResourceSnapshot,
)


class FakeProbe:
    def __init__(self, cpu: float = 10.0, mem: float = 20.0) -> None:
        self.cpu = cpu
        self.mem = mem

    def sample(self) -> ResourceSnapshot:
        return ResourceSnapshot(cpu_percent=self.cpu, memory_percent=self.mem)


@pytest.mark.asyncio
async def test_ready_when_below_threshold() -> None:
    probe = FakeProbe(cpu=30.0, mem=40.0)
    monitor = ResourceMonitor(probe=probe, config=ResourceConfig(cpu_threshold=80, memory_threshold=85))
    ready = await monitor.wait_until_ready()
    assert ready is True


@pytest.mark.asyncio
async def test_not_ready_retries() -> None:
    probe = FakeProbe(cpu=95.0, mem=90.0)
    monitor = ResourceMonitor(probe=probe, config=ResourceConfig(cpu_threshold=80, memory_threshold=85, retry_delay_seconds=0.01))
    ready = await monitor.wait_until_ready()
    assert ready is False


@pytest.mark.asyncio
async def test_is_over_threshold() -> None:
    probe = FakeProbe(cpu=95.0, mem=40.0)
    monitor = ResourceMonitor(probe=probe, config=ResourceConfig(cpu_threshold=80, memory_threshold=85))
    assert monitor.is_over_threshold is True
    probe.cpu = 30.0
    assert monitor.is_over_threshold is False


@pytest.mark.asyncio
async def test_should_pause_after_sustained_overage() -> None:
    probe = FakeProbe(cpu=95.0, mem=90.0)
    monitor = ResourceMonitor(probe=probe, config=ResourceConfig(cpu_threshold=80, memory_threshold=85, max_over_threshold_seconds=0.0))
    assert monitor.is_over_threshold is True
    assert monitor.should_pause is True


@pytest.mark.asyncio
async def test_should_not_pause_when_brief_spike() -> None:
    probe = FakeProbe(cpu=95.0, mem=40.0)
    monitor = ResourceMonitor(probe=probe, config=ResourceConfig(cpu_threshold=80, memory_threshold=85, max_over_threshold_seconds=3600.0))
    assert monitor.is_over_threshold is True
    assert monitor.should_pause is False


def test_resource_snapshot_defaults() -> None:
    snap = ResourceSnapshot(cpu_percent=50.0, memory_percent=60.0)
    assert snap.cpu_percent == 50.0
    assert snap.memory_percent == 60.0
    assert snap.timestamp > 0


def test_psutil_probe_fallback() -> None:
    probe = PsutilProbe()
    snap = probe.sample()
    assert snap.cpu_percent >= 0.0
    assert snap.memory_percent >= 0.0


@pytest.mark.asyncio
async def test_context_manager() -> None:
    probe = FakeProbe()
    monitor = ResourceMonitor(probe=probe)
    async with monitor:
        assert True
