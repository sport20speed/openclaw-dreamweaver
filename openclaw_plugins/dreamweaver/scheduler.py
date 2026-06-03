"""DreamScheduler — cron-like time-window dream scheduling (PRD §6.1.3).

Supports:
  - Cron expression (e.g., "0 3 * * *" = every day at 3am)
  - Time windows (e.g., "03:00-05:00")
  - Combined: cron defines when to check, window defines allowed hours
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# ── Cron parser (minimal, just 5-field) ───────────────────────────

_MINUTE, _HOUR, _DOM, _MONTH, _DOW = range(5)


def _parse_field(value: str, lo: int, hi: int) -> set[int]:
    """Parse a single cron field into allowed values."""
    if value == "*":
        return set(range(lo, hi + 1))

    result: set[int] = set()
    for part in value.split(","):
        step = 1
        if "/" in part:
            part, step_str = part.split("/", 1)
            step = int(step_str)

        if "-" in part:
            a, b = part.split("-", 1)
            result.update(range(int(a), int(b) + 1, step))
        elif part == "*":
            result.update(range(lo, hi + 1, step))
        else:
            result.add(int(part))

    return {v for v in result if lo <= v <= hi}


def cron_matches(expression: str, t: Optional[time.struct_time] = None) -> bool:
    """Check if a 5-field cron expression matches the given (or current) time."""
    if t is None:
        t = time.localtime()
    fields = expression.strip().split()
    if len(fields) != 5:
        return False

    try:
        minutes = _parse_field(fields[_MINUTE], 0, 59)
        hours = _parse_field(fields[_HOUR], 0, 23)
        doms = _parse_field(fields[_DOM], 1, 31)
        months = _parse_field(fields[_MONTH], 1, 12)
        dows = _parse_field(fields[_DOW], 0, 7)  # 0 and 7 both = Sunday

        return (
            t.tm_min in minutes
            and t.tm_hour in hours
            and t.tm_mday in doms
            and t.tm_mon in months
            and ((t.tm_wday + 1) % 7 in dows)  # tm_wday: Mon=0, cron Sun=0
        )
    except (ValueError, IndexError):
        return False


# ── Time window ───────────────────────────────────────────────────

def in_window(window: str) -> bool:
    """Check if current time falls in a window like '03:00-05:00'."""
    m = re.match(r"(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})", window)
    if not m:
        return False
    now = time.localtime()
    now_minutes = now.tm_hour * 60 + now.tm_min
    start = int(m.group(1)) * 60 + int(m.group(2))
    end = int(m.group(3)) * 60 + int(m.group(4))
    if start <= end:
        return start <= now_minutes < end
    else:
        return now_minutes >= start or now_minutes < end


# ── Scheduler ─────────────────────────────────────────────────────

@dataclass
class ScheduleConfig:
    enabled: bool = True
    cron_expression: str = ""         # e.g. "0 3 * * *"
    time_window: str = ""             # e.g. "03:00-05:00"
    check_interval_seconds: float = 60.0  # How often to poll


class DreamScheduler:
    """Polling-based scheduler that triggers dreams at configured times."""

    def __init__(
        self,
        config: Optional[ScheduleConfig] = None,
        *,
        on_trigger: Optional[Callable[[], Any]] = None,
    ) -> None:
        self._config = config or ScheduleConfig()
        self._on_trigger = on_trigger
        self._running = False
        self._task: Optional[asyncio.Task[None]] = None
        self._last_trigger: float = 0.0
        self._trigger_cooldown: float = 300.0  # 5 min between triggers

    async def start(self) -> None:
        if not self._config.enabled:
            logger.info("DreamScheduler disabled")
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info(
            "DreamScheduler started (cron=%s, window=%s, interval=%.0fs)",
            self._config.cron_expression or "none",
            self._config.time_window or "any",
            self._config.check_interval_seconds,
        )

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _loop(self) -> None:
        while self._running:
            try:
                if self._should_trigger():
                    logger.info("DreamScheduler: triggering scheduled dream")
                    if self._on_trigger:
                        result = self._on_trigger()
                        if asyncio.iscoroutine(result):
                            await result
                    self._last_trigger = time.time()
            except Exception:
                logger.exception("DreamScheduler loop error")
            await asyncio.sleep(self._config.check_interval_seconds)

    def _should_trigger(self) -> bool:
        """Check if conditions are met to trigger a dream."""
        if time.time() - self._last_trigger < self._trigger_cooldown:
            return False

        # Check window
        if self._config.time_window and not in_window(self._config.time_window):
            return False

        # Check cron
        if self._config.cron_expression and not cron_matches(self._config.cron_expression):
            return False

        return True
