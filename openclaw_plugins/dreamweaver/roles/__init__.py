"""DreamWeaver self-play roles — Genius, Critic, Judge, Refiner, Mutator."""

from .base import BaseRole, DreamContext, RoleOutput, LLMProvider
from .genius import GeniusRole
from .critic import CriticRole
from .judge import JudgeRole
from .refiner import RefinerRole
from .mutator import MutatorRole

__all__ = [
    "BaseRole", "DreamContext", "RoleOutput", "LLMProvider",
    "GeniusRole", "CriticRole", "JudgeRole", "RefinerRole", "MutatorRole",
]
