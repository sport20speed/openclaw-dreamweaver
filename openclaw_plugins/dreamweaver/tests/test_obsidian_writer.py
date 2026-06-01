"""Unit tests for ObsidianWriter."""

from __future__ import annotations

import os
from typing import Any, Optional

import pytest

from openclaw_plugins.dreamweaver.obsidian_writer import (
    ObsidianWriter,
    ObsidianWriterConfig,
    VaultNote,
    _chunk_text,
    _extract_wikilinks,
    _slugify,
)
from openclaw_plugins.dreamweaver.self_play import DreamResult


class FakeVaultFS:
    def __init__(self, existing_notes: list[str] | None = None) -> None:
        self.notes: dict[str, VaultNote] = {}
        self.stubs: list[str] = []
        self._existing = set(existing_notes or [])

    async def write_note(self, note: VaultNote) -> str:
        self.notes[note.path] = note
        return os.path.join("/fake/vault", note.path)

    async def note_exists(self, title: str) -> Optional[str]:
        for note in self.notes.values():
            if note.title == title:
                return note.path
        if title in self._existing:
            return f"existing/{title}.md"
        return None

    async def create_stub(self, title: str) -> str:
        self.stubs.append(title)
        note = VaultNote(path=f"stubs/{title}.md", title=title, content=f"# {title}\n\n存根笔记 — 由 DreamWeaver 自动创建。\n")
        self.notes[note.path] = note
        return note.path


class FakeVectorDB:
    def __init__(self) -> None:
        self.dream_chunks: list[dict[str, Any]] = []
        self.conversation_summaries: list[dict[str, Any]] = []

    async def add_dream_chunks(self, dream_id: str, chunks: list[str], metadata: dict[str, Any]) -> None:
        self.dream_chunks.append({"dream_id": dream_id, "chunks": list(chunks), "metadata": dict(metadata)})

    async def add_conversation_summary(self, dream_id: str, motif: str, summary: str) -> None:
        self.conversation_summaries.append({"dream_id": dream_id, "motif": motif, "summary": summary})


def _make_result(**overrides: Any) -> DreamResult:
    defaults = dict(motif="如何用最少的代码重构核心模块", final_solution="采用微内核架构 [[微内核]] [[IPC通信]] 重新设计核心调度层...",
                    best_score=8.7, total_iterations=45, logs=[], started_at=0.0, finished_at=1.0, convergence_reason="convergence")
    defaults.update(overrides)
    return DreamResult(**defaults)


def test_slugify_basic() -> None:
    assert _slugify("Hello World") == "Hello-World"


def test_slugify_strips_chinese() -> None:
    assert _slugify("你好世界") == "dream"


def test_slugify_truncates() -> None:
    long = "a" * 80
    result = _slugify(long, max_len=60)
    assert len(result) <= 60


def test_slugify_special_chars() -> None:
    assert _slugify("A/B:C*D?") == "ABCD"


def test_extract_wikilinks() -> None:
    content = "参考 [[微内核]] 和 [[IPC通信]] 的设计"
    links = _extract_wikilinks(content)
    assert links == ["微内核", "IPC通信"]


def test_extract_no_links() -> None:
    assert _extract_wikilinks("没有链接的内容") == []


def test_chunk_text_short() -> None:
    chunks = _chunk_text("短文本", max_chars=500)
    assert len(chunks) == 1
    assert chunks[0] == "短文本"


def test_chunk_text_long() -> None:
    long_text = ("段落内容。" * 200) + "\n\n" + ("另一段。" * 200)
    chunks = _chunk_text(long_text, max_chars=1000)
    assert len(chunks) >= 2


@pytest.mark.asyncio
async def test_write_creates_note() -> None:
    fs = FakeVaultFS()
    writer = ObsidianWriter(fs=fs)
    result = _make_result()
    path = await writer.write(result)
    assert path is not None
    assert len(fs.notes) >= 1


