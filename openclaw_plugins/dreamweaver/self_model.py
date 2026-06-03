"""M4 Lite: Self-Model — domain awareness, token budget, motif filtering.

Answers three questions:
  1. What am I good at? (domain score matrix)
  2. Can I afford this? (token budget check)
  3. Should I accept this motif? (predicted value vs cost)
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class DomainStats:
    domain: str
    avg_score: float = 0.0
    count: int = 0
    avg_tokens: int = 0
    confidence: float = 0.0  # 0-1: how many samples back this up

    def update(self, score: float, tokens: int) -> None:
        self.avg_score = round((self.avg_score * self.count + score) / (self.count + 1), 2)
        self.avg_tokens = int((self.avg_tokens * self.count + tokens) / (self.count + 1))
        self.count += 1
        self.confidence = min(0.95, 0.3 + self.count * 0.05)


# ── Domain classifier (simple keyword-based) ───────────────────────

DOMAIN_KEYWORDS = {
    "技术": ["代码", "编程", "架构", "算法", "性能", "重构", "Python", "JS", "API", "数据库", "SQL", "微服务", "容器", "Docker", "Kubernetes", "CI/CD", "测试", "DevOps", "前端", "后端"],
    "AI/ML": ["AI", "机器学习", "深度学习", "模型", "大模型", "训练", "推理", "向量", "RAG", "prompt", "LLM", "Agent", "NLP", "CV", "transformer", "embedding"],
    "产品": ["用户", "体验", "UX", "UI", "产品", "需求", "迭代", "MVP", "原型", "AB测试", "转化率", "增长", "留存"],
    "效率": ["效率", "工作流", "自动化", "工具", "快捷", "批处理", "脚本", "时间管理", "GTD", "番茄", "专注", "习惯"],
    "商业": ["商业", "创业", "营销", "销售", "融资", "市场", "竞品", "定价", "商业模式", "ROI", "增长", "变现"],
    "创意": ["创意", "设计", "艺术", "写作", "音乐", "灵感", "创新", "头脑风暴", "跨界", "变异"],
    "知识管理": ["知识", "笔记", "Obsidian", "第二大脑", "PKM", "阅读", "学习", "记忆", "卡片", "链接", "图谱"],
}


def classify_motif(motif: str) -> str:
    """Classify a motif into a domain using keyword matching."""
    text = motif.lower()
    scores = {}
    for domain, keywords in DOMAIN_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw.lower() in text)
        if score > 0:
            scores[domain] = score
    return max(scores, key=scores.get) if scores else "通用"


# ── Self Model ─────────────────────────────────────────────────────

@dataclass
class SelfModelSnapshot:
    domain_stats: dict[str, DomainStats] = field(default_factory=dict)
    total_dreams: int = 0
    today_tokens: int = 0
    daily_limit: int = 100_000
    last_updated: str = ""


class SelfModel:
    """Tracks domain performance and manages resource budgets."""

    CREATE_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS self_model_state (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    """

    def __init__(self, db_path: str | None = None, daily_token_limit: int = 100_000) -> None:
        self._db_path = db_path
        self._domains: dict[str, DomainStats] = {}
        self._today_tokens = 0
        self._daily_limit = daily_token_limit
        self._today_date = time.strftime("%Y-%m-%d")
        if db_path:
            self._load()

    def _load(self) -> None:
        try:
            conn = sqlite3.connect(self._db_path)
            conn.execute(self.CREATE_TABLE_SQL)
            row = conn.execute("SELECT value FROM self_model_state WHERE key='domains'").fetchone()
            if row:
                data = json.loads(row[0])
                self._domains = {
                    k: DomainStats(domain=k, avg_score=v["score"], count=v["count"],
                                   avg_tokens=v["tokens"], confidence=v["conf"])
                    for k, v in data.items()
                }
            tok_row = conn.execute("SELECT value FROM self_model_state WHERE key='today_tokens'").fetchone()
            if tok_row:
                saved = json.loads(tok_row[0])
                if saved.get("date") == self._today_date:
                    self._today_tokens = saved.get("tokens", 0)
            conn.close()
        except Exception:
            pass

    def _save(self) -> None:
        if not self._db_path:
            return
        try:
            conn = sqlite3.connect(self._db_path)
            conn.execute(self.CREATE_TABLE_SQL)
            data = {k: {"score": v.avg_score, "count": v.count, "tokens": v.avg_tokens, "conf": v.confidence}
                    for k, v in self._domains.items()}
            conn.execute(
                "INSERT OR REPLACE INTO self_model_state VALUES ('domains', ?)",
                (json.dumps(data, ensure_ascii=False),),
            )
            conn.execute(
                "INSERT OR REPLACE INTO self_model_state VALUES ('today_tokens', ?)",
                (json.dumps({"date": self._today_date, "tokens": self._today_tokens}),),
            )
            conn.commit()
            conn.close()
        except Exception:
            pass

    def should_accept(self, motif: str, estimated_tokens: int = 0) -> tuple[bool, str, dict]:
        """Decide whether to accept a dream motif.

        Returns:
            (accepted: bool, reason: str, context: dict)
        """
        # Reset daily counter if date changed
        today = time.strftime("%Y-%m-%d")
        if today != self._today_date:
            self._today_date = today
            self._today_tokens = 0

        # Check token budget
        if self._daily_limit > 0 and self._today_tokens + estimated_tokens > self._daily_limit:
            remaining = self._daily_limit - self._today_tokens
            return (False, f"今日Token预算不足（剩余{remaining}，预估{estimated_tokens}）",
                    {"budget_remaining": remaining})

        # Check domain confidence
        domain = classify_motif(motif)
        ds = self._domains.get(domain)

        if ds and ds.confidence > 0.6 and ds.avg_score < 3.5:
            return (False, f"领域「{domain}」历史均分{ds.avg_score:.1f}（{ds.count}次），预期价值低",
                    {"domain": domain, "avg_score": ds.avg_score})

        context = {
            "domain": domain,
            "domain_avg_score": ds.avg_score if ds else 0,
            "domain_confidence": ds.confidence if ds else 0,
            "estimated_tokens": estimated_tokens,
            "budget_remaining": self._daily_limit - self._today_tokens,
        }
        return (True, "", context)

    def record(self, motif: str, score: float, tokens: int) -> None:
        """Record a dream outcome to update domain stats and token counter."""
        domain = classify_motif(motif)
        if domain not in self._domains:
            self._domains[domain] = DomainStats(domain=domain)
        self._domains[domain].update(score, tokens)
        self._today_tokens += tokens
        self._save()
        logger.info("M4: recorded %s/%s score=%.1f tokens=%d", domain, motif[:50], score, tokens)

    def snapshot(self) -> dict[str, Any]:
        """Return current self-model state."""
        return {
            "domains": {k: {"avg_score": v.avg_score, "count": v.count, "confidence": v.confidence}
                        for k, v in sorted(self._domains.items(), key=lambda x: x[1].avg_score, reverse=True)},
            "total_dreams": sum(d.count for d in self._domains.values()),
            "today_tokens": self._today_tokens,
            "daily_limit": self._daily_limit,
            "budget_pct": round(self._today_tokens / self._daily_limit * 100, 1) if self._daily_limit else 0,
        }
