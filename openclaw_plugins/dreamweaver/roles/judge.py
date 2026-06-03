"""Judge — fair comparison with ethical veto."""

import json, logging, re
from .base import BaseRole, DreamContext, RoleOutput

logger = logging.getLogger(__name__)

JUDGE_V3 = """公正评分两个方案（A=当前 B=历史最佳），0-10分。维度：正确性、创新性、实用性、鲁棒性、效率。输出JSON:
{{"score_A":..,"score_B":..,"winner":"A"/"B","reason":"..."}}

**反锚定规则**：你只看到两个方案和母题本身。不要假设任何关于迭代次数、历史评分、或对话上下文的信息。仅根据方案自身的质量评分。
若涉及武器/恶意软件/社会工程，score=0，reason标注"伦理否决"。

母题：{motif}
方案A：{solution_A}
方案B：{solution_B}"""

class JudgeRole(BaseRole):
    role_name = "judge"; temperature = 0.05; max_tokens = 512

    async def execute(self, context: DreamContext) -> RoleOutput:
        # ECC anti-anchoring: strip iteration context, only pass solutions + motif
        prompt = JUDGE_V3.format(motif=context.motif, solution_A=context.current_solution, solution_B=context.best_solution)
        text, tokens = await self._call(prompt)
        v = self._parse(text)
        # Default score 6.0 (neutral) instead of 5.0 — avoid anchoring to "below average"
        return RoleOutput(role="judge", content=text, score=v.get("score_A", 6.0), tokens_used=tokens, metadata={"verdict": v})

    @staticmethod
    def _parse(response: str) -> dict:
        try:
            m = re.search(r"\{[\s\S]*?\}", response)
            if m:
                raw = json.loads(m.group(0))
                # Normalize keys (strip quotes that may have been embedded)
                out = {}
                for k, v in raw.items():
                    clean = k.strip().strip('"').strip("'").strip('"').strip("'")
                    out[clean] = v
                return out if "score_A" in out else {"score_A": float(list(out.values())[0]) if out else 6, "score_B": 6, "winner": "B", "reason": ""}
        except: pass
        return {"score_A": 6, "score_B": 6, "winner": "B", "reason": ""}
