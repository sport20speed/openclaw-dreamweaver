"""TaskAnalyzer — extract unsolved problems from PI agent session logs (Dev Diary §3).

Reads PI agent JSONL session files, identifies user questions that weren't fully
resolved, and converts them into MotifCandidate objects for the MotifGenerator.
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any

from .motif_generator import MotifCandidate, MotifSource

logger = logging.getLogger(__name__)


# ── Session parsing ───────────────────────────────────────────────

class SessionReader:
    """Read and parse PI agent JSONL session files."""

    def __init__(self, sessions_dir: str | None = None) -> None:
        self._dir = Path(sessions_dir or os.path.expandvars(r"%USERPROFILE%\.pi\agent\sessions"))
        if not self._dir.exists():
            logger.warning("PI sessions dir not found: %s", self._dir)

    def list_files(self, *, limit: int = 10) -> list[Path]:
        """Return recent session files sorted by modification time."""
        files = sorted(
            self._dir.rglob("*.jsonl"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        return files[:limit]

    def read_session(self, path: Path) -> list[dict[str, Any]]:
        """Parse a JSONL session file into a list of events."""
        events: list[dict[str, Any]] = []
        try:
            with open(path, encoding="utf-8") as f:
                for lineno, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        logger.debug("Skipping malformed JSON at %s:%d", path, lineno)
        except Exception:
            logger.exception("Failed to read session: %s", path)
        return events


# ── Problem extraction ─────────────────────────────────────────────

class TaskAnalyzer:
    """Extract unsolved problems from PI agent session data."""

    # Phrases that indicate user dissatisfaction
    DISSAT_INDICATORS = [
        r"不对", r"不是这", r"再试", r"重新", r"换个", r"修正",
        r"还没", r"不完整", r"落掉了", r"忘了", r"还是不行",
        r"wrong", r"retry", r"again", r"not working", r"fix",
    ]

    # Minimum user message length to be considered a question
    MIN_QUESTION_LENGTH = 20

    def __init__(self, sessions_dir: str | None = None) -> None:
        self._reader = SessionReader(sessions_dir)

    async def analyze(self, limit_sessions: int = 5, max_results: int = 10) -> list[MotifCandidate]:
        """Scan recent PI sessions and extract unsolved problem motifs."""
        files = self._reader.list_files(limit=limit_sessions)
        if not files:
            return []

        candidates: list[MotifCandidate] = []

        for filepath in files:
            events = self._reader.read_session(filepath)
            extracted = self._extract_problems(events, source=str(filepath.name)[:40])
            candidates.extend(extracted)

        # Deduplicate by similar titles
        seen = set()
        unique: list[MotifCandidate] = []
        for c in candidates:
            key = c.title[:60].lower()
            if key not in seen:
                seen.add(key)
                unique.append(c)

        return unique[:max_results]

    def _extract_problems(self, events: list[dict[str, Any]], source: str) -> list[MotifCandidate]:
        """Find user messages followed by dissatisfaction patterns."""
        user_msgs: list[dict[str, Any]] = []
        assistant_msgs: list[dict[str, Any]] = []

        for e in events:
            if e.get("type") != "message":
                continue
            role = e.get("role", "")
            if role == "user":
                user_msgs.append(e)
            elif role == "assistant":
                assistant_msgs.append(e)

        problems: list[MotifCandidate] = []

        for i, msg in enumerate(user_msgs):
            content = (msg.get("content") or "").strip()
            if len(content) < self.MIN_QUESTION_LENGTH:
                continue

            # Check if user showed dissatisfaction with the NEXT user message
            next_msg = user_msgs[i + 1] if i + 1 < len(user_msgs) else None
            if next_msg:
                next_content = (next_msg.get("content") or "").lower()
                if self._has_dissatisfaction(next_content):
                    title = self._to_motif_title(content)
                    problems.append(MotifCandidate(
                        source=MotifSource.UNSOLVED,
                        title=title,
                        description=content[:500],
                        tags=["pi-session", "unsolved"],
                    ))

        return problems

    def _has_dissatisfaction(self, text: str) -> bool:
        """Check if text contains dissatisfaction indicators."""
        text_lower = text.lower()
        for pattern in self.DISSAT_INDICATORS:
            if re.search(pattern, text_lower):
                return True
        return False

    @staticmethod
    def _to_motif_title(question: str) -> str:
        """Convert a user question into a motif title."""
        # Clean up
        title = question.strip()
        # Remove common prefixes
        prefixes = ["请", "帮我", "你能", "能不能", "可以", "请问", "你好", "hi", "hey"]
        for prefix in prefixes:
            if title.lower().startswith(prefix.lower()):
                title = title[len(prefix):].strip()
        # Limit length
        if len(title) > 120:
            title = title[:120] + "..."
        return title
