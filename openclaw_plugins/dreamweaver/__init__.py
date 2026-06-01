"""OpenClaw DreamWeaver — 梦境自主进化引擎插件。

Usage (from OpenClaw bootstrap)::

    from openclaw_plugins.dreamweaver import DreamWeaverPlugin
    plugin = DreamWeaverPlugin(config_dict, llm_provider)
    await plugin.setup()
    app.include_router(plugin.router)
    await plugin.start()
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

from .api import create_router
from .config import DreamWeaverConfig
from .database import DreamRepository
from .dream_service import DreamService
from .obsidian_writer import ObsidianWriter
from .resource_monitor import PsutilProbe, ResourceConfig, ResourceMonitor
from .self_play import LLMProvider

logger = logging.getLogger(__name__)


class DreamWeaverPlugin:
    """Top-level plugin that wires all sub-modules and exposes the API router.

    Minimal integration surface — OpenClaw calls setup() then start().
    """

    def __init__(
        self,
        raw_config: Dict[str, Any],
        llm: LLMProvider,
    ) -> None:
        self._config = DreamWeaverConfig.from_dict(raw_config)
        self._llm = llm

        # Sub-modules (built during setup)
        self.service: Optional[DreamService] = None
        self.router: Any = None
        self._repo: Optional[DreamRepository] = None
        self._resource_monitor: Optional[ResourceMonitor] = None
        self._writer: Optional[ObsidianWriter] = None

    @property
    def config(self) -> DreamWeaverConfig:
        return self._config

    # ── Lifecycle ──────────────────────────────────────────────

    async def setup(
        self,
        *,
        db_path: str = "openclaw_data/dreamweaver.db",
        vault_fs: Any = None,  # VaultFileSystem impl
        vector_db: Any = None,  # VectorDB impl
    ) -> None:
        """Initialise sub-modules. Call once before start()."""
        if not self._config.enabled:
            logger.info("DreamWeaver disabled by config — skipping setup")
            return

        # Database
        self._repo = DreamRepository(db_path)
        await self._repo.init()

        # Resource monitor
        self._resource_monitor = ResourceMonitor(
            probe=PsutilProbe(),
            config=ResourceConfig(
                cpu_threshold=self._config.resource_cpu_threshold,
                memory_threshold=self._config.resource_memory_threshold,
            ),
        )

        # Obsidian writer
        if self._config.obsidian_vault_path and vault_fs:
            from .obsidian_writer import ObsidianWriterConfig

            self._writer = ObsidianWriter(
                fs=vault_fs,
                vector_db=vector_db,
                config=ObsidianWriterConfig(
                    vault_path=self._config.obsidian_vault_path,
                    dream_folder=self._config.dream_folder,
                ),
            )

        # Dream service (orchestrator)
        self.service = DreamService(
            config=self._config,
            llm=self._llm,
            writer=self._writer,
            resource_monitor=self._resource_monitor,
        )

        # Wire up persistence callbacks
        if self._repo:
            async def on_complete(result: Any) -> None:
                # Save DreamResult to SQLite
                from datetime import datetime

                dream_id = datetime.now().strftime("%Y%m%d-") + "dream"
                await self._repo.save_result(dream_id, result)  # type: ignore[union-attr]

            self.service.on_dream_complete = on_complete

        # API router
        self.router = create_router(self.service, self._repo)

    async def start(self) -> None:
        """Begin listening for idle events."""
        if self.service:
            await self.service.start()
            logger.info("DreamWeaver plugin started")

    async def stop(self) -> None:
        """Graceful shutdown."""
        if self.service:
            await self.service.stop()
        if self._repo:
            await self._repo.close()
        logger.info("DreamWeaver plugin stopped")

    # ── Convenience (for embedding into host app) ──────────────

    def get_router(self) -> Any:
        if self.router is None:
            raise RuntimeError("Call setup() before get_router()")
        return self.router
