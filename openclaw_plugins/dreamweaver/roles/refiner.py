"""Refiner — improves solutions without losing innovation (V3 slim)."""

from .base import BaseRole, DreamContext, RoleOutput

REFINER_V3 = """你是高级架构师。解决Critic指出的漏洞但不牺牲创新。300字以内。
规则：忽略次要问题;修复代价是核心创新则拒绝。
原始方案：{solution}
Critic反馈：{critic_feedback}
问题：{motif}"""

class RefinerRole(BaseRole):
    role_name = "refiner"; temperature = 0.7; max_tokens = 2048
    async def execute(self, context: DreamContext) -> RoleOutput:
        prompt = REFINER_V3.format(motif=context.motif, solution=context.current_solution, critic_feedback=context.critic_feedback)
        text, tokens = await self._call(prompt)
        return RoleOutput(role="refiner", content=text, prompt=prompt, tokens_used=tokens, temperature=self.temperature, model="deepseek-v4-flash")
