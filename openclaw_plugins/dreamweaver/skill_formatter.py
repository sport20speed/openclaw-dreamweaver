"""Skill formatter — applies khazix-writer and 刘润 styles to dream output.

khazix-writer: 口语化、真诚、有观点的公众号长文风格 → 用于最终方案
wechat-article-pro 刘润风格: 案例+分析+结论、简洁清晰 → 用于五角色对话
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── Skill loader ───────────────────────────────────────────────────

class SkillLoader:
    """Loads .agents skill Markdown files for prompt injection."""

    SKILLS_DIR = Path.home() / ".agents" / "skills"

    @classmethod
    def load(cls, name: str) -> Optional[str]:
        """Load a skill by directory name."""
        path = cls.SKILLS_DIR / name / "SKILL.md"
        if not path.exists():
            logger.warning("Skill not found: %s", path)
            return None
        return path.read_text(encoding="utf-8")

    @classmethod
    def get_khazix_prompt(cls) -> str:
        """Extract khazix-writer core style instructions (abbreviated)."""
        skill = cls.load("khazix-writer") or ""
        if not skill:
            return "请用口语化、有观点、真诚的风格写作"

        # Extract just the style-relevant parts (not the full skill)
        lines = []
        capture = False
        for line in skill.split("\n"):
            if "风格一句话概括" in line or "核心价值观" in line or "语言风格要求" in line:
                capture = True
            if capture:
                lines.append(line)
            if len(lines) > 80:  # Keep it concise
                break
        return "\n".join(lines) if lines else skill[:2000]

    @classmethod
    def get_liurun_prompt(cls) -> str:
        """Extract 刘润 style instructions from wechat-article-pro."""
        skill = cls.load("wechat-article-pro") or ""
        if not skill:
            return "请用简洁有力、逻辑清晰、观点鲜明的风格，开篇切入，案例论证，结论建议"

        # Extract 刘润 writing characteristics
        lines = []
        capture = False
        for line in skill.split("\n"):
            if "刘润写作特点" in line or "写作风格参考" in line or "结构建议" in line:
                capture = True
            if capture:
                lines.append(line)
            if "禁止事项" in line:
                break
        return "\n".join(lines) if lines else skill[:1500]


# ── Formatter ──────────────────────────────────────────────────────

class SkillFormatter:
    """Wraps dream output sections in skill-style prompts."""

    @staticmethod
    def format_solution(solution: str, motif: str, score: float) -> str:
        """Format the final solution using khazix-writer style."""
        khazix = SkillLoader.get_khazix_prompt()
        header = f"""---
style: khazix-writer
motif: {motif}
score: {score:.1f}
---

> 以下方案按「数字生命卡兹克」公众号长文风格输出。

## 最终方案

"""
        return header + solution

    @staticmethod
    def format_dialogues(logs_text: str) -> str:
        """Format the 5-role dialogues using 刘润 style."""
        liurun = SkillLoader.get_liurun_prompt()
        header = f"""---
style: wechat-article-pro · 刘润风格
---

> 以下对话按「刘润公众号」风格输出——案例切入、数据支撑、清晰结论。

## 五角色完整对话

"""
        return header + logs_text

    @staticmethod
    def get_full_note(result, dialogues_text: str) -> str:
        """Build the complete Obsidian note with both skill formats."""
        solution_section = SkillFormatter.format_solution(
            result.final_solution, result.motif, result.best_score
        )
        dialogue_section = SkillFormatter.format_dialogues(dialogues_text)

        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)

        return f"""---
dream_id: {now.strftime('%Y%m%d')}-{result.motif[:8].strip()}
date: {now.strftime('%Y-%m-%dT%H:%M:%S')}
motif: "{result.motif[:200]}"
score: {result.best_score:.1f}
iterations: {result.total_iterations}
tags: [AI梦境, 自动生成]
convergence_reason: {result.convergence_reason}
---

# 梦境方案：{result.motif[:80]}

## 背景与问题
{result.motif}

{solution_section}

## 演化历程摘要
- 总迭代: {result.total_iterations} 轮
- 最终得分: {result.best_score:.1f}/10
- 结束原因: {result.convergence_reason}

{dialogue_section}

## 行动建议
- [ ] 评审方案可行性
- [ ] 识别可立即应用的部分
- [ ] 如需深入，可基于此方案再次做梦
"""
