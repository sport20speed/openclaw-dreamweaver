"""IdleDetector — monitors user activity and emits idle/active state transitions.

Data sources (PRD §6.1.1):
  - Frontend WebSocket heartbeat (every 10 s) carrying last_interaction timestamp.
  - OpenClaw task queue — any unfinished user task means 'active'.
  - (Phase 2+) Optional camera / microphone presence detection.

State machine:
  ACTIVE ──(no interaction for idle_timeout_seconds)──▶ IDLE
  IDLE   ──(any interaction event)──────────────────▶ ACTIVE
"""

from __future__ import annotations

import asyncio
import logging
import time
from enum import Enum
from typing import Any, Callable, Optional

from .config import DreamWeaverConfig

logger = logging.getLogger(__name__)


class ActivityState(str, Enum):
    ACTIVE = "active"
    IDLE = "idle"


OnStateChange = Callable[[ActivityState, ActivityState], Any]


class IdleDetector:
    _POLL_INTERVAL: float = 2.0
    _DEBOUNCE_SECONDS: float = 5.0

    def __init__(self, config: DreamWeaverConfig) -> None:
        self._config = config
        self._timeout: float = float(config.idle_timeout_seconds)
        self._state: ActivityState = ActivityState.ACTIVE
        self._last_interaction: float = time.time()
        self._task_queue_active: bool = False
        self._state_changed_at: float = 0.0
        self.on_state_change: Optional[OnStateChange] = None
        self._monitor_task: Optional[asyncio.Task[None]] = None
        self._running: bool = False

    @property
    def state(self) -> ActivityState:
        return self._state

    @property
    def idle_seconds(self) -> float:
        if self._task_queue_active:
            return 0.0
        return time.time() - self._last_interaction

    @property
    def is_idle(self) -> bool:
        return self._state == ActivityState.IDLE

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._last_interaction = time.time()
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("IdleDetector started (timeout=%ds)", self._timeout)

    async def stop(self) -> None:
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            self._monitor_task = None
        logger.info("IdleDetector stopped")

    async def record_heartbeat(self, last_interaction_ts: float) -> None:
        if last_interaction_ts > self._last_interaction:
            self._last_interaction = last_interaction_ts
            await self._on_activity_detected("heartbeat")

    async def record_task_activity(self) -> None:
        self._task_queue_active = True
        await self._on_activity_detected("task_queue")

    async def record_task_idle(self) -> None:
        self._task_queue_active = False

    async def record_manual_activity(self) -> None:
        await self._on_activity_detected("manual")

    async def _on_activity_detected(self, source: str) -> None:
        was_idle = self._state == ActivityState.IDLE
        if was_idle:
            old = self._state
            self._state = ActivityState.ACTIVE
            self._state_changed_at = time.time()
            logger.info("IdleDetector: IDLE → ACTIVE (source=%s)", source)
            await self._fire_state_change(old, self._state)

    async def _on_idle_timeout(self) -> None:
        if self._state == ActivityState.IDLE:
            return
        if self._task_queue_active:
            return
        if time.time() - self._state_changed_at < self._DEBOUNCE_SECONDS:
            return
        old = self._state
        self._state = ActivityState.IDLE
        self._state_changed_at = time.time()
        logger.info("IdleDetector: ACTIVE → IDLE (%.0fs inactive)", self.idle_seconds)
        await self._fire_state_change(old, self._state)

    async def _fire_state_change(self, old: ActivityState, new: ActivityState) -> None:
        if self.on_state_change is None:
            return
        result = self.on_state_change(old, new)
        if asyncio.iscoroutine(result):
            await result

    async def _monitor_loop(self) -> None:
        while self._running:
            try:
                if self._state == ActivityState.ACTIVE:
                    if self.idle_seconds >= self._timeout:
                        await self._on_idle_timeout()
                await asyncio.sleep(self._POLL_INTERVAL)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("IdleDetector monitor loop error")
                await asyncio.sleep(1.0)
