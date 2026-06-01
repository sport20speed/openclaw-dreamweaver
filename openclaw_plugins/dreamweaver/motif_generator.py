"""MotifGenerator — collects, scores, and selects the best dream motif.

Motif sources (PRD §6.2.1):
  1. User unsolved tasks (from OpenClaw task history)
  2. Knowledge graph gaps (from Obsidian vault note graph)
  3. User #dream tags (highest priority)
  4. Global trending topics (arXiv, ProductHunt, HackerNews)
  5. Random cross-domain mutation (5 % chance)

Scoring dimensions (each 0-10): relevance, innovation, solvability, actionability.
"""

from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol

logger = logging.getLogger(__name__)


class MotifSource:
    UNSOLVED = "unsolved"
    KNOWLEDGE_GAP = "knowledge_gap"
    USER_TAGGED = "user_tagged"
    TRENDING = "trending"
    CROSS_DOMAIN = "cross_domain"


@dataclass
class MotifCandidate:
    source: str
    title: str
    description: str
    tags: list[str] = field(default_factory=list)
    score_relevance: float = 0.0
    score_innovation: float = 0.0
    score_solvability: float = 0.0
    score_actionability: float = 0.0

    @property
    def total_score(self) -> float:
        return self.score_relevance + self.score_innovation + self.score_solvability + self.score_actionability


class TaskHistoryProvider(Protocol):
    async def get_unsolved_tasks(self, limit: int = 10) -> list[dict[str, Any]]: ...


class VaultReader(Protocol):
    async def find_tagged_notes(self, tag: str, limit: int = 20) -> list[dict[str, Any]]: ...
    async def get_graph_gaps(self, min_refs: int = 3, max_edges: int = 2) -> list[dict[str, Any]]: ...


class TrendingFetcher(Protocol):
    async def fetch_topics(self, limit: int = 10) -> list[dict[str, Any]]: ...


class LLMScorer(Protocol):
    async def score_candidates(self, candidates: list[MotifCandidate]) -> list[MotifCandidate]: ...


@dataclass
class MotifGeneratorConfig:
    cross_domain_probability: float = 0.05
    max_candidates_per_source: int = 5
    max_unsolved_tasks: int = 10
    max_tagged_notes: int = 20
    max_trending_topics: int = 10
    knowledge_gap_min_refs: int = 3
    knowledge_gap_max_edges: int = 2


