"""Critic — identifies fatal flaws with surgical precision."""

from __future__ import annotations

from .base import BaseRole, DreamContext, RoleOutput

CRITIC_PROMPT_V2 = """你是最严厉的审稿人。你的目标是从根本逻辑、实现可行性、效率、隐含假设、伦理风险、资源消耗、意外后果等维度，找到方案中的致命缺陷。

关键约束：
- 不要指出任何通过简单工程优化就能解决的问题。
- 攻击方案的核心假设——论证为什么这些假设在当前约束下可能不成立。
- 至少找到一条方案的**内部逻辑矛盾**——方案自身不同部分之间存在不一致。
- 你的攻击对象是方案的逻辑结构和核心假设，**不是它的表述方式**。如果一个方案用糟糕的比喻但仍然逻辑自洽，你必须把逻辑作为唯一攻击目标。
- 至少列出5个具体漏洞，说明每个漏洞的严重程度和可能后果。

当前方案：{current_solution}
问题背景：{motif}"""


class CriticRole(BaseRole):
    role_name = "critic"
    temperature = 0.7

    async def execute(self, context: DreamContext) -> RoleOutput:
        prompt = CRITIC_PROMPT_V2.format(
            motif=context.motif,
            current_solution=context.current_solution,
        )
        text, tokens = await self._call(prompt)
        return RoleOutput(role="critic", content=text, tokens_used=tokens)
