"""ObsidianWriter — writes dream results to Obsidian vault and vector DB (PRD §6.4)."""

from __future__ import annotations

import asyncio
import logging
import os
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional, Protocol

from .self_play import DreamResult

logger = logging.getLogger(__name__)


@dataclass
class VaultNote:
    path: str
    title: str
    content: str
    frontmatter: dict[str, Any] = field(default_factory=dict)


class VaultFileSystem(Protocol):
    async def write_note(self, note: VaultNote) -> str: ...
    async def note_exists(self, title: str) -> Optional[str]: ...
    async def create_stub(self, title: str) -> str: ...


class VectorDB(Protocol):
    async def add_dream_chunks(self, dream_id: str, chunks: list[str], metadata: dict[str, Any]) -> None: ...
    async def add_conversation_summary(self, dream_id: str, motif: str, summary: str) -> None: ...


def _slugify(text: str, max_len: int = 60) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = re.sub(r"[^a-zA-Z0-9\s\-]", "", text)
    text = re.sub(r"[\s_]+", "-", text).strip("-")
    if len(text) > max_len:
        text = text[:max_len].rsplit("-", 1)[0]
    return text or "dream"


def _extract_wikilinks(content: str) -> list[str]:
    return re.findall(r"\[\[([^\]]+)\]\]", content)


def _chunk_text(text: str, max_chars: int = 1500) -> list[str]:
    paragraphs = text.split("\n\n")
    chunks: list[str] = []
    buf = ""
    for para in paragraphs:
        if len(buf) + len(para) > max_chars and buf:
            chunks.append(buf.strip())
            buf = para
        else:
            buf = buf + "\n\n" + para if buf else para
    if buf.strip():
        chunks.append(buf.strip())
    return chunks


@dataclass
class ObsidianWriterConfig:
    vault_path: str = ""
    dream_folder: str = "Dreams"
    chunk_max_chars: int = 1500


class ObsidianWriter:
    def __init__(self, fs: Optional[VaultFileSystem] = None, vector_db: Optional[VectorDB] = None,
                 config: Optional[ObsidianWriterConfig] = None) -> None:
        self._fs = fs
        self._vdb = vector_db
        self._config = config or ObsidianWriterConfig()

    async def write(self, result: DreamResult) -> Optional[str]:
        if not self._fs:
            logger.warning("No VaultFileSystem configured, skipping note write")
            return None
        note = self._build_note(result)
        try:
            abs_path = await self._fs.write_note(note)
            logger.info("Dream note written: %s", abs_path)
        except Exception:
            logger.exception("Failed to write dream note")
            return None

        wikilinks = _extract_wikilinks(result.final_solution)
        if self._fs:
            await asyncio.gather(*(self._ensure_link_target(link) for link in wikilinks), return_exceptions=True)

        if self._vdb:
            try:
                chunks = _chunk_text(result.final_solution, self._config.chunk_max_chars)
                await self._vdb.add_dream_chunks(dream_id=note.frontmatter.get("dream_id", ""), chunks=chunks,
                                                  metadata={"motif": result.motif, "score": result.best_score,
                                                            "date": note.frontmatter.get("date", ""),
                                                            "tags": note.frontmatter.get("tags", [])})
                summary = f"梦境：{result.motif[:120]} —— 评分 {result.best_score:.1f}，迭代 {result.total_iterations} 轮。详见 [[{note.title}]]"
                await self._vdb.add_conversation_summary(dream_id=note.frontmatter.get("dream_id", ""), motif=result.motif, summary=summary)
            except Exception:
                logger.exception("Vector DB sync failed, note still written")
        return abs_path

    def _build_note(self, result: DreamResult) -> VaultNote:
        now = datetime.now(timezone.utc)
        dream_id = now.strftime("%Y%m%d-") + _slugify(result.motif, 30)[:8]
        date_iso = now.strftime("%Y-%m-%dT%H:%M:%S")
        folder_date = now.strftime("%Y-%m-%d")
        title = f"梦境：{_slugify(result.motif, 50)}"
        tags = ["dream", "auto-generated"]
        if result.convergence_reason == "convergence":
            tags.append("converged")
        elif result.convergence_reason == "interrupted":
            tags.append("interrupted")

        evolution_lines = [f"- 总迭代轮数：{result.total_iterations}", f"- 最终得分：{result.best_score:.1f}/10",
                           f"- 结束原因：{result.convergence_reason}"]
        scored_logs = [log for log in result.logs if log.score is not None]
        if len(scored_logs) >= 3:
            best = max(scored_logs, key=lambda l: l.score or 0)
            evolution_lines.append(f"- 最高分轮次：第 {best.round} 轮 (角色: {best.role}, 得分: {best.score:.1f})")

        related_section = ""
        wikilinks = _extract_wikilinks(result.final_solution)
        if wikilinks:
            unique = list(dict.fromkeys(wikilinks))[:10]
            related_section = "## 与现有知识的关联\n" + "\n".join(f"- [[{link}]]" for link in unique) + "\n\n"

        content = f"""---
dream_id: {dream_id}
date: {date_iso}
motif: "{result.motif[:200]}"
score: {result.best_score:.1f}
iterations: {result.total_iterations}
tags: [{', '.join(tags)}]
convergence_reason: {result.convergence_reason}
---

# {title}

## 背景与问题
{result.motif}

## 最终方案
{result.final_solution}

## 演化历程摘要
{chr(10).join(evolution_lines)}

{related_section}## 行动建议
- [ ] 评审方案可行性
- [ ] 识别可立即应用的部分
- [ ] 如需深入，可基于此方案再次做梦
"""
        vault_rel_path = os.path.join(self._config.dream_folder, folder_date, f"{_slugify(result.motif, 50)}.md")
        return VaultNote(path=vault_rel_path, title=title, content=content, frontmatter={
            "dream_id": dream_id, "date": date_iso, "motif": result.motif,
            "score": result.best_score, "iterations": result.total_iterations, "tags": tags,
        })

    async def _ensure_link_target(self, target: str) -> None:
        if not self._fs:
            return
        try:
            exists = await self._fs.note_exists(target)
            if exists is None:
                await self._fs.create_stub(target)
                logger.debug("Created stub for [[%s]]", target)
        except Exception:
            logger.debug("Failed to check/create stub for [[%s]]", target)
