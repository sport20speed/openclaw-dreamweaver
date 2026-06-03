"""Genius — radical solution generator (V3 slim)."""

from .base import BaseRole, DreamContext, RoleOutput

GENIUS_V3 = """你是创新突破专家。从第一性原理推导问题本质，提出激进方案。简洁回答，控制在500字以内。
规则：禁止A+B组合式创新;至少1个违反直觉的核心机制;含技术路径+效果+优势。
问题：{motif}
参考：{best_solution_summary}"""

class GeniusRole(BaseRole):
    role_name = "genius"; temperature = 0.85; max_tokens = 2048
    async def execute(self, context: DreamContext) -> RoleOutput:
        prompt = GENIUS_V3.format(motif=context.motif, best_solution_summary=context.best_solution_summary or "无")
        text, tokens = await self._call(prompt)
        return RoleOutput(role="genius", content=text, prompt=prompt, tokens_used=tokens, temperature=self.temperature, model="deepseek-v4-flash")
