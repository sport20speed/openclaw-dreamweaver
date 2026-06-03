"""Critic — finds fatal flaws (V3 slim)."""

from .base import BaseRole, DreamContext, RoleOutput

CRITIC_V3 = """你最严厉的审稿人。攻击方案核心假设，找出≥3个致命漏洞。200字以内。
规则：攻击逻辑结构和核心假设;不攻击行文风格。
当前方案：{current_solution}
问题：{motif}"""

class CriticRole(BaseRole):
    role_name = "critic"; temperature = 0.75; max_tokens = 1024
    async def execute(self, context: DreamContext) -> RoleOutput:
        prompt = CRITIC_V3.format(motif=context.motif, current_solution=context.current_solution)
        text, tokens = await self._call(prompt)
        return RoleOutput(role="critic", content=text, tokens_used=tokens)
