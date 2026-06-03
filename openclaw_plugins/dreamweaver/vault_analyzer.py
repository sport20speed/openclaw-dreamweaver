"""VaultAnalyzer — Obsidian knowledge graph gap detection (Dev Diary §4).

Scans an Obsidian vault directory, parses [[wikilinks]] from all .md files,
builds a directed graph, and identifies "hub orphans" — nodes with high
in-degree (heavily referenced) but low out-degree (poorly connected).

These are the knowledge gaps that MotifGenerator should target ("如何连接 A 与 B").
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .motif_generator import MotifCandidate, MotifSource

logger = logging.getLogger(__name__)


# ── Data types ─────────────────────────────────────────────────────

@dataclass
class GraphNode:
    name: str
    in_degree: int = 0       # How many notes link TO this node
    out_degree: int = 0      # How many outgoing links FROM notes titled this
    referencing_notes: list[str] = field(default_factory=list)
    out_links: list[str] = field(default_factory=list)

    @property
    def pagerank(self) -> float:
        """Simple approximate PageRank: in_degree weighted by out_degree of referrers."""
        if self.in_degree == 0:
            return 0.0
        # Baseline: in_degree normalized to [0, 1]
        return min(1.0, self.in_degree / max(self.out_degree, 1))

    @property
    def is_hub_orphan(self) -> bool:
        """Is this node heavily referenced but poorly connected?"""
        return self.in_degree >= 3 and self.out_degree <= 2


# ── Analyzer ───────────────────────────────────────────────────────

class VaultAnalyzer:
    """Scans Obsidian vault and identifies knowledge gaps."""

    def __init__(self, vault_path: str | None = None) -> None:
        self._vault = Path(vault_path) if vault_path else None
        if self._vault and not self._vault.exists():
            logger.warning("Vault path not found: %s", self._vault)

    async def analyze(
        self,
        *,
        max_notes: int = 500,
        min_refs: int = 3,
        max_edges: int = 2,
    ) -> list[dict[str, Any]]:
        """Scan vault and return graph gap nodes suitable for motif generation."""
        if not self._vault or not self._vault.exists():
            return []

        # Build graph
        graph = self._build_graph(max_notes=max_notes)

        # Find hub orphans
        orphans = [
            {
                "node": name,
                "ref_count": node.in_degree,
                "edge_count": node.out_degree,
                "referenced_by": node.referencing_notes[:5],
            }
            for name, node in graph.items()
            if node.in_degree >= min_refs and node.out_degree <= max_edges
        ]

        # Sort by most referenced
        orphans.sort(key=lambda x: x["ref_count"], reverse=True)
        return orphans

    async def get_tagged_notes(self, tag: str, limit: int = 20) -> list[dict[str, Any]]:
        """Find notes containing a specific #tag."""
        if not self._vault or not self._vault.exists():
            return []

        results: list[dict[str, Any]] = []
        pattern = re.compile(rf"#{re.escape(tag)}\b", re.IGNORECASE)

        for md_file in self._vault.rglob("*.md"):
            if len(results) >= limit:
                break
            try:
                content = md_file.read_text(encoding="utf-8", errors="ignore")
                if pattern.search(content):
                    # Extract title from first heading
                    title = md_file.stem
                    h1 = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
                    if h1:
                        title = h1.group(1).strip()

                    # Extract all tags
                    tags = re.findall(r"#([\w一-鿿-]+)", content)

                    results.append({
                        "path": str(md_file.relative_to(self._vault)),
                        "title": title,
                        "content": content[:500],
                        "tags": list(set(tags))[:10],
                    })
            except Exception:
                pass

        return results

    async def to_motif_candidates(self, limit: int = 5) -> list[MotifCandidate]:
        """Convert top knowledge gaps to motif candidates."""
        gaps = await self.analyze()
        candidates: list[MotifCandidate] = []

        for g in gaps[:limit]:
            node = g["node"]
            ref_count = g["ref_count"]
            candidates.append(MotifCandidate(
                source=MotifSource.KNOWLEDGE_GAP,
                title=f"如何将'{node}'与相关知识体系深度连接",
                description=(
                    f"'{node}' 在你的知识库中被引用了 {ref_count} 次，"
                    f"但仅有 {g['edge_count']} 条外链。"
                    f"这说明它是你的思维枢纽之一，但尚未被充分探索。"
                    f"被以下笔记引用：{', '.join(g.get('referenced_by', [])[:3])}"
                ),
            ))

        return candidates

    # ── Internal ───────────────────────────────────────────────────

    def _build_graph(self, max_notes: int = 500) -> dict[str, GraphNode]:
        """Parse all .md files and build [[wikilink]] graph."""
        graph: dict[str, GraphNode] = defaultdict(lambda: GraphNode(name=""))
        count = 0

        for md_file in self._vault.rglob("*.md"):
            if count >= max_notes:
                break
            if md_file.name.startswith(".") or md_file.name.startswith("00-"):
                continue

            try:
                content = md_file.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            note_name = md_file.stem
            if note_name not in graph:
                graph[note_name] = GraphNode(name=note_name)

            # Extract all [[outgoing links]]
            out_links = re.findall(r"\[\[([^\]|#]+)(?:[|#][^\]]+)?\]\]", content)

            # Count outgoing links for THIS note (as a source)
            graph[note_name].out_links = list(set(out_links))
            graph[note_name].out_degree = len(graph[note_name].out_links)

            # For each out link, increment the TARGET's in-degree
            for target in out_links:
                target_clean = target.strip()
                if target_clean not in graph:
                    graph[target_clean] = GraphNode(name=target_clean)
                graph[target_clean].in_degree += 1
                if note_name not in graph[target_clean].referencing_notes:
                    graph[target_clean].referencing_notes.append(note_name)

            count += 1

        return dict(graph)
