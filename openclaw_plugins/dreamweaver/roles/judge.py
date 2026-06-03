"""Judge — fair comparison with ethical veto."""

import json, logging, re
from .base import BaseRole, DreamContext, RoleOutput

logger = logging.getLogger(__name__)

JUDGE_V4 = """公正评分两个方案（A=当前 B=历史最佳），0-10分。输出JSON:
{{"score_A":..,"score_B":..,"winner":"A"/"B","reason":"...","confidence":..}}

评分维度权重（当前第{round}轮）:
{weight_text}

**反锚定规则**：只基于方案自身质量评分。
若涉及武器/恶意软件/社会工程，score=0，reason标注"伦理否决"。

母题：{motif}
方案A：{solution_A}
方案B：{solution_B}"""

class JudgeRole(BaseRole):
    role_name = "judge"; temperature = 0.05; max_tokens = 640

    @staticmethod
    def _weights_for_round(round_num: int) -> dict:
        """Dynamic dimension weights per PRD V1.1 §2.3."""
        if round_num <= 3:
            return {"innovation": 1.5, "correctness": 1.0, "practicality": 0.8, "robustness": 0.8, "efficiency": 0.8}
        return {"innovation": 0.8, "correctness": 1.2, "practicality": 1.5, "robustness": 1.5, "efficiency": 1.0}

    async def execute(self, context: DreamContext) -> RoleOutput:
        r = context.current_round
        w = self._weights_for_round(r)
        weight_text = "\n".join([f"  {k}: ×{v}" for k, v in w.items()])

        prompt = JUDGE_V4.format(motif=context.motif, solution_A=context.current_solution,
                                  solution_B=context.best_solution, round=r, weight_text=weight_text)
        text, tokens = await self._call(prompt)
        v = self._parse(text)
        return RoleOutput(role="judge", content=text, prompt=prompt, score=v.get("score_A", 6.0),
                          tokens_used=tokens, temperature=self.temperature, model="deepseek-v4-pro",
                          metadata={"verdict": v})

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
