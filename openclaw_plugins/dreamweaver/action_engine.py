"""Action suggestion engine — generates concrete steps from dream solutions (Dev Diary §14).

Each step includes:
  - Action: what to do
  - Tool: what tool/library to use
  - Time: estimated effort
  - Criterion: how to know it's done
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Optional

from .self_play import DreamResult, LLMProvider

logger = logging.getLogger(__name__)

ACTION_PROMPT = """你是一个项目执行顾问。阅读以下方案，提取 3-5 个具体、可直接执行的操作步骤。

每条步骤必须包含：
1. 做什么（一句话描述）
2. 用什么工具/库（具体技术栈）
3. 预估耗时
4. 完成标准（如何验证这一步已完成）

问题：{motif}
方案：{solution}

输出标准 JSON 数组（不要其他文字）：
[
  {{"action": "...", "tool": "...", "time": "...", "criterion": "..."}},
  ...
]

要求：
- 步骤必须是可直接复制粘贴执行的操作序列，不是笼统建议
- 优先级排序：最紧急/最重要/最先做的放在第一位
- 每一步之间应该有递进关系"""


@dataclass
class ActionStep:
    action: str
    tool: str = ""
    time: str = "30分钟"
    criterion: str = ""


@dataclass
class ActionPlan:
    motif: str
    steps: list[ActionStep]
    raw: str = ""


class ActionEngine:
    """Extracts executable action plans from dream results."""

    def __init__(self, llm: LLMProvider):
        self._llm = llm

    async def generate(self, result: DreamResult) -> Optional[ActionPlan]:
        """Analyze dream result and produce action steps."""
        prompt = ACTION_PROMPT.format(
            motif=result.motif,
            solution=result.final_solution[:4000],  # Truncate for API limits
        )

        try:
            text, _ = await self._llm.generate(
                system_prompt=prompt, temperature=0.3, max_tokens=1024
            )
            steps = self._parse(text)
            if steps:
                return ActionPlan(motif=result.motif, steps=steps, raw=text)
        except Exception:
            logger.exception("Action engine failed")

        # Fallback: heuristic extraction
        return self._heuristic(result)

    @staticmethod
    def _parse(text: str) -> list[ActionStep]:
        """Parse JSON or markdown list from LLM response."""
        # Try JSON first
        json_match = re.search(r"\[[\s\S]*?\]", text)
        if json_match:
            try:
                data = json.loads(json_match.group(0))
                return [ActionStep(**item) for item in data if isinstance(item, dict)]
            except (json.JSONDecodeError, TypeError):
                pass

        # Try markdown checkbox list
        steps: list[ActionStep] = []
        checkbox = re.findall(r"-\s*\[[ x]\]\s*(.+)", text)
        for line in checkbox[:5]:
            steps.append(ActionStep(action=line.strip()))
        return steps

    @staticmethod
    def _heuristic(result: DreamResult, count: int = 4) -> ActionPlan:
        """Heuristic fallback when LLM is unavailable."""
        # Extract sentences that look actionable (start with verbs)
        sentences = re.split(r"[。.；;]", result.final_solution)
        verbs = r"^(需要|应该|可以|建议|采用|使用|配置|安装|运行|执行|创建|修改|添加|删除|优化)"
        actions = [s.strip() for s in sentences if re.match(verbs, s.strip())][:count]

        if not actions:
            actions = [
                f"评审方案中关于'{result.motif[:30]}'的核心建议",
                "识别方案中可直接应用的技术路径",
                "制定分阶段实施计划",
                "评估资源需求和风险",
            ]

        return ActionPlan(
            motif=result.motif,
            steps=[ActionStep(action=a) for a in actions],
        )

    def to_checklist(self, plan: ActionPlan) -> str:
        """Format ActionPlan as markdown checkbox list for Obsidian."""
        lines = ["## 行动建议\n"]
        for i, step in enumerate(plan.steps, 1):
            tool_info = f" · 工具: {step.tool}" if step.tool else ""
            time_info = f" · 预计: {step.time}" if step.time else ""
            criterion_info = f" · 完成标准: {step.criterion}" if step.criterion else ""
            lines.append(
                f"- [ ] **步骤 {i}:** {step.action}{tool_info}{time_info}{criterion_info}"
            )
        return "\n".join(lines)
