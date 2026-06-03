"""Critic — finds fatal flaws (V3 slim)."""

from .base import BaseRole, DreamContext, RoleOutput

CRITIC_V4 = """你最严厉的审稿人。输出固定三段式（每段≤150字）：

1. fatal_flaw: 攻击方案逻辑链条中的核心假设——为什么这个假设在当前约束下可能不成立？
2. edge_case: 找出方案在极端场景下失效的条件——在什么边界情况下方案会崩溃？
3. hidden_assumption: 方案依赖但未言明的前提——方案默认了什么不成立的条件？

攻击深度递增规则：
- 第1轮：攻击方案本身的逻辑漏洞
- 第2轮：攻击上一轮 Refiner 的修复方案
- 第3+轮：攻击方案的元假设——问题本身的提问方式是否错误？

当前方案：{current_solution}
问题：{motif}
当前是第{round}轮"""

class CriticRole(BaseRole):
    role_name = "critic"; temperature = 0.75; max_tokens = 1536  # up from 1024 for structured output

    async def execute(self, context: DreamContext) -> RoleOutput:
        prompt = CRITIC_V4.format(motif=context.motif, current_solution=context.current_solution, round=context.current_round)
        text, tokens = await self._call(prompt)
        return RoleOutput(role="critic", content=text, prompt=prompt, tokens_used=tokens, temperature=self.temperature, model="deepseek-v4-flash")
