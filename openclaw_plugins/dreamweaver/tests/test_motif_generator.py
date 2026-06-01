"""Unit tests for MotifGenerator."""

from __future__ import annotations

from typing import Any

import pytest

from openclaw_plugins.dreamweaver.motif_generator import (
    LLMScorer,
    MotifCandidate,
    MotifGenerator,
    MotifGeneratorConfig,
    MotifSource,
    TaskHistoryProvider,
    TrendingFetcher,
    VaultReader,
)


class FakeTaskProvider:
    def __init__(self, tasks: list[dict[str, Any]] | None = None) -> None:
        self._tasks = tasks or []

    async def get_unsolved_tasks(self, limit: int = 10) -> list[dict[str, Any]]:
        return self._tasks[:limit]


class FakeVaultReader:
    def __init__(
        self,
        tagged: list[dict[str, Any]] | None = None,
        gaps: list[dict[str, Any]] | None = None,
    ) -> None:
        self._tagged = tagged or []
        self._gaps = gaps or []

    async def find_tagged_notes(
        self, tag: str, limit: int = 20
    ) -> list[dict[str, Any]]:
        return [n for n in self._tagged if tag in n.get("tags", [])][:limit]

    async def get_graph_gaps(
        self, min_refs: int = 3, max_edges: int = 2
    ) -> list[dict[str, Any]]:
        return [
            g
            for g in self._gaps
            if g.get("ref_count", 0) >= min_refs
            and g.get("edge_count", 0) <= max_edges
        ]


class FakeTrendingFetcher:
    def __init__(self, topics: list[dict[str, Any]] | None = None) -> None:
        self._topics = topics or []

    async def fetch_topics(self, limit: int = 10) -> list[dict[str, Any]]:
        return self._topics[:limit]


class FakeLLMScorer:
    async def score_candidates(
        self, candidates: list[MotifCandidate]
    ) -> list[MotifCandidate]:
        for c in candidates:
            c.score_relevance = 7.0
            c.score_innovation = 6.0
            c.score_solvability = 7.0
            c.score_actionability = 6.0
        return candidates


def _make_generator(tasks=None, vault=None, trending=None, scorer=None, config=None) -> MotifGenerator:
    return MotifGenerator(task_provider=tasks, vault_reader=vault, trending_fetcher=trending, llm_scorer=scorer, config=config)


def _unsolved_tasks(count: int) -> list[dict[str, Any]]:
    return [
        {"id": f"task-{i}", "title": f"未解决任务 {i}", "description": f"这是第 {i} 个未完成任务的详细描述", "tags": ["pending", f"area-{i}"]}
        for i in range(count)
    ]


@pytest.mark.asyncio
async def test_user_supplied_motif_wins_immediately() -> None:
    gen = _make_generator()
    motif = await gen.generate(user_motif="用户自定义的母题")
    assert motif is not None
    assert motif.title == "用户自定义的母题"
    assert motif.source == MotifSource.USER_TAGGED
    assert motif.total_score == 40.0


@pytest.mark.asyncio
async def test_user_tagged_notes_max_priority() -> None:
    vault = FakeVaultReader(tagged=[{"title": "我的梦境想法", "content": "我希望 AI 帮我思考如何优化工作流", "tags": ["dream", "workflow"]}])
    gen = _make_generator(vault=vault)
    motif = await gen.generate()
    assert motif is not None
    assert motif.source == MotifSource.USER_TAGGED
    assert motif.total_score == 40.0


@pytest.mark.asyncio
async def test_no_providers_returns_none() -> None:
    gen = _make_generator()
    motif = await gen.generate()
    assert motif is None


@pytest.mark.asyncio
async def test_collects_unsolved_tasks() -> None:
    tasks = FakeTaskProvider(_unsolved_tasks(3))
    gen = _make_generator(tasks=tasks, scorer=FakeLLMScorer())
    motif = await gen.generate()
    assert motif is not None
    assert motif.source == MotifSource.UNSOLVED
    assert motif.total_score == 26.0


@pytest.mark.asyncio
async def test_falls_back_to_trending() -> None:
    trending = FakeTrendingFetcher([{"title": "最新 AI 突破", "summary": "某团队在模型压缩领域取得重大进展", "source": "arXiv", "tags": ["AI", "compression"]}])
    gen = _make_generator(trending=trending, scorer=FakeLLMScorer())
    motif = await gen.generate()
    assert motif is not None
    assert motif.source == MotifSource.TRENDING


@pytest.mark.asyncio
async def test_one_source_error_does_not_kill_pipeline() -> None:
    class BrokenVault:
        async def find_tagged_notes(self, tag: str, limit: int = 20):
            raise RuntimeError("disk broken")
        async def get_graph_gaps(self, min_refs=3, max_edges=2):
            raise RuntimeError("disk broken")
    tasks = FakeTaskProvider(_unsolved_tasks(2))
    gen = _make_generator(tasks=tasks, vault=BrokenVault(), scorer=FakeLLMScorer())
    motif = await gen.generate()
    assert motif is not None
    assert motif.source == MotifSource.UNSOLVED


@pytest.mark.asyncio
async def test_collects_knowledge_gaps() -> None:
    vault = FakeVaultReader(gaps=[{"node": "分布式系统", "ref_count": 10, "edge_count": 1}, {"node": "类型论", "ref_count": 8, "edge_count": 2}])
    gen = _make_generator(vault=vault, scorer=FakeLLMScorer())
    motif = await gen.generate()
    assert motif is not None
    assert motif.source == MotifSource.KNOWLEDGE_GAP
    assert "分布式系统" in motif.title or "类型论" in motif.title


@pytest.mark.asyncio
async def test_cross_domain_always_fires_with_p1() -> None:
    config = MotifGeneratorConfig(cross_domain_probability=1.0)
    tasks = FakeTaskProvider(_unsolved_tasks(1))
    gen = _make_generator(tasks=tasks, config=config, scorer=FakeLLMScorer())
    motif = await gen.generate()
    assert motif is not None
    assert motif.total_score == 26.0


@pytest.mark.asyncio
async def test_cross_domain_never_fires_with_p0() -> None:
    config = MotifGeneratorConfig(cross_domain_probability=0.0)
    tasks = FakeTaskProvider(_unsolved_tasks(1))
    gen = _make_generator(tasks=tasks, config=config, scorer=FakeLLMScorer())
    motif = await gen.generate()
    assert motif is not None
    assert motif.source == MotifSource.UNSOLVED


@pytest.mark.asyncio
async def test_heuristic_scoring_when_no_llm() -> None:
    tasks = FakeTaskProvider(_unsolved_tasks(1))
    gen = _make_generator(tasks=tasks)
    motif = await gen.generate()
    assert motif is not None
    assert motif.total_score > 0


@pytest.mark.asyncio
async def test_respects_max_candidates_per_source() -> None:
    config = MotifGeneratorConfig(max_candidates_per_source=2)
    tasks = FakeTaskProvider(_unsolved_tasks(10))
    gen = _make_generator(tasks=tasks, config=config, scorer=FakeLLMScorer())
    motif = await gen.generate()
    assert motif is not None
