"""ResourceMonitor — enforces CPU / memory limits before and during dreams (PRD §6.6)."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Optional, Protocol

logger = logging.getLogger(__name__)


@dataclass
class ResourceSnapshot:
    cpu_percent: float
    memory_percent: float
    timestamp: float = 0.0

    def __post_init__(self) -> None:
        if self.timestamp == 0.0:
            self.timestamp = time.time()


@dataclass
class ResourceConfig:
    cpu_threshold: int = 80
    memory_threshold: int = 85
    retry_delay_seconds: float = 300.0
    sample_interval_seconds: float = 10.0
    max_over_threshold_seconds: float = 60.0


class SystemProbe(Protocol):
    def sample(self) -> ResourceSnapshot: ...


class PsutilProbe:
    def sample(self) -> ResourceSnapshot:
        try:
            import psutil
            return ResourceSnapshot(
                cpu_percent=psutil.cpu_percent(interval=0.1),
                memory_percent=psutil.virtual_memory().percent,
            )
        except ImportError:
            return ResourceSnapshot(cpu_percent=0.0, memory_percent=0.0)


class ResourceMonitor:
    def __init__(
        self,
        probe: Optional[SystemProbe] = None,
        config: Optional[ResourceConfig] = None,
    ) -> None:
        self._probe = probe or PsutilProbe()
        self._config = config or ResourceConfig()
        self._over_threshold_since: Optional[float] = None
        self._paused = asyncio.Event()
        self._paused.set()

    async def wait_until_ready(self) -> bool:
        for attempt in range(3):
            snap = self._probe.sample()
            if (
                snap.cpu_percent < self._config.cpu_threshold
                and snap.memory_percent < self._config.memory_threshold
            ):
                logger.debug("Resources OK: CPU %.1f%%, MEM %.1f%%", snap.cpu_percent, snap.memory_percent)
                return True
            logger.info("Resources over threshold, retrying in %.0fs (attempt %d/3)", self._config.retry_delay_seconds, attempt + 1)
            await asyncio.sleep(self._config.retry_delay_seconds)
        logger.warning("ResourceMonitor: 3 attempts exhausted, aborting")
        return False

    @property
    def is_over_threshold(self) -> bool:
        snap = self._probe.sample()
        return snap.cpu_percent > self._config.cpu_threshold or snap.memory_percent > self._config.memory_threshold

    @property
    def should_pause(self) -> bool:
        if self.is_over_threshold:
            if self._over_threshold_since is None:
                self._over_threshold_since = time.time()
            elapsed = time.time() - self._over_threshold_since
            return elapsed >= self._config.max_over_threshold_seconds
        else:
            self._over_threshold_since = None
            return False

    def current_snapshot(self) -> ResourceSnapshot:
        return self._probe.sample()

    async def start_monitoring(self) -> None:
        self._paused.set()
        self._over_threshold_since = None

    async def stop_monitoring(self) -> None:
        pass

    async def __aenter__(self) -> "ResourceMonitor":
        await self.start_monitoring()
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.stop_monitoring()
