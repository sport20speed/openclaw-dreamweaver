"""DreamWeaver data models — SQLite ORM models and Pydantic schemas."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class DreamStatus(str, enum.Enum):
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    INTERRUPTED = "interrupted"


class UserActivity(str, enum.Enum):
    ACTIVE = "active"
    IDLE = "idle"


class AgentRole(str, enum.Enum):
    GENIUS = "genius"
    CRITIC = "critic"
    JUDGE = "judge"
    REFINER = "refiner"
    MUTATOR = "mutator"


class DreamRecord(BaseModel):
    id: str
    motif: str
    status: DreamStatus = DreamStatus.IDLE
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    iterations: int = 0
    best_score: Optional[float] = None
    outcome_path: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    model_used: str = ""
    created_at: datetime = Field(default_factory=datetime.now)


class DreamIteration(BaseModel):
    id: Optional[int] = None
    dream_id: str
    round: int
    role: AgentRole
    prompt: str
    response: str
    score: Optional[float] = None
    tokens_used: int = 0
    timestamp: datetime = Field(default_factory=datetime.now)


class DreamStatusResponse(BaseModel):
    status: DreamStatus
    current_round: int = 0
    max_rounds: int = 100
    motif: Optional[str] = None
    best_score: Optional[float] = None
    elapsed_seconds: float = 0.0


class DreamStartRequest(BaseModel):
    motif: Optional[str] = None


class DreamHistoryQuery(BaseModel):
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    sort_by: str = "score"


class DreamConfig(BaseModel):
    enabled: bool = True
    idle_timeout_seconds: int = 900
    max_iterations: int = 100
    convergence_rounds: int = 20
    obsidian_vault_path: str = ""
    dream_folder: str = "Dreams"
    cloud_enabled: bool = False
    local_model: str = "deepseek-coder:33b"
    daily_token_limit: int = 100_000
    notification: bool = True
    max_dream_duration_minutes: int = 60
    checkpoint_interval: int = 10
    mutation_interval: int = 10
    api_retry_max: int = 3
    resource_cpu_threshold: int = 80
    resource_memory_threshold: int = 85
