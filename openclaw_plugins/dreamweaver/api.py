"""FastAPI routes for DreamWeaver (PRD §6.5.2).

Endpoints::

    GET  /dream/status         — current dream state + progress
    POST /dream/start          — manually trigger a dream
    POST /dream/stop           — interrupt running dream
    GET  /dream/history        — paginated dream list
    GET  /dream/{dream_id}     — single dream detail
    DELETE /dream/{dream_id}   — remove dream + files
    POST /dream/{dream_id}/apply — mark as applied
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from .database import DreamRepository
from .dream_service import DreamService
from .models import DreamHistoryQuery, DreamStartRequest, DreamStatusResponse

logger = logging.getLogger(__name__)


def create_router(
    service: DreamService, repo: Optional[DreamRepository] = None
) -> APIRouter:
    """Build the /dream route group wired to a live DreamService and optional repo."""

    router = APIRouter(prefix="/dream", tags=["dreamweaver"])

    # ── Config ────────────────────────────────────────────────

    @router.get("/config")
    async def get_config() -> dict:
        """Return current runtime config."""
        c = service._config
        return {
            "enabled": c.enabled,
            "idle_timeout_seconds": c.idle_timeout_seconds,
            "max_iterations": c.max_iterations,
            "convergence_rounds": c.convergence_rounds,
            "mutation_interval": c.mutation_interval,
            "checkpoint_interval": c.checkpoint_interval,
            "max_dream_duration_minutes": c.max_dream_duration_minutes,
            "cloud_enabled": c.cloud_enabled,
            "cloud_model": c.cloud_model,
            "judge_model": c.judge_model,
            "local_model": c.local_model,
            "daily_token_limit": c.daily_token_limit,
            "notification": c.notification,
            "obsidian_vault_path": c.obsidian_vault_path,
            "dream_folder": c.dream_folder,
            "resource_cpu_threshold": c.resource_cpu_threshold,
            "resource_memory_threshold": c.resource_memory_threshold,
        }

    @router.post("/config")
    async def update_config(body: dict) -> dict:
        """Update runtime config. Send only the fields to change."""
        for key, val in body.items():
            if hasattr(service._config, key):
                setattr(service._config, key, val)
        return {"ok": True}

    # ── Status ────────────────────────────────────────────────

    @router.get("/status", response_model=DreamStatusResponse)
    async def get_status() -> DreamStatusResponse:
        """Return current dream state, progress, motif, and score."""
        return service.status()

    # ── Start / Stop ──────────────────────────────────────────

    @router.post("/start")
    async def start_dream(body: DreamStartRequest) -> dict:
        """Manually trigger a dream. Set motif in body or leave empty for auto."""
        ok = await service.start_dream(motif=body.motif)
        if not ok:
            raise HTTPException(
                status_code=409,
                detail="Dream already running or resources unavailable",
            )
        status = service.status()
        return {"ok": True, "status": status.model_dump()}

    @router.post("/stop")
    async def stop_dream() -> dict:
        """Interrupt the current dream, save checkpoint, return intermediate result."""
        result = await service.stop_dream()
        if result is None:
            raise HTTPException(status_code=404, detail="No dream is running")
        return {
            "ok": True,
            "motif": result.motif,
            "best_score": result.best_score,
            "iterations": result.total_iterations,
            "reason": result.convergence_reason,
        }

    # ── History ───────────────────────────────────────────────

    @router.get("/history")
    async def list_dreams(
        limit: int = Query(default=20, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
        sort_by: str = Query(default="created_at"),
    ) -> dict:
        """Return paginated dream history."""
        if repo is None:
            return {"items": [], "total": 0}
        items = await repo.list_dreams(limit=limit, offset=offset, sort_by=sort_by)
        total = await repo.count_dreams()
        return {"items": items, "total": total}

    # ── Detail ────────────────────────────────────────────────

    @router.get("/{dream_id}")
    async def get_dream(dream_id: str) -> dict:
        """Return a single dream with all its iteration logs."""
        if repo is None:
            raise HTTPException(status_code=404, detail="Repository not configured")
        dream = await repo.get_dream(dream_id)
        if dream is None:
            raise HTTPException(status_code=404, detail="Dream not found")
        iterations = await repo.get_iterations(dream_id)
        return {"dream": dream, "iterations": iterations}

    # ── Delete ────────────────────────────────────────────────

    @router.delete("/{dream_id}")
    async def delete_dream(dream_id: str) -> dict:
        """Remove a dream and its iteration logs."""
        if repo is None:
            raise HTTPException(status_code=404, detail="Repository not configured")
        await repo.delete_dream(dream_id)
        return {"ok": True}

    # ── Apply (user marks as implemented) ─────────────────────

    @router.post("/{dream_id}/apply")
    async def apply_dream(dream_id: str) -> dict:
        """Mark a dream as 'applied' (user has acted on its suggestions)."""
        if repo is None:
            raise HTTPException(status_code=404, detail="Repository not configured")
        dream = await repo.get_dream(dream_id)
        if dream is None:
            raise HTTPException(status_code=404, detail="Dream not found")
        await repo.update_dream(dream_id, status="applied")
        return {"ok": True}

    return router
