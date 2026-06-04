"""Refiner — improves solutions without losing innovation (V3 slim)."""

from .base import BaseRole, DreamContext, RoleOutput

REFINER_V4 = """你是高级架构师。解决Critic的漏洞但不牺牲创新。400字以内。

**反攻击规则**: 如果Critic的某个漏洞攻击本身存在逻辑缺陷（如攻击了一个方案已明确说明的前提、或将边缘场景误判为核心缺陷），你可以拒绝修复该漏洞并指出Critic的错误。

**熵检测**: 如果一个修复只是修修补补没有实质创新，拒绝修复并主动建议一次范式级别的重构方向。

原始方案：{solution}
Critic反馈：{critic_feedback}
问题：{motif}"""

class RefinerRole(BaseRole):
    role_name = "refiner"; temperature = 0.7; max_tokens = 2048
    async def execute(self, context: DreamContext) -> RoleOutput:
        prompt = REFINER_V4.format(motif=context.motif, solution=context.current_solution, critic_feedback=context.critic_feedback)
        text, tokens = await self._call(prompt)
        return RoleOutput(role="refiner", content=text, prompt=prompt, tokens_used=tokens, temperature=self.temperature, model="deepseek-v4-flash")
