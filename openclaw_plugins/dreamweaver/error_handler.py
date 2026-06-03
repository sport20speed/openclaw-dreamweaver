"""Unified error handling framework — 3-layer retry + degradation (Dev Diary §10).

Layers:
  Role   — single API call failure → retry 3x with exponential backoff
  Engine — 5 consecutive API failures → switch to fallback / skip round
  System — DreamService crash → watchdog auto-restart via notification
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


# ── Config ────────────────────────────────────────────────────────

@dataclass
class ErrorHandlerConfig:
    role_max_retries: int = 3
    role_base_delay: float = 1.0       # seconds, doubles each retry
    role_max_delay: float = 30.0       # cap
    engine_max_consecutive_failures: int = 5
    engine_cooldown_seconds: float = 60.0  # pause after consecutive failures


# ── Layer 1: Role-level retry ─────────────────────────────────────

async def retry_with_backoff(
    fn: Callable[..., Any],
    *args: Any,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    **kwargs: Any,
) -> Any:
    """Call fn with exponential backoff retry on exception."""
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            return await fn(*args, **kwargs)
        except Exception as e:
            last_error = e
            if attempt < max_retries:
                delay = min(base_delay * (2 ** attempt), max_delay)
                logger.warning(
                    "Role retry %d/%d after %.1fs: %s",
                    attempt + 1, max_retries, delay, str(e)[:100],
                )
                await asyncio.sleep(delay)
    raise last_error  # type: ignore[misc]


# ── Layer 2: Engine-level failure tracking ────────────────────────

@dataclass
class EngineHealth:
    consecutive_failures: int = 0
    total_failures: int = 0
    total_calls: int = 0
    last_failure_time: float = 0.0
    degraded: bool = False

    def record_success(self) -> None:
        self.consecutive_failures = 0
        self.total_calls += 1
        self.degraded = False

    def record_failure(self) -> None:
        self.consecutive_failures += 1
        self.total_failures += 1
        self.total_calls += 1
        self.last_failure_time = time.time()

    @property
    def failure_rate(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return self.total_failures / self.total_calls


class EngineGuard:
    """Tracks API health and triggers degradation."""

    def __init__(self, config: Optional[ErrorHandlerConfig] = None) -> None:
        self._config = config or ErrorHandlerConfig()
        self.health = EngineHealth()
        self._cooldown_until: float = 0.0

    async def check_before_call(self) -> bool:
        """Return False if engine is in cooldown."""
        if time.time() < self._cooldown_until:
            logger.warning("Engine in cooldown, %.0fs remaining", self._cooldown_until - time.time())
            return False
        return True

    def after_success(self) -> None:
        self.health.record_success()

    def after_failure(self) -> None:
        self.health.record_failure()
        if self.health.consecutive_failures >= self._config.engine_max_consecutive_failures:
            self._cooldown_until = time.time() + self._config.engine_cooldown_seconds
            self.health.degraded = True
            logger.error(
                "Engine degraded: %d consecutive failures, cooldown %.0fs",
                self.health.consecutive_failures,
                self._config.engine_cooldown_seconds,
            )

    @property
    def is_degraded(self) -> bool:
        return self.health.degraded or time.time() < self._cooldown_until


# ── Layer 3: Watchdog ─────────────────────────────────────────────

class Watchdog:
    """Monitors a background task and restarts it on failure."""

    def __init__(
        self,
        task_fn: Callable[..., Any],
        *,
        name: str = "watchdog",
        max_restarts: int = 3,
        restart_delay: float = 5.0,
        on_restart: Optional[Callable[[int, Exception], Any]] = None,
    ) -> None:
        self._fn = task_fn
        self._name = name
        self._max_restarts = max_restarts
        self._restart_delay = restart_delay
        self._on_restart = on_restart
        self._restart_count = 0
        self._task: Optional[asyncio.Task[Any]] = None

    async def start(self, *args: Any, **kwargs: Any) -> None:
        """Start the watched task and auto-restart on crash."""
        self._restart_count = 0
        self._task = asyncio.create_task(self._run(*args, **kwargs))

    async def _run(self, *args: Any, **kwargs: Any) -> None:
        while self._restart_count <= self._max_restarts:
            try:
                await self._fn(*args, **kwargs)
                return  # Normal completion
            except asyncio.CancelledError:
                logger.info("Watchdog[%s] cancelled", self._name)
                return
            except Exception as e:
                self._restart_count += 1
                logger.exception(
                    "Watchdog[%s] crashed (restart %d/%d): %s",
                    self._name, self._restart_count, self._max_restarts, e,
                )
                if self._on_restart:
                    result = self._on_restart(self._restart_count, e)
                    if asyncio.iscoroutine(result):
                        await result
                if self._restart_count <= self._max_restarts:
                    await asyncio.sleep(self._restart_delay)

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