@pytest.mark.asyncio
async def test_note_has_frontmatter() -> None:
    fs = FakeVaultFS()
    writer = ObsidianWriter(fs=fs)
    result = _make_result()
    await writer.write(result)
    note = list(fs.notes.values())[0]
    assert "---" in note.content
    assert "dream_id:" in note.content
    assert "score:" in note.content
    assert "## 背景与问题" in note.content
    assert "## 最终方案" in note.content
    assert "## 演化历程摘要" in note.content
    assert "## 行动建议" in note.content


@pytest.mark.asyncio
async def test_wikilinks_resolved_to_stubs() -> None:
    fs = FakeVaultFS(existing_notes=["微内核"])
    writer = ObsidianWriter(fs=fs)
    result = _make_result(final_solution="使用 [[微内核]] 和 [[IPC通信]] 方案")
    await writer.write(result)
    assert "IPC通信" in fs.stubs or any("IPC通信" in n.title for n in fs.notes.values())


@pytest.mark.asyncio
async def test_vector_db_sync() -> None:
    vdb = FakeVectorDB()
    fs = FakeVaultFS()
    writer = ObsidianWriter(fs=fs, vector_db=vdb)
    result = _make_result()
    await writer.write(result)
    assert len(vdb.dream_chunks) >= 1
    assert len(vdb.conversation_summaries) == 1
    assert "45 轮" in vdb.conversation_summaries[0]["summary"]


@pytest.mark.asyncio
async def test_no_fs_returns_none() -> None:
    writer = ObsidianWriter(fs=None)
    result = _make_result()
    path = await writer.write(result)
    assert path is None


@pytest.mark.asyncio
async def test_fs_error_returns_none() -> None:
    class BrokenFS:
        async def write_note(self, note: VaultNote) -> str:
            raise OSError("disk full")
        async def note_exists(self, title: str) -> Optional[str]:
            return None
        async def create_stub(self, title: str) -> str:
            return ""
    writer = ObsidianWriter(fs=BrokenFS())
    result = _make_result()
    path = await writer.write(result)
    assert path is None


@pytest.mark.asyncio
async def test_vdb_error_does_not_kill_write() -> None:
    class BrokenVDB:
        async def add_dream_chunks(self, *args: Any, **kwargs: Any) -> None:
            raise RuntimeError("ChromaDB down")
        async def add_conversation_summary(self, *args: Any, **kwargs: Any) -> None:
            raise RuntimeError("ChromaDB down")
    fs = FakeVaultFS()
    writer = ObsidianWriter(fs=fs, vector_db=BrokenVDB())
    result = _make_result()
    path = await writer.write(result)
    assert path is not None
    assert len(fs.notes) >= 1


@pytest.mark.asyncio
async def test_convergence_tags() -> None:
    fs = FakeVaultFS()
    writer = ObsidianWriter(fs=fs)
    for reason, tag in [("convergence", "converged"), ("interrupted", "interrupted"), ("max_iterations", "dream")]:
        result = _make_result(convergence_reason=reason)
        await writer.write(result)
        dream_notes = [n for n in fs.notes.values() if "Dreams" in n.path.replace("\\", "/")]
        note = dream_notes[-1]
        assert tag in note.content or tag in str(note.frontmatter.get("tags", []))


@pytest.mark.asyncio
async def test_vault_path_structure() -> None:
    fs = FakeVaultFS()
    writer = ObsidianWriter(fs=fs)
    result = _make_result()
    await writer.write(result)
    note = list(fs.notes.values())[0]
    normalized = note.path.replace("\\", "/")
    assert normalized.startswith("Dreams/20")
    assert normalized.endswith(".md")


@pytest.mark.asyncio
async def test_wikilink_stub_errors_are_silent() -> None:
    class PartialFS:
        async def write_note(self, note: VaultNote) -> str:
            return "/fake/path.md"
        async def note_exists(self, title: str) -> Optional[str]:
            raise OSError("cannot read")
        async def create_stub(self, title: str) -> str:
            raise OSError("cannot create")
    writer = ObsidianWriter(fs=PartialFS())
    result = _make_result(final_solution="使用 [[某概念]] 方案")
    path = await writer.write(result)
    assert path is not None
