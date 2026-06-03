"""Refiner — improves solutions without losing innovation (V3 slim)."""

from .base import BaseRole, DreamContext, RoleOutput

REFINER_V3 = """你是高级架构师。解决Critic指出的致命漏洞，但不牺牲核心创新。
规则：选择性忽略次要问题;若修复代价是核心创新，拒绝修复并说明理由。
原始方案：{solution}
Critic反馈：{critic_feedback}
问题背景：{motif}"""

class RefinerRole(BaseRole):
    role_name = "refiner"; temperature = 0.7
    async def execute(self, context: DreamContext) -> RoleOutput:
        prompt = REFINER_V3.format(motif=context.motif, solution=context.current_solution, critic_feedback=context.critic_feedback)
        text, tokens = await self._call(prompt)
        return RoleOutput(role="refiner", content=text, tokens_used=tokens)
