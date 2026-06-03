"""Judge — fair, evidence-based comparison with ethical veto."""

from __future__ import annotations

import json
import logging
import re

from .base import BaseRole, DreamContext, RoleOutput

logger = logging.getLogger(__name__)

JUDGE_PROMPT_V2 = """你是一位公正的专家评委。阅读同一个问题的两个方案（方案A vs 方案B），根据以下三维度进行综合评分：

评分维度（每项0-10分）：
1. **概念新颖度** — 方案是否使用了非传统机制？是否打破了领域内默认假设？
2. **假设突破度** — 是否挑战了问题域内的隐含约束？是否从第一性原理出发？
3. **实用转化率** — 从概念到可执行的距离有多近？是否包含具体路径？

问题：{motif}
方案A（当前方案）：{solution_A}
方案B（历史最佳）：{solution_B}

输出标准 JSON（不要包含任何其他文字）：
{{"score_A": <总分0-10>, "score_B": <总分0-10>, "winner": "A"/"B", "reason": "<详细胜负分析，必须基于具体证据>",
 "novelty_A": <0-10>, "breakthrough_A": <0-10>, "practicality_A": <0-10>,
 "novelty_B": <0-10>, "breakthrough_B": <0-10>, "practicality_B": <0-10>}}

**伦理否决：** 如果任一方案涉及武器、恶意软件、社会工程攻击、大规模监控、生物武器或不道德内容，对应方案的所有维度分必须为0，且 reason 中注明"伦理否决：<具体原因>"。"""


class JudgeRole(BaseRole):
    role_name = "judge"
    temperature = 0.05  # Near-deterministic for consistency

    async def execute(self, context: DreamContext) -> RoleOutput:
        prompt = JUDGE_PROMPT_V2.format(
            motif=context.motif,
            solution_A=context.current_solution,
            solution_B=context.best_solution,
        )
        text, tokens = await self._call(prompt)
        verdict = self._parse(text)
        return RoleOutput(
            role="judge",
            content=text,
            score=verdict.get("score_A", 5.0),
            tokens_used=tokens,
            metadata={"verdict": verdict},
        )

    @staticmethod
    def _parse(response: str) -> dict:
        """Extract JSON verdict robustly."""
        json_match = re.search(r"\{[\s\S]*?\}", response)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except (json.JSONDecodeError, ValueError, TypeError):
                pass
        try:
            return json.loads(response)
        except (json.JSONDecodeError, ValueError, TypeError):
            logger.warning("Failed to parse Judge response, using defaults")
            return {"score_A": 5.0, "score_B": 5.0, "winner": "B", "reason": "解析失败"}