class MotifGenerator:
    def __init__(
        self,
        task_provider: Optional[TaskHistoryProvider] = None,
        vault_reader: Optional[VaultReader] = None,
        trending_fetcher: Optional[TrendingFetcher] = None,
        llm_scorer: Optional[LLMScorer] = None,
        config: Optional[MotifGeneratorConfig] = None,
    ) -> None:
        self._tasks = task_provider
        self._vault = vault_reader
        self._trending = trending_fetcher
        self._scorer = llm_scorer
        self._config = config or MotifGeneratorConfig()

    async def generate(self, *, user_motif: Optional[str] = None) -> Optional[MotifCandidate]:
        if user_motif:
            logger.info("Using user-supplied motif: %s", user_motif[:80])
            return MotifCandidate(source=MotifSource.USER_TAGGED, title=user_motif, description=user_motif,
                                  score_relevance=10.0, score_innovation=10.0, score_solvability=10.0, score_actionability=10.0)

        candidates: list[MotifCandidate] = []
        results = await asyncio.gather(
            self._collect_user_tagged(), self._collect_unsolved(),
            self._collect_knowledge_gaps(), self._collect_trending(),
            return_exceptions=True,
        )
        for result in results:
            if isinstance(result, Exception):
                logger.warning("Motif source collection failed: %s", result)
            elif isinstance(result, list):
                candidates.extend(result)

        cross = await self._collect_cross_domain(candidates)
        if cross:
            candidates.extend(cross)

        if not candidates:
            logger.warning("No motif candidates collected from any source")
            return None

        scored = await self._score_candidates(candidates)
        best = self._select_best(scored)
        logger.info("Selected motif: '%s' (source=%s, score=%.1f)", best.title[:80], best.source, best.total_score)
        return best

    async def _collect_user_tagged(self) -> list[MotifCandidate]:
        if self._vault is None:
            return []
        try:
            notes = await self._vault.find_tagged_notes("dream", limit=self._config.max_tagged_notes)
        except Exception:
            logger.exception("Failed to read #dream tagged notes")
            return []
        out: list[MotifCandidate] = []
        for n in notes[: self._config.max_candidates_per_source]:
            out.append(MotifCandidate(source=MotifSource.USER_TAGGED, title=n.get("title", ""),
                       description=n.get("content", "")[:500], tags=n.get("tags", [])))
        return out

    async def _collect_unsolved(self) -> list[MotifCandidate]:
        if self._tasks is None:
            return []
        try:
            tasks = await self._tasks.get_unsolved_tasks(limit=self._config.max_unsolved_tasks)
        except Exception:
            logger.exception("Failed to query unsolved tasks")
            return []
        out: list[MotifCandidate] = []
        for t in tasks[: self._config.max_candidates_per_source]:
            desc = t.get("description", t.get("title", ""))
            out.append(MotifCandidate(source=MotifSource.UNSOLVED, title=t.get("title", ""),
                       description=desc[:500] if desc else "", tags=t.get("tags", [])))
        return out

    async def _collect_knowledge_gaps(self) -> list[MotifCandidate]:
        if self._vault is None:
            return []
        try:
            gaps = await self._vault.get_graph_gaps(min_refs=self._config.knowledge_gap_min_refs,
                                                     max_edges=self._config.knowledge_gap_max_edges)
        except Exception:
            logger.exception("Failed to query knowledge gaps")
            return []
        out: list[MotifCandidate] = []
        for g in gaps[: self._config.max_candidates_per_source]:
            node = g.get("node", "")
            out.append(MotifCandidate(source=MotifSource.KNOWLEDGE_GAP, title=f"如何连接 '{node}' 与相关知识",
                       description=f"'{node}' 被引用了 {g.get('ref_count', 0)} 次，但仅有 {g.get('edge_count', 0)} 条连接边。探索如何桥接这个概念与其他知识节点。"))
        return out

    async def _collect_trending(self) -> list[MotifCandidate]:
        if self._trending is None:
            return []
        try:
            topics = await self._trending.fetch_topics(limit=self._config.max_trending_topics)
        except Exception:
            logger.exception("Failed to fetch trending topics")
            return []
        out: list[MotifCandidate] = []
        for t in topics[: self._config.max_candidates_per_source]:
            out.append(MotifCandidate(source=MotifSource.TRENDING, title=t.get("title", ""),
                       description=t.get("summary", "")[:500], tags=t.get("tags", [])))
        return out

    async def _collect_cross_domain(self, existing: list[MotifCandidate]) -> list[MotifCandidate]:
        if random.random() > self._config.cross_domain_probability:
            return []
        if not existing:
            return []
        base = random.choice(existing)
        paradigms = ["流体力学原理", "区块链共识机制", "生物进化论", "量子纠缠", "蜂群智能",
                     "热力学第二定律", "分形几何", "博弈论中的囚徒困境", "光合作用能量转换", "蚁群路径优化"]
        paradigm = random.choice(paradigms)
        return [MotifCandidate(source=MotifSource.CROSS_DOMAIN,
                title=f"[跨域变异] 用{paradigm}重新审视: {base.title[:60]}",
                description=f"原始问题: {base.description[:200]}\n变异方向: 假设我们只能使用{paradigm}来理解并解决此问题，会产生怎样意想不到的方案？",
                tags=base.tags + ["cross-domain", paradigm])]

    async def _score_candidates(self, candidates: list[MotifCandidate]) -> list[MotifCandidate]:
        to_score: list[MotifCandidate] = []
        for c in candidates:
            if c.source == MotifSource.USER_TAGGED:
                c.score_relevance = 10.0; c.score_innovation = 10.0
                c.score_solvability = 10.0; c.score_actionability = 10.0
            else:
                to_score.append(c)
        if to_score and self._scorer:
            try:
                to_score = await self._scorer.score_candidates(to_score)
            except Exception:
                logger.exception("LLM scoring failed, using heuristic fallback")
                to_score = self._heuristic_score(to_score)
        elif to_score:
            to_score = self._heuristic_score(to_score)
        scored = [c for c in candidates if c.source == MotifSource.USER_TAGGED]
        scored.extend(to_score)
        return scored

    @staticmethod
    def _heuristic_score(candidates: list[MotifCandidate]) -> list[MotifCandidate]:
        for c in candidates:
            desc_len = len(c.description); tag_count = len(c.tags)
            c.score_relevance = min(7.0, 3.0 + desc_len / 100.0)
            c.score_innovation = 8.0 if c.source == MotifSource.CROSS_DOMAIN else 5.0
            c.score_solvability = min(8.0, 4.0 + tag_count * 0.5)
            c.score_actionability = min(7.0, 3.0 + desc_len / 150.0)
        return candidates

    @staticmethod
    def _select_best(candidates: list[MotifCandidate]) -> MotifCandidate:
        user_tagged = [c for c in candidates if c.source == MotifSource.USER_TAGGED]
        if user_tagged:
            return max(user_tagged, key=lambda c: c.total_score)
        return max(candidates, key=lambda c: c.total_score)
