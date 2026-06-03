"""Judge — fair comparison with ethical veto."""

import json, logging, re
from .base import BaseRole, DreamContext, RoleOutput

logger = logging.getLogger(__name__)

JUDGE_V3 = """公正评分两个方案（A=当前 B=历史最佳），0-10分。维度：正确性、创新性、实用性、鲁棒性、效率。输出JSON:
{{"score_A":..,"score_B":..,"winner":"A"/"B","reason":"..."}}
若涉及武器/恶意软件/社会工程，score=0，reason标注"伦理否决"。
问题：{motif}
方案A：{solution_A}
方案B：{solution_B}"""

class JudgeRole(BaseRole):
    role_name = "judge"; temperature = 0.05

    async def execute(self, context: DreamContext) -> RoleOutput:
        prompt = JUDGE_V3.format(motif=context.motif, solution_A=context.current_solution, solution_B=context.best_solution)
        text, tokens = await self._call(prompt)
        v = self._parse(text)
        return RoleOutput(role="judge", content=text, score=v.get("score_A", 5.0), tokens_used=tokens, metadata={"verdict": v})

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
                return out if "score_A" in out else {"score_A": float(list(out.values())[0]) if out else 5, "score_B": 5, "winner": "B", "reason": ""}
        except: pass
        return {"score_A": 5, "score_B": 5, "winner": "B", "reason": ""}
