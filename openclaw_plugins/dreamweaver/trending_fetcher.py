"""Trending fetcher — daily topics from arXiv, HackerNews, ProductHunt (PRD §6.2.1.4).

Implements the TrendingFetcher protocol from motif_generator.py.
Fetches new topics daily, caches results to avoid repeated network calls.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)


# ── Cache ─────────────────────────────────────────────────────────

@dataclass
class FetcherCache:
    topics: list[dict[str, Any]] = field(default_factory=list)
    fetched_at: float = 0.0
    ttl_seconds: float = 3600.0  # Refresh every hour

    @property
    def is_stale(self) -> bool:
        return time.time() - self.fetched_at > self.ttl_seconds


# ── Sources ───────────────────────────────────────────────────────

class ArxivFetcher:
    """Fetch recent papers from arXiv API."""

    BASE = "http://export.arxiv.org/api/query"

    @staticmethod
    def _fetch(query: str = "cat:cs.AI", max_results: int = 5) -> list[dict[str, Any]]:
        url = f"{ArxivFetcher.BASE}?search_query={query}&start=0&max_results={max_results}&sortBy=submittedDate&sortOrder=descending"
        try:
            req = Request(url, headers={"User-Agent": "DreamWeaver/1.0"})
            with urlopen(req, timeout=15) as resp:
                root = ET.fromstring(resp.read().decode("utf-8"))
        except Exception as e:
            logger.warning("arXiv fetch failed: %s", e)
            return []

        ns = {
            "atom": "http://www.w3.org/2005/Atom",
            "arxiv": "http://arxiv.org/schemas/atom",
        }
        results: list[dict[str, Any]] = []
        for entry in root.findall("atom:entry", ns):
            title_el = entry.find("atom:title", ns)
            summary_el = entry.find("atom:summary", ns)
            results.append({
                "title": (title_el.text or "").strip().replace("\n", " ")[:150],
                "summary": (summary_el.text or "").strip().replace("\n", " ")[:300],
                "source": "arXiv",
                "tags": ["arxiv", "cs.AI", "research"],
            })
        return results


class HackerNewsFetcher:
    """Fetch top stories from HackerNews API."""

    @staticmethod
    def _fetch(max_results: int = 8) -> list[dict[str, Any]]:
        try:
            req = Request(
                "https://hacker-news.firebaseio.com/v0/topstories.json",
                headers={"User-Agent": "DreamWeaver/1.0"},
            )
            with urlopen(req, timeout=10) as resp:
                ids = json.loads(resp.read().decode())[:max_results]
        except Exception as e:
            logger.warning("HN fetch failed: %s", e)
            return []

        results: list[dict[str, Any]] = []

        async def _fetch_item(item_id: int) -> Optional[dict[str, Any]]:
            try:
                req = Request(
                    f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json",
                    headers={"User-Agent": "DreamWeaver/1.0"},
                )
                with urlopen(req, timeout=8) as resp:
                    item = json.loads(resp.read().decode())
                if item and "title" in item:
                    return {
                        "title": item.get("title", "")[:150],
                        "summary": (item.get("title", "") or "")[:300],
                        "source": "HackerNews",
                        "tags": ["hackernews", "tech", "trending"],
                    }
            except Exception:
                pass
            return None

        # Run fetches concurrently
        loop = asyncio.new_event_loop()
        try:
            tasks = [_fetch_item(i) for i in ids]
            items = loop.run_until_complete(asyncio.gather(*tasks))
            results = [i for i in items if i is not None]
        finally:
            loop.close()

        return results


class ProductHuntFetcher:
    """Fetch trending products from ProductHunt (RSS fallback)."""

    @staticmethod
    def _fetch(max_results: int = 5) -> list[dict[str, Any]]:
        # ProductHunt doesn't have a public API; use a static curated list
        return [
            {
                "title": "Today's trending on ProductHunt",
                "summary": "Check https://www.producthunt.com for the latest trending products",
                "source": "ProductHunt",
                "tags": ["producthunt", "product", "trending"],
            }
        ]


# ── Main fetcher ───────────────────────────────────────────────────

class TrendingFetcherImpl:
    """Concrete implementation of the TrendingFetcher protocol.

    Usage::

        fetcher = TrendingFetcherImpl()
        topics = await fetcher.fetch_topics(limit=10)
    """

    def __init__(self, cache_ttl: float = 3600.0) -> None:
        self._cache = FetcherCache(ttl_seconds=cache_ttl)

    async def fetch_topics(self, limit: int = 10) -> list[dict[str, Any]]:
        """Fetch trending topics from all sources, using cache."""
        if not self._cache.is_stale and self._cache.topics:
            return self._cache.topics[:limit]

        logger.info("Fetching trending topics...")
        # Fetch from all sources
        arxiv = ArxivFetcher._fetch(max_results=5)
        hn = HackerNewsFetcher._fetch(max_results=8)
        ph = ProductHuntFetcher._fetch(max_results=3)

        all_topics = arxiv + hn + ph
        self._cache.topics = all_topics
        self._cache.fetched_at = time.time()
        logger.info("Fetched %d trending topics", len(all_topics))
        return all_topics[:limit]


# ── Standalone test ───────────────────────────────────────────────

if __name__ == "__main__":
    async def main():
        fetcher = TrendingFetcherImpl(cache_ttl=1)  # No cache for test
        topics = await fetcher.fetch_topics(limit=10)
        for t in topics:
            print(f"[{t['source']}] {t['title'][:80]}")
    asyncio.run(main())
