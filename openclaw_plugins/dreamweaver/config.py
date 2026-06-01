"""DreamWeaver configuration — reads from OpenClaw config.yaml dreamweaver: section."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class DreamWeaverConfig:
    """Mirrors the dreamweaver: block in OpenClaw's config.yaml (§13.2)."""

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

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "DreamWeaverConfig":
        valid_keys = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in d.items() if k in valid_keys})

    @classmethod
    def defaults(cls) -> "DreamWeaverConfig":
        return cls()
