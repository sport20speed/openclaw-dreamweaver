"""DreamService — main orchestrator for the dream lifecycle (PRD §5.2).

Ties together IdleDetector → MotifGenerator → SelfPlayEngine → ObsidianWriter.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Callable, Optional

from .config import DreamWeaverConfig
from .idle_detector import ActivityState, IdleDetector
from .models import DreamStatus, DreamStatusResponse
from .motif_generator import MotifCandidate, MotifGenerator
from .obsidian_writer import ObsidianWriter
from .resource_monitor import ResourceMonitor
from .self_play import DreamResult, LLMProvider, SelfPlayConfig, SelfPlayEngine

logger = logging.getLogger(__name__)

StatusCallback = Callable[[dict[str, Any]], Any]


class DreamService:
    def __init__(self, config: DreamWeaverConfig, llm: LLMProvider, *,
                 judge_llm: Optional[LLMProvider] = None,
                 motif_generator: Optional[MotifGenerator] = None,
                 writer: Optional[ObsidianWriter] = None,
                 resource_monitor: Optional[ResourceMonitor] = None) -> None:
        self._config = config
        self._llm = llm
        self._judge_llm = judge_llm or llm
        self._motif_gen = motif_generator
        self._writer = writer
        self._resources = resource_monitor or ResourceMonitor()
        self._idle_detector = IdleDetector(config)
        self._idle_detector.on_state_change = self._on_activity_change

        self._status: DreamStatus = DreamStatus.IDLE
        self._current_round: int = 0
        self._current_motif: Optional[str] = None
        self._best_score: float = 0.0
        self._started_at: float = 0.0
        self._last_result: Optional[DreamResult] = None
        self._stop_signal: Optional[asyncio.Event] = None
        self._run_task: Optional[asyncio.Task[None]] = None

        self.on_status_push: Optional[StatusCallback] = None
        self.on_dream_complete: Optional[Callable[[DreamResult], Any]] = None

    async def start(self) -> None:
        if self._config.enabled:
            await self._idle_detector.start()
            logger.info("DreamService started (idle timeout=%ds)", self._config.idle_timeout_seconds)
        else:
            logger.info("DreamService disabled by config")

    async def stop(self) -> None:
        if self._status == DreamStatus.RUNNING:
            await self.stop_dream()
        await self._idle_detector.stop()
        logger.info("DreamService stopped")

    async def start_dream(self, motif: Optional[str] = None) -> bool:
        if self._status == DreamStatus.RUNNING:
            logger.warning("Dream already running, ignoring start_dream")
            return False
        ready = await self._resources.wait_until_ready()
        if not ready:
            self._set_status(DreamStatus.IDLE)
            return False
        self._set_status(DreamStatus.RUNNING)
        self._stop_signal = asyncio.Event()
        self._run_task = asyncio.create_task(self._dream_loop(motif))
        return True

    async def stop_dream(self) -> Optional[DreamResult]:
        if self._status != DreamStatus.RUNNING:
            return None
        if self._stop_signal:
            self._stop_signal.set()
        if self._run_task:
            try:
                await asyncio.wait_for(self._run_task, timeout=10.0)
            except asyncio.TimeoutError:
                logger.warning("Dream did not stop within 10s, cancelling task")
                self._run_task.cancel()
                try:
                    await self._run_task
                except asyncio.CancelledError:
                    pass
        self._set_status(DreamStatus.INTERRUPTED)
        self._run_task = None
        # ── 释放锁 ──
        try:
            if _os.path.exists(_lock):
                _os.remove(_lock)
        except Exception:
            pass
        return self._last_result

    def status(self) -> DreamStatusResponse:
        elapsed = (time.time() - self._started_at) if self._started_at > 0 else 0.0
        return DreamStatusResponse(status=self._status, current_round=self._current_round,
                                   max_rounds=self._config.max_iterations, motif=self._current_motif,
                                   best_score=self._best_score, elapsed_seconds=elapsed)

    async def _on_activity_change(self, old: ActivityState, new: ActivityState) -> None:
        if new == ActivityState.IDLE:
            logger.info("DreamService: user idle detected, triggering dream")
            await self.start_dream()
        elif new == ActivityState.ACTIVE and self._status == DreamStatus.RUNNING:
            logger.info("DreamService: user returned, interrupting dream")
            await self.stop_dream()

    async def _dream_loop(self, manual_motif: Optional[str]) -> None:
        self._started_at = time.time()
        self._current_round = 0
        self._best_score = 0.0
        try:
            motif_candidate: Optional[MotifCandidate] = None
            if manual_motif:
                motif_candidate = MotifCandidate(source="manual", title=manual_motif, description=manual_motif,
                                                  score_relevance=10.0, score_innovation=10.0,
                                                  score_solvability=10.0, score_actionability=10.0)
            elif self._motif_gen:
                motif_candidate = await self._motif_gen.generate()

            if motif_candidate is None:
                logger.warning("DreamService: no motif generated, aborting")
                self._set_status(DreamStatus.IDLE)
                return

            self._current_motif = motif_candidate.title
            await self._push_status()

            play_config = SelfPlayConfig(
                max_iterations=self._config.max_iterations,
                convergence_rounds=self._config.convergence_rounds,
                checkpoint_interval=self._config.checkpoint_interval,
                mutation_interval=self._config.mutation_interval,
            )
            engine = SelfPlayEngine(self._llm, play_config, judge_llm=self._judge_llm)

            async def on_checkpoint(result: DreamResult) -> None:
                self._current_round = result.total_iterations
                self._best_score = result.best_score
                await self._push_status()

            result = await engine.run(motif=motif_candidate.title, stop_signal=self._stop_signal, on_checkpoint=on_checkpoint)
            self._last_result = result
            self._current_round = result.total_iterations
            self._best_score = result.best_score

            if result.convergence_reason == "interrupted":
                self._set_status(DreamStatus.INTERRUPTED)
            else:
                self._set_status(DreamStatus.COMPLETED)
            # ── 释放锁 ──
            try:
                if _os.path.exists(_lock):
                    _os.remove(_lock)
            except Exception:
                pass

            if self._writer and result.convergence_reason != "interrupted":
                path = await self._writer.write(result)
                if path:
                    logger.info("Dream result saved to %s", path)

            if self.on_dream_complete:
                result_cb = self.on_dream_complete(result)
                if asyncio.iscoroutine(result_cb):
                    await result_cb

            await self._push_status()
        except Exception:
            logger.exception("Dream loop crashed")
            self._set_status(DreamStatus.FAILED)
            await self._push_status()
            # ── 释放锁 ──
            try:
                if _os.path.exists(_lock):
                    _os.remove(_lock)
            except Exception:
                pass

    def _set_status(self, s: DreamStatus) -> None:
        self._status = s

    async def _push_status(self) -> None:
        if self.on_status_push:
            data = self.status().model_dump()
            result = self.on_status_push(data)
            if asyncio.iscoroutine(result):
                await result
