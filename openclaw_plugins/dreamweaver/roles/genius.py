"""Genius — generates radical, innovative solutions."""

from __future__ import annotations

from .base import BaseRole, DreamContext, RoleOutput

GENIUS_PROMPT_V2 = """你是创新突破专家。你的任务不是提出"更好的方案"，而是提出一个**让该领域专家皱眉然后眼睛一亮**的方案。

核心约束：
- 禁止使用"方案A+方案B"的组合式创新。必须从第一性原理重新推导问题的本质。
- 在你的方案中至少包含一个**违反直觉的核心机制**——某件让读者第一反应是"这不可能"但细想后"好像有道理"的事。
- 激进创新的边界是已知科学原理和逻辑一致性。你不能通过否定物理定律来获得创新。
- 必须包含：具体技术路径、关键算法的伪代码思路、预期效果对比矩阵。

问题：{motif}
之前最佳方案参考（如有）：{best_solution_summary}
请输出完整方案文档。"""


class GeniusRole(BaseRole):
    role_name = "genius"
    temperature = 0.85  # Higher creativity

    async def execute(self, context: DreamContext) -> RoleOutput:
        prompt = GENIUS_PROMPT_V2.format(
            motif=context.motif,
            best_solution_summary=context.best_solution_summary,
        )
        text, tokens = await self._call(prompt)
        return RoleOutput(role="genius", content=text, tokens_used=tokens)
