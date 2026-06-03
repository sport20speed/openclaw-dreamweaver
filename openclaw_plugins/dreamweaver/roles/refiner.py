"""Refiner — improves solutions without sacrificing innovation."""

from __future__ import annotations

from .base import BaseRole, DreamContext, RoleOutput

REFINER_PROMPT_V2 = """你是一名高级架构师。在不削弱方案核心创新性的前提下，解决 Critic 指出的致命漏洞，输出改进后的完整方案。

关键约束：
- **严禁为了修补漏洞而牺牲创新内核。** 如果 Critic 指出了5个漏洞，你只需要修补其中最致命的2个，其余通过设计规避而非妥协。
- **如果某个漏洞的修复代价是牺牲核心创新**，请明确说明理由并拒绝修复。
- 输出完整的改进方案文档，而非仅列出改了什么。

原始方案：{solution}
Critic反馈：{critic_feedback}
问题背景：{motif}"""


class RefinerRole(BaseRole):
    role_name = "refiner"
    temperature = 0.7

    async def execute(self, context: DreamContext) -> RoleOutput:
        prompt = REFINER_PROMPT_V2.format(
            motif=context.motif,
            solution=context.current_solution,
            critic_feedback=context.critic_feedback,
        )
        text, tokens = await self._call(prompt)
        return RoleOutput(role="refiner", content=text, tokens_used=tokens)
